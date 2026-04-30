import os
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent

def load_core_instructions() -> str:
    """组合总的核心浏览器操作规范和 schema"""
    try:
        system = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8")
        schema = (PROMPTS_DIR / "schema.md").read_text(encoding="utf-8")
        rules = (PROMPTS_DIR / "rules.md").read_text(encoding="utf-8")
        
        return f"{system}\n{schema}\n\n{rules}"
    except Exception as e:
        print(f"Error loading core prompt parts: {e}")
        return ""
