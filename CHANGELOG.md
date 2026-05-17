# 更新记录

## Unreleased

> 日常改动写在这里，攒够了升为版本号。

## v0.2.0 (2026-05-17)

React 前端重写，保持原版 vanilla HTML 作为回退。

### 前端重写 (2026-05-17 17:50)
- **React 18 + Vite 5** 重写全部 1140 行 vanilla JS 为 48 个组件文件
- 组件树：Sidebar (10) + Chat (10) + Modals (5) + Shared (3) + Contexts (3) + Hooks (4)
- 状态管理：useReducer 驱动对话 CRUD（12 个 action），3 个 Context（Theme/Toast/Conversations）
- 保留原版 `static/index.html`：删除 `static/dist/` 后自动回退
- `npm run build` 671ms 输出到 `static/dist/`
- server.py `_serve_static()` 自动检测 React 构建

### 测试修复 & 增强 (2026-05-17 15:50)
- 修复 5 个测试 bug：路径错误、import 拼写、环境变量泄漏、注释误导、Ollama 守卫缺失
- 新增 6 个测试：分页、stream、分词、expand_query、.env 加载
- 测试从 27 升至 33 个

### 改进
- LLM 提供商可切换（DeepSeek / Ollama），API Key 硬编码移除
- BM25 中文 bigram 分词，query rewrite 可配置开关
- README 英文化，CLAUDE.md 工作流文档，GitHub pre-push hook
- 目录整理、CHANGELOG 规范（具体时间 + 详细说明）

---

## v0.1.0 (2026-05-17)

首个可用版本。本地 RAG 知识库，Ollama 向量化 + DeepSeek 推理，OpenAI 兼容 API。
