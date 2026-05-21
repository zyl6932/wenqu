"""
本地知识库 Web 服务器 — FastAPI + uvicorn
启动: python server.py 或 uvicorn server:app --host 0.0.0.0 --port 8080
"""
import json
import sys
import time as _time
import threading
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response

from core.rag import (
    import_docs, ask_stream, get_doc_content,
    list_chunks, update_chunk, delete_chunk, delete_chunks, split_chunk, merge_chunks,
    record_feedback, build_prompt,
)
from core.storage import delete_source as delete_doc
from core.storage import count_sources, get_db
from core.retrieve import retrieve
from core.config import EMBED_CFG, get_runtime_config, _runtime_overrides, apply_runtime_overrides

STATIC_DIR = Path(__file__).parent / "static"
REACT_DIST = STATIC_DIR / "dist"

# ── 错误日志 ──────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
_log_lock = threading.Lock()


def log_error(msg: str):
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = LOG_DIR / f"error-{datetime.date.today().isoformat()}.log"
    try:
        with _log_lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── 请求速率限制 ────────────────────────────────────
_request_counts: dict[str, list[float]] = {}
_request_lock = threading.Lock()


def _check_rate(client_ip: str) -> bool:
    now = _time.time()
    with _request_lock:
        times = _request_counts.get(client_ip, [])
        times = [t for t in times if now - t < 1.0]
        if len(times) >= 10:
            _request_counts[client_ip] = times
            return False
        times.append(now)
        _request_counts[client_ip] = times
        # 超过 5000 个 IP 时清理过期条目（最后活跃 >60s 前）
        if len(_request_counts) > 5000:
            stale = [ip for ip, ts in _request_counts.items()
                     if not ts or (isinstance(ts, list) and ts and ts[-1] < now - 60)]
            for ip in stale:
                del _request_counts[ip]
        return True


app = FastAPI(title="问渠 (Wenqu)", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate(client_ip):
        return JSONResponse({"error": "请求过于频繁"}, status_code=429)
    return await call_next(request)


# ── API 路由 ─────────────────────────────────────────

@app.get("/api/health")
async def api_health():
    return {"status": "ok"}


@app.get("/api/health/full")
async def api_health_full():
    return {
        "status": "ok",
        "port": _check_port(8080),
        "ollama": _check_ollama(),
        "data": _check_data(),
    }


@app.get("/api/config")
async def api_get_config():
    return get_runtime_config()


@app.post("/api/config")
def api_update_config(data: dict):
    changed = False
    for key in ("min_similarity", "top_k", "enable_query_rewrite", "enable_rerank"):
        if key in data:
            _runtime_overrides[key] = data[key]
            changed = True
    if changed:
        apply_runtime_overrides()
        from core.retrieve import clear_cache
        clear_cache()
    return {"config": get_runtime_config(), "message": "已更新" if changed else "无变更"}


@app.get("/api/docs")
async def api_list_docs(page: int = 1, page_size: int = 50):
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    offset = (page - 1) * page_size
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    rows = db.execute(
        "SELECT path, added_at FROM sources ORDER BY added_at DESC LIMIT ? OFFSET ?",
        (page_size, offset)
    ).fetchall()
    docs = [
        {"path": row[0], "name": Path(row[0]).name, "added_at": row[1]}
        for row in rows
    ]
    return {"docs": docs, "total": total, "page": page, "page_size": page_size}


@app.delete("/api/docs")
def api_delete_doc(data: dict):
    path = data.get("path", "").strip()
    if not path:
        raise HTTPException(400, "缺少 path 参数")
    try:
        delete_doc(path)
        return {"message": f"已删除 {Path(path).name}"}
    except Exception as e:
        log_error(f"DELETE /api/docs: {e}")
        raise HTTPException(500, str(e))


@app.post("/api/docs/reindex")
def api_reindex():
    log_lines = []
    import_docs(on_log=log_lines.append)
    from core.retrieve import clear_cache
    clear_cache()
    return {"message": "\n".join(log_lines) or "重新索引完成"}


@app.get("/api/docs/content")
async def api_doc_content(path: str = ""):
    if not path:
        raise HTTPException(400, "缺少 path 参数")
    try:
        content = get_doc_content(path)
        return {"path": path, "name": Path(path).name, "content": content}
    except Exception as e:
        log_error(f"GET /api/docs/content: {e}")
        raise HTTPException(500, str(e))


@app.get("/api/chunks")
async def api_list_chunks(source: str | None = None, page: int = 1, page_size: int = 50):
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    try:
        chunks, total = list_chunks(source, page=page, page_size=page_size)
        return {"chunks": chunks, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        log_error(f"GET /api/chunks: {e}")
        raise HTTPException(500, str(e))


@app.put("/api/chunks")
def api_update_chunk(data: dict):
    chunk_id = data.get("id")
    text = data.get("text", "")
    if not chunk_id:
        raise HTTPException(400, "缺少 id")
    try:
        update_chunk(int(chunk_id), text)
        return {"message": "已更新"}
    except Exception as e:
        log_error(f"PUT /api/chunks: {e}")
        raise HTTPException(500, str(e))


@app.delete("/api/chunks")
def api_delete_chunks(data: dict):
    chunk_id = data.get("id")
    chunk_ids = data.get("ids")
    try:
        if chunk_ids:
            delete_chunks([int(c) for c in chunk_ids])
            return {"message": f"已删除 {len(chunk_ids)} 块"}
        elif chunk_id:
            delete_chunk(int(chunk_id))
            return {"message": "已删除"}
        else:
            raise HTTPException(400, "缺少 id 或 ids")
    except Exception as e:
        log_error(f"DELETE /api/chunks: {e}")
        raise HTTPException(500, str(e))


@app.post("/api/chunks/split")
def api_split_chunk(data: dict):
    chunk_id = data.get("id")
    separator = data.get("separator", "")
    if not chunk_id or not separator:
        raise HTTPException(400, "缺少 id 或 separator")
    try:
        new_ids = split_chunk(int(chunk_id), separator)
        return {"message": f"已拆分为 {len(new_ids)} 块", "ids": new_ids}
    except Exception as e:
        log_error(f"POST /api/chunks/split: {e}")
        raise HTTPException(500, str(e))


@app.post("/api/chunks/merge")
def api_merge_chunks(data: dict):
    chunk_ids = data.get("ids", [])
    if len(chunk_ids) < 2:
        raise HTTPException(400, "至少选择两块")
    try:
        new_id = merge_chunks([int(c) for c in chunk_ids])
        return {"message": "已合并", "id": new_id}
    except Exception as e:
        log_error(f"POST /api/chunks/merge: {e}")
        raise HTTPException(500, str(e))


@app.post("/api/ask")
def api_ask(data: dict):
    question = data.get("question", "").strip()
    if not question:
        raise HTTPException(400, "问题不能为空")

    result = retrieve(question)
    if result is None:
        return {"answer": "未找到相关内容", "sources": []}

    contexts, source_paths = result
    prompt = build_prompt(contexts, question)
    from core.llm import chat
    answer = chat([{"role": "system", "content": "你是严谨的知识库助手。"}, {"role": "user", "content": prompt}])
    return {"answer": answer, "sources": [Path(s).name for s in source_paths]}


@app.post("/api/ask/stream")
async def api_ask_stream(data: dict):
    question = data.get("question", "").strip()
    if not question:
        raise HTTPException(400, "问题不能为空")

    llm_provider = data.get("llm_provider", None)
    history = data.get("history", None)
    if history is not None and (not isinstance(history, list) or not all(
        isinstance(m, dict) and "role" in m and "content" in m for m in history
    )):
        history = None

    async def sse_generate():
        try:
            for event_type, payload in ask_stream(question, history=history, llm_provider=llm_provider):
                line = json.dumps({event_type: payload}, ensure_ascii=False)
                yield f"data: {line}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse_generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "close"},
    )


@app.post("/api/import")
def api_import():
    log_lines = []
    import_docs(on_log=log_lines.append)
    return {"message": "\n".join(log_lines) or "导入完成"}


@app.post("/api/upload")
def api_upload(file: UploadFile = File(...), request=None):
    if not file.filename:
        raise HTTPException(400, "无文件")
    if request:
        cl = request.headers.get("content-length")
        if cl and int(cl) > 100 * 1024 * 1024:
            raise HTTPException(413, "文件大小不能超过 100MB")
    docs_dir = Path(__file__).parent / "docs"
    docs_dir.mkdir(exist_ok=True)
    save_path = docs_dir / Path(file.filename).name
    content = file.file.read()
    with open(save_path, 'wb') as f:
        f.write(content)
    import_docs()
    from core.retrieve import clear_cache
    clear_cache()
    return {"message": f"已上传并导入 {file.filename}"}


@app.post("/api/title")
def api_gen_title(data: dict):
    question = data.get("question", "").strip()
    if not question:
        raise HTTPException(400, "问题不能为空")
    try:
        from core.llm import chat
        prompt = f"为以下用户问题生成一个简洁的对话标题（最多15字，不要引号，直接输出标题文本）：\n\n{question}"
        title = chat([{"role": "user", "content": prompt}])
        title = title.strip().strip('"').strip("'").strip()[:20]
        return {"title": title or question[:15]}
    except Exception:
        return {"title": question[:15]}


@app.post("/api/feedback")
async def api_feedback(data: dict):
    question = data.get("question", "")
    contexts = data.get("contexts", [])
    helpful = data.get("helpful", True)
    if not question or not contexts:
        raise HTTPException(400, "缺少 question 或 contexts")
    try:
        record_feedback(question, contexts, helpful)
        return {"message": "反馈已记录"}
    except Exception as e:
        log_error(f"POST /api/feedback: {e}")
        raise HTTPException(500, str(e))


# ── OpenAI 兼容端点 ──────────────────────────────────

@app.get("/v1/models")
@app.post("/v1/models")
async def api_v1_models():
    return {
        "object": "list",
        "data": [{"id": "wenqu-v1", "object": "model", "owned_by": "wenqu"}],
    }


@app.post("/v1/chat/completions")
async def api_v1_chat_completions(data: dict, request: Request):
    messages = data.get("messages", [])
    if not messages:
        return JSONResponse(
            {"error": {"message": "缺少 messages", "type": "invalid_request_error"}}, 400
        )

    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break
    if not user_msg:
        return JSONResponse(
            {"error": {"message": "需要用户消息", "type": "invalid_request_error"}}, 400
        )

    result = retrieve(user_msg)
    request_id = f"chatcmpl-{hash(user_msg) % 10**9:09d}"

    if result is None:
        msg = "知识库为空，请先导入文档。"
        if data.get("stream"):
            async def empty_stream():
                chunk = json.dumps({
                    "id": request_id, "object": "chat.completion.chunk",
                    "created": int(_time.time()), "model": "wenqu-v1",
                    "choices": [{"index": 0, "delta": {"content": msg}, "finish_reason": "stop"}],
                })
                yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(empty_stream(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache"})
        return {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": msg}, "finish_reason": "stop"}],
        }

    contexts, source_paths = result
    prompt = build_prompt(contexts, user_msg)
    system_msg = {"role": "system", "content": "你是一个严谨的知识库助手，仅根据提供的参考内容回答问题。"}
    llm_messages = [system_msg] + messages[:-1] + [{"role": "user", "content": prompt}]

    if data.get("stream"):
        async def sse_chat():
            try:
                from core.llm import chat_stream
                for kind, text in chat_stream(llm_messages):
                    if kind == "think":
                        chunk = json.dumps({
                            "id": request_id, "object": "chat.completion.chunk",
                            "created": int(_time.time()), "model": "wenqu-v1",
                            "choices": [{"index": 0, "delta": {"reasoning_content": text}, "finish_reason": None}],
                        })
                    else:
                        chunk = json.dumps({
                            "id": request_id, "object": "chat.completion.chunk",
                            "created": int(_time.time()), "model": "wenqu-v1",
                            "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                        })
                    if await request.is_disconnected():
                        return
                    yield f"data: {chunk}\n\n"
                chunk = json.dumps({
                    "id": request_id, "object": "chat.completion.chunk",
                    "created": int(_time.time()), "model": "wenqu-v1",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                })
                yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception:
                yield "data: [DONE]\n\n"
        return StreamingResponse(sse_chat(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    try:
        from core.llm import chat
        answer = chat(llm_messages)
    except Exception as e:
        return JSONResponse({"error": {"message": str(e), "type": "api_error"}}, 500)

    return {
        "id": request_id, "object": "chat.completion", "created": int(_time.time()),
        "model": "wenqu-v1",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
        "sources": [Path(s).name for s in source_paths],
    }


@app.post("/v1/embeddings")
def api_v1_embeddings(data: dict):
    inp = data.get("input", "")
    if isinstance(inp, str):
        texts = [inp]
    elif isinstance(inp, list):
        texts = inp
    else:
        return JSONResponse({"error": {"message": "无效 input", "type": "invalid_request_error"}}, 400)
    try:
        from core.embed import embed
        embeddings = embed(texts)
        return {
            "object": "list",
            "data": [{"object": "embedding", "index": i, "embedding": emb} for i, emb in enumerate(embeddings)],
            "model": EMBED_CFG.model,
        }
    except Exception as e:
        return JSONResponse({"error": {"message": str(e), "type": "api_error"}}, 500)


# ── 静态文件 & SPA ──────────────────────────────────

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if (REACT_DIST / "index.html").is_file():
        file_path = REACT_DIST / full_path if full_path else REACT_DIST / "index.html"
        if file_path.is_file():
            content_type = {
                ".html": "text/html; charset=utf-8", ".js": "application/javascript",
                ".css": "text/css", ".svg": "image/svg+xml", ".woff2": "font/woff2",
            }.get(file_path.suffix, "application/octet-stream")
            return Response(file_path.read_bytes(), media_type=content_type)
        return FileResponse(REACT_DIST / "index.html")

    fp = STATIC_DIR / full_path if full_path else STATIC_DIR / "index.html"
    if fp.is_file():
        import mimetypes
        ct = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
        return Response(fp.read_bytes(), media_type=ct)
    return FileResponse(STATIC_DIR / "index.html")


# ── 启动自检 ────────────────────────────────────────

def _check_port(port: int) -> dict:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        s.close()
        return {"ok": True, "msg": f"端口 {port} 可用"}
    except OSError:
        who = ""
        try:
            import subprocess
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}" | findstr "LISTENING"',
                shell=True, capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                pid = result.stdout.strip().split()[-1]
                who = f" (PID: {pid})"
        except Exception:
            pass
        return {"ok": False, "msg": f"端口 {port} 已被占用{who}"}


def _check_ollama() -> dict:
    import json as _j, urllib.request as urlreq
    try:
        req = urlreq.Request("http://localhost:11434/api/tags")
        with urlreq.urlopen(req, timeout=5) as resp:
            models = _j.loads(resp.read()).get("models", [])
        names = {m["name"].split(":")[0] for m in models}
        names_tagged = {m["name"] for m in models}
        model_base = EMBED_CFG.model.split(":")[0]
        model_ok = EMBED_CFG.model in names_tagged or model_base in names
        if not model_ok:
            return {"ok": False, "msg": f"模型未安装: {EMBED_CFG.model}"}
        return {"ok": True, "msg": f"Ollama 正常，{len(names)} 个模型可用"}
    except Exception as e:
        return {"ok": False, "msg": f"Ollama 连接失败: {e}"}


def _check_data() -> dict:
    try:
        db = get_db()
        docs = db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if docs == 0:
            return {"ok": True, "msg": "知识库为空，请导入文档", "warn": True}
        orphan = db.execute(
            "SELECT COUNT(*) FROM chunks WHERE source NOT IN (SELECT path FROM sources)"
        ).fetchone()[0]
        if orphan > 0:
            return {"ok": True, "msg": f"已导入 {docs} 个文档, {chunks} 个向量块 (⚠ 发现 {orphan} 个孤儿块)", "warn": True}
        return {"ok": True, "msg": f"已导入 {docs} 个文档, {chunks} 个向量块"}
    except Exception as e:
        return {"ok": False, "msg": f"数据库检查失败: {e}"}


def _check_api_key() -> dict:
    from core.config import LLM_CFG
    if LLM_CFG.provider == "ollama":
        return {"ok": True, "msg": f"使用本地 Ollama 模型: {LLM_CFG.model}"}
    if not LLM_CFG.api_key:
        return {"ok": False, "msg": "未配置 DEEPSEEK_KEY，请在 .env 中设置。或设置 LLM_PROVIDER=ollama 使用本地模型"}
    return {"ok": True, "msg": f"使用 DeepSeek: {LLM_CFG.model}"}


def _check_windows_firewall(port: int) -> dict:
    import subprocess
    try:
        result = subprocess.run(
            f'netsh advfirewall firewall show rule name=all | findstr "知识库HTTP"',
            shell=True, capture_output=True, text=True, timeout=5
        )
        if "知识库HTTP" in result.stdout:
            return {"ok": True, "msg": "防火墙规则 '知识库HTTP' 已配置"}
        return {"ok": True, "msg": "防火墙规则未配置，局域网设备可能无法访问", "warn": True}
    except Exception:
        return {"ok": True, "msg": "跳过防火墙检查"}


def _check_docs_dir() -> dict:
    docs_dir = Path(__file__).parent / "docs"
    if not docs_dir.exists():
        return {"ok": True, "msg": "docs 目录不存在 (将自动创建)", "warn": True}
    files = list(docs_dir.glob("*"))
    supported = [f for f in files if f.suffix.lower() in {".txt", ".md", ".docx", ".pptx", ".pdf"}]
    if supported:
        return {"ok": True, "msg": f"docs 目录有 {len(supported)} 个可导入文件"}
    return {"ok": True, "msg": "docs 目录无文件", "warn": True}


def startup_diagnostics(port: int) -> bool:
    print("=" * 60)
    print("  知识库 Web 服务器 — 启动自检")
    print("=" * 60)
    checks = [
        ("LLM API Key", _check_api_key()),
        ("端口检查", _check_port(port)),
        ("Ollama 服务", _check_ollama()),
        ("数据完整性", _check_data()),
        ("文档目录", _check_docs_dir()),
        ("防火墙规则", _check_windows_firewall(port)),
    ]
    blocker = False
    for name, result in checks:
        icon = "✗" if not result["ok"] else ("⚠" if result.get("warn") else "✓")
        if not result["ok"]:
            blocker = True
        print(f"  {icon} {name}: {result['msg']}")
    print("=" * 60)
    if blocker:
        print("\n[自检失败] 请修复以上问题后重新启动。")
        return False
    print("  自检通过 ✓")
    return True


# ── 主入口 ───────────────────────────────────────────

def main():
    port = 8080

    print()
    print("  ██╗    ██╗███████╗███╗   ██╗  ██████╗ ██╗   ██╗")
    print("  ██║    ██║██╔════╝████╗  ██║ ██╔═══██╗██║   ██║")
    print("  ██║ █╗ ██║█████╗  ██╔██╗ ██║ ██║   ██║██║   ██║")
    print("  ██║███╗██║██╔══╝  ██║╚██╗██║ ██║▄▄ ██║██║   ██║")
    print("  ╚███╔███╔╝███████╗██║ ╚████║ ╚██████╔╝╚██████╔╝")
    print("   ╚══╝╚══╝ ╚══════╝╚═╝  ╚═══╝  ╚══▀▀═╝  ╚═════╝ ")
    print("         本地知识库 RAG 系统 · 问渠那得清如许")
    print()

    if not startup_diagnostics(port):
        try:
            input("\n按 Enter 退出...")
        except (EOFError, OSError):
            pass
        sys.exit(1)

    import uvicorn
    print(f"\n  服务已启动: http://localhost:{port}")
    print("  按 Ctrl+C 停止\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
