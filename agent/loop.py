import os
from playwright.sync_api import Page
from .llm import LLMClient
from .visual import VisualSubagent
from browser.clean import clean_html
from browser.table import Indexer
from browser.capture import BrowserCapture
from .tools import AgentTools
from .memory import AgentMemory
from tools.log import LogTool
from tools.save import SaveTool
from rag.key_rag import KeyRAG
from rag.space_rag import SpaceRAG
from rag.fusion import FusionModule

class AgentLoop:
    """
    ReAct 循环控制器
    """
    def __init__(self, page: Page, max_steps: int = 10):
        self.page = page
        self.max_steps = max_steps
        self.llm = LLMClient()
        self.visual_subagent = VisualSubagent(self.llm)
        self.tools = AgentTools(self.page)
        self.memory = AgentMemory(max_history=5)

    def run(self, task: str):
        """
        开始 ReAct 循环: 感知 -> 思考 -> 行动
        """
        LogTool.info(f"开始任务: {task}")
        
        for step in range(self.max_steps):
            LogTool.step(step + 1, self.max_steps)
            
            # 0. 获取所有标签页信息
            pages, tabs_display = BrowserCapture.get_tabs_info(self.page)
            LogTool.info(f"当前标签页:\n{tabs_display}")

            # 1. 截图与视觉预感知
            screenshot_path = os.path.join("outputs", f"step_{step}.jpg")
            # 优化截图：禁用动画等待，避免隐藏滚动条导致的闪烁
            self.page.screenshot(path=screenshot_path, animations="disabled", caret="initial")
            
            LogTool.info(f"正在分析截图 (Step {step + 1})...")
            perception, visual_usage = self.visual_subagent.perceive(
                screenshot_path, 
                task, 
                tabs_display,
                self.memory.get_formatted_history(),
                save_prompt_path=os.path.join("outputs", f"step_{step}_visual_prompt.txt")
            )
            LogTool.perception(
                perception.get('status'), 
                perception.get('todo'),
                perception.get('issues'), 
                perception.get('is_completed', False)
            )
            LogTool.usage(visual_usage, self.llm.get_token_usage())

            # 2. 清洗 HTML 与构建索引
            LogTool.info("正在处理 DOM 并构建索引...")
            indexer = Indexer(self.page)
            indexer.build_index()
            
            space_table = indexer.get_space_table()
            key_table = indexer.get_key_table()
            
            html_with_ids = self.page.content()
            cleaned_html = clean_html(html_with_ids)
            
            # 保存清洗后的 HTML
            SaveTool.save_text(cleaned_html, os.path.join("outputs", f"step_{step}_cleaned.html"))

            # 3. 双路 RAG 检索
            top_k = int(os.getenv("TOP_K", "3"))
            path_depth = int(os.getenv("PATH_DEPTH", "2"))
            radius_percent = float(os.getenv("FOCUS_RADIUS_PERCENT", "5.0"))

            space_rag = SpaceRAG(space_table)
            key_rag = KeyRAG(key_table)
            
            # 获取视口大小用于空间检索
            viewport_size = self.page.viewport_size
            space_nodes = space_rag.search(
                perception.get('focus_point', []), 
                viewport_size,
                radius_percent=radius_percent
            )
            key_nodes = key_rag.search(perception.get('keywords', []), top_k=top_k)

            # 打印 RAG 命中日志
            LogTool.info(f"RAG 检索完成:")
            LogTool.info(f"  - 空间命中 ({len(space_nodes)} 个): {', '.join(space_nodes)}")
            LogTool.info(f"  - 语义命中 ({len(key_nodes)} 个): {', '.join(key_nodes)}")

            # 4. 融合
            fusion = FusionModule(cleaned_html)
            local_html = fusion.fuse(key_nodes, space_nodes, path_depth=path_depth)

            # 5. 主 LLM 决策
            LogTool.info("正在思考下一步行动...")
            response, main_usage = self.llm.ask_main_agent(
                task=task,
                step=step + 1,
                max_steps=self.max_steps,
                perception=perception,
                tabs_display=tabs_display,
                local_html=local_html,
                history=self.memory.get_formatted_history(),
                save_prompt_path=os.path.join("outputs", f"step_{step}_main_prompt.txt")
            )
            
            # 解析 Thought 和 Action
            import re
            thought_match = re.search(r'Thought:\s*(.+)', response, re.DOTALL)
            thought = thought_match.group(1).split('Action:')[0].strip() if thought_match else "无思考过程"
            
            # 仅解析第一个 Action
            action_match = re.search(r'Action:\s*(.+)', response)
            action_str = action_match.group(1).strip() if action_match else "无动作指令"
            
            LogTool.action(thought, action_str)
            LogTool.usage(main_usage, self.llm.get_token_usage())
            
            if action_match:
                # 通过工具层（中间层）执行动作
                success, new_page, executed_action, action_result = self.tools.execute(action_str)
                
                # 记录记忆
                self.memory.add_step(step + 1, thought, executed_action, action_result, perception.get('status'))
                
                if success:
                    # 如果活跃页面发生变更，同步 Loop 层的 page 引用
                    if new_page:
                        self.page = new_page
                    
                    # 检查是否包含 finish 动作
                    if "finish" in executed_action.lower():
                        LogTool.info("任务完成！")
                        break
                else:
                    LogTool.error("动作执行过程中出现失败。")
                
                # 动作执行后稍微等待，确保浏览器状态（如新标签页）同步完成
                self.page.wait_for_timeout(1000)
            else:
                LogTool.error("未找到有效的 Action 指令。")
                # 记录空动作到记忆
                self.memory.add_step(step + 1, thought, "无动作", "不合法: 未输出 Action", perception.get('status'))
            
            # 记忆压缩
            if self.memory.should_compress():
                LogTool.info("正在压缩历史记忆...")
                compress_usage = self.memory.compress(self.llm)
                if compress_usage:
                    LogTool.usage(compress_usage, self.llm.get_token_usage())

        LogTool.info("循环结束。")
