#!/usr/bin/env python3
"""相邻类目互串的两个修复方案离线实验。

方案A（类目合并）：统计双向混淆率——A 类文献高相似投给 B 的比例与 B→A 的
比例取 min，双向都高说明这条边界在向量空间里不可学（人看也是糊的），
合并掉。纯数据判定，不靠 GLM 拍脑袋。

方案B（判别器仲裁）：在 11.7 万已清洗标签上训练 softmax 判别头
（bge 向量 → 类目）。近邻投票给出 top-2 候选后，由判别器在候选间仲裁——
只在边界区改判，保留近邻证据结构。这是"学边界"与"查邻居"的混合。

输出：基线 vs A vs A+B 的测试集准确率对比，判别头权重与合并映射存盘。
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_anchor_fullscale import eval_gates, per_doc_stats  # noqa: E402
from scripts.self_review_gold import gpu_votes  # noqa: E402

OUT = PROJECT_ROOT / "output/anchor_full"
CACHE_STEM = PROJECT_ROOT / "rag_store/deep_clustering_anchor/anchors_5f36bedf3fb3253e"
MUTUAL_MERGE_FLOOR = 0.25   # 双向混淆率 ≥ 此值判定边界不可学，合并
VOTE_SIM = 0.75


def nn_accuracy(train_vecs, train_labels, test_vecs, test_labels):
    stats = per_doc_stats(test_vecs, train_vecs, train_labels.tolist())
    return eval_gates(stats, test_labels.tolist(), 0.45, 0.70)


def merge_unlearnable(train_vecs, train_labels, votes, name_of):
    """双向混淆率高的类目对合并（小并大，迭代至稳定）。"""
    size = defaultdict(int)
    for x in train_labels:
        size[x] += 1
    directed = defaultdict(int)
    for (best, _, _, best_sim), own in zip(votes, train_labels):
        if best_sim >= VOTE_SIM and best != own:
            directed[(str(own), str(best))] += 1
    pairs = []
    for (a, b), count in directed.items():
        if size[a] < 50 or size[b] < 50:
            continue
        rate_ab = count / size[a]
        rate_ba = directed.get((b, a), 0) / size[b]
        mutual = min(rate_ab, rate_ba)
        if mutual >= MUTUAL_MERGE_FLOOR:
            pairs.append((mutual, rate_ab, rate_ba, a, b))
    pairs.sort(reverse=True)
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    merged_pairs = []
    for mutual, rab, rba, a, b in pairs:
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        keep, drop = (ra, rb) if size[ra] >= size[rb] else (rb, ra)
        parent[rb] = keep
        size[keep] += size[rb]
        merged_pairs.append({"kept": keep, "merged": drop, "mutual": round(mutual, 3),
                             "kept_name": name_of.get(keep, keep),
                             "merged_name": name_of.get(drop, drop)})
    mapping = {x: find(x) for x in set(train_labels.tolist())}
    return mapping, merged_pairs


def train_head(train_vecs, train_labels, epochs=30):
    import torch
    classes = sorted(set(train_labels.tolist()))
    index = {c: i for i, c in enumerate(classes)}
    y = np.array([index[x] for x in train_labels])
    counts = np.bincount(y, minlength=len(classes))
    weights = torch.tensor(1.0 / np.sqrt(counts), dtype=torch.float32).cuda()
    weights = weights / weights.mean()
    model = torch.nn.Linear(1024, len(classes)).cuda()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    x_all = torch.from_numpy(train_vecs).cuda()
    y_all = torch.from_numpy(y).cuda()
    for epoch in range(epochs):
        perm = torch.randperm(len(x_all), device="cuda")
        total = 0.0
        for start in range(0, len(x_all), 8192):
            idx = perm[start:start + 8192]
            loss = loss_fn(model(x_all[idx]), y_all[idx])
            opt.zero_grad(); loss.backward(); opt.step()
            total += float(loss) * len(idx)
        if epoch % 10 == 9:
            print(f"    head epoch {epoch + 1}: loss={total / len(x_all):.4f}", flush=True)
    return model, classes


def head_predict(model, classes, vecs, batch=8192):
    import torch
    out = []
    with torch.no_grad():
        for start in range(0, len(vecs), batch):
            logits = model(torch.from_numpy(vecs[start:start + batch]).cuda())
            probs = torch.softmax(logits, dim=1).cpu().numpy()
            out.append(probs)
    probs = np.concatenate(out)
    pred = [classes[i] for i in probs.argmax(1)]
    return pred, probs


def main() -> None:
    meta = json.loads(CACHE_STEM.with_suffix(".json").read_text())
    train_vecs = np.load(CACHE_STEM.with_suffix(".npy"))
    train_labels = np.array(meta["labels"])
    taxonomy = json.loads((OUT / "taxonomy.json").read_text())["topics"]
    name_of = {t["topic_id"]: t["topic_name"] for t in taxonomy}
    test_rows = json.loads((OUT / "eval_test.json").read_text())
    test_labels = np.array([r["gold_topic_id"] for r in test_rows])

    import os
    import torch
    from sentence_transformers import SentenceTransformer
    device = os.environ.get("BGE_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[0] 测试集编码 {len(test_rows)} 条（{device}）…", flush=True)
    model_enc = SentenceTransformer(str(PROJECT_ROOT / "models" / "bge-m3"), device=device)
    test_vecs = model_enc.encode([r["text"][:2000] for r in test_rows], batch_size=256,
                                 show_progress_bar=False, normalize_embeddings=True,
                                 convert_to_numpy=True).astype(np.float32)
    del model_enc
    torch.cuda.empty_cache()

    baseline = nn_accuracy(train_vecs, train_labels, test_vecs, test_labels)
    print(f"[基线] 准确={baseline['accuracy']:.2%} 宏F1={baseline['macro_f1']}", flush=True)

    # ---- 方案A：不可学边界合并 ----
    print("[A] 训练库自投票 → 双向混淆分析…", flush=True)
    votes = gpu_votes(train_vecs, train_vecs, train_labels,
                      self_positions=list(range(len(train_labels))))
    mapping, merged_pairs = merge_unlearnable(train_vecs, train_labels, votes, name_of)
    train_labels_a = np.array([mapping.get(x, x) for x in train_labels])
    test_labels_a = np.array([mapping.get(x, x) for x in test_labels])
    print(f"    合并 {len(merged_pairs)} 对不可学边界：")
    for p in merged_pairs:
        print(f"      {p['merged_name']} → {p['kept_name']} (双向混淆 {p['mutual']})", flush=True)
    after_a = nn_accuracy(train_vecs, train_labels_a, test_vecs, test_labels_a)
    print(f"[A后] 准确={after_a['accuracy']:.2%} 宏F1={after_a['macro_f1']} "
          f"类目 {len(set(train_labels_a.tolist()))}", flush=True)

    # ---- 方案B：判别头 + 候选仲裁 ----
    print("[B] 训练 softmax 判别头…", flush=True)
    head, classes = train_head(train_vecs, train_labels_a, epochs=30)
    pred_all, probs_all = head_predict(head, classes, test_vecs)
    head_acc = float(np.mean(np.array(pred_all) == test_labels_a))
    print(f"[B-纯判别器] 准确={head_acc:.2%}", flush=True)

    # 仲裁版：候选 = 近邻 top1 + 判别器 top1，判别器概率高者胜
    nn_votes = gpu_votes(test_vecs, train_vecs, train_labels_a)
    class_index = {c: i for i, c in enumerate(classes)}
    arb_pred = []
    for (v1_label, _, _, _), prob in zip(nn_votes, probs_all):
        head_top = classes[int(prob.argmax())]
        cands = list(dict.fromkeys([v1_label, head_top]))
        if len(cands) == 1:
            arb_pred.append(cands[0])
        else:
            scores = {c: prob[class_index[c]] for c in cands}
            arb_pred.append(max(scores, key=scores.get))
    arb_acc = float(np.mean(np.array(arb_pred) == test_labels_a))
    print(f"[B-仲裁(近邻top1+判别top1取概率高者)] 准确={arb_acc:.2%}", flush=True)

    # 存档
    torch.save({"state_dict": head.state_dict(), "classes": classes},
               PROJECT_ROOT / "rules/deep_clustering/gold/discriminative_head.pt")
    (OUT / "report_boundary_fix.json").write_text(json.dumps({
        "baseline": baseline, "after_merge": after_a,
        "merge_pairs": merged_pairs,
        "pure_head_accuracy": round(head_acc, 4),
        "arbitrated_accuracy": round(arb_acc, 4),
        "categories_after_merge": len(classes),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[存档] report_boundary_fix.json + discriminative_head.pt", flush=True)


if __name__ == "__main__":
    main()
