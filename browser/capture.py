from playwright.sync_api import Page
from typing import List, Tuple

class BrowserCapture:
    """
    负责浏览器信息的获取，如截图和标签页信息
    """
    @staticmethod
    def get_tabs_info(current_page: Page) -> Tuple[List[Page], str]:
        """
        获取当前上下文中所有标签页的信息
        返回: (所有页面对象列表, 格式化后的字符串展示)
        """
        # 给予浏览器微小的响应时间，确保新开的标签页已注册到 context 中
        current_page.wait_for_timeout(500)
        
        pages = current_page.context.pages
        tabs_info = []
        for i, p in enumerate(pages):
            try:
                # 检查页面是否已关闭
                if p.is_closed():
                    continue
                
                title = p.title()
                url = p.url
                is_current = " (当前)" if p == current_page else ""
                tabs_info.append(f"[{i}] {title} - {url}{is_current}")
            except Exception:
                # 忽略正在关闭或发生异常的页面
                continue
        
        tabs_display = "\n".join(tabs_info)
        return pages, tabs_display
