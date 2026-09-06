#!/usr/bin/env python3
"""实验：语步导向的双轴聚类（v2 设计）vs 现有方法——gold 类目为金标签。

v2 设计（用户 2026-09-06 提出）：
  文献 → 分句 → LLM 句子级语步分类（背景/目的/方法/结果/结论）
  技术路线轴 = "方法句"向量聚合 → 聚类（方法相似性）
  应用场景轴 = "背景句+目的句"向量聚合 → 聚类（场景相似性）

对照（同一批次）：
  ① v2-技术轴：方法句向量 KMeans（auto k / oracle k）
  ② v2-应用轴：背景+目的句向量 KMeans
  ③ 现有管线简化版：整篇摘要混合向量 KMeans auto（≈ 全字段混合语义）
  ④ LLM 语义分组（现有小样本管线，technical 轴成绩已知）

评估：ARI / NMI / 簇纯度（gold technical_cluster_id / application_cluster_id）。
不改动生产代码——独立实验脚本。
"""
import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD_JSON = ROOT / "rules/deep_clustering/gold/anchor_gold_current.json"

from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score

SENT_SPLIT = re.compile(r"[。！？]|(?<=[.!?])\s")


def split_sentences(text: str) -> list:
    parts, out = [], []
    for m in SENT_SPLIT.finditer(text):
        end = m.end()
        while end < len(text) and text[end] in "”’\"')]}":
            end += 1
        parts.append((m.start(), end))
    last = 0
    for s, e in parts:
        seg = text[s:e].strip()
        if seg:
            out.append(seg)
        last = e
    if last < len(text) and text[last:].strip():
        out.append(text[last:].strip())
    return [s for s in out if len(s) >= 8][:12]  # 每篇最多 12 句


def classify_moves_batch(abstracts: list, glm) -> list:
    """用生产语步引擎（中文摘要语步识别工具同款管线）逐篇分类，线程池并发。

    返回 [[句, 语步], ...] 列表（按篇）。do_review=False 省去冲突二次审核
    （实验场景规则校验已够）；引擎 = GLM 主判 + 规则调分 + 确定性校准。
    """
    from concurrent.futures import ThreadPoolExecutor
    from training.move_classifier import classify_full
    from training.rule_lib import RuleLib

    rule_lib = RuleLib.load(ROOT / "rules/move_recognition/mr_zh_abstract.yaml")

    def one(abstract: str):
        try:
            res = classify_full(abstract, rule_lib, do_review=False)
            return [(s.get("text") or "", s.get("llm_label") or "")
                    for s in (res.get("evidence") or []) if s.get("llm_label")]
        except Exception:  # noqa: BLE001
            return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(one, abstracts))


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
    ap.add_argument("--out", default="/tmp/move_cluster_eval.json")
    args = ap.parse_args()

    print("加载 gold...", flush=True)
    docs = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    by_tech = defaultdict(list)
    by_app = defaultdict(list)
    for i, d in enumerate(docs):
        if d.get("technical_cluster_id"):
            by_tech[d["technical_cluster_id"]].append(i)
        if d.get("application_cluster_id"):
            by_app[d["application_cluster_id"]].append(i)

    from infrastructure.rag.m3_encoder import m3_encoder
    from infrastructure.llm.glm_client import glm_client

    rng = random.Random(args.seed)
    results = []
    for bi in range(args.batches):
        # 批次构造：3-6 个 technical 类目（与之前评估同款）
        cats = rng.sample([k for k, v in by_tech.items() if len(v) >= 8], rng.randint(3, 6))
        idxs, gold_t = [], []
        for c in cats:
            for i in rng.sample(by_tech[c], min(max(2, args.size // len(cats) - rng.randint(0, 2)), len(by_tech[c]))):
                idxs.append(i)
                gold_t.append(docs[i]["technical_cluster_id"])
        if len(idxs) < 6:
            continue
        gold_a = [docs[i]["application_cluster_id"] for i in idxs]
        n = len(idxs)

        # ① v2：分句 + 语步分类
        abstracts = [str(docs[i].get("ch_abstract") or "") for i in idxs]
        try:
            move_lists = classify_moves_batch(abstracts, glm_client)
        except Exception as exc:  # noqa: BLE001
            print(f"[{bi}] 语步分类失败: {exc}", flush=True)
            continue
        method_sents, scene_sents = [], []
        for sent_pairs in move_lists:
            method_sents.append([s for s, mv in sent_pairs if mv == "研究方法"])
            scene_sents.append([s for s, mv in sent_pairs if mv in ("研究背景", "研究目的")])

        def doc_vector(sent_lists, fallbacks):
            """文献向量：句向量均值；该类句子为空时退回首句/题名。"""
            vectors, valid = [], 0
            for i, sents in enumerate(sent_lists):
                use = sents if sents else [fallbacks[i]]
                vec = np.asarray(m3_encoder.encode(use)).mean(axis=0)
                norm = np.linalg.norm(vec)
                vectors.append(vec / max(norm, 1e-9))
                valid += 1 if sents else 0
            return np.asarray(vectors), valid

        titles = [str(docs[i].get("ch_name") or abstracts[j][:40]) for j, i in enumerate(idxs)]
        method_vec, m_hit = doc_vector(method_sents, titles)
        scene_vec, s_hit = doc_vector(scene_sents, titles)
        # ③ 现有管线简化版：整篇混合
        mixed_vec = np.asarray(m3_encoder.encode(abstracts))

        rec = {"batch": bi, "n": n, "gold_cats_t": len(set(gold_t)), "gold_cats_a": len(set(gold_a)),
               "method_sent_docs": m_hit, "scene_sent_docs": s_hit}
        # v2 技术轴（方法句）vs gold technical
        rec["v2_tech_auto"] = eval_labels(kmeans_auto(method_vec), gold_t)
        rec["v2_tech_oracle"] = eval_labels(
            KMeans(n_clusters=len(set(gold_t)), n_init=10, random_state=42).fit_predict(method_vec), gold_t)
        # v2 应用轴（背景+目的句）vs gold application
        rec["v2_app_auto"] = eval_labels(kmeans_auto(scene_vec), gold_a)
        rec["v2_app_oracle"] = eval_labels(
            KMeans(n_clusters=len(set(gold_a)), n_init=10, random_state=42).fit_predict(scene_vec), gold_a)
        # 基线：混合向量（technical 金标签）
        rec["mixed_auto"] = eval_labels(kmeans_auto(mixed_vec), gold_t)
        rec["mixed_oracle"] = eval_labels(
            KMeans(n_clusters=len(set(gold_t)), n_init=10, random_state=42).fit_predict(mixed_vec), gold_t)
        results.append(rec)
        if (bi + 1) % 5 == 0:
            done = [r for r in results if "v2_tech_auto" in r]
            print(f"[{bi + 1}/{args.batches}] v2技术ARI={np.mean([r['v2_tech_auto']['ari'] for r in done]):.3f} "
                  f"v2应用ARI={np.mean([r['v2_app_auto']['ari'] for r in done]):.3f} "
                  f"混合基线ARI={np.mean([r['mixed_auto']['ari'] for r in done]):.3f}", flush=True)

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n========== 汇总 ==========")
    print(f"批次: {len(results)}")
    if results:
        print(f"语步抽取覆盖率: 方法句 {np.mean([r['method_sent_docs'] for r in results])/np.mean([r['n'] for r in results]):.0%} | "
              f"背景目的句 {np.mean([r['scene_sent_docs'] for r in results])/np.mean([r['n'] for r in results]):.0%}")
        for key, desc in [
            ("v2_tech_auto", "v2技术轴(方法句)auto "),
            ("v2_tech_oracle", "v2技术轴(方法句)金k "),
            ("v2_app_auto", "v2应用轴(场景句)auto "),
            ("v2_app_oracle", "v2应用轴(场景句)金k "),
            ("mixed_auto", "混合基线(现有)auto  "),
            ("mixed_oracle", "混合基线(现有)金k  "),
        ]:
            rows = [r[key] for r in results if r.get(key)]
            if rows:
                print(f"{desc} ARI={np.mean([x['ari'] for x in rows]):.3f}  "
                      f"NMI={np.mean([x['nmi'] for x in rows]):.3f}  纯度={np.mean([x['purity'] for x in rows]):.3f}")
    print(f"明细: {args.out}")


if __name__ == "__main__":
    main()
