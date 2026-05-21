"""
LLM 调用层 — 支持 DeepSeek API 和 Ollama 本地模型
"""
import json
import threading
import urllib.request
from .config import LLM_CFG

_llm_semaphore = threading.BoundedSemaphore(10)  # 最多 10 个并发 LLM 请求


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
    with _llm_semaphore:
        return _chat(messages, temperature, provider)


def _chat(messages: list[dict], temperature: float | None = None, provider: str | None = None) -> str:
    provider = provider or LLM_CFG.provider
    if provider == "ollama":
        result = _ollama_post(
            f"{LLM_CFG.ollama_url}/api/chat",
            {
                "model": LLM_CFG.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature if temperature is not None else LLM_CFG.temperature,
                    "seed": LLM_CFG.seed,
                },
            },
        )
        return result["message"]["content"]

    result = _deepseek_post(
        f"{LLM_CFG.api_base}/chat/completions",
        {
            "model": LLM_CFG.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else LLM_CFG.temperature,
            "seed": LLM_CFG.seed,
        },
    )
    msg = result["choices"][0]["message"]
    # deepseek-reasoner 返回 reasoning_content
    return msg.get("content") or msg.get("reasoning_content") or ""


def chat_stream(messages: list[dict], provider: str | None = None):
    """流式调用 LLM。yield ("token", text) 或 ("think", text)。"""
    try:
        _llm_semaphore.acquire()
        yield from _chat_stream(messages, provider)
    finally:
        _llm_semaphore.release()


def _chat_stream(messages: list[dict], provider: str | None = None):
    provider = provider or LLM_CFG.provider
    if provider == "ollama":
        for line in _ollama_stream(
            f"{LLM_CFG.ollama_url}/api/chat",
            {
                "model": LLM_CFG.model,
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
            delta = chunk["choices"][0].get("delta", {})
            # 新模型可能不含 reasoning_content 或值为空
            rc = delta.get("reasoning_content")
            if rc:
                yield ("think", rc)
            if "content" in delta and delta["content"]:
                yield ("token", delta["content"])
        except (json.JSONDecodeError, KeyError, IndexError):
            continue
