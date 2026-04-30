# 视觉预感知 (Visual Subagent)
'''
需求描述：通过截图分析，为后续 RAG 提供引导参数。
输出参数:
    - focus_point: 目标区域中心坐标 $(x, y)$。
    - keywords: 目标语义关键词。
    - status: 当前已完成任务的总结。
    - issues: 识别出的阻碍（如弹窗覆盖、加载中等）。
'''