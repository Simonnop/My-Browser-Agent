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

    def execute(self, action_str: str) -> Tuple[bool, Optional[Page], List[str], List[str]]:
        """
        执行 Agent 发出的动作指令，支持 ";" 分隔多个动作，每个动作支持 "||" 备选方案
        返回: (是否全部成功, 可能产生的新活跃页面, 执行的动作列表, 执行结果列表)
        """
        # 1. 解析多个动作（由分号分隔）
        # 注意：这里假设动作指令内部不会包含分号，或者已经进行了适当的转义
        raw_actions = [a.strip() for a in action_str.split(";") if a.strip()]
        
        all_success = True
        final_new_page = None
        executed_actions = []
        execution_results = []

        for raw_action in raw_actions:
            # 2. 处理备选方案（由 || 分隔）
            candidates = [c.strip() for c in raw_action.split("||")]
            
            action_success = False
            last_message = "所有候选动作均执行失败"
            
            for i, candidate in enumerate(candidates):
                if len(candidates) > 1:
                    LogTool.info(f"正在尝试候选动作 {i+1}/{len(candidates)}: {candidate}")
                else:
                    LogTool.info(f"工具层执行动作: {candidate}")
                
                success, new_page, message = self.browser_actions.execute_action(candidate)
                
                if success:
                    action_success = True
                    if new_page:
                        LogTool.info("检测到活跃页面发生变更，正在同步工具层状态...")
                        self.update_page(new_page)
                        final_new_page = new_page
                    executed_actions.append(candidate)
                    execution_results.append(message)
                    break
                else:
                    LogTool.error(f"候选动作执行失败: {candidate} | 原因: {message}")
                    if i == len(candidates) - 1:
                        executed_actions.append(candidates[0]) # 记录首选动作
                        execution_results.append(message)
            
            if not action_success:
                all_success = False
                continue

        return all_success, final_new_page, executed_actions, execution_results

    @staticmethod
    def format_action_result(success: bool, action_str: str) -> str:
        """
        格式化动作执行结果，用于反馈给 LLM（如果需要的话）
        """
        status = "成功" if success else "失败"
        return f"动作 [{action_str}] 执行{status}。"
