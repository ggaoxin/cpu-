"""LLM 成对裁决合并测试。

核心思路（解决跨桶碎片化的完整性问题）：
- 微聚类产出中间簇（KMeans桶内LLM聚类，纯但跨桶碎）
- 对每个中间簇，取 bge 最相似的 top-K 候选簇
- LLM 成对裁决："这两簇是否同一具体研究主题？"（读双方rep_route，yes/no）
- 连通分量合并 → 最终簇

成对判断避免"自由合并"的大类聚合倾向；LLM读内容能判主题（小批量已证0.573）。
"""
from __future__ import annotations
import json, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)
from sklearn.metrics.pairwise import cosine_similarity

from infrastructure.llm.glm_client import GLMClient
from infrastructure.clustering.semantic_cluster import _llm_cluster_docs, _merge_clusters
from infrastructure.rag.m3_encoder import m3_encoder

CACHE_ROUTES = Path("/tmp/zh500_topic_routes.json")
CACHE_INTER = Path("/tmp/zh500_intermediate.json")

gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
papers = gold_data["papers"]
gold = [p["gold"] for p in papers]
doc_ids = [p["document_id"] for p in papers]
id2gold = {p["document_id"]: p["gold"] for p in papers}
routes_by_id = json.loads(CACHE_ROUTES.read_text(encoding="utf-8"))
routes = [routes_by_id[d] for d in doc_ids]
n = len(papers)
glm = GLMClient()

SYSP_PAIR = (
    "你是科技文献主题分析专家。下面是若干【簇对】，每对含两个簇的标签与代表路线。"
    "请判断每对的两个簇是否研究【同一具体主题】（同一研究对象/问题，仅方法/角度不同算同一）。\n"
    "- 同一具体主题 → same=true（如 '区域经济空间格局' 与 '区域产业集聚测度' 都研究区域经济格局→true）\n"
    "- 相关但不同具体主题 → same=false（如 '区域经济'≠'城市土地利用'≠'农业粮食'；"
    "'配电网规划'≠'配电网故障保护'；'电力设备'≠'故障诊断'）\n"
    "- 默认 false，只有确属同一具体对象/问题才 true\n"
    "输出JSON：{\"pairs\":[{\"id\":0,\"same\":false},...]}"
)


def build_intermediate():
    if CACHE_INTER.exists():
        d = json.loads(CACHE_INTER.read_text(encoding="utf-8"))
        return d["intermediate"], np.array(d["M"])
    M = m3_encoder.encode(routes)
    from sklearn.cluster import KMeans
    B = max(2, -(-n // 40)); B = min(B, n)
    bl = KMeans(n_clusters=B, n_init=10, random_state=42).fit_predict(M)
    inter = []
    for b in range(B):
        idxs = [i for i in range(n) if bl[i] == b]
        docs = [{"document_id": doc_ids[i], "title": "", "route": routes[i]} for i in idxs]
        mp = _llm_cluster_docs(docs, glm, temp=0.3)
        l2i = {}
        for i in idxs:
            l2i.setdefault(mp.get(doc_ids[i], "未分类"), []).append(i)
        for lbl, gi in l2i.items():
            inter.append({"label": lbl, "doc_indices": gi, "rep": routes[gi[0]]})
    CACHE_INTER.write_text(json.dumps({"intermediate": inter, "M": M.tolist()},
                                      ensure_ascii=False), encoding="utf-8")
    return inter, M


def pairwise_llm_merge(intermediate, M, glm, top_k=4, batch=20):
    K = len(intermediate)
    cents = np.array([M[c["doc_indices"]].mean(axis=0) for c in intermediate])
    cos = cosine_similarity(cents)
    # 每个簇取 top_k 最相似候选（排除自身）
    pair_set = set()
    for i in range(K):
        order = np.argsort(-cos[i])
        cnt = 0
        for j in order:
            j = int(j)
            if j == i:
                continue
            pair_set.add((min(i, j), max(i, j)))
            cnt += 1
            if cnt >= top_k:
                break
    pairs = sorted(pair_set)
    print(f"  候选簇对={len(pairs)} (top_k={top_k})")

    # 批量 LLM 裁决
    same_pairs = set()
    batches = [pairs[i:i+batch] for i in range(0, len(pairs), batch)]

    def ask(b):
        listing = "\n".join(
            f"[{k}] 簇A「{intermediate[a]['label']}」: {intermediate[a]['rep'][:110]}\n"
            f"    簇B「{intermediate[b_]['label']}」: {intermediate[b_]['rep'][:110]}"
            for k, (a, b_) in enumerate(b))
        try:
            out = glm.chat_json(SYSP_PAIR, f"共{len(b)}对：\n{listing}",
                                temperature=0.1, timeout=90.0, max_tokens=800)
            res = []
            for item in out.get("pairs", []):
                k = int(item.get("id", -1))
                if 0 <= k < len(b) and bool(item.get("same", False)):
                    res.append(b[k])
            return res
        except Exception as e:
            print(f"  batch失败: {e}")
            return []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(ask, b) for b in batches]
        for i, fut in enumerate(as_completed(futs), 1):
            for p in fut.result():
                same_pairs.add(p)
            if i % 5 == 0:
                print(f"    裁决 {i}/{len(batches)} ({time.time()-t0:.0f}s)")
    print(f"  LLM判同={len(same_pairs)}对 ({time.time()-t0:.0f}s)")

    # 连通分量
    parent = list(range(K))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b in same_pairs:
        parent[find(a)] = find(b)
    comp = {}
    for i in range(K):
        comp.setdefault(find(i), []).append(i)
    # 组装
    groups = []
    for cids in comp.values():
        di = []
        for c in cids:
            di.extend(intermediate[c]["doc_indices"])
        labels = [intermediate[c]["label"] for c in cids if intermediate[c]["label"]]
        lbl = Counter(labels).most_common(1)[0][0] if labels else "未分类"
        groups.append({"label": lbl, "doc_indices": di, "cids": cids})
    return groups


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


def eval_groups(groups):
    algo = [-1]*n
    for ci, g in enumerate(groups):
        for i in g["doc_indices"]:
            algo[i] = ci
    return {"k": len(groups), "ari": adjusted_rand_score(gold, algo),
            "nmi": normalized_mutual_info_score(gold, algo),
            "hom": homogeneity_score(gold, algo), "comp": completeness_score(gold, algo),
            "vm": v_measure_score(gold, algo), "pur": purity(gold, algo)}


print("构建中间簇...")
inter, M = build_intermediate()
print(f"中间簇={len(inter)}")
# 纯度
cg = [Counter(id2gold[doc_ids[i]] for i in c["doc_indices"]).most_common(1)[0][0] for c in inter]
pur_inter = np.mean([Counter(id2gold[doc_ids[i]] for i in c["doc_indices"]).most_common(1)[0][1]/len(c["doc_indices"]) for c in inter])
print(f"中间簇平均纯度={pur_inter:.3f}")

for tk in [3, 5, 8]:
    print(f"\n=== top_k={tk} LLM成对合并 ===")
    groups = pairwise_llm_merge(inter, M, glm, top_k=tk)
    r = eval_groups(groups)
    print(f"  k={r['k']} ARI={r['ari']:.3f} NMI={r['nmi']:.3f} hom={r['hom']:.3f} comp={r['comp']:.3f} V={r['vm']:.3f} pur={r['pur']:.3f}")

# 对比 bge 合并
base = _merge_clusters(inter, M, threshold=0.78, glm_client=None)
rb = eval_groups(base)
print(f"\n对比 bge0.78: k={rb['k']} ARI={rb['ari']:.3f} NMI={rb['nmi']:.3f} pur={rb['pur']:.3f}")
