#!/usr/bin/env python3
"""低置信双候选阈值校准（双轴）。

验证假设：判别头 top-2 概率差小的"胶着区"，top-1 常错但 top-2 覆盖正确答案。
对每个候选阈值报告：胶着区占比 / 胶着区 top-1 准确率 / 胶着区 top-2 召回。
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/root/autodl-tmp/semantic_toolkit")
sys.path.insert(0, str(ROOT))

from scripts.build_application_gold import application_views  # noqa: E402
from scripts.build_anchor_fullscale import load_corpus  # noqa: E402

test_rows = json.loads((ROOT / "output/anchor_full/eval_test.json").read_text())
golds = np.array([r["gold_topic_id"] for r in test_rows])

import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

enc = SentenceTransformer(str(ROOT / "models/bge-m3"), device="cuda")

for axis, head_file, text_source in (
    ("technical", "discriminative_head.pt", "abstract"),
    ("application", "discriminative_head_application.pt", "view"),
):
    if text_source == "abstract":
        vecs = enc.encode([r["text"][:2000] for r in test_rows], batch_size=256,
                          show_progress_bar=False, normalize_embeddings=True,
                          convert_to_numpy=True).astype(np.float32)
    else:
        rows = load_corpus(ROOT.parent / "abstract.jsonl", 0)
        id_to_pos = {r["document_id"]: i for i, r in enumerate(rows)}
        views = application_views(rows)
        vecs = enc.encode([views[id_to_pos[r["document_id"]]] for r in test_rows],
                          batch_size=256, show_progress_bar=False,
                          normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
    ckpt = torch.load(ROOT / "rules/deep_clustering/gold" / head_file,
                      map_location="cpu", weights_only=False)
    head = torch.nn.Linear(1024, len(ckpt["classes"]))
    head.load_state_dict(ckpt["state_dict"]); head.eval()
    classes = list(ckpt["classes"])
    with torch.no_grad():
        probs = torch.softmax(head(torch.from_numpy(vecs)), dim=1).numpy()
    order = np.argsort(-probs, axis=1)
    p1 = probs[np.arange(len(probs)), order[:, 0]]
    p2 = probs[np.arange(len(probs)), order[:, 1]]
    gap = p1 - p2
    top1_right = classes[order[:, 0]][...] == golds if False else np.array(
        [classes[order[i, 0]] == golds[i] for i in range(len(golds))])
    top2_right = np.array([golds[i] in (classes[order[i, 0]], classes[order[i, 1]])
                           for i in range(len(golds))])
    overall = top1_right.mean()
    print(f"=== {axis} 轴（全量 top-1 = {overall:.2%}）===")
    for th in (0.10, 0.15, 0.20, 0.25, 0.30):
        mask = gap < th
        n = int(mask.sum())
        if n == 0:
            continue
        print(f"  gap<{th:.2f}: 胶着 {n} 篇({n/len(golds):.1%}) | "
              f"胶着区 top-1 {top1_right[mask].mean():.1%} | "
              f"胶着区 top-2 召回 {top2_right[mask].mean():.1%}")
    print()
