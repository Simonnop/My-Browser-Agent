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
from tools.collect_store import COLLECT_CONTEXT_PATH, reset_collect_context
from .collector import Collector

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
        
        if os.getenv("COLLECT_CONTEXT_CLEAR_ON_RUN", "1").lower() not in ("0", "false", "no"):
            reset_collect_context()

        for step in range(self.max_steps):
            LogTool.step(step + 1, self.max_steps)
            
            # 每轮开头：合并标签页（保留最新）并同步工具层引用
            self.page = BrowserCapture.ensure_single_tab(self.page)
            self.tools.set_page(self.page)
            LogTool.info(BrowserCapture.get_page_info(self.page))

            # 1. 截图与视觉预感知
            screenshot_path = os.path.join("outputs", f"step_{step}.jpg")
            fix_screenshot_path = os.path.join("outputs", f"_current_screen.jpg")
            self.page.screenshot(path=screenshot_path, animations="disabled", caret="initial")
            self.page.screenshot(path=fix_screenshot_path, animations="disabled", caret="initial")
            
            LogTool.info(f"正在分析截图 (Step {step + 1})...")
            perception, visual_usage = self.visual_subagent.perceive(
                screenshot_path, 
                task, 
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

            # 1.5 Collected RAG: 视觉感知后按需检索已采集数据
            use_collect_info = perception.get('use_collect_info', False)
            collected_context = self.memory.get_collected_context(use_collect_info)
            if collected_context:
                LogTool.info("use_collect_info=true，已从采集上下文文件注入数据")

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
            collected_prefix = (
                f"已采集数据（全文读取自固定文件 {COLLECT_CONTEXT_PATH}）:\n{collected_context}\n\n"
                if collected_context
                else ""
            )
            response, main_usage = self.llm.ask_main_agent(
                task=task,
                step=step + 1,
                max_steps=self.max_steps,
                perception=perception,
                local_html=local_html,
                history=self.memory.get_formatted_history(),
                save_prompt_path=os.path.join("outputs", f"step_{step}_main_prompt.txt"),
                collected_context=collected_prefix,
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
                # 处理 collect 动作
                collect_match = re.match(r'collect\(task="(.+?)"\)', action_str)
                if collect_match:
                    collect_task = collect_match.group(1)
                    LogTool.info(f"启动采集子循环: {collect_task}")
                    collector = Collector(self.page, self.llm)
                    items = collector.collect(collect_task, loop_step=step + 1)
                    self.memory.record_collection(collect_task, items)
                    self.memory.add_step(step + 1, thought, action_str, f"采集到 {len(items)} 条数据", perception.get('status'))
                else:
                    # 通过工具层（中间层）执行动作
                    success, executed_action, action_result = self.tools.execute(action_str)
                    
                    # 同步 Loop 层的 page 引用
                    self.page = self.tools.page
                    
                    # 记录记忆
                    self.memory.add_step(step + 1, thought, executed_action, action_result, perception.get('status'))
                    
                    if success:
                        # 检查是否包含 finish 动作
                        if "finish" in executed_action.lower():
                            LogTool.info("任务完成！")
                            break
                    else:
                        LogTool.error("动作执行过程中出现失败。")
                
                # 动作执行后稍微等待
                self.page.wait_for_timeout(1000)
            else:
                LogTool.error("未找到有效的 Action 指令。")
                # 记录空动作到记忆
                self.memory.add_step(step + 1, thought, "无动作", "不合法: 未输出 Action", perception.get('status'))
            
            # 记忆压缩
            if self.memory.should_compress():
                LogTool.info("正在压缩历史记忆...")
                compress_usage = self.memory.compress(self.llm, task=task)
                if compress_usage:
                    LogTool.usage(compress_usage, self.llm.get_token_usage())

        LogTool.info("循环结束。")
