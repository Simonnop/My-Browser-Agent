import os
import sys
import time
from dotenv import load_dotenv
from graph.graph import app
from graph.utils import create_initial_state
from browser.driver import driver
from graph.state import AgentState

load_dotenv()

# 设置默认通过9222端口连接(可在.env中修改)
if not os.getenv("DEBUG_PORT"):
    os.environ["DEBUG_PORT"] = "9222"

MAX_STEPS = int(os.getenv("MAX_STEPS", "10"))

def load_task(task_name: str) -> str:
    """
    从 tasks 目录加载任务内容，文件不存在时抛出 FileNotFoundError
    """
    task_path = os.path.join(os.path.dirname(__file__), "tasks", f"{task_name}.md")
    if not os.path.exists(task_path):
        raise FileNotFoundError(f"任务文件 {task_path} 不存在")

    with open(task_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def get_task():
    """
    获取任务: 优先从命令行参数读取 task_name，否则提示用户输入
    """
    if len(sys.argv) >= 2:
        task_name = sys.argv[1]
        return load_task(task_name)

    print("提示: 也可以通过命令行参数直接指定任务, 例如: python run.py custom")
    print("-" * 40)
    user_input = input("请输入任务 (按下<Enter>退出): ").strip()
    return user_input

def run_task(state: AgentState):
    """
    执行单次任务，支持重试
    """
    print(f"[*] 任务: {state['task']}")

    while True:
        try:
            print("[*] 正在启动 LangGraph ReAct 循环流...")
            app.invoke(state)
            print("[*] 任务完成。")
            return True
        except Exception as e:
            print(f"[-] 执行失败: {e}")
            print(f"[*] 即将重试...")
            time.sleep(5)

def main():
    """
    程序入口: 启动 Agent，支持命令行参数或交互式输入任务，并循环等待下一个任务
    """    

    if not os.getenv("LLM_API_KEY"):
        print("[-] 请先在 .env 文件或环境变量中设置 LLM_API_KEY")
        return

    if not driver.browser:
        print("[-] 未能连接到浏览器，程序退出。请检查对应端口的浏览器是否已经启动 (例如 --remote-debugging-port=9222)")
        return

    # 首次获取任务
    task_description = get_task()
    
    state = create_initial_state(task_description, driver.page, max_steps=MAX_STEPS)

    # 循环等待用户输入下一个任务
    while task_description:
        state["task"] = task_description
        run_task(state)
        print("-" * 40)
        task_description = input("请输入任务 (按下<Enter>退出): ").strip()
    
    print("[*] 再见!")

if __name__ == "__main__":
    main()
