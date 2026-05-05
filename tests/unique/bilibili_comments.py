import asyncio
import os
import subprocess
import socket
import time
import hashlib
import json
import csv
import re
from playwright.async_api import async_playwright

# --- 配置区 ---
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9222
USER_DATA_DIR = os.path.abspath('./chrome_profile')

def check_browser_running():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', DEBUG_PORT)) == 0

def start_chrome():
    if not check_browser_running():
        print(f"[*] 正在启动浏览器...")
        cmd = [
            CHROME_PATH,
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={USER_DATA_DIR}",
            "--no-first-run"
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)

def parse_likes(like_str):
    """将点赞文本转换为整数，处理 '1.2万' 等情况"""
    if not like_str or like_str.strip() == "赞":
        return 0
    like_str = like_str.strip()
    if '万' in like_str:
        num = float(like_str.replace('万', ''))
        return int(num * 10000)
    # 只提取数字
    num_match = re.search(r'\d+', like_str)
    return int(num_match.group()) if num_match else 0

def get_comment_id(user, content):
    return hashlib.md5(f"{user}{content}".encode('utf-8')).hexdigest()

async def parse_page_comments(page, results_dict):
    threads = await page.locator("bili-comment-thread-renderer").all()
    new_found = 0
    
    for thread in threads:
        try:
            main_comment = thread.locator("bili-comment-renderer#comment")
            user_name = await main_comment.locator("#user-name a").first.inner_text(timeout=300)
            content = await main_comment.locator("#content #contents").first.inner_text(timeout=300)
            pub_date = await main_comment.locator("#pubdate").first.inner_text(timeout=300)
            like_count_raw = await main_comment.locator("#like #count").first.inner_text(timeout=300)
            
            # 关键：转换点赞数为整数
            likes = parse_likes(like_count_raw)

            c_id = get_comment_id(user_name, content)
            if c_id not in results_dict:
                results_dict[c_id] = {
                    "user": user_name.strip(),
                    "content": content.strip().replace('\n', ' '),
                    "date": pub_date.strip(),
                    "likes": likes  # 存储为整数
                }
                new_found += 1
        except:
            continue
    return new_found

def save_results(all_comments):
    if not all_comments:
        print("[!] 没有采集到数据。")
        return

    # 1. 转换成列表并按照 likes 字段降序排序
    data = list(all_comments.values())
    data.sort(key=lambda x: x['likes'], reverse=True) # reverse=True 表示从大到小

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # 2. 保存 JSON
    json_file = f"bilibili_sorted_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    # 3. 保存 CSV
    csv_file = f"bilibili_sorted_{timestamp}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    print(f"\n[√] 已按点赞量排序并保存：")
    print(f"    - CSV : {csv_file} (最高赞: {data[0]['likes']})")

async def run_crawler(max_pages=20):
    start_chrome()
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{DEBUG_PORT}")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            all_comments = {} 
            for i in range(max_pages):                
                # 检查是否触底
                if await page.locator("div#end .bottombar:has-text('没有更多评论')").count() > 0:
                    break

                await page.mouse.wheel(0, 10000)
                await asyncio.sleep(0.5)
            
            await parse_page_comments(page, all_comments)

            save_results(all_comments)

        except Exception as e:
            print(f"[X] 出错: {e}")

if __name__ == "__main__":
    asyncio.run(run_crawler(max_pages=10))