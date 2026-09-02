#!/usr/bin/env python3
"""重建应用轴视图向量体系（正确配方：库/查询/判别头统一到应用视图空间）。

1) 复现语料顺序 → 构造应用视图 → GPU 编码
2) 应用轴缓存 = 视图向量(train) + ZA 标签
3) 应用轴判别头 = 在(视图向量, ZA标签)上训练
4) 离线评测：查询侧同样用视图编码（与产线修复后的行为一致）
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/root/autodl-tmp/semantic_toolkit")
sys.path.insert(0, str(ROOT))

from scripts.build_anchor_fullscale import encode_all, eval_gates, per_doc_stats, load_corpus  # noqa: E402
from scripts.build_application_gold import application_views  # noqa: E402

slot = ROOT / "rules/deep_clustering/gold/anchor_gold_current.json"
slot_rows = json.loads(slot.read_text())
test_rows = json.loads((ROOT / "output/anchor_full/eval_test.json").read_text())

rows = load_corpus(ROOT.parent / "abstract.jsonl", 0)
id_to_pos = {r["document_id"]: i for i, r in enumerate(rows)}
train_pos = [id_to_pos[r["document_id"]] for r in slot_rows]
test_pos = [id_to_pos[r["document_id"]] for r in test_rows]
print(f"[0] 对齐: train={len(train_pos)} test={len(test_pos)}", flush=True)

views = application_views(rows)
vectors = encode_all(views)  # 全量视图向量（GPU）

train_vecs = vectors[np.array(train_pos)]
test_vecs = vectors[np.array(test_pos)]
train_labels = [r["application_cluster_id"] for r in slot_rows]
test_golds = [r["gold_application_topic_id"] for r in test_rows]

# 离线评测（查询=视图，与产线修复后一致）
nn = eval_gates(per_doc_stats(test_vecs, train_vecs, train_labels), test_golds, 0.45, 0.70)
print(f"[1] 视图配方离线: NN={nn['accuracy']:.2%} 宏F1={nn['macro_f1']}", flush=True)

from scripts.fix_boundary_confusion import head_predict, train_head  # noqa: E402

head, classes = train_head(train_vecs, np.array(train_labels), epochs=30)
pred, _ = head_predict(head, classes, test_vecs)
head_acc = float(np.mean(np.array(pred) == np.array(test_golds)))
print(f"[2] 视图配方判别头: {head_acc:.2%}", flush=True)

import torch  # noqa: E402
torch.save({"state_dict": head.state_dict(), "classes": classes},
           ROOT / "rules/deep_clustering/gold/discriminative_head_application.pt")

stat = slot.stat()
digest = hashlib.md5(
    f"{slot.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|application".encode()).hexdigest()[:16]
np.save(ROOT / f"rag_store/deep_clustering_anchor/anchors_{digest}.npy", train_vecs)
(ROOT / f"rag_store/deep_clustering_anchor/anchors_{digest}.json").write_text(
    json.dumps({"labels": train_labels,
                "doc_ids": [r["document_id"] for r in slot_rows]}, ensure_ascii=False),
    encoding="utf-8")
print(f"[3] 应用轴缓存重建（视图向量）: anchors_{digest}", flush=True)

report = json.loads((ROOT / "output/anchor_full/taxonomy_application.json").read_text())
report["recipe"] = "application_view (库/查询/判别头统一)"
report["nn_test_view_recipe"] = nn
report["head_test_view_recipe"] = round(head_acc, 4)
(ROOT / "output/anchor_full/taxonomy_application.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("[4] 报告已更新", flush=True)
