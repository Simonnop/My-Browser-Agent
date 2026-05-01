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
            // 0. 清除之前可能存在的旧 ID，防止重复冲突
            const oldElements = document.querySelectorAll('[data-agent-id]');
            oldElements.forEach(el => el.removeAttribute('data-agent-id'));

            const elements = document.querySelectorAll('div, span, a, button, input, form, ul, li, h1, h2, h3, h4, h5, h6, table, p, nav, main, header, footer, section, article, label, select, textarea, svg, img, i, em');
            let idCounter = 0;
            const spaceData = [];
            const keyData = {};

            elements.forEach(el => {
                // 检查是否可见
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const tagName = el.tagName.toLowerCase();
                const role = el.getAttribute('role');
                
                // 语义化/交互式节点判定
                const isInteractive = ['a', 'button', 'input', 'select', 'textarea'].includes(tagName) || 
                                     ['option', 'menuitem', 'tab', 'button', 'link'].includes(role);
                
                // 只要不是 display:none，且 (有尺寸 OR 是交互节点)，就认为值得索引
                const isVisible = (rect.width > 0 && rect.height > 0) || (isInteractive && style.display !== 'none');
                
                // 增加“视口内”判定：Space-RAG 必须是当前屏幕用户可见的
                const isInViewport = (
                    rect.top < window.innerHeight &&
                    rect.bottom > 0 &&
                    rect.left < window.innerWidth &&
                    rect.right > 0
                );

                if (isVisible && style.visibility !== 'hidden' && style.opacity !== '0') {
                    const id = String(idCounter++);
                    el.setAttribute('data-agent-id', id);
                    
                    // 收集空间信息 (仅对在视口内且有物理尺寸的元素)
                    if (isInViewport && rect.width > 0 && rect.height > 0) {
                        const cx = rect.left + rect.width / 2;
                        const cy = rect.top + rect.height / 2;

                        // 遮挡检测 (Occlusion Check)
                        // 使用 elementFromPoint 检查中心点是否被其他元素（如弹窗、遮罩）覆盖
                        const elementAtPoint = document.elementFromPoint(cx, cy);
                        const isOccluded = elementAtPoint && !el.contains(elementAtPoint) && !elementAtPoint.contains(el);

                        spaceData.push({
                            id: id,
                            center: [cx, cy],
                            rect: {
                                x: rect.left,
                                y: rect.top,
                                width: rect.width,
                                height: rect.height
                            },
                            is_occluded: isOccluded // 标记是否被覆盖
                        });
                    }

                    // 收集关键词信息
                    const keys = [];
                    
                    // 1. 属性优先 (title, aria-label, placeholder)
                    const attrTitle = el.getAttribute('title');
                    const attrAria = el.getAttribute('aria-label');
                    const attrPlaceholder = el.getAttribute('placeholder');
                    
                    if (attrTitle) keys.push(attrTitle.trim());
                    if (attrAria) keys.push(attrAria.trim());
                    if (attrPlaceholder) keys.push(attrPlaceholder.trim());
                    if (el.name) keys.push(el.name);
                    if (el.id) keys.push(el.id);

                    // 2. 文本内容
                    const isLeaf = el.children.length === 0;
                    const importantTags = ['a', 'button', 'input', 'label', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'option'];
                    
                    // 如果是叶子节点、重要标签、或者具有交互 role，则收集文本
                    if (isLeaf || importantTags.includes(tagName) || isInteractive) {
                        const text = el.innerText ? el.innerText.trim() : "";
                        if (text && text.length < 100) { // 避免收集超长文本块
                            keys.append_unique = (val) => {
                                if (val && !keys.includes(val)) keys.push(val);
                            };
                            keys.append_unique(text);
                        }
                    }

                    keys.forEach(k => {
                        if (k) {
                            if (!keyData[k]) keyData[k] = [];
                            if (!keyData[k].includes(id)) keyData[k].push(id);
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
