from .state import AgentState
from .nodes import MAX_HISTORY


def should_continue(state: AgentState) -> str:
    """
    从 perceive 节点决定出口。
    - 超过最大步数 → 结束
    - 否则 → 进入 index_and_rag
    """
    if state["step"] >= state["max_steps"]:
        return "end"
    return "index_and_rag"


def route_after_action(state: AgentState) -> str:
    """
    从 route_action 节点决定出口。
    - finish → 结束
    - 需要压缩 → compress_memory
    - 否则 → 进入下一轮 perceive
    """
    if state.get("is_finish", False):
        return "end"

    history = state.get("history", [])
    if len(history) > MAX_HISTORY:
        return "compress_memory"

    return "perceive"
