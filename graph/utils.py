import re
import os
from typing import Any

from .state import AgentState
from tools.log import LogTool
from tools.save import SaveTool


def create_initial_state(task: str, page: Any, max_steps: int = 10) -> AgentState:
    """
    构建图的初始状态。首回合无上一轮 LLM 输出，
    focus_point 默认为视口中心，keywords 从任务描述中简单提取。
    """
    viewport = page.viewport_size or {"width": 1920, "height": 1080}
    center = [viewport["width"] / 2, viewport["height"] / 2]
    keywords = _extract_keywords_from_task(task)

    # 初始化输出目录
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
    SaveTool.prepare_dir(output_dir, clear=True)
    LogTool.info(f"已清空并初始化输出目录: {output_dir}")

    return AgentState(
        task=task,
        step=0,
        max_steps=max_steps,
        page=page,
        screenshot_path="",
        page_info="",
        focus_point=center,
        keywords=keywords,
        space_nodes=[],
        key_nodes=[],
        local_html="",
        thought="",
        action="",
        action_result="",
        action_success=False,
        is_finish=False,
        history=[],
        past_summary="暂无更早的历史记录总结。",
        token_usage={"total_input_tokens": 0, "total_output_tokens": 0},
    )


def _extract_keywords_from_task(task: str) -> list[str]:
    """
    从任务描述中提取关键词（简单分词：按标点和空白分割，过滤短词）。
    用于首回合 KeyRAG 输入。
    """
    words = re.split(r'[，。、；：""''！？\s,.:;!?\'"()\[\]{}]+', task)
    return [w.strip() for w in words if len(w.strip()) >= 2]


def parse_action(action_str: str) -> tuple[str, dict]:
    """
    解析动作字符串，返回 (动作类型, 参数字典)。
    例如: 'click(data-agent-id="5", by_pos=True)' → ('click', {'agent_id': '5', 'by_pos': True})
    """
    # 提取动作类型
    type_match = re.match(r'(\w+)\(', action_str)
    if not type_match:
        return ("unknown", {})

    action_type = type_match.group(1)
    params: dict[str, Any] = {}

    # 提取参数
    param_str = action_str[len(action_type) + 1:-1] if action_str.endswith(")") else ""
    if not param_str:
        return (action_type, params)

    for m in re.finditer(r'(\w+)=(?:"([^"]*?)"|(\w+))', param_str):
        key = m.group(1)
        val = m.group(2) if m.group(2) is not None else m.group(3)
        # 布尔值转换
        if val == "True":
            val = True
        elif val == "False":
            val = False
        elif val.lstrip("-").isdigit():
            val = int(val)
        params[key] = val

    return (action_type, params)


def format_history_entry(step: int, thought: str, action: str, action_result: str, status: str) -> dict:
    """
    格式化一条历史记录条目。
    """
    return {
        "step": step,
        "thought": thought,
        "action": action,
        "action_result": action_result,
        "status": status,
    }


def get_formatted_history(history: list[dict], past_summary: str) -> str:
    """
    格式化全部历史供 LLM 参考。
    """
    lines = [f"【前期任务总结】: {past_summary}", "【近期执行细节】:"]

    if not history:
        lines.append("暂无近期执行记录。")
    else:
        for entry in history:
            lines.append(f"Step {entry['step']}:")
            lines.append(f"  Thought: {entry['thought']}")
            lines.append(f"  Action: {entry['action']} -> {entry['action_result']}")
            lines.append(f"  Final Status: {entry['status']}")

    return "\n".join(lines)
