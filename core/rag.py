"""
RAG 编排层 — 串联检索 + 生成 + 对话
"""
import re
from pathlib import Path

from .config import LLM_CFG, STORAGE_CFG, RETRIEVAL_CFG
from .llm import chat, chat_stream
from .chunker import estimate_tokens, clean_text, split_text, split_with_structure, build_overview, extract_keywords
from .embed import embed_single, clear_cache
from .storage import (
    count_chunks, count_sources, insert_chunk, update_chunk_text,
    delete_chunk_by_id, delete_chunks_by_ids, get_chunk_by_id,
    source_exists, insert_source, delete_source, list_sources,
    save_feedback, load_all_chunks,
    get_db,
)
from .retrieve import retrieve, clear_cache as clear_retrieval_cache, expand_query, correct_query


# ── 提示构建 ───────────────────────────────────────
def build_prompt(contexts: list[str], question: str) -> str:
    context = "\n\n---\n\n".join(contexts)
    return f"""你是一个知识库助手，你的职责是**仅根据以下参考内容**回答问题。

重要规则：
1. 只能使用「参考内容」中明确出现的信息。不要引入你自己的知识。
2. 如果参考内容中找不到答案，直接说"根据已有资料，我无法回答这个问题"，禁止猜测、推理或编造任何信息。
3. 回答时引用参考内容中的原文片段。

参考内容：
{context}

问题：{question}

请用中文回答，简洁明了。"""


# ── 智能 top_k ─────────────────────────────────────
def _smart_top_k(question: str) -> int:
    tokens = estimate_tokens(question)
    keywords = len(re.findall(r"[一-鿿]{2,}|[a-zA-Z]{2,}", question))
    if tokens <= 5 and keywords <= 2:
        return 5
    elif tokens <= 15:
        return 8
    return 12


# ── 多轮对话上下文 ──────────────────────────────────
def expand_with_history(question: str, history: list[dict] | None) -> str:
    if not history or len(history) < 2:
        return question
    recent_user = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            recent_user = msg.get("content", "")
            break
    if not recent_user or recent_user == question:
        return question
    keywords = re.findall(r"[一-鿿]{2,}|[a-zA-Z]{2,}", recent_user)
    if not keywords:
        return question
    if len(question) < 10:
        return question + " " + " ".join(keywords[:5])
    return question


# ── 流式问答 ───────────────────────────────────────
def ask_stream(question: str, top_k: int | None = None, history: list[dict] | None = None, llm_provider: str | None = None):
    think_steps = []
    source_names = []
    prompt = question

    enriched_q = expand_with_history(question, history)
    dynamic_k = _smart_top_k(question)
    tk = max(top_k or RETRIEVAL_CFG.top_k, dynamic_k)
    trace: dict = {}
    yield ("thinking", "正在检索相关知识…")
    result = retrieve(enriched_q, top_k=tk, trace=trace)

    if result is None:
        if count_sources() > 0:
            yield ("error", "未找到相关内容，请换个方式提问")
        else:
            yield ("error", "知识库为空，请先导入文档")
        return

    contexts, source_paths = result
    source_names = [Path(s).name for s in source_paths]
    yield ("sources", source_names)

    # 准备思考步骤（不立即发送，穿插在 token 流中）
    think_steps.append(f"问题：{trace.get('original', question)}")
    if trace.get("corrected"):
        think_steps.append(f"纠错：{trace['corrected']}")
    if trace.get("expanded"):
        think_steps.append(f"扩展：{trace['expanded']}")
    if trace.get("rewritten"):
        think_steps.append(f"改写：{trace['rewritten']}")
    think_steps.append(f"检索 {trace.get('total_chunks', 0)} 个向量块中…")
    if trace.get("docs_matched"):
        think_steps.append(f"匹配文档：{', '.join(trace['docs_matched'])}")
    think_steps.append(f"语义检索 {trace.get('semantic_top', 0)} 个候选（最高 {trace.get('top_score', 0)}）")
    think_steps.append(f"BM25 检索 {trace.get('bm25_top', 0)} 个候选")
    think_steps.append(f"RRF 融合 → 返回 {len(contexts)} 个片段")

    prompt = build_prompt(contexts, question)
    system_msg = {"role": "system", "content": "你是一个严谨的知识库助手，仅根据提供的参考内容回答问题。如果参考内容中找不到答案，请直接说\"根据已有资料，我无法回答这个问题\"，不要编造。请用中文回答，简洁明了。"}

    # 如果指定了 llm_provider，临时切换（支持前端运行时切换 本地/联网）
    previous_provider = None
    if llm_provider:
        previous_provider = LLM_CFG.provider
        LLM_CFG.provider = llm_provider

    try:
        messages = [system_msg]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        full_answer = ""
        think_idx = 0
        think_step_interval = 6
        token_count = 0
        for kind, text in chat_stream(messages):
            if kind == "think":
                full_answer += text
                yield ("think", text)
            else:
                full_answer += text
                yield ("token", text)
                token_count += 1
                if think_idx < len(think_steps) and token_count >= think_step_interval:
                    yield ("thinking", think_steps[think_idx])
                    think_idx += 1
                    token_count = 0
    finally:
        if llm_provider and previous_provider is not None:
            LLM_CFG.provider = previous_provider

    # 发出剩余的思考步骤
    while think_idx < len(think_steps):
        yield ("thinking", think_steps[think_idx])
        think_idx += 1

    # 质量兜底
    need_retry = False
    retry_hint = ""
    if len(full_answer.strip()) < 15:
        need_retry = True
        retry_hint = "请展开详细回答，不要过于简短。"
    elif "无法回答" in full_answer or "没有找到" in full_answer:
        keywords = re.findall(r"[一-鿿]{2,}", question)
        if keywords and not any(kw in full_answer for kw in keywords[:3]):
            need_retry = True
            retry_hint = f"请围绕「{question}」回答，参考内容中应有相关信息。"

    if need_retry:
        retry_messages = [system_msg]
        if history:
            retry_messages.extend(history)
        retry_messages.append({"role": "user", "content": prompt + f"\n\n（{retry_hint}）"})
        yield ("token", "\n[补充回答] ")
        for kind, text in chat_stream(retry_messages):
            if kind == "think":
                yield ("think", text)
            else:
                yield ("token", text)

    if source_names:
        yield ("sources", source_names)


# ── 导入文档 ───────────────────────────────────────
from .parser import parse_file

def import_docs():
    STORAGE_CFG.docs_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ("*.txt", "*.md", "*.docx", "*.pptx", "*.pdf", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp", "*.webp"):
        files.extend(STORAGE_CFG.docs_dir.rglob(ext))

    # 过滤 Office 临时文件
    files = [f for f in files if not f.name.startswith("~$")]

    if not files:
        print(f">>> 请在 {STORAGE_CFG.docs_dir} 目录放入文档，然后重新运行")
        return

    for fp in files:
        path = str(fp.resolve())
        if source_exists(path):
            print(f"  跳过 (已导入): {fp.name}")
            continue

        try:
            text = parse_file(str(fp))
        except Exception as e:
            print(f"  跳过 ({e}): {fp.name}")
            continue

        text = clean_text(text)
        if not text.strip():
            print(f"  无有效内容: {fp.name}")
            continue

        structured = split_with_structure(text)
        if not structured:
            print(f"  无有效内容: {fp.name}")
            continue

        # 去重
        seen_prefix: set[str] = set()
        unique = [c for c in structured if (key := c["text"][:80].strip()) not in seen_prefix and not seen_prefix.add(key)]

        # 概览 + 摘要
        overview = build_overview(text)
        if overview:
            unique.insert(0, {"text": overview, "level": 0, "heading": ""})
        try:
            summary = chat([
                {"role": "system", "content": "你是一个文档摘要助手。用2-3句话概括文档核心内容，输出纯文本。"},
                {"role": "user", "content": f"请为以下文档生成简短摘要（50字以内）：\n\n{text[:2000]}"},
            ])
            if summary and len(summary) > 10:
                unique.insert(0, {"text": f"【文档摘要】{summary}", "level": 0, "heading": ""})
        except Exception:
            pass

        # 建立父子关系：最近的一级标题作为父节点
        texts = [c["text"] for c in unique]
        parent_ids: dict[str, int] = {}  # heading -> parent chunk id
        print(f"  向量化 {fp.name} ({len(texts)} 块)...", end=" ", flush=True)
        from .embed import embed
        embeddings = embed(texts)
        for c, emb in zip(unique, embeddings):
            level = c["level"]
            heading = c["heading"]
            pid = parent_ids.get(heading) if heading and level > 0 else None
            cid = insert_chunk(path, c["text"], emb, level, pid)
            if level == 1 and heading:
                parent_ids[heading] = cid
        insert_source(path)
        print("完成")


# ── 块管理 ──────────────────────────────────────────
def list_chunks(source: str | None = None) -> list[dict]:
    rows = load_all_chunks(source)
    return [
        {"id": r[0], "source": r[1], "text": r[2], "tokens": estimate_tokens(r[2]), "keywords": extract_keywords(r[2])}
        for r in rows
    ]


def update_chunk(chunk_id: int, new_text: str):
    new_text = new_text.strip()
    if not new_text:
        raise ValueError("文本不能为空")
    from .embed import embed_single
    emb = embed_single(new_text)
    update_chunk_text(chunk_id, new_text, emb)
    clear_retrieval_cache()
    clear_cache()


def delete_chunk(chunk_id: int):
    delete_chunk_by_id(chunk_id)
    clear_retrieval_cache()
    clear_cache()


def delete_chunks(ids: list[int]):
    delete_chunks_by_ids(ids)
    clear_retrieval_cache()
    clear_cache()


def split_chunk(chunk_id: int, separator: str) -> list[int]:
    row = get_chunk_by_id(chunk_id)
    if not row:
        raise ValueError(f"块 {chunk_id} 不存在")
    source, text = row[1], row[2]
    if separator not in text:
        raise ValueError("分隔文本不在块内容中")
    parts = [p.strip() for p in text.split(separator, 1) if p.strip()]
    if len(parts) < 2:
        raise ValueError("拆分后不足两块")
    delete_chunk_by_id(chunk_id)
    from .embed import embed
    embeddings = embed(parts)
    new_ids = [insert_chunk(source, part, emb) for part, emb in zip(parts, embeddings)]
    clear_retrieval_cache()
    clear_cache()
    return new_ids


def merge_chunks(chunk_ids: list[int]) -> int:
    if len(chunk_ids) < 2:
        raise ValueError("至少需要两块")
    db = get_db()
    placeholders = ",".join("?" * len(chunk_ids))
    rows = db.execute(
        f"SELECT id, source, text FROM chunks WHERE id IN ({placeholders}) ORDER BY id", chunk_ids
    ).fetchall()
    if len(rows) != len(chunk_ids):
        raise ValueError("部分块不存在")
    source = rows[0][1]
    merged_text = "\n\n".join(r[2] for r in rows)
    delete_chunks_by_ids([r[0] for r in rows])
    from .embed import embed_single
    emb = embed_single(merged_text)
    new_id = insert_chunk(source, merged_text, emb)
    clear_retrieval_cache()
    clear_cache()
    return new_id


def record_feedback(question: str, contexts: list[str], helpful: bool):
    score = 1 if helpful else -1
    for ctx in contexts[:5]:
        save_feedback(question, ctx[:80], score)


def get_doc_content(path: str) -> str:
    fp = Path(path)
    if not fp.exists():
        return ""
    return parse_file(str(fp))
