import json
import base64
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from graph.state import AgentState
from tools.observers import get_som_state, get_scroll_state, get_focus_state
from tools.actions import action_click, action_type, action_clear, action_scroll, action_press_enter, action_goto_url, action_human_intervention

import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# 初始化 LLM 
# 动态加载额外请求体（如关闭特定的思考/搜索标志）
extra_body = {}
if os.getenv("DISABLE_LLM_THINKING") == "true":
    # 兼容常见的关闭大模型自身思考/搜索的 flag，如果有特殊的可以直接写在这里
    extra_body.update({
        "disable_thinking": True, 
        "enable_reasoning": False,
        "reasoning_format": "none",
        "search": False,
        "thinking": {"type": "disabled"}
    })

llm_kwargs = {}
if extra_body:
    llm_kwargs["extra_body"] = extra_body
    
llm = ChatOpenAI(
    model=os.getenv('LLM_MODEL', 'gpt-4o'),
    openai_api_key=os.getenv('LLM_API_KEY'),
    openai_api_base=os.getenv('LLM_BASE_URL'),
    temperature=0,
    **llm_kwargs
)

def observe_node(state: AgentState) -> dict:
    """
    负责提取当前浏览器状态：获取 SOM、可滚动区域、当前焦点区域
    """
    print("[Observe] 当前页面扫描和截图标记...")
    som_b64, mapping_str = get_som_state()
    scroll_b64 = get_scroll_state()
    focus_b64 = get_focus_state()
    
    # 记录每个步骤的图片输出
    step = state.get("step_count", 0)
    run_dir = state.get("run_dir", "logs/default")
    round_dir = os.path.join(run_dir, f"round_{step}")
    os.makedirs(round_dir, exist_ok=True)
    
    if som_b64:
        with open(os.path.join(round_dir, "som_image.png"), "wb") as f:
            f.write(base64.b64decode(som_b64))
    if scroll_b64:
        with open(os.path.join(round_dir, "scroll_image.png"), "wb") as f:
            f.write(base64.b64decode(scroll_b64))
    if focus_b64:
        with open(os.path.join(round_dir, "focus_image.png"), "wb") as f:
            f.write(base64.b64decode(focus_b64))
            
    with open(os.path.join(round_dir, "som_mapping.json"), "w", encoding="utf-8") as f:
        f.write(mapping_str)
    
    return {
        "current_som_image": som_b64,
        "current_som_mapping": mapping_str,
        "current_scroll_image": scroll_b64,
        "current_focus_image": focus_b64
    }

def build_llm_prompt(state: AgentState) -> list:
    """构建包含图片的多模态 Message"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_prompt = f"""你是一个智能浏览器 Agent。你的目标是：
{state['task']}

当前时间：{current_time}

当前你的 TODO List：
{state.get('todo_list', '暂无计划，请你制定。')}

注意：如果你发现自己在多轮操作中反复尝试同一个目标却一直没有成功（例如找不到元素、页面没反应、登录需要验证码或扫码等异常情况），请立刻使用 human_intervention 动作呼叫人工协助，询问人类接下来该怎么做。

你需要分析当前页面的状态，返回以下 JSON 格式的输出(不要包含多余的字符)：
{{
  "thought": "你的思考过程...",
  "updated_todo_list": "更新后的TODO List...",
  "action": {{
    "type": "click/type/clear/scroll/press_enter/goto_url/human_intervention/exit",
    "params": {{
      // 如果 type=click: "element_id": "1"
      // 如果 type=type: "text": "内容"
      // 如果 type=clear: 这里不需要参数
      // 如果 type=press_enter: 这里不需要参数
      // 如果 type=goto_url: "url": "https://www.google.com"
      // 如果 type=human_intervention: "question": "你想问的问题"
      // 如果 type=exit: "reason": "任务完成原因"
    }}
  }}
}}
"""
    
    # 构建人类消息，将多模态数据附上
    content = [
        {"type": "text", "text": "以下是当前页面的状态：\n1. 带可交互元素标注的 Set-Of-Mark"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{state['current_som_image']}"}},
        {"type": "text", "text": "2. 带滚动区域标注的页面"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{state['current_scroll_image']}"}}
    ]
    
    if state['current_focus_image']:
        content.append({"type": "text", "text": "3. 当前有光标聚焦的输入框区域"})
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{state['current_focus_image']}"}})
        
    # 加入历史执行轨迹，以支持 ReAct 逻辑，而不包含之前的巨图
    messages = [SystemMessage(content=system_prompt)]
    
    # 筛选之前的 message history（由于包含太多多模态历史会导致Token超载，我们把历史记录洗成纯文本）
    for msg in state.get("messages", []):
        if isinstance(msg, AIMessage):
            messages.append(AIMessage(content=msg.content))
        elif isinstance(msg, HumanMessage):
            # 去除原有的强结构化字典内容（即曾经的多模态输入），只有纯文本留存
            if isinstance(msg.content, list):
                text_only = "\n".join([item["text"] for item in msg.content if isinstance(item, dict) and item.get("type") == "text"])
                if text_only:
                    messages.append(HumanMessage(content=f"(历史输入)\n{text_only}"))
            else:
                messages.append(HumanMessage(content=msg.content))
                
    # 把本轮的多模态作为最后一条附加进去
    messages.append(HumanMessage(content=content))
        
    return messages

def think_node(state: AgentState) -> dict:
    """
    负责调用 LLM，分析当前状况，给出下一步的 Action 和更新的 TODO.
    """
    print("[Think] LLM 正在思考...")
    prompt = build_llm_prompt(state)
    
    # 构建 log 路径
    step = state.get("step_count", 0)
    run_dir = state.get("run_dir", "logs/default")
    round_dir = os.path.join(run_dir, f"round_{step}")
    os.makedirs(round_dir, exist_ok=True)
    
    # 抽取并保存 prompt (省略超长 base64 防止撑爆看日志的体验)
    prompt_log = []
    for msg in prompt:
        if isinstance(msg, SystemMessage):
            prompt_log.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            clean_content = []
            if isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        clean_content.append({"type": "image_url", "image_url": "data:image/png;base64,<BASE64_IMAGE_OMITTED_IN_LOG>"})
                    else:
                        clean_content.append(item)
                prompt_log.append({"role": "human", "content": clean_content})
            else:
                prompt_log.append({"role": "human", "content": msg.content})
                
    with open(os.path.join(round_dir, "prompt.json"), "w", encoding="utf-8") as f:
        json.dump(prompt_log, f, ensure_ascii=False, indent=2)

    response = llm.invoke(prompt)
    
    # 保存 response
    with open(os.path.join(round_dir, "response.txt"), "w", encoding="utf-8") as f:
        f.write(response.content)
    
    try:
        content = response.content
        
        # 兼容强制带 <think> 输出的大模型（如 DeepSeek-R1 无法强制关掉的情况），人工切分过滤
        if "<think>" in content and "</think>" in content:
            content = content.split("</think>")[-1].strip()
            
        if "```json" in content:
            content = content.split("```json")[-1].split("```")[0].strip()
        data = json.loads(content)
        
        print(f"[LLM Thought]: {data.get('thought')}")
        print(f"[LLM Action]: {data.get('action')}")
        
        return {
            "next_action": data.get("action", {}),
            "todo_list": data.get("updated_todo_list", state.get('todo_list', '')),
            "messages": [AIMessage(content=response.content)],
        }
    except Exception as e:
        print(f"[-] LLM 返回格式解析失败: {e}, Content: {response.content}")
        return {
            "next_action": {"type": "exit", "params": {"reason": "解析失败，异常退出"}},
            "messages": [AIMessage(content=response.content)]
        }

def action_node(state: AgentState) -> dict:
    """
    根据 Think 节点的输出来执行具体的浏览器操作。
    """
    action = state.get("next_action", {})
    action_type_ = action.get("type")
    params = action.get("params", {})
    
    result = ""
    print(f"[Action] 执行操作: {action_type_} with {params}")
    
    if action_type_ == "click":
        el_id = params.get("element_id")
        result = action_click(str(el_id), state["current_som_mapping"])
        
    elif action_type_ == "type":
        text = params.get("text", "")
        result = action_type(text)
        
    elif action_type_ == "clear":
        result = action_clear()
        
    elif action_type_ == "scroll":
        direction = params.get("direction", "down")
        result = action_scroll(direction)
        
    elif action_type_ == "press_enter":
        result = action_press_enter()
        
    elif action_type_ == "goto_url":
        url = params.get("url", "")
        result = action_goto_url(url)
        
    elif action_type_ == "human_intervention":
        question = params.get("question", "需要你的帮助：")
        result = action_human_intervention(question)
        
    elif action_type_ == "exit":
        reason = params.get("reason", "任务完成")
        result = f"Task Finished. Reason: {reason}"
        
    else:
        result = f"未知操作: {action_type_}"
        
    # 将操作结果变成 HumanMessage
    new_msg = HumanMessage(content=f"上一轮动作执行结果: {result}")
    
    return {
        "messages": [new_msg],
        "step_count": state.get("step_count", 0) + 1,
        "is_finished": (action_type_ == "exit" or state.get("step_count", 0) >= state.get("max_steps", 10))
    }
