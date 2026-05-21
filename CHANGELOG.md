# 更新记录

## Unreleased

### 新增 (2026-05-21)
- **对话标题栏**：聊天区顶部显示当前对话标题，与侧边栏"问渠"像素级对齐
- **LLM 生成标题**：新对话发送首条消息后，异步调用 LLM 自动生成简洁标题
- **设置弹窗**：独立居中弹窗+模糊背景，主题/字号/LLM模型/检索参数/导出/文档管理全部收入
- **LLM 运行时切换**：设置面板一键切换 联网(DeepSeek) / 本地(Ollama)，localStorage 持久化，无需重启
- **知识单元树分块**：`split_with_structure()` 检测标题层级，`get_parent_chunk()` 命中子块时自动带父章节
- **检索过程流式展示**：思考步骤穿插在 token 流中，不再阻塞回答输出
- `POST /api/title` 标题生成端点
- `core/retrieve.py` 完整注解（10 步管线流程图 + 各模块说明）
- 检索缓存改 LRU（上限 1000），嵌入缓存用 SHA256 key

### 改进 (2026-05-21)
- **Markdown 修复**：marked v12 API 适配（`setOptions`→`marked.use`），完整 GFM 渲染恢复
- **UI 细节**：聊天区/输入框边距大幅缩进（20→144px），文档列表加滚动条，导入按钮不受裁剪
- **字号修复**：`.message-content` 改用 CSS 变量 `var(--font-size)`，字体缩放生效
- **标题栏对齐**：侧边栏收起时标题自动右移避开展开按钮，收起/展开时动态 padding
- **LLM 兼容**：`reasoning_content` 空值不阻塞普通 token，新增 `deepseek-v4-flash` 模型支持
- **检索性能**：BM25 索引缓存、embedding 二进制存储、numpy 向量计算（Phase 1+2）
- **HTTP 层升级**：`http.server` → FastAPI + uvicorn（SSE 改用 StreamingResponse，CORS 中间件，客户端断连检测，减少 ~200 行）
- **文档增量索引**：sources 表记录文件 mtime，`import_docs()` 自动检测变更并重新索引，不再需要手动删了再导
- **LLM 摘要可选**：导入时 LLM 摘要生成默认关闭（`generate_summary=False`），不再拖慢导入
- LLM provider 线程安全：`llm_provider` 沿调用链传参，不再修改全局配置
- `sys.stdout` 劫持移除：`import_docs()` 改用 `on_log` 回调
- 后台启动不再因 `input()` EOFError 崩溃
- 新增 `POST /api/docs/reindex` 端点
- 测试保持 39 个全部通过

### 修复 (2026-05-21)
- `chat_header` 与 `sidebar-header` 高度对齐（line-height 30px + padding 16px 统一）
- 侧边栏按钮/标题重叠 → 动态缩进
- 设置面板内容被截断 → 收进独立弹窗

## v0.3.0 (2026-05-20)

### 新增
- **检索参数运行时调整**：相似度阈值、top_k、查询改写可在 Web 设置面板实时调节，即时生效
- `GET/POST /api/config` 端点支持读写检索配置
- 刷新保护：页面刷新/关闭时自动中断流式请求，服务端检测断连即停止 LLM 调用，避免浪费
- 递归文件夹导入：`docs/` 子目录中的文档自动递归扫描导入
- 并发压测脚本 `tests/test_concurrent.py`（200 并发，3 种场景）

### 改进
- 高并发优化：线程池化（32 workers）、SQLite WAL 模式、LLM 信号量限流（10 并发）、嵌入缓存线程锁
- 前端恢复逻辑：刷新页面后检测半成品消息，自动清理思考动画并提示重新发送
- README 新增系统架构图（系统概览、检索管线、组件树、API/SSE 协议）
- README 新增运行时配置调整说明
- 测试从 33 升至 37 个（新增 4 个运行时配置测试）
- 思考过程 UI 持续优化：默认折叠、箭头后置、颜色调整、流式光标仅在输出时显示

### 修复
- `rglob` 递归扫描替代 `glob`，支持多层嵌套文件夹
- `.gitignore` 改为递归模式覆盖所有子目录的二进制文件，过滤 Office 临时文件
- 思考内容多余换行符和空格清理

---

## v0.2.0 (2026-05-17)

React 前端重写，保持原版 vanilla HTML 作为回退。

### 前端重写
- React 18 + Vite 5，48 个组件文件，useReducer 驱动对话 CRUD
- 保留原版 `static/index.html`：删除 `static/dist/` 后自动回退

### 测试
- 修复 5 个测试 bug，新增 6 个测试，从 27 升至 33 个

### 改进
- LLM 提供商可切换（DeepSeek / Ollama），API Key 硬编码移除
- BM25 中文 bigram 分词，query rewrite 可配置开关
- README 英文化，CLAUDE.md 工作流文档，GitHub pre-push hook
- 目录整理、CHANGELOG 规范

---

## v0.1.0 (2026-05-17)

首个可用版本。本地 RAG 知识库，Ollama 向量化 + DeepSeek 推理，OpenAI 兼容 API。
