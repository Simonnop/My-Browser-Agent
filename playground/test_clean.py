import asyncio
import re
import os
from playwright.async_api import async_playwright

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
    TARGET = "https://www.bilibili.com"
    SAVE_NAME = "bilibili"
    
    asyncio.run(save_cleaned_html(TARGET, SAVE_NAME))