"""精分测试：bge 粗合并(th=0.78)→对大粗簇用 LLM 按实际内容精分。

思路：bge 粗合并把同域不同主题糊在一起（如区域经济+城市+农业+人文 都"绿色生产率"），
但粗簇是同质的。LLM 读粗簇内每篇实际 route，能按研究主题精分。
小粗簇（已够细）不动。最终簇 = 小粗簇 + 大粗簇的精分子簇。
"""
from __future__ import annotations
import json, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering

from infrastructure.llm.glm_client import GLMClient
from infrastructure.clustering.semantic_cluster import _merge_clusters

CACHE_ROUTES = Path("/tmp/zh500_topic_routes.json")
CACHE_INTER = Path("/tmp/zh500_intermediate.json")

SYSP_SPLIT = (
    "你是科技文献主题分析专家。下面是【已判定为同一大类】的若干文献研究主题描述，"
    "但其中可能混入了不同的具体研究主题。请阅读每篇，按【具体研究对象/问题】精分：\n"
    "- 只有研究【同一具体对象/问题】的才归一组（如 区域经济空间格局 ≠ 城市土地利用 ≠ 农业粮食 ≠ 旅游客流）\n"
    "- 同一主题的不同方法/角度仍归一组\n"
    "- 宁可多分，不要把不同具体主题糊一起\n"
    "输出JSON：{\"groups\":[{\"indices\":[0,3,5],\"label\":\"3-8字标签\"},...]}\n"
    "indices 是输入列表的0-based序号；每个输入必须归且仅归一组。"
)


def coarse_groups(intermediate, M, th=0.78):
    cents = np.array([M[c["doc_indices"]].mean(axis=0) for c in intermediate])
    cos = cosine_similarity(cents)
    dist = np.clip(1.0 - cos, 0.0, 2.0)
    np.fill_diagonal(dist, 0.0)
    agg = AgglomerativeClustering(n_clusters=None, metric="precomputed",
                                  linkage="average", distance_threshold=1.0 - th)
    lab = agg.fit_predict(dist)
    comp = {}
    for i in range(len(intermediate)):
        comp.setdefault(int(lab[i]), []).append(i)
    return list(comp.values())  # 每个 = 中间簇id列表


def llm_split(doc_indices, routes, glm, target=None):
    """对一组 doc（route列表）做 LLM 精分，返回 [{label, doc_indices}]。"""
    n = len(doc_indices)
    if target is None:
        target = max(1, round(n / 22))
    listing = "\n".join(f"[{i}] {routes[di][:160]}" for i, di in enumerate(doc_indices))
    hint = (f"共{n}篇。请精分为【约{target}组（{max(2,target-1)}~{target+2}组）】，"
            f"按具体研究主题归类。同一主题合并为一组（不要每2-3篇就拆一组）。")
    try:
        out = glm.chat_json(SYSP_SPLIT, f"{hint}\n{listing}",
                            temperature=0.1, timeout=120.0, max_tokens=2500)
        groups = out.get("groups", [])
        result = []
        covered = set()
        for g in groups:
            idxs = [int(x) for x in g.get("indices", []) if isinstance(x, (int, float))]
            real = [doc_indices[x] for x in idxs if 0 <= x < len(doc_indices) and doc_indices[x] not in covered]
            for r in real:
                covered.add(r)
            if real:
                result.append({"label": (g.get("label") or "").strip() or "未分类",
                               "doc_indices": real})
        miss = [di for di in doc_indices if di not in covered]
        if miss:
            result.append({"label": "未分类", "doc_indices": miss})
        return result
    except Exception as e:  # noqa: BLE001
        print(f"  精分失败({len(doc_indices)}篇): {e}")
        return [{"label": "未分类", "doc_indices": list(doc_indices)}]


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


def eval_groups(groups, doc_ids, papers):
    gold = [p["gold"] for p in papers]
    id2algo = {}
    for g in groups:
        for i in g["doc_indices"]:
            id2algo[doc_ids[i]] = g["label"]
    algo = [id2algo.get(p["document_id"], "未分类") for p in papers]
    return {
        "k": len(groups),
        "ari": adjusted_rand_score(gold, algo),
        "nmi": normalized_mutual_info_score(gold, algo),
        "hom": homogeneity_score(gold, algo),
        "comp": completeness_score(gold, algo),
        "vm": v_measure_score(gold, algo),
        "pur": purity(gold, algo),
    }


def run(papers, doc_ids, routes, M, intermediate, glm, th_coarse, label):
    coarse = coarse_groups(intermediate, M, th=th_coarse)
    sizes = sorted((sum(len(intermediate[c]["doc_indices"]) for c in g) for g in coarse), reverse=True)
    print(f"\n[{label}] bge粗簇={len(coarse)} th={th_coarse} 大小: {sizes[:12]}")
    SPLIT_MIN = 12
    final_groups = []
    big_tasks = []
    for g in coarse:
        doc_idx = []
        for cid in g:
            doc_idx.extend(intermediate[cid]["doc_indices"])
        if len(doc_idx) <= SPLIT_MIN:
            labels = [intermediate[cid]["label"] for cid in g if intermediate[cid]["label"]]
            lbl = Counter(labels).most_common(1)[0][0] if labels else "未分类"
            final_groups.append({"label": lbl, "doc_indices": doc_idx})
        else:
            big_tasks.append(doc_idx)
    t0 = time.time()
    refined = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(llm_split, t, routes, glm): t for t in big_tasks}
        for i, fut in enumerate(as_completed(futs), 1):
            refined.extend(fut.result())
    final_groups.extend(refined)
    covered = set(i for g in final_groups for i in g["doc_indices"])
    miss = [i for i in range(len(doc_ids)) if i not in covered]
    # 把漏分 + 落入"未分类/空"垃圾组的文档，按 bge 重分到最近实簇
    JUNK = {"未分类", "无", "", "其它", "其他"}
    junk_docs = list(miss) + [i for g in final_groups
                              if g["label"].strip() in JUNK for i in g["doc_indices"]]
    real = [g for g in final_groups if g["label"].strip() not in JUNK]
    if junk_docs and real:
        cents = []
        for g in real:
            v = M[g["doc_indices"]].mean(axis=0)
            cents.append(v / (np.linalg.norm(v) + 1e-9))
        cents = np.array(cents)
        for i in junk_docs:
            v = M[i]; v = v / (np.linalg.norm(v) + 1e-9)
            real[int(np.argmax(cents @ v))]["doc_indices"].append(i)
        final_groups = real
    r = eval_groups(final_groups, doc_ids, papers)
    print(f"[{label}] k={r['k']} ARI={r['ari']:.3f} NMI={r['nmi']:.3f} "
          f"hom={r['hom']:.3f} comp={r['comp']:.3f} V={r['vm']:.3f} pur={r['pur']:.3f}  ({time.time()-t0:.0f}s)")
    return r, final_groups


def main():
    gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
    papers = gold_data["papers"]
    glm = GLMClient()
    routes_by_id = json.loads(CACHE_ROUTES.read_text(encoding="utf-8"))
    doc_ids = [p["document_id"] for p in papers]
    routes = [routes_by_id[did] for did in doc_ids]

    d = json.loads(CACHE_INTER.read_text(encoding="utf-8"))
    intermediate = d["intermediate"]
    M = np.array(d["M"])
    print(f"中间簇={len(intermediate)}")

    results = {}
    best_r, best_g, best_th = None, None, None
    for th in [0.78, 0.80, 0.82]:
        r, g = run(papers, doc_ids, routes, M, intermediate, glm, th, f"th={th}")
        results[th] = r
        if best_r is None or r["ari"] > best_r["ari"]:
            best_r, best_g, best_th = r, g, th

    print(f"\n{'='*50}")
    print("汇总:")
    for th, r in results.items():
        mark = "  <- best" if th == best_th else ""
        print(f"  th={th}: k={r['k']} ARI={r['ari']:.3f} NMI={r['nmi']:.3f} "
              f"hom={r['hom']:.3f} comp={r['comp']:.3f} V={r['vm']:.3f} pur={r['pur']:.3f}{mark}")

    # 对比纯 bge
    base = _merge_clusters(intermediate, M, threshold=0.78, glm_client=None)
    rb = eval_groups(base, doc_ids, papers)
    print(f"  纯bge0.78(无精分): k={rb['k']} ARI={rb['ari']:.3f} NMI={rb['nmi']:.3f} pur={rb['pur']:.3f}")

    print(f"\n=== 最优 th={best_th} 簇分布 ===")
    id2a = {}
    for g in best_g:
        for i in g["doc_indices"]:
            id2a[doc_ids[i]] = g["label"]
    algo = [id2a.get(p["document_id"], "未分类") for p in papers]
    for lbl, cnt in Counter(algo).most_common():
        print(f"  {lbl:18} {cnt}")
    print("\ngold→算法簇:")
    g2a = {}
    for p, a in zip(papers, algo):
        g2a.setdefault(p["gold"], Counter())[a] += 1
    for g in sorted(g2a, key=lambda x: -sum(g2a[x].values())):
        tops = g2a[g].most_common(2)
        print(f"  {g:14} → {', '.join(f'{k}({v})' for k,v in tops)}")


if __name__ == "__main__":
    main()
