import asyncio
import json
from playwright.async_api import async_playwright

async def get_modern_accessibility_tree(url: str):
    """
    使用 CDP (Chrome DevTools Protocol) 获取最新版 Playwright 的可访问树。
    """
    print(f"🚀 启动浏览器并访问: {url}")
    
    async with async_playwright() as p:
        # 1. 启动 Chromium 浏览器
        browser = await p.chromium.launch(headless=True)
        # 建议设置 user_agent，避免部分网站拦截
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 2. 导航并等待页面主要部分加载
            # 对于 Bilibili，我们等待 networkidle 或者特定的 DOM 元素
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # 额外等待：确保 Bilibili 的动态推荐位加载
            await page.wait_for_timeout(2000) 
            
            print("✅ 页面加载完成，正在通过 CDP 获取全量无障碍树...")
            
            # 3. 创建 CDP 会话并请求全量可访问树
            client = await page.context.new_cdp_session(page)
            # Accessibility.getFullAXTree 返回的是浏览器内核最原始的节点信息
            result = await client.send("Accessibility.getFullAXTree")
            
            # 4. 格式化并输出
            # 注意：返回的数据通常在 'nodes' 键中
            ax_nodes = result.get("nodes", [])
            
            print(f"🔍 成功解析到 {len(ax_nodes)} 个无障碍节点。")
            
            # 将前 10 个节点作为示例展示，或完整保存到文件
            output_file = "bilibili_ax_tree.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
                
            print(f"💾 完整树结构已保存至: {output_file}")
            
        except Exception as e:
            print(f"❌ 运行过程中出错: {e}")
            
        finally:
            await browser.close()
            print("🏁 任务结束，浏览器已安全关闭。")

if __name__ == "__main__":
    TARGET = "https://www.bilibili.com"
    asyncio.run(get_modern_accessibility_tree(TARGET))