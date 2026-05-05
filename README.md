# My Browser Agent

My Browser Agent 是一个基于大语言模型（LLM）的自动化浏览器控制代理。它利用 **LangGraph** 构建 ReAct 工作流，并通过 **Playwright** 基于 CDP (Chrome DevTools Protocol) 自动接管本地 Chrome 浏览器，像人类一样自主执行网页浏览、点击、输入等复杂任务。

## ✨ 特性

- **即插即用**：直接挂载和接管本地已安装的 Chrome 浏览器，支持持久化的 Chrome 配置文件（不会丢失登录态）。
- **Set-of-Marks (SOM)**：基于 PIL 离线绘制的非侵入式 SOM 技术，包含高分屏适配、被遮挡元素过滤等诸多细节优化。
- **LangGraph 工作流**：标准灵活的 ReAct (Reason + Act) 循环，支持思考、观察与动作执行。
- **交互式与批处理**：支持在终端直接对话输入任务，也支持通过 Markdown 文件加载预设任务。

## 🔍 SOM (Set-of-Marks) 核心优化

本项目在元素提取方面经过了诸多特别的细节设计，这让其在交互精确度上具有很大优势：
1. **非侵入式离线绘制**：获取坐标后使用 Python (`PIL`) 对 Playwright 截图在离线状态下绘制标签与边框，不向原网页 DOM 动态注入节点或样式，避免触发反作弊机制，防止破坏前端框架视图并避免引发样式坍塌和排版错位。
2. **Checkbox / Radio 免过滤豁免**：现代前端 UI 库常将真实的 Checkbox 设为透明（`opacity: 0`），本项目放宽了特定元素的可见性判定，防止重要表单组件因为美化层而被漏抓。
3. **真实顶层可视探活 (True Top-Level Visibility)**：结合 `document.elementFromPoint` 和重叠面积对比逻辑，动态剔除虽在 DOM 树中被展示，但实际上被 Modal 浮层或 Toast Banner 物理遮挡、相互包裹的“假可见”元素。页面标签大幅瘦身，提供给大模型的图片更加整洁清晰。
4. **高分屏 (Retina) 自适应**：结合 `window.devicePixelRatio` 映射逻辑像素点坐标到物理截图像素点，确保高分屏 Mac 等设备下的标签套圈完美对齐不偏移。

## 📦 环境依赖

- **Python**: >= 3.10
- 根据个人系统安装好 **Google Chrome**

## 🚀 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/your-repo/My-Browser-Agent.git
cd My-Browser-Agent

# 推荐使用虚拟环境
pip install -r requirements.txt

# 安装 Playwright 浏览器内核 (可选，通常本项目通过 CDP 连接原生 Chrome，但仍建议安装)
playwright install chromium
```

### 2. 配置环境变量

复制环境模板，并配置大模型访问密钥（推荐使用支持良好视觉处理的 GPT-4o 或其他多模态大语言模型）：

```bash
cp .env.example .env
```
在 `.env` 文件中填入：
- `LLM_API_KEY`: 你的大模型 API Key
- `LLM_BASE_URL`: URL（例如 `https://api.openai.com/v1`）
- `LLM_MODEL`: 模型名称（例如 `gpt-4o`）

### 3. 运行 Agent

本项目支持两种方式运行任务。

**方式一：交互式运行**
启动脚本后输入你要执行的指令：
```bash
python run.py
```

**方式二：通过任务文件运行**
执行预置在 `tasks/` 目录下的 Markdown 任务（例如 `tasks/test.md`）：
```bash
python run.py test
```

## 📁 核心目录说明

- `browser/`：浏览器驱动模块，包含 Playwright CDP 连接逻辑，以及用于页面元素标记（SOM）的 JavaScript 注入脚本。
- `graph/`：LangGraph 定义目录，核心节点（`think`, `action`, `observe`）与 Agent 状态维护。
- `llm/`：大模型接口与 Prompt 模板生成逻辑。
- `tasks/`：预设的常用任务脚本目录（Markdown格式）。
- `chrome_profile/`：本地浏览器配置缓存，自动生成的接管数据存放目录。

## ⚠️ 注意事项

- **Mac 默认 Chrome 路径**：在 `browser/driver.py` 中的 `CHROME_PATH` 默认指定为 MacOS 下的 Google Chrome 路径。若在 Windows/Linux 下运行，请修改为对应的 Chrome 可执行文件路径。
- **端口冲突**：默认占用 `9222` debug 端口，如果已运行使用了该端口的无头浏览器，请在 `.env` 中通过 `DEBUG_PORT` 进行修改并关闭已有的所有 Chrome 进程后再试。

