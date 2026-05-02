import os
from playwright.sync_api import Page


class BrowserCapture:
    """
    负责浏览器信息的获取，如截图和当前页面信息；单标签合并在每轮 loop 开头执行。
    """

    @staticmethod
    def ensure_single_tab(page: Page) -> Page:
        """
        同一 BrowserContext 内只保留一个标签页：保留最晚出现在 context.pages 中的一页，其余关闭。
        轮询直至标签数量短暂稳定，避免 target=_blank 等异步新开标签尚未注册到列表。
        """
        ctx = page.context
        timeout_ms = int(os.getenv("TAB_SYNC_TIMEOUT_MS", "8000"))
        interval_ms = int(os.getenv("TAB_SYNC_INTERVAL_MS", "150"))
        stable_need = int(os.getenv("TAB_SYNC_STABLE_ROUNDS", "3"))

        def alive_pages():
            return [p for p in ctx.pages if not p.is_closed()]

        last_count = None
        stable = 0
        elapsed = 0
        while elapsed <= timeout_ms:
            n = len(alive_pages())
            if last_count is None:
                last_count = n
            elif n == last_count:
                stable += 1
                if stable >= stable_need:
                    break
            else:
                stable = 0
                last_count = n
            try:
                page.wait_for_timeout(interval_ms)
            except Exception:
                pass
            elapsed += interval_ms

        alive = alive_pages()
        if len(alive) <= 1:
            return alive[0] if alive else page

        keeper = alive[-1]
        try:
            keeper.bring_to_front()
        except Exception:
            pass

        for p in alive[:-1]:
            try:
                if not p.is_closed():
                    p.close(run_before_unload=False)
            except Exception:
                pass

        # 再收敛一轮：应对 close 失败或关闭过程中又打开页
        alive = alive_pages()
        if len(alive) > 1:
            keeper = alive[-1]
            try:
                keeper.bring_to_front()
            except Exception:
                pass
            for p in alive[:-1]:
                try:
                    if not p.is_closed():
                        p.close(run_before_unload=False)
                except Exception:
                    pass
            alive = alive_pages()

        if len(alive) == 1:
            return alive[0]
        if alive:
            return alive[-1]
        return page

    @staticmethod
    def get_page_info(current_page: Page) -> str:
        """
        返回当前页面标题和 URL 的简短摘要
        """
        try:
            title = current_page.title() or "无标题"
        except Exception:
            title = "无标题"
        try:
            url = current_page.url
        except Exception:
            url = ""
        return f"当前页面: {title} | {url}"

    @staticmethod
    def take_screenshot(current_page: Page, path: str):
        """
        截取当前页面截图
        """
        current_page.screenshot(path=path, animations="disabled", caret="initial")
