"""
向量索引层 — numpy 内存矩阵 + 批量 cosine 检索
替代原有的 json.loads + Python for-loop 暴力扫描
"""
import json
import threading
import numpy as np
from pathlib import Path

from .config import STORAGE_CFG
from .storage import load_all_chunks


class VectorStore:
    def __init__(self):
        self._ids: np.ndarray | None = None
        self._embeddings: np.ndarray | None = None
        self._texts: list[str] = []
        self._sources: list[str] = []
        self._index_path = STORAGE_CFG.data_dir / "vectors.npy"
        self._ids_path = STORAGE_CFG.data_dir / "vector_ids.npy"
        self._lock = threading.Lock()

    def build(self):
        rows = load_all_chunks()
        if not rows:
            with self._lock:
                self._ids = None
                self._embeddings = None
                self._texts = []
                self._sources = []
            return

        ids = []
        embs = []
        texts = []
        sources = []
        for row in rows:
            chunk_id, source, text, emb_data = row
            emb = _deserialize(emb_data)
            if emb is None:
                continue
            ids.append(chunk_id)
            embs.append(emb)
            texts.append(text)
            sources.append(source)

        if not embs:
            with self._lock:
                self._ids = None
                self._embeddings = None
                self._texts = []
                self._sources = []
            return

        new_ids = np.array(ids, dtype=np.int64)
        embeddings = np.array(embs, dtype=np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        new_embeddings = embeddings / norms
        with self._lock:
            self._ids = new_ids
            self._embeddings = new_embeddings
            self._texts = texts
            self._sources = sources

    def search(self, query_emb, top_k: int = 10,
               min_similarity: float = 0.0) -> list[tuple[float, int, str, str]]:
        """返回 [(score, chunk_id, text, source), ...] 按分数降序（COW 快照模式）"""
        with self._lock:
            ids = self._ids
            embeddings = self._embeddings
            texts = self._texts
            sources = self._sources

        if embeddings is None or ids is None:
            return []

        q = np.asarray(query_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm

        scores = np.dot(embeddings, q)
        if min_similarity > 0:
            mask = scores >= min_similarity
            indices = np.where(mask)[0]
            top_indices = indices[np.argsort(scores[indices])[::-1][:top_k]]
        else:
            top_indices = np.argpartition(scores, -min(top_k, len(scores)))[-top_k:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [(float(scores[i]), int(ids[i]), texts[i], sources[i])
                for i in top_indices]

    def add(self, chunk_id: int, embedding: list[float], text: str = "", source: str = ""):
        emb = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        with self._lock:
            if self._embeddings is None:
                self._ids = np.array([chunk_id], dtype=np.int64)
                self._embeddings = emb.reshape(1, -1)
                self._texts = [text]
                self._sources = [source]
            else:
                self._ids = np.append(self._ids, chunk_id)
                self._embeddings = np.vstack([self._embeddings, emb])
                self._texts.append(text)
                self._sources.append(source)

    def remove(self, chunk_id: int):
        with self._lock:
            if self._ids is None:
                return
            mask = self._ids != chunk_id
            if not mask.all():
                self._ids = self._ids[mask]
                self._embeddings = self._embeddings[mask]
                self._texts = [t for i, t in enumerate(self._texts) if mask[i]]
                self._sources = [s for i, s in enumerate(self._sources) if mask[i]]

    def remove_many(self, chunk_ids: list[int]):
        with self._lock:
            if self._ids is None:
                return
            ids_set = set(chunk_ids)
            mask = np.array([i not in ids_set for i in self._ids], dtype=bool)
            if not mask.all():
                self._ids = self._ids[mask]
                self._embeddings = self._embeddings[mask]
                self._texts = [t for i, t in enumerate(self._texts) if mask[i]]
                self._sources = [s for i, s in enumerate(self._sources) if mask[i]]

    def save(self):
        with self._lock:
            if self._embeddings is None:
                return
            np.save(str(self._index_path), self._embeddings)
            np.save(str(self._ids_path), self._ids)

    def load_disk(self) -> bool:
        with self._lock:
            if self._index_path.exists() and self._ids_path.exists():
                self._embeddings = np.load(str(self._index_path))
                self._ids = np.load(str(self._ids_path))
                return True
            return False

    def clear(self):
        with self._lock:
            self._ids = None
            self._embeddings = None
            self._texts = []
            self._sources = []

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._ids) if self._ids is not None else 0


def _deserialize(emb_data) -> np.ndarray | None:
    """解析嵌入 blob：新格式是 binary float32，旧格式是 JSON 字符串"""
    if isinstance(emb_data, bytes):
        if len(emb_data) > 0 and emb_data[0:1] == b'[':
            # 旧格式：JSON 字符串
            try:
                return np.array(json.loads(emb_data.decode("utf-8")), dtype=np.float32)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        # 新格式：float32 binary
        if len(emb_data) % 4 == 0:
            return np.frombuffer(emb_data, dtype=np.float32)
    elif isinstance(emb_data, str):
        try:
            return np.array(json.loads(emb_data), dtype=np.float32)
        except json.JSONDecodeError:
            pass
    return None


def serialize_embedding(embedding: list[float]) -> bytes:
    return np.array(embedding, dtype=np.float32).tobytes()


_vector_store: VectorStore | None = None
_vs_lock = threading.Lock()


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        with _vs_lock:
            if _vector_store is None:
                vs = VectorStore()
                if not vs.load_disk():
                    vs.build()
                    vs.save()
                _vector_store = vs
    return _vector_store


def rebuild_vector_store():
    global _vector_store
    with _vs_lock:
        if _vector_store is None:
            _vector_store = VectorStore()
        _vector_store.build()
        _vector_store.save()


def clear_vector_store():
    global _vector_store
    with _vs_lock:
        _vector_store = None
