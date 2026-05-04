import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

# 设置默认通过9222端口连接(可在.env中修改)
if not os.getenv("DEBUG_PORT"):
    os.environ["DEBUG_PORT"] = "9222"

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
    程序入口: 启动 Agent，接管已在指定端口运行的浏览器实例，并运行 LangGraph 图
    """
    if len(sys.argv) < 2:
        print("用法: python run.py <task_name>")
        print("示例: python run.py custom (将加载 tasks/custom.md)")
        return

    task_name = sys.argv[1]
    target_task = load_task(task_name)
    print(f"[*] 已加载任务 [{task_name}]: {target_task}")

    if not os.getenv("LLM_API_KEY"):
        print("[-] 请先在 .env 文件或环境变量中设置 LLM_API_KEY")
        # return (注满开发时可能有其它大模型可省略)

    max_steps = int(os.getenv("MAX_STEPS", "10"))
    
    # 从 tools.browser 导入并拉起已连接的实例，保证全局只有这一个驱动点
    from tools.browser import driver
    if not driver.browser:
        print("[-] 未能连接到浏览器，程序退出。请检查对应端口的浏览器是否已经启动 (例如 --remote-debugging-port=9222)")
        return

    print("[*] 浏览器关联成功。")
    try:
        from graph.graph import app
        from graph.utils import create_initial_state
        initial_state = create_initial_state(target_task, driver.page, max_steps=max_steps)
        print("[*] 正在启动 LangGraph ReAct 循环流...")
        app.invoke(initial_state)
    except Exception as e:
        print(f"[-] 执行过程中发生异常: {e}")

    print("[*] 循环结束。")

if __name__ == "__main__":
    main()
