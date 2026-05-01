import os
import json
import base64
from openai import OpenAI
from dotenv import load_dotenv
from .prompt import VISUAL_PERCEPTION_PROMPT, MAIN_AGENT_PROMPT, MEMORY_COMPRESSION_PROMPT

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

    def get_token_usage(self):
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens
        }

    def ask_visual_subagent(self, screenshot_path: str, task_description: str, tabs_display: str, save_prompt_path: str = None) -> tuple[dict, dict]:
        """
        封装视觉感知请求
        返回: (感知结果dict, 本次消耗usage_dict)
        """
        with open(screenshot_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        prompt = VISUAL_PERCEPTION_PROMPT.format(
            task_description=task_description,
            tabs_display=tabs_display
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

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": False, "thinking": {"type": "disabled"}},
        )
        
        res_content = response.choices[0].message.content

        if save_prompt_path:
            from tools.save import SaveTool
            full_log = f"--- PROMPT ---\n{prompt}\n\n--- RESPONSE ---\n{res_content}"
            SaveTool.save_text(full_log, save_prompt_path)

        usage = response.usage
        self.total_input_tokens += usage.prompt_tokens
        self.total_output_tokens += usage.completion_tokens
        
        usage_dict = {
            "input": usage.prompt_tokens,
            "output": usage.completion_tokens
        }
        
        return json.loads(response.choices[0].message.content), usage_dict

    def ask_main_agent(self, task: str, step: int, max_steps: int, perception: dict, tabs_display: str, local_html: str, history: str, save_prompt_path: str = None) -> tuple[str, dict]:
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
            is_completed=perception.get('is_completed', False),
            tabs_display=tabs_display,
            local_html=local_html
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"enable_thinking": False, "thinking": {"type": "disabled"}},
        )
        
        res_content = response.choices[0].message.content

        if save_prompt_path:
            from tools.save import SaveTool
            full_log = f"--- PROMPT ---\n{prompt}\n\n--- RESPONSE ---\n{res_content}"
            SaveTool.save_text(full_log, save_prompt_path)

        usage = response.usage
        self.total_input_tokens += usage.prompt_tokens
        self.total_output_tokens += usage.completion_tokens
        
        usage_dict = {
            "input": usage.prompt_tokens,
            "output": usage.completion_tokens
        }
        
        return response.choices[0].message.content, usage_dict

    def ask_for_summary(self, history_to_compress: str, existing_summary: str) -> tuple[str, dict]:
        """
        请求 LLM 压缩记忆
        返回: (总结str, 本次消耗usage_dict)
        """
        prompt = MEMORY_COMPRESSION_PROMPT.format(
            history_to_compress=history_to_compress,
            existing_summary=existing_summary
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"enable_thinking": False, "thinking": {"type": "disabled"}},
        )

        usage = response.usage
        self.total_input_tokens += usage.prompt_tokens
        self.total_output_tokens += usage.completion_tokens

        usage_dict = {
            "input": usage.prompt_tokens,
            "output": usage.completion_tokens
        }

        return response.choices[0].message.content.strip(), usage_dict
