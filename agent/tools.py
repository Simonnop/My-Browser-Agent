from typing import Tuple
from playwright.sync_api import Page
from browser.action import BrowserActions
from tools.log import LogTool

class AgentTools:
    """
    Agent 工具集（中间层）: 暴露给 LLM 调用，并协调 BrowserActions 执行
    """
    def __init__(self, page: Page):
        self.page = page
        self.browser_actions = BrowserActions(page)

    def set_page(self, page: Page):
        """Loop 层合并标签页后，同步 BrowserActions 持有的 Page"""
        self.page = page
        self.browser_actions.page = page

    def execute(self, action_str: str) -> Tuple[bool, str, str]:
        """
        执行 Agent 发出的单条动作指令（若输出中含 ||，仅取第一段，忽略备选）。
        返回: (是否成功, 执行的动作, 执行结果)
        """
        primary = action_str.split("||")[0].strip()
        LogTool.info(f"工具层执行动作: {primary}")

        success, message = self.browser_actions.execute_action(primary)
        if success:
            self.page = self.browser_actions.page
        else:
            LogTool.error(f"动作执行失败: {primary} | 原因: {message}")

        return success, primary, message

    @staticmethod
    def format_action_result(success: bool, action_str: str) -> str:
        """
        格式化动作执行结果，用于反馈给 LLM（如果需要的话）
        """
        status = "成功" if success else "失败"
        return f"动作 [{action_str}] 执行{status}。"
