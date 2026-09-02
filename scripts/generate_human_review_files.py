#!/usr/bin/env python3
"""生成人工确认所需的两份文件（基于已缓存的锚点向量，GPU 加速）。

1. human_review_categories.csv — 类目审查表：92 类 × 每类 3 篇样例（类目级审查，
   杠杆最大：判断类目是否该合并/改名/拆分）
2. human_review_queue.csv — 高危标签队列：簇标签与近邻投票不一致、或 top-2 票数
   接近的训练集文献，按"最可能标错"排序取前 500（标签级修正，命中率远高于随机）

人工只需看这两个文件；anchor_train.json / eval_test.json 勿直接人工翻阅。
"""
import json
import random
from pathlib import Path

import numpy as np
import torch

ROOT = Path("/root/autodl-tmp/semantic_toolkit")
CACHE = ROOT / "rag_store/deep_clustering_anchor/anchors_dc506b4d2ba715d9"
OUT = ROOT / "output/anchor_full"

meta = json.loads((CACHE.with_suffix(".json")).read_text())
vecs = np.load(CACHE.with_suffix(".npy"))
labels = np.array(meta["labels"])
doc_ids = meta["doc_ids"]
print(f"锚点库: {vecs.shape[0]} 篇 / {len(set(labels.tolist()))} 类目")

train_rows = json.loads((ROOT / "output/anchor_full/anchor_train.json").read_text())
id2abstract = {r["document_id"]: r["ch_abstract"] for r in train_rows}
tax = {t["topic_id"]: t for t in json.loads((OUT / "taxonomy.json").read_text())["topics"]}
name_of = {tid: t["topic_name"] for tid, t in tax.items()}

# ---- GPU 逐块计算：每篇的近邻投票 vs 自身簇标签 + 裕度 ----
base = torch.from_numpy(vecs).cuda()
records = []  # (idx, own, best, best_sim, margin)
k = 5
for start in range(0, len(vecs), 2048):
    chunk = base[start:start + 2048]
    sims = chunk @ base.T
    rows = torch.arange(sims.shape[0], device=sims.device)
    cols = torch.arange(start, start + sims.shape[0], device=sims.device)
    sims[rows, cols] = -1.0  # 排除自身
    topv, topi = sims.topk(k, dim=1)
    topv, topi = topv.cpu().numpy(), topi.cpu().numpy()
    for r in range(len(topv)):
        votes = {}
        for j in range(k):
            lbl = labels[int(topi[r, j])]
            votes[lbl] = votes.get(lbl, 0.0) + float(topv[r, j])
        ranked = sorted(votes.items(), key=lambda kv: -kv[1])
        best_lbl, best_v = ranked[0]
        second_v = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = (best_v - second_v) / (best_v + second_v + 1e-9)
        records.append((start + r, labels[start + r], best_lbl, float(topv[r].max()), float(margin)))
    if start % 20480 == 0:
        print(f"  … {start}/{len(vecs)}")
del base
torch.cuda.empty_cache()

# ---- ① 高危队列：先取"标签与投票不一致"，再补"票数极接近"的边界样本 ----
disagree = [r for r in records if r[1] != r[2]]
borderline = sorted((r for r in records if r[1] == r[2] and r[4] < 0.10), key=lambda r: r[4])
queue = sorted(disagree, key=lambda r: -r[3])[:400] + borderline[:100]
with (OUT / "human_review_queue.csv").open("w", encoding="utf-8") as fh:
    fh.write("priority,document_id,当前类目,投票最强类目,最高相似度,票数裕度,摘要前150字\n")
    for i, (idx, own, best, sim, margin) in enumerate(queue, 1):
        did = doc_ids[idx]
        abstract = id2abstract.get(did, "")[:150].replace('"', "'").replace("\n", " ")
        fh.write(f"{i},{did},{name_of.get(own, own)}({own}),{name_of.get(best, best)}({best}),"
                 f"{sim:.3f},{margin:.3f},\"{abstract}\"\n")
print(f"① 高危队列: {len(queue)} 条（不一致 {len(disagree)} 中取 400 + 边界 100）"
      f" → human_review_queue.csv")

# ---- ② 类目审查表：每类 3 篇样例 ----
rng = random.Random(42)
by_cat = {}
for idx, own in enumerate(labels.tolist()):
    by_cat.setdefault(own, []).append(idx)
with (OUT / "human_review_categories.csv").open("w", encoding="utf-8") as fh:
    fh.write("topic_id,topic_name,size,cohesion,top_terms,sample1,sample2,sample3\n")
    for tid, t in sorted(tax.items(), key=lambda kv: -kv[1]["size"]):
        members = by_cat.get(tid, [])
        samples = rng.sample(members, min(3, len(members)))
        snippets = ["；".join(id2abstract.get(doc_ids[i], "")[:60].replace('"', "'").split("，")[:2])
                    for i in samples]
        fh.write(f"{tid},\"{t['topic_name']}\",{t['size']},{t['cohesion']},"
                 f"\"{'/'.join(t['top_terms'][:6])}\","
                 + ",".join(f"\"{s}\"" for s in snippets) + "\n")
print(f"② 类目审查表: {len(tax)} 类 × 3 样例 → human_review_categories.csv")
