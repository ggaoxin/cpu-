#!/usr/bin/env python3
"""Round 3：批次级 gold 评估——"讲一件事"口径（与综述口径一致）。

每个批次（20 篇，多类目混合）：
  批次 gold = GLM 读全部文献的提取句，判定"这批文献讲了哪几件事、每篇属哪件事"
  被评方法（同批）：
    ① v2 技术轴向（方法句向量）KMeans → 对 gold
    ② v2 场景轴向（背景+目的句向量）KMeans → 对 gold
    ③ 混合摘要向量 KMeans → 对 gold（现有方案口径）
gold 生成用证据句 + 并列覆盖规则（与综述骨架的语义一致）。
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

BATCH_GOLD_SYSTEM = (
    "你是科技文献主题判定专家。给定一批文献的描述片段，判断这批文献一共讲了哪几件事"
    "（每件事是一个具体的研究主题，如'YOLO目标检测''糖尿病基因筛选'——不是大学科），"
    "并把每篇文献归入它讲的那件事。每篇必须且只归一件事；讲不同事情的文献不得混入同组。"
    '只输出JSON：{"groups":[{"name":"事情名","docs":[文献编号,...]},...]}'
)


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
    ap.add_argument("--batches", type=int, default=20)
    ap.add_argument("--size", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--scene-with-title", action="store_true", help="场景轴并入题名（gold 无题名，仅对齐生产口径的变体）")
    ap.add_argument("--out", default="/tmp/batch_gold_eval.json")
    args = ap.parse_args()

    moves = json.loads(Path("/tmp/gold_moves.json").read_text(encoding="utf-8"))
    silver = {r["idx"]: r for r in json.loads(Path("/tmp/silver_gold.json").read_text(encoding="utf-8"))}
    # 批次按 silver 类目分层抽样（3-6 个类目×若干篇）——模拟真实文献集的
    # 主题群结构；纯随机 20 篇会讲 20 件事，聚类对齐无意义（实测 ARI≈0）
    def stratified(pool, class_key, rng):
        by_cls = defaultdict(list)
        for r in pool:
            cls = (silver.get(r["idx"]) or {}).get(class_key) or ""
            if cls and cls != "未归类":
                by_cls[cls].append(r)
        classes = [k for k, v in by_cls.items() if len(v) >= 3]
        if len(classes) < 3:
            return None
        picked = []
        for c in rng.sample(classes, rng.randint(3, 6)):
            picked.extend(rng.sample(by_cls[c], min(max(2, 20 // 4), len(by_cls[c]))))
        return picked[:24]

    from infrastructure.rag.m3_encoder import m3_encoder
    from infrastructure.llm.glm_client import glm_client

    def encode_mean(texts):
        v = np.asarray(m3_encoder.encode(texts)).mean(axis=0)
        return v / max(np.linalg.norm(v), 1e-9)

    def batch_gold(rows, kind):
        """GLM 批次分组：kind=method 用方法句、scene 用背景目的句。"""
        lines = [f"[{r['idx']}] {'；'.join((r['method'] if kind == 'method' else r['background'] + r['purpose'])[:3])[:150]}"
                 for r in rows]
        try:
            raw = glm_client.chat_json(BATCH_GOLD_SYSTEM, "\n".join(lines),
                                       temperature=0.0, timeout=120.0, max_tokens=2000)
        except Exception:  # noqa: BLE001
            return None
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            raw = raw["data"]
        label_of = {}
        for g in (raw.get("groups") or []):
            if not isinstance(g, dict):
                continue
            for d in (g.get("docs") or []):
                label_of[str(d)] = str(g.get("name") or "")
        labels = [label_of.get(str(r["idx"]), "") for r in rows]
        if sum(1 for x in labels if x) < len(rows) * 0.8 or len(set(labels)) < 2:
            return None
        return labels

    method_pool_all = [r for r in moves if r["method"]]
    scene_pool_all = [r for r in moves if r["background"] or r["purpose"]]
    rng = random.Random(args.seed)
    results = []
    for bi in range(args.batches):
        for kind, pool, class_key in [
            ("method", method_pool_all, "method_class"),
            ("scene", scene_pool_all, "scene_class"),
        ]:
            picked = stratified(pool, class_key, rng)
            if not picked or len(picked) < 6:
                continue
            gold = batch_gold(picked, kind)
            if not gold:
                continue
            # v2 提取句向量
            key = "method" if kind == "method" else "scene"
            v2_vec = np.asarray([
                encode_mean(r[key] if kind == "method" else r["background"] + r["purpose"])
                for r in picked])
            # 混合基线向量：该轴的"另一侧句"也混入？——现有方案口径=整篇摘要。
            # 用 gold_moves 无摘要 → 用全句（方法+背景+目的提取句合并）近似摘要语义
            all_sents_vec = np.asarray([
                encode_mean(r["method"] + r["background"] + r["purpose"]) for r in picked])
            k_true = len(set(gold))
            results.append({
                "batch": bi, "kind": kind, "n": len(picked), "gold_k": k_true,
                "v2_auto": eval_labels(kmeans_auto(v2_vec), gold),
                "v2_oracle": eval_labels(
                    KMeans(n_clusters=k_true, n_init=10, random_state=42).fit_predict(v2_vec), gold),
                "mixed_auto": eval_labels(kmeans_auto(all_sents_vec), gold),
                "mixed_oracle": eval_labels(
                    KMeans(n_clusters=k_true, n_init=10, random_state=42).fit_predict(all_sents_vec), gold),
            })
        if (bi + 1) % 5 == 0:
            done_m = [r for r in results if r["kind"] == "method"]
            done_s = [r for r in results if r["kind"] == "scene"]
            if done_m:
                print(f"[{bi+1}] 方法批 v2={np.mean([r['v2_auto']['ari'] for r in done_m]):.3f} "
                      f"混合={np.mean([r['mixed_auto']['ari'] for r in done_m]):.3f} | "
                      f"场景批 v2={np.mean([r['v2_auto']['ari'] for r in done_s]):.3f} "
                      f"混合={np.mean([r['mixed_auto']['ari'] for r in done_s]):.3f}", flush=True)

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n========== 批次级 gold（讲一件事口径）==========")
    for kind, label in [("method", "方法轴批"), ("scene", "场景轴批")]:
        rows_k = [r for r in results if r["kind"] == kind]
        if not rows_k:
            continue
        print(f"-- {label}（{len(rows_k)} 批，gold 平均 {np.mean([r['gold_k'] for r in rows_k]):.1f} 件事/批）--")
        for key, desc in [("v2_auto", "v2提取句 auto"), ("v2_oracle", "v2提取句 金k"),
                          ("mixed_auto", "混合句 auto"), ("mixed_oracle", "混合句 金k")]:
            vals = [r[key] for r in rows_k]
            print(f"   {desc} ARI={np.mean([v['ari'] for v in vals]):.3f}  "
                  f"NMI={np.mean([v['nmi'] for v in vals]):.3f}  纯度={np.mean([v['purity'] for v in vals]):.3f}")
    print(f"明细: {args.out}")


if __name__ == "__main__":
    main()
