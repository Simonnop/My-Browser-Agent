from typing import Optional, Tuple, List
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

    def update_page(self, new_page: Page):
        """
        当发生标签页切换或关闭时，更新当前活跃页面
        """
        self.page = new_page
        self.browser_actions = BrowserActions(new_page)

    def execute(self, action_str: str) -> Tuple[bool, Optional[Page], str, str]:
        """
        执行 Agent 发出的动作指令，支持 "||" 备选方案
        返回: (是否成功, 可能产生的新活跃页面, 执行的动作, 执行结果)
        """
        # 处理备选方案（由 || 分隔）
        candidates = [c.strip() for c in action_str.split("||")]
        
        final_new_page = None
        action_success = False
        last_message = "所有候选动作均执行失败"
        executed_action = candidates[0] # 默认记录首选动作
        
        for i, candidate in enumerate(candidates):
            if len(candidates) > 1:
                LogTool.info(f"正在尝试候选动作 {i+1}/{len(candidates)}: {candidate}")
            else:
                LogTool.info(f"工具层执行动作: {candidate}")
            
            success, new_page, message = self.browser_actions.execute_action(candidate)
            
            if success:
                action_success = True
                last_message = message
                if new_page:
                    LogTool.info("检测到活跃页面发生变更，正在同步工具层状态...")
                    self.update_page(new_page)
                    final_new_page = new_page
                executed_action = candidate
                break
            else:
                LogTool.error(f"候选动作执行失败: {candidate} | 原因: {message}")
                last_message = message
        
        return action_success, final_new_page, executed_action, last_message

    @staticmethod
    def format_action_result(success: bool, action_str: str) -> str:
        """
        格式化动作执行结果，用于反馈给 LLM（如果需要的话）
        """
        status = "成功" if success else "失败"
        return f"动作 [{action_str}] 执行{status}。"
