from typing import List, Dict
from difflib import SequenceMatcher

class KeyRAG:
    """
    语义路检索: 根据关键词检索最相关的节点
    """
    def __init__(self, key_table: Dict[str, List[str]]):
        self.key_table = key_table

    def _get_similarity(self, s1: str, s2: str) -> float:
        """
        计算两个字符串的相似度 (0.0 - 1.0)
        """
        if not s1 or not s2:
            return 0.0
        return SequenceMatcher(None, s1, s2).ratio()

    def search(self, keywords: List[str], top_k: int = 3) -> List[str]:
        """
        使用滑动窗口检索关键词，窗口长度与关键词长度一致。
        相似度取所有窗口相似度的最大值。
        """
        if not keywords or not self.key_table:
            return []

        all_hit_ids = []
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            keyword_len = len(keyword_lower)
            node_scores = {}
            
            for key_text, node_ids in self.key_table.items():
                key_text_lower = key_text.lower()
                text_len = len(key_text_lower)
                
                if text_len <= keyword_len:
                    # 如果文本比关键词短或等长，直接计算整体相似度
                    similarity = self._get_similarity(keyword_lower, key_text_lower)
                else:
                    # 滑动窗口逻辑
                    if keyword_lower in key_text_lower:
                        # 如果完全包含，给予最高相似度 (1.0)
                        similarity = 1.0
                    else:
                        max_sim = 0
                        # 遍历所有可能的窗口
                        for i in range(text_len - keyword_len + 1):
                            window = key_text_lower[i : i + keyword_len]
                            sim = self._get_similarity(keyword_lower, window)
                            if sim > max_sim:
                                max_sim = sim
                        similarity = max_sim
                
                # 仅保留有一定相似度的结果（阈值 0.3），避免引入过多噪声
                if similarity > 0.3:
                    for node_id in node_ids:
                        # 如果同一个 node_id 对应多个 key_text，记录最高相似度
                        if similarity > node_scores.get(node_id, 0):
                            node_scores[node_id] = similarity
            
            # 对当前关键词命中的节点按相似度从高到低排序
            sorted_keyword_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)
            # 取当前关键词的前 top_k 个最相关的 Node ID
            keyword_top_k = [n[0] for n in sorted_keyword_nodes[:top_k]]
            all_hit_ids.extend(keyword_top_k)

        # 全局去重，并保持顺序（先出现的关键词命中结果排在前面）
        seen = set()
        unique_hit_ids = []
        for node_id in all_hit_ids:
            if node_id not in seen:
                unique_hit_ids.append(node_id)
                seen.add(node_id)
        
        return unique_hit_ids
