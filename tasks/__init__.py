from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parent


def load_task_instruction_sections(task_name: str, query: str = "") -> tuple[str, str, str]:
    """
    (task.md 正文, skills.md 全文, attachment.md 全文)。
    query 参数保留以兼容旧调用，已不再用于 RAG 裁剪。
    顺序供上游按「前缀缓存」拼装：task 在前，skills / attachment 随后。
    """
    task_dir = TASKS_DIR / task_name
    if not task_dir.exists():
        print(f"Task directory {task_dir} does not exist.")
        return "", "", ""

    task_body = ""
    task_path = task_dir / "task.md"
    if task_path.exists():
        task_body = task_path.read_text(encoding="utf-8").strip()

    skills_section = ""
    skills_path = task_dir / "skills.md"
    if skills_path.exists():
        skills_section = skills_path.read_text(encoding="utf-8").strip()

    attachment_section = ""
    attach_path = task_dir / "attachment.md"
    if attach_path.exists():
        attachment_section = attach_path.read_text(encoding="utf-8").strip()

    return task_body, skills_section, attachment_section


def load_task_instructions(task_name: str, query: str = "") -> str:
    """读取 task 下 task.md / skills.md / attachment.md 全文（不做 RAG 裁剪）。"""
    task_body, skills_section, attachment_section = load_task_instruction_sections(task_name, query)
    return "\n\n".join(x for x in (task_body, skills_section, attachment_section) if x)
