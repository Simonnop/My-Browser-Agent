import re

def clean_html(raw_html: str) -> str:
    # 1. 彻底移除 script、style、noscript、iframe 等不需要分析的块
    cleaned_html = re.sub(r'<(script|style|noscript|iframe)[^>]*>.*?</\1>', '', raw_html, flags=re.IGNORECASE | re.DOTALL)
    # 2. 移除 link、meta、base 无关单标签
    cleaned_html = re.sub(r'<(link|meta|base)[^>]*>', '', cleaned_html, flags=re.IGNORECASE)
    # 3. 简化 SVG（SVG 图标路径经常极长，大模型不需要解析几千个坐标点）
    cleaned_html = re.sub(r'<svg[^>]*>.*?</svg>', '<svg>...</svg>', cleaned_html, flags=re.IGNORECASE | re.DOTALL)
    # 4. 移除 HTML 注释
    cleaned_html = re.sub(r'<!--.*?-->', '', cleaned_html, flags=re.DOTALL)
    # 5. 精简 data URIs 和 base64 图片数据（减少超量无用字符）
    cleaned_html = re.sub(r'(src|srcset)\s*=\s*"data:image/[^"]+"', r'\1="..."', cleaned_html, flags=re.IGNORECASE)

    # 7. 只保留常用 HTML 标签，过滤掉生僻或自定义标签
    def filter_tags(match):
        tag_name = match.group(2).lower()
        allowed_tags = {
            'html', 'body', 'div', 'span', 'a', 'p', 'img', 'button', 'input', 
            'form', 'ul', 'li', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
            'table', 'tr', 'td', 'th', 'tbody', 'thead', 'label', 'select', 
            'option', 'textarea', 'nav', 'header', 'footer', 'main', 'section', 
            'article', 'aside', 'svg'
        }
        if tag_name in allowed_tags:
            return match.group(0)
        return ""

    cleaned_html = re.sub(r'<(/?)([a-zA-Z0-9\-]+)([^>]*)>', filter_tags, cleaned_html)

    # 8. 压缩多余空白符
    cleaned_html = re.sub(r'\s+', ' ', cleaned_html).strip()

    # 9. 截断标签中间的纯文本内容，超过30字符保留前30个字符，并加省略号
    def truncate_text(match):
        text = match.group(1)
        if len(text) > 30:
            return f">{text[:30]}...<"
        return match.group(0)

    cleaned_html = re.sub(r'>([^<]+)<', truncate_text, cleaned_html)

    # 10. 将相邻标签换行，整理排版
    cleaned_html = cleaned_html.replace('><', '>\n<')
    
    return cleaned_html


# def clean_html(raw_html: str, attr_limit: int = 50) -> str:
#     """
#     通用 HTML 清洗函数：
#     1. 保留 CSS 选择器属性 (id, class, data-*, name等)。
#     2. 移除 href 属性。
#     3. 移除 value 为空的属性。
#     4. 截断过长的属性值 (Attribute Truncation)。
#     5. 递归删除无文本容器节点。
#     """
    
#     # 1. 基础块处理 (Script, Style, Comments)
#     cleaned = re.sub(r'<(script|style|noscript|iframe|canvas)[^>]*>.*?</\1>', '', raw_html, flags=re.IGNORECASE | re.DOTALL)
#     cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
    
#     # 2. 属性清洗与截断
#     def strip_attributes(match):
#         tag_name = match.group(1).lower()
#         full_tag = match.group(0)
        
#         # 定义核心定位属性白名单
#         allowed_attrs = {'id', 'class', 'name', 'type', 'title', 'alt', 'placeholder', 'role'}
        
#         # 提取属性对
#         found_attrs = re.findall(r'\s([a-zA-Z0-9\-\:_]+)="([^"]*)"', full_tag)
        
#         kept = []
#         for name, value in found_attrs:
#             n_lower = name.lower()
#             v_stripped = value.strip()
            
#             # 核心过滤逻辑：
#             # - v_stripped 不能为空
#             # - n_lower 不是 href
#             # - n_lower 在白名单内或以 data- 开头
#             if v_stripped and n_lower != 'href':
#                 if n_lower in allowed_attrs or n_lower.startswith('data-'):
#                     # --- 属性截断逻辑 ---
#                     if len(v_stripped) > attr_limit:
#                         final_value = v_stripped[:attr_limit] + "..."
#                     else:
#                         final_value = v_stripped
#                     kept.append(f'{name}="{final_value}"')
        
#         return f'<{tag_name} {" ".join(kept)}>' if kept else f'<{tag_name}>'

#     cleaned = re.sub(r'<([a-zA-Z0-9\-]+)([^>]+)>', strip_attributes, cleaned)

#     # 3. 标签白名单过滤
#     def filter_tags(match):
#         tag_name = match.group(2).lower()
#         allowed_tags = {
#             'html', 'body', 'main', 'header', 'footer', 'section', 'article', 'nav',
#             'div', 'span', 'p', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
#             'table', 'tr', 'td', 'th', 'form', 'input', 'button', 'select', 'option', 
#             'a', 'img', 'svg'
#         }
#         return match.group(0) if tag_name in allowed_tags else ""

#     cleaned = re.sub(r'<(/?)([a-zA-Z0-9\-]+)([^>]*)>', filter_tags, cleaned)

#     # 4. 文本节点脱水与截断 (保留前20个字符)
#     def process_text(match):
#         text = match.group(1).strip()
#         if not text: return "><"
#         return f">{text[:20]}...<" if len(text) > 20 else f">{text}<" # 截断20个字符

#     cleaned = re.sub(r'>([^<]+)<', process_text, cleaned)

#     # 5. 递归清除空容器
#     protected_void_tags = {'img', 'input', 'svg', 'br', 'hr'}
#     while True:
#         pattern = r'<([a-zA-Z0-9\-]+)[^>]*>\s*</\1>'
#         matches = list(re.finditer(pattern, cleaned, flags=re.IGNORECASE))
#         if not matches:
#             break
#         new_cleaned = cleaned
#         for m in reversed(matches):
#             if m.group(1).lower() not in protected_void_tags:
#                 new_cleaned = new_cleaned[:m.start()] + new_cleaned[m.end():]
#         if new_cleaned == cleaned:
#             break
#         cleaned = new_cleaned

#     # 6. 整理格式
#     cleaned = re.sub(r'\s+', ' ', cleaned).strip()
#     cleaned = cleaned.replace('><', '>\n<')
    
#     return cleaned
