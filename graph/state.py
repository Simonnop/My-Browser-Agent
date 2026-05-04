from typing import Annotated, TypedDict, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Browser Agent Current State
    """
    # 任务说明与目标
    task: str
    
    # Message History (对话/执行历史)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 页面当前数据 (在 observe 步骤产出)
    current_som_image: str  # base64 或者是文件路径
    current_som_mapping: str # JSON 字符串形式的映射，发给LLM
    current_focus_image: str # 当前光标所在的截图 (base64)
    current_scroll_image: str # 滚动区域截图 (base64)
    
    # Agent 返回的 Function Calls 序列 (用于 actions 节点)
    next_action: dict
    
    # 更新的 TODO List (LLM 每轮都会返回最新的计划)
    todo_list: str
    
    # 控制参数
    step_count: int
    max_steps: int
    is_finished: bool
    run_dir: str
