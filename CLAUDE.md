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

## 推送前工作流（必须遵守）
每次 `git push` 之前：
1. 运行 `python run_tests.py` 确保 27 个测试全部通过
2. 在 `CHANGELOG.md` 顶部记录本次改动内容
3. pre-push hook 会自动执行以上检查（测试不通过会拒绝推送）

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
