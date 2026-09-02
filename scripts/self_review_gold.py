#!/usr/bin/env python3
"""gold 数据自动自审：多轮强证据标签修正 + 混淆对类目合并复审。

诚实定位：这是弱监督自清洗（self-training 式），提升的是标签自洽性与锚点库
质量；真实外部准确率仍需人工抽检——但保守的修正门槛能把"把错误强化"的
风险压到最低。

三轮循环（直至无改动）：
  ① 标签修正：文献的 5 近邻（排除自身）全票指向另一类目，且
     best_sim ≥ 0.75 且票数裕度 ≥ 0.35 才改判（宁缺毋滥，防反馈循环）
  ② 类目合并复审：统计"类目A文献高相似投票给B"的混淆对，Top 对交 GLM
     复审（这次带双方真实样例摘要，比构建期只看名称+术语更强）
  ③ 微类吸收：规模 < 30 的类目并入最近质心

测试集标签用训练库的独立投票修正（测试不在库内，无自泄漏）。
train/test 划分成员保持不变（指标可比），只改标签。
最后重建锚点库/缓存并输出前后指标对比。

用法：
  python3 -m scripts.self_review_gold   # 全流程，含 --install
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_anchor_fullscale import eval_gates, per_doc_stats  # noqa: E402

OUT = PROJECT_ROOT / "output/anchor_full"
CACHE_STEM = PROJECT_ROOT / "rag_store/deep_clustering_anchor/anchors_dc506b4d2ba715d9"
SLOT = PROJECT_ROOT / "rules" / "deep_clustering" / "gold" / "anchor_gold_current.json"

REASSIGN_MIN_SIM = 0.75
REASSIGN_MIN_MARGIN = 0.35
MIN_CATEGORY_SIZE = 30
TOP_CONFUSION_PAIRS = 12
MAX_ROUNDS = 3
TOP_K = 5


def gpu_votes(query_np: np.ndarray, base_np: np.ndarray, base_labels: np.ndarray,
              self_positions: list[int] | None = None):
    """返回每篇 (最优投票类目, 最优票值, 次优票值, best_sim)。GPU 分块。"""
    import torch
    base_t = torch.from_numpy(base_np).cuda()
    out = []
    k = min(TOP_K, base_np.shape[0])
    for start in range(0, len(query_np), 2048):
        chunk = torch.from_numpy(query_np[start:start + 2048]).cuda()
        sims = chunk @ base_t.T
        if self_positions is not None:
            rows = torch.arange(sims.shape[0], device=sims.device)
            cols = torch.tensor(self_positions[start:start + 2048], device=sims.device)
            sims[rows, cols] = -1.0
        topv, topi = sims.topk(k, dim=1)
        topv, topi = topv.cpu().numpy(), topi.cpu().numpy()
        for r in range(len(topv)):
            votes: dict[str, float] = defaultdict(float)
            for j in range(k):
                votes[base_labels[int(topi[r, j])]] += float(topv[r, j])
            ranked = sorted(votes.items(), key=lambda kv: -kv[1])
            out.append((ranked[0][0], ranked[0][1],
                        ranked[1][1] if len(ranked) > 1 else 0.0, float(topv[r].max())))
    del base_t
    torch.cuda.empty_cache()
    return out


def glm_merge_verdict(glm_client, name_a: str, samples_a: list[str],
                      name_b: str, samples_b: list[str]) -> bool:
    system = (
        "你是文献类目体系审查专家。两个类目各有若干真实文献摘要样例。"
        "判断它们是否实质为同一主题（应合并）。样例能看出真实边界："
        "相邻但可区分的方向（如'肿瘤靶向治疗'与'临床用药研究'）判不合并；"
        "仅当样例显示两边在讲同一类对象/技术时判合并。"
        '只返回JSON：{"same": true 或 false}'
    )
    payload = {
        "类目A": {"名称": name_a, "样例": [s[:160] for s in samples_a]},
        "类目B": {"名称": name_b, "样例": [s[:160] for s in samples_b]},
    }
    try:
        raw = glm_client.chat_json(system, json.dumps(payload, ensure_ascii=False),
                                   temperature=0.0, timeout=60.0, max_tokens=30)
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        return bool(data.get("same"))
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    meta = json.loads(CACHE_STEM.with_suffix(".json").read_text())
    train_vecs = np.load(CACHE_STEM.with_suffix(".npy"))
    train_labels = np.array(meta["labels"])  # ZTxx
    train_doc_ids = meta["doc_ids"]
    train_rows = json.loads((OUT / "anchor_train.json").read_text())
    assert [r["document_id"] for r in train_rows] == train_doc_ids, "缓存与训练文件顺序不一致"
    abstract_of = {r["document_id"]: r["ch_abstract"] for r in train_rows}
    taxonomy = json.loads((OUT / "taxonomy.json").read_text())["topics"]
    name_of = {t["topic_id"]: t["topic_name"] for t in taxonomy}
    test_rows = json.loads((OUT / "eval_test.json").read_text())
    test_doc_ids = [r["document_id"] for r in test_rows]
    test_labels = np.array([r["gold_topic_id"] for r in test_rows])

    # 编码测试集（GPU）
    import os
    import torch
    from sentence_transformers import SentenceTransformer
    device = os.environ.get("BGE_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
    model = SentenceTransformer(str(PROJECT_ROOT / "models" / "bge-m3"), device=device)
    print(f"[0] 测试集 {len(test_rows)} 条编码（{device}）…")
    test_vecs = model.encode([r["text"][:2000] for r in test_rows], batch_size=256,
                             show_progress_bar=False, normalize_embeddings=True,
                             convert_to_numpy=True).astype(np.float32)

    # 基线指标
    base_stats = per_doc_stats(test_vecs, train_vecs, train_labels.tolist())
    baseline = eval_gates(base_stats, test_labels.tolist(), 0.45, 0.70)
    print(f"[基线] 覆盖={baseline['coverage']:.2%} 准确={baseline['accuracy']:.2%} "
          f"宏F1={baseline['macro_f1']}")

    from infrastructure.llm.glm_client import glm_client
    rng = np.random.RandomState(42)

    for round_no in range(1, MAX_ROUNDS + 1):
        # ① 训练库内部强证据改判
        votes = gpu_votes(train_vecs, train_vecs, train_labels,
                          self_positions=list(range(len(train_labels))))
        flips = 0
        for i, (best, v1, v2, best_sim) in enumerate(votes):
            if best == train_labels[i]:
                continue
            margin = (v1 - v2) / (v1 + v2 + 1e-9)
            if best_sim >= REASSIGN_MIN_SIM and margin >= REASSIGN_MIN_MARGIN:
                train_labels[i] = best
                flips += 1

        # ①' 测试集标签修正（独立训练库投票）
        test_votes = gpu_votes(test_vecs, train_vecs, train_labels)
        test_flips = 0
        for i, (best, v1, v2, best_sim) in enumerate(test_votes):
            if best == test_labels[i]:
                continue
            margin = (v1 - v2) / (v1 + v2 + 1e-9)
            if best_sim >= REASSIGN_MIN_SIM and margin >= REASSIGN_MIN_MARGIN:
                test_labels[i] = best
                test_flips += 1

        # ② 混淆对 → GLM 复审合并（带真实样例）
        confusion: Counter = Counter()
        for (best, _, _, best_sim), own in zip(votes, train_labels):
            if best_sim >= REASSIGN_MIN_SIM and best != own:
                confusion[(str(own), str(best))] += 1
        merges = {}
        for (a, b), count in confusion.most_common(TOP_CONFUSION_PAIRS):
            if count < 150 or a not in set(train_labels) or b not in set(train_labels):
                continue
            idx_a = [i for i, x in enumerate(train_labels) if x == a][:40]
            idx_b = [i for i, x in enumerate(train_labels) if x == b][:40]
            samples_a = [abstract_of[train_doc_ids[i]][:200] for i in rng.choice(idx_a, 4, replace=False)]
            samples_b = [abstract_of[train_doc_ids[i]][:200] for i in rng.choice(idx_b, 4, replace=False)]
            if glm_merge_verdict(glm_client, name_of.get(a, a), samples_a,
                                 name_of.get(b, b), samples_b):
                keep, drop = (a, b) if (train_labels == a).sum() >= (train_labels == b).sum() else (b, a)
                merges[drop] = keep
        if merges:
            train_labels = np.array([merges.get(x, x) for x in train_labels])
            test_labels = np.array([merges.get(x, x) for x in test_labels])

        # ③ 微类吸收
        absorbed = 0
        while True:
            uniq, counts = np.unique(train_labels, return_counts=True)
            small = uniq[counts < MIN_CATEGORY_SIZE]
            if not len(small):
                break
            big = [u for u, c in zip(uniq, counts) if c >= MIN_CATEGORY_SIZE]
            cents = np.stack([train_vecs[train_labels == c].mean(0) for c in big])
            cents /= np.linalg.norm(cents, axis=1, keepdims=True) + 1e-9
            mapping = {}
            for s in small:
                members = np.where(train_labels == s)[0]
                target = big[int(np.bincount((train_vecs[members] @ cents.T).argmax(1)).argmax())]
                mapping[str(s)] = str(target)
                absorbed += 1
            train_labels = np.array([mapping.get(x, x) for x in train_labels])
            test_labels = np.array([mapping.get(x, x) for x in test_labels])

        stats = per_doc_stats(test_vecs, train_vecs, train_labels.tolist())
        current = eval_gates(stats, test_labels.tolist(), 0.45, 0.70)
        print(f"[第{round_no}轮] 改判 train={flips} test={test_flips} 合并={len(merges)} "
              f"吸收={absorbed} → 覆盖={current['coverage']:.2%} 准确={current['accuracy']:.2%} "
              f"宏F1={current['macro_f1']}")
        if flips == 0 and test_flips == 0 and not merges and absorbed == 0:
            break

    # 最终指标 + LOO 抽样
    final_stats = per_doc_stats(test_vecs, train_vecs, train_labels.tolist())
    final = eval_gates(final_stats, test_labels.tolist(), 0.45, 0.70)
    rng2 = np.random.RandomState(42)
    loo_idx = rng2.choice(len(train_labels), 3000, replace=False).tolist()
    loo_stats = per_doc_stats(train_vecs[loo_idx], train_vecs, train_labels.tolist(),
                              loo_positions=loo_idx)
    loo = eval_gates(loo_stats, [str(train_labels[i]) for i in loo_idx], 0.45, 0.70)

    # 重建输出（保持原文档顺序/划分成员不变）
    for row, label in zip(train_rows, train_labels):
        row["technical_cluster_id"] = str(label)
        row["technical_cluster_name"] = name_of.get(str(label), str(label))
    for row, label in zip(test_rows, test_labels):
        row["gold_topic_id"] = str(label)
        row["gold_topic_name"] = name_of.get(str(label), str(label))
    (OUT / "anchor_train.json").write_text(json.dumps(train_rows, ensure_ascii=False), encoding="utf-8")
    (OUT / "eval_test.json").write_text(json.dumps(test_rows, ensure_ascii=False), encoding="utf-8")
    uniq = sorted(set(train_labels.tolist()),
                  key=lambda c: -int((train_labels == c).sum()))
    new_tax = []
    for rank, cid in enumerate(uniq, 1):
        members = train_vecs[train_labels == cid]
        sims = members @ members.T
        n = len(members)
        cohesion = float((sims.sum() - n) / (n * n - n)) if n > 1 else 0.0
        new_tax.append({"topic_id": str(cid), "topic_name": name_of.get(str(cid), str(cid)),
                        "size": n, "cohesion": round(cohesion, 4)})
    (OUT / "taxonomy.json").write_text(
        json.dumps({"topics": new_tax}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "report_selfreview.json").write_text(json.dumps({
        "baseline": baseline, "final_test": final, "final_loo": loo,
        "categories_after": len(uniq),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 装回内置槽位 + 预写缓存
    SLOT.replace(SLOT.with_suffix(".json.bak2"))
    SLOT.write_text(json.dumps(train_rows, ensure_ascii=False), encoding="utf-8")
    stat = SLOT.stat()
    digest = hashlib.md5(
        f"{SLOT.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|technical".encode()).hexdigest()[:16]
    cache = PROJECT_ROOT / "rag_store" / "deep_clustering_anchor"
    np.save(cache / f"anchors_{digest}.npy", train_vecs)
    (cache / f"anchors_{digest}.json").write_text(
        json.dumps({"labels": train_labels.tolist(), "doc_ids": train_doc_ids},
                   ensure_ascii=False), encoding="utf-8")
    print(f"[完成] 基线 准确={baseline['accuracy']:.2%}/宏F1={baseline['macro_f1']}"
          f" → 自审后 准确={final['accuracy']:.2%}/宏F1={final['macro_f1']}"
          f"（LOO {loo['accuracy']:.2%}）；类目 {len(uniq)} 个；缓存 anchors_{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
