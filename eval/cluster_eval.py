"""深度聚类算法2 评测脚本：算内部指标(从响应读)+外部指标(vs gold)。

用法:
    python eval/cluster_eval.py /tmp/resp_v2_xxx.json [--gold eval/gold_12.json]

外部指标需 gold 标注文件(gold_12.json)。无 gold 时只报内部指标。
"""
from __future__ import annotations
import json
import sys
import argparse
from collections import Counter
from pathlib import Path


def _extract_result(resp: dict) -> dict:
    """从响应里挖出 result(兼容 data.results[0].result 结构)。"""
    data = resp.get("data", resp)
    if isinstance(data, dict) and "results" in data:
        return data["results"][0]["result"]
    return data


def _algo_labels(result: dict) -> tuple[list[str], list[str]]:
    """返回 (document_ids, 算法簇标签)。标签取选定轴 technical.topic_name。"""
    docs = result.get("documents", [])
    ids = [d.get("document_id", f"D{i}") for i, d in enumerate(docs)]
    labels = [d.get("technical", {}).get("topic_name", "") for d in docs]
    return ids, labels


def _purity(gold: list[str], algo: list[str]) -> float:
    clusters: dict[str, list[str]] = {}
    for g, a in zip(gold, algo):
        clusters.setdefault(a, []).append(g)
    total = sum(max(Counter(v).values()) for v in clusters.values())
    return total / len(gold)


def evaluate(resp_path: str, gold_path: str | None) -> None:
    resp = json.loads(Path(resp_path).read_text(encoding="utf-8"))
    result = _extract_result(resp)
    ids, algo = _algo_labels(result)

    # ---- 内部指标(后端 clustering_quality 预填) ----
    q = result.get("clustering_quality", {}) or {}
    print("=" * 60)
    print("内部指标(聚类结构本身)")
    print("=" * 60)
    print(f"  k(簇数)            : {q.get('cluster_count')}")
    print(f"  silhouette(轮廓)   : {q.get('silhouette_score')}")
    print(f"  CH指数(越大越好)   : {q.get('calinski_harabasz_score', '—')}")
    print(f"  DB指数(越小越好)   : {q.get('davies_bouldin_score', '—')}")
    print(f"  method             : {q.get('clustering_method')}")

    # 簇大小分布
    clusters = result.get("clusters", [])
    sizes = [c.get("size", 0) for c in clusters]
    print(f"  簇大小分布         : {sizes}")

    if not gold_path:
        print("\n(未提供 gold,跳过外部指标)")
        return

    # ---- 外部指标(vs gold) ----
    gold_data = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    gold_map = {p["document_id"]: p["gold"] for p in gold_data["papers"]}
    gold = [gold_map.get(i, "未知") for i in ids]

    try:
        from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
            homogeneity_score, completeness_score, v_measure_score)
    except ImportError:
        print("\n(sklearn 未安装,跳过外部指标)")
        return

    ari = adjusted_rand_score(gold, algo)
    nmi = normalized_mutual_info_score(gold, algo)
    pur = _purity(gold, algo)
    hom = homogeneity_score(gold, algo)
    com = completeness_score(gold, algo)
    vm = v_measure_score(gold, algo)

    print()
    print("=" * 60)
    print(f"外部指标(vs gold {len(set(gold))}簇 → 算法 {len(set(algo))}簇)")
    print("=" * 60)
    print(f"  ARI(调整兰德,1=一致,0=随机) : {ari:.3f}")
    print(f"  NMI(归一化互信息)            : {nmi:.3f}")
    print(f"  纯度(簇内多数类占比)         : {pur:.3f}")
    print(f"  同质性(每簇是否纯)           : {hom:.3f}")
    print(f"  完整性(每类是否聚一起)       : {com:.3f}")
    print(f"  V-measure(调和)              : {vm:.3f}")

    print()
    print("--- 逐篇对比 ---")
    for i, g, a in zip(ids, gold, algo):
        mark = "✓" if _same_cluster(g, a, gold, algo) else "✗"
        print(f"  {i}: gold={g:8} algo={a:14} {mark}")


def _same_cluster(g, a, gold, algo) -> bool:
    """该篇的 gold 类是否与算法簇里多数类一致。"""
    cluster_members = [gold[j] for j in range(len(algo)) if algo[j] == a]
    if not cluster_members:
        return False
    return g == Counter(cluster_members).most_common(1)[0][0]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("resp", help="算法2 响应 json 路径")
    ap.add_argument("--gold", default="eval/gold_12.json", help="gold 标注 json")
    args = ap.parse_args()
    evaluate(args.resp, args.gold if Path(args.gold).exists() else None)
