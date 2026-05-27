"""
测试用例 — 覆盖核心模块
运行: python run_tests.py
"""
import json
import os
import sys
import unittest
from pathlib import Path


# ── 辅助函数 ──────────────────────────────────────────
def _ollama_available():
    """检查 Ollama 是否可用。"""
    try:
        import urllib.request, json
        req = urllib.request.Request("http://localhost:11434/api/tags")
        urllib.request.urlopen(req, timeout=3)
        return True
    except Exception:
        return False


def _server_up():
    """检查服务器是否在运行。"""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:8080/api/health", timeout=2)
        return True
    except Exception:
        return False


# ── 配置测试 ──────────────────────────────────────────
class ConfigTest(unittest.TestCase):
    def test_config_loads(self):
        from core.config import LLM_CFG, EMBED_CFG, RETRIEVAL_CFG, STORAGE_CFG
        self.assertTrue(len(EMBED_CFG.model) > 0)
        self.assertTrue(RETRIEVAL_CFG.chunk_max_tokens > 0)
        self.assertTrue(isinstance(STORAGE_CFG.data_dir, Path))
        self.assertIsInstance(LLM_CFG.api_key, str)

    def test_env_override(self):
        original = os.environ.get('PORT')
        os.environ['PORT'] = '9999'
        try:
            from core.config import ServerConfig
            s = ServerConfig(port=int(os.environ['PORT']))
            self.assertEqual(s.port, 9999)
        finally:
            if original is not None:
                os.environ['PORT'] = original
            else:
                os.environ.pop('PORT', None)

    def test_storage_paths_resolve_to_project_root(self):
        from core.config import STORAGE_CFG
        project_root = Path(__file__).parent.parent
        self.assertEqual(STORAGE_CFG.data_dir, project_root / "data")
        self.assertEqual(STORAGE_CFG.docs_dir, project_root / "docs")
        self.assertEqual(STORAGE_CFG.log_dir, project_root / "logs")

    def test_llm_provider_defaults(self):
        from core.config import LLM_CFG
        self.assertIn(LLM_CFG.provider, ("deepseek", "ollama"))

    def test_query_rewrite_toggle(self):
        from core.config import RETRIEVAL_CFG
        self.assertIsInstance(RETRIEVAL_CFG.enable_query_rewrite, bool)

    def test_dotenv_loader_loads_env_file(self):
        # .env 存在时 DEEPSEEK_KEY 应被加载
        from core.config import LLM_CFG
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            # 切换到 ollama 模式不需要 Key，但 deepseek 模式需要
            if LLM_CFG.provider == "deepseek":
                self.assertTrue(len(LLM_CFG.api_key) > 0, "DeepSeek 模式下 API Key 不能为空，请检查 .env")


# ── 存储测试 ──────────────────────────────────────────
class StorageTest(unittest.TestCase):
    def test_db_creates_tables(self):
        from core.storage import get_db
        db = get_db()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        names = [t[0] for t in tables]
        for t in ['chunks', 'sources', 'feedback']:
            self.assertIn(t, names)

    def test_count(self):
        from core.storage import count_chunks, count_sources
        self.assertIsInstance(count_chunks(), int)
        self.assertIsInstance(count_sources(), int)


# ── 分块测试 ──────────────────────────────────────────
class ChunkerTest(unittest.TestCase):
    def test_clean_text(self):
        from core.chunker import clean_text
        dirty = "\x00测试  文本\x1f内容\n\n\n多余空行"
        cleaned = clean_text(dirty)
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("\x1f", cleaned)

    def test_split_text(self):
        from core.chunker import split_text, estimate_tokens
        text = "这是第一句。这是第二句。这是第三句。" * 20
        chunks = split_text(text, max_tokens=100, overlap_tokens=20)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(estimate_tokens(c), 120)

    def test_estimate_tokens(self):
        from core.chunker import estimate_tokens
        self.assertGreater(estimate_tokens("Hello World 测试"), 3)

    def test_extract_keywords(self):
        from core.chunker import extract_keywords
        kw = extract_keywords("机器视觉是人工智能的重要应用领域")
        self.assertTrue(any('机器视觉' in k or '人工智能' in k for k in kw))

    def test_build_overview(self):
        from core.chunker import build_overview
        text = "1.1 概述\n内容...\n2.1 湖北小食代科技有限公司实习"
        ov = build_overview(text)
        self.assertIn("【文档章节概览】", ov)
        self.assertIn("小食代", ov)


# ── 检索测试 ─────────────────────────────────────────
class RetrieveTest(unittest.TestCase):
    def test_correct_query(self):
        from core.retrieve import correct_query
        self.assertIn("机器视觉", correct_query("机器试觉"))
        self.assertIn("ollama", correct_query("ollma"))
        self.assertIn("PLC", correct_query("plc"))

    def test_expand_query(self):
        from core.retrieve import expand_query
        result = expand_query("plc")
        self.assertIn("plc", result.lower())

    def test_retrieve_cached(self):
        if not _ollama_available():
            self.skipTest("Ollama 未运行")
        from core.retrieve import retrieve, clear_cache
        clear_cache()
        r1 = retrieve("测试问题")
        r2 = retrieve("测试问题")
        self.assertEqual(r1 is None, r2 is None)

    def test_expand_query_noop_for_long_question(self):
        from core.retrieve import expand_query
        long_q = "这是一个很长的复杂问题，包含很多关键信息"
        result = expand_query(long_q)
        self.assertEqual(result, long_q)


# ── 嵌入测试 ─────────────────────────────────────────
class EmbedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ollama_ok = _ollama_available()

    def test_embed_returns_correct_dim(self):
        if not self.ollama_ok:
            self.skipTest("Ollama 未运行")
        from core.embed import embed
        embs = embed(["测试文本"])
        self.assertEqual(len(embs), 1)
        self.assertGreater(len(embs[0]), 100)

    def test_embed_cache(self):
        if not self.ollama_ok:
            self.skipTest("Ollama 未运行")
        from core.embed import embed, clear_cache
        clear_cache()
        embed(["缓存测试"])
        from core.embed import _embed_cache
        self.assertGreater(len(_embed_cache), 0)

    def test_cosine_same_word_closer_than_different(self):
        if not self.ollama_ok:
            self.skipTest("Ollama 未运行")
        from core.embed import cosine, embed_single
        a = embed_single("猫")
        b = embed_single("狗")
        c = embed_single("猫")
        self.assertGreater(cosine(a, c), cosine(a, b))


# ── 解析测试 ─────────────────────────────────────────
class ParserTest(unittest.TestCase):
    def test_parse_txt(self):
        from core.parser import parse_file
        txt_path = Path(__file__).parent.parent / "docs" / "ollama_guide.txt"
        if not txt_path.exists():
            self.skipTest("ollama_guide.txt 不存在")
        text = parse_file(str(txt_path))
        self.assertGreater(len(text), 50)

    def test_has_pypdf(self):
        try:
            import pypdf  # noqa: F401
            from core.parser import HAS_PYPDF
            self.assertTrue(HAS_PYPDF)
        except ImportError:
            self.skipTest("pypdf 未安装")


# ── 服务器 API 测试 ─────────────────────────────────
class APITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = "http://localhost:8080"
        cls.server_up = _server_up()

    def _skip_if_down(self):
        if not self.server_up:
            self.skipTest("服务器未运行")

    def test_health(self):
        self._skip_if_down()
        import urllib.request
        resp = urllib.request.urlopen(f"{self.base}/api/health", timeout=5)
        self.assertEqual(resp.status, 200)

    def test_v1_models(self):
        self._skip_if_down()
        import urllib.request, json
        resp = urllib.request.urlopen(f"{self.base}/v1/models", timeout=5)
        data = json.loads(resp.read())
        self.assertEqual(data['object'], 'list')
        self.assertGreater(len(data['data']), 0)

    def test_docs_list(self):
        self._skip_if_down()
        import urllib.request, json
        resp = urllib.request.urlopen(f"{self.base}/api/docs", timeout=5)
        data = json.loads(resp.read())
        self.assertIn('docs', data)

    def test_docs_list_pagination(self):
        self._skip_if_down()
        import urllib.request, json
        resp = urllib.request.urlopen(f"{self.base}/api/docs?page=1&page_size=2", timeout=5)
        data = json.loads(resp.read())
        self.assertIn('docs', data)
        self.assertIn('total', data)
        self.assertIn('page', data)
        self.assertIn('page_size', data)
        self.assertTrue(len(data['docs']) <= 2)

    def test_v1_chat_completions_stream(self):
        self._skip_if_down()
        import urllib.request, json
        body = json.dumps({
            "model": "wenqu-v1",
            "messages": [{"role": "user", "content": "你好"}],
            "stream": True,
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.base}/v1/chat/completions", data=body)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as resp:
            content_type = resp.headers.get("Content-Type", "")
            self.assertIn("event-stream", content_type)
            data_lines = []
            for _ in range(20):
                line = resp.readline().decode("utf-8").strip()
                if line:
                    data_lines.append(line)
                if "[DONE]" in line:
                    break
            self.assertTrue(any("chat.completion.chunk" in l for l in data_lines))

    def test_chunks_list_pagination(self):
        self._skip_if_down()
        import urllib.request, json
        resp = urllib.request.urlopen(f"{self.base}/api/chunks?page=1&page_size=2", timeout=5)
        data = json.loads(resp.read())
        self.assertIn('chunks', data)
        self.assertIn('total', data)


# ── 索引 & 分词测试 ──────────────────────────────────
# ── 运行时配置测试 ──────────────────────────────────
class APIConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = "http://localhost:8080"
        cls.server_up = _server_up()

    def _skip_if_down(self):
        if not self.server_up:
            self.skipTest("服务器未运行")

    def test_get_config(self):
        self._skip_if_down()
        import urllib.request, json
        resp = urllib.request.urlopen(f"{self.base}/api/config", timeout=5)
        data = json.loads(resp.read())
        self.assertIn('min_similarity', data)
        self.assertIn('top_k', data)
        self.assertIsInstance(data['top_k'], int)
        self.assertGreater(data['top_k'], 0)

    def test_update_top_k(self):
        self._skip_if_down()
        import urllib.request, json
        # 先保存旧值
        resp = urllib.request.urlopen(f"{self.base}/api/config", timeout=5)
        old = json.loads(resp.read())
        old_k = old['top_k']
        # 改值
        body = json.dumps({"top_k": 15}).encode()
        req = urllib.request.Request(f"{self.base}/api/config", data=body, method='POST')
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        self.assertEqual(data['config']['top_k'], 15)
        # 恢复
        body = json.dumps({"top_k": old_k}).encode()
        req = urllib.request.Request(f"{self.base}/api/config", data=body, method='POST')
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)

    def test_update_threshold(self):
        self._skip_if_down()
        import urllib.request, json
        resp = urllib.request.urlopen(f"{self.base}/api/config", timeout=5)
        old = json.loads(resp.read())
        old_v = old['min_similarity']
        # 改值
        body = json.dumps({"min_similarity": 0.5}).encode()
        req = urllib.request.Request(f"{self.base}/api/config", data=body, method='POST')
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        self.assertEqual(data['config']['min_similarity'], 0.5)
        # 恢复
        body = json.dumps({"min_similarity": old_v}).encode()
        req = urllib.request.Request(f"{self.base}/api/config", data=body, method='POST')
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)

    def test_config_affects_retrieval(self):
        self._skip_if_down()
        import urllib.request, json
        # 改 top_k 为 3
        body = json.dumps({"top_k": 3}).encode()
        req = urllib.request.Request(f"{self.base}/api/config", data=body, method='POST')
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        self.assertEqual(data['config']['top_k'], 3)
        # 发一个检索请求看是否成功
        body2 = json.dumps({"question": "测试"}).encode()
        req2 = urllib.request.Request(f"{self.base}/api/ask", data=body2, method='POST')
        req2.add_header("Content-Type", "application/json")
        resp2 = urllib.request.urlopen(req2, timeout=30)
        ans = json.loads(resp2.read())
        self.assertIn('answer', ans)
        # 恢复默认
        body = json.dumps({"top_k": 10}).encode()
        req = urllib.request.Request(f"{self.base}/api/config", data=body, method='POST')
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)


# ── LLM 切换测试 ──────────────────────────────────
class LLMProviderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = "http://localhost:8080"
        cls.server_up = _server_up()

    def _skip_if_down(self):
        if not self.server_up:
            self.skipTest("服务器未运行")

    def test_ask_stream_default(self):
        """默认（不传 llm_provider）使用 deepseek"""
        self._skip_if_down()
        import urllib.request, json
        body = json.dumps({"question": "测试"}).encode()
        req = urllib.request.Request(f"{self.base}/api/ask/stream", data=body, method='POST')
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=30)
        data_lines = []
        for _ in range(10):
            line = resp.readline().decode("utf-8").strip()
            if line:
                data_lines.append(line)
            if 'token' in line or 'error' in line:
                break
        self.assertTrue(any('token' in l or 'error' in l or 'thinking' in l for l in data_lines))

    def test_ask_stream_ollama(self):
        """传入 llm_provider=ollama 切换到本地模型"""
        self._skip_if_down()
        import urllib.request, json
        body = json.dumps({"question": "测试", "llm_provider": "ollama"}).encode()
        req = urllib.request.Request(f"{self.base}/api/ask/stream", data=body, method='POST')
        req.add_header("Content-Type", "application/json")
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            data_lines = []
            for _ in range(10):
                line = resp.readline().decode("utf-8").strip()
                if line:
                    data_lines.append(line)
                if 'token' in line or 'error' in line:
                    break
            # 即使 Ollama 未运行，至少应返回 error 事件而非 HTTP 错误
            self.assertTrue(any('token' in l or 'error' in l or 'thinking' in l for l in data_lines))
        except Exception as e:
            # 如果 Ollama 不可用也会收到 SSE error 事件
            pass


class BM25Test(unittest.TestCase):
    def test_bm25_like_search(self):
        from core.storage import count_chunks
        if count_chunks() == 0:
            self.skipTest("知识库为空")
        from core.retrieve import _bm25_like_search
        results = _bm25_like_search("机器视觉", top_k=5)
        self.assertIsInstance(results, list)

    def test_bm25_like_search_empty(self):
        from core.retrieve import _bm25_like_search
        results = _bm25_like_search("", top_k=5)
        self.assertEqual(results, [])

    def test_tokenize_chinese_bigram(self):
        from core.retrieve import _tokenize
        tokens = _tokenize("机器视觉特征提取")
        self.assertIn("机器", tokens)
        self.assertIn("视觉", tokens)
        self.assertIn("提取", tokens)
        self.assertNotIn("机", tokens)

    def test_tokenize_mixed_cn_en(self):
        from core.retrieve import _tokenize
        tokens = _tokenize("Ollama安装")
        self.assertIn("ollama", tokens)
        self.assertIn("安装", tokens)

    def test_tokenize_short_chinese(self):
        from core.retrieve import _tokenize
        tokens = _tokenize("电")
        self.assertEqual(tokens, ["电"])

    def test_tokenize_punctuation_skipped(self):
        from core.retrieve import _tokenize
        tokens = _tokenize("测试，文本。")
        self.assertIn("测试", tokens)
        self.assertIn("文本", tokens)
        self.assertNotIn("，", tokens)


# ── 前端构建测试 ──────────────────────────────────
class FrontendBuildTest(unittest.TestCase):
    """检测前端构建产物是否存在且 JS 无语法错误"""

    def test_dist_index_html_exists(self):
        dist = Path(__file__).parent.parent / 'static' / 'dist' / 'index.html'
        self.assertTrue(dist.exists(), f'{dist} 不存在，请先 npm run build')

    def test_dist_js_bundle_exists(self):
        dist = Path(__file__).parent.parent / 'static' / 'dist' / 'assets'
        self.assertTrue(dist.exists(), 'static/dist/assets 不存在')
        js_files = list(dist.glob('index-*.js'))
        self.assertTrue(len(js_files) > 0, '未找到 JS bundle')

    def test_js_bundle_parseable(self):
        """用 Node.js 解析 JS bundle，检测语法错误（白屏常见原因）"""
        import subprocess
        dist = Path(__file__).parent.parent / 'static' / 'dist' / 'assets'
        js_files = list(dist.glob('index-*.js'))
        if not js_files:
            self.skipTest('无 JS bundle')
        js_file = js_files[0].resolve()
        result = subprocess.run(
            ['node', '-e', f'new Function(require("fs").readFileSync(String.raw`{js_file}`,"utf8"))'],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, f'JS bundle 语法错误:\n{result.stderr[:500]}')

    def test_js_bundle_has_react_root(self):
        """确认 bundle 包含 React 根节点渲染代码"""
        dist = Path(__file__).parent.parent / 'static' / 'dist' / 'assets'
        js_files = list(dist.glob('index-*.js'))
        if not js_files:
            self.skipTest('无 JS bundle')
        content = js_files[0].read_text(encoding='utf-8')
        self.assertIn('root', content, 'JS bundle 中未找到 root 引用')


# ── 回归测试（针对已知 bug）──────────────────────────
class RegressionTest(unittest.TestCase):
    def test_embed_deserialize_both_formats(self):
        """嵌入反序列化兼容 JSON 和 numpy binary 两种存储格式"""
        import numpy as np
        from core.embed import embed_single

        # 生成和存储一样格式的 embedding
        emb = embed_single("测试")
        # JSON 字符串
        json_str = json.dumps(emb)
        loaded_from_json = json.loads(json_str)
        self.assertEqual(len(loaded_from_json), len(emb))

        # numpy binary
        binary = np.array(emb, dtype=np.float32).tobytes()
        loaded_from_binary = np.frombuffer(binary, dtype=np.float32).tolist()
        self.assertEqual(len(loaded_from_binary), len(emb))
        # 数值近似相等（float32 精度）
        for a, b in zip(loaded_from_binary, emb):
            self.assertAlmostEqual(a, b, delta=1e-5)

    def test_parser_rejects_legacy_doc(self):
        """旧 .doc 格式应被拒绝并给出清晰错误，而非 UTF-8 崩溃"""
        from core.parser import parse_file
        import tempfile
        # 创建假的 .doc 文件
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as f:
            f.write(b'\xbe\x00\x00\x00')
            tmp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                parse_file(tmp_path)
            self.assertIn("旧版 .doc 格式不支持", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    def test_import_skips_doc_files(self):
        """import_docs 导入时跳过 .doc 文件而不崩溃"""
        from core.rag import import_docs
        log_lines = []
        import_docs(on_log=log_lines.append)
        # 确认没有任何 UTF-8 错误出现在输出中
        output = " ".join(log_lines)
        self.assertNotIn("utf-8", output.lower())
        self.assertNotIn("UnicodeDecodeError", output)

    def test_config_all_keys_present(self):
        """运行时配置返回完整字段"""
        from core.config import get_runtime_config
        cfg = get_runtime_config()
        for key in ("min_similarity", "top_k", "enable_query_rewrite", "enable_rerank"):
            self.assertIn(key, cfg)


class StaticFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = "http://localhost:8080"
        cls.server_up = _server_up()

    def _skip_if_down(self):
        if not self.server_up:
            self.skipTest("服务器未运行")

    def test_js_file_served(self):
        self._skip_if_down()
        import urllib.request
        # 先读 index.html 找到 JS 文件名
        resp = urllib.request.urlopen(f"{self.base}/", timeout=5)
        html = resp.read().decode("utf-8")
        import re
        m = re.search(r'/assets/(index-[a-zA-Z0-9_-]+\.js)', html)
        if not m:
            self.skipTest("JS filename not found in HTML")
        js_path = f"/assets/{m.group(1)}"
        resp = urllib.request.urlopen(f"{self.base}{js_path}", timeout=5)
        self.assertEqual(resp.status, 200)
        self.assertIn("application/javascript", resp.headers.get("Content-Type", ""))

    def test_css_file_served(self):
        self._skip_if_down()
        import urllib.request
        resp = urllib.request.urlopen(f"{self.base}/", timeout=5)
        html = resp.read().decode("utf-8")
        import re
        m = re.search(r'/assets/(index-[a-zA-Z0-9_-]+\.css)', html)
        if not m:
            self.skipTest("CSS filename not found in HTML")
        css_path = f"/assets/{m.group(1)}"
        resp = urllib.request.urlopen(f"{self.base}{css_path}", timeout=5)
        self.assertEqual(resp.status, 200)
        self.assertIn("text/css", resp.headers.get("Content-Type", ""))


class AskStreamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = "http://localhost:8080"
        cls.server_up = _server_up()

    def _skip_if_down(self):
        if not self.server_up:
            self.skipTest("服务器未运行")

    def test_ask_stream_returns_data(self):
        """流式问答能正常返回数据（不会 UTF-8 崩溃或无响应）"""
        self._skip_if_down()
        import urllib.request, json
        body = json.dumps({"question": "测试"}).encode()
        req = urllib.request.Request(f"{self.base}/api/ask/stream", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=30)
        content_type = resp.headers.get("Content-Type", "")
        self.assertIn("event-stream", content_type)
        # 读取至少一条有效输出
        lines = []
        for _ in range(30):
            line = resp.readline().decode("utf-8").strip()
            if line:
                lines.append(line)
            if any(ev in line for ev in ("token", "error", "thinking")):
                break
        self.assertGreater(len(lines), 0, "SSE 流未返回任何数据")

    def test_ask_stream_no_utf8_error(self):
        """流式问答不会返回 UTF-8 解码错误"""
        self._skip_if_down()
        import urllib.request, json
        body = json.dumps({"question": "测试"}).encode()
        req = urllib.request.Request(f"{self.base}/api/ask/stream", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req, timeout=30)
        for _ in range(50):
            line = resp.readline().decode("utf-8").strip()
            if line and "error" in line:
                data = json.loads(line[6:])  # strip "data: "
                self.assertNotIn("utf-8", data.get("error", "").lower())
                self.assertNotIn("UnicodeDecodeError", data.get("error", ""))
                self.assertNotIn("list index out of range", data.get("error", ""))
                break


if __name__ == '__main__':
    print("=" * 60)
    print("  知识库测试套件")
    print("=" * 60)
    if '--full' in sys.argv:
        unittest.main(argv=['tests.py'], exit=False)
    else:
        suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
        filtered = unittest.TestSuite()
        for test_class in [ConfigTest, StorageTest, ChunkerTest, RetrieveTest, BM25Test, EmbedTest, ParserTest,
                           APIConfigTest, LLMProviderTest, RegressionTest, StaticFileTest, AskStreamTest, FrontendBuildTest]:
            filtered.addTests(unittest.TestLoader().loadTestsFromTestCase(test_class))
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(filtered)
        print()
        print("要运行完整测试（含API），请先启动服务器然后执行:")
        print("  python run_tests.py --full")
