"""
知识库效果评估脚本 — 量化召回率、准确率、MRR
用法:
  python eval_kb.py              # 快速评估当前配置
  python eval_kb.py --compare    # 对比 6 种策略
  python eval_kb.py --full       # 含 LLM 端到端评估
"""
import json
import time
from dataclasses import dataclass
from core.retrieve import retrieve, clear_cache
from core.embed import embed, cosine
from core.chunker import split_text
from core.llm import chat
from core.rag import build_prompt
from core.config import RETRIEVAL_CFG
from core.storage import get_db
MIN_SIMILARITY = RETRIEVAL_CFG.min_similarity

# ═══════════════════════════════════════════════════════════
# Benchmark 问题集
# ═══════════════════════════════════════════════════════════

BENCHMARK = [
    # ── ollama_guide.txt ──
    {
        "id": "O-1", "question": "什么是Ollama？",
        "keywords": ["Ollama", "本地运行", "大语言模型", "工具"],
        "expected": ["本地运行大语言模型的工具"],
    },
    {
        "id": "O-2", "question": "Ollama支持哪些模型？",
        "keywords": ["Qwen", "Llama", "Mistral", "模型"],
        "expected": ["Qwen", "Llama", "Mistral"],
    },
    {
        "id": "O-3", "question": "Ollama默认端口是多少？",
        "keywords": ["11434", "端口", "localhost"],
        "expected": ["11434"],
    },
    {
        "id": "O-4", "question": "知识库系统需要哪两个模型配合？",
        "keywords": ["大语言模型", "嵌入模型", "向量化", "生成回答"],
        "expected": ["大语言模型", "嵌入模型"],
    },
    {
        "id": "O-5", "question": "什么是RAG？它有什么优势？",
        "keywords": ["RAG", "检索增强", "幻觉", "更新", "重新训练"],
        "expected": ["检索增强生成", "减少幻觉", "不需要重新训练"],
    },
    {
        "id": "O-6", "question": "最小的嵌入模型是什么？有多大？",
        "keywords": ["all-minilm", "67MB", "最小", "嵌入"],
        "expected": ["all-minilm", "67MB"],
    },

    # ── 生产实习课程报告.docx ──
    {
        "id": "R-1", "question": "参观了哪些公司？",
        "keywords": ["公司", "实习", "参观", "有限", "企业", "基地", "工业园", "创业园"],
        "expected": [
            "湖北小食代科技有限公司", "湖北传开食品有限公司",
            "美利信科技股份有限公司", "汇科创业园", "襄阳东昇机械有限公司",
            "襄阳康贝尔智能装备有限公司", "襄阳东风李尔泰极爱思汽车座椅有限公司",
            "襄阳中基创展智能科技有限公司", "东风汽车股份有限公司",
            "风华磁材", "骆驼集团新能源", "襄阳群龙汽车部件股份有限公司",
            "湖北晖泓科技有限公司", "湖北中盛电气有限公司",
            "襄樊恒德汽车配件有限公司", "湖北欣华捷新能源汽车科技有限公司",
            "中印南方印刷有限公司",
        ],
    },
    {
        "id": "R-2", "question": "进入车间参观需要注意哪些安全事项？",
        "keywords": ["安全帽", "嬉戏", "打闹", "拍摄", "脚下", "堆放", "航车", "保密"],
        "expected": ["佩戴安全帽", "严禁嬉戏打闹", "注意脚下", "严禁拍摄内部构造"],
    },
    {
        "id": "R-3", "question": "动员会和安全教育讲了哪些内容？",
        "keywords": ["动员会", "安全教育", "行为规范", "安全事故", "职业素养", "防护"],
        "expected": ["实习目的", "安全规范", "事故案例", "职业素养"],
    },
    {
        "id": "R-4", "question": "印刷的工艺流程是什么？",
        "keywords": ["CTP", "制版", "水墨", "印刷", "装订", "平印", "轮转"],
        "expected": ["CTP制版", "水墨不相容", "平印", "轮转印刷"],
    },
    {
        "id": "R-5", "question": "机械电子工程师应该具备哪些职业素养？",
        "keywords": ["职业素养", "责任心", "时间观念", "抗压", "团队", "3-5年"],
        "expected": ["责任心", "时间观念", "抗压能力", "3-5年经验积累"],
    },
    {
        "id": "R-6", "question": "PLC实训是在哪里进行的？",
        "keywords": ["PLC", "汇科创业园", "实训", "变频器", "伺服"],
        "expected": ["汇科创业园"],
    },
    {
        "id": "R-7", "question": "钣金车间的工艺流程包括哪些步骤？",
        "keywords": ["拆图", "激光切割", "折弯", "数字化", "板材"],
        "expected": ["数字化拆图", "激光切割", "折弯"],
    },
    {
        "id": "R-8", "question": "新能源汽车的核心部件有哪些？",
        "keywords": ["电池包", "底盘", "电驱动", "纯电", "前驱", "后驱", "电机"],
        "expected": ["电池包", "驱动电机", "底盘"],
    },
    {
        "id": "R-9", "question": "中印南方印刷有限公司的历史沿革是怎样的？",
        "keywords": ["603厂", "上海印刷五厂", "乐凯", "迁至", "文创园"],
        "expected": ["1965年文字603厂", "上海印刷五厂内迁", "中国乐凯"],
    },
    {
        "id": "R-10", "question": "职业规划方面有什么建议？",
        "keywords": ["3-5年", "经验", "专业术语", "职业规划", "技术交流", "阶梯"],
        "expected": ["3-5年经验积累", "建立专业术语体系", "能力阶梯式提升"],
    },
]


# ═══════════════════════════════════════════════════════════
# 核心评估逻辑（共享 embedding，一次计算多种策略）
# ═══════════════════════════════════════════════════════════

def is_relevant(chunk: str, keywords: list[str]) -> bool:
    hits = sum(1 for kw in keywords if kw.lower() in chunk.lower())
    return hits >= 2


@dataclass
class Strategy:
    name: str
    top_k: int = 10
    expand: int = 1


STRATEGIES = [
    Strategy("top_k=4  无扩展", top_k=4, expand=0),
    Strategy("top_k=6  无扩展", top_k=6, expand=0),
    Strategy("top_k=10 无扩展", top_k=10, expand=0),
    Strategy("top_k=6  + expand±1", top_k=6, expand=1),
    Strategy("top_k=10 + expand±1 ★", top_k=10, expand=1),
    Strategy("top_k=10 + expand±2", top_k=10, expand=2),
]

DEFAULT = STRATEGIES[4]  # 当前配置


def rank_chunks(question: str):
    """对数据库中所有 chunk 按相似度排序（只计算一次 embedding）。"""
    db = get_db()
    rows = db.execute("SELECT id, source, text, embedding FROM chunks").fetchall()
    q_emb = embed([question])[0]

    scored = []
    for cid, source, text, emb_blob in rows:
        emb = json.loads(emb_blob)
        s = cosine(q_emb, emb)
        scored.append((s, cid, text, source))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def simulate_retrieve(scored: list, strategy: Strategy) -> list[str]:
    """从预计算的排序结果中模拟检索（含上下文扩展）。"""
    # 过滤低于阈值的
    relevant = [(s, cid, t, src) for s, cid, t, src in scored if s >= MIN_SIMILARITY]
    top = relevant[:strategy.top_k]
    if not top:
        return []

    db = get_db()
    expanded_ids: set[int] = set()
    contexts = []
    for _, chunk_id, _, source in top:
        for adj_id in range(chunk_id - strategy.expand, chunk_id + strategy.expand + 1):
            if adj_id in expanded_ids:
                continue
            expanded_ids.add(adj_id)
            row = db.execute(
                "SELECT text FROM chunks WHERE id = ? AND source = ?",
                (adj_id, source),
            ).fetchone()
            if row:
                contexts.append(row[0])

    # 内容去重
    seen = set()
    unique = []
    for t in contexts:
        key = t[:80]
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def evaluate_strategy(scored_map: dict, strategy: Strategy, verbose: bool = True) -> dict:
    """评估单个策略的全部指标。"""
    results = []
    total_recall = total_precision = total_mrr = total_cov = 0.0
    n = 0

    for item in BENCHMARK:
        qid = item["id"]
        question = item["question"]
        keywords = item["keywords"]
        expected = item["expected"]
        scored = scored_map[question]

        # 总相关 chunk 数
        total_rel = sum(1 for _, _, text, _ in scored if is_relevant(text, keywords))

        # 模拟检索
        contexts = simulate_retrieve(scored, strategy)
        retrieved_rel = sum(1 for c in contexts if is_relevant(c, keywords))

        # Recall / Precision
        recall = retrieved_rel / total_rel if total_rel > 0 else 0.0
        precision = retrieved_rel / len(contexts) if contexts else 0.0

        # MRR
        mrr_val = 0.0
        above = [(s, cid, t) for s, cid, t, _ in scored if s >= MIN_SIMILARITY]
        for rank, (_, _, text) in enumerate(above[:strategy.top_k], 1):
            if is_relevant(text, keywords):
                mrr_val = 1.0 / rank
                break

        # LLM 覆盖率（仅 verbose 模式）
        coverage = 0.0
        if verbose and contexts:
            try:
                prompt = build_prompt(contexts, question)
                answer = chat([{"role": "user", "content": prompt}])
                hits = sum(1 for fact in expected if fact.lower() in answer.lower())
                coverage = hits / len(expected) if expected else 0.0
            except Exception:
                pass

        total_recall += recall
        total_precision += precision
        total_mrr += mrr_val
        total_cov += coverage
        n += 1

        results.append({
            "id": qid, "recall": recall, "precision": precision,
            "mrr": mrr_val, "coverage": coverage,
            "rel_ret": retrieved_rel, "rel_total": total_rel,
        })

    avg = {
        "recall": total_recall / n, "precision": total_precision / n,
        "mrr": total_mrr / n, "coverage": total_cov / n,
    }
    avg["weighted"] = avg["recall"] * 0.4 + avg["precision"] * 0.2 + avg["mrr"] * 0.2 + avg["coverage"] * 0.2

    if verbose:
        _print_results(strategy.name, results, avg)

    return {"strategy": strategy.name, **avg, "details": results}


def _print_results(name: str, results: list, avg: dict):
    print(f"\n{'='*70}")
    print(f"策略: {name}")
    print(f"{'='*70}")
    print(f"{'ID':<6} {'Recall':>7} {'Prec':>7} {'MRR':>7} {'覆盖':>7}")
    print(f"{'-'*50}")
    for r in results:
        print(f"{r['id']:<6} {r['recall']:>6.1%} {r['precision']:>6.1%} {r['mrr']:>6.2f} {r['coverage']:>6.1%}")
    print(f"{'-'*50}")
    print(f"{'平均':<6} {avg['recall']:>6.1%} {avg['precision']:>6.1%} {avg['mrr']:>6.2f} {avg['coverage']:>6.1%}")
    print(f"加权总分: {avg['weighted']:.1%} (R×0.4 + P×0.2 + MRR×0.2 + Cov×0.2)")


def compare():
    """对比所有策略（共享 embedding）。"""
    print("\n" + "=" * 70)
    print("策略对比测试 (共享 embedding，快速)")
    print("=" * 70)

    # 预计算所有问题的排序（最耗时步骤，只做一次）
    print("预计算 embedding 排序...")
    scored_map = {}
    for item in BENCHMARK:
        q = item["question"]
        scored_map[q] = rank_chunks(q)
        print(f"  ✓ {item['id']}")
    print(f"完成，共 {len(BENCHMARK)} 个问题\n")

    all_results = []
    for strat in STRATEGIES:
        result = evaluate_strategy(scored_map, strat, verbose=False)
        all_results.append(result)

    # 排名
    all_results.sort(key=lambda r: r["weighted"], reverse=True)

    print(f"\n{'='*70}")
    print("排名")
    print(f"{'='*70}")
    print(f"{'#':<3} {'策略':<30} {'Recall':>7} {'Prec':>7} {'MRR':>7} {'加权':>7}")
    print(f"{'-'*70}")
    for i, r in enumerate(all_results, 1):
        marker = " ★" if r["strategy"] == DEFAULT.name else ""
        print(f"{i:<3} {r['strategy']:<30} {r['recall']:>6.1%} {r['precision']:>6.1%} "
              f"{r['mrr']:>6.2f} {r['weighted']:>6.1%}{marker}")

    return all_results


def main():
    import sys

    if "--compare" in sys.argv:
        compare()
    else:
        # 默认：快速评估当前策略
        print("预计算 embedding 排序...")
        scored_map = {}
        for item in BENCHMARK:
            scored_map[item["question"]] = rank_chunks(item["question"])
            print(f"  ✓ {item['id']}")
        evaluate_strategy(scored_map, DEFAULT, verbose=True)


if __name__ == "__main__":
    main()
