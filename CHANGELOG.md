# 更新记录

## 2026-05-17

### 新增
- LLM 提供商可切换：支持 Ollama 本地模型 (`LLM_PROVIDER=ollama`)，无需 API Key
- `/v1/chat/completions` 支持 stream 模式 (SSE)，OpenAI SDK 可直接调用
- API 分页：`/api/docs` 和 `/api/chunks` 支持 `?page=&page_size=`
- 启动 ASCII banner
- 对话消息删除功能、复制按钮反馈
- 推送前自动测试 (pre-push hook)

### 修复
- 移除硬编码的 API Key，改为 `.env` 自动加载
- 修复 StorageConfig 路径指向 `core/docs/` 的 bug，正确解析到项目根目录
- docs 目录二进制文件 (PDF/docx) 不再纳入 Git 追踪

### 改进
- BM25 中文分词从单字改为 bigram，检索质量提升
- Query rewrite 改为可配置 (`ENABLE_QUERY_REWRITE=0` 关闭)

---

## 2026-05-17 (初始)

- 本地知识库 RAG 问答系统，纯 Python 核心
- 支持 txt/md/docx/pdf/图片解析
- Ollama 向量化 + DeepSeek LLM
- 混合检索（向量 + BM25 + RRF）
- SSE 流式问答，多轮对话
- OpenAI 兼容 API
- Web 管理界面（深色/浅色主题）
