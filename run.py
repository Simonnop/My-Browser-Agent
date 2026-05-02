import os
import sys
import time
from playwright.sync_api import sync_playwright
from graph.graph import app
from graph.utils import create_initial_state
from tools.save import SaveTool
from tools.log import LogTool
from dotenv import load_dotenv

load_dotenv()


def load_task(task_name: str) -> str:
    """
    从 tasks 目录加载任务内容
    """
    task_path = os.path.join(os.path.dirname(__file__), "tasks", f"{task_name}.md")
    if not os.path.exists(task_path):
        print(f"错误: 任务文件 {task_path} 不存在")
        sys.exit(1)

    with open(task_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def main():
    """
    程序入口: 启动浏览器并运行 LangGraph 图
    """
    if len(sys.argv) < 2:
        print("用法: python run.py <task_name>")
        print("示例: python run.py custom (将加载 tasks/custom.md)")
        return

    task_name = sys.argv[1]
    target_task = load_task(task_name)
    target_url = "https://www.baidu.com"

    LogTool.info(f"已加载任务 [{task_name}]: {target_task}")

    if not os.getenv("LLM_API_KEY"):
        LogTool.error("请先在 .env 文件或环境变量中设置 LLM_API_KEY")
        return

    max_steps = int(os.getenv("MAX_STEPS", "10"))
    headless = os.getenv("HEADLESS", "false").lower() == "true"
    user_data_dir = os.getenv("USER_DATA_DIR", "")

    # 浏览器伪装配置
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    extra_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-infobars",
    ]

    with sync_playwright() as p:
        if user_data_dir:
            user_data_path = os.path.abspath(user_data_dir)
            LogTool.info(f"使用持久化浏览器数据目录: {user_data_path}")
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_path,
                headless=headless,
                no_viewport=False,
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                args=extra_args,
                ignore_default_args=["--enable-automation"],
                locale="zh-CN",
                timezone_id="Asia/Shanghai"
            )
            page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = p.chromium.launch(
                headless=headless,
                args=extra_args,
                ignore_default_args=["--enable-automation"]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                locale="zh-CN",
                timezone_id="Asia/Shanghai"
            )
            page = context.new_page()

        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        LogTool.info(f"正在访问: {target_url}")
        page.goto(target_url)
        page.wait_for_load_state("networkidle")

        # 构建初始状态并运行 LangGraph 图
        initial_state = create_initial_state(target_task, page, max_steps=max_steps)
        app.invoke(initial_state)

        LogTool.info("循环结束。")

        # 结束后保持一会儿以便观察结果
        time.sleep(5)

        if not user_data_dir:
            browser.close()
        else:
            context.close()


if __name__ == "__main__":
    main()
