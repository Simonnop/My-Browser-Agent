from typing import TypedDict, Any, Optional


class AgentState(TypedDict, total=False):
    # 任务
    task: str                     # 用户任务描述
    step: int                     # 当前步骤（从 1 开始）
    max_steps: int                # 最大步数

    # 浏览器（不可序列化，仅运行时使用）
    page: Any                     # Playwright Page 对象
    screenshot_path: str          # 当前截图路径
    page_info: str                # 当前页面标题和 URL 摘要

    # RAG 输入（上一轮 LLM 输出，供本轮 RAG 检索使用）
    focus_point: list             # 上一轮聚焦坐标 [x, y]（首回合默认视口中心）
    keywords: list                # 上一轮页面关键词列表（首回合从任务描述提取）

    # RAG 结果
    space_nodes: list             # 空间 RAG 命中节点 ID 列表
    key_nodes: list               # 语义 RAG 命中节点 ID 列表
    local_html: str               # 融合后的局部 HTML

    # LLM 决策输出
    thought: str                  # LLM 思考过程
    action: str                   # LLM 输出的原始动作字符串

    # 动作执行结果
    action_result: str            # 动作执行结果消息
    action_success: bool          # 动作是否成功
    is_finish: bool               # 是否触发了 finish 动作

    # 记忆
    history: list                 # 步骤历史记录列表
    past_summary: str             # 压缩后的历史总结
    token_usage: dict              # Token 消耗统计
