from typing import List, Dict, Any

class CollectedRAG:
    """
    采集数据按需检索: 从已采集的数据中按关键词匹配返回 top_k 条
    """
    @staticmethod
    def search(collected: List[Dict[str, Any]], query: str, top_k: int = 3) -> str:
        if not query or not collected:
            return ""
        query_lower = query.lower()
        scored = []
        for entry in collected:
            for item in entry.get("items", []):
                text = str(item)
                score = sum(1 for w in query_lower.split() if w in text.lower())
                scored.append((score, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = [t for s, t in scored[:top_k] if s > 0]
        return "\n".join(hits) if hits else ""
