import asyncio
import json
import io
import time
import os
import subprocess
import socket
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont

# --- 配置区 ---
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9222
USER_DATA_DIR = os.path.abspath('./chrome_profile')

# --- 逻辑更新：只捕捉当前聚焦的那一个元素 ---
JS_GET_ONLY_FOCUS = """
() => {
    // 1. 递归查找真正获得焦点的最深层元素 (穿透所有 Shadow DOM)
    const getDeepActiveElement = (root = document) => {
        let el = root.activeElement;
        while (el && el.shadowRoot && el.shadowRoot.activeElement) {
            el = el.shadowRoot.activeElement;
        }
        return el;
    };

    const target = getDeepActiveElement();

    // 如果焦点在 body 或 html 上，说明没有聚焦在具体的输入框
    if (!target || target === document.body || target === document.documentElement) {
        return [];
    }

    // 2. 获取该元素的坐标和属性
    const rect = target.getBoundingClientRect();
    
    // 如果元素太小或不可见，可能不是我们要找的
    if (rect.width <= 0 || rect.height <= 0) return [];

    return [{
        tagName: target.tagName,
        className: target.className,
        text: target.innerText || target.value || "",
        x: rect.left,
        y: rect.top,
        w: rect.width,
        h: rect.height
    }];
}
"""

def check_browser_running():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', DEBUG_PORT)) == 0

def start_chrome():
    if not check_browser_running():
        print(f"[*] 正在启动浏览器...")
        if not os.path.exists(USER_DATA_DIR): os.makedirs(USER_DATA_DIR)
        cmd = [CHROME_PATH, f"--remote-debugging-port={DEBUG_PORT}", f"--user-data-dir={USER_DATA_DIR}", "--no-first-run"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)

async def run_som(output_img="single_focus_result.png"):
    start_chrome()
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            # 接入当前正在操作的页面
            page = browser.contexts[0].pages[0]

            print("[*] 正在锁定唯一的焦点元素...")
            dpr = await page.evaluate("window.devicePixelRatio || 1")
            elements = await page.evaluate(JS_GET_ONLY_FOCUS)

            if not elements:
                print("[!] 未检测到任何聚焦的输入元素。请确保你在评论框里点了鼠标且光标在闪烁。")
                await browser.close()
                return

            # 截图
            screenshot_bytes = await page.screenshot(type="png", full_page=False)
            img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
            draw = ImageDraw.Draw(img, "RGBA")
            
            # 绘图标注
            el = elements[0]
            x, y, w, h = el['x']*dpr, el['y']*dpr, el['w']*dpr, el['h']*dpr
            
            # 亮绿色高亮，醒目且适用于大多数网页背景
            outline_color = (0, 255, 0, 255)
            fill_color = (0, 255, 0, 80)
            draw.rectangle([x, y, x + w, y + h], outline=outline_color, width=max(4, int(4*dpr)))
            draw.rectangle([x, y, x + w, y + h], fill=fill_color)

            # 保存（按 DPR 压缩到逻辑像素大小）
            final_size = (int(img.width / dpr), int(img.height / dpr))
            img = img.resize(final_size, Image.LANCZOS)
            img.save(output_img)
            print(f"[*] 成功！已锁定焦点元素: <{el['tagName']}.{el['className'].replace(' ', '.')}>")
            print(f"[*] 标注图片: {output_img}")

            await browser.close()
        except Exception as e:
            print(f"[-] 出错: {e}")

if __name__ == "__main__":
    time.sleep(2)
    asyncio.run(run_som())