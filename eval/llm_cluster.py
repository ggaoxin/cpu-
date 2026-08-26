"""LLM 直接聚类验证：提取每篇技术路线 → 汇总喂 LLM → LLM 输出聚类分组。

绕过 bge+KMeans 的向量中间损失，用 LLM 的语义理解直接聚类。
验证用：跑 N 轮，算 ARI/NMI vs consensus gold，看质量上限与稳定性。

用法:
    python eval/llm_cluster.py --rounds 3
"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from infrastructure.document_parser.mineru_reader import _cache_get
from infrastructure.llm.glm_client import GLMClient

DEFAULT_PAPERS = [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14]
PAPERS_DIR = "/root/autodl-tmp/data/papers"

# step1: 单篇抽技术路线（narrative，中文，聚焦本文核心方法）
SYSP_EXTRACT = (
    "你是科技文献分析专家。阅读文献全文，用中文概括本文自己提出/采用的核心技术路线（100-200字）。\n"
    "要求：\n"
    "- 只写本文自己的核心方法/模型/算法，不要写 related work 里提及的他人方法\n"
    "- 聚焦怎么做（技术手段），不要写应用领域\n"
    "只输出JSON：{\"route\":\"中文技术路线描述\"}"
)

# step2: 汇总聚类
SYSP_CLUSTER = (
    "你是科技文献聚类专家。以下是若干篇文献各自的技术路线描述。请按技术主题将它们聚成若干簇（3-8个）。\n\n"
    "要求：\n"
    "- 按每篇文献自己提出/采用的核心方法聚类，本质相似的归同簇\n"
    "- 每簇给一个 3-8 字的具体中文标签（如 强化学习/对比学习/实体检索/合成数据/冷启动推荐/视觉定位/材料科学/推理）\n"
    "- 每篇必须归且仅归一个簇；同簇文献数尽量均衡，避免单例\n"
    "只输出JSON：{\"clusters\":[{\"label\":\"中文标签\",\"document_ids\":[\"EN_00001\",...]}]}"
)


def _extract_route(glm, full_text, title, temp):
    try:
        d = glm.chat_json(SYSP_EXTRACT, f"标题：{title}\n全文（前8000字）：\n{full_text[:8000]}",
                          temperature=temp, timeout=60.0, max_tokens=300)
        return (d.get("route") or "").strip()
    except Exception as e:  # noqa: BLE001
        print(f"  抽取失败: {e}")
        return ""


def _llm_cluster(glm, docs, temp):
    """docs: [{document_id, title, route}] → {document_id: cluster_label}"""
    listing = "\n".join(
        f"[{d['document_id']}] 标题：{d['title']}\n    技术路线：{d['route']}"
        for d in docs)
    try:
        out = glm.chat_json(SYSP_CLUSTER, f"文献列表：\n{listing}",
                            temperature=temp, timeout=90.0, max_tokens=800)
        mapping = {}
        for cl in out.get("clusters", []):
            label = cl.get("label", "").strip()
            for did in cl.get("document_ids", []):
                mapping[did.strip()] = label
        return mapping
    except Exception as e:  # noqa: BLE001
        print(f"  聚类失败: {e}")
        return {}


def _purity(gold, algo):
    clusters = {}
    for g, a in zip(gold, algo):
        clusters.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in clusters.values()) / len(gold)


def run(rounds, gold_path):
    glm = GLMClient()
    gold_data = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    gold_map = {p["document_id"]: p["gold"] for p in gold_data["papers"]}

    # 1. 取全文 + 抽技术路线（每篇1次，temp=0）
    docs = []
    for i, n in enumerate(DEFAULT_PAPERS, 1):
        did = f"EN_{i:05d}"
        cached = _cache_get(f"{PAPERS_DIR}/{n}.pdf")
        title = (cached or {}).get("title", f"{n}.pdf")
        full = (cached or {}).get("full_text", "")
        route = _extract_route(glm, full, title, 0.0)
        docs.append({"document_id": did, "title": title, "route": route})
        print(f"  [{did} {n}.pdf] route: {route[:60]}")

    gold = [gold_map[d["document_id"]] for d in docs]
    print(f"\ngold({len(set(gold))}簇): {dict(Counter(gold))}")

    # 2. 多轮聚类，看稳定性 + vs gold
    print(f"\n聚类 {rounds} 轮...")
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, v_measure_score
    all_algos = []
    for r in range(rounds):
        temp = 0.3 + r * 0.1
        mapping = _llm_cluster(glm, docs, temp)
        algo = [mapping.get(d["document_id"], "?") for d in docs]
        all_algos.append(algo)
        ari = adjusted_rand_score(gold, algo)
        nmi = normalized_mutual_info_score(gold, algo)
        vm = v_measure_score(gold, algo)
        pur = _purity(gold, algo)
        print(f"  r{r}(temp={temp:.1f}): k={len(set(algo))} ARI={ari:.3f} NMI={nmi:.3f} "
              f"纯度={pur:.3f} V={vm:.3f}")
        print(f"    簇: {dict(Counter(algo))}")

    # 3. 多轮一致性：每对文献同簇频率
    if rounds >= 2:
        n = len(docs)
        agree = 0
        for i in range(n):
            for j in range(i + 1, n):
                same = sum(1 for algo in all_algos if algo[i] == algo[j])
                if same == rounds or same == 0:
                    agree += 1
        print(f"\n多轮稳定对: {agree}/{n*(n-1)//2} (全同簇或全不同簇的比例)")

    # 4. 逐篇对比（最后一轮）
    print("\n逐篇(最后一轮):")
    algo = all_algos[-1]
    for d, g, a in zip(docs, gold, algo):
        print(f"  {d['document_id']}: {d['title'][:30]:30} gold={g:10} algo={a}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--gold", default="eval/gold_12_consensus.json")
    args = ap.parse_args()
    run(args.rounds, args.gold if Path(args.gold).exists() else "eval/gold_12.json")
