"""对照实验：500篇全量一次LLM聚类（不分桶），看分层损失多大。

小批量(50篇)llm_cluster ARI=0.573。500篇一次若仍高→分层是不必要损失；
若也降到~0.3→LLM在500篇规模注意力也撑不住，必须分层但需改策略。
"""
from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path
import pandas as pd
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)
from infrastructure.llm.glm_client import GLMClient
from infrastructure.clustering.semantic_cluster import llm_cluster, _llm_cluster_docs

gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
papers = gold_data["papers"]
gold = [p["gold"] for p in papers]
doc_ids = [p["document_id"] for p in papers]
routes_by_id = json.loads(Path("/tmp/zh500_topic_routes.json").read_text(encoding="utf-8"))
routes = [routes_by_id[d] for d in doc_ids]

glm = GLMClient()


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


def report(algo, label):
    print(f"\n{label}: k={len(set(algo))} ARI={adjusted_rand_score(gold,algo):.3f} "
          f"NMI={normalized_mutual_info_score(gold,algo):.3f} "
          f"hom={homogeneity_score(gold,algo):.3f} comp={completeness_score(gold,algo):.3f} "
          f"V={v_measure_score(gold,algo):.3f} pur={purity(gold,algo):.3f}")


# 1. 全量 _llm_cluster_docs（500篇一次喂LLM）
print("全量500篇一次LLM聚类...")
docs = [{"document_id": did, "title": "", "route": r} for did, r in zip(doc_ids, routes)]
t0 = time.time()
mapping = _llm_cluster_docs(docs, glm, temp=0.3)
algo = [mapping.get(did, "未分类") for did in doc_ids]
report(algo, f"全量一次 _llm_cluster_docs ({time.time()-t0:.0f}s)")

# 2. llm_cluster（全量，含PCA等）
df = pd.DataFrame({"document_id": doc_ids, "title": [""]*len(papers),
                   "technical_route_text": routes})
print("\nllm_cluster(全量)...")
t0 = time.time()
res = llm_cluster(df, "technical", glm)
id2a = {doc_ids[i]: cl["topic_name"] for cl in res["clusters"] for i in cl["doc_indices"]}
algo2 = [id2a.get(did, "未分类") for did in doc_ids]
report(algo2, f"llm_cluster全量 ({time.time()-t0:.0f}s)")
