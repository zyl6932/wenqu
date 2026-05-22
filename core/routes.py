"""
API 路由 — 全部 FastAPI 端点
通过 register_routes(app) 注册
"""
import asyncio
import json
import time as _time
import mimetypes
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor as _TPE

from fastapi import Request, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response

from .rag import (
    import_docs, ask_stream, get_doc_content,
    list_chunks, update_chunk, delete_chunk, delete_chunks, split_chunk, merge_chunks,
    record_feedback, build_prompt,
)
from .storage import delete_source as delete_doc
from .storage import count_sources, get_db
from .retrieve import retrieve
from .config import EMBED_CFG, get_runtime_config, _runtime_overrides, apply_runtime_overrides
from .server_utils import log_error, check_rate

STATIC_DIR = Path(__file__).parent.parent / "static"
REACT_DIST = STATIC_DIR / "dist"


def register_routes(app):
    # ── 限流中间件（线程池运行，避免阻塞事件循环）────
    _rate_executor = _TPE(max_workers=4, thread_name_prefix="rate")

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        loop = asyncio.get_running_loop()
        ok = await loop.run_in_executor(_rate_executor, check_rate, client_ip)
        if not ok:
            return JSONResponse({"error": "请求过于频繁"}, status_code=429)
        return await call_next(request)

    # ── 基础 ───────────────────────────────────────
    @app.get("/api/health")
    async def api_health():
        return {"status": "ok"}

    @app.get("/api/health/full")
    async def api_health_full():
        from .server_utils import _check_port, _check_ollama, _check_data
        return {"status": "ok", "port": _check_port(8080), "ollama": _check_ollama(), "data": _check_data()}

    # ── 配置 ───────────────────────────────────────
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
            from .retrieve import clear_cache
            clear_cache()
        return {"config": get_runtime_config(), "message": "已更新" if changed else "无变更"}

    # ── 文档 ───────────────────────────────────────
    @app.get("/api/docs")
    async def api_list_docs(page: int = 1, page_size: int = 50):
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        offset = (page - 1) * page_size
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        rows = db.execute(
            "SELECT path, added_at FROM sources ORDER BY added_at DESC LIMIT ? OFFSET ?",
            (page_size, offset)).fetchall()
        docs = [{"path": r[0], "name": Path(r[0]).name, "added_at": r[1]} for r in rows]
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
        from .retrieve import clear_cache
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

    # ── 向量块 ─────────────────────────────────────
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

    # ── 问答 ───────────────────────────────────────
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
        from .llm import chat
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
            isinstance(m, dict) and "role" in m and "content" in m for m in history)):
            history = None

        async def sse_generate():
            loop = asyncio.get_running_loop()
            queue = asyncio.Queue(maxsize=64)
            cancelled = threading.Event()

            def produce():
                try:
                    for event_type, payload in ask_stream(question, history=history, llm_provider=llm_provider):
                        if cancelled.is_set():
                            return
                        loop.call_soon_threadsafe(queue.put_nowait, (event_type, payload))
                except Exception as e:
                    if not cancelled.is_set():
                        loop.call_soon_threadsafe(queue.put_nowait, ('error', str(e)))
                if not cancelled.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            future = loop.run_in_executor(None, produce)
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    event_type, payload = item
                    line = json.dumps({event_type: payload}, ensure_ascii=False)
                    yield f"data: {line}\n\n"
            finally:
                cancelled.set()
                try:
                    await asyncio.wait_for(future, timeout=5)
                except (asyncio.TimeoutError, Exception):
                    pass

        return StreamingResponse(sse_generate(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "close"})

    # ── 导入/上传 ──────────────────────────────────
    @app.post("/api/import")
    def api_import():
        log_lines = []
        import_docs(on_log=log_lines.append)
        return {"message": "\n".join(log_lines) or "导入完成"}

    @app.post("/api/upload")
    def api_upload(file: UploadFile = File(...), request=None, background_tasks=None):
        if not file.filename:
            raise HTTPException(400, "无文件")
        if request:
            cl = request.headers.get("content-length")
            if cl and int(cl) > 100 * 1024 * 1024:
                raise HTTPException(413, "文件大小不能超过 100MB")
        docs_dir = Path(__file__).parent.parent / "docs"
        docs_dir.mkdir(exist_ok=True)
        save_path = docs_dir / Path(file.filename).name
        with open(save_path, 'wb') as f:
            while chunk := file.file.read(1 << 20):
                f.write(chunk)
        if background_tasks:
            background_tasks.add_task(_import_bg)
        else:
            import_docs()
            from .retrieve import clear_cache
            clear_cache()
        return {"message": f"已上传 {file.filename}，后台导入中", "status": "importing"}

    # ── 标题 / 反馈 ────────────────────────────────
    @app.post("/api/title")
    def api_gen_title(data: dict):
        question = data.get("question", "").strip()
        if not question:
            raise HTTPException(400, "问题不能为空")
        try:
            from .llm import chat
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

    # ── OpenAI 兼容 ─────────────────────────────────
    @app.get("/v1/models")
    @app.post("/v1/models")
    async def api_v1_models():
        return {"object": "list", "data": [{"id": "wenqu-v1", "object": "model", "owned_by": "wenqu"}]}

    @app.post("/v1/chat/completions")
    async def api_v1_chat_completions(data: dict, request: Request):
        messages = data.get("messages", [])
        if not messages:
            return JSONResponse({"error": {"message": "缺少 messages", "type": "invalid_request_error"}}, 400)
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break
        if not user_msg:
            return JSONResponse({"error": {"message": "需要用户消息", "type": "invalid_request_error"}}, 400)

        result = retrieve(user_msg)
        request_id = f"chatcmpl-{hash(user_msg) % 10**9:09d}"
        if result is None:
            msg = "知识库为空，请先导入文档。"
            if data.get("stream"):
                async def empty_stream():
                    chunk = json.dumps({"id": request_id, "object": "chat.completion.chunk",
                                        "created": int(_time.time()), "model": "wenqu-v1",
                                        "choices": [{"index": 0, "delta": {"content": msg}, "finish_reason": "stop"}]})
                    yield f"data: {chunk}\n\ndata: [DONE]\n\n"
                return StreamingResponse(empty_stream(), media_type="text/event-stream",
                                         headers={"Cache-Control": "no-cache"})
            return {"choices": [{"index": 0, "message": {"role": "assistant", "content": msg}, "finish_reason": "stop"}]}

        contexts, source_paths = result
        prompt = build_prompt(contexts, user_msg)
        system_msg = {"role": "system", "content": "你是一个严谨的知识库助手，仅根据提供的参考内容回答问题。"}
        llm_messages = [system_msg] + messages[:-1] + [{"role": "user", "content": prompt}]

        if data.get("stream"):
            async def sse_chat():
                loop = asyncio.get_running_loop()
                queue = asyncio.Queue(maxsize=64)
                cancelled = threading.Event()

                def produce():
                    try:
                        from .llm import chat_stream
                        for kind, text in chat_stream(llm_messages):
                            if cancelled.is_set():
                                return
                            loop.call_soon_threadsafe(queue.put_nowait, (kind, text))
                    except Exception:
                        pass
                    if not cancelled.is_set():
                        loop.call_soon_threadsafe(queue.put_nowait, None)

                future = loop.run_in_executor(None, produce)
                try:
                    while True:
                        item = await queue.get()
                        if item is None:
                            break
                        kind, text = item
                        if kind == "usage":
                            continue
                        if kind == "think":
                            chunk = json.dumps({"id": request_id, "object": "chat.completion.chunk",
                                                "created": int(_time.time()), "model": "wenqu-v1",
                                                "choices": [{"index": 0, "delta": {"reasoning_content": text}, "finish_reason": None}]})
                        else:
                            chunk = json.dumps({"id": request_id, "object": "chat.completion.chunk",
                                                "created": int(_time.time()), "model": "wenqu-v1",
                                                "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]})
                        if await request.is_disconnected():
                            return
                        yield f"data: {chunk}\n\n"
                    chunk = json.dumps({"id": request_id, "object": "chat.completion.chunk",
                                        "created": int(_time.time()), "model": "wenqu-v1",
                                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
                    yield f"data: {chunk}\n\ndata: [DONE]\n\n"
                finally:
                    cancelled.set()
                    try:
                        await asyncio.wait_for(future, timeout=5)
                    except (asyncio.TimeoutError, Exception):
                        pass
            return StreamingResponse(sse_chat(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache"})

        try:
            from .llm import chat
            answer = chat(llm_messages)
        except Exception as e:
            return JSONResponse({"error": {"message": str(e), "type": "api_error"}}, 500)
        return {"id": request_id, "object": "chat.completion", "created": int(_time.time()), "model": "wenqu-v1",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
                "sources": [Path(s).name for s in source_paths]}

    @app.post("/v1/embeddings")
    def api_v1_embeddings(data: dict):
        inp = data.get("input", "")
        texts = [inp] if isinstance(inp, str) else (inp if isinstance(inp, list) else [])
        if not texts:
            return JSONResponse({"error": {"message": "无效 input", "type": "invalid_request_error"}}, 400)
        try:
            from .embed import embed
            embeddings = embed(texts)
            return {"object": "list", "data": [{"object": "embedding", "index": i, "embedding": emb}
                     for i, emb in enumerate(embeddings)], "model": EMBED_CFG.model}
        except Exception as e:
            return JSONResponse({"error": {"message": str(e), "type": "api_error"}}, 500)

    # ── 静态文件 & SPA ──────────────────────────────
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if (REACT_DIST / "index.html").is_file():
            fp = REACT_DIST / full_path if full_path else REACT_DIST / "index.html"
            if fp.is_file():
                ct = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
                      ".css": "text/css", ".svg": "image/svg+xml", ".woff2": "font/woff2"}.get(fp.suffix, "application/octet-stream")
                return Response(fp.read_bytes(), media_type=ct)
            return FileResponse(REACT_DIST / "index.html")
        fp = STATIC_DIR / full_path if full_path else STATIC_DIR / "index.html"
        if fp.is_file():
            ct = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
            return Response(fp.read_bytes(), media_type=ct)
        return FileResponse(STATIC_DIR / "index.html")


def _import_bg():
    """后台导入任务"""
    try:
        import_docs()
        from .retrieve import clear_cache
        clear_cache()
    except Exception:
        pass
