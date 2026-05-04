import os
import time
from graph.state import AgentState

def create_initial_state(task: str, page, max_steps: int = 10) -> AgentState:
    """
    初始化图的数据状态
    """
    run_dir = os.path.join("logs", f"run_{int(time.time())}")
    os.makedirs(run_dir, exist_ok=True)
    return {
        "task": task,
        "messages": [],
        "current_som_image": "",
        "current_som_mapping": "",
        "current_focus_image": "",
        "current_scroll_image": "",
        "next_action": {},
        "todo_list": "初始任务，待规划",
        "step_count": 0,
        "max_steps": max_steps,
        "is_finished": False,
        "run_dir": run_dir
    }