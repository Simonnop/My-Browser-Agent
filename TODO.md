
# 开发任务列表 (TODO List)

## 1. 核心功能实现
- [x] HTML Cleaner: 基础清洗逻辑与标签过滤
- [x] Visual Subagent: 截图与基础感知 (Status/Focus Point/Keywords)
- [x] Indexer: 双表索引构建 (Key Table & Space Table)
- [x] Dual-RAG: 
    - [x] Key-RAG 语义检索
    - [x] Space-RAG 空间检索 (基于视觉聚焦半径 $p\%$)
- [x] Fusion Module: 全局去重、Graph Distance $n$ 路径扩展、顺序重组
- [x] Main Decision LLM: 思考与行动 ReAct 循环

## 2. 增强特性
- [x] 多标签页支持 (Tab perception, switch_tab, close_tab)
- [x] 动作鲁棒性:
    - [x] 多动作列表执行 (分号分隔)
    - [x] 候选动作集支持 (Fallback `||` 逻辑)
    - [x] 执行前合法性验证 (Editable/Visible check)
- [x] 记忆系统:
    - [x] 详细历史记录 (Step/Thought/Actions/Results)
    - [x] 记忆总结与压缩机制 (LLM Summarization)
- [x] 浏览器持久化: 支持 Cookie 与 Session (chrome_profile)

## 3. 观测与日志
- [x] Token 消耗统计 (每步及累计)
- [x] 详尽的控制台日志 (Step, Perception, RAG hits, Action, Usage)
- [x] Prompt 追溯日志 (保存每轮生成的完整 Prompt)
- [x] 截图追溯 (保存每步的截图)

## 4. 待办事项 (Next Steps)
- [ ] 优化 Space-RAG: 针对多屏幕/超长页面的坐标偏移优化
- [ ] 完善 Tool 库: 增加更多常用动作（如 hover, drag_and_drop 等）
- [ ] 引入重试机制: 在整个 ReAct 循环层面增加错误自愈逻辑
- [ ] 性能评估: 针对不同任务的成功率、Token 成本及耗时进行 Benchmark

---
*更新日期: 2026-05-01*
