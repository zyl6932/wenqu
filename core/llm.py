"""
LLM 调用层 — 支持 DeepSeek API 和 Ollama 本地模型
"""
import json
import threading
import urllib.request
from .config import LLM_CFG, EMBED_CFG

_llm_semaphore = threading.BoundedSemaphore(10)

_LLM_ACQUIRE_TIMEOUT = 30


def _acquire_semaphore():
    if not _llm_semaphore.acquire(timeout=_LLM_ACQUIRE_TIMEOUT):
        raise RuntimeError("LLM 并发已满，请稍后重试")

_cached_ollama_model: str | None = None


def _detect_ollama_model() -> str:
    """自动检测 Ollama 中可用的对话模型"""
    global _cached_ollama_model
    if _cached_ollama_model:
        return _cached_ollama_model
    try:
        import json, urllib.request as urlreq
        req = urlreq.Request(f"{EMBED_CFG.ollama_url}/api/tags")
        with urlreq.urlopen(req, timeout=5) as resp:
            models = json.loads(resp.read()).get("models", [])
        chat_models = [m["name"] for m in models if "embed" not in m.get("name", "").lower()]
        _cached_ollama_model = chat_models[0] if chat_models else "qwen2.5"
    except Exception:
        _cached_ollama_model = "qwen2.5"
    return _cached_ollama_model  # 最多 10 个并发 LLM 请求


def _deepseek_post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {LLM_CFG.api_key}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _deepseek_stream(url: str, data: dict):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {LLM_CFG.api_key}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            yield line


def _ollama_post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _ollama_stream(url: str, data: dict):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            yield line


def chat(messages: list[dict], temperature: float | None = None, provider: str | None = None) -> str:
    _acquire_semaphore()
    try:
        return _chat(messages, temperature, provider)
    finally:
        _llm_semaphore.release()


def _chat(messages: list[dict], temperature: float | None = None, provider: str | None = None) -> str:
    provider = provider or LLM_CFG.provider
    model = _detect_ollama_model() if provider == "ollama" else LLM_CFG.model
    if provider == "ollama":
        result = _ollama_post(
            f"{LLM_CFG.ollama_url}/api/chat",
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature if temperature is not None else LLM_CFG.temperature,
                    "seed": LLM_CFG.seed,
                },
            },
        )
        msg = result.get("message", {})
        return msg.get("content", "")

    result = _deepseek_post(
        f"{LLM_CFG.api_base}/chat/completions",
        {
            "model": LLM_CFG.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else LLM_CFG.temperature,
            "seed": LLM_CFG.seed,
        },
    )
    choices = result.get("choices", [])
    if not choices:
        return ""
    msg = choices[0].get("message", {})
    return msg.get("content") or msg.get("reasoning_content") or ""


def chat_stream(messages: list[dict], provider: str | None = None):
    """流式调用 LLM。yield ("token", text) 或 ("think", text)。"""
    _acquire_semaphore()
    try:
        yield from _chat_stream(messages, provider)
    finally:
        _llm_semaphore.release()


def _chat_stream(messages: list[dict], provider: str | None = None):
    provider = provider or LLM_CFG.provider
    model = _detect_ollama_model() if provider == "ollama" else LLM_CFG.model
    if provider == "ollama":
        for line in _ollama_stream(
            f"{LLM_CFG.ollama_url}/api/chat",
            {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": LLM_CFG.temperature,
                    "seed": LLM_CFG.seed,
                },
            },
        ):
            try:
                chunk = json.loads(line.decode("utf-8").strip())
                if "message" in chunk and "content" in chunk["message"]:
                    yield ("token", chunk["message"]["content"])
            except (json.JSONDecodeError, KeyError):
                continue
        return

    for line in _deepseek_stream(
        f"{LLM_CFG.api_base}/chat/completions",
        {
            "model": LLM_CFG.model,
            "messages": messages,
            "temperature": LLM_CFG.temperature,
            "seed": LLM_CFG.seed,
            "stream": True,
        },
    ):
        line = line.decode("utf-8").strip()
        if not line or not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
            choices = chunk.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            # 新模型可能不含 reasoning_content 或值为空
            rc = delta.get("reasoning_content")
            if rc:
                yield ("think", rc)
            if "content" in delta and delta["content"]:
                yield ("token", delta["content"])
        except (json.JSONDecodeError, KeyError, IndexError):
            continue
