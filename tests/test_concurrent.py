"""
并发压力测试 — 模拟多人同时问答
用法: python tests/test_concurrent.py
"""
import json
import time
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "http://localhost:8080"
CONCURRENT = 50  # 并发数（每次测试 50 并发，跑 4 轮 = 200）
LLM_CONCURRENT = 10  # 真实 LLM 问答并发数（避免 API 浪费）


def health_check(_):
    """健康检查 — 轻量级，测试纯 HTTP 并发"""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(f"{BASE}/api/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return time.perf_counter() - start, resp.status == 200 and data.get("status") == "ok"
    except Exception as e:
        return time.perf_counter() - start, False


def ask_stream(_):
    """流式问答 — 测试完整 RAG 链路（检索 + LLM）"""
    start = time.perf_counter()
    try:
        body = json.dumps({"question": "机器视觉"}).encode()
        req = urllib.request.Request(f"{BASE}/api/ask/stream", data=body)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            output = b""
            for line in resp:
                output += line
            return time.perf_counter() - start, len(output) > 0
    except Exception as e:
        return time.perf_counter() - start, False


def docs_list(_):
    """文档列表 — 测试 SQLite 并发读"""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(f"{BASE}/api/docs")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return time.perf_counter() - start, "docs" in data
    except Exception:
        return time.perf_counter() - start, False


def run_test(name, fn, total, workers):
    """运行一轮测试，统计延迟和成功率"""
    print(f"\n{'='*60}")
    print(f"  {name} — {total} 请求，{workers} 并发")
    print(f"{'='*60}")

    latencies = []
    ok = 0
    fail = 0
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fn, i) for i in range(total)]
        done = 0
        for future in as_completed(futures):
            lat, success = future.result()
            latencies.append(lat)
            if success:
                ok += 1
            else:
                fail += 1
            done += 1
            if done % 50 == 0:
                print(f"  进度: {done}/{total}")

    elapsed = time.perf_counter() - start
    latencies.sort()

    def pct(p):
        idx = int(len(latencies) * p / 100)
        return latencies[min(idx, len(latencies) - 1)]

    print(f"\n  总耗时:     {elapsed:.1f}s")
    print(f"  吞吐量:     {total / elapsed:.0f} req/s")
    print(f"  成功:       {ok}")
    print(f"  失败:       {fail}")
    print(f"  成功率:     {ok / total * 100:.1f}%")
    print(f"  P50 延迟:   {pct(50)*1000:.0f}ms")
    print(f"  P95 延迟:   {pct(95)*1000:.0f}ms")
    print(f"  P99 延迟:   {pct(99)*1000:.0f}ms")
    print(f"  最大延迟:   {latencies[-1]*1000:.0f}ms")
    return ok, fail


if __name__ == "__main__":
    # 快速检查服务器是否运行
    try:
        urllib.request.urlopen(f"{BASE}/api/health", timeout=2)
    except Exception:
        print("服务器未运行，请先启动 python server.py")
        exit(1)

    print("=" * 60)
    print("  并发压力测试")
    print("=" * 60)

    # 1. 轻量级并发：健康检查 200 并发
    run_test("GET /api/health (轻量)", health_check, total=200, workers=200)

    # 2. SQLite 并发读：文档列表 100 并发
    run_test("GET /api/docs (SQLite 读)", docs_list, total=100, workers=50)

    # 3. 完整 RAG 流式问答（限制 LLM 并发 = 10）
    run_test("POST /api/ask/stream (完整 RAG)", ask_stream, total=20, workers=LLM_CONCURRENT)

    print(f"\n{'='*60}")
    print("  测试完成")
    print(f"{'='*60}")
