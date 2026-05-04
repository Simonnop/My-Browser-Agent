import json
import time
import os
from tools.browser import driver

def action_click(element_idx: str, som_mapping_str: str) -> str:
    mapping = json.loads(som_mapping_str)
    if element_idx not in mapping:
        return f"Error: 元素编号 {element_idx} 不在当前的SOM映射中。"
    el = mapping[element_idx]
    x, y, w, h = el['x'], el['y'], el['w'], el['h']
    cx, cy = x + w/2, y + h/2
    
    driver.page.mouse.click(cx, cy)
    time.sleep(1) # wait for action result
    return f"成功点击元素 {element_idx} (坐标: {cx}, {cy})"

def action_type(text: str) -> str:
    delay_ms = int(os.getenv("TYPE_DELAY_MS", "50"))
    driver.page.keyboard.type(text, delay=delay_ms)
    time.sleep(0.5)
    return f"成功在当前焦点输入文本: {text}"

def action_clear() -> str:
    """清空当前焦点输入框的内容"""
    driver.page.keyboard.press("Meta+A") # Mac
    driver.page.keyboard.press("Backspace")
    time.sleep(0.5)
    return "成功清空当前焦点的输入内容"

def action_scroll(direction: str, amount: int = 500) -> str:
    """可以扩展为针对选中的区域滚动，比如 scroll(S1, 'down')"""
    if direction.lower() == "down":
        driver.page.mouse.wheel(0, amount)
    elif direction.lower() == "up":
        driver.page.mouse.wheel(0, -amount)
        
    time.sleep(1)
    return f"成功向 {direction} 滚动 {amount} 像素"

def action_press_enter() -> str:
    driver.page.keyboard.press("Enter")
    time.sleep(1)
    return "成功按下 Enter 键"

def action_goto_url(url: str) -> str:
    try:
        # 如果没有前缀则加上
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
            
        driver.page.goto(url, wait_until="domcontentloaded")
        time.sleep(2)
        return f"成功跳转到网址: {url}"
    except Exception as e:
        return f"访问失败: {e}"

def action_human_intervention(question: str) -> str:
    """请求人类干预"""
    print(f"\n[AI需要干预] {question}")
    answer = input("请输入你的回答(或者直接按回车跳过): ")
    return f"人类的回答是: {answer}"
