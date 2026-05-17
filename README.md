# Wenqu (问渠)

A local knowledge base RAG Q&A system. Pure Python with zero-dependency core, using Ollama for embeddings and DeepSeek API or Ollama for LLM inference.

> The name comes from Zhu Xi's poem: "问渠那得清如许，为有源头活水来" — the pond stays clear because fresh water keeps flowing from the source.

## Features

- **Document parsing** — txt / md / docx / pptx / pdf / images, with auto chunking, dedup, and summarization
- **Hybrid retrieval** — Ollama + bge-m3 embeddings, combined with BM25 + RRF fusion ranking
- **Streaming Q&A** — SSE streaming responses, multi-turn conversations, auto-completion and correction
- **OpenAI-compatible** — `/v1/chat/completions`, `/v1/embeddings`, `/v1/models` — drop-in with any OpenAI SDK
- **Web UI** — built-in interface with dark/light theme, conversation management, chunk editor, drag-and-drop upload
- **Zero-dependency core** — core modules use only Python standard library; `pypdf` is optional

## Quick start

### Prerequisites

- Python >= 3.10
- [Ollama](https://ollama.com) running with the `bge-m3` model

```bash
# Install Ollama and pull the embedding model
ollama pull bge-m3
# (Optional) Vision model for image-based PDF extraction
ollama pull minicpm-v:8b
```

### Install & Run

```bash
# Clone
git clone https://github.com/zyl6932/wenqu.git
cd wenqu

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env:
#   - For DeepSeek API: set DEEPSEEK_KEY
#   - For fully offline mode: set LLM_PROVIDER=ollama (requires ollama pull qwen2.5 first)

# Add documents to docs/
# Place your .txt, .md, .docx, .pdf files in the docs/ directory

# Start
python server.py
```

Open `http://localhost:8080` in your browser, then click **+ 导入文档** to index your documents and start asking questions.

### Docker (CPU only)

```bash
docker build -t wenqu .
# Linux / macOS
docker run -p 8080:8080 -v $(pwd)/docs:/app/docs -v $(pwd)/data:/app/data wenqu
# Windows PowerShell
docker run -p 8080:8080 -v ${PWD}/docs:/app/docs -v ${PWD}/data:/app/data wenqu
```

## API

| Endpoint | Description |
|----------|-------------|
| `POST /api/ask` | Synchronous Q&A |
| `POST /api/ask/stream` | Streaming Q&A (SSE) |
| `POST /v1/chat/completions` | OpenAI Chat Completions compatible |
| `POST /v1/embeddings` | OpenAI Embeddings compatible |
| `GET /v1/models` | List models |
| `POST /api/import` | Import documents from docs/ |
| `GET /api/docs` | List imported documents |
| `DELETE /api/docs` | Delete a document |
| `GET /api/chunks` | List chunks (supports pagination) |
| `PUT /api/chunks` | Edit a chunk |
| `DELETE /api/chunks` | Delete chunks |
| `POST /api/chunks/split` | Split a chunk |
| `POST /api/chunks/merge` | Merge chunks |
| `POST /api/upload` | Upload file via drag-and-drop |
| `POST /api/feedback` | Submit feedback |
| `GET /api/health` | Health check |

See [API.md](API.md) for details.

## Project structure

```
wenqu/
├── server.py            # Web server entry point
├── run_tests.py         # Test runner
├── core/                # Core modules
│   ├── chunker.py       # Text chunking, summarization, keywords
│   ├── config.py        # Config management (.env auto-loading)
│   ├── embed.py         # Embedding via Ollama
│   ├── llm.py           # LLM calls (DeepSeek / Ollama)
│   ├── logging.py       # Logging
│   ├── parser.py        # Multi-format document parsing
│   ├── rag.py           # RAG orchestration
│   ├── retrieve.py      # Hybrid retrieval (vector + BM25 + RRF)
│   └── storage.py       # SQLite storage
├── static/
│   └── index.html       # Web frontend
├── tests/
│   └── test_core.py     # 33 test cases
├── scripts/             # Scripts (hooks, startup, utilities)
│   └── tools/           # Backup, evaluation, update tools
├── docs/                # Documents to index
├── data/                # Vector database (not committed)
├── logs/                # Error logs (not committed)
├── CLAUDE.md            # Project workflow
├── CHANGELOG.md         # Release notes (Chinese)
├── README.md
└── API.md
```

## Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `deepseek` | LLM backend: `deepseek` (requires key) or `ollama` (offline) |
| `DEEPSEEK_KEY` | — | DeepSeek API key (not needed in ollama mode) |
| `DEEPSEEK_BASE` | `https://api.deepseek.com/v1` | DeepSeek API base URL |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Chat model (set to e.g. `qwen2.5` for ollama mode) |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `EMBED_MODEL` | `bge-m3` | Embedding model |
| `VISION_MODEL` | `minicpm-v:8b` | Vision model for image extraction |
| `ENABLE_QUERY_REWRITE` | `1` | Query rewriting: `1` on, `0` off (saves an LLM call) |
| `HOST` | `0.0.0.0` | Listen host |
| `PORT` | `8080` | Listen port |
| `CHUNK_MAX_TOKENS` | `400` | Max tokens per chunk |
| `TOP_K` | `10` | Number of retrieval results |

## License

MIT
