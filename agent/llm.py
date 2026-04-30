import base64
import json
from pathlib import Path
from openai import APIStatusError, OpenAI

from agent.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


def call_llm(prompt: str, image_path: Path | None = None) -> str:
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not set")

    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )
    
    content_list = [{"type": "text", "text": prompt}]
    
    if image_path and image_path.exists():
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        content_list.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
        })

    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            extra_body={"enable_thinking": False, "thinking": {"type": "disabled"}},
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON."},
                {
                    "role": "user",
                    "content": content_list,
                },
            ],
            temperature=0.2,
        )
    except APIStatusError as exc:
        if exc.status_code == 402:
            raise RuntimeError(
                "LLM 返回 402：账户余额不足。请在当前 LLM_BASE_URL 对应服务商充值，"
                "或设置环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 指向可用线路。"
            ) from exc
        raise RuntimeError(
            f"LLM 请求失败（HTTP {exc.status_code}）。详情: {exc}"
        ) from exc
    return completion.choices[0].message.content

def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])
