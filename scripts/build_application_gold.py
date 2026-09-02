#!/usr/bin/env python3
"""为全量语料构建应用场景轴 gold 标签，与技术轴共用内置槽位（双轴 gold）。

流程（与技术轴 build_anchor_fullscale 对称，表示不同）：
  1) 复现同一份语料与文档顺序（同 SEED 的 load_corpus，与槽位文件逐一对得上）
  2) 用系统自己的"应用场景视图"构造文本（dual_axis_cluster._view_text 的
     APPLICATION_CUES 句子打分，抓任务对象/行业领域/应用目标句），而非原始摘要
     ——与产线应用轴的本地表示一致
  3) GPU 编码 → k 扫描 → 聚类
  4) 自审循环：GLM 按"应用场景/行业领域"命名（非技术路线）、合并/吸收/拆分
  5) 应用轴标签合并写回槽位文件（application_cluster_id/name），
     train/test 划分成员与技术轴保持一致（两轴同批文献、各自类目体系）
  6) 训练应用轴判别头 → discriminative_head_application.pt
  7) 预写双轴向量缓存（技术轴用原向量、应用轴用视图向量）
  8) 应用轴测试集指标（NN vs 判别头）

用法：
  BGE_DEVICE=cuda python3 -m scripts.build_application_gold /root/autodl-tmp/abstract.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_anchor_fullscale import (  # noqa: E402
    ABSORB_MIN, GENERIC_PAT, MERGE_CANDIDATE_SIM, SEED, load_corpus,
    absorb_small, merge_duplicates, split_heterogeneous,
)
from scripts.build_anchor_dataset_from_corpus import cluster_terms  # noqa: E402
from scripts.fix_boundary_confusion import head_predict, train_head  # noqa: E402
from scripts.build_anchor_fullscale import eval_gates, per_doc_stats  # noqa: E402

OUT = PROJECT_ROOT / "output/anchor_full"
SLOT = PROJECT_ROOT / "rules" / "deep_clustering" / "gold" / "anchor_gold_current.json"
APP_PREFIX = "ZA"


def application_views(rows: list[dict]) -> list[str]:
    """用产线应用轴的本地视图构造器（cue 句子打分）生成每篇的应用场景视图。"""
    from infrastructure.clustering.dual_axis_cluster import _view_text
    views = []
    for row in rows:
        paper = {"title": "", "abstract": row["text"], "keywords": [],
                 "full_text": "", "semantic_text": row["text"]}
        view, _focus = _view_text(paper, "application")
        views.append(view or row["text"][:1200])
    return views


def name_application_cluster(glm_client, terms: list[str], snippets: list[str]) -> str | None:
    attempts = [
        {"高频术语": terms, "样例片段": [s[:120] for s in snippets]},
        {"高频术语": terms},
    ]
    system = (
        "你是科技文献应用场景类目命名专家。下面给出一个文献簇的高频术语与样例。"
        "请按【应用场景/行业领域/服务对象】视角命名一个中文类目（6-14 汉字）："
        "概括这批文献共同面向什么行业、什么对象、什么使用场景"
        "（如：新能源与储能、临床诊疗与医疗器械、电商与数字营销、农业种植与育种）；"
        "禁止从方法/算法角度命名，禁止'综合应用/其他'类无信息量命名。"
        '只返回JSON：{"topic_name":"类目名"}'
    )
    for payload in attempts:
        try:
            raw = glm_client.chat_json(system, json.dumps(payload, ensure_ascii=False),
                                       temperature=0.1, timeout=60.0, max_tokens=120)
        except Exception:  # noqa: BLE001
            continue
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        name = str(data.get("topic_name") or "").strip()
        if name and 6 <= len(name) <= 20 and not any(p in name for p in GENERIC_PAT):
            return name
    return None


def review_loop_application(glm_client, rows, vectors, labels, max_rounds=3):
    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor
    from scripts.build_anchor_fullscale import cohesion_of, terms_by_cluster
    from scripts.build_anchor_fullscale import glm_same_topic

    label_names: dict[int, str] = {}
    verdict_cache: dict = {}
    history = []
    for round_no in range(1, max_rounds + 1):
        cids = sorted(np.unique(labels).tolist())
        unnamed = [c for c in cids if c not in label_names]
        if unnamed:
            terms_map = terms_by_cluster(rows, labels)
            def _name(cid):
                members = np.where(labels == cid)[0]
                snippets = [rows[i]["text"] for i in members[:2]]
                return name_application_cluster(glm_client, terms_map.get(cid, []), snippets)
            with ThreadPoolExecutor(max_workers=4) as pool:
                for cid, name in zip(unnamed, pool.map(_name, unnamed)):
                    label_names[cid] = name or "、".join(terms_map.get(cid, [])[:3]) or f"app_{cid}"
        terms_map = terms_by_cluster(rows, labels)
        merges = merge_duplicates(glm_client, vectors, labels, label_names, terms_map, verdict_cache)
        absorbed = absorb_small(vectors, labels)
        splits = split_heterogeneous(vectors, labels)
        final_cids = sorted(np.unique(labels).tolist())
        cohesions = sorted(round(cohesion_of(vectors[labels == c]), 3) for c in final_cids)
        history.append({"round": round_no, "merges": merges, "absorbed": absorbed,
                        "splits": splits, "categories": len(final_cids),
                        "cohesion_median": cohesions[len(cohesions) // 2]})
        print(f"    第{round_no}轮：合并{merges} 吸收{absorbed} 拆分{splits}"
              f" → {len(final_cids)} 类（内聚中位 {cohesions[len(cohesions) // 2]}）", flush=True)
        if merges + absorbed + splits == 0:
            break
    return labels, history, label_names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus")
    parser.add_argument("--k-list", default="80,100,120")
    args = parser.parse_args()

    rows = load_corpus(Path(args.corpus), 0)  # 同 SEED → 与技术轴同一批同序
    slot_rows = json.loads(SLOT.read_text())
    train_ids = [r["document_id"] for r in slot_rows]
    test_rows = json.loads((OUT / "eval_test.json").read_text())
    id_to_pos = {r["document_id"]: i for i, r in enumerate(rows)}
    assert all(did in id_to_pos for did in train_ids), "语料复现与槽位文件对不上"
    assert all(r["document_id"] in id_to_pos for r in test_rows), "测试集对不上"
    print(f"[0] 语料 {len(rows)} 条；槽位 train={len(train_ids)} test={len(test_rows)} 对齐校验通过", flush=True)

    views = application_views(rows)
    from scripts.build_anchor_fullscale import encode_all
    vectors = encode_all(views)

    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import silhouette_score
    k_list = [int(x) for x in args.k_list.split(",")]
    scores = {}
    for k in k_list:
        trial = MiniBatchKMeans(n_clusters=k, random_state=SEED, batch_size=4096, n_init=5
                                ).fit_predict(vectors)
        scores[k] = float(silhouette_score(vectors, trial, sample_size=5000, random_state=SEED))
        print(f"    k={k:3d} silhouette={scores[k]:.4f}", flush=True)
    best_k = max(scores, key=scores.get)
    print(f"[3] 选定 k={best_k}", flush=True)
    labels = MiniBatchKMeans(n_clusters=best_k, random_state=SEED, batch_size=4096, n_init=10
                             ).fit_predict(vectors).astype(np.int64)

    from infrastructure.llm.glm_client import glm_client
    print("[4] 应用轴自审循环（场景命名/合并/吸收/拆分）…", flush=True)
    labels, history, label_names = review_loop_application(glm_client, rows, vectors, labels)

    train_pos = [id_to_pos[d] for d in train_ids]
    test_pos = [id_to_pos[r["document_id"]] for r in test_rows]
    cids = sorted(np.unique(labels).tolist(), key=lambda c: -int((labels == c).sum()))
    id_map = {int(c): f"{APP_PREFIX}{i + 1:02d}" for i, c in enumerate(cids)}
    name_map = {id_map[int(c)]: label_names.get(int(c), f"app_{int(c)}") for c in cids}
    app_label_of = {rows[i]["document_id"]: id_map[int(labels[i])] for i in range(len(rows))}
    print(f"[5] 应用轴类目 {len(cids)} 个", flush=True)

    # ---- 指标：应用轴 train/test（NN + 判别头） ----
    train_vecs = vectors[np.array(train_pos)]
    test_vecs = vectors[np.array(test_pos)]
    train_labels = [app_label_of[rows[i]["document_id"]] for i in train_pos]
    test_golds = [app_label_of[rows[i]["document_id"]] for i in test_pos]
    stats = per_doc_stats(test_vecs, train_vecs, train_labels)
    nn = eval_gates(stats, test_golds, 0.45, 0.70)
    print(f"[6] 应用轴 NN：覆盖={nn['coverage']:.2%} 准确={nn['accuracy']:.2%} 宏F1={nn['macro_f1']}", flush=True)
    head, classes = train_head(train_vecs, np.array(train_labels), epochs=30)
    pred, _ = head_predict(head, classes, test_vecs)
    head_acc = float(np.mean(np.array(pred) == np.array(test_golds)))
    print(f"[7] 应用轴判别头：准确={head_acc:.2%}", flush=True)

    # ---- 写回：槽位 + 测试集 + 应用类目表 + 判别头 + 双轴缓存 ----
    import torch
    for row in slot_rows:
        label = app_label_of[row["document_id"]]
        row["application_cluster_id"] = label
        row["application_cluster_name"] = name_map[label]
    SLOT.replace(SLOT.with_suffix(".json.bak3"))
    SLOT.write_text(json.dumps(slot_rows, ensure_ascii=False), encoding="utf-8")
    for row in test_rows:
        label = app_label_of[row["document_id"]]
        row["gold_application_topic_id"] = label
        row["gold_application_topic_name"] = name_map[label]
    (OUT / "eval_test.json").write_text(json.dumps(test_rows, ensure_ascii=False), encoding="utf-8")
    taxonomy = [{"topic_id": id_map[int(c)], "topic_name": name_map[id_map[int(c)]],
                 "size": int((labels == c).sum())} for c in cids]
    (OUT / "taxonomy_application.json").write_text(
        json.dumps({"topics": taxonomy, "k_sweep": scores, "review_history": history,
                    "nn_test": nn, "head_test_accuracy": round(head_acc, 4)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    torch.save({"state_dict": head.state_dict(), "classes": classes},
               PROJECT_ROOT / "rules/deep_clustering/gold/discriminative_head_application.pt")

    # 双轴缓存（新文件 mtime → 新 digest）
    tech_cache = PROJECT_ROOT / "rag_store/deep_clustering_anchor/anchors_5f36bedf3fb3253e.npy"
    tech_vecs = np.load(tech_cache)
    tech_labels = json.loads(tech_cache.with_suffix(".json").read_text())["labels"]
    stat = SLOT.stat()
    cache = PROJECT_ROOT / "rag_store/deep_clustering_anchor"
    for axis, vecs, labs in (("technical", tech_vecs, tech_labels),
                             ("application", train_vecs, train_labels)):
        digest = hashlib.md5(f"{SLOT.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{axis}".encode()).hexdigest()[:16]
        np.save(cache / f"anchors_{digest}.npy", vecs)
        (cache / f"anchors_{digest}.json").write_text(
            json.dumps({"labels": labs, "doc_ids": train_ids}, ensure_ascii=False), encoding="utf-8")
        print(f"    缓存 anchors_{digest}.npy（{axis}，{vecs.shape}）", flush=True)
    print(f"[8] 完成：槽位双轴 gold（技术 {len(set(tech_labels))} 类 + 应用 {len(cids)} 类）", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
