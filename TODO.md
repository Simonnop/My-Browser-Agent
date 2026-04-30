
# 产品需求文档 (PRD)：多模态浏览器 Agent (Space-Aided Agent)

## 1. 文档概述
本文档旨在定义一个基于视觉引导与双路 RAG（检索增强生成）机制的浏览器 Agent 系统。该系统通过视觉子智能体提供空间与语义线索，结合高效的 DOM 清洗与双表索引技术，实现在超长 HTML 环境下的精准定位与低 Token 消耗的操作决策。

## 2. 系统架构
系统采用“预处理 - 感知 - 索引检索 - 融合 - 决策”的五阶段流水线。

### 2.1 核心组件
- **HTML Cleaner**: 静态 HTML 净化器。
- **Visual Subagent**: 视觉感知子智能体（Vision-based）。
- **Indexer**: 双表索引构建器（Space Table & Key Table）。
- **Dual-RAG Engine**: 空间与语义双路检索引擎。
- **Fusion Module**: 全局去重与 DOM 重组模块。
- **Main LLM**: 主决策大模型。

---

## 3. 详细功能需求

### 3.1 HTML 深度预处理 (Preprocessing)
**需求描述**：在进入任何索引逻辑前，必须对原始 DOM 进行清洗，以移除 70% 以上的无效噪声。

**处理规则**：
1. **彻底移除块**: `script`, `style`, `noscript`, `iframe` 及其内部内容。
2. **过滤无关标签**: `link`, `meta`, `base`。
3. **图形简化**: `svg` 内部路径全部替换为 `...`，仅保留标签。
4. **资源占位**: 将所有 `src` 和 `srcset` 中的 Base64 Data URIs 替换为 `...`。
5. **标签白名单**: 仅保留交互及语义相关的标签（如 `div`, `span`, `a`, `button`, `input`, `form`, `ul`, `li`, `h1-h6`, `table` 等）。
6. **文本截断**: 标签间的文本长度若超过 **30 字符**，则保留前 30 个并加 `...`。
7. **格式优化**: 压缩多余空白符，并在标签间插入换行符以增强层级感。

### 3.2 双表索引构建 (Indexing)
**需求描述**：构建以 `node_id` 为核心的两张查询表，实现 $O(1)$ 或 $O(\log N)$ 的检索效率。

- **Key Table (关键词表)**:
    - **结构**: `Map<String, List<NodeID>>`
    - **内容**: 索引节点的 `innerText`、`placeholder`、`aria-label` 等关键文本属性。
- **Space Table (空间坐标表)**:
    - **结构**: `List<{id: NodeID, center: [x, y], rect: Rect}>`
    - **内容**: 存储所有清洗后可见元素的屏幕中心坐标及边界框。

### 3.3 视觉预感知 (Visual Subagent)
**需求描述**：通过截图分析，为后续 RAG 提供引导参数。
- **输出参数**:
    - `focus_point`: 目标区域中心坐标 $(x, y)$。
    - `keywords`: 目标语义关键词。
    - `status`: 当前已完成任务的总结。
    - `issues`: 识别出的阻碍（如弹窗覆盖、加载中等）。

### 3.4 双路 RAG 检索 (Dual-RAG)
系统并行启动以下两路检索逻辑：

1. **Key-RAG (语义路)**:
    - 输入 `keywords`，在 Key Table 中匹配最相关的 $top\text{-}k$ 个核心节点。
2. **Space-RAG (空间路)**:
    - 输入 `focus_point`，在 Space Table 中计算欧几里得距离，筛选最近的 $top\text{-}k$ 个核心节点。

**路径扩展规则**：
对于上述任一路检索命中的核心节点，向上/向下寻找路径距离 $n$（推荐 $n=3$）以内的所有相邻节点，以保证提供给大模型的 HTML 具有局部语义连贯性。

### 3.5 融合与去重 (Fusion & Deduplication)
**需求描述**：消除两路检索产生的数据冗余。
- **逻辑**:
    1. 获取两路 RAG 产生的节点合集。
    2. 基于 `node_id` 进行全局去重。
    3. 按原始 DOM 树的先后顺序重组去重后的节点。
    4. 构建最终的局部 HTML 代码块。

---

## 4. 非功能需求与技术参数

| 参数项 | 设定值 | 说明 |
| :--- | :--- | :--- |
| **$top\text{-}k$** | 3 - 5 | 每路 RAG 提取的核心节点数量 |
| **$n$ (Path Depth)** | 2 | 节点扩展的 DOM 路径层级深度 |
| **Text Threshold** | 30 | 节点纯文本截断阈值 |
| **Deduplication ID**| `data-agent-id` | 用于跨表追踪的唯一 ID |
| **Distance Algorithm**| Euclidean Distance | 空间距离计算方式 |

---

## 5. 业务流程 (Workflow)
1. **感知**: 视觉 Subagent 截图并输出 $(x, y)$ 和关键词。
2. **清洗**: 系统同步运行 `clean_html` 并构建双表索引。
3. **检索**:
    - 使用 $(x, y)$ 查 Space Table。
    - 使用关键词查 Key Table。
4. **提取**: 对命中的节点进行 $n$ 层路径扩展。
5. **融合**: 节点去重，生成紧凑的局部 DOM 片段。
6. **执行**: 主 LLM 结合 Subagent 的问题描述与局部 DOM，输出 Action 动作（如 `click(id=123)`）。

---

## 6. 异常处理
- **坐标偏离**: 若 Space-RAG 未找到 50px 范围内的节点，则完全依赖 Key-RAG 的检索结果。
- **关键词无匹配**: 若 Key-RAG 为空，则完全依赖 Space-RAG 提供的空间上下文。
- **Token 溢出**: 若 $top\text{-}k$ 和 $n$ 过大导致 Token 超过阈值，系统应自动缩小 $n$ 的值。