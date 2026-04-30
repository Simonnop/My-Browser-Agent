import os
import shutil
import time
import difflib
from playwright.sync_api import sync_playwright

from agent.config import (
    ENABLE_SCREENSHOT, RESET_PROFILE, USER_DATA_DIR, MAX_CYCLES, OUTPUT_DIR,
    LOOP_INTERVAL_SEC
)
from agent.dom_utils import clean_html
from agent.llm import call_llm, extract_json
from agent.actions import apply_actions
from agent.prompts import load_core_instructions
from agent.prompt import CyclePromptDynamic, build_cycle_user_prompt
from agent.rag import (
    format_html_rag_focus_prompt_block,
    normalize_rag_keywords_for_retrieval,
    retrieve_relevant_html_tree,
    save_html_rag_prompt_snapshot,
)
from tasks import load_task_instruction_sections
import argparse
from pathlib import Path

def main(task_name: str = "fill_resume"):
    if RESET_PROFILE and USER_DATA_DIR.exists():
        shutil.rmtree(USER_DATA_DIR)
        USER_DATA_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=False,
            args=["--mute-audio"]  # 添加这一行，开启全局静音
        )
        page = context.new_page()
        current_page = {"page": page}

        history: list[dict] = []
        known_pages: list = []
        need_screenshot = ENABLE_SCREENSHOT
        last_cleaned_html = ""

        def register_page(new_page) -> None:
            if new_page not in known_pages:
                known_pages.append(new_page)
                try:
                    new_page.on("popup", register_page)
                except Exception:
                    pass
                current_page["page"] = new_page

        for p_page in context.pages:
            register_page(p_page)
        context.on("page", register_page)

        cycle_count = 0
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        send_html_full = True
        add_content = ""

        while True:
            cycle_count += 1
            if cycle_count > MAX_CYCLES:
                print(f"\n[!] Reached maximum cycle limit ({MAX_CYCLES}). Exiting to prevent infinite loop.")
                break
                
            for p_page in context.pages:
                register_page(p_page)
            page = current_page["page"]
            pages = [p_page for p_page in known_pages if not p_page.is_closed()]
            tabs_info = []
            active_index = 0
            for i, p_page in enumerate(pages):
                if p_page == page:
                    active_index = i
                title = p_page.title() or "(untitled)"
                url = p_page.url
                tabs_info.append(f"[{i}] {title} - {url}")
            if not tabs_info:
                tabs_info.append(f"[0] {page.title() or '(untitled)'} - {page.url}")
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            screenshot_path = OUTPUT_DIR / f"page_{timestamp}.png"
            html_path = OUTPUT_DIR / f"page_{timestamp}.html"
            answer_path = OUTPUT_DIR / f"llm_answer_{timestamp}.txt"
            prompt_path = OUTPUT_DIR / f"llm_prompt_{timestamp}.txt"
            raw_path = OUTPUT_DIR / f"llm_raw_{timestamp}.txt"

            print(f"\n[{timestamp}] --- Starting cycle ---")
            cycle_start_time = time.time()

            state_start_time = time.time()
            if need_screenshot:
                page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"Captured screenshot in {time.time() - state_start_time:.2f}s")
            else:
                print("Skipped screenshot (need_screenshot=False)")
                
            html_start_time = time.time()
            raw_html = page.content()
            
            cleaned_html = clean_html(raw_html)
            
            # 上一轮专用于 RAG 的短检索词（如「姓名」）；可由 LLM 的 rag_keywords 与 task hint 归一得到
            prev = history[-1] if history else {}
            last_rag_query = normalize_rag_keywords_for_retrieval(
                prev.get("rag_keywords", ""),
                prev.get("current_focused_task", ""),
            ).strip()

            # 每轮循环开始前先确保输出目录存在
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            core_instructions = load_core_instructions()
            task_md, skills_section, attachment_section = load_task_instruction_sections(
                task_name, query=last_rag_query
            )
            
            # 与本轮 llm_prompt 同名的 HTML RAG 快照（仅 top 15 分块，见 rag_html_{ts}.json）
            rag_html_dump_path = OUTPUT_DIR / f"rag_html_{timestamp}.json"

            # 应用 RAG 过滤当前的 HTML 以保证焦点清晰并节约 token
            if last_rag_query:
                rag_html, rag_focus_items = retrieve_relevant_html_tree(
                    cleaned_html,
                    query=last_rag_query,
                    prompt_rag_dump_path=rag_html_dump_path,
                )
                html_rag_focus_block = format_html_rag_focus_prompt_block(
                    last_rag_query, rag_focus_items
                )
            else:
                save_html_rag_prompt_snapshot(
                    rag_html_dump_path,
                    "",
                    [],
                    status="skipped",
                    reason="no_rag_query",
                )
                rag_html = 'no rag_query'
                html_rag_focus_block = format_html_rag_focus_prompt_block(
                    "",
                    [],
                    skipped_reason="本轮无 rag_keywords / 检索词，未对页面做 HTML 向量 RAG。",
                )

            html_path.write_text(raw_html, encoding="utf-8")
            print(f"Processed HTML (from {len(raw_html)} to {len(rag_html)} chars after RAG) in {time.time() - html_start_time:.2f}s")

            if last_cleaned_html:
                diff_lines = difflib.unified_diff(
                    last_cleaned_html.splitlines(),
                    cleaned_html.splitlines(),
                    fromfile="previous.html",
                    tofile="current.html",
                    lineterm="",
                )
                html_diff = "\n".join(diff_lines)
                # diff 过大时省略：避免变更说明超过当前页面规模时冲爆上下文
                page_chars = len(cleaned_html)
                if page_chars > 0 and len(html_diff) > page_chars * 0.1:
                    html_diff = html_diff[:1000]
            else:
                html_diff = "(no previous html)"
            
            prompt_history = []
            for i, rec in enumerate(history):
                if i < len(history) - 3:
                    summary_actions = [{"type": a.get("type", "unknown")} for a in rec.get("actions", [])]
                    compressed_rec = {
                        "current_focused_task": rec.get("current_focused_task", ""),
                        "rag_keywords": rec.get("rag_keywords", ""),
                        "answer": rec.get("answer", ""),
                        "actions_summary": summary_actions
                    }
                    if "error" in rec:
                        compressed_rec["error"] = rec["error"]
                    prompt_history.append(compressed_rec)
                else:
                    prompt_history.append(rec)

            if send_html_full:
                html_full = cleaned_html
                send_html_full = True
                html_rag_focus_block = "no html_rag_focus_block"
                print("Sending full HTML to LLM")
            else:
                html_full = "no html_full"

            prompt = build_cycle_user_prompt(
                core_instructions=core_instructions,
                task_md=task_md,
                skills_rag_section=skills_section,
                attachment_rag_section=attachment_section,
                dynamic=CyclePromptDynamic(
                    url=page.url,
                    title=page.title() or "",
                    tab_lines=tabs_info,
                    active_tab_index=active_index,
                    prompt_history=prompt_history,
                    screenshot_path=screenshot_path,
                    html_file_path=html_path,
                    html_diff=html_diff,
                    html_rag_focus_block=html_rag_focus_block,
                    html_full=html_full,
                ),
                add_content = add_content,
            )

            add_content = ""

            last_cleaned_html = cleaned_html

            prompt_path.write_text(prompt, encoding="utf-8")

            print("Calling LLM... (This may take a few seconds)")
            llm_start_time = time.time()
            llm_text = call_llm(prompt, screenshot_path if need_screenshot else None)
            print(f"LLM replied in {time.time() - llm_start_time:.2f}s")

            need_screenshot = ENABLE_SCREENSHOT

            raw_path.write_text(llm_text, encoding="utf-8")
            response = extract_json(llm_text)

            answer = response.get("answer", "")
            current_focused_task = response.get("current_focused_task", "")
            _rk = response.get("rag_keywords", response.get("rag_query", ""))
            rag_keywords_raw = _rk.strip() if isinstance(_rk, str) else str(_rk or "").strip()
            rag_keywords = normalize_rag_keywords_for_retrieval(
                rag_keywords_raw,
                current_focused_task,
            ).strip()
            current_focused_html = response.get("current_focused_html", "")
            actions = response.get("actions", [])
            new_skill = response.get("new_skill", "")
            exiting = any(
                isinstance(a, dict) and str(a.get("type", "")).lower() == "exit"
                for a in (actions or [])
            )

            if new_skill and isinstance(new_skill, str) and new_skill.strip():
                if exiting:
                    try:
                        skills_path = Path("tasks") / task_name / "skills.md"
                        if skills_path.exists():
                            content = skills_path.read_text(encoding="utf-8").strip()
                            skills_path.write_text(content + f"\n- **{time.strftime('%m-%d')} Learn**: {new_skill.strip()}\n", encoding="utf-8")
                        else:
                            skills_path.write_text(f"### Task Skills:\n- **{time.strftime('%m-%d')} Learn**: {new_skill.strip()}\n", encoding="utf-8")
                        print(f"\n  [💡] Agent learned a new skill and appended to skills.md: {new_skill.strip()}")
                    except Exception as e:
                        print(f"\n  [!] Failed to save new skill: {e}")
                else:
                    print("\n  [i] new_skill 仅在当轮 actions 含 exit 时写入 skills.md，本回合已忽略。")

            for action in actions:
                if action.get("type") == "view_screenshot":
                    need_screenshot = True
                    print("  => LLM requested the screenshot for the next cycle.")

            answer_path.write_text(answer, encoding="utf-8")
            print(f"LLM Answer: {answer}")
            
            page, error_msg, successful_actions = apply_actions(page, actions)
            current_page["page"] = page
            
            cycle_record = {
                "current_focused_task": current_focused_task,
                "rag_keywords": rag_keywords,
                "current_focused_html": current_focused_html,
                "answer": answer,
                "actions": actions,
                "successful_actions": successful_actions,
            }
            if error_msg:
                cycle_record["error"] = error_msg
                print("Action Error:", error_msg)
                
            history.append(cycle_record)

            cycle_elapsed = time.time() - cycle_start_time
            print(f"----------------------------------")
            print(f"Cycle {cycle_count}/{MAX_CYCLES} completed in {cycle_elapsed:.2f}s")
            print(f"Waiting {LOOP_INTERVAL_SEC}s for next cycle...\n")

            if len(history) >= 2:
                if (history[-1]["answer"] == history[-2]["answer"] or history[-1]["actions"] == history[-2]["actions"] or history[-1]["current_focused_task"] == history[-2]["current_focused_task"]):
                    print(f"[!] Warning: The LLM output the exact same answer for 2 consecutive cycles. Injecting system intervention warning.")
                    send_html_full = True
                    # 告诉模型进入了死循环, 让他重新思考
                    add_content = "你进入死循环了, 请观察 full_html, 并给出新的答案"

            try:
                page.wait_for_timeout(LOOP_INTERVAL_SEC * 1000)
            except Exception:
                time.sleep(LOOP_INTERVAL_SEC)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Browser Agent")
    parser.add_argument("task", nargs="?", default="fill_resume", help="Name of the task folder to run")
    args = parser.parse_args()
    main(args.task)