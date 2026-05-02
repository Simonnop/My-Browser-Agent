from typing import List, Dict, Any, Tuple, Optional

from tools.log import LogTool


def add_history_entry(history: list[dict], entry: dict) -> list[dict]:
    """
    追加一条历史记录，返回新的列表（不修改原列表）。
    """
    return history + [entry]


def should_compress(history: list[dict], max_history: int = 5) -> bool:
    """
    判断是否需要压缩记忆。
    """
    return len(history) > max_history


def compress_history(
    llm_client,
    history: list[dict],
    past_summary: str,
    task: str,
    max_history: int = 5,
) -> Tuple[str, list[dict], Optional[Dict[str, int]]]:
    """
    使用 LLM 压缩记忆：保留最近 2 步，压缩其余的到 past_summary。
    返回: (new_past_summary, new_history, usage)
    """
    if not should_compress(history, max_history):
        return past_summary, history, None

    # 提取需要压缩的历史（保留最近的 2 步作为上下文）
    num_to_compress = len(history) - 2
    to_compress = history[:num_to_compress]
    remaining = history[num_to_compress:]

    # 格式化需要压缩的历史
    history_text = ""
    for entry in to_compress:
        history_text += (
            f"Step {entry['step']}: Thought: {entry['thought']}, "
            f"Action: {entry['action']}, Result: {entry['action_result']}, "
            f"Perception: {entry['status']}\n"
        )

    # 调用 LLM 进行总结
    new_summary, usage = llm_client.ask_for_summary(history_text, past_summary, task)
    return new_summary, remaining, usage


def get_formatted_history(history: list[dict], past_summary: str) -> str:
    """
    格式化全部历史供 LLM 参考。
    """
    lines = [f"【前期任务总结】: {past_summary}", "【近期执行细节】:"]

    if not history:
        lines.append("暂无近期执行记录。")
    else:
        for entry in history:
            lines.append(f"Step {entry['step']}:")
            lines.append(f"  Thought: {entry['thought']}")
            lines.append(f"  Action: {entry['action']} -> {entry['action_result']}")
            lines.append(f"  Final Status: {entry['status']}")

    return "\n".join(lines)


# 保留旧的 AgentMemory 类以兼容非图模式的调用（如 collector）
class AgentMemory:
    """
    Agent 记忆管理类（旧版兼容，LangGraph 模式使用纯函数）
    """
    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
        self.past_summary: str = "暂无更早的历史记录总结。"
        self.collected: List[Dict[str, Any]] = []

    def add_step(self, step: int, thought: str, action: str, action_result: str, perception_status: str):
        self.history.append({
            "step": step,
            "thought": thought,
            "action": action,
            "action_result": action_result,
            "status": perception_status
        })

    def should_compress(self) -> bool:
        return len(self.history) > self.max_history

    def compress(self, llm_client, task: str):
        if not self.should_compress():
            return None
        new_summary, new_history, usage = compress_history(
            llm_client, self.history, self.past_summary, task, self.max_history
        )
        self.past_summary = new_summary
        self.history = new_history
        return usage

    def get_formatted_history(self) -> str:
        return get_formatted_history(self.history, self.past_summary)

    def record_collection(self, task: str, data: List[Dict[str, Any]]):
        if data:
            self.collected.append({"task": task, "items": data})

    def get_collected_context(self, use_collect_info: bool = False, top_k: int = 3) -> str:
        if not use_collect_info:
            return ""
        from tools.collect_store import read_collect_context_text
        return read_collect_context_text()

    def clear(self):
        self.history = []
        self.past_summary = "暂无更早的历史记录总结。"
        self.collected.clear()
