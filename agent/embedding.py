import math
from typing import Dict, List, Optional

from agent.config import EMBEDDING_MODEL

try:
    from fastembed import TextEmbedding
except Exception:  # pragma: no cover - optional dependency
    TextEmbedding = None

MAX_EMBED_TEXTS = 200
EMBED_TEXT_CHARS = 300


_EMBEDDER: Optional["TextEmbedding"] = None


def get_embedding_client() -> "TextEmbedding":
    global _EMBEDDER
    if TextEmbedding is None:
        raise RuntimeError("fastembed is not installed. Run: pip install fastembed")
    if _EMBEDDER is None:
        _EMBEDDER = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _EMBEDDER


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    # 避免 numpy float32 等与 JSON 不兼容的类型
    return float(dot / (math.sqrt(norm_a) * math.sqrt(norm_b)))


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    try:
        embedder = get_embedding_client()
        vectors = embedder.embed(texts)
        return [list(vector) for vector in vectors]
    except Exception as exc:
        print(f"Embedding request failed: {exc}")
        return []


def build_embedding_cache(texts: List[str]) -> Dict[str, List[float]]:
    if not texts:
        return {}
    unique_texts = []
    seen = set()
    for text in texts:
        if text in seen:
            continue
        seen.add(text)
        unique_texts.append(text)
    embeddings = embed_texts(unique_texts)
    return dict(zip(unique_texts, embeddings))


def clip_text(text: str) -> str:
    return text[:EMBED_TEXT_CHARS]
