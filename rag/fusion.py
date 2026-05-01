from bs4 import BeautifulSoup
from typing import List, Set
import copy

class FusionModule:
    """
    融合与去重模块: 整合两路 RAG 结果并构建局部 HTML
    """
    def __init__(self, cleaned_html: str):
        self.soup = BeautifulSoup(cleaned_html, 'html.parser')

    def fuse(self, key_node_ids: List[str], space_node_ids: List[str], path_depth: int = 2) -> str:
        """
        1. 合并去重
        2. 路径扩展
        3. 按原始顺序重组
        """
        core_ids = set(key_node_ids) | set(space_node_ids)
        if not core_ids:
            return ""

        all_relevant_ids: Set[str] = set(core_ids)
        
        # 路径扩展: 实现真实的图距离 n 扩展
        # 每一步扩展都会包含当前节点的所有相邻节点（父节点和子节点）
        # 经过 2 步扩展，就能包含“兄弟节点”（父节点的子节点）
        for _ in range(path_depth):
            new_ids = set()
            for node_id in all_relevant_ids:
                node = self.soup.find(attrs={"data-agent-id": node_id})
                if node:
                    # 1. 添加父节点 (向上一步)
                    parent = node.parent
                    if parent and parent.name != '[document]':
                        p_id = parent.get('data-agent-id')
                        if p_id: 
                            new_ids.add(p_id)
                    
                    # 2. 添加所有直接子节点 (向下一步)
                    children = node.find_all(attrs={"data-agent-id": True}, recursive=False)
                    for child in children:
                        c_id = child.get('data-agent-id')
                        if c_id:
                            new_ids.add(c_id)
            
            # 如果没有新节点加入，提前结束
            if new_ids.issubset(all_relevant_ids):
                break
            all_relevant_ids.update(new_ids)

        # 3. 构建“必须保留”的节点集合（包含所有命中节点及其祖先）
        # 这样可以确保 HTML 结构完整（从根到叶子的路径是连贯的）
        result_soup = copy.deepcopy(self.soup)
        must_keep_elements = set()

        for node_id in all_relevant_ids:
            # 在新 soup 中查找对应的节点
            element = result_soup.find(attrs={"data-agent-id": node_id})
            if element:
                # 将该节点及其所有祖先加入保留集合
                curr = element
                while curr and curr.name != '[document]':
                    if curr in must_keep_elements:
                        break # 已经处理过该祖先路径
                    must_keep_elements.add(curr)
                    curr = curr.parent

        # 4. 执行剪枝：移除不在 must_keep_elements 中的所有节点
        # 注意：需要自底向上处理，或者直接遍历所有标签进行判断
        for tag in result_soup.find_all(True):
            if tag not in must_keep_elements:
                tag.decompose()

        # 返回保留了原始结构和顺序的局部 HTML
        # 如果有 body 则返回 body 内容，否则返回整个 soup
        if result_soup.body:
            return str(result_soup.body)
        return str(result_soup)
