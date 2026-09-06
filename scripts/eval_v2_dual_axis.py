#!/usr/bin/env python3
"""v2 双轴聚类评估：提取库（方法句/背景目的句）vs 原摘要混合——gold 双轴标签。

技术路线轴：文献"方法句"向量 → 聚类 → 对齐 gold technical_cluster_id
应用场景轴：文献"背景句+目的句"向量 → 聚类 → 对齐 gold application_cluster_id
基线：原摘要混合向量（现有方案口径，对 technical 标签）

依赖 /tmp/gold_moves.json（build_gold_moves.py 产出）。
"""
import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score


def purity(pred, gold):
    mapping = defaultdict(Counter)
    for p, g in zip(pred, gold):
        mapping[p][g] += 1
    return sum(c.most_common(1)[0][1] for c in mapping.values()) / len(gold)


def kmeans_auto(matrix, k_max=8):
    best, best_score = None, -2
    for k in range(2, min(k_max + 1, len(matrix))):
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(matrix)
        score = silhouette_score(matrix, labels, metric="cosine")
        if score > best_score:
            best_score, best = score, labels
    return best


def eval_labels(pred, gold):
    return {
        "ari": round(adjusted_rand_score(gold, pred), 4),
        "nmi": round(normalized_mutual_info_score(gold, pred), 4),
        "purity": round(purity(pred, gold), 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=10)
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="/tmp/v2_dual_eval.json")
    args = ap.parse_args()

    rows = json.loads(Path("/tmp/gold_moves.json").read_text(encoding="utf-8"))
    docs = json.loads((ROOT / "rules/deep_clustering/gold/anchor_gold_current.json").read_text(encoding="utf-8"))
    # 摘要按 idx 取（基线用）；首句作场景 fallback
    abstract_of = {i: str(docs[i].get("ch_abstract") or "") for i in range(len(docs))}

    from infrastructure.rag.m3_encoder import m3_encoder
    encode_cache = {}

    def encode_mean(texts):
        return np.asarray(m3_encoder.encode(texts)).mean(axis=0)

    # 分轴子集（用户定调 2026-09-06）：技术轴用"有方法句"的文献池，
    # 应用轴用"有背景/目的句"的文献池——各轴只用提取到对应语步的样本，
    # 干净评估提取向量的聚类能力
    tech_pool = defaultdict(list)   # tech_label → 有方法句的行
    app_pool = defaultdict(list)    # app_label → 有背景/目的句的行
    for r in rows:
        if r["method"]:
            tech_pool[r["tech_label"]].append(r)
        if (r["background"] or r["purpose"]) and r.get("app_label"):
            app_pool[r["app_label"]].append(r)
    print(f"技术轴子集: {sum(len(v) for v in tech_pool.values())} 篇 | "
          f"应用轴子集: {sum(len(v) for v in app_pool.values())} 篇", flush=True)

    rng = random.Random(args.seed)
    results = []
    for bi in range(args.batches):
        # 两轴独立抽批（各自从对应池、按各自 gold 标签分层）
        cats_t = rng.sample([k for k, v in tech_pool.items() if len(v) >= 5], rng.randint(3, 6))
        picked_t = []
        for c in cats_t:
            picked_t.extend(rng.sample(tech_pool[c], min(max(2, args.size // len(cats_t)), len(tech_pool[c]))))
        cats_a = rng.sample([k for k, v in app_pool.items() if len(v) >= 5], rng.randint(3, 6))
        picked_a = []
        for c in cats_a:
            picked_a.extend(rng.sample(app_pool[c], min(max(2, args.size // len(cats_a)), len(app_pool[c]))))
        if len(picked_t) < 6 or len(picked_a) < 6:
            continue
        picked, n = picked_t, len(picked_t)
        n = len(picked)

        def axis_vec(kind, batch_rows):
            vecs = []
            for r in batch_rows:
                key = (kind, r["idx"])
                if kind == "method":
                    sents = r["method"]
                else:
                    sents = r["background"] + r["purpose"]
                if not sents:
                    # 退回摘要首句（背景性表述）
                    first = abstract_of[r["idx"]].split("。")[0]
                    sents = [first] if first else [r["tech_label"]]
                v = encode_mean(sents)
                vecs.append(v / max(np.linalg.norm(v), 1e-9))
            return np.asarray(vecs)

        # 技术轴批（picked_t）：方法句向量 vs gold technical
        method_vec = axis_vec("method", picked_t)
        mixed_t = np.asarray(m3_encoder.encode([abstract_of[r["idx"]] for r in picked_t]))
        gold_t = [r["tech_label"] for r in picked_t]
        rec = {"batch": bi, "n_t": len(picked_t), "n_a": len(picked_a),
               "gold_t": len(set(gold_t)), "gold_a": len(set(r["app_label"] for r in picked_a))}
        rec["v2_tech_auto"] = eval_labels(kmeans_auto(method_vec), gold_t)
        rec["v2_tech_oracle"] = eval_labels(
            KMeans(n_clusters=len(set(gold_t)), n_init=10, random_state=42).fit_predict(method_vec), gold_t)
        rec["mixed_auto"] = eval_labels(kmeans_auto(mixed_t), gold_t)
        rec["mixed_oracle"] = eval_labels(
            KMeans(n_clusters=len(set(gold_t)), n_init=10, random_state=42).fit_predict(mixed_t), gold_t)

        # 应用轴批（picked_a）：背景+目的句向量 vs gold application
        scene_vec = axis_vec("scene", picked_a)
        mixed_a = np.asarray(m3_encoder.encode([abstract_of[r["idx"]] for r in picked_a]))
        gold_a = [r["app_label"] for r in picked_a]
        k_a = len(set(gold_a))
        rec["v2_app_auto"] = eval_labels(kmeans_auto(scene_vec), gold_a)
        rec["v2_app_oracle"] = eval_labels(
            KMeans(n_clusters=k_a, n_init=10, random_state=42).fit_predict(scene_vec), gold_a)
        rec["mixed_on_app_auto"] = eval_labels(kmeans_auto(mixed_a), gold_a)
        rec["mixed_on_app_oracle"] = eval_labels(
            KMeans(n_clusters=k_a, n_init=10, random_state=42).fit_predict(mixed_a), gold_a)
        results.append(rec)
        if (bi + 1) % 5 == 0:
            print(f"[{bi+1}] v2技术={np.mean([r['v2_tech_auto']['ari'] for r in results]):.3f} "
                  f"v2应用={np.mean([r['v2_app_auto']['ari'] for r in results if r.get('v2_app_auto')]):.3f} "
                  f"混合={np.mean([r['mixed_auto']['ari'] for r in results]):.3f}", flush=True)

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n========== v2 双轴评估 ==========")
    print(f"批次: {len(results)}")
    for key, desc in [
        ("v2_tech_auto", "技术轴(方法句)auto   "),
        ("v2_tech_oracle", "技术轴(方法句)金k   "),
        ("v2_app_auto", "应用轴(背景+目的)auto"),
        ("v2_app_oracle", "应用轴(背景+目的)金k"),
        ("mixed_on_app_auto", "混合向量对应用轴auto"),
        ("mixed_on_app_oracle", "混合向量对应用轴金k"),
        ("mixed_auto", "混合基线(技术轴)auto "),
        ("mixed_oracle", "混合基线(技术轴)金k "),
    ]:
        vals = [r[key] for r in results if r.get(key)]
        if vals:
            print(f"{desc} ARI={np.mean([v['ari'] for v in vals]):.3f}  NMI={np.mean([v['nmi'] for v in vals]):.3f}  纯度={np.mean([v['purity'] for v in vals]):.3f}  (n={len(vals)})")
    print(f"明细: {args.out}")


if __name__ == "__main__":
    main()
