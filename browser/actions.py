import json
import time
import os
from browser.driver import driver
from graph.state import AgentState
from langchain_core.messages import HumanMessage

def format_action_result(state: AgentState, action_type_: str, params: dict, result: str) -> dict:
    action_desc = f"Action: {action_type_}"
    if params:
        action_desc += f" with {params}"
    
    page_title = state.get("current_page_title", "")
    page_url = state.get("current_page_url", "")
    
    content_parts = []
    if page_url:
        content_parts.append(f"当前页面: {page_title}\n页面 URL: {page_url}")
    content_parts.append(action_desc)
    content_parts.append(f"执行结果: {result}")
    
    new_msg = HumanMessage(content="\n".join(content_parts))
    
    return {
        "messages": [new_msg],
        "step_count": state.get("step_count", 0) + 1,
        "is_finished": (action_type_ == "exit" or state.get("step_count", 0) >= state.get("max_steps", 10))
    }

def action_click(params: dict, som_mapping_str: str) -> str:
    element_idx = str(params.get("element_id"))
    mapping = json.loads(som_mapping_str)
    if element_idx not in mapping:
        return f"Error: 元素编号 {element_idx} 不在当前的SOM映射中。"
    el = mapping[element_idx]
    x, y, w, h = el['x'], el['y'], el['w'], el['h']
    cx, cy = x + w/2, y + h/2
    
    driver.page.mouse.click(cx, cy)
    time.sleep(1) # wait for action result
    return f"成功点击元素 {element_idx} (坐标: {cx}, {cy})"

def action_type(params: dict) -> str:
    text = params.get("text", "")
    delay_ms = int(os.getenv("TYPE_DELAY_MS", "50"))
    driver.page.keyboard.type(text, delay=delay_ms)
    time.sleep(0.5)
    return f"成功在当前焦点输入文本: {text}"

def action_clear(params: dict = None) -> str:
    """清空当前焦点输入框的内容"""
    driver.page.keyboard.press("Meta+A") # Mac
    driver.page.keyboard.press("Backspace")
    time.sleep(0.5)
    return "成功清空当前焦点的输入内容"

def action_scroll(params: dict) -> str:
    """可以扩展为针对选中的区域滚动，比如 scroll(S1, 'down')"""
    direction = params.get("direction", "down")
    amount = int(params.get("amount", 500))
    if direction.lower() == "down":
        driver.page.mouse.wheel(0, amount)
    elif direction.lower() == "up":
        driver.page.mouse.wheel(0, -amount)
        
    time.sleep(1)
    return f"成功向 {direction} 滚动 {amount} 像素"

def action_press_enter(params: dict = None) -> str:
    driver.page.keyboard.press("Enter")
    time.sleep(1)
    return "成功按下 Enter 键"

def action_goto_url(params: dict) -> str:
    url = params.get("url", "")
    try:
        # 如果没有前缀则加上
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
            
        driver.page.goto(url, wait_until="domcontentloaded")
        time.sleep(2)
        return f"成功跳转到网址: {url}"
    except Exception as e:
        return f"访问失败: {e}"

def action_wait(params: dict) -> str:
    """等待指定秒数，用于页面加载、动画完成等场景"""
    seconds = int(params.get("seconds", 3))
    time.sleep(seconds)
    return f"成功等待 {seconds} 秒"

def action_human_intervention(params: dict) -> str:
    """请求人类干预"""
    question = params.get("question", "需要你的帮助：")
    print(f"\n[AI需要干预] {question}")
    answer = input("请输入你的回答(或者直接按回车跳过): ")
    return f"人类的回答是: {answer}"
