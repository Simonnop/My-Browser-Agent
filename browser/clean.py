import os
from bs4 import BeautifulSoup, Comment
import re

def clean_html(html_content: str) -> str:
    """
    根据 PRD 需求清洗 HTML 内容
    1. 移除 script, style, noscript, iframe
    2. 过滤 link, meta, base
    3. 简化 svg
    4. 替换 Base64 Data URIs
    5. 标签白名单
    6. 文本截断 (30字符)
    7. 格式优化
    """
    text_threshold = int(os.getenv("TEXT_THRESHOLD", "30"))
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. & 2. 移除不需要的标签
    remove_tags = ['script', 'style', 'noscript', 'iframe', 'link', 'meta', 'base', 'head']
    for tag in soup.find_all(remove_tags):
        tag.decompose()

    # 移除注释
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 3. 图形简化: svg 内部路径全部替换为 ...
    for svg in soup.find_all('svg'):
        svg.clear()
        svg.append('...')

    # 4. 资源占位: 替换 Base64 Data URIs
    for tag in soup.find_all(src=True):
        if tag['src'].startswith('data:'):
            tag['src'] = '...'
    for tag in soup.find_all(srcset=True):
        tag['srcset'] = '...'

    # 5. 标签白名单 (保留交互及语义相关的标签)
    allowed_tags = {
        'div', 'span', 'a', 'button', 'input', 'form', 'ul', 'li', 
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'tr', 'td', 'th', 
        'p', 'nav', 'main', 'header', 'footer', 'section', 'article',
        'label', 'select', 'option', 'textarea', 'svg', 'img', 'body', 'html',
        'i', 'em'
    }
    
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            # 这里的处理方式是将不符合要求的标签替换为其子内容，或者直接移除
            # 为了保留层级，我们将其内容展开
            tag.unwrap()

    # 6. 文本截断: 标签间的文本长度若超过 30 字符，则保留前 30 个并加 ...
    # 7. 格式优化: 压缩多余空白符
    for element in soup.find_all(string=True):
        if element.parent and element.parent.name in ['script', 'style']:
            continue
        
        text = element.strip()
        if not text:
            element.extract()
            continue
            
        # 压缩空白符
        text = re.sub(r'\s+', ' ', text)
        
        if len(text) > text_threshold:
            new_text = text[:text_threshold] + "..."
            element.replace_with(new_text)
        else:
            element.replace_with(text)

    # 格式优化: 返回压缩后的 HTML 字符串
    return str(soup)
