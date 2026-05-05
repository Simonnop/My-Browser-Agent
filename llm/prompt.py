from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from graph.state import AgentState

def build_llm_prompt(state: AgentState) -> list:
    """构建包含图片的多模态 Message"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_prompt = f"""你是一个智能浏览器 Agent。你的目标是：
{state['task']}

当前时间：{current_time}

当前你的 TODO List：
{state.get('todo_list', '暂无计划，请你制定。')}

注意：如果你发现自己在多轮操作中反复尝试同一个目标却一直没有成功（例如找不到元素、页面没反应等异常情况），请立刻使用 human_intervention 动作呼叫人工协助，询问人类接下来该怎么做。

注意：遇到登录提示，请立刻使用 human_intervention 动作呼叫人工来登录。

你需要分析当前页面的状态，返回以下 JSON 格式的输出(不要包含多余的字符)：
{{
  "thought": "你的思考过程...",
  "updated_todo_list": "更新后的TODO List...",
  "action": {{
    "type": "click/type/clear/scroll/press_enter/goto_url/wait/human_intervention/exit",
    "params": {{
      // 如果 type=click: "element_id": "1"
      // 如果 type=type: "text": "内容"
      // 如果 type=clear: 这里不需要参数
      // 如果 type=press_enter: 这里不需要参数
      // 如果 type=goto_url: "url": "https://www.google.com"
      // 如果 type=wait: "seconds": 3 (等待页面加载，默认3秒)
      // 如果 type=human_intervention: "question": "你想问的问题"
      // 如果 type=exit: "reason": "任务完成原因"
    }}
  }}
}}
"""
    
    # 构建人类消息，将多模态数据附上
    page_title = state.get('current_page_title', '')
    page_url = state.get('current_page_url', '')
    page_info = f"当前页面: {page_title}\n页面 URL: {page_url}" if page_url else ""
    
    content = [
        {"type": "text", "text": f"以下是当前页面的状态：\n{page_info}\n1. 带可交互元素标注的 Set-Of-Mark (可能会出现多余的非可交互元素，请忽略)"},
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
