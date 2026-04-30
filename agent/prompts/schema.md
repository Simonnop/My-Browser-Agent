```json
{
  "current_focused_task": "A brief description of exactly what part of the task you are focusing on right now (e.g., 'filling out the email field', 'submitting the second step of the form').",
  "rag_keywords": "Minimal tokens for the NEXT cycle HTML/skills RAG (e.g. one field name in task language: 姓名).",
  "current_focused_html": "A small snippet of the relevant HTML code that pertains to the current_focused_task, proving you have located the right element.",
  "answer": "short reasoning and current status",
  "new_skill": "(optional) Only when ending the run with {\"type\":\"exit\"}: summarize reusable patterns/workarounds from the whole task to append to skills.md. Leave empty in all other rounds.",
  "actions": [
    {"type": "click", "selectors": ["CSS obj1", "CSS fallback2"], "clickCount": 1},
    {"type": "fill", "selectors": ["CSS selector", "CSS fallback"], "text": "..."},
    {"type": "clear", "selectors": ["CSS selector", "CSS fallback"]},
    {"type": "select", "selector": "CSS selector of <select>", "option": "label or value of the option"},
    {"type": "press", "selector": "CSS selector", "key": "Enter"},
    {"type": "scroll", "x": 0, "y": 800},
    {"type": "wait", "ms": 1000},
    {"type": "goto", "url": "https://..."},
    {"type": "switch_tab", "index": 0},
    {"type": "exit"}
  ]
}
```