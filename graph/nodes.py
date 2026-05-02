import os
import re
from typing import Optional

from .state import AgentState
from .utils import format_history_entry, get_formatted_history

from agent.llm import LLMClient
from agent.memory import add_history_entry, should_compress
from agent.tools import AgentTools
from browser.capture import BrowserCapture
from browser.table import Indexer
from browser.clean import clean_html
from rag.key_rag import KeyRAG
from rag.space_rag import SpaceRAG
from rag.fusion import FusionModule
from tools.log import LogTool
from tools.save import SaveTool

# 模块级单例，确保 Token 统计跨节点累积
_llm_client: Optional[LLMClient] = None


def _get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


# ───────────────────── perceive ─────────────────────


def perceive_node(state: AgentState) -> dict:
    """
    截图 + 获取页面信息（无 LLM 调用）。
    """
    page = state["page"]
    step = state["step"] + 1

    LogTool.step(step, state["max_steps"])

    # 合并标签页，同步引用
    page = BrowserCapture.ensure_single_tab(page)
    page_info = BrowserCapture.get_page_info(page)
    LogTool.info(page_info)

    # 截图
    screenshot_path = os.path.join("outputs", f"step_{step}.jpg")
    fix_path = os.path.join("outputs", "_current_screen.jpg")
    page.screenshot(path=screenshot_path, animations="disabled", caret="initial")
    page.screenshot(path=fix_path, animations="disabled", caret="initial")
    LogTool.info(f"截图完成: {screenshot_path}")

    return {
        "page": page,
        "step": step,
        "screenshot_path": screenshot_path,
        "page_info": page_info,
    }


# ───────────────── index_and_rag ───────────────────


def index_and_rag_node(state: AgentState) -> dict:
    """
    DOM 索引构建 + 双路 RAG 检索 + 融合。
    使用上一轮 LLM 输出的 focus_point 和 keywords。
    """
    page = state["page"]
    step = state["step"]
    focus_point = state.get("focus_point", [])
    keywords = state.get("keywords", [])

    LogTool.info("正在构建 DOM 索引...")
    indexer = Indexer(page)
    indexer.build_index()

    space_table = indexer.get_space_table()
    key_table = indexer.get_key_table()

    # 清洗 HTML
    html_with_ids = page.content()
    cleaned_html = clean_html(html_with_ids)
    SaveTool.save_text(cleaned_html, os.path.join("outputs", f"step_{step}_cleaned.html"))

    # 双路 RAG
    top_k = int(os.getenv("TOP_K", "3"))
    radius_percent = float(os.getenv("FOCUS_RADIUS_PERCENT", "5.0"))

    space_rag = SpaceRAG(space_table)
    key_rag = KeyRAG(key_table)

    viewport_size = page.viewport_size
    space_nodes = space_rag.search(focus_point, viewport_size, radius_percent=radius_percent)
    key_nodes = key_rag.search(keywords, top_k=top_k)

    LogTool.info(f"RAG 检索完成: 空间命中 {len(space_nodes)} 个, 语义命中 {len(key_nodes)} 个")

    # 融合
    path_depth = int(os.getenv("PATH_DEPTH", "2"))
    fusion = FusionModule(cleaned_html)
    local_html = fusion.fuse(key_nodes, space_nodes, path_depth=path_depth)

    return {
        "space_nodes": space_nodes,
        "key_nodes": key_nodes,
        "local_html": local_html,
    }


# ───────────────────── decide ──────────────────────


def decide_node(state: AgentState) -> dict:
    """
    主 LLM 决策：接收截图 + 局部 HTML，输出 Thought + focus_point + keywords + Action。
    """
    step = state["step"]
    max_steps = state["max_steps"]
    task = state["task"]
    screenshot_path = state["screenshot_path"]
    local_html = state["local_html"]
    history = state.get("history", [])
    past_summary = state.get("past_summary", "暂无更早的历史记录总结。")

    history_str = get_formatted_history(history, past_summary)

    LogTool.info("正在思考下一步行动...")
    llm = _get_llm()

    raw_response, usage = llm.ask_decide(
        screenshot_path=screenshot_path,
        task=task,
        step=step,
        max_steps=max_steps,
        local_html=local_html,
        history=history_str,
        save_prompt_path=os.path.join("outputs", f"step_{step}_decide_prompt.txt"),
    )

    # 解析输出
    thought = _extract_field(raw_response, "Thought") or "无思考过程"
    focus_point = _extract_focus_point(raw_response)
    keywords = _extract_keywords(raw_response)
    action = _extract_field(raw_response, "Action") or "无动作指令"

    LogTool.action(thought, action)
    LogTool.usage(usage, llm.get_token_usage())

    return {
        "thought": thought,
        "action": action,
        "focus_point": focus_point,
        "keywords": keywords,
    }


# ───────────────── route_action ────────────────────


MAX_HISTORY = 5


def route_action_node(state: AgentState) -> dict:
    """
    执行动作并记录历史。判断是否需要压缩记忆。
    """
    step = state["step"]
    thought = state["thought"]
    action = state["action"]
    page = state["page"]
    history = state.get("history", [])

    is_finish = False
    action_success = False
    action_result = ""

    # 判断 finish
    if "finish(" in action.lower():
        reason_match = re.search(r'finish\(reason="(.+?)"\)', action)
        reason = reason_match.group(1) if reason_match else "任务完成"
        LogTool.info(f"任务完成: {reason}")
        is_finish = True
        action_success = True
        action_result = reason
    else:
        # 通过工具层执行动作
        tools = AgentTools(page)
        action_success, executed_action, action_result = tools.execute(action)
        page = tools.page
        if not action_success:
            LogTool.error(f"动作执行失败: {action_result}")
        else:
            page.wait_for_timeout(1000)

    # 记录历史（status 字段记录动作是否成功，供下一轮 LLM 验证）
    status = "成功" if action_success else "失败"
    entry = format_history_entry(step, thought, action, action_result, status)
    history = add_history_entry(history, entry)

    return {
        "page": page,
        "action_result": action_result,
        "action_success": action_success,
        "is_finish": is_finish,
        "history": history,
    }


# ─────────────── compress_memory ───────────────────


def compress_memory_node(state: AgentState) -> dict:
    """
    记忆压缩：当 history 过长时，调用 LLM 压缩历史。
    """
    history = state.get("history", [])
    past_summary = state.get("past_summary", "暂无更早的历史记录总结。")
    task = state["task"]

    if not should_compress(history, MAX_HISTORY):
        return {}

    LogTool.info("正在压缩历史记忆...")
    from agent.memory import compress_history as do_compress
    llm = _get_llm()
    new_summary, new_history, usage = do_compress(llm, history, past_summary, task, MAX_HISTORY)

    if usage:
        LogTool.usage(usage, llm.get_token_usage())

    return {
        "past_summary": new_summary,
        "history": new_history,
    }


# ─────────────── 内部工具函数 ──────────────────────


def _extract_field(text: str, field_name: str) -> str:
    """从 LLM 输出中提取指定字段的值。"""
    match = re.search(rf'{field_name}:\s*(.+)', text)
    if match:
        return match.group(1).strip()
    return ""


def _extract_focus_point(text: str) -> list:
    """提取 focus_point 坐标。"""
    match = re.search(r'focus_point:\s*\[([^\]]+)\]', text)
    if match:
        try:
            coords = [float(x.strip()) for x in match.group(1).split(",")]
            if len(coords) == 2:
                return coords
        except ValueError:
            pass
    return []


def _extract_keywords(text: str) -> list:
    """提取 keywords 列表。"""
    match = re.search(r'keywords:\s*\[([^\]]+)\]', text)
    if match:
        try:
            raw = match.group(1)
            # 去掉引号并分割
            kws = [w.strip().strip('"').strip("'") for w in raw.split(",")]
            return [w for w in kws if w]
        except Exception:
            pass
    return []
