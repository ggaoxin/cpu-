#!/usr/bin/env python3
"""小样本 LLM 语义分组 vs 嵌入聚类 批量评估（gold 类目为金标签）。

用法：
    python3 scripts/eval_llm_clustering.py --batches 20 --size 20     # 20批×20篇
    python3 scripts/eval_llm_clustering.py --batches 100 --size 20    # 100批

批次构造（模拟真实使用）：从 3-6 个 gold 类目各抽 2-7 篇，批内类目数与
篇数随机。每批评估三种划分（同批同输入）：
  ① LLM 语义分组（题名+摘要 → GLM）——产品管线同款函数
  ② 嵌入 KMeans 自动 k（gold 库 1024 维嵌入，轮廓系数选 k，模拟算法管线）
  ③ 嵌入 KMeans oracle k（k=真实类目数，算法上限参照）
指标：ARI（调整兰德指数）、NMI、簇纯度、LLM 校验失败率。
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

GOLD_JSON = ROOT / "rules/deep_clustering/gold/anchor_gold_current.json"
GOLD_NPY = ROOT / "rag_store/deep_clustering_anchor/anchors_0f0a9a54b4ea7be0.npy"

from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score


def build_batches(docs_by_label, rng, n_batches, size):
    """每批：随机 3-6 个类目，类目内抽 2-7 篇，总数≈size。"""
    labels_pool = [lb for lb, lst in docs_by_label.items() if len(lst) >= 8]
    batches = []
    for _ in range(n_batches):
        n_cats = rng.randint(3, 6)
        cats = rng.sample(labels_pool, n_cats)
        per = max(2, size // n_cats - rng.randint(0, 2))
        chosen, gold = [], []
        for cat in cats:
            sample = rng.sample(docs_by_label[cat], min(per, len(docs_by_label[cat])))
            for doc in sample:
                chosen.append(doc)
                gold.append(cat)
        # 不足 size 从其他类目补
        if len(chosen) < size:
            extra_cats = [lb for lb in labels_pool if lb not in cats]
            for cat in rng.sample(extra_cats, min(size - len(chosen), len(extra_cats))):
                doc = rng.choice(docs_by_label[cat])
                chosen.append(doc)
                gold.append(cat)
                if len(chosen) >= size:
                    break
        batches.append((chosen, gold))
    return batches


def embed_kmeans_auto(emb):
    """嵌入 KMeans + 轮廓系数自动选 k（2..8），模拟算法管线。"""
    best_labels, best_score = None, -2
    for k in range(2, min(9, len(emb))):
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(emb)
        score = silhouette_score(emb, labels, metric="cosine")
        if score > best_score:
            best_score, best_labels = score, labels
    return best_labels


def embed_kmeans_oracle(emb, k):
    return KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(emb)


def purity(pred, gold):
    """簇纯度：每簇按多数类计对，总和/总数。"""
    mapping = defaultdict(Counter)
    for p, g in zip(pred, gold):
        mapping[p][g] += 1
    return sum(c.most_common(1)[0][1] for c in mapping.values()) / len(gold)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=20)
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--axis", choices=["technical", "application"], default="technical")
    ap.add_argument("--out", default="/tmp/llm_cluster_eval.json")
    args = ap.parse_args()

    print(f"加载 gold（{GOLD_JSON.name}）...", flush=True)
    docs = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    # 与锚点向量库同序（anchors npy 行序 = gold json 序，doc_ids 校验）
    emb_all = np.load(GOLD_NPY, mmap_mode="r")
    doc_ids = [d["document_id"] for d in docs]
    assert len(doc_ids) == emb_all.shape[0], "gold 与向量库数量不一致"

    axis = args.axis
    label_key = f"{axis}_cluster_id"
    docs_by_label = defaultdict(list)
    for i, d in enumerate(docs):
        if str(d.get(label_key) or "").strip():
            docs_by_label[d[label_key]].append(i)
    print(f"轴={axis} 类目数 {len(docs_by_label)}，开始 {args.batches} 批 × ~{args.size} 篇", flush=True)

    from application.service.deep_clustering_service import _llm_small_sample_repartition
    from infrastructure.llm.glm_client import glm_client

    rng = random.Random(args.seed)
    batches = build_batches(docs_by_label, rng, args.batches, args.size)
    results = []
    for bi, (idxs, gold) in enumerate(batches):
        n = len(idxs)
        gold_labels = [docs[i][label_key] for i in idxs]
        n_gold_cats = len(set(gold_labels))
        rec = {"batch": bi, "n": n, "gold_cats": n_gold_cats}

        # ① LLM 语义分组（产品管线同款）
        papers = [{
            "document_id": docs[i]["document_id"],
            "title": docs[i].get("ch_name") or "",
            "abstract": docs[i].get("ch_abstract") or "",
            "keywords": docs[i].get("keywords") or [],
        } for i in idxs]
        axis_stub = {
            "clusters": [{"cluster_id": "C01", "topic_name": "x", "doc_indices": list(range(n))}],
            "doc_axis_info": [dict() for _ in range(n)],
            "quality": {},
        }
        try:
            stats = _llm_small_sample_repartition(axis_stub, papers, glm_client, axis)
        except Exception as exc:  # noqa: BLE001
            stats = None
            rec["llm_error"] = str(exc)[:80]
        if stats:
            cluster_of = {}
            for c in axis_stub["clusters"]:
                for index in c["doc_indices"]:
                    cluster_of[index] = c["cluster_id"]
            pred = [cluster_of.get(i, "MISS") for i in range(n)]
            rec["llm"] = {
                "ari": round(adjusted_rand_score(gold_labels, pred), 4),
                "nmi": round(normalized_mutual_info_score(gold_labels, pred), 4),
                "purity": round(purity(pred, gold_labels), 4),
                "k": len(axis_stub["clusters"]),
            }
        else:
            rec["llm"] = None  # 校验失败/异常

        # ②③ 嵌入 KMeans
        emb = np.asarray(emb_all[idxs])
        auto = embed_kmeans_auto(emb)
        rec["embed_auto"] = {
            "ari": round(adjusted_rand_score(gold_labels, auto), 4),
            "nmi": round(normalized_mutual_info_score(gold_labels, auto), 4),
            "purity": round(purity(auto, gold_labels), 4),
        }
        oracle = embed_kmeans_oracle(emb, n_gold_cats)
        rec["embed_oracle"] = {
            "ari": round(adjusted_rand_score(gold_labels, oracle), 4),
            "nmi": round(normalized_mutual_info_score(gold_labels, oracle), 4),
            "purity": round(purity(oracle, gold_labels), 4),
        }
        results.append(rec)
        if (bi + 1) % 5 == 0:
            done = [r for r in results if r.get("llm")]
            print(f"[{bi+1}/{args.batches}] LLM成功率 {len(done)}/{bi+1} | "
                  f"LLM ARI均值 {np.mean([r['llm']['ari'] for r in done]) if done else 0:.3f} | "
                  f"嵌入auto ARI {np.mean([r['embed_auto']['ari'] for r in results]):.3f} | "
                  f"嵌入oracle ARI {np.mean([r['embed_oracle']['ari'] for r in results]):.3f}", flush=True)

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = [r for r in results if r.get("llm")]
    print("\n========== 汇总 ==========")
    print(f"批次: {len(results)} | LLM 分组成功: {len(ok)} ({len(ok)/len(results):.0%})")
    if ok:
        print(f"LLM 语义分组   ARI={np.mean([r['llm']['ari'] for r in ok]):.3f}  "
              f"NMI={np.mean([r['llm']['nmi'] for r in ok]):.3f}  "
              f"纯度={np.mean([r['llm']['purity'] for r in ok]):.3f}")
    print(f"嵌入KMeans自动 ARI={np.mean([r['embed_auto']['ari'] for r in results]):.3f}  "
          f"NMI={np.mean([r['embed_auto']['nmi'] for r in results]):.3f}  "
          f"纯度={np.mean([r['embed_auto']['purity'] for r in results]):.3f}")
    print(f"嵌入KMeans金k  ARI={np.mean([r['embed_oracle']['ari'] for r in results]):.3f}  "
          f"NMI={np.mean([r['embed_oracle']['nmi'] for r in results]):.3f}  "
          f"纯度={np.mean([r['embed_oracle']['purity'] for r in results]):.3f}")
    if ok:
        print(f"LLM 簇数 vs 金类目数: {np.mean([r['llm']['k'] for r in ok]):.1f} vs "
              f"{np.mean([r['gold_cats'] for r in ok]):.1f}")
    print(f"明细已存: {args.out}")


if __name__ == "__main__":
    main()
