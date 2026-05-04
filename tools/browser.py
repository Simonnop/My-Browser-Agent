import os
import time
from playwright.sync_api import sync_playwright

# 禁用 Playwright 底层 Node.js 的 deprecation 警告（如 url.parse）
os.environ["NODE_OPTIONS"] = "--no-deprecation"

DEBUG_PORT = os.getenv("DEBUG_PORT", "9222")

class BrowserDriver:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(BrowserDriver, cls).__new__(cls)
            cls._instance.playwright = sync_playwright().start()
            cls._instance.browser = None
            cls._instance.page = None
            cls._instance.connect()
        return cls._instance
        
    def connect(self):
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            context = self.browser.contexts[0]
            self.page = context.pages[0] if context.pages else context.new_page()
            
            # 监听新标签页事件 (如果有新标签页打开，自动接管并关闭旧页面)
            context.on("page", self._handle_new_page)
            
            print(f"[*] 已连接到 localhost:{DEBUG_PORT} 的浏览器实例")
        except Exception as e:
            print(f"[-] 无法连接到浏览器, 请确保浏览器已开启 debugging 端口 {DEBUG_PORT}: {e}")

    def _handle_new_page(self, new_page):
        print("\n[*] 检测到新标签页打开，正在自动接管并尝试关闭旧标签页...")
        old_page = self.page
        self.page = new_page
        try:
            if old_page and not old_page.is_closed():
                old_page.close()
                print("[*] 旧标签页已关闭，Agent 控制流成功转移到新标签页。")
        except Exception as e:
            print(f"[-] 关闭旧标签页时出错: {e}")

    def execute_js(self, js, *args):
        return self.page.evaluate(js, *args)

    def wait_for_idle(self, timeout=3000):
        try:
            self.page.wait_for_load_state('networkidle', timeout=timeout)
        except:
            pass # 忽略超时
        
    def screenshot(self):
        self.wait_for_idle()
        return self.page.screenshot(type="png", full_page=False)

driver = BrowserDriver()
