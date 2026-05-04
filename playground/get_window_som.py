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
# 如果是 Mac，通常路径如下；如果是 Windows，请指向 chrome.exe
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9222
USER_DATA_DIR = os.path.abspath('/Users/simonnop/Codebase/My-Browser-Agent/chrome_profile')

JS_MARK_TOP_LAYER_ONLY = """
() => {
    const isVisible = (el, rect) => {
        // if (rect.width < 3 || rect.height < 3) return false;
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };

    // 层级检测：判断元素的中心点是否真的暴露在最上层
    const isTopElement = (el, rect) => {
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        
        // 如果中心点不在视口内，判定为不可见
        if (cx < 0 || cx > window.innerWidth || cy < 0 || cy > window.innerHeight) return false;

        const topEl = document.elementFromPoint(cx, cy);
        if (!topEl) return false;

        // 检查返回的最上层元素是否是当前元素本身或其子/父节点
        return el.contains(topEl) || topEl.contains(el);
    };

    const candidates = [];
    const elements = document.querySelectorAll('*');

    // 1. 初步筛选：鼠标手型或输入框，且必须在最上层
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (el.tagName === 'BODY' || el.tagName === 'HTML') return;

        const isPointer = style.cursor === 'pointer';
        const isInputType = ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);

        if ((isPointer || isInputType) && isVisible(el, rect) && isTopElement(el, rect)) {
            candidates.push({
                tagName: el.tagName,
                x: rect.left,
                y: rect.top,
                w: rect.width,
                h: rect.height,
                area: rect.width * rect.height
            });
        }
    });

    // 2. 坐标区域包含删除逻辑 (INPUT 豁免)
    return candidates.filter((itemB, indexB) => {
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(itemB.tagName)) return true;

        const isCoveredByOthers = candidates.some((itemA, indexA) => {
            if (indexA === indexB) return false;
            
            const aCoversB = (
                itemB.x >= itemA.x - 0.5 &&
                itemB.y >= itemA.y - 0.5 &&
                (itemB.x + itemB.w) <= (itemA.x + itemA.w) + 0.5 &&
                (itemB.y + itemB.h) <= (itemA.y + itemA.h) + 0.5
            );

            return aCoversB && (itemA.area > itemB.area);
        });

        return !isCoveredByOthers;
    });
}
"""

def get_high_contrast_color(index):
    h = (index * 0.618033988749895) % 1
    r, g, b = colorsys.hls_to_rgb(h, 0.4, 0.8)
    return (int(r * 255), int(g * 255), int(b * 255))

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

async def run_som(output_img="som_result.png"):
    start_chrome()
    
    async with async_playwright() as p:
        # 接入现有浏览器
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()

        print("[*] 页面加载完成。正在计算元素坐标...")
        
        # --- 关键修正：获取 DPR ---
        dpr = await page.evaluate("window.devicePixelRatio")
        elements = await page.evaluate(JS_MARK_TOP_LAYER_ONLY)
        
        # 截图 (仅视口部分)
        screenshot_bytes = await page.screenshot(type="png", full_page=False)
        img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")
        
        # 尝试加载字体，如果不可用则使用默认
        try:
            font = ImageFont.truetype("Arial.ttf", int(15 * dpr))
        except:
            font = ImageFont.load_default()

        mapping = {}
        for i, el in enumerate(elements):
            idx = i + 1
            # 缩放坐标：逻辑像素 * DPR = 物理像素
            x, y = el['x'] * dpr, el['y'] * dpr
            w, h = el['w'] * dpr, el['h'] * dpr
            
            color = get_high_contrast_color(i)
            
            # 绘制外框
            draw.rectangle([x, y, x + w, y + h], outline=color + (200,), width=max(1, int(1*dpr)))
            
            # 绘制标签背景
            label = str(idx)
            label_size = draw.textbbox((0, 0), label, font=font)
            label_w = label_size[2] - label_size[0] + 4
            label_h = label_size[3] - label_size[1] + 4
            
            # 标签放在元素左上角内部，或上方
            draw.rectangle([x, y, x + label_w, y + label_h], fill=color + (255,))
            draw.text((x + 2, y), label, fill="white", font=font)
            
            mapping[idx] = el

        # 按 DPR 压缩到逻辑像素大小
        final_size = (int(img.width / dpr), int(img.height / dpr))
        img = img.resize(final_size, Image.LANCZOS)
        img.save(output_img)
        with open("som_mapping.json", "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

        print(f"[*] 标注成功！共识别 {len(elements)} 个元素。")
        print(f"[*] 截图已保存至: {output_img}")
        
        # 断开连接，但不关闭浏览器
        await browser.close()

if __name__ == "__main__":
    # 以 B 站为例测试
    asyncio.run(run_som())