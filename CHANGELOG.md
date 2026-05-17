# 更新记录

## Unreleased

### 测试修复 & 增强
- **test_parse_txt** — 修复文档路径指向 `tests/docs/` 而非项目根 `docs/`，此前因路径不存在静默跳过从未真正执行
- **test_read_pdf** — 修复 `from core.pypdf import` 拼写错误（应为 `pypdf`），被 `try/except` 吞掉未暴露
- **test_env_override** — 修复 `os.environ['PORT']` 修改后未清理，可能污染后续测试
- **test_cosine** — 修正注释：同义词→同一词更近，实际语义正确
- **test_embed_* / test_retrieve_cached** — 新增 Ollama 可用性守卫，Ollama 未运行时自动跳过而非报错
- 新增 6 个测试：分页接口、stream 响应格式、标点分词、expand_query 边界、.env 加载检查
- 测试从 27 升至 33 个

## v0.1.0 (2026-05-17)

首个可用版本。

### 核心功能
- 本地知识库 RAG 问答系统，纯 Python 核心（零外部依赖）
- 支持 txt / md / docx / pptx / pdf / 图片解析
- Ollama 向量化 (bge-m3) + DeepSeek / Ollama LLM
- 混合检索：向量相似度 + BM25 + RRF 重排序
- SSE 流式问答，多轮对话
- OpenAI 兼容 API (`/v1/chat/completions`、`/v1/embeddings`、`/v1/models`)
- Web 管理界面：对话管理、块编辑器、深色/浅色主题、拖拽上传
- Docker 支持

### 开发者工具
- 27 个测试用例覆盖核心模块
- pre-push hook：推送前自动跑测试
- CLAUDE.md 工作流文档
- CHANGELOG.md 版本记录
