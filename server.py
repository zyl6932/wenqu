"""
本地知识库 Web 服务器 — 纯 Python 内置库，零外部依赖
启动: python server.py
访问: http://localhost:8080
"""
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

MAX_WORKERS = 32  # 线程池上限


class ThreadingHTTPServer(HTTPServer):
    """线程池 HTTP 服务器，有界并发，避免线程爆炸。"""
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        self._executor.submit(self.process_request_thread, request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

# 错误日志
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

def log_error(msg: str):
    """记录错误到日志文件。"""
    import datetime
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = LOG_DIR / f"error-{datetime.date.today().isoformat()}.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── 请求计数器 ─────────────────────────────────────────
import threading
import time as _time

_request_counts: dict[str, list[float]] = {}
_request_lock = threading.Lock()


def _track_request(client_ip: str) -> bool:
    """简单限流：每 IP 每秒最多 10 请求。返回 True 表示放行。"""
    now = _time.time()
    with _request_lock:
        times = _request_counts.get(client_ip, [])
        # 清理过期记录
        times = [t for t in times if now - t < 1.0]
        if len(times) >= 10:
            _request_counts[client_ip] = times
            return False
        times.append(now)
        _request_counts[client_ip] = times
        return True

from core.rag import (
    import_docs, ask_stream, get_doc_content,
    list_chunks, update_chunk, delete_chunk, delete_chunks, split_chunk, merge_chunks,
    record_feedback, build_prompt,
)
from core.storage import delete_source as delete_doc
from core.storage import count_sources, get_db
from core.retrieve import retrieve
from core.config import EMBED_CFG, SERVER_CFG, get_runtime_config, _runtime_overrides, apply_runtime_overrides

STATIC_DIR = Path(__file__).parent / "static"
REACT_DIST = STATIC_DIR / "dist"


class APIHandler(SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/docs":
            self._handle_list_docs()
        elif path == "/api/docs/content":
            self._handle_doc_content()
        elif path == "/api/chunks":
            self._handle_list_chunks()
        elif path == "/api/config":
            self._json(get_runtime_config())
        elif path == "/api/health":
            self._json({"status": "ok"})
        elif path == "/api/health/full":
            self._json({
                "status": "ok",
                "port": _check_port(8080),
                "ollama": _check_ollama(),
                "data": _check_data(),
            })
        elif path == "/v1/models":
            self._handle_v1_models()
        elif path.startswith("/api/"):
            self._json({"error": "未知接口"}, 404)
        else:
            self._serve_static()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/ask":
            self._handle_ask()
        elif path == "/api/ask/stream":
            self._handle_ask_stream()
        elif path == "/v1/chat/completions":
            self._handle_chat_completions()
        elif path == "/v1/embeddings":
            self._handle_v1_embeddings()
        elif path == "/v1/models":
            self._handle_v1_models()
        elif path == "/api/import":
            self._handle_import()
        elif path == "/api/chunks/split":
            self._handle_split_chunk()
        elif path == "/api/chunks/merge":
            self._handle_merge_chunks()
        elif path == "/api/title":
            self._handle_gen_title()
        elif path == "/api/config":
            self._handle_config_update()
        elif path == "/api/feedback":
            self._handle_feedback()
        elif path == "/api/upload":
            self._handle_upload()
        else:
            self._json({"error": "未知接口"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path
        if path == "/api/chunks":
            self._handle_update_chunk()
        else:
            self._json({"error": "未知接口"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == "/api/docs":
            self._handle_delete_doc()
        elif path == "/api/chunks":
            self._handle_delete_chunks()
        else:
            self._json({"error": "未知接口"}, 404)

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")

    def _serve_static(self):
        url_path = urlparse(self.path).path
        if url_path == "/" or url_path == "":
            url_path = "/index.html"

        # 如果 React 构建存在，优先提供 dist/ 内容
        if (REACT_DIST / "index.html").is_file():
            base_dir = REACT_DIST
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".js": "application/javascript",
                ".css": "text/css",
                ".svg": "image/svg+xml",
                ".woff2": "font/woff2",
            }
        else:
            base_dir = STATIC_DIR
            content_types = {
                ".html": "text/html; charset=utf-8",
                ".js": "application/javascript",
                ".css": "text/css",
                ".svg": "image/svg+xml",
            }

        file_path = base_dir / url_path.lstrip("/")
        if not file_path.is_file():
            if base_dir == REACT_DIST:
                # SPA fallback: 非文件路径返回 index.html
                file_path = REACT_DIST / "index.html"
            else:
                file_path = STATIC_DIR / "index.html"
        if not file_path.is_file():
            self.send_error(404)
            return

        content_type = content_types.get(file_path.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self._send_cors()
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    # ── 问答 ─────────────────────────────────────────────

    def _handle_ask(self):
        data = self._read_body()
        question = data.get("question", "").strip()
        if not question:
            self._json({"error": "问题不能为空"}, 400)
            return

        result = retrieve(question)
        if result is None:
            self._json({"answer": "未找到相关内容", "sources": []})
            return

        contexts, source_paths = result
        from core.rag import build_prompt
        from core.llm import chat
        prompt = build_prompt(contexts, question)
        answer = chat([{"role": "system", "content": "你是严谨的知识库助手。"}, {"role": "user", "content": prompt}])
        self._json({"answer": answer, "sources": [Path(s).name for s in source_paths]})

    def _handle_ask_stream(self):
        data = self._read_body()
        question = data.get("question", "").strip()
        if not question:
            self._json({"error": "问题不能为空"}, 400)
            return

        llm_provider = data.get("llm_provider", None)
        history = data.get("history", None)
        # 验证 history 格式
        if history is not None and (not isinstance(history, list) or not all(
            isinstance(m, dict) and "role" in m and "content" in m for m in history
        )):
            history = None

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._send_cors()
        self.end_headers()

        try:
            for event_type, payload in ask_stream(question, history=history, llm_provider=llm_provider):
                try:
                    line = json.dumps({event_type: payload}, ensure_ascii=False)
                    self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    # 客户端已断开（刷新/关闭页面），停止生成，释放 LLM 资源
                    return
        except Exception as e:
            try:
                err = json.dumps({"error": str(e)}, ensure_ascii=False)
                self.wfile.write(f"data: {err}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                pass

    # ── 导入 ─────────────────────────────────────────────

    def _handle_import(self):
        log_lines = []
        import_docs(on_log=log_lines.append)
        self._json({"message": "
".join(log_lines) or "导入完成"})

    # ── 文档管理 ─────────────────────────────────────────

    def _handle_list_docs(self):
        params = parse_qs(urlparse(self.path).query)
        page = max(1, int(params.get("page", ["1"])[0]))
        page_size = min(100, max(1, int(params.get("page_size", ["50"])[0])))
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
        self._json({"docs": docs, "total": total, "page": page, "page_size": page_size})

    def _handle_delete_doc(self):
        data = self._read_body()
        path = data.get("path", "").strip()
        if not path:
            self._json({"error": "缺少 path 参数"}, 400)
            return
        try:
            delete_doc(path)
            self._json({"message": f"已删除 {Path(path).name}"})
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_doc_content(self):
        params = parse_qs(urlparse(self.path).query)
        path = params.get("path", [""])[0]
        if not path:
            self._json({"error": "缺少 path 参数"}, 400)
            return
        try:
            content = get_doc_content(path)
            self._json({"path": path, "name": Path(path).name, "content": content})
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    # ── 向量块管理 ─────────────────────────────────────

    def _handle_list_chunks(self):
        params = parse_qs(urlparse(self.path).query)
        source = params.get("source", [None])[0]
        page = max(1, int(params.get("page", ["1"])[0]))
        page_size = min(100, max(1, int(params.get("page_size", ["50"])[0])))
        try:
            chunks, total = list_chunks(source, page=page, page_size=page_size)
            self._json({"chunks": chunks, "total": total, "page": page, "page_size": page_size})
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_update_chunk(self):
        data = self._read_body()
        chunk_id = data.get("id")
        text = data.get("text", "")
        if not chunk_id:
            self._json({"error": "缺少 id"}, 400)
            return
        try:
            update_chunk(int(chunk_id), text)
            self._json({"message": "已更新"})
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_delete_chunks(self):
        data = self._read_body()
        chunk_id = data.get("id")
        chunk_ids = data.get("ids")
        try:
            if chunk_ids:
                delete_chunks([int(c) for c in chunk_ids])
                self._json({"message": f"已删除 {len(chunk_ids)} 块"})
            elif chunk_id:
                delete_chunk(int(chunk_id))
                self._json({"message": "已删除"})
            else:
                self._json({"error": "缺少 id 或 ids"}, 400)
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_split_chunk(self):
        data = self._read_body()
        chunk_id = data.get("id")
        separator = data.get("separator", "")
        if not chunk_id or not separator:
            self._json({"error": "缺少 id 或 separator"}, 400)
            return
        try:
            new_ids = split_chunk(int(chunk_id), separator)
            self._json({"message": f"已拆分为 {len(new_ids)} 块", "ids": new_ids})
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_merge_chunks(self):
        data = self._read_body()
        chunk_ids = data.get("ids", [])
        if len(chunk_ids) < 2:
            self._json({"error": "至少选择两块"}, 400)
            return
        try:
            new_id = merge_chunks([int(c) for c in chunk_ids])
            self._json({"message": "已合并", "id": new_id})
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    # ── OpenAI 兼容端点 ─────────────────────────────

    def _handle_chat_completions(self):
        """OpenAI /v1/chat/completions 兼容接口（支持 stream 和非 stream）"""
        data = self._read_body()
        messages = data.get("messages", [])
        if not messages:
            self._json({"error": {"message": "缺少 messages", "type": "invalid_request_error"}}, 400)
            return

        # 提取最后一条用户消息
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break
        if not user_msg:
            self._json({"error": {"message": "需要用户消息", "type": "invalid_request_error"}}, 400)
            return

        import time as _time

        # RAG 检索
        result = retrieve(user_msg)
        if result is None:
            if data.get("stream"):
                self._send_sse()
                self._sse_chunk({
                    "id": f"chatcmpl-{hash(user_msg) % 10**9:09d}",
                    "object": "chat.completion.chunk",
                    "created": int(_time.time()),
                    "model": "wenqu-v1",
                    "choices": [{"index": 0, "delta": {"content": "知识库为空，请先导入文档。"}, "finish_reason": "stop"}],
                })
                self._sse_done()
            else:
                self._json({
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": "知识库为空，请先导入文档。"},
                        "finish_reason": "stop"
                    }]
                })
            return

        contexts, source_paths = result
        prompt = build_prompt(contexts, user_msg)

        system_msg = {"role": "system", "content": "你是一个严谨的知识库助手，仅根据提供的参考内容回答问题。"}
        llm_messages = [system_msg] + messages[:-1] + [{"role": "user", "content": prompt}]
        request_id = f"chatcmpl-{hash(user_msg) % 10**9:09d}"

        if data.get("stream"):
            self._send_sse()
            try:
                from core.llm import chat_stream
                for kind, text in chat_stream(llm_messages):
                    if kind == "think":
                        if not self._sse_chunk({
                            "id": request_id,
                            "object": "chat.completion.chunk",
                            "created": int(_time.time()),
                            "model": "wenqu-v1",
                            "choices": [{"index": 0, "delta": {"reasoning_content": text}, "finish_reason": None}],
                        }): return
                    else:
                        if not self._sse_chunk({
                            "id": request_id,
                            "object": "chat.completion.chunk",
                            "created": int(_time.time()),
                            "model": "wenqu-v1",
                            "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
                        }): return
                self._sse_chunk({
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": int(_time.time()),
                    "model": "wenqu-v1",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                })
                self._sse_done()
            except Exception:
                self._sse_done()
            return

        try:
            from core.llm import chat
            answer = chat(llm_messages)
        except Exception as e:
            self._json({"error": {"message": str(e), "type": "api_error"}}, 500)
            return

        self._json({
            "id": request_id,
            "object": "chat.completion",
            "created": int(_time.time()),
            "model": "wenqu-v1",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop"
            }],
            "sources": [Path(s).name for s in source_paths],
        })

    def _send_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._send_cors()
        self.end_headers()

    def _sse_chunk(self, data: dict):
        try:
            self.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def _sse_done(self):
        try:
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _handle_v1_embeddings(self):
        """OpenAI /v1/embeddings 兼容接口"""
        data = self._read_body()
        inp = data.get("input", "")
        if isinstance(inp, str):
            texts = [inp]
        elif isinstance(inp, list):
            texts = inp
        else:
            self._json({"error": {"message": "无效 input", "type": "invalid_request_error"}}, 400)
            return
        try:
            from core.embed import embed
            embeddings = embed(texts)
            self._json({
                "object": "list",
                "data": [
                    {"object": "embedding", "index": i, "embedding": emb}
                    for i, emb in enumerate(embeddings)
                ],
                "model": EMBED_CFG.model,
            })
        except Exception as e:
            self._json({"error": {"message": str(e), "type": "api_error"}}, 500)

    def _handle_v1_models(self):
        """OpenAI /v1/models 兼容接口"""
        self._json({
            "object": "list",
            "data": [
                {"id": "wenqu-v1", "object": "model", "owned_by": "wenqu"},
            ]
        })

    def _handle_gen_title(self):
        data = self._read_body()
        question = data.get("question", "").strip()
        if not question:
            self._json({"error": "问题不能为空"}, 400)
            return
        try:
            from core.llm import chat
            prompt = f"为以下用户问题生成一个简洁的对话标题（最多15字，不要引号，直接输出标题文本）：\n\n{question}"
            title = chat([{"role": "user", "content": prompt}])
            title = title.strip().strip('"').strip("'").strip()[:20]
            self._json({"title": title or question[:15]})
        except Exception as e:
            self._json({"title": question[:15]})

    def _handle_config_update(self):
        data = self._read_body()
        changed = False
        for key in ("min_similarity", "top_k", "enable_query_rewrite"):
            if key in data:
                _runtime_overrides[key] = data[key]
                changed = True
        if changed:
            apply_runtime_overrides()
            from core.retrieve import clear_cache
            clear_cache()
        self._json({"config": get_runtime_config(), "message": "已更新" if changed else "无变更"})

    def _handle_feedback(self):
        data = self._read_body()
        question = data.get("question", "")
        contexts = data.get("contexts", [])
        helpful = data.get("helpful", True)
        if not question or not contexts:
            self._json({"error": "缺少 question 或 contexts"}, 400)
            return
        try:
            record_feedback(question, contexts, helpful)
            self._json({"message": "反馈已记录"})
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_upload(self):
        """处理文件上传，保存到 docs 目录并导入。"""
        import cgi
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self._json({"error": "需要 multipart/form-data"}, 400)
            return
        try:
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD': 'POST'})
            file_item = form['file']
            if not file_item.filename:
                self._json({"error": "无文件"}, 400)
                return
            docs_dir = Path(__file__).parent / "docs"
            docs_dir.mkdir(exist_ok=True)
            save_path = docs_dir / Path(file_item.filename).name
            with open(save_path, 'wb') as f:
                f.write(file_item.file.read())
            # 触发导入
            from core.rag import import_docs
            import_docs()
            self._json({"message": f"已上传并导入 {file_item.filename}"})
        except Exception as e:
            log_error(f"{self.command} {self.path}: {e}")
            self._json({"error": str(e)}, 500)


# ── 兜底机制：启动自检 ──────────────────────────────────
def _check_api_key() -> dict:
    """检查 LLM API Key 是否已配置。"""
    from core.config import LLM_CFG
    if LLM_CFG.provider == "ollama":
        return {"ok": True, "msg": f"使用本地 Ollama 模型: {LLM_CFG.model}"}
    if not LLM_CFG.api_key:
        return {"ok": False, "msg": "未配置 DEEPSEEK_KEY，请在 .env 中设置。或设置 LLM_PROVIDER=ollama 使用本地模型"}
    return {"ok": True, "msg": f"使用 DeepSeek: {LLM_CFG.model}"}

def _check_port(port: int) -> dict:
    """检查端口是否被占用。"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        s.close()
        return {"ok": True, "msg": f"端口 {port} 可用"}
    except OSError:
        # 端口被占用，查出是谁在用
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
    s.close()


def _check_ollama() -> dict:
    """检查 Ollama 是否运行且模型可用。"""
    import json, urllib.request as urlreq
    try:
        req = urlreq.Request("http://localhost:11434/api/tags")
        with urlreq.urlopen(req, timeout=5) as resp:
            models = json.loads(resp.read()).get("models", [])
        names = {m["name"].split(":")[0] for m in models}
        names_tagged = {m["name"] for m in models}
        model_base = EMBED_CFG.model.split(":")[0]
        model_ok = EMBED_CFG.model in names_tagged or model_base in names
        checks = []
        checks.append({"model": EMBED_CFG.model, "ok": model_ok})
        missing = [c for c in checks if not c["ok"]]
        if missing:
            missing_names = ", ".join(c["model"] for c in missing)
            return {"ok": False, "msg": f"模型未安装: {missing_names}"}
        return {"ok": True, "msg": f"Ollama 正常，{len(names)} 个模型可用"}
    except Exception as e:
        return {"ok": False, "msg": f"Ollama 连接失败: {e}"}


def _check_data() -> dict:
    """检查知识库数据完整性。"""
    try:
        from core.storage import get_db as _sdb
        db = _sdb()
        docs = db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        chunks = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if docs == 0:
            return {"ok": True, "msg": "知识库为空，请导入文档", "warn": True}
        # 检查是否有孤儿 chunk
        orphan = db.execute(
            "SELECT COUNT(*) FROM chunks WHERE source NOT IN (SELECT path FROM sources)"
        ).fetchone()[0]
        if orphan > 0:
            return {"ok": True, "msg": f"已导入 {docs} 个文档, {chunks} 个向量块 (⚠ 发现 {orphan} 个孤儿块)", "warn": True}
        return {"ok": True, "msg": f"已导入 {docs} 个文档, {chunks} 个向量块"}
    except Exception as e:
        return {"ok": False, "msg": f"数据库检查失败: {e}"}


def _check_windows_firewall(port: int) -> dict:
    """检查 Windows 防火墙是否允许指定端口。"""
    import subprocess
    try:
        result = subprocess.run(
            f'netsh advfirewall firewall show rule name=all | findstr "知识库HTTP"',
            shell=True, capture_output=True, text=True, timeout=5
        )
        if "知识库HTTP" in result.stdout:
            return {"ok": True, "msg": f"防火墙规则 '知识库HTTP' 已配置"}
        else:
            return {"ok": True, "msg": "防火墙规则未配置，局域网设备可能无法访问", "warn": True}
    except Exception:
        # 非 Windows 或权限不足，跳过
        return {"ok": True, "msg": "跳过防火墙检查"}


def _check_docs_dir() -> dict:
    """检查 docs 目录是否存在且有文件。"""
    docs_dir = Path(__file__).parent / "docs"
    if not docs_dir.exists():
        return {"ok": True, "msg": "docs 目录不存在 (将自动创建)", "warn": True}
    files = list(docs_dir.glob("*"))
    supported = [f for f in files if f.suffix.lower() in {".txt", ".md", ".docx", ".pptx", ".pdf"}]
    if supported:
        return {"ok": True, "msg": f"docs 目录有 {len(supported)} 个可导入文件"}
    return {"ok": True, "msg": "docs 目录无文件", "warn": True}


def startup_diagnostics(port: int) -> bool:
    """启动前全面自检，返回 True 表示可以安全启动。"""
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

    all_ok = True
    blocker = False

    for name, result in checks:
        icon = ""
        if not result["ok"]:
            icon = "✗"
            blocker = True
        elif result.get("warn"):
            icon = "⚠"
        else:
            icon = "✓"
        print(f"  {icon} {name}: {result['msg']}")

    print("=" * 60)

    if blocker:
        print("\n[自检失败] 请修复以上问题后重新启动。")
        print("常见修复方法:")
        print("  端口被占用: netstat -ano | findstr :8080 然后 taskkill /PID xxx /F")
        print("  Ollama 连接失败: 运行 ollama serve 或检查是否安装")
        print("  模型未安装: ollama pull bge-m3")
        return False
    else:
        print("  自检通过 ✓")
        return True


def main():
    port = 8080

    # 启动 banner
    print()
    print("  ██╗    ██╗███████╗███╗   ██╗  ██████╗ ██╗   ██╗")
    print("  ██║    ██║██╔════╝████╗  ██║ ██╔═══██╗██║   ██║")
    print("  ██║ █╗ ██║█████╗  ██╔██╗ ██║ ██║   ██║██║   ██║")
    print("  ██║███╗██║██╔══╝  ██║╚██╗██║ ██║▄▄ ██║██║   ██║")
    print("  ╚███╔███╔╝███████╗██║ ╚████║ ╚██████╔╝╚██████╔╝")
    print("   ╚══╝╚══╝ ╚══════╝╚═╝  ╚═══╝  ╚══▀▀═╝  ╚═════╝ ")
    print("         本地知识库 RAG 系统 · 问渠那得清如许")
    print()

    # 启动前自检
    if not startup_diagnostics(port):
        try: input("\n按 Enter 退出...")
        except (EOFError, OSError): pass
        sys.exit(1)

    server = ThreadingHTTPServer(("0.0.0.0", port), APIHandler)
    print(f"\n  服务已启动: http://localhost:{port}")
    print("  按 Ctrl+C 停止\n")

    # 优雅关闭
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        server.shutdown()
        print("服务器已安全停止")


if __name__ == "__main__":
    main()
