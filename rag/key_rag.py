from typing import List, Dict
import re

class KeyRAG:
    """
    语义路检索: 根据关键词检索最相关的节点
    """
    def __init__(self, key_table: Dict[str, List[str]]):
        self.key_table = key_table

    def search(self, keywords: List[str], top_k: int = 3) -> List[str]:
        """
        简单的关键词匹配。在实际应用中，这里可以使用 Embedding 进行向量检索。
        """
        if not keywords or not self.key_table:
            return []

        # 计算每个 node_id 的匹配分数
        scores = {}
        for keyword in keywords:
            # 简单模糊匹配
            for key_text, node_ids in self.key_table.items():
                if keyword.lower() in key_text.lower():
                    for node_id in node_ids:
                        scores[node_id] = scores.get(node_id, 0) + 1

        # 按分数排序
        sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return [n[0] for n in sorted_nodes[:top_k]]
