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

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Browser                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              React 18 SPA (Vite 5, 48 components)             │  │
│  │  ThemeContext / ToastContext / ConversationContext (useReducer) │  │
│  │  SSE streaming · Markdown · Dark/Light · Drag-drop upload      │  │
│  └──────────────────────────┬────────────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────────────┘
                              │ HTTP/SSE (localhost:8080)
┌─────────────────────────────┼───────────────────────────────────────┐
│                        Python Server (stdlib only)                   │
│  ┌──────────────────────────┴────────────────────────────────────┐  │
│  │               server.py  (ThreadPoolExecutor, 32 workers)      │  │
│  │  /api/ask · /api/ask/stream · /v1/chat/completions · /api/docs │  │
│  └──────┬──────────┬──────────┬──────────┬────────────────────────┘  │
│         │          │          │          │                           │
│    ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌───▼─────┐                      │
│    │  rag   │ │retrieve│ │embed │ │storage  │                      │
│    │ 编排层  │ │ 检索层  │ │向量化 │ │ 持久层   │                      │
│    └───┬────┘ └───┬──┬─┘ └──┬───┘ └───┬─────┘                      │
│        │          │  │       │         │                             │
│  ┌─────▼──┐ ┌─────▼──▼──┐ ┌─▼──────┐ ┌▼──────────┐                 │
│  │  llm   │ │  混合检索   │ │ Ollama │ │  SQLite   │                 │
│  │DeepSeek│ │Vector+BM25 │ │ bge-m3 │ │ WAL mode  │                 │
│  │ /Ollama│ │  +RRF融合   │ │        │ │thread-safe│                 │
│  └────────┘ └────────────┘ └────────┘ └───────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Retrieval Pipeline

```
User question
     │
     ▼
┌─────────────┐
│ correct_query │  "机器试觉" → "机器视觉"
└──────┬──────┘
       ▼
┌─────────────┐
│ expand_query │  "plc" → "PLC 可编程逻辑控制器 自动化控制"
└──────┬──────┘
       ▼
┌─────────────┐
│rewrite_query │  LLM rewrites for better embedding match  [optional]
└──────┬──────┘
       ▼
┌─────────────────────────────────────────┐
│           Multi-path Retrieval           │
│  ┌──────────────┐  ┌──────────────────┐  │
│  │ Vector Search │  │   BM25 Search     │  │
│  │  cosine(emb)  │  │ bigram tokenizer  │  │
│  └──────┬───────┘  └────────┬─────────┘  │
│         │                   │             │
│         └───────┬───────────┘             │
│                 ▼                         │
│         ┌─────────────┐                   │
│         │  RRF Fusion  │  k=60            │
│         │ + feedback   │                  │
│         │   boosting   │                   │
│         └──────┬──────┘                   │
└────────────────┼──────────────────────────┘
                 ▼
┌─────────────────┐
│   LLM Rerank    │  Top candidates ranked by LLM
└────────┬────────┘
         ▼
┌─────────────────┐
│  build_prompt()  │  Context → System Prompt
└────────┬────────┘
         ▼
┌─────────────────────────────┐
│      LLM Generation          │
│  ┌────────────────────────┐ │
│  │  thinking (R1 reasoner) │ │  reasoning_content → think-dots UI
│  │  ────────────────────── │ │
│  │  answer tokens          │ │  streaming-cursor animation
│  └────────────────────────┘ │
│  quality fallback: retry if │
│  answer < 15 chars or says │
│  "无法回答" but keywords    │
│  exist in retrieved chunks  │
└─────────────────────────────┘
```

### Frontend Component Tree

```
<main.jsx>
  <ThemeProvider>   ← localStorage "wenqu_theme"
    <ToastProvider>  ← ephemeral queue
      <ConversationProvider>  ← useReducer (12 actions)
        <App>
          ├── <ToastContainer />          fixed top-right
          ├── <Sidebar>
          │     ├── <SidebarHeader />      "问渠" + search/collapse btn
          │     ├── <SearchPanel />        对话过滤
          │     ├── <ConversationList>     时间分组 (今天/昨天/7天/更早)
          │     │     └── <ConversationItem />   select/rename/delete
          │     └── <SettingsPanel>
          │           ├── <ThemeToggle />   ☀/☽
          │           ├── <FontSizeControl />  12-20px
          │           ├── <ExportButton />  .md download
          │           └── <DocSection>
          │                 ├── <DocItem />  icon + open chunks
          │                 └── <ImportButton />
          ├── <ChatArea>
          │     ├── <MessageList>    scroll + scroll-to-bottom btn
          │     │     ├── <EmptyChat />     3 quick-start buttons
          │     │     └── <MessageItem>
          │     │           ├── <MessageContent />   Markdown rendering
          │     │           ├── <MessageSources />   citation tags
          │     │           └── <MessageActions />   copy/regenerate/feedback/delete
          │     └── <ChatInput>
          │           ├── <SearchHistoryDropdown />
          │           └── textarea + send/stop button
          ├── <DocModal />       view document content
          └── <ChunkModal>       edit/split/merge/delete chunks
              ├── <ChunkToolbar />
              └── <ChunkItem /> ×N
```

### API Design

```
GET  /api/health              Health check
GET  /api/health/full         Full diagnostics (port/ollama/data)
POST /api/ask                 Sync Q&A
POST /api/ask/stream          SSE streaming Q&A  ← main flow
POST /v1/chat/completions     OpenAI-compatible (stream/non-stream)
POST /v1/embeddings           OpenAI-compatible embeddings
GET  /v1/models               Model list

GET    /api/docs               List documents (paginated)
GET    /api/docs/content       View document content
DELETE /api/docs               Delete document + chunks
POST   /api/import             Import docs/ directory
POST   /api/upload             Drag-drop file upload (multipart)

GET    /api/chunks             List chunks (paginated)
PUT    /api/chunks             Edit chunk text (re-embeds)
DELETE /api/chunks             Delete chunk(s)
POST   /api/chunks/split       Split chunk by separator
POST   /api/chunks/merge       Merge multiple chunks

POST   /api/feedback           Record helpful/unhelpful
```

### SSE Stream Events

```
Client POST /api/ask/stream {"question":"...", "history":[...]}
                        │
Server:                 ▼
  data: {"sources": ["doc1.pdf", "doc2.pdf"]}      ← source list
  data: {"thinking": "原始问题：...\n检索范围：..."} ← retrieval trace
  data: {"think": "嗯，用户只说了..."}              ← R1 reasoning token (streaming)
  data: {"token": "根"}                             ← answer token (streaming)
  data: {"token": "据"}                             ← ...
  data: {"token": "..."}                            ← ...
  data: {"sources": ["doc1.pdf"]}                   ← final sources
```

## Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `deepseek` | LLM backend: `deepseek` (requires key) or `ollama` (offline) |
| `DEEPSEEK_KEY` | — | DeepSeek API key (not needed in ollama mode) |
| `DEEPSEEK_BASE` | `https://api.deepseek.com/v1` | DeepSeek API base URL |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Chat model: `deepseek-chat` / `deepseek-v4-flash` / `deepseek-reasoner` |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `EMBED_MODEL` | `bge-m3` | Embedding model |
| `VISION_MODEL` | `minicpm-v:8b` | Vision model for image extraction |
| `ENABLE_QUERY_REWRITE` | `1` | Query rewriting: `1` on, `0` off (saves an LLM call) |
| `HOST` | `0.0.0.0` | Listen host |
| `PORT` | `8080` | Listen port |
| `CHUNK_MAX_TOKENS` | `400` | Max tokens per chunk |
| `TOP_K` | `10` | Number of retrieval results |
| `MIN_SIMILARITY` | `0.25` | Minimum cosine similarity threshold |

> **Runtime adjustment**: `TOP_K`, `MIN_SIMILARITY`, and `ENABLE_QUERY_REWRITE` can be changed at runtime via the Settings panel in the Web UI. Changes take effect immediately without restarting the server.

## License

MIT
