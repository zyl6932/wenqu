"""
结构化日志系统 — 级别/轮转/格式
"""
import datetime
import threading
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}
_LEVEL = LOG_LEVELS["INFO"]
_lock = threading.Lock()


def set_level(level: str):
    global _LEVEL
    _LEVEL = LOG_LEVELS.get(level.upper(), 20)


def _log(level: str, msg: str, **kwargs):
    if LOG_LEVELS.get(level, 20) < _LEVEL:
        return
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
    line = f"[{ts}] [{level:<5}] {msg}"
    if extra:
        line += " | " + extra
    print(line)

    # 写入文件
    if level in ("WARN", "ERROR"):
        try:
            with _lock:
                log_file = LOG_DIR / f"server-{datetime.date.today():%Y-%m-%d}.log"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            pass


def debug(msg: str, **kwargs): _log("DEBUG", msg, **kwargs)
def info(msg: str, **kwargs): _log("INFO", msg, **kwargs)
def warn(msg: str, **kwargs): _log("WARN", msg, **kwargs)
def error(msg: str, **kwargs): _log("ERROR", msg, **kwargs)
