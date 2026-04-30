import asyncio
import re
import os
from playwright.async_api import async_playwright
import re
import re
import re
import re

def clean_html(raw_html: str, attr_limit: int = 50) -> str:
    """
    通用 HTML 清洗函数：
    1. 保留 CSS 选择器属性 (id, class, data-*, name等)。
    2. 移除 href 属性。
    3. 移除 value 为空的属性。
    4. 截断过长的属性值 (Attribute Truncation)。
    5. 递归删除无文本容器节点。
    """
    
    # 1. 基础块处理 (Script, Style, Comments)
    cleaned = re.sub(r'<(script|style|noscript|iframe|canvas)[^>]*>.*?</\1>', '', raw_html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
    
    # 2. 属性清洗与截断
    def strip_attributes(match):
        tag_name = match.group(1).lower()
        full_tag = match.group(0)
        
        # 定义核心定位属性白名单
        allowed_attrs = {'id', 'class', 'name', 'type', 'title', 'alt', 'placeholder', 'role'}
        
        # 提取属性对
        found_attrs = re.findall(r'\s([a-zA-Z0-9\-\:_]+)="([^"]*)"', full_tag)
        
        kept = []
        for name, value in found_attrs:
            n_lower = name.lower()
            v_stripped = value.strip()
            
            # 核心过滤逻辑：
            # - v_stripped 不能为空
            # - n_lower 不是 href
            # - n_lower 在白名单内或以 data- 开头
            if v_stripped and n_lower != 'href':
                if n_lower in allowed_attrs or n_lower.startswith('data-'):
                    # --- 属性截断逻辑 ---
                    if len(v_stripped) > attr_limit:
                        final_value = v_stripped[:attr_limit] + "..."
                    else:
                        final_value = v_stripped
                    kept.append(f'{name}="{final_value}"')
        
        return f'<{tag_name} {" ".join(kept)}>' if kept else f'<{tag_name}>'

    cleaned = re.sub(r'<([a-zA-Z0-9\-]+)([^>]+)>', strip_attributes, cleaned)

    # 3. 标签白名单过滤
    def filter_tags(match):
        tag_name = match.group(2).lower()
        allowed_tags = {
            'html', 'body', 'main', 'header', 'footer', 'section', 'article', 'nav',
            'div', 'span', 'p', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'table', 'tr', 'td', 'th', 'form', 'input', 'button', 'select', 'option', 
            'a', 'img', 'svg'
        }
        return match.group(0) if tag_name in allowed_tags else ""

    cleaned = re.sub(r'<(/?)([a-zA-Z0-9\-]+)([^>]*)>', filter_tags, cleaned)

    # 4. 文本节点脱水与截断 (保留前20个字符)
    def process_text(match):
        text = match.group(1).strip()
        if not text: return "><"
        return f">{text[:20]}...<" if len(text) > 20 else f">{text}<" # 截断20个字符

    cleaned = re.sub(r'>([^<]+)<', process_text, cleaned)

    # 5. 递归清除空容器
    protected_void_tags = {'img', 'input', 'svg', 'br', 'hr'}
    while True:
        pattern = r'<([a-zA-Z0-9\-]+)[^>]*>\s*</\1>'
        matches = list(re.finditer(pattern, cleaned, flags=re.IGNORECASE))
        if not matches:
            break
        new_cleaned = cleaned
        for m in reversed(matches):
            if m.group(1).lower() not in protected_void_tags:
                new_cleaned = new_cleaned[:m.start()] + new_cleaned[m.end():]
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned

    # 6. 整理格式
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.replace('><', '>\n<')
    
    return cleaned

async def save_cleaned_html(url: str, output_file: str):
    """
    抓取并保存清洗后的 HTML
    """
    print(f"🌟 开始处理目标: {url}")

    raw_file = output_file + "_raw.html"
    cleaned_file = output_file + "_cleaned.html"
    
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # 1. 导航并等待页面渲染（针对 B站 建议等待 networkidle）
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # 2. 获取渲染后的完整 HTML
            raw_content = await page.content()

            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(raw_content)
            
            # 3. 执行清洗逻辑
            print("🧹 正在执行 HTML 精简清洗...")
            cleaned_content = clean_html(raw_content)
            
            # 4. 保存到本地文件
            with open(cleaned_file, "w", encoding="utf-8") as f:
                f.write(cleaned_content)
            
            # 获取绝对路径方便你点击查看
            file_path = os.path.abspath(cleaned_file)
            raw_file_path = os.path.abspath(raw_file)
            print(f"✅ 处理成功！文件已保存至：\n{file_path}\n{raw_file_path}")
            
        except Exception as e:
            print(f"❌ 运行中发生错误: {e}")
        finally:
            await browser.close()
            print("🔒 浏览器已关闭。")

if __name__ == "__main__":
    # 配置区
    TARGET = "https://www.bilibili.com/video/BV1sF9QBXEoX/?spm_id_from=333.1387.favlist.content.click&vd_source=c6cb02e29405a36bf355c0d056529151"
    SAVE_NAME = "bilibili"
    
    asyncio.run(save_cleaned_html(TARGET, SAVE_NAME))