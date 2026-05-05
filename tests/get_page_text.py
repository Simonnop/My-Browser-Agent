import asyncio
import os
import subprocess
import socket
import time
from playwright.async_api import async_playwright

# --- 配置区 ---
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9222
USER_DATA_DIR = os.path.abspath('./chrome_profile')

def check_browser_running():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', DEBUG_PORT)) == 0

def start_chrome():
    if not check_browser_running():
        print(f"[*] 正在启动浏览器并开启调试端口 {DEBUG_PORT}...")
        cmd = [
            CHROME_PATH,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={USER_DATA_DIR}",
            "--no-first-run"
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)

async def get_all_text(output_file="page_text.txt"):
    start_chrome()
    
    async with async_playwright() as p:
        try:
            # 1. 接入现有浏览器
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            # 2. 注入穿透 Shadow DOM 的纯文本提取脚本
            scanner_js = """
            () => {
                const BLACKLIST = ['SCRIPT', 'STYLE', 'NOSCRIPT', 'HEAD', 'TITLE', 'IFRAME'];
                
                function extractText(node) {
                    let text = "";

                    // 1. 如果是文本节点
                    if (node.nodeType === 3) {
                        return node.textContent.trim() ? node.textContent.trim() + "\\n" : "";
                    }

                    // 2. 如果是元素节点
                    if (node.nodeType === 1) {
                        if (BLACKLIST.includes(node.tagName)) return "";

                        // 处理 Shadow DOM
                        if (node.shadowRoot) {
                            for (let child of node.shadowRoot.childNodes) {
                                text += extractText(child);
                            }
                        }

                        // 处理常规子节点
                        for (let child of node.childNodes) {
                            text += extractText(child);
                        }
                    }
                    return text;
                }

                return extractText(document.body);
            }
            """

            print("[*] 正在提取全页纯文本 (穿透 Shadow DOM)...")
            all_text = await page.evaluate(scanner_js)

            # 3. 简单清洗：去除多余的空行
            cleaned_text = "\\n".join([line for line in all_text.splitlines() if line.strip()])

            # 4. 保存结果
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(cleaned_text)
            
            print(f"[√] 文本提取完成！共 {len(cleaned_text)} 字符。已保存至: {output_file}")

        except Exception as e:
            print(f"[X] 发生错误: {e}")
        finally:
            print("[*] 任务结束。")

if __name__ == "__main__":
    asyncio.run(get_all_text())