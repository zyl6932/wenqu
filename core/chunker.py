"""
文本处理层 — 清洗 + 分块 + 关键词
"""
import re
from collections import Counter

from .config import RETRIEVAL_CFG
from .llm import chat

TOKEN_RE = re.compile(r"[一-鿿　-〿]|[a-zA-Z]+|\d+|[^\s]")


def estimate_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))


# ── 清洗 ────────────────────────────────────────────
def clean_text(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    text = re.sub(r"[​-‏ - ⁠-⁯﻿]", "", text)
    text = re.sub(r"(?:^|\n)\s*(?:第\d+页|-\s*\d+\s*-|Page\s*\d+|\d+\s*/\s*\d+)\s*(?:\n|$)", "\n", text, flags=re.IGNORECASE)

    lines = text.split("\n")
    line_counts: dict[str, int] = {}
    for line in lines:
        key = line.strip()
        if key and len(key) < 30:
            line_counts[key] = line_counts.get(key, 0) + 1
    watermark_lines = {k for k, v in line_counts.items() if v >= 3}

    cleaned = []
    for line in lines:
        line = re.sub(r"[ ]{2,}", " ", line.strip())
        if not line or line in watermark_lines or re.match(r"^\d+$", line):
            cleaned.append("")
            continue
        if len(line) < 4 and not re.search(r"[，。！？、；：""''（）]", line):
            cleaned.append("")
            continue
        cleaned.append(line)

    result = []
    prev_empty = False
    for line in cleaned:
        if line == "":
            if not prev_empty:
                result.append(line)
            prev_empty = True
        else:
            result.append(line)
            prev_empty = False

    text = "\n".join(result).strip()
    merged: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            merged.append("")
            continue
        if merged and merged[-1] and merged[-1] != "":
            prev = merged[-1]
            if (not re.search(r"[。！？.!?：:；;）)】》\]]\s*$", prev)
                and not re.match(r"^[\d.]+[\s、]|[一二三四五六七八九十]+[、.．]|[（(]\d|[•·\-*▪►▶]", line)
                and not re.match(r"^第[一二三四五六七八九十\d]+[章节部]", line)):
                merged[-1] = prev + line
                continue
        merged.append(line)
    return "\n".join(merged).strip()


# ── 分句 ────────────────────────────────────────────
def split_sentences(text: str) -> list[str]:
    sentences = []
    paragraphs = re.split(r"\n\s*\n", text)
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        for line in para.split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = re.split(r"(?<=[。！？!?])\s*(?=\S)|(?<=……)\s*(?=\S)|(?<=\.{3})\s*(?=\S)", line)
            for s in parts:
                s = s.strip()
                if s:
                    sentences.append(s)
    return sentences


# ── 分块 ────────────────────────────────────────────
def split_text(text: str, max_tokens: int | None = None, overlap_tokens: int | None = None) -> list[str]:
    mt = max_tokens or RETRIEVAL_CFG.chunk_max_tokens
    ol = overlap_tokens or RETRIEVAL_CFG.chunk_overlap
    sentences = split_sentences(text)
    chunks = []
    current = ""
    current_tokens = 0

    for s in sentences:
        s_tokens = estimate_tokens(s)
        if s_tokens > mt:
            if current:
                chunks.append(current)
                current, current_tokens = "", 0
            chunks.append(truncate_by_tokens(s, mt))
            continue
        if current_tokens + s_tokens > mt:
            if current:
                chunks.append(current)
            if ol > 0 and current:
                overlap_text = get_overlap_tail(current, ol)
                tentative = overlap_text + s
                if estimate_tokens(tentative) <= mt:
                    current, current_tokens = tentative, estimate_tokens(tentative)
                else:
                    current, current_tokens = s, s_tokens
            else:
                current, current_tokens = s, s_tokens
        else:
            current += s
            current_tokens += s_tokens

    if current:
        chunks.append(current)
    return [c for c in chunks if estimate_tokens(c) >= 10]


def truncate_by_tokens(text: str, max_tokens: int) -> str:
    matches = list(TOKEN_RE.finditer(text))
    if len(matches) <= max_tokens:
        return text
    end_pos = matches[max_tokens - 1].end()
    truncated = text[:end_pos]
    last_period = max(truncated.rfind("。"), truncated.rfind("！"), truncated.rfind("？"))
    if last_period > len(truncated) * 0.6:
        return truncated[:last_period + 1]
    return truncated


def get_overlap_tail(text: str, overlap_tokens: int) -> str:
    sentences = split_sentences(text)
    tail = ""
    tail_tokens = 0
    for s in reversed(sentences):
        s_tokens = estimate_tokens(s)
        if tail_tokens + s_tokens > overlap_tokens and tail:
            break
        tail = s + tail
        tail_tokens += s_tokens
    return tail


# ── 语义分块 ───────────────────────────────────────
def semantic_split(text: str, max_tokens: int | None = None) -> list[str]:
    mt = max_tokens or RETRIEVAL_CFG.chunk_max_tokens
    if estimate_tokens(text) <= mt:
        return [text] if estimate_tokens(text) >= 10 else []

    sample = text[:3000]
    prompt = f"请分析以下文本的结构，识别出主要的章节或主题边界。输出每个边界的起始文字（前10-20字），每行一个，不要解释。\n\n文本：\n{sample}\n\n边界位置（每行一个起始文字）："
    try:
        result = chat([{"role": "user", "content": prompt}])
        boundaries = [line.strip() for line in result.strip().split("\n") if line.strip() and len(line.strip()) >= 4]
    except Exception:
        boundaries = []

    if not boundaries:
        return split_text(text, mt)

    chunks = []
    current = text
    for boundary in boundaries:
        idx = current.find(boundary)
        if idx <= 0:
            continue
        split_point = max(0, idx - 20)
        for sep in ["。", "！", "？", ".", "\n"]:
            last_sep = current.rfind(sep, max(0, split_point - 50), split_point + 50)
            if last_sep > 0:
                split_point = last_sep + 1
                break
        chunk = current[:split_point].strip()
        if chunk and estimate_tokens(chunk) >= 10:
            chunks.append(chunk)
        current = current[split_point:].strip()

    if current and estimate_tokens(current) >= 10:
        chunks.append(current)

    final = []
    for chunk in chunks:
        if estimate_tokens(chunk) > mt:
            final.extend(split_text(chunk, mt))
        else:
            final.append(chunk)
    return final if final else split_text(text, mt)


# ── 关键词 ──────────────────────────────────────────
def extract_keywords(text: str, top_n: int = 5) -> list[str]:
    cn_words = re.findall(r"[一-鿿]{2,6}", text)
    en_words = re.findall(r"[A-Za-z][a-zA-Z]{2,}", text)
    freq = Counter(cn_words + en_words)
    stops = {"我们", "他们", "这个", "那个", "可以", "进行", "通过", "以及", "同时", "主要", "包括", "具有", "其中", "方面", "本次", "能够", "需要", "这些", "一些", "利用"}
    keywords = [w for w, _ in freq.most_common(top_n * 2) if w not in stops]
    return keywords[:top_n]


def build_overview(text: str) -> str:
    """生成文档章节概览"""
    lines = text.split("\n")
    headings = [line.strip() for line in lines if re.match(r"^[\d.]+\s+\S", line) and len(line.strip()) > 4]
    companies = set()
    for pattern in [r"[一-鿿]{2,20}(?:公司|企业|集团|基地|创业园|产业园)", r"[一-鿿]{2,20}有限公司"]:
        companies.update(re.findall(pattern, text))

    parts = []
    if headings:
        parts.append("【文档章节概览】\n" + "\n".join(headings[:20]))
    if companies:
        parts.append("【涉及公司/机构】\n" + "\n".join(f"- {n}" for n in sorted(companies)[:30]))

    if not parts:
        return ""
    overview = "\n\n".join(parts)
    if estimate_tokens(overview) > 200:
        truncated = ""
        tokens = 0
        for line in overview.split("\n"):
            lt = estimate_tokens(line) + 1
            if tokens + lt > 200:
                break
            truncated += line + "\n"
            tokens += lt
        overview = truncated.strip()
    return overview
