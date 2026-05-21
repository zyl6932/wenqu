"""
本地知识库 Web 服务器 — FastAPI + uvicorn
启动: python server.py
"""
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.routes import register_routes
from core.server_utils import startup_diagnostics

app = FastAPI(title="问渠 (Wenqu)", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app)


def main():
    port = 8080

    print()
    print("  ██╗    ██╗███████╗███╗   ██╗  ██████╗ ██╗   ██╗")
    print("  ██║    ██║██╔════╝████╗  ██║ ██╔═══██╗██║   ██║")
    print("  ██║ █╗ ██║█████╗  ██╔██╗ ██║ ██║   ██║██║   ██║")
    print("  ██║███╗██║██╔══╝  ██║╚██╗██║ ██║▄▄ ██║██║   ██║")
    print("  ╚███╔███╔╝███████╗██║ ╚████║ ╚██████╔╝╚██████╔╝")
    print("   ╚══╝╚══╝ ╚══════╝╚═╝  ╚═══╝  ╚══▀▀═╝  ╚═════╝ ")
    print("         本地知识库 RAG 系统 · 问渠那得清如许")
    print()

    if not startup_diagnostics(port):
        try:
            input("\n按 Enter 退出...")
        except (EOFError, OSError):
            pass
        sys.exit(1)

    import uvicorn
    print(f"\n  服务已启动: http://localhost:{port}")
    print("  按 Ctrl+C 停止\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
