"""用户方案测试：bge 递归二分到大类簇(≤50) → 簇内 LLM 挖小类。

不预设 k、不做跨簇合并。层次化 bge 二分保证同主题文献留在同一分支(完整性)，
LLM 在同质小簇内挖细主题(纯度)。
"""
from __future__ import annotations
import json, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)
from sklearn.metrics.pairwise import cosine_similarity

from infrastructure.llm.glm_client import GLMClient
from infrastructure.clustering.semantic_cluster import _llm_cluster_docs
from infrastructure.rag.m3_encoder import m3_encoder

gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
papers = gold_data["papers"]
gold = [p["gold"] for p in papers]
doc_ids = [p["document_id"] for p in papers]
id2gold = {p["document_id"]: p["gold"] for p in papers}
routes_by_id = json.loads(Path("/tmp/zh500_topic_routes.json").read_text(encoding="utf-8"))
routes = [routes_by_id[d] for d in doc_ids]
n = len(papers)
glm = GLMClient()

M = m3_encoder.encode(routes)
MAX_LEAF = 50  # 叶簇最大文献数（LLM可处理规模）


def bge_bisect(idxs, M, max_leaf=MAX_LEAF):
    """递归二分：idxs 组若 > max_leaf，用 bge agglomerative 劈成2，递归。返回叶簇列表。"""
    if len(idxs) <= max_leaf:
        return [idxs]
    sub = M[idxs]
    # 余弦距离二分
    cos = cosine_similarity(sub)
    dist = np.clip(1 - cos, 0, 2)
    np.fill_diagonal(dist, 0)
    try:
        lab = AgglomerativeClustering(n_clusters=2, metric="precomputed",
                                      linkage="average").fit_predict(dist)
    except Exception:
        lab = KMeans(n_clusters=2, n_init=10, random_state=42).fit_predict(sub)
    g0 = [idxs[i] for i in range(len(idxs)) if lab[i] == 0]
    g1 = [idxs[i] for i in range(len(idxs)) if lab[i] == 1]
    if not g0 or not g1:  # 劈不开，强制KMeans
        lab = KMeans(n_clusters=2, n_init=10, random_state=42).fit_predict(sub)
        g0 = [idxs[i] for i in range(len(idxs)) if lab[i] == 0]
        g1 = [idxs[i] for i in range(len(idxs)) if lab[i] == 1]
    return bge_bisect(g0, M, max_leaf) + bge_bisect(g1, M, max_leaf)


def llm_cluster_leaf(idxs, routes, glm):
    """叶簇内 LLM 聚类，返回 [{label, idxs}]。"""
    docs = [{"document_id": str(i), "title": "", "route": routes[i]} for i in idxs]
    mp = _llm_cluster_docs(docs, glm, temp=0.3)
    l2i = {}
    for i in idxs:
        l2i.setdefault(mp.get(str(i), "未分类"), []).append(i)
    return [{"label": lbl, "idxs": gi} for lbl, gi in l2i.items()]


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


# 1. 递归二分
print("bge 递归二分...")
leaves = bge_bisect(list(range(n)), M)
sizes = sorted(map(len, leaves), reverse=True)
print(f"叶簇数={len(leaves)} 大小={sizes[:20]}  max={sizes[0]} min={sizes[-1]}")

# 叶簇的 gold 纯度（看大类是否同类聚一起）
print("\n=== 叶簇 gold 纯度（验证大类是否同类聚一起）===")
purities = []
for lf in leaves:
    gs = [id2gold[doc_ids[i]] for i in lf]
    top, cnt = Counter(gs).most_common(1)[0]
    pur = cnt / len(gs)
    purities.append(pur)
print(f"  平均纯度={np.mean(purities):.3f}  纯叶(>0.7):{sum(1 for p in purities if p>0.7)}/{len(leaves)}")
# 各叶簇的主gold
print("  叶簇(主gold / 占比 / 大小):")
for lf in sorted(leaves, key=lambda x: -len(x))[:15]:
    gs = [id2gold[doc_ids[i]] for i in lf]
    top, cnt = Counter(gs).most_common(1)[0]
    print(f"    {top:14} {cnt}/{len(lf)}={100*cnt/len(lf):.0f}%  size={len(lf)}")

# 2. 每叶 LLM 细分
print("\n叶簇内 LLM 挖小类...")
t0 = time.time()
all_sub = []
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(llm_cluster_leaf, lf, routes, glm): lf for lf in leaves}
    for i, fut in enumerate(as_completed(futs), 1):
        all_sub.extend(fut.result())
        if i % 5 == 0:
            print(f"  {i}/{len(leaves)} ({time.time()-t0:.0f}s)")

# 3. 评估
algo = [-1]*n
for ci, s in enumerate(all_sub):
    for i in s["idxs"]:
        algo[i] = ci
ari = adjusted_rand_score(gold, algo)
nmi = normalized_mutual_info_score(gold, algo)
hom = homogeneity_score(gold, algo)
comp = completeness_score(gold, algo)
vm = v_measure_score(gold, algo)
pur = purity(gold, algo)
print(f"\n{'='*50}")
print(f"最终: k={len(all_sub)} ARI={ari:.3f} NMI={nmi:.3f} hom={hom:.3f} comp={comp:.3f} V={vm:.3f} pur={pur:.3f}  ({time.time()-t0:.0f}s)")

# 映射
print("\ngold→算法簇:")
g2a = {}
sub_label = {ci: s["label"] for ci, s in enumerate(all_sub)}
for p, a in zip(papers, algo):
    g2a.setdefault(p["gold"], Counter())[sub_label[a]] += 1
for g in sorted(g2a, key=lambda x: -sum(g2a[x].values())):
    tops = g2a[g].most_common(2)
    tot = sum(g2a[g].values())
    print(f"  {g:14} → {', '.join(f'{k}({v})' for k,v in tops)}  ({100*tops[0][1]/tot:.0f}%)")
