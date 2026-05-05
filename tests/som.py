import asyncio
import json
import io
import time
import colorsys
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw
import os

# --- 核心逻辑：手型+输入框识别，包含区域涵盖删除，并强制层级检测 ---
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
    r, g, b = colorsys.hls_to_rgb(h, 0.5, 0.8)
    return (int(r * 255), int(g * 255), int(b * 255))

async def generate_top_layer_som(url, output_path="som_top_layer.png"):
    async with async_playwright() as p:
        user_data_path = os.path.abspath('/Users/simonnop/Codebase/My-Browser-Agent/chrome_profile')
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_path,
            headless=False,
            viewport={'width': 1280, 'height': 720},
            ignore_default_args=["--enable-automation"]
        )
        page = await browser.new_page()
        await page.goto(url)
        
        print("[*] 页面已加载。按回车开始执行最上层元素标注...")
        input()
        
        start_time = time.time()
        
        elements = await page.evaluate(JS_MARK_TOP_LAYER_ONLY)
        
        screenshot_bytes = await page.screenshot(type="png")
        img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img, "RGBA")
        
        mapping = {}
        for i, el in enumerate(elements):
            idx = i + 1
            x, y, w, h = el['x'], el['y'], el['w'], el['h']
            color = get_high_contrast_color(i)
            
            # 绘制 1px 细边框
            draw.rectangle([x, y, x + w, y + h], outline=color + (160,), width=1)
            
            # 标在左下方
            label = str(idx)
            label_w = len(label) * 8 + 4
            draw.rectangle([x, y + h, x + label_w, y + h + 12], fill=color + (255,))
            draw.text((x + 2, y + h - 1), label, fill="white")
            
            mapping[idx] = el

        img.save(output_path)
        with open("som_mapping.json", "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)

        print(f"[*] 标注完成！当前页面共有 {len(elements)} 个可交互顶层元素。")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(generate_top_layer_som("https://wx.mail.qq.com/home/index?sid=zY1pcYwuNWcuNFZVACxKYQAA#/compose"))