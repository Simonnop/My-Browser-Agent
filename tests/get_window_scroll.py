import asyncio
import json
import io
import time
import colorsys
import os
import subprocess
import socket
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont

# --- 配置区 ---
# 如果是 Windows，请修改为如 "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9222
USER_DATA_DIR = os.path.abspath('./chrome_profile')

# --- 核心 JS：检测可滚动区域 ---
JS_MARK_SCROLLABLE = """
() => {
    const scrollableElements = [];
    const elements = document.querySelectorAll('*');

    elements.forEach(el => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        
        // 1. 基础过滤：不可见或太小的元素不计入
        if (rect.width < 10 || rect.height < 10) return;
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return;

        // 2. 判定逻辑
        const overflowY = style.overflowY;
        const overflowX = style.overflowX;
        
        const hasScrollStyle = (s) => s === 'auto' || s === 'scroll';
        
        // 检查溢出属性 + 实际内容是否超出容器
        const canScrollY = hasScrollStyle(overflowY) && el.scrollHeight > el.clientHeight + 2;
        const canScrollX = hasScrollStyle(overflowX) && el.scrollWidth > el.clientWidth + 2;

        // 3. 特殊处理：根节点（HTML/BODY）代表整个页面的滚动
        const isRoot = el.tagName === 'HTML' || el.tagName === 'BODY';
        const isPageScroll = isRoot && (document.documentElement.scrollHeight > window.innerHeight);

        if (canScrollY || canScrollX || isPageScroll) {
            // 只保留在视口内的滚动区域
            if (rect.bottom < 0 || rect.top > window.innerHeight || 
                rect.right < 0 || rect.left > window.innerWidth) return;

            scrollableElements.push({
                tagName: el.tagName,
                id: el.id || '',
                className: el.className || '',
                x: rect.left,
                y: rect.top,
                w: rect.width,
                h: rect.height,
                area: rect.width * rect.height,
                type: isPageScroll ? 'page' : (canScrollY ? 'vertical' : 'horizontal')
            });
        }
    });

    // 4. 按面积降序排列：确保小的滚动区域（子元素）在绘制时标签不会被大的（父元素）完全挡住
    return scrollableElements.sort((a, b) => b.area - a.area);
}
"""

def get_color_by_type(scroll_type):
    """根据滚动类型返回不同颜色"""
    if scroll_type == 'page':
        return (255, 45, 85)    # 红色：全局滚动
    elif scroll_type == 'vertical':
        return (0, 122, 255)   # 蓝色：纵向局部滚动
    else:
        return (52, 199, 89)    # 绿色：横向局部滚动

def check_browser_running():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', DEBUG_PORT)) == 0

def start_chrome():
    if not check_browser_running():
        print(f"[*] 正在启动浏览器并监听端口 {DEBUG_PORT}...")
        cmd = [
            CHROME_PATH,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={USER_DATA_DIR}",
            "--no-first-run"
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2) 
    else:
        print("[*] 浏览器已在运行，直接接入。")

async def run_som(output_img="scroll_zones.png"):
    start_chrome()
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            print("[*] 正在分析页面滚动区域...")
            
            # 获取设备像素比 (DPR)
            dpr = await page.evaluate("window.devicePixelRatio")
            # 执行滚动区域检测脚本
            elements = await page.evaluate(JS_MARK_SCROLLABLE)
            
            # 截图
            screenshot_bytes = await page.screenshot(type="png", full_page=False)
            img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
            draw = ImageDraw.Draw(img, "RGBA")
            
            try:
                font = ImageFont.truetype("Arial.ttf", int(12 * dpr))
            except:
                font = ImageFont.load_default()

            mapping = {}
            for i, el in enumerate(elements):
                idx = i + 1
                x, y = el['x'] * dpr, el['y'] * dpr
                w, h = el['w'] * dpr, el['h'] * dpr
                
                # 获取类型对应的颜色
                base_color = get_color_by_type(el['type'])
                
                # 绘制半透明填充矩形 (可选，为了清晰增加识别度)
                draw.rectangle([x, y, x + w, y + h], outline=base_color + (255,), width=max(2, int(2*dpr)))
                draw.rectangle([x, y, x + w, y + h], fill=base_color + (30,))
                
                # 绘制标签背景
                label = f"{idx} ({el['type']})"
                label_bbox = draw.textbbox((x, y), label, font=font)
                draw.rectangle(label_bbox, fill=base_color + (255,))
                draw.text((x, y), label, fill="white", font=font)
                
                mapping[idx] = el

            # 按 DPR 压缩到逻辑像素大小
            final_size = (int(img.width / dpr), int(img.height / dpr))
            img = img.resize(final_size, Image.LANCZOS)
            img.save(output_img)
            with open("scroll_mapping.json", "w", encoding="utf-8") as f:
                json.dump(mapping, f, indent=2, ensure_ascii=False)

            print(f"[*] 检测完成！找到 {len(elements)} 个可滚动区域。")
            print(f"[*] 红色: 全局 | 蓝色: 纵向 | 绿色: 横向")
            print(f"[*] 截图保存至: {output_img}")
            
            await browser.close()
            
        except Exception as e:
            print(f"[!] 运行出错: {e}")

if __name__ == "__main__":
    # 可以先手动在浏览器打开一个内容较多的页面（如 B 站、小红书、知乎）
    asyncio.run(run_som())