"""
知识库数据备份 / 恢复
用法:
  python tools/backup.py backup              # 备份
  python tools/backup.py restore <备份路径>  # 恢复
"""
import shutil
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
BACKUP_DIR = ROOT / "backups"


def backup():
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"kb_backup_{ts}"
    dest.mkdir()

    # 复制数据库
    db_src = DATA_DIR / "vectors.db"
    if db_src.exists():
        shutil.copy2(db_src, dest / "vectors.db")
        print(f"✓ vectors.db")

    # 复制 docs 目录
    docs_dest = dest / "docs"
    docs_dest.mkdir()
    for f in DOCS_DIR.glob("*"):
        if f.is_file():
            shutil.copy2(f, docs_dest / f.name)
            print(f"✓ {f.name}")

    print(f"\n备份完成: {dest}")


def restore(backup_path: str):
    src = Path(backup_path)
    if not src.exists():
        print(f"备份不存在: {src}")
        sys.exit(1)

    db_src = src / "vectors.db"
    if db_src.exists():
        shutil.copy2(db_src, DATA_DIR / "vectors.db")
        print(f"✓ 恢复 vectors.db")

    docs_src = src / "docs"
    if docs_src.exists():
        for f in docs_src.glob("*"):
            shutil.copy2(f, DOCS_DIR / f.name)
            print(f"✓ 恢复 {f.name}")

    print("\n恢复完成")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tools/backup.py backup|restore [路径]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "backup":
        backup()
    elif cmd == "restore":
        if len(sys.argv) < 3:
            print("请指定备份路径")
            sys.exit(1)
        restore(sys.argv[2])
    else:
        print(f"未知命令: {cmd}")
