"""
采集结果固定落盘：所有 collect 内每一轮截图提取的数据追加到同一 JSON 文件，
主 Agent / 提示词通过读取该文件注入上下文。
"""

import json
import os
from typing import Any, Dict, List, Optional

# 默认路径；可通过环境变量 COLLECT_CONTEXT_PATH 覆盖
COLLECT_CONTEXT_PATH = os.getenv(
    "COLLECT_CONTEXT_PATH",
    os.path.join("outputs", "collected", "context.json"),
)


def _load_store() -> Dict[str, Any]:
    if not os.path.isfile(COLLECT_CONTEXT_PATH):
        return {"chunks": []}
    try:
        with open(COLLECT_CONTEXT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"chunks": []}
        chunks = data.get("chunks")
        if not isinstance(chunks, list):
            data["chunks"] = []
        return data
    except (json.JSONDecodeError, OSError):
        return {"chunks": []}


def reset_collect_context() -> None:
    """新任务开始时清空固定采集文件"""
    parent = os.path.dirname(COLLECT_CONTEXT_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(COLLECT_CONTEXT_PATH, "w", encoding="utf-8") as f:
        json.dump({"chunks": []}, f, ensure_ascii=False, indent=2)


def append_collect_chunk(
    task: str,
    scroll_index: int,
    items: List[Dict[str, Any]],
    loop_step: Optional[int] = None,
) -> None:
    """追加一条采集片段（collect 内任意一轮截图提取完成后调用）"""
    os.makedirs(os.path.dirname(COLLECT_CONTEXT_PATH) or ".", exist_ok=True)
    data = _load_store()
    chunk: Dict[str, Any] = {
        "task": task,
        "scroll_index": scroll_index,
        "items": items,
    }
    if loop_step is not None:
        chunk["loop_step"] = loop_step
    data["chunks"].append(chunk)
    with open(COLLECT_CONTEXT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_collect_context_text() -> str:
    """读取固定采集文件全文，供提示词拼接"""
    if not os.path.isfile(COLLECT_CONTEXT_PATH):
        return ""
    try:
        with open(COLLECT_CONTEXT_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""
