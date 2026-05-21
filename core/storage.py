"""
数据存储层 — SQLite + JSON向量（WAL 模式，线程安全）
"""
import json
import sqlite3
import threading
from pathlib import Path
import numpy as np
from .config import STORAGE_CFG

_pool_lock = threading.Lock()
_pool: dict[int, sqlite3.Connection] = {}


def _init_conn(conn: sqlite3.Connection):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("""CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY,
        source TEXT,
        text TEXT,
        embedding BLOB,
        level INTEGER DEFAULT 0,
        parent_id INTEGER DEFAULT NULL
    )""")
    # 兼容旧表：如果缺少新列则添加
    for col, typ in [("level", "INTEGER DEFAULT 0"), ("parent_id", "INTEGER DEFAULT NULL")]:
        try: conn.execute(f"ALTER TABLE chunks ADD COLUMN {col} {typ}")
        except: pass
    for col, typ in [("file_mtime", "REAL DEFAULT 0")]:
        try: conn.execute(f"ALTER TABLE sources ADD COLUMN {col} {typ}")
        except: pass
    conn.execute("""CREATE TABLE IF NOT EXISTS sources (
        path TEXT PRIMARY KEY,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_mtime REAL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY,
        question TEXT,
        chunk_prefix TEXT,
        helpful INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source)")
    conn.commit()


def get_db() -> sqlite3.Connection:
    """线程安全的数据库连接（WAL 模式，连接复用）"""
    tid = threading.get_ident()
    with _pool_lock:
        conn = _pool.get(tid)
        if conn is None:
            STORAGE_CFG.data_dir.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(STORAGE_CFG.data_dir / "vectors.db"), check_same_thread=False)
            _init_conn(conn)
            _pool[tid] = conn
    return conn


# ── 块 CRUD（与上层检索逻辑解耦）─────────────────────

def count_chunks(source: str | None = None) -> int:
    db = get_db()
    if source:
        return db.execute("SELECT COUNT(*) FROM chunks WHERE source = ?", (source,)).fetchone()[0]
    return db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]


def count_sources() -> int:
    return get_db().execute("SELECT COUNT(*) FROM sources").fetchone()[0]


def load_all_chunks(source: str | None = None, limit: int | None = None, offset: int = 0) -> list[tuple[int, str, str, str]]:
    """返回 [(id, source, text, emb_json_str)]。limit=None 表示全部。"""
    db = get_db()
    if source:
        return db.execute(
            "SELECT id, source, text, embedding FROM chunks WHERE source = ? ORDER BY id LIMIT ? OFFSET ?",
            (source, limit or -1, offset),
        ).fetchall()
    return db.execute(
        "SELECT id, source, text, embedding FROM chunks ORDER BY id LIMIT ? OFFSET ?",
        (limit or -1, offset),
    ).fetchall()


def load_chunks_for_sources(sources: list[str]) -> list[tuple[int, str, str, str]]:
    """只加载指定来源的块"""
    if not sources:
        return []
    db = get_db()
    placeholders = ",".join("?" * len(sources))
    return db.execute(
        f"SELECT id, source, text, embedding FROM chunks WHERE source IN ({placeholders}) ORDER BY id",
        sources,
    ).fetchall()


def load_chunks_except(sources: list[str]) -> list[tuple[int, str, str, str]]:
    """加载非指定来源的块"""
    db = get_db()
    if not sources:
        return db.execute("SELECT id, source, text, embedding FROM chunks ORDER BY id").fetchall()
    placeholders = ",".join("?" * len(sources))
    return db.execute(
        f"SELECT id, source, text, embedding FROM chunks WHERE source NOT IN ({placeholders}) ORDER BY id",
        sources,
    ).fetchall()


def insert_chunk(source: str, text: str, embedding: list[float], level: int = 0, parent_id: int | None = None) -> int:
    db = get_db()
    emb_blob = np.array(embedding, dtype=np.float32).tobytes()
    cur = db.execute(
        "INSERT INTO chunks (source, text, embedding, level, parent_id) VALUES (?, ?, ?, ?, ?)",
        (source, text, emb_blob, level, parent_id),
    )
    db.commit()
    return cur.lastrowid


def get_parent_chunk(chunk_id: int) -> tuple | None:
    """返回父块 (id, source, text) 或 None"""
    db = get_db()
    child = db.execute("SELECT parent_id FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
    if not child or not child[0]:
        return None
    return db.execute("SELECT id, source, text FROM chunks WHERE id = ?", (child[0],)).fetchone()


def get_child_chunks(parent_id: int) -> list[tuple[int, str, str]]:
    """返回所有子块"""
    return get_db().execute(
        "SELECT id, source, text FROM chunks WHERE parent_id = ? ORDER BY id", (parent_id,)
    ).fetchall()


def update_chunk_text(chunk_id: int, text: str, embedding: list[float]):
    db = get_db()
    emb_blob = np.array(embedding, dtype=np.float32).tobytes()
    db.execute(
        "UPDATE chunks SET text = ?, embedding = ? WHERE id = ?",
        (text, emb_blob, chunk_id),
    )
    db.commit()


def delete_chunk_by_id(chunk_id: int):
    db = get_db()
    db.execute("DELETE FROM chunks WHERE id = ?", (chunk_id,))
    db.commit()


def delete_chunks_by_ids(chunk_ids: list[int]):
    if not chunk_ids:
        return
    db = get_db()
    db.executemany("DELETE FROM chunks WHERE id = ?", [(cid,) for cid in chunk_ids])
    db.commit()


def get_chunk_by_id(chunk_id: int) -> tuple | None:
    return get_db().execute("SELECT id, source, text, embedding FROM chunks WHERE id = ?", (chunk_id,)).fetchone()


def get_adjacent_chunks(chunk_id: int, source: str, expand: int) -> list[str]:
    """获取某块的前后相邻块"""
    db = get_db()
    texts = []
    for adj_id in range(chunk_id - expand, chunk_id + expand + 1):
        row = db.execute("SELECT text FROM chunks WHERE id = ? AND source = ?", (adj_id, source)).fetchone()
        if row:
            texts.append(row[0])
    return texts


# ── 来源管理 ──────────────────────────────────────

def source_exists(path: str) -> bool:
    return get_db().execute("SELECT 1 FROM sources WHERE path = ?", (path,)).fetchone() is not None


def source_needs_update(path: str) -> bool:
    """检查文件的 mtime 是否已变更（需要重新索引）"""
    import os
    fp = Path(path)
    if not fp.exists():
        return False
    current_mtime = os.path.getmtime(str(fp))
    row = get_db().execute("SELECT file_mtime FROM sources WHERE path = ?", (path,)).fetchone()
    if not row:
        return True
    return abs(row[0] - current_mtime) > 1.0  # 1 秒容忍度


def insert_source(path: str, mtime: float | None = None):
    import os
    if mtime is None:
        fp = Path(path)
        if fp.exists():
            mtime = os.path.getmtime(str(fp))
        else:
            mtime = 0.0
    db = get_db()
    db.execute("INSERT INTO sources (path, file_mtime) VALUES (?, ?)", (path, mtime))
    db.commit()


def delete_source(path: str):
    db = get_db()
    db.execute("DELETE FROM chunks WHERE source = ?", (path,))
    db.execute("DELETE FROM sources WHERE path = ?", (path,))
    db.commit()


def list_sources() -> list[tuple[str, str]]:
    """返回 [(path, added_at)]"""
    return get_db().execute("SELECT path, added_at FROM sources ORDER BY added_at DESC").fetchall()


def overview_sources() -> list[tuple[str, str]]:
    """返回有【文档章节概览】块的来源"""
    return get_db().execute(
        "SELECT source, text FROM chunks WHERE text LIKE '【文档章节概览】%'"
    ).fetchall()


# ── 反馈 ──────────────────────────────────────────

def save_feedback(question: str, chunk_prefix: str, helpful: int):
    db = get_db()
    db.execute(
        "INSERT INTO feedback (question, chunk_prefix, helpful) VALUES (?, ?, ?)",
        (question, chunk_prefix, helpful),
    )
    db.commit()


def get_feedback_boost(chunk_text: str) -> float:
    try:
        prefix = chunk_text[:80]
        rows = get_db().execute("SELECT helpful FROM feedback WHERE chunk_prefix = ?", (prefix,)).fetchall()
        return sum(r[0] for r in rows) * 0.05 if rows else 0.0
    except Exception:
        return 0.0
