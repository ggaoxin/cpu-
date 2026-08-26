"""LLM验证的凝聚式合并（簇数自然涌现，无预设k、无阈值）。

每轮：bge提议每簇的最近邻候选对 → LLM读双方内容判"合并后是否同一主题" →
通过则合（连通分量）→ 不通过的簇对标黑名单 → 无通过时停止。
bge只排序不裁决，LLM只判单对不自由合并 → 绕开各自短板。
"""
from __future__ import annotations
import json, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans

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

CACHE_INTER = Path("/tmp/zh500_intermediate_v2.json")

SYSP_MERGE = (
    "你是科技文献主题分析专家。下面是若干【簇对】，每对含两个簇的标签与代表路线。"
    "判断：这两簇合并后，是否仍属于【同一具体研究主题】（同一研究对象/问题，方法/角度不同算同一）？\n"
    "- 是同一具体主题（如 区域经济空间格局 与 区域产业集聚演化 都研究区域经济格局）→ merge=true\n"
    "- 相关但不同具体主题（区域经济≠城市土地≠农业；配电网规划≠配电网故障保护；电力设备≠故障诊断）→ merge=false\n"
    "客观判断，不要默认false。输出JSON：{\"pairs\":[{\"id\":0,\"merge\":true},...]}"
)


def build_intermediate():
    if CACHE_INTER.exists():
        d = json.loads(CACHE_INTER.read_text(encoding="utf-8"))
        return d["intermediate"], np.array(d["M"])
    M = m3_encoder.encode(routes)
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


def llm_agglomerative(intermediate, M, glm, max_rounds=15):
    """LLM验证凝聚式合并。返回最终组列表。"""
    # 当前活动簇：用id引用intermediate，但合并后组可能含多个intermediate簇
    # 用 union-find 在 intermediate id 上
    K = len(intermediate)
    cents = np.array([M[c["doc_indices"]].mean(axis=0) for c in intermediate])
    cents_n = cents / (np.linalg.norm(cents, axis=1, keepdims=True) + 1e-9)
    parent = list(range(K))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def group_info(gid):
        cids = [i for i in range(K) if find(i) == gid]
        di = []
        for c in cids:
            di.extend(intermediate[c]["doc_indices"])
        labels = [intermediate[c]["label"] for c in cids]
        reps = [intermediate[c]["rep"] for c in cids]
        lbl = Counter(labels).most_common(1)[0][0] if labels else "未分类"
        return lbl, di, reps

    blocked = set()  # (a,b) 已判不合

    for rnd in range(max_rounds):
        # 当前组id列表
        gids = list({find(i) for i in range(K)})
        # 计算组心
        g_cent = {}
        for g in gids:
            cids = [i for i in range(K) if find(i) == g]
            v = cents[cids].mean(axis=0)
            g_cent[g] = v / (np.linalg.norm(v) + 1e-9)
        # 每组找最近邻组（排除黑名单）
        candidates = set()
        for g in gids:
            best, best_sim = -1, -1
            for g2 in gids:
                if g2 == g:
                    continue
                key = (min(g, g2), max(g, g2))
                if key in blocked:
                    continue
                s = float(g_cent[g] @ g_cent[g2])
                if s > best_sim:
                    best_sim, best = s, g2
            if best >= 0:
                candidates.add((min(g, best), max(g, best), best_sim))
        if not candidates:
            print(f"  round{rnd}: 无候选，停止")
            break
        cands = sorted(candidates, key=lambda x: -x[2])
        # 批量LLM判
        def ask(batch):
            listing = "\n".join(
                f"[{k}] A「{group_info(a)[0]}」: {group_info(a)[2][0][:100]}\n"
                f"    B「{group_info(b)[0]}」: {group_info(b)[2][0][:100]}"
                for k, (a, b, _) in enumerate(batch))
            try:
                out = glm.chat_json(SYSP_MERGE, f"共{len(batch)}对：\n{listing}",
                                    temperature=0.1, timeout=90.0, max_tokens=600)
                res = []
                for item in out.get("pairs", []):
                    k = int(item.get("id", -1))
                    if 0 <= k < len(batch) and bool(item.get("merge", False)):
                        res.append((batch[k][0], batch[k][1]))
                return res
            except Exception:
                return []
        merged = 0
        BATCH = 20
        batches = [cands[i:i+BATCH] for i in range(0, len(cands), BATCH)]
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = [ex.submit(ask, b) for b in batches]
            for fut in as_completed(futs):
                for a, b in fut.result():
                    parent[find(a)] = find(b)
                    merged += 1
        # 标记本轮未合的为黑名单
        for a, b, _ in cands:
            if find(a) != find(b):
                blocked.add((a, b))
        ng = len({find(i) for i in range(K)})
        print(f"  round{rnd}: 候选{len(cands)} 合并{merged} 剩余组{ng} 黑名单{len(blocked)}")
        if merged == 0:
            break
    # 组装
    comp = {}
    for i in range(K):
        comp.setdefault(find(i), []).append(i)
    groups = []
    for cids in comp.values():
        di = []
        for c in cids:
            di.extend(intermediate[c]["doc_indices"])
        labels = [intermediate[c]["label"] for c in cids if intermediate[c]["label"]]
        lbl = Counter(labels).most_common(1)[0][0] if labels else "未分类"
        groups.append({"label": lbl, "doc_indices": di})
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


print("构建中间簇（无数量预设prompt）...")
inter, M = build_intermediate()
print(f"中间簇={len(inter)}")
pur = np.mean([Counter(id2gold[doc_ids[i]] for i in c["doc_indices"]).most_common(1)[0][1]/len(c["doc_indices"]) for c in inter])
print(f"中间簇纯度={pur:.3f}")

print("\nLLM验证凝聚式合并...")
t0 = time.time()
groups = llm_agglomerative(inter, M, glm)
r = eval_groups(groups)
print(f"\n结果: k={r['k']} ARI={r['ari']:.3f} NMI={r['nmi']:.3f} "
      f"hom={r['hom']:.3f} comp={r['comp']:.3f} V={r['vm']:.3f} pur={r['pur']:.3f}  ({time.time()-t0:.0f}s)")

# 分布 + 映射
algo = [-1]*n
for ci, g in enumerate(groups):
    for i in g["doc_indices"]:
        algo[i] = ci
print("\n算法簇分布:")
g2label = {ci: g["label"] for ci, g in enumerate(groups)}
for ci, cnt in Counter(algo).most_common(15):
    print(f"  {g2label[ci]:18} {cnt}")
print("\ngold→算法簇:")
g2a = {}
for p, a in zip(papers, algo):
    g2a.setdefault(p["gold"], Counter())[g2label[a]] += 1
for g in sorted(g2a, key=lambda x: -sum(g2a[x].values())):
    tops = g2a[g].most_common(2)
    print(f"  {g:14} → {', '.join(f'{k}({v})' for k,v in tops)}")
