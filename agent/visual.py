from typing import Dict, Any, List
from .llm import LLMClient

class VisualSubagent:
    """
    视觉预感知子智能体: 分析截图并提取关键信息
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def perceive(self, screenshot_path: str, task_description: str, history: str, save_prompt_path: str = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        分析截图，输出 (感知结果dict, 本次消耗usage_dict)
        """
        return self.llm.ask_visual_subagent(screenshot_path, task_description, history, save_prompt_path=save_prompt_path)
