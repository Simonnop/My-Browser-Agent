from typing import List, Dict, Any, Optional

from tools.collect_store import read_collect_context_text


class AgentMemory:
    """
    Agent 记忆管理类: 负责记录任务执行的历史过程，并支持总结压缩机制
    """
    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
        self.past_summary: str = "暂无更早的历史记录总结。"
        self.collected: List[Dict[str, Any]] = []

    def add_step(self, step: int, thought: str, action: str, action_result: str, perception_status: str):
        """
        添加一个步骤的执行记录
        """
        self.history.append({
            "step": step,
            "thought": thought,
            "action": action,
            "action_result": action_result,
            "status": perception_status
        })

    def should_compress(self) -> bool:
        """
        判断是否需要压缩记忆
        """
        return len(self.history) > self.max_history

    def compress(self, llm_client, task: str):
        """
        使用 LLM 压缩记忆: 将历史记录合并到 past_summary 中
        """
        if not self.should_compress():
            return None

        # 提取需要压缩的历史（保留最近的 2 步作为上下文，压缩其余的）
        num_to_compress = len(self.history) - 2
        to_compress = self.history[:num_to_compress]
        self.history = self.history[num_to_compress:]

        # 格式化需要压缩的历史
        history_text = ""
        for entry in self.history[:num_to_compress]:
            history_text += f"Step {entry['step']}: Thought: {entry['thought']}, Action: {entry['action']}, Result: {entry['action_result']}, Perception: {entry['status']}\n"

        # 调用 LLM 进行总结
        new_summary, usage = llm_client.ask_for_summary(history_text, self.past_summary, task)
        self.past_summary = new_summary
        
        return usage

    def get_formatted_history(self) -> str:
        """
        获取格式化后的历史记忆字符串，供 LLM 参考
        """
        lines = [f"【前期任务总结】: {self.past_summary}", "【近期执行细节】:"]
        
        if not self.history:
            lines.append("暂无近期执行记录。")
        else:
            for entry in self.history:
                lines.append(f"Step {entry['step']}:")
                lines.append(f"  Thought: {entry['thought']}")
                lines.append(f"  Action: {entry['action']} -> {entry['action_result']}")
                lines.append(f"  Final Status: {entry['status']}")
            
        return "\n".join(lines)

    def record_collection(self, task: str, data: List[Dict[str, Any]]):
        """
        记录一次采集任务的结果
        """
        if data:
            self.collected.append({"task": task, "items": data})

    def get_collected_context(self, use_collect_info: bool = False, top_k: int = 3) -> str:
        """
        当视觉子 Agent 的 use_collect_info 为 true 时，读取固定采集文件全文注入提示词。
        """
        if not use_collect_info:
            return ""
        return read_collect_context_text()

    def clear(self):
        """
        清空记忆
        """
        self.history = []
        self.past_summary = "暂无更早的历史记录总结。"
        self.collected.clear()
