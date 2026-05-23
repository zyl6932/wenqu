"""
向量嵌入层 — Ollama / 未来可切换为 OpenAI / 本地模型
"""
import hashlib
import json
import threading
import urllib.request
from collections import OrderedDict
from .config import EMBED_CFG

_EMBED_CACHE_MAX = 50000
_embed_cache: OrderedDict[str, list[float]] = OrderedDict()
_cache_lock = threading.Lock()
_embed_semaphore = threading.BoundedSemaphore(5)


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
        batch_idx = 0
        try:
            for batch_idx in range(0, len(uncached_texts), bs):
                batch = uncached_texts[batch_idx:batch_idx + bs]
                data = json.dumps({"model": EMBED_CFG.model, "input": batch}).encode()
                req = urllib.request.Request(f"{EMBED_CFG.ollama_url}/api/embed", data=data)
                req.add_header("Content-Type", "application/json")
                _embed_semaphore.acquire()
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        result = json.loads(resp.read())
                finally:
                    _embed_semaphore.release()
                batch_embs = result.get("embeddings", [])
                if len(batch_embs) != len(batch):
                    raise RuntimeError(f"嵌入返回数量不匹配: 期望 {len(batch)}, 实际 {len(batch_embs)}")
                new_embs.extend(batch_embs)
        except Exception as e:
            raise RuntimeError(f"向量化失败 (batch {batch_idx // bs}): {e}") from e
        with _cache_lock:
            for idx, ut, emb in zip(uncached_idx, uncached_texts, new_embs):
                results[idx] = emb
                _embed_cache[hashlib.sha256(ut.encode()).hexdigest()] = emb
            while len(_embed_cache) > _EMBED_CACHE_MAX:
                _embed_cache.popitem(last=False)

    return results  # type: ignore


def embed_single(text: str) -> list[float]:
    return embed([text])[0]


def cosine(a: list[float], b: list[float]) -> float:
    import numpy as np
    va = np.asarray(a, dtype=np.float32)
    vb = np.asarray(b, dtype=np.float32)
    dot = np.dot(va, vb)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    return float(dot / (na * nb)) if na and nb else 0.0


def clear_cache():
    with _cache_lock:
        _embed_cache.clear()
