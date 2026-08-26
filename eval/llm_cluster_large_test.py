"""大批量分层聚类验证：500篇中文摘要 → 抽研究主题 → llm_cluster_large → 评测 vs gold。

测试用户设计的分桶→桶内LLM微聚类→LLM跨桶合并方案。
抽取用"研究主题"维度（与 gold 同维度，公平评测聚类管线质量）。
抽取结果缓存到 /tmp/zh500_topic_routes.json，重跑免重复调用。

用法: python eval/llm_cluster_large_test.py
"""
from __future__ import annotations
import json, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from infrastructure.llm.glm_client import GLMClient
from infrastructure.clustering.semantic_cluster import llm_cluster_large

CACHE = Path("/tmp/zh500_topic_routes.json")

SYSP_TOPIC = (
    "你是科技文献分析专家。阅读文献摘要，用中文概括本文的核心研究主题（100-200字）。\n"
    "要求：\n"
    "- 概括本文研究什么（核心研究对象/问题/方法主题），让人能据此判断与其它文献是否同类\n"
    "- 聚焦最能区分本文的主题特征，不要堆砌细节，不要写 related work\n"
    "只输出JSON：{\"topic\":\"中文研究主题描述\"}"
)


def extract_routes(papers, glm):
    if CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
        if len(cache) >= len(papers):
            print(f"命中抽取缓存 {len(cache)} 篇")
            return [cache[p["document_id"]] for p in papers]
    routes = {}
    cache = {} if not CACHE.exists() else json.loads(CACHE.read_text(encoding="utf-8"))

    def _one(p):
        did = p["document_id"]
        if did in cache:
            return did, cache[did]
        try:
            d = glm.chat_json(SYSP_TOPIC, f"摘要：\n{p['abstract'][:8000]}",
                              temperature=0.0, timeout=60.0, max_tokens=300)
            return did, (d.get("topic") or "").strip()
        except Exception as e:  # noqa: BLE001
            print(f"  抽取失败 {did}: {e}")
            return did, ""

    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_one, p) for p in papers]
        for fut in as_completed(futs):
            did, r = fut.result()
            routes[did] = r
            cache[did] = r
            done += 1
            if done % 50 == 0:
                print(f"  抽取 {done}/{len(papers)}  ({time.time()-t0:.0f}s)")
                CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"抽取完成 {len(routes)} 篇  {time.time()-t0:.0f}s")
    return [routes[p["document_id"]] for p in papers]


def _purity(gold, algo):
    clusters = {}
    for g, a in zip(gold, algo):
        clusters.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in clusters.values()) / len(gold)


def main():
    from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                                 v_measure_score, homogeneity_score, completeness_score)
    gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
    papers = gold_data["papers"]
    print(f"加载 {len(papers)} 篇, gold {gold_data['n_clusters']} 簇")

    glm = GLMClient()
    routes = extract_routes(papers, glm)
    empty = sum(1 for r in routes if not r)
    print(f"空 route: {empty}")

    df = pd.DataFrame({
        "document_id": [p["document_id"] for p in papers],
        "title": [""] * len(papers),
        "technical_route_text": routes,
    })

    print("\n运行 llm_cluster_large (分桶→微聚类→合并)...")
    t0 = time.time()
    res = llm_cluster_large(df, "technical", glm, bucket_size=40)
    print(f"聚类完成 {time.time()-t0:.0f}s")
    meta = res.get("_meta", {})
    print(f"  桶数={meta.get('buckets')} 中间簇={meta.get('intermediate_clusters')} 最终簇={res['k']}")

    doc_ids = [p["document_id"] for p in papers]
    id2algo = {}
    for cl in res["clusters"]:
        for i in cl["doc_indices"]:
            id2algo[doc_ids[i]] = cl["topic_name"]
    gold = [p["gold"] for p in papers]
    algo = [id2algo.get(p["document_id"], "未分类") for p in papers]

    ari = adjusted_rand_score(gold, algo)
    nmi = normalized_mutual_info_score(gold, algo)
    vm = v_measure_score(gold, algo)
    hom = homogeneity_score(gold, algo)
    comp = completeness_score(gold, algo)
    pur = _purity(gold, algo)

    print("\n" + "=" * 56)
    print("外部指标 (vs gold 22簇)")
    print("=" * 56)
    print(f"  ARI      : {ari:.3f}")
    print(f"  NMI      : {nmi:.3f}")
    print(f"  纯度     : {pur:.3f}")
    print(f"  同质性   : {hom:.3f}")
    print(f"  完整性   : {comp:.3f}")
    print(f"  V-measure: {vm:.3f}")
    print(f"  算法簇数 : {res['k']}  (gold 22)")

    print("\n算法簇分布 (top15):")
    for lbl, cnt in Counter(algo).most_common(15):
        print(f"  {lbl:16} {cnt}")
    print("\ngold 簇→算法簇映射 (主要):")
    g2a = {}
    for p, a in zip(papers, algo):
        g2a.setdefault(p["gold"], Counter())[a] += 1
    for g in sorted(g2a, key=lambda x: -sum(g2a[x].values()))[:12]:
        tops = g2a[g].most_common(2)
        tops_s = ", ".join(f"{k}({v})" for k, v in tops)
        print(f"  {g:14} → {tops_s}")


if __name__ == "__main__":
    main()
