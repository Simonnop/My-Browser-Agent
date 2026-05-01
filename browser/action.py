import os
from playwright.sync_api import Page
import time
from typing import Optional, Tuple

class BrowserActions:
    """
    提供基础的浏览器操作
    """
    def __init__(self, page: Page):
        self.page = page
        self.timeout = int(os.getenv("ACTION_TIMEOUT_MS", "3000"))

    def _validate_element(self, agent_id: str, action_type: str):
        """
        验证元素是否合法，例如 div 不能输入文本
        """
        selector = f'[data-agent-id="{agent_id}"]'
        el = self.page.locator(selector)
        
        # 检查是否存在
        if el.count() == 0:
            raise ValueError(f"节点 ID {agent_id} 不存在于当前页面")

        tag_name = el.evaluate("el => el.tagName.toLowerCase()")
        
        if action_type in ["type", "clear", "select"]:
            is_input = el.evaluate("el => el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea' || el.isContentEditable")
            if not is_input and action_type != "select":
                raise ValueError(f"节点 ID {agent_id} (标签: {tag_name}) 不是输入框，无法执行 {action_type} 操作")
            
            if action_type == "select" and tag_name != "select":
                raise ValueError(f"节点 ID {agent_id} (标签: {tag_name}) 不是 select 标签，无法执行选择操作")

    def click(self, agent_id: str):
        """
        根据 data-agent-id 点击元素
        """
        self._validate_element(agent_id, "click")
        selector = f'[data-agent-id="{agent_id}"]'
        self.page.click(selector, timeout=self.timeout)
        # 等待动作完成后的潜在加载
        try:
            self.page.wait_for_load_state("networkidle", timeout=self.timeout)
        except Exception:
            pass

    def type_text(self, agent_id: str, text: str, press_enter: bool = True):
        """
        根据 data-agent-id 输入文本，增强健壮性
        """
        self._validate_element(agent_id, "type")
        selector = f'[data-agent-id="{agent_id}"]'
        
        try:
            # 1. 尝试直接使用 fill
            self.page.fill(selector, text, timeout=self.timeout)
        except Exception:
            # 2. 如果 fill 失败，尝试点击该元素并使用键盘输入
            self.page.click(selector, timeout=self.timeout)
            self.page.keyboard.type(text)
        
        try:
            self.page.wait_for_load_state("networkidle", timeout=self.timeout)
        except Exception:
            pass

    def clear(self, agent_id: str):
        """
        清空输入框文本
        """
        self._validate_element(agent_id, "clear")
        selector = f'[data-agent-id="{agent_id}"]'
        self.page.fill(selector, "", timeout=self.timeout)

    def select(self, agent_id: str, option: str):
        """
        从下拉框选择选项
        """
        self._validate_element(agent_id, "select")
        selector = f'[data-agent-id="{agent_id}"]'
        self.page.select_option(selector, option, timeout=self.timeout)

    def press(self, agent_id: str, key: str):
        """
        在特定元素上按键
        """
        self._validate_element(agent_id, "press")
        selector = f'[data-agent-id="{agent_id}"]'
        self.page.press(selector, key, timeout=self.timeout)

    def hover(self, agent_id: str):
        """
        悬停在特定元素上
        """
        self._validate_element(agent_id, "hover")
        selector = f'[data-agent-id="{agent_id}"]'
        self.page.hover(selector, timeout=self.timeout)
        try:
            self.page.wait_for_load_state("networkidle", timeout=self.timeout)
        except Exception:
            pass

    def goto(self, url: str):
        """
        导航到指定 URL
        """
        self.page.goto(url, timeout=self.timeout * 2) # 页面加载给予双倍时间
        try:
            self.page.wait_for_load_state("networkidle", timeout=self.timeout)
        except Exception:
            pass

    def close_tab(self):
        """
        关闭当前标签页并返回新的活跃页面
        """
        context = self.page.context
        self.page.close()
        remaining_pages = context.pages
        if remaining_pages:
            new_page = remaining_pages[0]
            new_page.bring_to_front()
            return new_page
        return None

    def switch_tab(self, index: int):
        """
        根据索引切换标签页
        """
        pages = self.page.context.pages
        if 0 <= index < len(pages):
            new_page = pages[index]
            new_page.bring_to_front()
            return new_page
        raise ValueError(f"Invalid tab index: {index}")

    def scroll(self, x: int = 0, y: int = 800):
        """
        更稳定的滚动逻辑：优先使用 JS 注入，回退到鼠标滚轮
        """
        try:
            # 1. 尝试使用 JavaScript 滚动（最稳定，不受鼠标焦点影响）
            self.page.evaluate(f"window.scrollBy({{ left: {x}, top: {y}, behavior: 'smooth' }})")
            # 给予平滑滚动一点时间
            self.page.wait_for_timeout(1000)
        except Exception:
            # 2. 如果 JS 失败，尝试模拟物理滚轮
            self.page.mouse.wheel(x, y)
            time.sleep(1)

    def wait(self, seconds: float = 2.0):
        """
        等待一段时间
        """
        time.sleep(seconds)

    def execute_action(self, action_str: str) -> Tuple[bool, Optional[Page], str]:
        """
        解析并执行动作字符串。
        返回: (success: bool, new_page: Optional[Page], message: str)
        """
        import re
        from tools.log import LogTool
        
        try:
            # 1. click(data-agent-id="...")
            click_match = re.match(r'click\(data-agent-id="(\d+)"\)', action_str)
            if click_match:
                agent_id = click_match.group(1)
                self.click(agent_id)
                return True, None, "成功"

            # 2. type(data-agent-id="...", text="...")
            type_match = re.match(r'type\(data-agent-id="(\d+)",\s*text="(.+)"\)', action_str)
            if type_match:
                agent_id = type_match.group(1)
                text = type_match.group(2)
                self.type_text(agent_id, text)
                return True, None, "成功"

            # 3. clear(data-agent-id="...")
            clear_match = re.match(r'clear\(data-agent-id="(\d+)"\)', action_str)
            if clear_match:
                agent_id = clear_match.group(1)
                self.clear(agent_id)
                return True, None, "成功"

            # 4. select(data-agent-id="...", option="...")
            select_match = re.match(r'select\(data-agent-id="(\d+)",\s*option="(.+)"\)', action_str)
            if select_match:
                agent_id = select_match.group(1)
                option = select_match.group(2)
                self.select(agent_id, option)
                return True, None, "成功"

            # 5. press(data-agent-id="...", key="...")
            press_match = re.match(r'press\(data-agent-id="(\d+)",\s*key="(.+)"\)', action_str)
            if press_match:
                agent_id = press_match.group(1)
                key = press_match.group(2)
                self.press(agent_id, key)
                return True, None, "成功"

            # 6. hover(data-agent-id="...")
            hover_match = re.match(r'hover\(data-agent-id="(\d+)"\)', action_str)
            if hover_match:
                agent_id = hover_match.group(1)
                self.hover(agent_id)
                return True, None, "成功"

            # 7. scroll(x=..., y=...)
            scroll_match = re.match(r'scroll\(x=(-?\d+),\s*y=(-?\d+)\)', action_str)
            if scroll_match:
                x = int(scroll_match.group(1))
                y = int(scroll_match.group(2))
                self.scroll(x, y)
                return True, None, "成功"

            # 8. wait(ms=...)
            wait_match = re.match(r'wait\(ms=(\d+)\)', action_str)
            if wait_match:
                ms = int(wait_match.group(1))
                self.wait(ms / 1000.0)
                return True, None, "成功"

            # 9. goto(url="...")
            goto_match = re.match(r'goto\(url="(.+)"\)', action_str)
            if goto_match:
                url = goto_match.group(1)
                self.goto(url)
                return True, None, "成功"

            # 10. switch_tab(index=...)
            switch_match = re.match(r'switch_tab\(index=(\d+)\)', action_str)
            if switch_match:
                index = int(switch_match.group(1))
                new_page = self.switch_tab(index)
                return True, new_page, "成功"
                
            # 11. close_tab()
            close_match = re.match(r'close_tab\(\)', action_str)
            if close_match:
                new_page = self.close_tab()
                return True, new_page, "成功"

            # 12. finish(reason="...")
            finish_match = re.match(r'finish\(reason="(.+)"\)', action_str)
            if finish_match:
                return True, None, "成功"

            msg = f"未识别的动作格式: {action_str}"
            LogTool.error(msg)
            return False, None, "不合法: 格式错误"
        except ValueError as e:
            msg = f"动作不合法: {str(e)}"
            LogTool.error(msg)
            return False, None, f"不合法: {str(e)}"
        except Exception as e:
            msg = f"执行动作时发生错误: {str(e)}"
            LogTool.error(msg)
            return False, None, f"失败: {str(e)}"
