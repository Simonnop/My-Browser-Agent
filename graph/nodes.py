import json
import base64
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from graph.state import AgentState
from browser.observers import get_som_state, get_scroll_state, get_focus_state
import browser.actions as actions
from browser.actions import format_action_result

import os
from llm.call import invoke_and_parse_llm
from llm.prompt import build_llm_prompt
from utils.log import save_observe_images
from browser.driver import driver

def observe_node(state: AgentState) -> dict:
    """
    负责提取当前浏览器状态：获取 SOM、可滚动区域、当前焦点区域
    """
    print("[Observe] 当前页面扫描和截图标记...")
    som_b64, mapping_str = get_som_state()
    scroll_b64 = get_scroll_state()
    focus_b64 = get_focus_state()
    
    # 记录每个步骤的图片输出
    step = state.get("step_count", 0)
    run_dir = state.get("run_dir", "logs/default")
    save_observe_images(run_dir, step, som_b64, scroll_b64, focus_b64, mapping_str)
    
    page_title = driver.execute_js("document.title")
    page_url = driver.execute_js("window.location.href")

    return {
        "current_som_image": som_b64,
        "current_som_mapping": mapping_str,
        "current_scroll_image": scroll_b64,
        "current_focus_image": focus_b64,
        "current_page_title": page_title,
        "current_page_url": page_url
    }

def think_node(state: AgentState) -> dict:
    """
    负责调用 LLM，分析当前状况，给出下一步的 Action 和更新的 todo.
    """
    print("[Think] LLM 正在思考...")
    prompt = build_llm_prompt(state)
    return invoke_and_parse_llm(prompt, state)

def action_node(state: AgentState) -> dict:
    """
    根据 Think 节点的输出来执行具体的浏览器操作。
    """
    action = state.get("next_action", {})
    action_type_ = action.get("type")
    params = action.get("params", {})
    
    result = ""
    print(f"[Action] 执行操作: {action_type_} with {params}")
    
    if action_type_ == "exit":
        reason = params.get("reason", "任务完成")
        result = f"Task Finished. Reason: {reason}"
    else:
        func_name = f"action_{action_type_}"
        if hasattr(actions, func_name):
            func = getattr(actions, func_name)
            if action_type_ == "click":
                result = func(params, state["current_som_mapping"])
            else:
                result = func(params)
        else:
            result = f"未知操作: {action_type_}"
            
    return format_action_result(state, action_type_, params, result)
