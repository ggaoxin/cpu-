"""递归 LLM 细分方案测试。

核心改进（回应用户想法）：
1. 用 bge 层次聚类的【自然组】替代 KMeans 均衡桶——同主题尽量同组，减少跨组碎片
2. 组内 LLM 聚类后，递归检查每个子簇是否仍混杂，混杂则再分，直到纯净
3. 跨组同主题簇：保守 LLM 成对合并（只合真同主题）

停止准则（无 gold）：LLM 自判"这组是否还含多个具体主题"。
"""
from __future__ import annotations
import json, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)
from sklearn.metrics.pairwise import cosine_similarity

from infrastructure.llm.glm_client import GLMClient
from infrastructure.clustering.semantic_cluster import _llm_cluster_docs, _LLM_CLUSTER_SYSP
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

SYSP_HOMO = (
    "你是科技文献主题分析专家。下面是若干篇文献的研究主题描述。请判断：\n"
    "它们是否都属于【同一个具体研究主题】（同一研究对象/问题）？\n"
    "- 若是同一主题（哪怕方法/角度不同），输出 {\"homogeneous\":true}\n"
    "- 若含2个及以上不同具体主题，输出 {\"homogeneous\":false,\"n_topics\":估计数}\n"
    "宁可判 homogeneous=false（倾向再分），只有确实同一对象/问题时才true。"
)


def llm_cluster_group(idxs, routes, glm, temp=0.3):
    """对一组 idx 做 LLM 聚类，返回 [{label, idxs}]。"""
    docs = [{"document_id": str(i), "title": "", "route": routes[i]} for i in idxs]
    mp = _llm_cluster_docs(docs, glm, temp=temp)
    l2i = {}
    for i in idxs:
        l2i.setdefault(mp.get(str(i), "未分类"), []).append(i)
    return [{"label": lbl, "idxs": gi} for lbl, gi in l2i.items()]


def is_homogeneous(idxs, routes, glm):
    if len(idxs) <= 2:
        return True
    listing = "\n".join(f"[{k}] {routes[i][:140]}" for k, i in enumerate(idxs[:30]))
    try:
        out = glm.chat_json(SYSP_HOMO, f"共{len(idxs)}篇：\n{listing}",
                            temperature=0.1, timeout=60.0, max_tokens=200)
        return bool(out.get("homogeneous", False))
    except Exception:
        return True


def recursive_split(idxs, routes, glm, depth=0, max_depth=4, min_size=4):
    """递归：LLM聚类 → 每子簇若不纯净且够大则再分。返回叶子簇列表。"""
    if len(idxs) <= min_size or depth >= max_depth:
        return [{"label": "leaf", "idxs": list(idxs)}]
    sub = llm_cluster_group(idxs, routes, glm)
    leaves = []
    for s in sub:
        if len(s["idxs"]) <= min_size:
            leaves.append(s)
        elif is_homogeneous(s["idxs"], routes, glm):
            leaves.append(s)
        else:
            leaves.extend(recursive_split(s["idxs"], routes, glm, depth+1, max_depth, min_size))
    return leaves


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


def eval_leaves(leaves):
    algo = [-1]*n
    for ci, lf in enumerate(leaves):
        for i in lf["idxs"]:
            algo[i] = ci
    return {
        "k": len(leaves),
        "ari": adjusted_rand_score(gold, algo),
        "nmi": normalized_mutual_info_score(gold, algo),
        "hom": homogeneity_score(gold, algo),
        "comp": completeness_score(gold, algo),
        "vm": v_measure_score(gold, algo),
        "pur": purity(gold, algo),
    }


# 1. bge 自然组（agglomerative，距离阈值使 max组≤50）
print("bge 自然组聚类...")
cos = cosine_similarity(M)
dist = np.clip(1 - cos, 0, 2)
np.fill_diagonal(dist, 0)
# 选阈值：从高到低，找到 max group ≤ 50 的
for th in [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]:
    agg = AgglomerativeClustering(n_clusters=None, metric="precomputed",
                                  linkage="average", distance_threshold=th)
    lab = agg.fit_predict(dist)
    sizes = Counter(lab)
    mx = max(sizes.values())
    print(f"  th={th}: 组数={len(sizes)} max组={mx}  mean={np.mean(list(sizes.values())):.1f}")

# 用 th=0.7（自然组，max组较大需递归处理）
TH = 0.7
agg = AgglomerativeClustering(n_clusters=None, metric="precomputed",
                              linkage="average", distance_threshold=TH)
lab = agg.fit_predict(dist)
groups = {}
for i in range(n):
    groups.setdefault(int(lab[i]), []).append(i)
group_lists = list(groups.values())
print(f"\n自然组={len(group_lists)} 大小={sorted(map(len,group_lists),reverse=True)[:15]}")

# 2. 每组递归 LLM 细分
print("\n递归 LLM 细分中...")
t0 = time.time()
all_leaves = []
# 大组(>50)需先LLM聚类再递归；小组直接递归
def process_group(gidx):
    return recursive_split(gidx, routes, glm)
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = [ex.submit(process_group, g) for g in group_lists]
    for i, fut in enumerate(as_completed(futs), 1):
        all_leaves.extend(fut.result())
        print(f"  组 {i}/{len(group_lists)} 完成 ({time.time()-t0:.0f}s)")

r = eval_leaves(all_leaves)
print(f"\n递归细分(无跨组合并): k={r['k']} ARI={r['ari']:.3f} NMI={r['nmi']:.3f} "
      f"hom={r['hom']:.3f} comp={r['comp']:.3f} V={r['vm']:.3f} pur={r['pur']:.3f}  ({time.time()-t0:.0f}s)")

# 分布 + 映射
algo = [-1]*n
for ci, lf in enumerate(all_leaves):
    for i in lf["idxs"]:
        algo[i] = ci
# LLM 命名 leaves（简略：用首篇route前20字）
print("\n叶子簇大小分布:", sorted(Counter(algo).values(), reverse=True)[:20])
g2a = {}
for p, a in zip(papers, algo):
    g2a.setdefault(p["gold"], Counter())[a] += 1
print("gold→主簇占比:")
for g in sorted(g2a, key=lambda x: -sum(g2a[x].values())):
    tops = g2a[g].most_common(1)
    tot = sum(g2a[g].values())
    print(f"  {g:14} → 簇{tops[0][0]}({tops[0][1]}/{tot}={100*tops[0][1]/tot:.0f}%)")
