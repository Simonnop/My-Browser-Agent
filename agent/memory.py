from typing import List, Dict, Any

class AgentMemory:
    """
    Agent 记忆管理类: 负责记录任务执行的历史过程，并支持总结压缩机制
    """
    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
        self.past_summary: str = "暂无更早的历史记录总结。"

    def add_step(self, step: int, thought: str, actions: List[str], action_results: List[str], perception_status: str):
        """
        添加一个步骤的执行记录，包含多个动作及其结果
        """
        self.history.append({
            "step": step,
            "thought": thought,
            "actions": actions,
            "action_results": action_results,
            "status": perception_status
        })

    def should_compress(self) -> bool:
        """
        判断是否需要压缩记忆
        """
        return len(self.history) > self.max_history

    def compress(self, llm_client):
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
        for entry in to_compress:
            actions_str = ", ".join(entry['actions'])
            results_str = ", ".join(entry['action_results'])
            history_text += f"Step {entry['step']}: Thought: {entry['thought']}, Actions: [{actions_str}], Results: [{results_str}], Perception: {entry['status']}\n"

        # 调用 LLM 进行总结
        new_summary, usage = llm_client.ask_for_summary(history_text, self.past_summary)
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
                for i, (act, res) in enumerate(zip(entry['actions'], entry['action_results'])):
                    lines.append(f"  Action {i+1}: {act} -> {res}")
                lines.append(f"  Final Status: {entry['status']}")
            
        return "\n".join(lines)

    def clear(self):
        """
        清空记忆
        """
        self.history = []
        self.past_summary = "暂无更早的历史记录总结。"
