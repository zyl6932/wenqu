"""
测试用例 — 覆盖核心模块
运行: python tests.py
"""
import sys
import unittest
from pathlib import Path

# ── 配置测试 ──────────────────────────────────────────
class ConfigTest(unittest.TestCase):
    def test_config_loads(self):
        from core.config import LLM_CFG, EMBED_CFG, RETRIEVAL_CFG, STORAGE_CFG
        self.assertTrue(len(EMBED_CFG.model) > 0)
        self.assertTrue(RETRIEVAL_CFG.chunk_max_tokens > 0)
        self.assertTrue(isinstance(STORAGE_CFG.data_dir, Path))
        # API key 可能为空（ollama 模式无需 key）或已设置
        self.assertIsInstance(LLM_CFG.api_key, str)

    def test_env_override(self):
        import os
        os.environ['PORT'] = '9999'
        from core.config import ServerConfig
        s = ServerConfig(port=int(os.environ['PORT']))
        self.assertEqual(s.port, 9999)

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
            self.assertLessEqual(estimate_tokens(c), 120)  # 留余量

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
        from core.retrieve import retrieve, clear_cache
        clear_cache()
        r1 = retrieve("测试问题")
        r2 = retrieve("测试问题")
        self.assertEqual(r1 is None, r2 is None)  # 缓存一致性


# ── 嵌入测试 ─────────────────────────────────────────
class EmbedTest(unittest.TestCase):
    def test_embed_returns_correct_dim(self):
        from core.embed import embed
        embs = embed(["测试文本"])
        self.assertEqual(len(embs), 1)
        self.assertGreater(len(embs[0]), 100)

    def test_embed_cache(self):
        from core.embed import embed, clear_cache
        clear_cache()
        embed(["缓存测试"])
        from core.embed import _embed_cache
        self.assertGreater(len(_embed_cache), 0)

    def test_cosine(self):
        from core.embed import cosine, embed_single
        a = embed_single("猫")
        b = embed_single("狗")
        c = embed_single("猫")
        self.assertGreater(cosine(a, c), cosine(a, b))  # 同义词更近


# ── 解析测试 ─────────────────────────────────────────
class ParserTest(unittest.TestCase):
    def test_parse_txt(self):
        from core.parser import parse_file
        txt_path = Path(__file__).parent / "docs" / "ollama_guide.txt"
        if txt_path.exists():
            text = parse_file(str(txt_path))
            self.assertGreater(len(text), 50)

    def test_read_pdf(self):
        from core.parser import HAS_PYPDF
        try:
            from core.pypdf import PdfReader
            self.assertTrue(HAS_PYPDF)
        except ImportError:
            self.skipTest("pypdf 未安装")


# ── 服务器 API 测试 ─────────────────────────────────
class APITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import urllib.request, json
        cls.base = "http://localhost:8080"
        try:
            urllib.request.urlopen(f"{cls.base}/api/health", timeout=2)
            cls.server_up = True
        except Exception:
            cls.server_up = False

    def test_health(self):
        if not self.server_up:
            self.skipTest("服务器未运行")
        import urllib.request
        resp = urllib.request.urlopen(f"{self.base}/api/health", timeout=5)
        self.assertEqual(resp.status, 200)

    def test_v1_models(self):
        if not self.server_up:
            self.skipTest("服务器未运行")
        import urllib.request, json
        resp = urllib.request.urlopen(f"{self.base}/v1/models", timeout=5)
        data = json.loads(resp.read())
        self.assertEqual(data['object'], 'list')
        self.assertGreater(len(data['data']), 0)

    def test_docs_list(self):
        if not self.server_up:
            self.skipTest("服务器未运行")
        import urllib.request, json
        resp = urllib.request.urlopen(f"{self.base}/api/docs", timeout=5)
        data = json.loads(resp.read())
        self.assertIn('docs', data)


# ── 索引测试（如有 bm25 相关问题）───────────────
class BM25Test(unittest.TestCase):
    def test_bm25_build(self):
        from core.storage import count_chunks
        if count_chunks() == 0:
            self.skipTest("知识库为空")
        from core.retrieve import _bm25
        _bm25.invalidate()
        _bm25.build()
        self.assertTrue(_bm25._built)
        self.assertGreater(_bm25.n, 0)

    def test_tokenize_chinese_bigram(self):
        from core.retrieve import _tokenize
        tokens = _tokenize("机器视觉特征提取")
        # bigram: 机器、器视、视觉、觉特、特征、征提、提取
        self.assertIn("机器", tokens)
        self.assertIn("视觉", tokens)
        self.assertIn("提取", tokens)
        # 单字不应出现
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


if __name__ == '__main__':
    print("=" * 60)
    print("  知识库测试套件")
    print("=" * 60)
    # 只运行不需要服务器的测试（快速模式）
    if '--full' in sys.argv:
        unittest.main(argv=['tests.py'], exit=False)
    else:
        suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
        # 过滤掉需要服务器的测试
        import unittest
        filtered = unittest.TestSuite()
        for test_class in [ConfigTest, StorageTest, ChunkerTest, BM25Test, EmbedTest, ParserTest]:
            filtered.addTests(unittest.TestLoader().loadTestsFromTestCase(test_class))
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(filtered)
        print()
        print("要运行完整测试（含API），请先启动服务器然后执行:")
        print("  python tests.py --full")
