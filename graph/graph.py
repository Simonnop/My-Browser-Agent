from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import perceive_node, index_and_rag_node, decide_node, route_action_node, compress_memory_node
from .edges import should_continue, route_after_action


def build_graph():
    """
    组装并编译 LangGraph 状态图。
    """
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("perceive", perceive_node)
    graph.add_node("index_and_rag", index_and_rag_node)
    graph.add_node("decide", decide_node)
    graph.add_node("route_action", route_action_node)
    graph.add_node("compress_memory", compress_memory_node)

    # 入口
    graph.set_entry_point("perceive")

    # 条件边
    graph.add_conditional_edges("perceive", should_continue, {
        "end": END,
        "index_and_rag": "index_and_rag",
    })

    graph.add_edge("index_and_rag", "decide")
    graph.add_edge("decide", "route_action")

    graph.add_conditional_edges("route_action", route_after_action, {
        "end": END,
        "compress_memory": "compress_memory",
        "perceive": "perceive",
    })

    graph.add_edge("compress_memory", "perceive")

    return graph.compile()


# 预编译的图实例，供 run.py 直接导入使用
app = build_graph()
