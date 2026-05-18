"""
LLM 调用层 — 支持 DeepSeek API 和 Ollama 本地模型
"""
import json
import urllib.request
from .config import LLM_CFG


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


def chat(messages: list[dict], temperature: float | None = None) -> str:
    if LLM_CFG.provider == "ollama":
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


def chat_stream(messages: list[dict]):
    """流式调用 LLM。yield ("token", text) 或 ("think", text)。"""
    if LLM_CFG.provider == "ollama":
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
            if "reasoning_content" in delta:
                yield ("think", delta["reasoning_content"])
            elif "content" in delta:
                yield ("token", delta["content"])
        except (json.JSONDecodeError, KeyError, IndexError):
            continue
