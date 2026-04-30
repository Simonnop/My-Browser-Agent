"""
单轮浏览器 Agent 的「用户消息」拼装。

顺序遵循常见前缀缓存（prefix cache）：越靠前、越跨轮不变的字节越长，
越容易与历史请求共享前缀命中。

层次（自前向后，大致由稳态 → 骤变）：
1. core：system.md + schema.md + rules.md（完全静态，仅随部署变）
2. 契约：本文件常量 STATIC_*（完全静态）
3. task.md：随 task_name 变，同一任务多轮内不变
4. skills.md / attachment.md：全文载入，同一任务多轮内不变（不再按检索词 RAG 裁剪）
5. 页面遥测：URL、Tabs、History、路径等（每轮变）
6. diff / RAG 聚焦：每轮变
7. HTML 正文：每轮变、体积最大，置于最后

段落标题字符串保持稳定，便于服务商按前缀分块缓存。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

# --- 静态前缀：勿在每轮插入时间相关文案 ---

STATIC_RESPONSE_CONTRACT = """## Response contract (fixed)
Return JSON with fields: answer (string), current_focused_task (string), rag_keywords (string), current_focused_html (string), actions (array).

rag_keywords: REQUIRED. Minimal retrieval tokens for the NEXT cycle only — typically ONE field or control name in the task language (e.g. Chinese: 姓名, 手机号, 性别; NOT a full sentence). Never copy current_focused_task verbatim; never use clauses like 「填写…模块…等字段」.

Each action: type in [click, fill, clear, select, press, scroll, wait, goto, switch_tab, exit], plus required fields.
"""

# 稳定小标题，供模型与人类扫读；文本固定以利前缀一致
SECTION_TASK = "## Task (from task.md)\n"
SECTION_SKILLS = "## Task skills (full skills.md)\n"
SECTION_ATTACHMENT = "## Task attachment (full attachment.md)\n"
SECTION_LIVE = "## Live page state\n"
SECTION_DIFF = "## HTML diff from previous cycle\n"
SECTION_RAG_FOCUS = "## HTML RAG focus (top-K snippets from clean_html ±N chars)\n"
SECTION_HTML = "## HTML for this cycle (truncated)\n"


@dataclass(frozen=True)
class CyclePromptDynamic:
    """每轮变化的字段，放在提示词后缀以缩短缓存失效区间。"""

    url: str
    title: str
    tab_lines: List[str]
    active_tab_index: int
    prompt_history: List[Any]
    screenshot_path: Path
    html_file_path: Path
    html_diff: str
    html_rag_focus_block: str
    html_full: str
    html_diff_max_chars: int = 100_000

    def tabs_block(self) -> str:
        return "\n".join(self.tab_lines)


def build_cycle_user_prompt(
    *,
    core_instructions: str,
    task_md: str,
    skills_rag_section: str,
    attachment_rag_section: str,
    dynamic: CyclePromptDynamic,
    add_content: str,
) -> str:
    """按前缀缓存友好顺序拼接一条完整的用户提示词。"""
    parts: List[str] = []

    # 1–2：长静态前缀
    c = (core_instructions or "").strip()
    if c:
        parts.append(c)

    parts.append(STATIC_RESPONSE_CONTRACT.rstrip())

    # 3–4：任务主述（稳）与 RAG 片段（次稳）
    t = (task_md or "").strip()
    if t:
        parts.append(f"{SECTION_TASK}{t}")

    s = (skills_rag_section or "").strip()
    if s:
        parts.append(f"{SECTION_SKILLS}{s}")

    a = (attachment_rag_section or "").strip()
    if a:
        parts.append(f"{SECTION_ATTACHMENT}{a}")

    # 5：页面遥测（每轮变）
    # hist = json.dumps(dynamic.prompt_history, ensure_ascii=False, indent=2)
    hist_parts: List[str] = []
    for i, h in enumerate(dynamic.prompt_history):
        hist_parts.append(f"Cycle {i+1}: {h.get('answer', '')}")
        if "actions" in h:
            hist_parts.append(f"Actions: {h.get('actions', [])}")
    hist = "\n".join(hist_parts)

    diff = dynamic.html_diff
    if dynamic.html_diff_max_chars > 0 and len(diff) > dynamic.html_diff_max_chars:
        diff = diff[: dynamic.html_diff_max_chars] + "\n… (diff truncated)"

    live = (
        "History:\n"
        f"{hist}\n"
        f"Screenshot file: {dynamic.screenshot_path}\n"
        f"HTML file: {dynamic.html_file_path}"
        f"{SECTION_LIVE}"
        f"URL: {dynamic.url}\n"
        f"Title: {dynamic.title}\n"
        "Tabs:\n"
        f"{dynamic.tabs_block()}\n"
        f"Active tab index: {dynamic.active_tab_index}\n"
    )
    parts.append(live)

    # 6–8：大块易变内容置尾
    parts.append(f"{SECTION_DIFF}{diff}")
    parts.append(f"{SECTION_RAG_FOCUS}{dynamic.html_rag_focus_block.strip()}")
    parts.append(f"{SECTION_HTML}{dynamic.html_full}")
    parts.append(f"{add_content}")
    return "\n\n".join(parts)
