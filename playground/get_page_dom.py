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

async def get_page_structure(output_file="universal_structure.txt"):
    start_chrome()
    
    async with async_playwright() as p:
        try:
            # 1. 接入现有浏览器
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            # 2. 注入通用的 Shadow DOM 穿透脚本
            # 该脚本会过滤 script/style/svg 等噪音，只提取结构和文本
            scanner_js = """
            () => {
                const BLACKLIST = ['SCRIPT', 'STYLE', 'SVG', 'PATH', 'NOSCRIPT', 'BR', 'HR', 'LINK', 'META'];
                
                function scan(node, depth = 0) {
                    let res = "";
                    let indent = "  ".repeat(depth);

                    // 处理文本节点
                    if (node.nodeType === 3) { // Node.TEXT_NODE
                        const txt = node.textContent.trim();
                        if (txt) res += `${indent}文本: "${txt}"\\n`;
                    } 
                    // 处理元素节点
                    else if (node.nodeType === 1) { // Node.ELEMENT_NODE
                        if (BLACKLIST.includes(node.tagName)) return "";

                        let tagName = node.tagName.toLowerCase();
                        let id = node.id ? `#${node.id}` : "";
                        let classes = "";
                        if (node.className && typeof node.className === 'string') {
                            classes = "." + node.className.trim().split(/\\s+/).join('.');
                        }

                        res += `${indent}<${tagName}${id}${classes}>\\n`;

                        // 核心：穿透 Shadow DOM
                        if (node.shadowRoot) {
                            res += `${indent}  [Shadow Root]\\n`;
                            for (let child of node.shadowRoot.childNodes) {
                                res += scan(child, depth + 2);
                            }
                        }

                        // 处理常规子节点
                        for (let child of node.childNodes) {
                            res += scan(child, depth + 1);
                        }
                    }
                    return res;
                }

                return scan(document.body);
            }
            """

            print("[*] 正在扫描全页 DOM (穿透 Shadow DOM)...")
            tree_text = await page.evaluate(scanner_js)

            # 3. 保存结果
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(tree_text)
            
            print(f"[√] 结构树扫描完成！已保存至: {output_file}")

        except Exception as e:
            print(f"[X] 发生错误: {e}")
        finally:
            print("[*] 任务结束，保持浏览器连接。")

if __name__ == "__main__":
    asyncio.run(get_page_structure())