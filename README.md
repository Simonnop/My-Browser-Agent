# Space-Aided Agent: 多模态浏览器智能体

Space-Aided Agent 是一个基于视觉引导与双路 RAG（检索增强生成）机制的先进浏览器 Agent 系统。它通过视觉子智能体提供空间与语义线索，结合高效的 DOM 清洗与双表索引技术，实现在复杂网页环境下的精准定位与低 Token 消耗的操作决策。

## 🚀 核心特性

- **视觉预感知 (Visual Perception)**: 引入专门的视觉子智能体，提供目标引导、滚动建议及任务状态核验。
- **双路 RAG 检索 (Dual-RAG)**:
    - **语义路 (Key-RAG)**: 采用**滑动窗口相似度算法**，针对关键词进行局部精准匹配，显著提升短文本及嵌套内容的召回率。
    - **空间路 (Space-RAG)**: 结合视觉感知提供的坐标，通过**视觉聚焦半径**进行检索，并内置**遮挡检测 (Occlusion Detection)**，确保仅暴露物理可见的节点。
- **高效双表索引 (Indexing)**:
    - **Key Table**: 智能收集 `title`、`aria-label`、`role` 等多维语义属性，实现 $O(1)$ 级别的关键词映射。
    - **Space Table**: 动态构建元素物理坐标索引，自动处理视口过滤与覆盖关系。
- **智能结果融合 (Fusion)**:
    - **路径扩展 (Path Expansion)**: 自动向上/下进行 DOM 树路径扩展，确保保留 UI 组件的完整上下文（如 Label 与 Input 的绑定关系）。
    - **去重与重组**: 对两路 RAG 结果进行全局去重，并按照原始 DOM 顺序重组 HTML，生成精简且合规的局部上下文。

## 🛠️ 技术架构

系统采用“预处理 - 感知 - 索引检索 - 融合 - 决策 - 执行”的五阶段流水线：

1. **Preprocessing**: 深度清洗 HTML，移除噪声，保留核心语义标签。
2. **Perception**: 视觉子智能体截图并识别目标位置。
3. **Indexing**: 构建 Space Table（坐标表）与 Key Table（关键词表）。
4. **Dual-RAG**: 并行进行空间与语义检索。
5. **Decision**: 主 LLM 结合局部 HTML 与压缩记忆输出 Action。
6. **Execution**: 工具层解析指令并执行，反馈结果至下一轮。

## 📦 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境
在根目录创建 `.env` 文件：
```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
HEADLESS=false
MAX_STEPS=20
```

### 3. 运行任务
将任务描述写入 `tasks/` 目录下的 `.md` 文件，然后运行：
```bash
python run.py <task_name>
```

## 📂 项目结构

- `agent/`: 核心逻辑，包含 ReAct 循环、Prompt 模板、LLM 客户端及记忆管理。
- `browser/`: 浏览器交互层，包含 HTML 清洗、双表索引构建及基础动作封装。
- `rag/`: 检索增强模块，包含语义检索、空间检索及结果融合逻辑。
- `tools/`: 辅助工具，如日志记录、文件保存等。
- `outputs/`: 记录执行过程中的截图、清洗后的 HTML 及 Prompt 日志。

## 📈 进阶功能

- **遮挡检测**: 索引器会自动识别被弹窗或遮罩层覆盖的元素，避免无效操作。
- **滚动居中**: 视觉子智能体会主动提示滚动，确保操作目标处于截图中心，提升 RAG 精度。
- **持久化上下文**: 支持 `USER_DATA_DIR` 配置，可复用已登录的浏览器 Session。
