"""
知识库更新脚本 — 清除旧数据、重新导入、重启服务
用法: python update.py
"""
import subprocess
import sys
import time
import os
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "vectors.db"


def kill_server():
    """停止正在运行的 server。"""
    print("停止旧服务...")
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq *server.py*"],
            capture_output=True,
        )
        # Fallback: kill all python processes that might be the server
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if ":8080" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                print(f"  已停止 PID {pid} (占用端口 8080)")
    else:
        subprocess.run(["pkill", "-f", "server.py"], capture_output=True)
    time.sleep(1)


def clear_db():
    """删除旧向量数据库。"""
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"已删除: {DB_PATH}")
    else:
        print("数据库不存在，跳过删除")


def reimport():
    """重新导入文档。"""
    print("重新导入文档...")
    result = subprocess.run(
        [sys.executable, str(ROOT / "kb.py"), "import"],
        cwd=str(ROOT),
        capture_output=False,
        timeout=600,
    )
    if result.returncode != 0:
        print("导入失败！")
        return False
    return True


def start_server():
    """启动 Web 服务（后台运行）。"""
    print("启动 Web 服务...")
    if sys.platform == "win32":
        # Windows: 使用 start 在新窗口启动
        subprocess.Popen(
            [sys.executable, str(ROOT / "server.py")],
            cwd=str(ROOT),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        subprocess.Popen(
            [sys.executable, str(ROOT / "server.py")],
            cwd=str(ROOT),
            start_new_session=True,
        )
    print("服务已启动: http://localhost:8080")


def main():
    print("=" * 50)
    print("知识库更新 + 重启")
    print("=" * 50)

    kill_server()
    clear_db()
    if not reimport():
        sys.exit(1)
    start_server()

    print("\n完成! 访问 http://localhost:8080")


if __name__ == "__main__":
    main()
