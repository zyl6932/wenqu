"""
服务器辅助函数 — 日志、限流、启动自检
"""
import json
import socket
import subprocess
import sys
import threading
import time as _time
from pathlib import Path

from .config import EMBED_CFG, LLM_CFG
from .storage import get_db

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
except Exception:
    pass

# ── 错误日志 ──────────────────────────────────────────
LOG_DIR = Path(__file__).parent.parent / "logs"
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


# ── 请求速率限制 ────────────────────────────────────
_request_counts: dict[str, list[float]] = {}
_request_lock = threading.Lock()


def check_rate(client_ip: str) -> bool:
    now = _time.time()
    with _request_lock:
        times = _request_counts.get(client_ip, [])
        times = [t for t in times if now - t < 1.0]
        if len(times) >= 10:
            _request_counts[client_ip] = times
            return False
        times.append(now)
        _request_counts[client_ip] = times
        if len(_request_counts) > 5000:
            stale = [ip for ip, ts in _request_counts.items()
                     if not ts or (isinstance(ts, list) and ts and ts[-1] < now - 60)]
            for ip in stale:
                del _request_counts[ip]
        return True


# ── 启动自检 ────────────────────────────────────────

def _check_port(port: int) -> dict:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        s.close()
        return {"ok": True, "msg": f"端口 {port} 可用"}
    except OSError:
        who = ""
        try:
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}" | findstr "LISTENING"',
                shell=True, capture_output=True, text=True, timeout=5)
            if result.stdout.strip():
                pid = result.stdout.strip().split()[-1]
                who = f" (PID: {pid})"
        except Exception:
            pass
        return {"ok": False, "msg": f"端口 {port} 已被占用{who}"}


def _check_ollama() -> dict:
    import urllib.request as urlreq
    try:
        req = urlreq.Request("http://localhost:11434/api/tags")
        with urlreq.urlopen(req, timeout=5) as resp:
            models = json.loads(resp.read()).get("models", [])
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
            "SELECT COUNT(*) FROM chunks WHERE source NOT IN (SELECT path FROM sources)").fetchone()[0]
        if orphan > 0:
            return {"ok": True, "msg": f"已导入 {docs} 个文档, {chunks} 个向量块 (⚠ 发现 {orphan} 个孤儿块)", "warn": True}
        return {"ok": True, "msg": f"已导入 {docs} 个文档, {chunks} 个向量块"}
    except Exception as e:
        return {"ok": False, "msg": f"数据库检查失败: {e}"}


def _check_api_key() -> dict:
    if LLM_CFG.provider == "ollama":
        return {"ok": True, "msg": f"使用本地 Ollama 模型: {LLM_CFG.model}"}
    if not LLM_CFG.api_key:
        return {"ok": False, "msg": "未配置 DEEPSEEK_KEY，请在 .env 中设置。或设置 LLM_PROVIDER=ollama 使用本地模型"}
    return {"ok": True, "msg": f"使用 DeepSeek: {LLM_CFG.model}"}


def _check_windows_firewall(port: int) -> dict:
    try:
        result = subprocess.run(
            f'netsh advfirewall firewall show rule name=all | findstr "知识库HTTP"',
            shell=True, capture_output=True, text=True, timeout=5)
        if "知识库HTTP" in result.stdout:
            return {"ok": True, "msg": "防火墙规则 '知识库HTTP' 已配置"}
        return {"ok": True, "msg": "防火墙规则未配置，局域网设备可能无法访问", "warn": True}
    except Exception:
        return {"ok": True, "msg": "跳过防火墙检查"}


def _check_docs_dir() -> dict:
    docs_dir = Path(__file__).parent.parent / "docs"
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
