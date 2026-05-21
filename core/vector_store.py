"""
向量索引层 — numpy 内存矩阵 + 批量 cosine 检索
替代原有的 json.loads + Python for-loop 暴力扫描
"""
import json
import numpy as np
from pathlib import Path

from .config import STORAGE_CFG
from .storage import load_all_chunks


class VectorStore:
    def __init__(self):
        self._ids: np.ndarray | None = None          # (N,) int64
        self._embeddings: np.ndarray | None = None    # (N, D) float32, L2-normalized
        self._index_path = STORAGE_CFG.data_dir / "vectors.npy"
        self._ids_path = STORAGE_CFG.data_dir / "vector_ids.npy"

    def build(self):
        rows = load_all_chunks()
        if not rows:
            self._ids = None
            self._embeddings = None
            return

        ids = []
        embs = []
        for row in rows:
            chunk_id, source, text, emb_data = row
            emb = _deserialize(emb_data)
            if emb is None:
                continue
            ids.append(chunk_id)
            embs.append(emb)

        if not embs:
            self._ids = None
            self._embeddings = None
            return

        self._ids = np.array(ids, dtype=np.int64)
        embeddings = np.array(embs, dtype=np.float32)
        # L2 归一化，后续用 dot product 代替 cosine
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        self._embeddings = embeddings / norms

    def search(self, query_emb: np.ndarray, top_k: int = 10,
               min_similarity: float = 0.0) -> list[tuple[float, int]]:
        """返回 [(score, chunk_id), ...] 按分数降序"""
        if self._embeddings is None or self._ids is None:
            return []

        q = np.asarray(query_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm

        scores = np.dot(self._embeddings, q)
        if min_similarity > 0:
            mask = scores >= min_similarity
            indices = np.where(mask)[0]
            top_indices = indices[np.argsort(scores[indices])[::-1][:top_k]]
        else:
            top_indices = np.argpartition(scores, -min(top_k, len(scores)))[-top_k:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        return [(float(scores[i]), int(self._ids[i])) for i in top_indices]

    def add(self, chunk_id: int, embedding: list[float]):
        emb = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        if self._embeddings is None:
            self._ids = np.array([chunk_id], dtype=np.int64)
            self._embeddings = emb.reshape(1, -1)
        else:
            self._ids = np.append(self._ids, chunk_id)
            self._embeddings = np.vstack([self._embeddings, emb])

    def remove(self, chunk_id: int):
        """移除单个 ID（标记式，下次 rebuild 生效）"""
        if self._ids is None:
            return
        mask = self._ids != chunk_id
        if not mask.all():
            self._ids = self._ids[mask]
            self._embeddings = self._embeddings[mask]

    def remove_many(self, chunk_ids: list[int]):
        if self._ids is None:
            return
        ids_set = set(chunk_ids)
        mask = np.array([i not in ids_set for i in self._ids], dtype=bool)
        if not mask.all():
            self._ids = self._ids[mask]
            self._embeddings = self._embeddings[mask]

    def save(self):
        if self._embeddings is None:
            return
        np.save(str(self._index_path), self._embeddings)
        np.save(str(self._ids_path), self._ids)

    def load_disk(self) -> bool:
        if self._index_path.exists() and self._ids_path.exists():
            self._embeddings = np.load(str(self._index_path))
            self._ids = np.load(str(self._ids_path))
            return True
        return False

    def clear(self):
        self._ids = None
        self._embeddings = None

    @property
    def size(self) -> int:
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


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        if not _vector_store.load_disk():
            _vector_store.build()
            _vector_store.save()
    return _vector_store


def rebuild_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    _vector_store.build()
    _vector_store.save()


def clear_vector_store():
    global _vector_store
    _vector_store = None
