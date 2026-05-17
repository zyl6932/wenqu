"""
数据存储层 — SQLite + JSON向量
模仿 RAGFlow internal/ 的分层：DAO → 业务逻辑完全隔离
"""
import json
import sqlite3
from pathlib import Path
from .config import STORAGE_CFG


def get_db() -> sqlite3.Connection:
    """获取数据库连接 — 唯一的 DB 入口"""
    STORAGE_CFG.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(STORAGE_CFG.data_dir / "vectors.db"))
    conn.execute("""CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY,
        source TEXT,
        text TEXT,
        embedding BLOB
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS sources (
        path TEXT PRIMARY KEY,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    return conn


# ── 块 CRUD（与上层检索逻辑解耦）─────────────────────

def count_chunks(source: str | None = None) -> int:
    db = get_db()
    if source:
        return db.execute("SELECT COUNT(*) FROM chunks WHERE source = ?", (source,)).fetchone()[0]
    return db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]


def count_sources() -> int:
    return get_db().execute("SELECT COUNT(*) FROM sources").fetchone()[0]


def load_all_chunks(source: str | None = None) -> list[tuple[int, str, str, str]]:
    """返回 [(id, source, text, emb_json_str)]"""
    db = get_db()
    if source:
        return db.execute("SELECT id, source, text, embedding FROM chunks WHERE source = ? ORDER BY id", (source,)).fetchall()
    return db.execute("SELECT id, source, text, embedding FROM chunks ORDER BY id").fetchall()


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


def insert_chunk(source: str, text: str, embedding: list[float]) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO chunks (source, text, embedding) VALUES (?, ?, ?)",
        (source, text, json.dumps(embedding)),
    )
    db.commit()
    return cur.lastrowid


def update_chunk_text(chunk_id: int, text: str, embedding: list[float]):
    db = get_db()
    db.execute(
        "UPDATE chunks SET text = ?, embedding = ? WHERE id = ?",
        (text, json.dumps(embedding), chunk_id),
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


def insert_source(path: str):
    get_db().execute("INSERT INTO sources (path) VALUES (?)", (path,))
    get_db().commit()


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
    get_db().execute(
        "INSERT INTO feedback (question, chunk_prefix, helpful) VALUES (?, ?, ?)",
        (question, chunk_prefix, helpful),
    )
    get_db().commit()


def get_feedback_boost(chunk_text: str) -> float:
    try:
        prefix = chunk_text[:80]
        rows = get_db().execute("SELECT helpful FROM feedback WHERE chunk_prefix = ?", (prefix,)).fetchall()
        return sum(r[0] for r in rows) * 0.05 if rows else 0.0
    except Exception:
        return 0.0
