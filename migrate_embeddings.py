"""迁移脚本：将 JSON 嵌入转为 numpy binary float32。运行一次即可。"""
import json
import sys
import numpy as np
from core.storage import get_db

db = get_db()

rows = db.execute("SELECT id, embedding FROM chunks").fetchall()
if not rows:
    print("知识库为空，无需迁移。")
    sys.exit(0)

migrated = 0
for chunk_id, emb_data in rows:
    if isinstance(emb_data, bytes) and emb_data and emb_data[0:1] != b'[':
        continue  # 已经是 binary 格式

    if isinstance(emb_data, str):
        emb = json.loads(emb_data)
    elif isinstance(emb_data, bytes):
        emb = json.loads(emb_data.decode("utf-8"))
    else:
        continue

    binary = np.array(emb, dtype=np.float32).tobytes()
    db.execute("UPDATE chunks SET embedding = ? WHERE id = ?", (binary, chunk_id))
    migrated += 1

db.commit()
print(f"迁移完成: {migrated}/{len(rows)} 条已转换。")
print("提示: 重启服务即可使用新格式。旧 JSON 格式仍兼容读取。")
