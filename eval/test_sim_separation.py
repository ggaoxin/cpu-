"""测试不同语义相似度信号对同主题/不同主题的分离能力。

采样 same-gold 对(应高相似)和 diff-gold 对(应低相似)，比较：
- bge-m3 余弦(当前用)
- bge-large-zh-v1.5 余弦(中文专用双塔)
- bge-reranker 分数(若已下载，cross-encoder)
看哪个信号能让"同主题 vs 不同主题"分得开 → 决定合并该用哪个 + 是否存在优阈值。
"""
from __future__ import annotations
import json, random
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
papers = gold_data["papers"]
routes_by_id = json.loads(Path("/tmp/zh500_topic_routes.json").read_text(encoding="utf-8"))
routes = [routes_by_id[p["document_id"]] for p in papers]
gold = [p["gold"] for p in papers]
n = len(papers)
random.seed(0)

# 采样 same/diff 对
same, diff = [], []
idxs = list(range(n))
for _ in range(300):
    i, j = random.sample(idxs, 2)
    if gold[i] == gold[j] and routes[i] and routes[j]:
        same.append((i, j))
    elif gold[i] != gold[j] and routes[i] and routes[j]:
        diff.append((i, j))
same = same[:200]; diff = diff[:200]
print(f"采样: same={len(same)} diff={len(diff)}")


def sep(scores_same, scores_diff, name):
    s = np.array(scores_same); d = np.array(scores_diff)
    print(f"\n{name}:")
    print(f"  same: mean={s.mean():.3f} std={s.std():.3f}  [P10={np.percentile(s,10):.3f} P50={np.percentile(s,50):.3f} P90={np.percentile(s,90):.3f}]")
    print(f"  diff: mean={d.mean():.3f} std={d.std():.3f}  [P10={np.percentile(d,10):.3f} P50={np.percentile(d,50):.3f} P90={np.percentile(d,90):.3f}]")
    # AUC: same 应高于 diff
    combined = np.concatenate([s, d])
    labels = np.concatenate([np.ones(len(s)), np.zeros(len(d))])
    order = np.argsort(-combined)
    ranks = np.empty_like(order); ranks[order] = np.arange(1, len(combined)+1)
    pos = labels.sum(); neg = len(labels) - pos
    auc = (ranks[labels==1].sum() - pos*(pos+1)/2) / (pos*neg)
    # 找最优阈值(最大正确率)
    best_t, best_acc = 0, 0
    for t in np.linspace(combined.min(), combined.max(), 50):
        acc = ((s >= t).sum() + (d < t).sum()) / (len(s)+len(d))
        if acc > best_acc: best_acc, best_t = acc, t
    print(f"  AUC={auc:.3f}  最优阈值={best_t:.3f}(正确率{best_acc:.3f})  gap={s.mean()-d.mean():.3f}")
    return auc, best_t, best_acc


# bge-m3
print("加载 bge-m3...")
m3 = SentenceTransformer("models/bge-m3")
emb_m3 = m3.encode(routes, normalize_embeddings=True, show_progress_bar=False)
ss = [float(emb_m3[i] @ emb_m3[j]) for i, j in same]
dd = [float(emb_m3[i] @ emb_m3[j]) for i, j in diff]
sep(ss, dd, "bge-m3 余弦")

# bge-large-zh
print("加载 bge-large-zh-v1.5...")
lz = SentenceTransformer("models/bge-large-zh-v1.5")
emb_lz = lz.encode(routes, normalize_embeddings=True, show_progress_bar=False)
ss = [float(emb_lz[i] @ emb_lz[j]) for i, j in same]
dd = [float(emb_lz[i] @ emb_lz[j]) for i, j in diff]
sep(ss, dd, "bge-large-zh-v1.5 余弦")

# reranker (若已下载)
rp = Path("/tmp/reranker_path.txt")
if rp.exists():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch
    rpath = rp.read_text().strip()
    print(f"加载 reranker: {rpath}")
    tok = AutoTokenizer.from_pretrained(rpath)
    rmodel = AutoModelForSequenceClassification.from_pretrained(rpath)
    rmodel.eval()
    def rscore(a, b):
        with torch.no_grad():
            inp = tok(a, b, padding=True, truncation=True, max_length=512, return_tensors="pt")
            return float(rmodel(**inp).logits[0, 0])
    ss = [rscore(routes[i], routes[j]) for i, j in same]
    dd = [rscore(routes[i], routes[j]) for i, j in diff]
    sep(ss, dd, "bge-reranker-v2-m3")
else:
    print("\n(reranker 未下载完，跳过)")
