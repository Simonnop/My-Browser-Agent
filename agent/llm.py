import os
import json
import base64
import re
from typing import Optional, Dict, List, Any, Tuple
from openai import OpenAI
from dotenv import load_dotenv
from .prompt import VISUAL_PERCEPTION_PROMPT, MAIN_AGENT_PROMPT, MEMORY_COMPRESSION_PROMPT
from tools.log import LogTool

load_dotenv()

class LLMClient:
    def __init__(self, model: str = None):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Token 消耗统计
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def ask_visual_subagent(self, screenshot_path: str, task_description: str, tabs_display: str, history: str, save_prompt_path: str = None) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        封装视觉感知请求
        返回: (感知结果dict, 本次消耗usage_dict)
        """
        with open(screenshot_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        prompt = VISUAL_PERCEPTION_PROMPT.format(
            task_description=task_description,
            tabs_display=tabs_display,
            history=history
        )
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]

        res_content, usage_dict = self._call_llm(
            messages=messages, 
            response_format={"type": "json_object"},
            save_prompt_path=save_prompt_path
        )
        
        fallback_perception = {
            "focus_point": [0, 0],
            "keywords": [],
            "suggested_tab_index": None,
            "suggested_scroll": False,
            "status": "感知解析失败",
            "todo": "请尝试刷新页面或重新观察",
            "issues": "JSON 解析错误",
            "is_completed": False
        }
        
        return self._parse_json(res_content, fallback_perception), usage_dict

    def ask_main_agent(self, task: str, step: int, max_steps: int, perception: dict, tabs_display: str, local_html: str, history: str, save_prompt_path: str = None) -> Tuple[str, Dict[str, int]]:
        """
        封装主决策请求
        返回: (动作str, 本次消耗usage_dict)
        """
        prompt = MAIN_AGENT_PROMPT.format(
            task=task,
            step=step,
            max_steps=max_steps,
            history=history,
            status=perception.get('status'),
            todo=perception.get('todo'),
            issues=perception.get('issues'),
            suggested_tab=perception.get('suggested_tab_index'),
            suggested_scroll=perception.get('suggested_scroll', False),
            is_completed=perception.get('is_completed', False),
            tabs_display=tabs_display,
            local_html=local_html
        )

        res_content, usage_dict = self._call_llm(
            messages=[{"role": "user", "content": prompt}],
            save_prompt_path=save_prompt_path
        )
        
        return res_content, usage_dict

    def ask_for_summary(self, history_to_compress: str, existing_summary: str) -> Tuple[str, Dict[str, int]]:
        """
        请求 LLM 压缩记忆
        返回: (总结str, 本次消耗usage_dict)
        """
        prompt = MEMORY_COMPRESSION_PROMPT.format(
            history_to_compress=history_to_compress,
            existing_summary=existing_summary
        )

        res_content, usage_dict = self._call_llm(
            messages=[{"role": "user", "content": prompt}]
        )

        return res_content.strip(), usage_dict


    def get_token_usage(self) -> Dict[str, int]:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens
        }

    def _call_llm(self, messages: List[Dict[str, Any]], response_format: Optional[Dict] = None, save_prompt_path: Optional[str] = None) -> Tuple[str, Dict[str, int]]:
        """
        统一的 LLM 调用封装，处理 Token 统计与日志保存
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format=response_format,
            extra_body={"enable_thinking": False, "thinking": {"type": "disabled"}},
        )
        
        res_content = response.choices[0].message.content
        usage = response.usage
        
        self.total_input_tokens += usage.prompt_tokens
        self.total_output_tokens += usage.completion_tokens
        
        usage_dict = {
            "input": usage.prompt_tokens,
            "output": usage.completion_tokens
        }

        if save_prompt_path:
            from tools.save import SaveTool
            # 提取消息中的文本内容用于保存日志
            prompt_text = ""
            for m in messages:
                content = m.get('content')
                if isinstance(content, list):
                    for item in content:
                        if item.get('type') == 'text':
                            prompt_text += item.get('text', '') + "\n"
                else:
                    prompt_text += str(content) + "\n"
            
            full_log = f"--- PROMPT ---\n{prompt_text}\n\n--- RESPONSE ---\n{res_content}"
            SaveTool.save_text(full_log, save_prompt_path)
            
        return res_content, usage_dict

    def _parse_json(self, content: str, fallback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        安全的 JSON 解析，支持 Markdown 代码块提取与保底逻辑
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except:
                    pass
            
            LogTool.error(f"JSON 解析失败，返回保底数据。原始内容前100字: {content[:100]}...")
            return fallback_data
