# My Browser Agent

一个基于 Playwright 和大语言模型（LLM）驱动的模块化浏览器自动化代理框架。与基础的浏览器操作脚本相比，本项目侧重于系统鲁棒性、自我学习机制及 DOM 节点的精简优化。项目分离了核心执行逻辑与具体业务任务，可灵活适应诸如复杂表单投递、自动化录入等定制化网页操作。

## 核心特性

1. **自我学习与经验积累 (Self-Learning)**
   LLM 的返回规范中包含 `new_skill` 字段。仅当本轮 `actions` 含 `exit`（任务结束）时，系统才会将该轮的可复用经验追加至当前任务的 `skills.md`；中间轮次的 `new_skill` 字段会被忽略。

2. **选择器平滑降级 (Selector Fallback)**
   针对网页 DOM 易变的问题，核心交互动作（如 `click`, `fill`, `clear`）支持传入 `selectors` 数组。执行器在首选 CSS 选择器失效时，会自动尝试候选选择器，提升元素定位的成功率。

3. **DOM 上下文压缩 (DOM Compression)**
   内置 DOM 清理管道，在将页面源码发送给 LLM 前，会自动剔除 `script`/`style`/`iframe` 等无关标签，精简 SVG 路径，截断长文本节点和冗余属性。有效节约 Token 消耗并降低模型注意力干扰。

4. **HTML RAG 聚焦 (HTML RAG Focus)**
   每轮循环开始前，系统会基于 LLM 输出的检索词（rag_keywords），使用 embedding 向量相似度对 clean_html 中的每个 DOM 节点打分排序，仅将 Top-K 相关节点及其上下文片段注入提示词。大幅减少无关节点的 token 浪费，同时保持对关键表单元素的注意力集中。

5. **Skills / Attachment RAG**
   对 `skills.md` 和 `attachment.md` 也支持基于 embedding 的语义检索，根据当前任务检索最相关的经验条目和数据块注入提示词，避免全量加载低相关内容。

6. **任务解耦架构 (Task-Oriented Design)**
   系统底层指令（schema、交互规则）与具体业务数据（目标说明、附件数据、技能点）完全隔离。新增自动化场景只需在 `tasks/` 目录下建立对应模块即可。

7. **防死锁机制 (Anti-Infinite-Loop)**
   执行引擎负责监控历史操作流。若检测到连续的循环内 LLM 输出了完全一致的操作指令且页面状态未发生实质流转，系统主动向当前上下文中注入强烈的**系统级干预警告（System Intervention Feedback）**，迫使其触发反思并尝试全新策略（如滚动页面、更换候选选择器等），从而保留任务连贯性破局。

8. **提示词前缀缓存优化 (Prompt Prefix Cache Optimization)**
   提示词拼装按「静态核心指令 → 任务描述 → 页面遥测 → HTML 正文」的顺序排列，越靠前、越稳定的内容越长，有助于 LLM 服务商按字节前缀命中缓存，降低延迟与成本。

## 项目结构

```text
My-Browser-Agent/
├── agent/                  # 核心引擎目录
│   ├── config.py           # 环境变量与配置参数
│   ├── llm.py              # LLM 通信封装（OpenAI 兼容接口）
│   ├── embedding.py        # Embedding 模型封装（fastembed + BGE）
│   ├── dom_utils.py        # DOM 精简处理逻辑
│   ├── rag.py              # RAG 检索管道
│   ├── actions.py          # 动作执行器（点击、输入、滚动、导航等）
│   ├── prompt.py           # 单轮用户提示词拼装器（前缀缓存友好）
│   └── prompts/            # 全局系统指令集
│       ├── __init__.py
│       ├── system.md       # 系统角色与行为准则
│       ├── schema.md       # Action JSON Schema 定义
│       └── rules.md        # 交互规则与安全约束
├── tasks/                  # 业务任务隔离区
│   ├── __init__.py         # 任务文件加载器
│   └── fill_resume/        # 示例任务：简历填写
│       ├── task.md         # 当前任务目标与执行指引
│       ├── attachment.md   # 任务相关数据或预设附件
│       └── skills.md       # 自我学习生成的经验集
├── outputs/                # 运行日志与中间状态文件保留
│   ├── page_{ts}.html      # 原始页面源码快照
│   ├── page_{ts}.png       # 页面截图（可选）
│   ├── llm_prompt_{ts}.txt # 发给 LLM 的完整提示词
│   ├── llm_answer_{ts}.txt # LLM 回答摘要
│   ├── llm_raw_{ts}.txt    # LLM 原始输出
│   └── rag_html_{ts}.json  # HTML RAG 分块快照
├── chrome_profile/         # 浏览器用户数据持久化目录
└── main.py                 # 项目主入口
```

## 快速开始

### 1. 环境准备

准备 Python 3.9+ 环境并安装依赖：

```bash
pip install openai playwright beautifulsoup4 fastembed
playwright install chromium
```

### 2. 配置参数

通过环境变量配置大模型和嵌入模型：

```bash
# LLM 配置（必填，无默认值）
export LLM_API_KEY="sk-xxxxxxxxxxxxxxxxxxx"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export LLM_MODEL="qwen3.6-flash"

# Embedding 模型（可选，默认 BAAI/bge-small-zh-v1.5）
export EMBEDDING_MODEL="BAAI/bge-small-zh-v1.5"

# 运行时参数
export ENABLE_SCREENSHOT="1"                   # 是否携带截图（1=开启，0=关闭）
export MAX_CYCLES="200"                        # 最大循环次数
export LOOP_INTERVAL_SEC="1"                   # 每轮间隔（秒）
export RESET_PROFILE="0"                       # 是否重置浏览器配置文件
export HTML_RAG_MAX_DEPTH="40"                 # RAG 遍历深度
export HTML_RAG_WINDOW_N="400"                 # RAG 上下文窗口大小
export HTML_RAG_BLOCKS_K="5"                   # RAG 返回 Top-K 块数
```

### 3. 运行任务

默认运行 `fill_resume` 任务：

```bash
python main.py
```

指定运行其他任务：

```bash
python main.py custom_task_name
```

## 新建自定义任务

1. 在 `tasks/` 目录下创建新的任务文件夹（例如 `tasks/buy_coffee/`）。
2. 在该目录下至少创建 `task.md`，描述任务目标和关键步骤。建议在任务描述中引导 Agent 的第一步使用 `{"type": "goto", "url": "目标地址"}` 来定位网页。
3. 可选准备 `attachment.md`（存放任务需要的确切文本、表单数据等），按 `### 区块标题` 分隔数据块以支持 RAG 检索。
4. 可选准备 `skills.md`（初始可留空，Agent 会在任务结束后自动积累新技能）。
5. 运行 `python main.py buy_coffee` 开始自动化任务。

## 工作流程

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  页面状态    │ ──→ │  DOM 清洗    │ ──→ │  HTML RAG   │
│  (URL/HTML)  │     │ (remove 无用 │     │  (节点打分  │
│              │     │  标签/截断)  │     │   取Top-K)  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                    ┌─────────────┐     ┌──────▼──────┐
                    │  动作执行    │ ←── │ 提示词拼装  │
                    │  (Playwright│     │ (前缀缓存  │
                    │   驱动)     │     │  友好顺序)  │
                    └─────────────┘     └──────┬──────┘
                         │                     │
                    ┌────▼─────┐     ┌────────▼────────┐
                    │ 防死锁检测│ ←── │  LLM 推理      │
                    │ (对比上轮 │     │ (answer +       │
                    │  操作)    │     │  actions)       │
                    └──────────┘     └─────────────────┘
```

每次循环：

1. **采集页面状态** — 获取当前页面的完整 HTML 和可选截图。
2. **DOM 清洗** — 移除无用标签、Base64 数据、长文本等，生成精简版 HTML。
3. **RAG 检索** — 使用上一轮的检索词对 DOM 节点做向量相似度打分，筛选出 Top-K 最相关节点及其上下文。
4. **提示词拼装** — 按前缀缓存友好顺序组合核心指令、任务描述、历史对话、页面遥测、RAG 聚焦块等内容。
5. **LLM 推理** — 将提示词（含可选截图）发送给 LLM，解析 JSON 格式的回复。
6. **执行动作** — 按序执行 LLM 输出的操作（点击、输入、导航等），失败时尝试候选选择器。
7. **自我学习** — 如果本轮动作包含 `exit`，将 `new_skill` 追加到 `skills.md`。
8. **防死锁检测** — 对比连续两轮的操作序列，若完全一致则注入系统级干预警告。
9. **等待下一轮** — 记录日志到 `outputs/` 目录后进入下一循环。
