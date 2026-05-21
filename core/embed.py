"""
向量嵌入层 — Ollama / 未来可切换为 OpenAI / 本地模型
"""
import hashlib
import json
import threading
import urllib.request
from .config import EMBED_CFG

_embed_cache: dict[str, list[float]] = {}
_cache_lock = threading.Lock()


def embed(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    """批量向量化，线程安全的带内存缓存"""
    bs = batch_size or EMBED_CFG.batch_size
    results: list[list[float] | None] = [None] * len(texts)
    uncached_idx: list[int] = []
    uncached_texts: list[str] = []

    with _cache_lock:
        for i, t in enumerate(texts):
            key = hashlib.sha256(t.encode()).hexdigest()
            if key in _embed_cache:
                results[i] = _embed_cache[key]
            else:
                uncached_idx.append(i)
                uncached_texts.append(t)

    if uncached_texts:
        new_embs = []
        for j in range(0, len(uncached_texts), bs):
            batch = uncached_texts[j:j + bs]
            data = json.dumps({"model": EMBED_CFG.model, "input": batch}).encode()
            req = urllib.request.Request(f"{EMBED_CFG.ollama_url}/api/embed", data=data)
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
            new_embs.extend(result["embeddings"])
        with _cache_lock:
            for idx, emb in zip(uncached_idx, new_embs):
                results[idx] = emb
                ut = uncached_texts[uncached_idx.index(idx)]
                _embed_cache[hashlib.sha256(ut.encode()).hexdigest()] = emb

    return results  # type: ignore


def embed_single(text: str) -> list[float]:
    return embed([text])[0]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def clear_cache():
    _embed_cache.clear()
