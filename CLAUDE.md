# 问渠 (Wenqu) — 本地知识库 RAG 系统

## 技术栈
- Python >= 3.10，核心零外部依赖（仅 pypdf 可选）
- 嵌入：Ollama + bge-m3
- LLM：DeepSeek API 或 Ollama 本地模型（支持 deepseek-reasoner 思考链）
- 存储：SQLite
- 前端：React 18 + Vite 5，原版 vanilla HTML 保留为回退

## 常用命令
```bash
python server.py                  # 启动服务 (localhost:8080)
python run_tests.py               # 运行测试 (47 tests, 完整版 160s)
cd frontend && npm run build      # 构建 React 前端
```
推送前 pre-push hook 自动跑 21 个快速测试（0.5s），发 release 时需手动跑全量 `python run_tests.py`。
pip install -r requirements.txt   # 安装 Python 依赖
cd frontend && npm install        # 安装前端依赖
```

## 标准工作流

### 日常推送
```bash
# 1. 改代码
# 2. 更新 CHANGELOG.md — 写到 Unreleased 区域，格式：
#    ### 标题 (YYYY-MM-DD HH:MM)
#    - 具体改动说明
#    不要只写一句"修复bug"，要写清楚修了哪个、有什么影响
# 3. 提交并推送（pre-push hook 自动跑测试）
git add -A
git commit -m "feat/fix/docs: 简述改动"
git push
```

### 发布新版本
不要每次都发 —— 积累足够多改动后再发（如 5-10 个功能/修复）。
```bash
# 1. 跑全量测试（必须全部通过）
python run_tests.py
# 2. 将 CHANGELOG.md 中 Unreleased 的内容移到新版本号下
# 3. 确保 pyproject.toml 版本号正确
# 4. 提交并推送
# 5. 创建 GitHub Release
gh release create vX.Y.Z --title "vX.Y.Z - 简述" --notes-file CHANGELOG.md
```
版本号遵循 semver：`v主.次.补丁`（如 v0.1.0 → v0.2.0 → v1.0.0）

## 项目结构
```
wenqu/
├── server.py            # Web 服务器入口
├── core/
│   ├── chunker.py       # 文档分块/摘要/关键词
│   ├── config.py        # 配置管理 + .env 加载
│   ├── embed.py         # Ollama 向量化
│   ├── llm.py           # LLM 调用（DeepSeek/Ollama）
│   ├── parser.py        # 多格式文档解析
│   ├── rag.py           # RAG 编排层
│   ├── retrieve.py      # 混合检索（向量+BM25+RRF）
│   └── storage.py       # SQLite 存储
├── frontend/src/        # React 前端源码
├── static/dist/         # React 构建产物
├── tests/test_core.py   # 33 个测试用例
├── docs/                # 待导入文档
├── data/                # 向量数据库（不入库）
├── CLAUDE.md            # 项目工作流
├── CHANGELOG.md         # 版本更新记录
└── API.md
```

## 配置方式
环境变量通过 `.env` 文件设置（自动加载），关键变量：
- `LLM_PROVIDER` — `deepseek` 或 `ollama`
- `DEEPSEEK_MODEL` — `deepseek-chat` / `deepseek-reasoner` (R1 思考链)
- `DEEPSEEK_KEY` — API Key（ollama 模式无需）
- `ENABLE_QUERY_REWRITE` — 查询改写开关

## 代码风格
- Python：类型注解、dataclass、无注释（命名自解释）
- 前端：React JSX，无 TypeScript
- 不引入不必要的抽象或依赖

---

# 行为准则

> 源自 Andrej Karpathy 对 LLM 编码陷阱的观察。偏向谨慎而非速度，琐碎任务自行判断。

## 1. 编码前思考

**不要假设。不要隐藏困惑。呈现权衡。**

- 明确说明假设 — 如果不确定，询问而不是猜测
- 存在歧义时呈现多种解释，不要默默选择
- 如果有更简单的方法，说出来。适时提出异议
- 不清楚的地方停下来，指出困惑并要求澄清

## 2. 简洁优先

**用最少的代码解决问题。不过度推测。**

- 不添加要求之外的功能
- 不为一次性代码创建抽象
- 不添加未要求的"灵活性"或"可配置性"
- 不为不可能发生的场景做错误处理
- 如果 200 行可以写成 50 行，重写它

**检验标准：** 资深工程师会觉得这过于复杂吗？如果是，简化。

## 3. 精准修改

**只碰必须碰的。只清理自己造成的混乱。**

- 不"改进"相邻的代码、注释或格式
- 不重构没坏的东西
- 匹配现有风格，即使你更倾向于不同的写法
- 注意到无关的死代码时提一下，不要删除
- 删除因你的改动而变得无用的导入/变量/函数
- 每一行修改都应该能直接追溯到用户的请求

## 4. 目标驱动执行

**定义成功标准。循环验证直到达成。**

- "添加验证" → "为无效输入编写测试，然后让它们通过"
- "修复 bug" → "编写重现 bug 的测试，然后让它通过"
- "重构 X" → "确保重构前后测试都能通过"

多步骤任务先列计划：
```
1. [步骤] → 验证: [检查]
2. [步骤] → 验证: [检查]
```

**这些准则生效的标志：** diff 中不必要的改动更少、因过度复杂而导致的重写更少、澄清问题在实现之前提出而非犯错之后。

# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.