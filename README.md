# 问渠

本地知识库 RAG 问答系统。纯 Python 实现，核心零外部依赖，基于 Ollama 做向量化，支持 DeepSeek API 或 Ollama 本地模型做 LLM 推理。

## 特性

- **文档解析** — 支持 txt / md / docx / pptx / pdf / 图片（OCR），自动分块、去重、摘要
- **向量检索** — Ollama + bge-m3，混合检索（向量相似度 + BM25 + RRF 重排序）
- **流式问答** — SSE 流式输出，多轮对话，自动补全 / 纠错
- **OpenAI 兼容** — `/v1/chat/completions`、`/v1/embeddings`、`/v1/models`，任意 OpenAI SDK 可直接接入
- **Web UI** — 问渠风格界面，支持深色/浅色主题、对话管理、块编辑器、拖拽上传
- **零外部依赖核心** — 核心模块仅用 Python 标准库，`pypdf` 为可选依赖

## 快速开始

### 环境要求

- Python >= 3.10
- [Ollama](https://ollama.com) 运行中，已拉取 `bge-m3` 模型

```bash
# 安装 Ollama 并拉取模型
ollama pull bge-m3
# （可选）视觉模型，用于图片/PDF 图片提取
ollama pull minicpm-v:8b
```

### 安装运行

```bash
# 克隆
git clone https://github.com/zyl6932/wenqu.git
cd wenqu

# 安装依赖
pip install -r requirements.txt

# 配置
cp .env.example .env
# 编辑 .env：
#   - 如果用 DeepSeek API，填 DEEPSEEK_KEY
#   - 如果想完全离线，改为 LLM_PROVIDER=ollama（需先 ollama pull qwen2.5）

# 放入文档到 docs/ 目录
# 把你的 .txt .md .docx .pdf 等文件放到 docs/

# 启动
python server.py
```

浏览器访问 `http://localhost:8080`，在 Web 界面中点击「+ 导入文档」即可开始问答。

### Docker（纯 CPU）

```bash
docker build -t wenqu .
# Linux / macOS
docker run -p 8080:8080 -v $(pwd)/docs:/app/docs -v $(pwd)/data:/app/data wenqu
# Windows PowerShell
docker run -p 8080:8080 -v ${PWD}/docs:/app/docs -v ${PWD}/data:/app/data wenqu
```

## API 概览

| 端点 | 说明 |
|------|------|
| `POST /api/ask` | 同步问答 |
| `POST /api/ask/stream` | 流式问答（SSE） |
| `POST /v1/chat/completions` | OpenAI Chat 兼容 |
| `POST /v1/embeddings` | OpenAI Embedding 兼容 |
| `GET /v1/models` | 模型列表 |
| `POST /api/import` | 导入 docs 目录文档 |
| `GET /api/docs` | 列出已导入文档 |
| `DELETE /api/docs` | 删除文档 |
| `GET /api/chunks` | 查看向量块 |
| `PUT /api/chunks` | 编辑向量块 |
| `DELETE /api/chunks` | 删除向量块 |
| `POST /api/chunks/split` | 拆分向量块 |
| `POST /api/chunks/merge` | 合并向量块 |
| `POST /api/upload` | 拖拽上传文件 |
| `POST /api/feedback` | 反馈记录 |
| `GET /api/health` | 健康检查 |

完整 API 文档见 [API.md](API.md)。

## 项目结构

```
wenqu/
├── server.py          # Web 服务器入口
├── core/
│   ├── chunker.py     # 文档分块、摘要、关键词
│   ├── config.py      # 配置管理（.env 自动加载）
│   ├── embed.py       # 向量化（Ollama）
│   ├── llm.py         # LLM 调用（DeepSeek / Ollama）
│   ├── logging.py     # 日志
│   ├── parser.py      # 文档解析（多格式）
│   ├── rag.py         # RAG 编排层
│   ├── retrieve.py    # 混合检索（向量 + BM25 bigram + RRF）
│   └── storage.py     # SQLite 存储
├── static/
│   └── index.html     # Web 前端
├── tests/
│   └── test_core.py   # 33 个测试用例
├── scripts/           # 脚本（含 pre-push hook）
├── docs/              # 待导入文档目录
├── data/              # 向量数据库（不入库）
├── CLAUDE.md          # 项目工作流文档
├── CHANGELOG.md       # 版本更新记录
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## 配置

通过环境变量或 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_PROVIDER` | `deepseek` | LLM 后端：`deepseek`（需 Key）或 `ollama`（离线） |
| `DEEPSEEK_KEY` | — | DeepSeek API Key（ollama 模式无需） |
| `DEEPSEEK_BASE` | `https://api.deepseek.com/v1` | DeepSeek API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 对话模型（ollama 模式设为 qwen2.5 等） |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama 地址 |
| `EMBED_MODEL` | `bge-m3` | 向量化模型 |
| `VISION_MODEL` | `minicpm-v:8b` | 视觉模型 |
| `ENABLE_QUERY_REWRITE` | `1` | 查询改写：`1` 开启，`0` 关闭（省 LLM 调用） |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8080` | 监听端口 |
| `CHUNK_MAX_TOKENS` | `400` | 分块最大 token |
| `TOP_K` | `10` | 检索返回数量 |

## License

MIT
