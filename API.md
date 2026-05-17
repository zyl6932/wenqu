# API 文档

Base URL: `http://localhost:8080`

---

## 问答

### `POST /api/ask`
同步问答。返回完整答案后才能获取结果。

**Body:** `{"question": "Ollama 怎么安装"}`

**Response:** `{"answer": "...", "sources": ["ollama_guide.txt"]}`

### `POST /api/ask/stream`
流式问答（SSE）。实时返回 token。

**Body:** `{"question": "...", "history": [{"role":"user","content":"..."}]}`

**SSE Events:**
- `data: {"token": "文"}` — 单个 token
- `data: {"sources": ["file.txt"]}` — 来源列表
- `data: {"error": "..."}` — 错误

---

## OpenAI 兼容

### `POST /v1/chat/completions`
OpenAI Chat Completions 兼容接口。任何 OpenAI SDK 可直接调用。

**Body:**
```json
{
  "model": "wenqu-v1",
  "messages": [{"role": "user", "content": "你的问题"}]
}
```

### `POST /v1/embeddings`
OpenAI Embeddings 兼容接口。

**Body:** `{"input": "要向量化的文本", "model": "bge-m3"}`

### `GET /v1/models`
列出可用模型。

---

## 文档管理

### `GET /api/docs`
列出已导入文档。

### `GET /api/docs/content?path=<urlencoded_path>`
获取文档内容。

### `DELETE /api/docs`
删除文档及其向量块。
**Body:** `{"path": "..."}`

### `POST /api/import`
扫描 docs 目录并导入新文档。

---

## 向量块管理

### `GET /api/chunks?source=<path>`
列出某文档的所有向量块。

### `PUT /api/chunks`
更新块文本（自动重新向量化）。
**Body:** `{"id": 1, "text": "新内容"}`

### `DELETE /api/chunks`
删除单个或多个块。
**Body:** `{"id": 1}` 或 `{"ids": [1,2,3]}`

### `POST /api/chunks/split`
拆分块。
**Body:** `{"id": 1, "separator": "分隔文本"}`

### `POST /api/chunks/merge`
合并块。
**Body:** `{"ids": [1, 2, 3]}`

---

## 反馈与健康

### `POST /api/feedback`
记录用户反馈。
**Body:** `{"question": "...", "contexts": [...], "helpful": true}`

### `GET /api/health`
简单健康检查。

### `GET /api/health/full`
完整诊断：端口 / Ollama / 数据完整性。

---

## 文件上传

### `POST /api/upload`
上传文件到 docs 目录并自动导入。
**Body:** `multipart/form-data` with `file` field.
