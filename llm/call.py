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

import json
from langchain_core.messages import AIMessage
from utils.log import save_think_log

def invoke_and_parse_llm(prompt: list, state: dict) -> dict:
    
    response = llm.invoke(prompt)
    
    step = state.get("step_count", 0)
    run_dir = state.get("run_dir", "logs/default")
    save_think_log(run_dir, step, prompt, response.content)
    
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

