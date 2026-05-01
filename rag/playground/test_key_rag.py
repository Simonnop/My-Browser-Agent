import sys
import os
from bs4 import BeautifulSoup

# 将项目根目录添加到 path 以便导入 rag 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from rag.key_rag import KeyRAG

def build_key_table_from_html(html_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    key_data = {}
    
    # 模拟 Indexer 中的 JS 逻辑
    tags = ['div', 'span', 'a', 'button', 'input', 'form', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'p', 'nav', 'main', 'header', 'footer', 'section', 'article', 'label', 'select', 'textarea', 'svg', 'img', 'i', 'em']
    elements = soup.find_all(tags)
    
    important_tags = ['a', 'button', 'input', 'label', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'option']
    
    for el in elements:
        agent_id = el.get('data-agent-id')
        if not agent_id:
            continue
            
        keys = []
        is_leaf = len(el.find_all(recursive=False)) == 0
        role = el.get('role')
        has_role = role in ['option', 'button', 'link']
        
        # innerText 逻辑
        if is_leaf or el.name in important_tags or has_role:
            text = el.get_text(strip=True)
            if text:
                keys.append(text)
        
        # 属性逻辑
        if el.get('placeholder'): keys.append(el.get('placeholder').strip())
        if el.get('aria-label'): keys.append(el.get('aria-label').strip())
        if el.get('title'): keys.append(el.get('title').strip())
        if el.get('name'): keys.append(el.get('name'))
        if el.get('id'): keys.append(el.get('id'))
        
        for k in keys:
            if k:
                if k not in key_data:
                    key_data[k] = []
                if agent_id not in key_data[k]:
                    key_data[k].append(agent_id)
                    
    return key_data, soup

def test_rag(keyword):
    html_path = os.path.join(os.path.dirname(__file__), 'test.html')
    key_table, soup = build_key_table_from_html(html_path)
    
    rag = KeyRAG(key_table)
    # 模拟从 KeyRAG 内部获取得分（如果可能）或者直接展示匹配项
    results = rag.search([keyword], top_k=10)
    
    print(f"\n--- 关键词: '{keyword}' 的 RAG 检索结果 (Top 10) ---")
    if not results:
        print("未找到任何相似度 > 0.3 的匹配节点。")
        # 调试：查看 key_table 中是否存在包含该关键词的项
        print("\n[调试信息] 检查 key_table 是否包含关键词:")
        found_in_table = False
        for k in key_table.keys():
            if keyword.lower() in k.lower():
                print(f"  - 命中 key_table 项: '{k}' -> IDs: {key_table[k]}")
                found_in_table = True
        if not found_in_table:
            print(f"  - key_table 中完全没有包含 '{keyword}' 的文本。请检查 Indexer 是否正确收集了该节点的文本。")
        return

    for i, node_id in enumerate(results):
        # 查找节点对应的原始 HTML 及其文本
        node = soup.find(attrs={"data-agent-id": node_id})
        node_text = node.get_text(strip=True) if node else "未知"
        node_tag = node.name if node else "未知"
        node_title = node.get('title', '无') if node else "无"
        
        print(f"{i+1}. [ID: {node_id}] <{node_tag}>")
        print(f"   文本: {node_text}")
        print(f"   Title: {node_title}")

if __name__ == "__main__":
    # 测试用户提到的“桂林”
    test_rag("桂林")
    # 也可以测试其他关键词
    test_rag("首页")
    test_rag("职位")
