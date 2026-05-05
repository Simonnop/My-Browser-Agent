import base64
import json
import io
from PIL import Image, ImageDraw, ImageFont
from browser.driver import driver

# 导入JS常量
from browser.js_scripts import JS_SET_OF_MARKS, JS_GET_ONLY_FOCUS, JS_MARK_SCROLLABLE
from browser.tools import get_high_contrast_color, get_color_by_type

def _get_base64_image(img: Image.Image) -> str:
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def get_som_state():
    """执行 SOM 标注并返回 base64 截图和元素映射 JSON"""
    dpr = driver.execute_js("window.devicePixelRatio || 1")
    elements = driver.execute_js(JS_SET_OF_MARKS)
    
    screenshot_bytes = driver.screenshot()
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    
    try:
        font = ImageFont.truetype("Arial.ttf", int(15 * dpr))
    except:
        font = ImageFont.load_default()

    mapping = {}
    for i, el in enumerate(elements):
        idx = i + 1
        x, y = el['x'] * dpr, el['y'] * dpr
        w, h = el['w'] * dpr, el['h'] * dpr
        
        color = get_high_contrast_color(i)
        
        # 绘制外框
        draw.rectangle([x, y, x + w, y + h], outline=color + (200,), width=max(1, int(1*dpr)))
        
        # 绘制标签背景
        label = str(idx)
        try:
            label_size = draw.textbbox((0, 0), label, font=font)
        except AttributeError: # Fallback for older PIL
            label_size = (0, 0, *font.getsize(label))
            
        label_w = label_size[2] - label_size[0] + 4
        label_h = label_size[3] - label_size[1] + 4
        
        draw.rectangle([x, y, x + label_w, y + label_h], fill=color + (255,))
        draw.text((x + 2, y), label, fill="white", font=font)
        
        mapping[str(idx)] = el

    final_size = (int(img.width / dpr), int(img.height / dpr))
    img = img.resize(final_size, Image.LANCZOS)
    return _get_base64_image(img), json.dumps(mapping, ensure_ascii=False)

def get_scroll_state():
    """获取可滚动区域的 base64 截图"""
    dpr = driver.execute_js("window.devicePixelRatio || 1")
    elements = driver.execute_js(JS_MARK_SCROLLABLE)
    
    screenshot_bytes = driver.screenshot()
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    
    try:
        font = ImageFont.truetype("Arial.ttf", int(12 * dpr))
    except:
        font = ImageFont.load_default()

    for i, el in enumerate(elements):
        idx = i + 1
        x, y = el['x'] * dpr, el['y'] * dpr
        w, h = el['w'] * dpr, el['h'] * dpr
        
        base_color = get_color_by_type(el['type'])
        
        draw.rectangle([x, y, x + w, y + h], outline=base_color + (255,), width=max(2, int(2*dpr)))
        draw.rectangle([x, y, x + w, y + h], fill=base_color + (30,))
        
        label = f"{idx} ({el['type']})"
        try:
            label_bbox = draw.textbbox((x, y), label, font=font)
        except AttributeError:
            ls = font.getsize(label)
            label_bbox = (x, y, x + ls[0], y + ls[1])

        draw.rectangle(label_bbox, fill=base_color + (255,))
        draw.text((x, y), label, fill="white", font=font)

    final_size = (int(img.width / dpr), int(img.height / dpr))
    img = img.resize(final_size, Image.LANCZOS)
    return _get_base64_image(img)

def get_focus_state():
    """获取当前焦点的截图"""
    dpr = driver.execute_js("window.devicePixelRatio || 1")
    elements = driver.execute_js(JS_GET_ONLY_FOCUS)
    if not elements:
        return "" # No focus
    
    screenshot_bytes = driver.screenshot()
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    
    el = elements[0]
    x, y, w, h = el['x']*dpr, el['y']*dpr, el['w']*dpr, el['h']*dpr
    
    outline_color = (0, 255, 0, 255)
    fill_color = (0, 255, 0, 80)
    draw.rectangle([x, y, x + w, y + h], outline=outline_color, width=max(4, int(4*dpr)))
    draw.rectangle([x, y, x + w, y + h], fill=fill_color)
    
    final_size = (int(img.width / dpr), int(img.height / dpr))
    img = img.resize(final_size, Image.LANCZOS)
    return _get_base64_image(img)
