
import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple

from pathlib import Path
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from agent.embedding import (
    MAX_EMBED_TEXTS,
    build_embedding_cache,
    clip_text,
    cosine_similarity,
    embed_texts,
)
from agent.config import (
    HTML_RAG_BLOCKS_K,
    HTML_RAG_MAX_DEPTH,
    HTML_RAG_WINDOW_N,
    OUTPUT_DIR,
)

# 单次 RAG 写入日志的单类分块条数上限（避免超大 HTML 撑爆文件）
MAX_RAG_LOG_ITEMS = 10000

# 与单次 llm_prompt_{ts}.txt 同周期的 HTML RAG 快照最多保留条数（可多于 k）
HTML_RAG_PROMPT_TOP_K = 15

# 长任务句里典型套话；短检索词里不应出现
_RAG_KW_BAD_FRAGMENTS = (
    "填写",
    "模块",
    "必填字段",
    "个人信息模块",
    "请点击",
    "请选择",
    "附加",
)


def normalize_rag_keywords_for_retrieval(keywords: str, task_hint: str = "") -> str:
    """
    把 LLM 输出的 rag_keywords 或 current_focused_task 收成「检索用词」
    （例如「姓名」「手机号」），便于 embedding 与 rag_scores.query。
    """
    raw_kw = (keywords or "").strip()
    hint = (task_hint or "").strip()

    def _clean_candidate(x: str) -> str:
        x = x.strip()
        if "的" in x:
            x = x.split("的")[-1].strip()
        x = re.sub(r"^(填写|选择|点击|请输入|请|在|往)+", "", x)
        return x.strip(" ：:【】「」()（）")

    def _is_usable_short(x: str) -> bool:
        if not x or len(x) > 20:
            return False
        return not any(b in x for b in _RAG_KW_BAD_FRAGMENTS)

    if raw_kw and _is_usable_short(raw_kw) and len(raw_kw) <= 16:
        return raw_kw[:20]

    text = raw_kw if raw_kw else hint
    if not text:
        return ""

    for part in re.split(r"[、，,]+", text):
        chunk = _clean_candidate(part)
        if not chunk:
            continue
        m = re.match(
            r"^([\u4e00-\u9fff]{1,10}|[a-zA-Z][a-zA-Z0-9\-]{0,20})",
            chunk,
        )
        if not m:
            continue
        cand = m.group(1)
        if _is_usable_short(cand) and "字段" not in cand:
            return cand[:20]

    m = re.search(r"[\u4e00-\u9fff]{2,8}", text)
    if m:
        cand = m.group(0)
        if _is_usable_short(cand):
            return cand

    if raw_kw:
        c = _clean_candidate(raw_kw)
        if c and len(c) <= 16:
            return c[:20]
    if hint:
        c = _clean_candidate(hint)
        if c and len(c) <= 16:
            return c[:20]
    return ""


def _json_safe_score_items(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """将 score 转为 Python float，避免 numpy.float32 导致 json 序列化失败。"""
    out: List[Dict[str, object]] = []
    for it in items:
        row = dict(it)
        if "score" in row:
            row["score"] = float(row["score"])
        out.append(row)
    return out


def html_rag_focus_items(
    items: List[Dict[str, object]],
    top_k: int = HTML_RAG_PROMPT_TOP_K,
) -> List[Dict[str, object]]:
    """对含 score 的条目按分排序取 top_k，并补 rank（用于旧版快照条目）。"""
    if not items or not all("score" in it for it in items):
        return []
    sorted_items = sorted(
        items,
        key=lambda x: float(x.get("score", 0) or 0),
        reverse=True,
    )[:top_k]
    return _json_safe_score_items(
        [{**dict(it), "rank": r} for r, it in enumerate(sorted_items, start=1)]
    )


def format_html_rag_focus_prompt_block(
    query: str,
    items: List[Dict[str, object]],
    *,
    skipped_reason: str = "",
) -> str:
    """
    「HTML RAG 聚焦」：每行 # / k / value / score / offsets，另起一行 chunk。
    """
    lines: List[str] = [
        "### HTML RAG 聚焦内容（得分 Top-K：在 clean_html 中定位节点后，向两侧各截取固定长度）",
        f"- 检索词: {query.strip() or '(无)'}",
    ]
    if skipped_reason:
        lines.append(f"- 说明: {skipped_reason}")
    if not items:
        if not skipped_reason:
            lines.append("- （本步未得到分块或未执行 RAG）")
    else:
        for it in items:
            rk = it.get("rank", "")
            k = it.get("k", rk)
            val = str(it.get("value", "") or "").replace("\n", " ").strip()
            sc = float(it.get("score", 0) or 0)
            chunk = it.get("chunk", it.get("text", ""))
            st = it.get("start")
            en = it.get("end")
            lines.append(
                f"- #{rk} k={k} value={val} score={sc:.4f} offsets=[{st},{en})"
            )
            lines.append(f"  chunk:\n{chunk}")
    return "\n".join(lines)


def save_html_rag_prompt_snapshot(
    dump_path: Optional[Path],
    query: str,
    items: List[Dict[str, object]],
    *,
    status: str = "ok",
    reason: str = "",
    top_k: int = HTML_RAG_PROMPT_TOP_K,
    total_candidates: Optional[int] = None,
) -> None:
    """
    与本轮 llm_prompt 同周期的 HTML RAG 结果写入 JSON。
    items 可为已带 rank/chunk 的块列表，或为旧版需再排序的条目。
    """
    if dump_path is None:
        return
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        tot = total_candidates if total_candidates is not None else len(items)
        payload_items: List[Dict[str, object]] = []
        if status == "ok" and items:
            if all("chunk" in it for it in items):
                cap = items[:top_k] if top_k else items
                payload_items = _json_safe_score_items([dict(x) for x in cap])
            else:
                payload_items = html_rag_focus_items(items, top_k)
        payload: Dict[str, object] = {
            "kind": "html",
            "query": query,
            "status": status,
            "reason": reason,
            "total_candidates": tot,
            "saved_top_k": len(payload_items),
            "items": payload_items,
        }
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"HTML RAG 快照写入失败: {exc}")


def _write_rag_scores(
    kind: str,
    query: str,
    items: List[Dict[str, object]],
    status: str = "ok",
    reason: str = "",
) -> None:
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        payload_items: List[Dict[str, object]] = []
        truncated = False
        total_chunks = len(items)

        if status == "ok" and items and all("score" in it for it in items):
            sorted_items = sorted(
                items,
                key=lambda x: float(x.get("score", 0) or 0),
                reverse=True,
            )
            if len(sorted_items) > MAX_RAG_LOG_ITEMS:
                truncated = True
                sorted_items = sorted_items[:MAX_RAG_LOG_ITEMS]
            payload_items = _json_safe_score_items(
                [{**dict(it), "rank": rank} for rank, it in enumerate(sorted_items, start=1)]
            )
        else:
            payload_items = _json_safe_score_items(list(items))

        payload = {
            "timestamp": timestamp,
            "kind": kind,
            "query": query,
            "status": status,
            "reason": reason,
            "total_chunks": total_chunks,
            "logged_chunks": len(payload_items),
            "truncated": truncated,
            "items": payload_items,
        }
        path = OUTPUT_DIR / "rag_scores.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception as exc:
        print(f"RAG score logging failed: {exc}")
        return

def calculate_similarity(query_embedding: List[float], text_embedding: List[float]) -> float:
    """
    Embedding 相似度计算（cosine similarity）。
    """
    return cosine_similarity(query_embedding, text_embedding)

def retrieve_relevant_skills(skills_text: str, query: str, top_k: int = 5) -> str:
    """
    基于当前任务 (query) 从 skills.md 中检索最相关的经验。
    Embedding RAG 实现：基于向量相似度检索。
    """
    if not skills_text or not str(query or "").strip():
        _write_rag_scores("skills", str(query or "").strip(), [], status="skipped", reason="empty_input")
        return skills_text

    query = str(query).strip()
        
    lines = [line.strip() for line in skills_text.split('\n') if line.strip() and line.strip().startswith('- ')]
    if not lines:
        _write_rag_scores("skills", query, [], status="skipped", reason="no_lines")
        return skills_text
        
    query_embeddings = embed_texts([query])
    if not query_embeddings:
        _write_rag_scores("skills", query, [], status="skipped", reason="embedding_unavailable")
        return skills_text
    query_embedding = query_embeddings[0]
    line_embeddings = embed_texts(lines)
    if not line_embeddings or len(line_embeddings) != len(lines):
        _write_rag_scores("skills", query, [], status="skipped", reason="embedding_mismatch")
        return skills_text

    scored_lines = []
    for line, embedding in zip(lines, line_embeddings):
        score = calculate_similarity(query_embedding, embedding)
        scored_lines.append((score, line))

    _write_rag_scores(
        "skills",
        query,
        [{"score": score, "text": line} for score, line in scored_lines],
    )
        
    # 按分数降序排列
    scored_lines.sort(key=lambda x: x[0], reverse=True)
    top_lines = [item[1] for item in scored_lines[:top_k]]
    
    return "### Relevant Task Skills (RAG Retrieved):\n" + "\n".join(top_lines)

def retrieve_relevant_attachment(attachment_text: str, query: str) -> str:
    """
    基于当前任务 (query) 从 attachment.md 中检索最相关的数据块。
    通过 Markdown 的 '###' 或 '####' 进行分块检索。
    """
    if not attachment_text or not str(query or "").strip():
        _write_rag_scores("attachment", str(query or "").strip(), [], status="skipped", reason="empty_input")
        return attachment_text

    query = str(query).strip()

    blocks = re.split(r'(?=^#{3,4} )', attachment_text, flags=re.MULTILINE)
    blocks = [b.strip() for b in blocks if b.strip()]

    query_embeddings = embed_texts([query])
    if not query_embeddings:
        _write_rag_scores("attachment", query, [], status="skipped", reason="embedding_unavailable")
        return attachment_text
    query_embedding = query_embeddings[0]
    block_embeddings = embed_texts(blocks)
    if not block_embeddings or len(block_embeddings) != len(blocks):
        _write_rag_scores("attachment", query, [], status="skipped", reason="embedding_mismatch")
        return attachment_text

    scored_blocks = []
    for block, embedding in zip(blocks, block_embeddings):
        score = calculate_similarity(query_embedding, embedding)
        scored_blocks.append((score, block))

    _write_rag_scores(
        "attachment",
        query,
        [
            {"score": score, "text": block[:200]}
            for score, block in scored_blocks
        ],
    )
        
    scored_blocks.sort(key=lambda x: x[0], reverse=True)
    
    # 选取最相关的 Top 2 数据块组合
    top_blocks = [item[1] for item in scored_blocks[:2]]
    return "### Relevant Attachment Data (RAG Retrieved):\n\n" + "\n\n".join(top_blocks)


def _tag_own_text(tag: Tag) -> str:
    """仅该标签直接子节点中的纯文本，不包含子元素内的文字。"""
    parts: List[str] = []
    for child in tag.children:
        if isinstance(child, NavigableString) and not isinstance(child, Comment):
            s = str(child).strip()
            if s:
                parts.append(s)
    return " ".join(parts) if parts else ""


def _tag_attr_text_for_rag(tag: Tag) -> str:
    """
    将节点 HTML 各属性的取值（不含属性名）拼成可嵌入的短串（与正文分开算分，最后取 max）。
    对过长 style 等做截断，避免无意义膨胀。
    """
    if not getattr(tag, "attrs", None):
        return ""
    parts: List[str] = []
    for key in sorted(tag.attrs.keys()):
        raw = tag.attrs[key]
        if raw is None:
            continue
        if isinstance(raw, list):
            val = " ".join(str(x).strip() for x in raw if x is not None and str(x).strip())
        else:
            val = str(raw).strip()
        if not val:
            continue
        k = str(key).strip().lower()
        if k == "style" and len(val) > 240:
            val = val[:240]
        elif len(val) > 480:
            val = val[:480]
        parts.append(val)
    return " ".join(parts) if parts else ""


def _node_log_text(tag: Tag) -> str:
    """
    日志展示：优先节点自身直接文本；无则表单属性；再无则 class/id。
    """
    own = _tag_own_text(tag)
    if own:
        return own[:200]
    for attr in ("value", "placeholder", "aria-label", "title", "alt", "data-placeholder", "name"):
        val = tag.get(attr)
        if val is not None and str(val).strip():
            return str(val).strip()[:200]
    ident = f"{tag.get('class', '')} {tag.get('id', '')}".strip()
    if ident:
        return ident.replace("\n", " ")[:200]
    return ""


def _find_tag_span_in_source_html(source_html: str, node: Tag) -> Tuple[int, int]:
    """
    在原始 clean_html 字符串中定位节点，返回 [start, end)（半开区间）。
    优先整段 outer HTML 匹配，失败则退化到起始标签或节点直接文本。
    """
    outer = str(node).strip()
    if len(outer) > 0:
        pos = source_html.find(outer)
        if pos != -1:
            return pos, pos + len(outer)
    if node.name:
        needle = f"<{node.name}"
        pos = source_html.find(needle)
        if pos != -1:
            est = len(outer) if outer else min(200, len(source_html) - pos)
            return pos, min(len(source_html), pos + max(est, 1))
    own = _tag_own_text(node)
    if own and len(own.strip()) >= 1:
        pos = source_html.find(own.strip())
        if pos != -1:
            return pos, pos + len(own.strip())
    return -1, -1


def _slice_context_window(source_html: str, start: int, end: int, n: int) -> str:
    """以 [start,end) 为中心向两侧各扩展 n 个字符（与 clean_html 同源）。"""
    if start < 0 or end < 0:
        return ""
    a = max(0, start - n)
    b = min(len(source_html), end + n)
    return source_html[a:b]


def _build_rag_context_blocks(
    source_html: str,
    scored: List[Tuple[float, Tag]],
    k: int,
    n: int,
) -> List[Dict[str, object]]:
    """得分排序后取前 k 个节点，在 source_html 上截取上下文片段。"""
    ordered = sorted(scored, key=lambda x: float(x[0]), reverse=True)
    seen: set[int] = set()
    top: List[Tuple[float, Tag]] = []
    for sc, tag in ordered:
        tid = id(tag)
        if tid in seen:
            continue
        seen.add(tid)
        top.append((float(sc), tag))
        if len(top) >= k:
            break

    out: List[Dict[str, object]] = []
    for rank, (sc, tag) in enumerate(top, 1):
        s, e = _find_tag_span_in_source_html(source_html, tag)
        chunk = _slice_context_window(source_html, s, e, n) if s >= 0 else ""
        if not (chunk or "").strip():
            chunk = _node_log_text(tag)
        out.append(
            {
                "rank": rank,
                "k": rank,
                "value": _node_log_text(tag),
                "score": sc,
                "start": s if s >= 0 else None,
                "end": e if s >= 0 else None,
                "chunk": chunk,
            }
        )
    return out


def retrieve_relevant_html_tree(
    html_content: str,
    query: str,
    max_depth: int = HTML_RAG_MAX_DEPTH,
    *,
    prompt_rag_dump_path: Optional[Path] = None,
) -> Tuple[str, List[Dict[str, object]]]:
    """
    HTML RAG（仅用于提示词聚焦块，不修改整页 HTML）：
    1. 与 query 的向量相似度：对每个标签节点用「自身直接文本」与「各属性取值拼成的串」分别嵌入，取二者与 query 相似度的较大值（不聚合子元素正文）。
    2. 按分排序，在原始 clean_html 上定位 top-K 节点，向两侧各取 HTML_RAG_WINDOW_N 字符作为块。

    max_depth：仅遍历到此深度内的节点参与打分；
    深层页面若仍偏少可调大或使用环境变量 HTML_RAG_MAX_DEPTH。

    返回: (原始 html_content 字符串, RAG 分块列表；不再对 DOM 做剪枝)
    """
    if not html_content or not str(query or "").strip():
        save_html_rag_prompt_snapshot(
            prompt_rag_dump_path,
            str(query or "").strip(),
            [],
            status="skipped",
            reason="empty_input",
        )
        return html_content, []

    query = str(query).strip()
    soup = BeautifulSoup(html_content, 'html.parser')

    query_embeddings = embed_texts([query])
    if not query_embeddings:
        save_html_rag_prompt_snapshot(
            prompt_rag_dump_path,
            query,
            [],
            status="skipped",
            reason="embedding_unavailable",
        )
        return html_content, []
    query_embedding = query_embeddings[0]
    embedding_cache: Dict[str, List[float]] = {}
    embed_budget = {"count": 0}
    rag_scored_nodes: List[Tuple[float, Tag]] = []

    def _prepare_embedding_cache() -> None:
        collected = []

        def collect(node, current_depth) -> None:
            if current_depth > max_depth:
                return
            if isinstance(node, NavigableString):
                return
            if not isinstance(node, Tag):
                return

            # 嵌入缓存：各节点自身直接正文 + 属性串（分开缓存，打分取 max）
            own_text = _tag_own_text(node)
            if own_text:
                collected.append(clip_text(own_text))
            attr_text = _tag_attr_text_for_rag(node)
            if attr_text:
                collected.append(clip_text(attr_text))

            for child in node.children:
                collect(child, current_depth + 1)

        collect(soup, 0)
        unique = []
        seen = set()
        for text in collected:
            if text in seen:
                continue
            seen.add(text)
            unique.append(text)
            if len(unique) >= MAX_EMBED_TEXTS:
                break
        if unique:
            embedding_cache.update(build_embedding_cache(unique))

    def _get_text_embedding(text: str) -> List[float]:
        clipped = clip_text(text)
        if clipped in embedding_cache:
            return embedding_cache[clipped]
        if embed_budget["count"] >= MAX_EMBED_TEXTS:
            return []
        embedding_cache.update(build_embedding_cache([clipped]))
        embed_budget["count"] += 1
        return embedding_cache.get(clipped, [])

    _prepare_embedding_cache()

    def get_node_relevance(node) -> float:
        """评估节点直接正文、属性取值与 query 的向量相关性（分别算再取较大值）。"""
        score = 0.0
        
        if isinstance(node, NavigableString):
            return 0.0
        
        if isinstance(node, Tag):
            own_text = _tag_own_text(node)
            if own_text:
                node_embedding = _get_text_embedding(own_text)
                score = max(score, calculate_similarity(query_embedding, node_embedding))
            attr_text = _tag_attr_text_for_rag(node)
            if attr_text:
                node_embedding = _get_text_embedding(attr_text)
                score = max(score, calculate_similarity(query_embedding, node_embedding))

            rag_scored_nodes.append((score, node))

        return score

    def walk_score(node, current_depth: int) -> None:
        if current_depth > max_depth:
            return
        if isinstance(node, NavigableString):
            return
        if isinstance(node, Tag):
            get_node_relevance(node)
            for child in node.children:
                walk_score(child, current_depth + 1)
        else:
            for child in getattr(node, "children", []):
                walk_score(child, current_depth)

    walk_score(soup, 0)

    rag_focus_blocks = _build_rag_context_blocks(
        html_content,
        rag_scored_nodes,
        HTML_RAG_BLOCKS_K,
        HTML_RAG_WINDOW_N,
    )

    save_html_rag_prompt_snapshot(
        prompt_rag_dump_path,
        query,
        rag_focus_blocks,
        status="ok",
        reason="",
        top_k=HTML_RAG_PROMPT_TOP_K,
        total_candidates=len(rag_scored_nodes),
    )

    return html_content, rag_focus_blocks