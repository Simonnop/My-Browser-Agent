import time

class LogTool:
    """
    日志工具
    """
    @staticmethod
    def info(message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [INFO] {message}")

    @staticmethod
    def error(message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [ERROR] {message}")

    @staticmethod
    def step(step_num: int, total_steps: int):
        print(f"\n" + "="*20 + f" STEP {step_num}/{total_steps} " + "="*20)

    @staticmethod
    def perception(status: str, todo: str = None, issues: str = None, is_completed: bool = False):
        print(f"感知状态: {status}")
        if todo:
            print(f"本轮待办: {todo}")
        if issues:
            print(f"发现问题: {issues}")
        if is_completed:
            print(f"视觉确认: 任务已完成")

    @staticmethod
    def action(thought: str, action: str):
        print(f"思考: {thought}")
        print(f"执行: {action}")

    @staticmethod
    def usage(usage_dict: dict, total_usage: dict):
        print(f"[Tokens] 本步消耗: 输入={usage_dict['input']}, 输出={usage_dict['output']} | "
              f"累计消耗: 输入={total_usage['total_input_tokens']}, 输出={total_usage['total_output_tokens']}, "
              f"总计={total_usage['total_tokens']}")
