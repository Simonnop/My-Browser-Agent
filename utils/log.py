import os
import json
import base64
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage

def save_observe_images(run_dir, step, som_b64, scroll_b64, focus_b64, mapping_str):
    round_dir = os.path.join(run_dir, f"round_{step}")
    os.makedirs(round_dir, exist_ok=True)
    
    if som_b64:
        with open(os.path.join(round_dir, "som_image.png"), "wb") as f:
            f.write(base64.b64decode(som_b64))
    if scroll_b64:
        with open(os.path.join(round_dir, "scroll_image.png"), "wb") as f:
            f.write(base64.b64decode(scroll_b64))
    if focus_b64:
        with open(os.path.join(round_dir, "focus_image.png"), "wb") as f:
            f.write(base64.b64decode(focus_b64))
            
    with open(os.path.join(round_dir, "som_mapping.json"), "w", encoding="utf-8") as f:
        f.write(mapping_str)

def save_think_log(run_dir, step, prompt, response_content):
    round_dir = os.path.join(run_dir, f"round_{step}")
    os.makedirs(round_dir, exist_ok=True)
    
    prompt_log = []
    for msg in prompt:
        if isinstance(msg, SystemMessage):
            prompt_log.append({"role": "system", "content": msg.content})
        elif isinstance(msg, AIMessage):
            prompt_log.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            clean_content = []
            if isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        clean_content.append({"type": "image_url", "image_url": "data:image/png;base64,<BASE64_IMAGE_OMITTED_IN_LOG>"})
                    else:
                        clean_content.append(item)
                prompt_log.append({"role": "human", "content": clean_content})
            else:
                prompt_log.append({"role": "human", "content": msg.content})
                
    with open(os.path.join(round_dir, "prompt.json"), "w", encoding="utf-8") as f:
        json.dump(prompt_log, f, ensure_ascii=False, indent=2)

    with open(os.path.join(round_dir, "response.txt"), "w", encoding="utf-8") as f:
        f.write(response_content)
