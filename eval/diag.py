"""诊断：定位大批量聚类损失来源——中间簇(微聚类)纯度 vs 合并质量。

用已缓存中间簇 + gold：
1. 每个中间簇的 gold 纯度（主 gold 占比）→ 微聚类质量
2. "完美合并"上限：用 gold 作合并信号（同主gold的中间簇合并），算 ARI
   → 若上限高，说明瓶颈在合并（bge 乱合），LLM 裁决有空间
   → 若上限也低，说明中间簇本身不纯，瓶颈在分桶/微聚类
3. 边界对（cos 0.65-0.85）中同gold vs 不同gold分布 → LLM 裁决潜力
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             homogeneity_score, completeness_score)
from sklearn.metrics.pairwise import cosine_similarity

gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
papers = gold_data["papers"]
gold = [p["gold"] for p in papers]
doc_ids = [p["document_id"] for p in papers]
id2gold = {p["document_id"]: p["gold"] for p in papers}

d = json.loads(Path("/tmp/zh500_intermediate.json").read_text(encoding="utf-8"))
intermediate = d["intermediate"]
M = np.array(d["M"])
n = d["n"]
K = len(intermediate)
print(f"中间簇={K}  文档={n}  gold簇={len(set(gold))}")

# 1. 中间簇纯度
print("\n=== 1. 中间簇(微聚类)纯度 ===")
purities = []
cluster_gold = []  # 每个中间簇的主gold
for c in intermediate:
    golds = [id2gold[doc_ids[i]] for i in c["doc_indices"]]
    cnt = Counter(golds)
    top_gold, top_n = cnt.most_common(1)[0]
    pur = top_n / len(golds)
    purities.append(pur)
    cluster_gold.append(top_gold)
print(f"  平均纯度: {np.mean(purities):.3f}  纯簇(>0.8): {sum(1 for p in purities if p>0.8)}/{K}")
print(f"  纯度分布: <0.5:{sum(1 for p in purities if p<0.5)}  0.5-0.8:{sum(1 for p in purities if 0.5<=p<=0.8)}  >0.8:{sum(1 for p in purities if p>0.8)}")

# 中间簇直接当最终结果（不合并）的 ARI
labels_no_merge = [-1]*n
for ci, c in enumerate(intermediate):
    for i in c["doc_indices"]:
        labels_no_merge[i] = ci
print(f"  不合并(k={K}): ARI={adjusted_rand_score(gold, labels_no_merge):.3f} "
      f"NMI={normalized_mutual_info_score(gold, labels_no_merge):.3f} "
      f"hom={homogeneity_score(gold, labels_no_merge):.3f} "
      f"comp={completeness_score(gold, labels_no_merge):.3f}")

# 2. 完美合并上限：同主gold的中间簇合并
print("\n=== 2. 完美合并上限（同主gold合并，乐观估计）===")
parent = list(range(K))
def find(x):
    while parent[x]!=x:
        parent[x]=parent[parent[x]]; x=parent[x]
    return x
for i in range(K):
    for j in range(i+1, K):
        if cluster_gold[i] == cluster_gold[j]:
            parent[find(i)] = find(j)
comp = {}
for i in range(K):
    comp.setdefault(find(i), []).append(i)
perfect_labels = [-1]*n
for ci, members in enumerate(comp.values()):
    for mid in members:
        for i in intermediate[mid]["doc_indices"]:
            perfect_labels[i] = ci
print(f"  完美合并(k={len(comp)}): ARI={adjusted_rand_score(gold, perfect_labels):.3f} "
      f"NMI={normalized_mutual_info_score(gold, perfect_labels):.3f} "
      f"hom={homogeneity_score(gold, perfect_labels):.3f} "
      f"comp={completeness_score(gold, perfect_labels):.3f}")

# 3. 边界对分析
print("\n=== 3. 边界对（cos 0.65-0.85）LLM裁决潜力 ===")
cents = np.array([M[c["doc_indices"]].mean(axis=0) for c in intermediate])
cos = cosine_similarity(cents)
same_gold_pairs = 0
diff_gold_pairs = 0
boundary = []
for i in range(K):
    for j in range(i+1, K):
        c = cos[i,j]
        sg = cluster_gold[i] == cluster_gold[j]
        if 0.65 <= c <= 0.85:
            boundary.append((c, sg, i, j))
            if sg: same_gold_pairs += 1
            else: diff_gold_pairs += 1
print(f"  边界对总数: {len(boundary)}  同gold(应合): {same_gold_pairs}  不同gold(不应合): {diff_gold_pairs}")
# 更宽边界
for lo, hi in [(0.60,0.70),(0.70,0.80),(0.80,0.90),(0.85,0.95)]:
    s=d=0
    for i in range(K):
        for j in range(i+1,K):
            if lo<=cos[i,j]<hi:
                if cluster_gold[i]==cluster_gold[j]: s+=1
                else: d+=1
    tot=s+d
    print(f"  cos[{lo:.2f},{hi:.2f}): {tot}对, 同gold {s}({100*s/tot:.0f}%) 不同gold {d}({100*d/tot:.0f}%)")
