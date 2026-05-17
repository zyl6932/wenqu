# 问渠 (Wenqu) — 本地知识库 RAG 系统

## 技术栈
- Python >= 3.10，核心零外部依赖（仅 pypdf 可选）
- 嵌入：Ollama + bge-m3
- LLM：DeepSeek API 或 Ollama 本地模型
- 存储：SQLite
- 前端：Vanilla HTML/CSS/JS（无框架）

## 常用命令
```bash
python server.py          # 启动服务 (localhost:8080)
python run_tests.py       # 运行测试 (27 tests)
pip install -r requirements.txt  # 安装依赖
```

## 标准工作流

### 日常推送
```bash
# 1. 改代码
# 2. 更新 CHANGELOG.md — 写到 Unreleased 区域，说明做了什么、为什么
#    不要只写一句"修复bug"，要写清楚修了哪个、有什么影响
# 3. 提交并推送（pre-push hook 自动跑测试）
git add -A
git commit -m "feat/fix/docs: 简述改动"
git push
```

### 发布新版本
不要每次都发 —— 积累足够多改动后再发（如 5-10 个功能/修复）。
```bash
# 1. 将 CHANGELOG.md 中 Unreleased 的内容移到新版本号下
# 2. 确保 pyproject.toml 版本号正确
# 3. 提交并推送
# 4. 创建 GitHub Release
gh release create vX.Y.Z --title "vX.Y.Z - 简述" --notes-file CHANGELOG.md
```
版本号遵循 semver：`v主.次.补丁`（如 v0.1.0 → v0.2.0 → v1.0.0）

## 项目结构
```
wenqu/
├── server.py          # Web 服务器（入口）
├── core/
│   ├── config.py      # 配置管理 + .env 加载
│   ├── chunker.py     # 文档分块/摘要/关键词
│   ├── embed.py       # Ollama 向量化
│   ├── llm.py         # LLM 调用（DeepSeek/Ollama）
│   ├── parser.py      # 多格式文档解析
│   ├── rag.py         # RAG 编排层
│   ├── retrieve.py    # 混合检索（向量+BM25+RRF）
│   └── storage.py     # SQLite 存储
├── static/index.html  # Web 前端
├── tests/test_core.py # 测试用例
├── docs/              # 待导入文档（二进制不入库）
├── data/              # 向量数据库（不入库）
├── .env.example       # 环境变量模板
└── CHANGELOG.md       # 更新记录
```

## 配置方式
环境变量通过 `.env` 文件设置（自动加载），关键变量：
- `LLM_PROVIDER` — `deepseek` 或 `ollama`
- `DEEPSEEK_KEY` — API Key（ollama 模式无需）
- `ENABLE_QUERY_REWRITE` — 查询改写开关

## 代码风格
- Python：类型注解、dataclass、无注释（命名自解释）
- 前端：Vanilla JS，无框架依赖
- 不引入不必要的抽象或依赖
