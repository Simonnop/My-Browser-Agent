from typing import Dict, List, Any, Optional
from playwright.sync_api import Page

class Indexer:
    """
    构建双表索引: Key Table 和 Space Table
    """
    def __init__(self, page: Page):
        self.page = page
        self.key_table: Dict[str, List[str]] = {}
        self.space_table: List[Dict[str, Any]] = []

    def build_index(self):
        """
        遍历 DOM 树，为可见元素分配 ID 并构建索引
        """
        # 1. 为所有可见的可交互或语义元素注入 data-agent-id
        # 我们只关注特定的标签
        js_script = """
        () => {
            const elements = document.querySelectorAll('div, span, a, button, input, form, ul, li, h1, h2, h3, h4, h5, h6, table, p, nav, main, header, footer, section, article, label, select, textarea, svg, img, i, em');
            let idCounter = 0;
            const spaceData = [];
            const keyData = {};

            elements.forEach(el => {
                // 检查是否可见
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                    const id = String(idCounter++);
                    el.setAttribute('data-agent-id', id);
                    
                    // 收集空间信息
                    spaceData.push({
                        id: id,
                        center: [rect.left + rect.width / 2, rect.top + rect.height / 2],
                        rect: {
                            x: rect.left,
                            y: rect.top,
                            width: rect.width,
                            height: rect.height
                        }
                    });

                    // 收集关键词信息
                    const keys = [];
                    // 仅对叶子节点或特定标签收集 innerText，避免父容器包含过多干扰文本
                    const isLeaf = el.children.length === 0;
                    const importantTags = ['a', 'button', 'input', 'label', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'];
                    
                    if (isLeaf || importantTags.includes(el.tagName.toLowerCase())) {
                        if (el.innerText) keys.push(el.innerText.trim());
                    }
                    
                    if (el.getAttribute('placeholder')) keys.push(el.getAttribute('placeholder').trim());
                    if (el.getAttribute('aria-label')) keys.push(el.getAttribute('aria-label').trim());
                    if (el.getAttribute('title')) keys.push(el.getAttribute('title').trim());
                    if (el.name) keys.push(el.name);
                    if (el.id) keys.push(el.id);

                    keys.forEach(k => {
                        if (k) {
                            if (!keyData[k]) keyData[k] = [];
                            if (!keyData[k].includes(id)) keyData[k].append(id);
                        }
                    });
                }
            });
            return { spaceData, keyData };
        }
        """
        # 修正 JS 中的一个小错误: append -> push
        js_script = js_script.replace('keyData[k].append(id)', 'keyData[k].push(id)')
        
        result = self.page.evaluate(js_script)
        self.space_table = result['spaceData']
        self.key_table = result['keyData']

    def get_space_table(self) -> List[Dict[str, Any]]:
        return self.space_table

    def get_key_table(self) -> Dict[str, List[str]]:
        return self.key_table
