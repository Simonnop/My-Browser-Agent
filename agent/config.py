import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # 加载 .env 文件（如果存在），优先级低于系统环境变量
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

USER_DATA_DIR = BASE_DIR / "chrome_profile"
USER_DATA_DIR.mkdir(exist_ok=True)

RESET_PROFILE = os.getenv("RESET_PROFILE", "0") == "1"
ENABLE_SCREENSHOT = os.getenv("ENABLE_SCREENSHOT", "1") == "1"
LOOP_INTERVAL_SEC = int(os.getenv("LOOP_INTERVAL_SEC", "1"))
MAX_CYCLES = int(os.getenv("MAX_CYCLES", "200"))

INSTRUCTIONS_PATH = Path(os.getenv("INSTRUCTIONS_PATH", str(BASE_DIR / "instructions.txt")))

# LLM configuration (all via environment variables, no defaults)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
# HTML RAG 遍历/剪枝深度；过小则深层叶子不会参与打分，rag_scores 里 chunk 会很少
HTML_RAG_MAX_DEPTH = int(os.getenv("HTML_RAG_MAX_DEPTH", "40"))
# HTML RAG：在 clean_html 中每块向匹配位置两侧各取 n 字符；提示词仅纳入得分最高的 k 块
HTML_RAG_WINDOW_N = int(os.getenv("HTML_RAG_WINDOW_N", "400"))
HTML_RAG_BLOCKS_K = int(os.getenv("HTML_RAG_BLOCKS_K", "5"))
PLAYWRIGHT_TIMEOUT_MS = 500
