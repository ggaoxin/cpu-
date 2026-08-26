"""滑动窗口 + 锚点重叠 LLM 聚类。

- 预排序：bge PCA-1 投影排序，让相似文献相邻（窗口内尽量同类）
- 滑窗：窗口50，步长30，重叠20篇锚点
- 每窗 LLM 聚类全部50篇（≤50，质量好）
- 跨窗连通：两窗口的簇若共享≥1篇锚点文献 → 同一最终簇（集合关系，不需LLM判断）
  同主题跨窗靠锚点自动连通 → 完整性；LLM窗内聚类 → 纯度
- 不预设k，不需跨桶合并
"""
from __future__ import annotations
import json, time
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from sklearn.decomposition import PCA
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)

from infrastructure.llm.glm_client import GLMClient
from infrastructure.clustering.semantic_cluster import _LLM_CLUSTER_SYSP
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

# 1. 预排序：PCA-1
print("bge编码 + PCA排序...")
M = m3_encoder.encode(routes)
pca1 = PCA(n_components=1, random_state=42).fit_transform(M)[:, 0]
order = np.argsort(pca1)  # 相似文献相邻
routes_o = [routes[i] for i in order]
orig_idx = list(order)  # 排序后位置→原始idx

WIN, STEP = 50, 30
OVERLAP = WIN - STEP


def llm_cluster_window(win_routes):
    listing = "\n".join(f"[{i}] {r[:150]}" for i, r in enumerate(win_routes))
    try:
        out = glm.chat_json(_LLM_CLUSTER_SYSP, f"文献列表（共{len(win_routes)}篇）：\n{listing}",
                            temperature=0.2, timeout=90.0, max_tokens=2500)
    except Exception:
        out = {"clusters": []}
    lab = ["未分类"] * len(win_routes)
    for cl in out.get("clusters", []):
        lbl = (cl.get("label") or "").strip() or "未分类"
        for idx in cl.get("indices", []):
            try:
                p = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= p < len(win_routes):
                lab[p] = lbl
    return lab


# 2. 滑窗聚类，记录每篇在每窗的簇标签
# 全局簇id：用 (window_id, local_label) 作为节点，共享文献的节点连通
print(f"滑窗聚类 WIN={WIN} STEP={STEP} OVERLAP={OVERLAP}...")
t0 = time.time()
# paper_global_clusters: 每篇文献在各窗口被分到的 (win, label)
paper_wins = defaultdict(list)  # orig_idx -> list of (win_id, label)
windows = []
wi = 0
s = 0
while s < n:
    e = min(s + WIN, n)
    win_routes = routes_o[s:e]
    labs = llm_cluster_window(win_routes)
    windows.append((s, e, labs))
    for pos in range(s, e):
        paper_wins[orig_idx[pos]].append((wi, labs[pos - s]))
    wi += 1
    if e >= n:
        break
    s += STEP
print(f"  {wi}个窗口 ({time.time()-t0:.0f}s)")

# 3. 连通：每个窗口的每个label是一个节点 (win_id,label)。
#    若两节点共享≥1篇文献 → 连通（同一最终簇）
nodes = set()
for pls in paper_wins.values():
    for nd in pls:
        nodes.add(nd)
node_list = list(nodes)
nidx = {nd: i for i, nd in enumerate(node_list)}
parent = list(range(len(node_list)))

def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x

# 每篇文献连接它所属的所有节点
for pls in paper_wins.values():
    ns = [nidx[nd] for nd in pls if nd in nidx]
    for k in range(1, len(ns)):
        parent[find(ns[0])] = find(ns[k])

# 4. 每篇文献 → 最终簇 = 其节点的根
final_cluster = [-1] * n
root_to_cid = {}
cid = 0
for i in range(n):
    pls = paper_wins.get(i, [])
    if not pls:
        final_cluster[i] = -1
        continue
    r = find(nidx[pls[0]])
    if r not in root_to_cid:
        root_to_cid[r] = cid; cid += 1
    final_cluster[i] = root_to_cid[r]

# 簇标签：每簇取其成员所有窗口标签的众数
member_labels = defaultdict(list)
for i in range(n):
    for (_, lbl) in paper_wins.get(i, []):
        member_labels[final_cluster[i]].append(lbl)
cid_label = {c: Counter(v).most_common(1)[0][0] if v else "未分类" for c, v in member_labels.items()}


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


algo = [cid_label.get(final_cluster[i], "未分类") for i in range(n)]
ari = adjusted_rand_score(gold, algo)
nmi = normalized_mutual_info_score(gold, algo)
hom = homogeneity_score(gold, algo)
comp = completeness_score(gold, algo)
vm = v_measure_score(gold, algo)
pur = purity(gold, algo)
print(f"\n{'='*50}")
print(f"滑窗+锚点: k={len(set(algo))} ARI={ari:.3f} NMI={nmi:.3f} "
      f"hom={hom:.3f} comp={comp:.3f} V={vm:.3f} pur={pur:.3f}  ({time.time()-t0:.0f}s)")

print("\n簇分布(top25):")
for lbl, cnt in Counter(algo).most_common(25):
    print(f"  {lbl:18} {cnt}")
print("\ngold→算法簇:")
g2a = {}
for p, a in zip(papers, algo):
    g2a.setdefault(p["gold"], Counter())[a] += 1
for g in sorted(g2a, key=lambda x: -sum(g2a[x].values())):
    tops = g2a[g].most_common(2)
    tot = sum(g2a[g].values())
    print(f"  {g:14} → {', '.join(f'{k}({v})' for k,v in tops)}  ({100*tops[0][1]/tot:.0f}%)")
