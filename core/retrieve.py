"""
检索层 — 混合检索管线

完整流程（10 步，其中 2 步涉及 LLM 调用）：

 用户问题
   │
   ├─ ① correct_query()   — 拼写纠错（规则匹配）
   ├─ ② expand_query()    — 关键词扩展（领域词典）
   ├─ ③ rewrite_query()   — LLM 改写查询 → [可关：ENABLE_QUERY_REWRITE=0]
   │
   ├─ ④ 文档级召回         — 先定位相关文档，优先在匹配文档内搜
   ├─ ⑤ 向量检索           — cosine 相似度，过滤低于 min_similarity 的
   ├─ ⑥ BM25 检索          — bigram 分词 + IDF 加权
   ├─ ⑦ RRF 融合           — Reciprocal Rank Fusion，合并两路结果
   ├─ ⑧ 质量加权           — 惩罚碎片/纯列表块，奖励用户点过赞的块
   ├─ ⑨ LLM Rerank         — 让 LLM 从候选中挑最相关的 → [可关：代码中注释掉]
   │
   ├─ ⑩ 上下文扩展         — 邻块 + 父节点
   └─ 返回 contexts + sources

性能概况（top_k=10, enable_query_rewrite=1）：

  LLM 调用 #1: rewrite_query   ~2-3s   ← 查询改写
  LLM 调用 #2: rerank          ~2-3s   ← 重排序
  本地计算：                   ~800ms  ← 嵌入 + 搜索 + 融合
  ─────────────────────────────────
  检索阶段总耗时：              ~5-7s（之后才进入 LLM 生成 ~20-40s）

优化建议：
  - 设 ENABLE_QUERY_REWRITE=0 省 2-3s
  - 注释掉 rerank() 省 2-3s
  - 两者并行化省 2-3s（rewrite 和 rerank 之间无数据依赖）
  - 降低 top_k 省 5-10s（生成更快，因为 prompt 更短）
"""
import json
import re
import threading
from collections import Counter
from pathlib import Path
import numpy as np

from .config import RETRIEVAL_CFG
from .embed import embed_single, cosine
from .llm import chat
from .chunker import estimate_tokens, TOKEN_RE
from .storage import (
    overview_sources, get_feedback_boost, get_db,
)
from .vector_store import get_vector_store
from collections import OrderedDict

_RETRIEVAL_CACHE_MAX = 1000
_retrieval_cache: OrderedDict[str, tuple[list[str], list[str]] | None] = OrderedDict()
_cache_lock = threading.Lock()
_MISS = object()


def _cache_get(key: str):
    """LRU 读取：命中时移到末尾（最近使用）。返回 _MISS 表示未命中。"""
    with _cache_lock:
        if key in _retrieval_cache:
            _retrieval_cache.move_to_end(key)
            return _retrieval_cache[key]
        return _MISS


def _cache_set(key: str, value):
    """LRU 写入：超出上限时淘汰最久未使用的"""
    with _cache_lock:
        if key in _retrieval_cache:
            _retrieval_cache.move_to_end(key)
        _retrieval_cache[key] = value
        while len(_retrieval_cache) > _RETRIEVAL_CACHE_MAX:
            _retrieval_cache.popitem(last=False)


# ═══════════════════════════════════════════════════════
#  BM25 全文检索索引
# ═══════════════════════════════════════════════════════

def _tokenize(text: str) -> list[str]:
    """
    中文：bigram 分词。"机器视觉" → ["机器", "器视", "视觉"]
    英文/数字：按单词切分。"ollama123" → ["ollama123"]
    中英混合："Ollama安装" → ["ollama", "安装"]
    单字中文保留："电" → ["电"]（搜索最短词时的兜底）
    """
    tokens = []
    buf = ""
    def _flush():
        nonlocal buf
        if not buf:
            return
        if re.search(r"[一-鿿]", buf):      # 中文 → 逐字 bigram
            if len(buf) == 1:
                tokens.append(buf)
            else:
                for i in range(len(buf) - 1):
                    tokens.append(buf[i:i + 2])
        else:                                # 英文/数字 → 整个单词
            tokens.append(buf)
        buf = ""
    for ch in text.lower():
        if re.match(r"[一-鿿]", ch):
            if buf and not re.search(r"[一-鿿]", buf):
                _flush()                     # 英文 → 中文边界，刷新英文 token
            buf += ch
        elif re.match(r"[a-zA-Z0-9]", ch):
            if buf and re.search(r"[一-鿿]", buf):
                _flush()                     # 中文 → 英文边界，刷新中文 token
            buf += ch
        else:
            _flush()                         # 标点/空格 → 刷新缓冲区
    _flush()
    return tokens


def _bm25_like_search(query: str, top_k: int = 10) -> list[tuple[float, int, str, str]]:
    """轻量全文检索：SQL LIKE + TF-IDF 加权，替代原内存 BM25。"""
    tokens = _tokenize(query)
    if not tokens:
        return []
    db = get_db()
    N = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
    if N == 0:
        return []
    import math
    # 预计算每个 token 的 DF 和 IDF
    token_idf: dict[str, float] = {}
    for token in tokens[:10]:
        df = db.execute(
            "SELECT count(*) FROM chunks WHERE text LIKE ?",
            (f"%{token}%",),
        ).fetchone()[0]
        token_idf[token] = math.log(1.0 + (N - df + 0.5) / (df + 0.5)) if df > 0 else 0.0
    # 对每个 token 检索并打分
    scored: dict[int, tuple[float, str, str]] = {}
    for token in tokens[:10]:
        idf = token_idf.get(token, 0)
        if idf == 0:
            continue
        try:
            rows = db.execute(
                "SELECT id, source, text FROM chunks WHERE text LIKE ? LIMIT ?",
                (f"%{token}%", top_k * 3),
            ).fetchall()
        except Exception:
            continue
        for chunk_id, source, text in rows:
            tf = text.lower().count(token.lower())
            score = idf * (1.0 + math.log(max(tf, 1)))
            if chunk_id in scored:
                prev = scored[chunk_id]
                scored[chunk_id] = (prev[0] + score, prev[1], prev[2])
            else:
                scored[chunk_id] = (score, source, text)
    ranked = sorted(scored.items(), key=lambda x: x[1][0], reverse=True)
    return [(score, cid, text, src) for cid, (score, src, text) in ranked[:top_k]]





# ═══════════════════════════════════════════════════════
#  查询预处理：纠错 + 扩展 + 改写
# ═══════════════════════════════════════════════════════

# 拼写纠错表（规则匹配，不需要 LLM）
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

# 领域关键词扩展表（规则匹配，不需要 LLM）
# 当用户问题 ≤10 字时触发，短问题通常需要扩展上下文
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
    """
    ① 拼写纠错（0 成本）

    遍历 query，按最长匹配优先替换拼写错误。
    "机器试觉" → "机器视觉"（"试觉" 匹配 _COMMON_TYPOS）

    时间复杂度 O(n·m)，n=query 长度，m=错误表条目数（通常几十个）
    """
    if not isinstance(question, str):
        return ""
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
    """
    ② 关键词扩展（0 成本）

    仅对短问题（≤10 字）生效。
    将问题中的关键词展开为同义/上位词列表，拼回原问题。
    "plc" → "plc PLC 可编程逻辑控制器 自动化控制"

    作用：短问题的词太少，向量和 BM25 都匹配不到足够多的候选项
    """
    if not isinstance(question, str):
        return ""
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
    """
    ③ 查询改写（LLM 调用 #1，2-3s）

    让 LLM 将自然问句改写为更适合向量检索的关键词串。
    "光敏电阻可以用于空气湿度的测量吗" → "光敏电阻 空气湿度测量 应用"
    去掉口语化表达，保留核心名词。

    配置开关：ENABLE_QUERY_REWRITE=0 可关闭，省一次 LLM 调用
    """
    if not isinstance(question, str) or not question.strip():
        return question if isinstance(question, str) else ""
    if not RETRIEVAL_CFG.enable_query_rewrite:
        return question
    prompt = f"你是一个检索助手。请将以下用户问题改写为更适合向量检索的查询文本。要求：保留原意，补充关键的同义词和上下文，输出纯文本不要解释不要引号，控制在50字以内。\n\n用户问题：{question}\n\n改写后的检索query："
    try:
        result = chat([{"role": "user", "content": prompt}])
        return result.strip().strip('"').strip("'").strip() or question
    except Exception:
        return question


# ═══════════════════════════════════════════════════════
#  融合排序：RRF + LLM Rerank + 质量加权
# ═══════════════════════════════════════════════════════

def _rrf_fusion(sem_results: list, bm25_results: list, k: int, top_k: int) -> list:
    """
    ⑦ RRF（Reciprocal Rank Fusion）融合

    将语义检索和 BM25 检索的结果合并排序。

    算法：对每条结果，score = 1/(k + rank)
      - 语义检索排名和 BM25 排名分别贡献分数
      - 同时被两路检索到的结果分数会叠加（排名更高）
      - k=60 控制排名的影响程度，k 越大排名差异越小

    输出：去除各路的原始分数，仅用 RRF 分排序，取 top_k * 2
    """
    scores: dict[int, float] = {}
    id_to_data: dict[int, tuple] = {}
    # 语义检索贡献（向量相似度高的在这里排名靠前）
    for rank, item in enumerate(sem_results):
        cid = item[1]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        id_to_data[cid] = item
    # BM25 检索贡献（关键词匹配好的在这里排名靠前）
    for rank, item in enumerate(bm25_results):
        cid = item[1]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        id_to_data[cid] = item
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [id_to_data[cid] for cid, _ in ranked[:top_k]]


def rerank(question: str, candidates: list, top_k: int = 5) -> list:
    """
    ⑨ LLM 重排序（LLM 调用 #2，2-3s）

    当候选数 > top_k 时，让 LLM 从 15 个候选中挑选最相关的 top_k 个。
    每条候选只取前 200 字，减少 token 消耗。

    作用：RRF 是纯数学排序（只看排名，不看语义），LLM Rerank 能理解语义相关性。
    代价：每次检索多一次 LLM 调用。

    可关闭：直接 return candidates[:top_k] 跳过 LLM 调用，省 2-3s
    """
    if len(candidates) <= top_k:
        return candidates
    items = []
    for i, (score, cid, text, src) in enumerate(candidates[:15]):
        items.append(f"[{i+1}] {text[:200]}")
    candidate_list = "\n".join(items)
    prompt = (
        f"你是一个文档检索排序助手。请根据与问题的相关性，从以下候选段落中选出最相关的 {top_k} 个。"
        f"只输出编号，用逗号分隔，不要解释。\n\n"
        f"问题：{question}\n\n"
        f"候选段落：\n{candidate_list}\n\n"
        f"最相关的 {top_k} 个编号："
    )
    try:
        result = chat([{"role": "user", "content": prompt}])
        indices = [int(num) - 1 for num in re.findall(r"\d+", result)
                   if 0 <= int(num) - 1 < len(candidates[:15])]
        if indices:
            return [candidates[i] for i in indices[:top_k]]
    except Exception:
        pass
    return candidates[:top_k]


def _chunk_quality_score(text: str) -> float:
    """
    ⑧ 块质量评分（0 成本）

    检测低质量片段并降权：
      - Token < 30：0.5x（太短，信息量不足）
      - Token < 50：0.8x
      - 超过 60% 行是列表项：0.6x（纯列表没有上下文）
      - 超过 50% 行是参考文献：0.4x（引用信息无用）
      - 有 ≥3 个中文句号：1.1x（完整段落，信息密度高）

    返回值限制在 [0, 1.2] 范围
    """
    score = 1.0
    tokens = estimate_tokens(text)
    if tokens < 30:
        score *= 0.5          # 太短 → 降权
    elif tokens < 50:
        score *= 0.8
    lines = text.strip().split("\n")
    # 大量列表行 → 可能是目录/索引
    list_lines = sum(1 for l in lines if re.match(r"^[\d.]+\s+\S", l.strip()))
    if list_lines > len(lines) * 0.6 and len(lines) > 3:
        score *= 0.6
    # 大量参考文献行 → 对问答几乎无用
    ref_lines = sum(1 for l in lines if re.match(r"^\[?\d+\]?\s", l.strip()) or "参考文献" in l)
    if ref_lines > len(lines) * 0.5:
        score *= 0.4
    # 完整段落 → 加分
    cn_sentences = len(re.findall(r"[。！？]", text))
    if cn_sentences >= 3:
        score *= 1.1
    return min(score, 1.2)


# ═══════════════════════════════════════════════════════
#  文档级召回：先定位文档，再在文档内搜索
# ═══════════════════════════════════════════════════════

def _document_level_retrieval(question: str) -> list[str]:
    """
    ④ 文档级召回（0 成本 LLM，~300ms 嵌入）

    策略：先找出哪些文档与问题相关，优先在这些文档里搜索。
    这比全库搜索更快且更准确（减少了无关文档的噪音）。

    实现：
      1. 查找所有有章节概览的文档（overview_sources）
      2. 用问题的向量与概览的向量做 cosine 相似度
      3. 返回最相关的 3 个文档
      4. 如果没有概览，返回最新 3 个文档
    """
    overviews = overview_sources()
    if not overviews:
        from .storage import list_sources
        return [s[0] for s in list_sources()][:3]
    q_emb = embed_single(question)
    scored = []
    for source, text, emb_blob in overviews:
        try:
            emb = json.loads(emb_blob)
        except Exception:
            import numpy as np
            emb = np.frombuffer(emb_blob, dtype=np.float32).tolist()
        scored.append((cosine(q_emb, emb), source))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [src for _, src in scored[:3]]


# ═══════════════════════════════════════════════════════
#  关键词兜底检索（最后一道防线）
# ═══════════════════════════════════════════════════════

def _keyword_search(question: str, top_k: int = 5) -> list | None:
    """
    关键词兜底检索（0 成本）

    当向量 + BM25 都找不到任何候选时触发。
    直接用 SQL LIKE 做关键词匹配，不再全量加载。
    """
    keywords = re.findall(r"[一-鿿]{2,}|[a-zA-Z]{2,}|\d+", question.lower())
    if not keywords:
        return None
    db = get_db()
    scored = []
    for kw in keywords[:5]:
        try:
            rows = db.execute(
                "SELECT id, source, text FROM chunks WHERE text LIKE ? LIMIT ?",
                (f"%{kw}%", top_k),
            ).fetchall()
        except Exception:
            continue
        for chunk_id, source, text in rows:
            scored.append((1.0, chunk_id, text, source))
    if not scored:
        return None
    seen = set()
    unique = []
    for s in scored:
        if s[1] not in seen:
            seen.add(s[1])
            unique.append(s)
    return unique[:top_k]


# ═══════════════════════════════════════════════════════
#  主检索入口
# ═══════════════════════════════════════════════════════

def retrieve(question: str, top_k: int | None = None, expand: int | None = None,
             trace: dict | None = None) -> tuple[list[str], list[str]] | None:
    """
    主检索入口 — 10 步完整管线。

    参数：
      question: 用户原始问题
      top_k:    最终返回的片段数（默认 10）
      expand:   邻块扩展数（默认 1，即前后各 1 块）
      trace:    调试用，填入 {step: value} 供 thinking 展示

    返回：
      (contexts, source_paths) 或 None（知识库为空）
    """
    if not isinstance(question, str) or not question.strip():
        return None
    tk = top_k if top_k is not None and top_k > 0 else RETRIEVAL_CFG.top_k
    ex = expand if expand is not None and expand >= 0 else RETRIEVAL_CFG.expand
    cache_key = f"{question}|{tk}|{ex}"

    # 缓存命中：同一问题 + 同参数直接返回上次结果
    cached = _cache_get(cache_key)
    if cached is not _MISS:
        return cached

    # 知识库为空
    from .storage import count_chunks
    if count_chunks() == 0:
        _cache_set(cache_key, None)
        return None

    # ── 步骤 ①②③：查询预处理 ──
    # ① 拼写纠错（规则匹配，0 成本）
    corrected_q = correct_query(question)
    # ② 关键词扩展（短问题时触发，0 成本）
    expanded_q = expand_query(corrected_q)
    # ③ LLM 查询改写（可关闭，2-3s）
    rewritten_q = rewrite_query(corrected_q)

    steps = {
        "original": question,
        "corrected": corrected_q if corrected_q != question else None,
        "expanded": expanded_q if expanded_q != corrected_q else None,
        "rewritten": rewritten_q if rewritten_q != corrected_q else None,
    }

    # ── 步骤 ④：文档级召回 ──
    # 先找出 3 个最相关文档，优先搜索它们
    relevant_docs = _document_level_retrieval(corrected_q)
    steps["docs_matched"] = [Path(d).name for d in relevant_docs] if relevant_docs else []

    # ── 步骤 ⑤：向量语义检索 ──
    q_emb = embed_single(rewritten_q)
    sem_top = []
    vs = None
    try:
        vs = get_vector_store()
        if vs.size > 0:
            sem_top = vs.search(q_emb, top_k=tk * 2, min_similarity=RETRIEVAL_CFG.min_similarity)
    except Exception:
        sem_top = []
    steps["total_chunks"] = vs.size if vs and vs.size > 0 else 0
    steps["semantic_top"] = len(sem_top)
    steps["top_score"] = round(sem_top[0][0], 3) if sem_top else 0

    # ── 步骤 ⑥：FTS5 全文检索 ──
    bm25_top = _bm25_like_search(expanded_q, top_k=tk * 2)
    steps["bm25_top"] = len(bm25_top)

    # ── 步骤 ⑦：RRF 融合 ──
    # 将语义和 BM25 两路候选融合为一个排序列表
    fused = _rrf_fusion(sem_top, bm25_top, RETRIEVAL_CFG.rrf_k, tk * 2)
    steps["fused_count"] = len(fused)

    # 将步骤信息写入 trace（供 ask_stream 的 thinking 展示）
    if trace is not None:
        trace.update(steps)

    # ── 步骤 ⑧：质量加权 + 反馈加权 ──
    # 对每个融合后的候选项，加上质量分和用户反馈分
    boosted = []
    for score, cid, text, src in fused:
        q_bonus = _chunk_quality_score(text) - 1.0     # 碎片扣分，完整段加分
        f_bonus = get_feedback_boost(text)              # 用户点过赞的 +0.05
        boosted.append((score + q_bonus + f_bonus, cid, text, src))
    boosted.sort(key=lambda x: x[0], reverse=True)
    fused = boosted

    # ── 步骤 ⑨：LLM 重排序 ──
    # 当候选 > top_k 时，让 LLM 挑选最相关的（默认关闭，省 2-3s + 1 次 LLM 调用）
    if RETRIEVAL_CFG.enable_rerank and len(fused) > tk:
        fused = rerank(corrected_q, fused, top_k=tk)

    # ── 兜底：两路都没找到候选 → 关键词暴力匹配 ──
    if not fused:
        kw_results = _keyword_search(question, tk)
        if kw_results:
            contexts = [t for _, _, t, _ in kw_results]
            sources = list(set(src for _, _, _, src in kw_results))
            _cache_set(cache_key, (contexts, sources))
            return contexts, sources
        _cache_set(cache_key, None)
        return None

    top = fused

    # ── 步骤 ⑩：上下文扩展 ──
    # 对每个匹配块，拉取前后邻块 + 父节点（章节标题）
    from .storage import get_adjacent_chunks, get_parent_chunk
    contexts_by_score: list[tuple[float, list[str]]] = []
    for score, chunk_id, _, source in top:
        group = get_adjacent_chunks(chunk_id, source, ex) or []
        # 命中子块时，自动带出父级标题块（如匹配到"1.2 工作原理"时带上"第一章 光敏电阻"）
        parent = get_parent_chunk(chunk_id)
        if parent and parent[2] not in group:
            group.insert(0, parent[2])
        if group:
            contexts_by_score.append((score, group))

    # 按分数排序，展开为扁平列表
    contexts = []
    for _, group in contexts_by_score:
        contexts.extend(group)

    # 去重：相邻块可能和父节点重复
    seen = set()
    unique = []
    for t in contexts:
        key = t[:80]
        if key not in seen:
            seen.add(key)
            unique.append(t)

    # 每个源文档取最高相关度分数
    src_scores: dict[str, float] = {}
    for score, _, _, src in top:
        if src not in src_scores or score > src_scores[src]:
            src_scores[src] = score
    sources = sorted(src_scores.keys(), key=lambda s: src_scores[s], reverse=True)
    source_scores = [round(src_scores[s], 4) for s in sources]
    _cache_set(cache_key, (unique, sources, source_scores))
    return unique, sources, source_scores


def clear_cache():
    """清空检索缓存和向量存储"""
    with _cache_lock:
        _retrieval_cache.clear()
    from .vector_store import rebuild_vector_store
    rebuild_vector_store()
