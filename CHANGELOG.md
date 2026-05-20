# 更新记录

## Unreleased

> 日常改动写在这里，攒够了升为版本号。

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
