# 更新记录

## Unreleased

- 测试套件修复：修正 5 个测试 bug（路径错误、import 拼写、环境变量泄漏等），新增分页/stream/分词覆盖

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
