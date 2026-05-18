"""
检索层 — BM25 + 语义向量 + RRF 融合 + 重排序 + 查询改写
模仿 RAGFlow 的 hybrid retrieval + fused re-ranking
"""
import json
import re
from collections import Counter
from pathlib import Path

from .config import RETRIEVAL_CFG
from .embed import embed_single, cosine
from .llm import chat
from .chunker import estimate_tokens, TOKEN_RE
from .storage import (
    load_all_chunks, load_chunks_for_sources, load_chunks_except,
    overview_sources, get_feedback_boost,
)

_retrieval_cache: dict[str, tuple[list[str], list[str]] | None] = {}


# ── BM25 索引 ───────────────────────────────────────
def _tokenize(text: str) -> list[str]:
    """中文 bigram 分词 + 英文单词切分"""
    tokens = []
    buf = ""
    def _flush():
        nonlocal buf
        if not buf:
            return
        if re.search(r"[一-鿿]", buf):
            if len(buf) == 1:
                tokens.append(buf)
            else:
                for i in range(len(buf) - 1):
                    tokens.append(buf[i:i + 2])
        else:
            tokens.append(buf)
        buf = ""
    for ch in text.lower():
        if re.match(r"[一-鿿]", ch):
            if buf and not re.search(r"[一-鿿]", buf):
                _flush()
            buf += ch
        elif re.match(r"[a-zA-Z0-9]", ch):
            if buf and re.search(r"[一-鿿]", buf):
                _flush()
            buf += ch
        else:
            _flush()
    _flush()
    return tokens


class _BM25Index:
    def __init__(self):
        self.docs: list[tuple[int, str, str, list[str]]] = []
        self.df: dict[str, int] = {}
        self.avgdl: float = 0.0
        self.n: int = 0
        self._built = False

    def build(self):
        rows = load_all_chunks()
        self.docs, self.df = [], {}
        total_len = 0
        for chunk_id, source, text, _ in rows:
            tokens = _tokenize(text)
            self.docs.append((chunk_id, source, text, tokens))
            total_len += len(tokens)
            seen = set()
            for t in tokens:
                if t not in seen:
                    self.df[t] = self.df.get(t, 0) + 1
                    seen.add(t)
        self.n = len(self.docs)
        self.avgdl = total_len / self.n if self.n else 1
        self._built = True

    def search(self, query: str, top_k: int = 10) -> list[tuple[float, int, str, str]]:
        if not self._built:
            self.build()
        q_tokens = _tokenize(query)
        if not q_tokens or not self.docs:
            return []
        idf = {t: max(0, (self.n - self.df.get(t, 0) + 0.5) / (self.df.get(t, 0) + 0.5) + 1) for t in set(q_tokens)}
        scored = []
        for chunk_id, source, text, doc_tokens in self.docs:
            if not doc_tokens:
                continue
            dl = len(doc_tokens)
            tf: dict[str, int] = {}
            for t in doc_tokens:
                tf[t] = tf.get(t, 0) + 1
            score = 0.0
            for qt in q_tokens:
                if qt in tf:
                    f = tf[qt]
                    score += idf.get(qt, 0) * (f * (RETRIEVAL_CFG.bm25_k1 + 1)) / (f + RETRIEVAL_CFG.bm25_k1 * (1 - RETRIEVAL_CFG.bm25_b + RETRIEVAL_CFG.bm25_b * dl / self.avgdl))
            if score > 0:
                scored.append((score, chunk_id, text, source))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def invalidate(self):
        self._built = False


_bm25 = _BM25Index()


# ── 查询处理 ────────────────────────────────────────
_COMMON_TYPOS = {
    "机器试觉": "机器视觉", "机器式觉": "机器视觉", "机器是觉": "机器视觉",
    "机器视绝": "机器视觉", "机器视脚": "机器视觉",
    "压祝": "压铸", "压住": "压铸",
    "变拼器": "变频器", "变频气": "变频器",
    "继电起": "继电器", "继点器": "继电器",
    "实心": "实习", "实系": "实习",
    "ollma": "ollama", "olama": "ollama",
    "deepsek": "deepseek",
    "plc": "PLC", "Plc": "PLC",
}

_EXPANSIONS = {
    "plc": ["PLC", "可编程逻辑控制器", "自动化控制"],
    "ollama": ["Ollama", "本地大模型", "LLM"],
    "视觉": ["机器视觉", "图像处理", "特征提取"],
    "实习": ["生产实习", "工厂实习", "企业参观"],
    "电池": ["新能源电池", "锂电池", "动力电池"],
    "汽车": ["汽车制造", "整车", "零部件"],
    "机器人": ["工业机器人", "机械臂", "机器人编程"],
    "rag": ["RAG", "检索增强生成", "知识库"],
}


def correct_query(question: str) -> str:
    sorted_typos = sorted(_COMMON_TYPOS.items(), key=lambda x: len(x[0]), reverse=True)
    result = question
    i = 0
    out = []
    while i < len(result):
        matched = False
        for wrong, right in sorted_typos:
            if result[i:].startswith(wrong):
                out.append(right)
                i += len(wrong)
                matched = True
                break
        if not matched:
            out.append(result[i])
            i += 1
    return "".join(out)


def expand_query(question: str) -> str:
    if len(question) > 10:
        return question
    keywords = re.findall(r"[一-鿿]{2,}|[a-zA-Z]{2,}", question)
    if not keywords:
        return question
    expanded = [question]
    for kw in keywords:
        kw_lower = kw.lower()
        for key, values in _EXPANSIONS.items():
            if kw_lower == key or kw_lower in [v.lower() for v in values]:
                for v in values:
                    if v not in expanded:
                        expanded.append(v)
                break
    return " ".join(expanded) if len(expanded) > 1 else question


def rewrite_query(question: str) -> str:
    if not RETRIEVAL_CFG.enable_query_rewrite:
        return question
    prompt = f"你是一个检索助手。请将以下用户问题改写为更适合向量检索的查询文本。要求：保留原意，补充关键的同义词和上下文，输出纯文本不要解释不要引号，控制在50字以内。\n\n用户问题：{question}\n\n改写后的检索query："
    try:
        result = chat([{"role": "user", "content": prompt}])
        return result.strip().strip('"').strip("'").strip() or question
    except Exception:
        return question


# ── 融合排序 ────────────────────────────────────────
def _rrf_fusion(sem_results: list, bm25_results: list, k: int, top_k: int) -> list:
    scores: dict[int, float] = {}
    id_to_data: dict[int, tuple] = {}
    for rank, item in enumerate(sem_results):
        cid = item[1]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        id_to_data[cid] = item
    for rank, item in enumerate(bm25_results):
        cid = item[1]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        id_to_data[cid] = item
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [id_to_data[cid] for cid, _ in ranked[:top_k]]


def rerank(question: str, candidates: list, top_k: int = 5) -> list:
    if len(candidates) <= top_k:
        return candidates
    items = []
    for i, (score, cid, text, src) in enumerate(candidates[:15]):
        items.append(f"[{i+1}] {text[:200]}")
    candidate_list = "\n".join(items)
    prompt = f"你是一个文档检索排序助手。请根据与问题的相关性，从以下候选段落中选出最相关的 {top_k} 个。只输出编号，用逗号分隔，不要解释。\n\n问题：{question}\n\n候选段落：\n{candidate_list}\n\n最相关的 {top_k} 个编号："
    try:
        result = chat([{"role": "user", "content": prompt}])
        indices = [int(num) - 1 for num in re.findall(r"\d+", result) if 0 <= int(num) - 1 < len(candidates[:15])]
        if indices:
            return [candidates[i] for i in indices[:top_k]]
    except Exception:
        pass
    return candidates[:top_k]


def _chunk_quality_score(text: str) -> float:
    score = 1.0
    tokens = estimate_tokens(text)
    if tokens < 30:
        score *= 0.5
    elif tokens < 50:
        score *= 0.8
    lines = text.strip().split("\n")
    list_lines = sum(1 for l in lines if re.match(r"^[\d.]+\s+\S", l.strip()))
    if list_lines > len(lines) * 0.6 and len(lines) > 3:
        score *= 0.6
    ref_lines = sum(1 for l in lines if re.match(r"^\[?\d+\]?\s", l.strip()) or "参考文献" in l)
    if ref_lines > len(lines) * 0.5:
        score *= 0.4
    cn_sentences = len(re.findall(r"[。！？]", text))
    if cn_sentences >= 3:
        score *= 1.1
    return min(score, 1.2)


# ── 分层文档召回 ────────────────────────────────────
def _document_level_retrieval(question: str) -> list[str]:
    overviews = overview_sources()
    if not overviews:
        from .storage import list_sources
        return [s[0] for s in list_sources()][:3]
    q_emb = embed_single(question)
    scored = []
    for source, text in overviews:
        rows = load_all_chunks(source)
        for cid, src, t, emb_blob in rows:
            if t == text:
                emb = json.loads(emb_blob)
                scored.append((cosine(q_emb, emb), source))
                break
    scored.sort(key=lambda x: x[0], reverse=True)
    return [src for _, src in scored[:3]]


# ── 关键词兜底 ──────────────────────────────────────
def _keyword_search(question: str, top_k: int = 5) -> list | None:
    rows = load_all_chunks()
    keywords = re.findall(r"[一-鿿]{2,}|[a-zA-Z]{2,}|\d+", question.lower())
    if not keywords:
        return None
    scored = []
    for chunk_id, source, text, _ in rows:
        text_lower = text.lower()
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            scored.append((hits / len(keywords), chunk_id, text, source))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k] if scored else None


# ── 主检索入口 ──────────────────────────────────────
def retrieve(question: str, top_k: int | None = None, expand: int | None = None, trace: dict | None = None) -> tuple[list[str], list[str]] | None:
    tk = top_k or RETRIEVAL_CFG.top_k
    ex = expand or RETRIEVAL_CFG.expand
    cache_key = f"{question}|{tk}|{ex}"
    if cache_key in _retrieval_cache:
        return _retrieval_cache[cache_key]

    from .storage import count_chunks
    if count_chunks() == 0:
        _retrieval_cache[cache_key] = None
        return None

    corrected_q = correct_query(question)
    expanded_q = expand_query(corrected_q)
    rewritten_q = rewrite_query(corrected_q)

    steps = {
        "original": question,
        "corrected": corrected_q if corrected_q != question else None,
        "expanded": expanded_q if expanded_q != corrected_q else None,
        "rewritten": rewritten_q if rewritten_q != corrected_q else None,
    }

    relevant_docs = _document_level_retrieval(corrected_q)
    steps["docs_matched"] = [Path(d).name for d in relevant_docs] if relevant_docs else []

    q_emb = embed_single(rewritten_q)

    primary_rows = load_chunks_for_sources(relevant_docs) if relevant_docs else load_all_chunks()
    other_rows = load_chunks_except(relevant_docs) if relevant_docs else []
    steps["total_chunks"] = len(primary_rows) + len(other_rows)

    sem_scored = []
    for chunk_id, source, text, emb_blob in primary_rows + other_rows:
        emb = json.loads(emb_blob)
        score = cosine(q_emb, emb)
        sem_scored.append((score, chunk_id, text, source))
    sem_scored.sort(key=lambda x: x[0], reverse=True)
    sem_top = [item for item in sem_scored if item[0] >= RETRIEVAL_CFG.min_similarity][:tk * 2]
    steps["semantic_top"] = len(sem_top)
    steps["top_score"] = round(sem_top[0][0], 3) if sem_top else 0

    _bm25.invalidate()
    bm25_top = _bm25.search(expanded_q, top_k=tk * 2)
    steps["bm25_top"] = len(bm25_top)

    fused = _rrf_fusion(sem_top, bm25_top, RETRIEVAL_CFG.rrf_k, tk * 2)
    steps["fused_count"] = len(fused)

    if trace is not None:
        trace.update(steps)

    boosted = []
    for score, cid, text, src in fused:
        q_bonus = _chunk_quality_score(text) - 1.0
        f_bonus = get_feedback_boost(text)
        boosted.append((score + q_bonus + f_bonus, cid, text, src))
    boosted.sort(key=lambda x: x[0], reverse=True)
    fused = boosted

    if len(fused) > tk:
        fused = rerank(corrected_q, fused, top_k=tk)

    if not fused:
        kw_results = _keyword_search(question, tk)
        if kw_results:
            contexts = [t for _, _, t, _ in kw_results]
            sources = list(set(src for _, _, _, src in kw_results))
            _retrieval_cache[cache_key] = (contexts, sources)
            return contexts, sources
        _retrieval_cache[cache_key] = None
        return None

    top = fused
    from .storage import get_adjacent_chunks
    expanded_ids: set[int] = set()
    contexts_by_score: list[tuple[float, list[str]]] = []
    for score, chunk_id, _, source in top:
        group = get_adjacent_chunks(chunk_id, source, ex)
        if group:
            contexts_by_score.append((score, group))

    contexts = []
    for _, group in contexts_by_score:
        contexts.extend(group)

    seen = set()
    unique = []
    for t in contexts:
        key = t[:80]
        if key not in seen:
            seen.add(key)
            unique.append(t)

    sources = list(set(src for _, _, _, src in top))
    _retrieval_cache[cache_key] = (unique, sources)
    return unique, sources


def clear_cache():
    _retrieval_cache.clear()
    _bm25.invalidate()
