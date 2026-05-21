"""
配置管理 — 模仿 RAGFlow service_conf.yaml 外置化
所有配置项集中管理，支持环境变量覆盖
"""
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv():
    """从 .env 文件加载环境变量（仅在未设置时生效）"""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()


@dataclass
class LLMConfig:
    provider: str = "deepseek"  # "deepseek" | "ollama"
    api_key: str = ""
    api_base: str = "https://api.deepseek.com/v1"
    ollama_url: str = "http://localhost:11434"
    model: str = "deepseek-chat"
    temperature: float = 0.0
    seed: int = 42


@dataclass
class EmbedConfig:
    provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    model: str = "bge-m3"
    batch_size: int = 10


@dataclass
class VisionConfig:
    provider: str = "ollama"
    model: str = "minicpm-v:8b"


@dataclass
class RetrievalConfig:
    min_similarity: float = 0.25
    top_k: int = 10
    expand: int = 1
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    chunk_max_tokens: int = 400
    chunk_overlap: int = 50
    rrf_k: int = 60
    enable_query_rewrite: bool = False
    enable_rerank: bool = False


_ROOT = Path(__file__).parent.parent  # 项目根目录

@dataclass
class StorageConfig:
    data_dir: Path = field(default_factory=lambda: _ROOT / "data")
    docs_dir: Path = field(default_factory=lambda: _ROOT / "docs")
    log_dir: Path = field(default_factory=lambda: _ROOT / "logs")


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080


def load_config() -> tuple[LLMConfig, EmbedConfig, VisionConfig, RetrievalConfig, StorageConfig, ServerConfig]:
    """从环境变量加载配置（优先），否则使用默认值"""
    llm = LLMConfig(
        provider=os.getenv("LLM_PROVIDER", LLMConfig.provider),
        api_key=os.getenv("DEEPSEEK_KEY", LLMConfig.api_key),
        api_base=os.getenv("DEEPSEEK_BASE", LLMConfig.api_base),
        ollama_url=os.getenv("OLLAMA_URL", LLMConfig.ollama_url),
        model=os.getenv("DEEPSEEK_MODEL", LLMConfig.model),
    )
    embed = EmbedConfig(
        ollama_url=os.getenv("OLLAMA_URL", EmbedConfig.ollama_url),
        model=os.getenv("EMBED_MODEL", EmbedConfig.model),
    )
    vision = VisionConfig(
        model=os.getenv("VISION_MODEL", VisionConfig.model),
    )
    retrieval = RetrievalConfig(
        chunk_max_tokens=int(os.getenv("CHUNK_MAX_TOKENS", RetrievalConfig.chunk_max_tokens)),
        top_k=int(os.getenv("TOP_K", RetrievalConfig.top_k)),
        enable_query_rewrite=os.getenv("ENABLE_QUERY_REWRITE", "0") not in ("0", "false", "False"),
        enable_rerank=os.getenv("ENABLE_RERANK", "0") in ("1", "true", "True"),
    )
    storage = StorageConfig()
    server = ServerConfig(
        host=os.getenv("HOST", ServerConfig.host),
        port=int(os.getenv("PORT", ServerConfig.port)),
    )
    return llm, embed, vision, retrieval, storage, server


# 全局配置单例
LLM_CFG, EMBED_CFG, VISION_CFG, RETRIEVAL_CFG, STORAGE_CFG, SERVER_CFG = load_config()

# 运行时覆写（通过 /api/config 修改，服务重启后恢复默认值）
_runtime_overrides: dict = {}

def get_runtime_config() -> dict:
    return {
        "min_similarity": _runtime_overrides.get("min_similarity", RETRIEVAL_CFG.min_similarity),
        "top_k": _runtime_overrides.get("top_k", RETRIEVAL_CFG.top_k),
        "enable_query_rewrite": _runtime_overrides.get("enable_query_rewrite", RETRIEVAL_CFG.enable_query_rewrite),
        "enable_rerank": _runtime_overrides.get("enable_rerank", RETRIEVAL_CFG.enable_rerank),
    }

def apply_runtime_overrides():
    """将运行时覆写应用到全局配置"""
    if "min_similarity" in _runtime_overrides:
        RETRIEVAL_CFG.min_similarity = float(_runtime_overrides["min_similarity"])
    if "top_k" in _runtime_overrides:
        RETRIEVAL_CFG.top_k = int(_runtime_overrides["top_k"])
    if "enable_query_rewrite" in _runtime_overrides:
        RETRIEVAL_CFG.enable_query_rewrite = _runtime_overrides["enable_query_rewrite"] in (True, "1", "true", "True")
    if "enable_rerank" in _runtime_overrides:
        RETRIEVAL_CFG.enable_rerank = _runtime_overrides["enable_rerank"] in (True, "1", "true", "True")
