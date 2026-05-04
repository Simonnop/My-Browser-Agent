from langgraph.graph import StateGraph, START, END
from graph.state import AgentState
from graph.nodes import observe_node, think_node, action_node

def route_next_step(state: AgentState) -> str:
    """如果 is_finished 是 True 或者过了 max_steps 步就结束, 否则重新回到 observe_node 继续下一步"""
    if state.get("is_finished"):
        return END
    
    # 防止无限死循环
    if state.get("step_count", 0) >= state.get("max_steps", 10):
        print("[!] 达到最大操作步数，强制停止。")
        return END

    return "observe"

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("observe", observe_node)
    builder.add_node("think", think_node)
    builder.add_node("action", action_node)

    # 流程：一开始先去观察页面
    builder.add_edge(START, "observe")
    
    # 观察完成后去思考
    builder.add_edge("observe", "think")
    
    # 思考完成后去执行操作
    builder.add_edge("think", "action")
    
    # 执行完操作根据状态判断是结束还是重新观察
    builder.add_conditional_edges("action", route_next_step)

    return builder.compile()

app = build_graph()