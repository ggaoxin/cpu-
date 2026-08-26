"""簇级别分离度测试：合并决策是在【簇代表】间做的，不是文档对。

重建中间簇 → 对每对中间簇，用 bge-m3 余弦 vs bge-reranker 打分簇代表相似度，
看哪个信号能区分"同gold簇对(应合) vs 不同gold簇对(不应合)"。
若 reranker 在簇级别分得开 → 存在可用阈值，阈值合并可行。
"""
from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.cluster import KMeans
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

# 重建中间簇
M = m3_encoder.encode(routes)
B = max(2, -(-n // 40)); B = min(B, n)
bl = KMeans(n_clusters=B, n_init=10, random_state=42).fit_predict(M)
glm = GLMClient()
intermediate = []
print(f"分桶={B}，微聚类中...")
t0 = time.time()
for b in range(B):
    idxs = [i for i in range(n) if bl[i] == b]
    docs = [{"document_id": doc_ids[i], "title": "", "route": routes[i]} for i in idxs]
    mp = _llm_cluster_docs(docs, glm, temp=0.3)
    l2i = {}
    for i in idxs:
        l2i.setdefault(mp.get(doc_ids[i], "未分类"), []).append(i)
    for lbl, gi in l2i.items():
        intermediate.append({"label": lbl, "doc_indices": gi, "rep": routes[gi[0]]})
print(f"中间簇={len(intermediate)}  {time.time()-t0:.0f}s")

K = len(intermediate)
cluster_gold = []
for c in intermediate:
    gs = [id2gold[doc_ids[i]] for i in c["doc_indices"]]
    cluster_gold.append(Counter(gs).most_common(1)[0][0])

# bge 簇心余弦
cents = np.array([M[c["doc_indices"]].mean(axis=0) for c in intermediate])
cents = cents / (np.linalg.norm(cents, axis=1, keepdims=True) + 1e-9)
cos = cents @ cents.T

# 采样簇对（全量K*(K-1)/2 可能多，采样）
pairs = []
for i in range(K):
    for j in range(i+1, K):
        pairs.append((i, j))
print(f"簇对总数={len(pairs)}")

# bge 分离
bge_same = [cos[i, j] for i, j in pairs if cluster_gold[i] == cluster_gold[j]]
bge_diff = [cos[i, j] for i, j in pairs if cluster_gold[i] != cluster_gold[j]]
print(f"\n=== bge-m3 簇心余弦 (同gold {len(bge_same)} / 不同gold {len(bge_diff)}) ===")
print(f"  同gold: mean={np.mean(bge_same):.3f} P50={np.percentile(bge_same,50):.3f} P90={np.percentile(bge_same,90):.3f}")
print(f"  不同gold: mean={np.mean(bge_diff):.3f} P50={np.percentile(bge_diff,50):.3f} P90={np.percentile(bge_diff,90):.3f}")

# reranker 簇代表对（采样，reranker慢）
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch
rpath = "/root/autodl-tmp/modelscope/models/models/BAAI--bge-reranker-v2-m3/snapshots/master"
tok = AutoTokenizer.from_pretrained(rpath)
rmodel = AutoModelForSequenceClassification.from_pretrained(rpath)
rmodel.eval()
def rscore(a, b):
    with torch.no_grad():
        inp = tok(a, b, padding=True, truncation=True, max_length=256, return_tensors="pt")
        return float(rmodel(**inp).logits[0, 0])

# 对每对用两个 rep_route 互打分取max（rep可能不代表全簇）
import random
random.seed(1)
sample_pairs = random.sample(pairs, min(300, len(pairs)))
rr_same, rr_diff = [], []
for i, j in sample_pairs:
    s = max(rscore(intermediate[i]["rep"], intermediate[j]["rep"]),
            rscore(intermediate[j]["rep"], intermediate[i]["rep"]))
    if cluster_gold[i] == cluster_gold[j]: rr_same.append(s)
    else: rr_diff.append(s)
print(f"\n=== bge-reranker 簇代表 (同gold {len(rr_same)} / 不同gold {len(rr_diff)}) ===")
print(f"  同gold: mean={np.mean(rr_same):.3f} P10={np.percentile(rr_same,10):.3f} P50={np.percentile(rr_same,50):.3f} P90={np.percentile(rr_same,90):.3f}")
print(f"  不同gold: mean={np.mean(rr_diff):.3f} P10={np.percentile(rr_diff,10):.3f} P50={np.percentile(rr_diff,50):.3f} P90={np.percentile(rr_diff,90):.3f}")
# 分离度：同gold P10 vs 不同gold P90 越分开越好
print(f"  gap(同mean-不同mean)={np.mean(rr_same)-np.mean(rr_diff):.3f}")
