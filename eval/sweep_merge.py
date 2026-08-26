"""扫合并阈值：固定微聚类中间簇，遍历 merge_threshold 评测 ARI/NMI/簇数。

微聚类(分桶→桶内LLM)与合并阈值无关，只跑一次并缓存中间簇，
随后各阈值仅重跑 _merge_clusters（秒级），快速找最优阈值。
"""
from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)

from infrastructure.llm.glm_client import GLMClient
from infrastructure.clustering.semantic_cluster import (
    _llm_cluster_docs, _merge_clusters, llm_cluster_large)
from infrastructure.rag.m3_encoder import m3_encoder

CACHE_ROUTES = Path("/tmp/zh500_topic_routes.json")
CACHE_INTER = Path("/tmp/zh500_intermediate.json")
SYSP_TOPIC = (
    "你是科技文献分析专家。阅读文献摘要，用中文概括本文的核心研究主题（100-200字）。\n"
    "要求：\n- 概括本文研究什么（核心研究对象/问题/方法主题），让人能据此判断与其它文献是否同类\n"
    "- 聚焦最能区分本文的主题特征，不要堆砌细节，不要写 related work\n"
    "只输出JSON：{\"topic\":\"中文研究主题描述\"}"
)


def get_routes(papers, glm):
    if CACHE_ROUTES.exists():
        cache = json.loads(CACHE_ROUTES.read_text(encoding="utf-8"))
        if len(cache) >= len(papers):
            return [cache[p["document_id"]] for p in papers]
    raise SystemExit("无抽取缓存，先跑 llm_cluster_large_test.py")


def build_intermediate(df, glm, bucket_size=40, random_state=42):
    """跑一次 bge编码→分桶→桶内微聚类，返回 (intermediate, M, n, B)。"""
    if CACHE_INTER.exists():
        d = json.loads(CACHE_INTER.read_text(encoding="utf-8"))
        inter = d["intermediate"]
        M = np.array(d["M"])
        return inter, M, d["n"], d["B"]

    text_col = "technical_route_text"
    doc_ids = [str(x) for x in df["document_id"].tolist()]
    n = len(doc_ids)
    routes = []
    for _, row in df.iterrows():
        r = str(row.get(text_col, "") or "").strip()
        routes.append(r or str(row.get("title", "") or "文献"))
    M = m3_encoder.encode(routes)
    B = max(2, -(-n // bucket_size)); B = min(B, n)
    bucket_labels = KMeans(n_clusters=B, n_init=10, random_state=random_state).fit_predict(M)
    intermediate = []
    for b in range(B):
        idxs = [i for i in range(n) if bucket_labels[i] == b]
        if not idxs:
            continue
        docs = [{"document_id": doc_ids[i], "title": "", "route": routes[i]} for i in idxs]
        mapping = _llm_cluster_docs(docs, glm, temp=0.3)
        lbl_to_idxs: dict[str, list[int]] = {}
        for i in idxs:
            lbl = mapping.get(doc_ids[i], "未分类")
            lbl_to_idxs.setdefault(lbl, []).append(i)
        for lbl, gidxs in lbl_to_idxs.items():
            intermediate.append({"label": lbl, "doc_indices": gidxs,
                                 "rep_route": routes[gidxs[0]]})
    CACHE_INTER.write_text(json.dumps(
        {"intermediate": intermediate, "M": M.tolist(), "n": n, "B": B},
        ensure_ascii=False), encoding="utf-8")
    return intermediate, M, n, B


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


def eval_groups(groups, n, doc_ids, papers):
    gold = [p["gold"] for p in papers]
    id2algo = {}
    for gi, g in enumerate(groups):
        for i in g["doc_indices"]:
            id2algo[doc_ids[i]] = g["label"]
    algo = [id2algo.get(p["document_id"], "未分类") for p in papers]
    return {
        "k": len(groups),
        "ari": adjusted_rand_score(gold, algo),
        "nmi": normalized_mutual_info_score(gold, algo),
        "hom": homogeneity_score(gold, algo),
        "comp": completeness_score(gold, algo),
        "vm": v_measure_score(gold, algo),
        "pur": purity(gold, algo),
        "biggest": Counter(algo).most_common(1)[0][1],
    }


def main():
    gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
    papers = gold_data["papers"]
    glm = GLMClient()
    routes = get_routes(papers, glm)
    df = pd.DataFrame({"document_id": [p["document_id"] for p in papers],
                       "title": [""] * len(papers), "technical_route_text": routes})
    doc_ids = [str(x) for x in df["document_id"].tolist()]

    print("构建中间簇（分桶→微聚类，缓存）...")
    t0 = time.time()
    intermediate, M, n, B = build_intermediate(df, glm)
    print(f"  桶={B} 中间簇={len(intermediate)}  {time.time()-t0:.0f}s")

    thresholds = [0.78, 0.80, 0.82, 0.84, 0.86, 0.88, 0.90, 0.92]
    print(f"\n{'thresh':>7} {'k':>4} {'ARI':>7} {'NMI':>7} {'hom':>7} {'comp':>7} {'V':>7} {'pur':>7} {'max':>5}")
    print("-" * 66)
    best = None
    for th in thresholds:
        groups = _merge_clusters(intermediate, M, threshold=th, glm_client=None)  # 不命名，快
        r = eval_groups(groups, n, doc_ids, papers)
        print(f"{th:>7.2f} {r['k']:>4} {r['ari']:>7.3f} {r['nmi']:>7.3f} "
              f"{r['hom']:>7.3f} {r['comp']:>7.3f} {r['vm']:>7.3f} {r['pur']:>7.3f} {r['biggest']:>5}")
        if best is None or r["ari"] > best["ari"]:
            best = {"th": th, **r}
    print("-" * 66)
    print(f"最优: th={best['th']:.2f}  ARI={best['ari']:.3f}  NMI={best['nmi']:.3f}  k={best['k']}")

    # 最优阈值下带 LLM 命名，看分布
    print(f"\n=== 最优阈值 {best['th']:.2f} + LLM 命名 ===")
    groups = _merge_clusters(intermediate, M, threshold=best["th"], glm_client=glm)
    gold = [p["gold"] for p in papers]
    id2algo = {}
    for g in groups:
        for i in g["doc_indices"]:
            id2algo[doc_ids[i]] = g["label"]
    algo = [id2algo.get(p["document_id"], "未分类") for p in papers]
    print("算法簇分布:")
    for lbl, cnt in Counter(algo).most_common():
        print(f"  {lbl:18} {cnt}")
    print("\ngold→算法簇映射:")
    g2a = {}
    for p, a in zip(papers, algo):
        g2a.setdefault(p["gold"], Counter())[a] += 1
    for g in sorted(g2a, key=lambda x: -sum(g2a[x].values())):
        tops = g2a[g].most_common(2)
        tops_s = ", ".join(f"{k}({v})" for k, v in tops)
        print(f"  {g:14} → {tops_s}")


if __name__ == "__main__":
    main()
