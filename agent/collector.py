import os
from typing import List, Dict, Any, Optional

from tools.log import LogTool
from tools.collect_store import append_collect_chunk


class Collector:
    """
    采集子循环: 内存截图 → 视觉模型提取 → 去重 → 滚动；
    每一轮提取结果追加写入固定文件（见 tools.collect_store.COLLECT_CONTEXT_PATH）。
    """

    MAX_SCROLLS = 10

    def __init__(self, page, llm_client):
        self.page = page
        self.llm = llm_client

    def collect(self, task: str, loop_step: Optional[int] = None) -> List[Dict[str, Any]]:
        all_items: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for i in range(self.MAX_SCROLLS):
            jpeg = self.page.screenshot(
                type="jpeg",
                quality=int(os.getenv("COLLECT_JPEG_QUALITY", "85")),
                animations="disabled",
                caret="initial",
            )

            items = self.llm.extract_from_screenshot_bytes(jpeg, task)
            new_items = self._deduplicate(items, seen)
            # 任意一轮提取结果都写入固定文件（含本轮增量 items）
            append_collect_chunk(task, scroll_index=i, items=list(new_items), loop_step=loop_step)

            if not new_items and i > 0:
                break
            all_items.extend(new_items)

            self.page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
            self.page.wait_for_timeout(500)

        LogTool.info(f"采集完成，共获取 {len(all_items)} 条数据（已写入采集上下文文件）")
        return all_items

    def _deduplicate(self, items: list, seen: set) -> list:
        new_items = []
        for item in items:
            key = str(item)
            if key not in seen:
                seen.add(key)
                new_items.append(item)
        return new_items
