#!/usr/bin/env python3
"""全量语料锚点数据集构建 v2：构建 → 自动审查迭代 → 阈值校准 → 最终指标。

与 v1（build_anchor_dataset_from_corpus）的差异：
  - 全量语料（默认 168k，去重后全用，不抽样）
  - 自动审查循环（替代人工抽查，最多 3 轮，直至无结构性改动收敛）：
      ① 重复类目合并：质心余弦 ≥ 0.93 只作候选线（实测真重复 0.98 与相邻主题
         0.93-0.96 在几何上不可分），名称相同直接合并，其余候选由 GLM 判定
         是否同一主题；带判定缓存防重复调用与级联失控
      ② 微类吸收：规模 < 30 的类目并入最近质心
      ③ 混杂大类拆分：内聚 < 0.35 且规模 ≥ 600 试拆 2-4 份，
         子簇两两质心余弦 < 0.80 才接受
      ④ 新生类目命名：GLM（内容过滤自动降级纯术语），失败用高频术语拼接兜底
  - 阈值校准：top-5 投票统计一次预计算（GPU 批量），随后
    threshold × anchor_min_combined 网格零成本扫描，宏F1 最高且覆盖率≥80% 的工作点
  - LOO 自检抽样 3000 篇（全量 LOO O(n²) 不可行）

用法（全量）：
  python3 -m scripts.build_anchor_fullscale /root/autodl-tmp/abstract.jsonl \
      --out output/anchor_full --install
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_anchor_dataset_from_corpus import SEED, STOP_TERMS  # noqa: E402

TOPIC_PREFIX = "ZT"
TRAIN_RATIO = 0.7
TOP_K = 5
MERGE_CANDIDATE_SIM = 0.93  # 候选线：几何只筛候选，合并与否由名称/GLM 判定
MAX_MERGES_PER_ROUND = 40
ABSORB_MIN = 30
SPLIT_MIN_SIZE = 600
SPLIT_MAX_COHESION = 0.35
SPLIT_SUB_MIN = 150
SPLIT_SUB_MAXSIM = 0.80
GENERIC_PAT = ("综合", "其他", "相关", "多种", "若干", "杂项", "混合")
TERMS_PER_CLUSTER = 150  # 每簇分词取样上限（全量单遍分词太慢）
LOO_SAMPLE = 3000


# ---------- 基础 ----------

def load_corpus(path: Path, sample_n: int) -> list[dict]:
    rows, seen = [], set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            text = str(row.get("text") or "").strip()
            if len(text) < 60:
                continue
            digest = hashlib.md5(text[:200].encode()).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            rows.append({"text": text, "category": str(row.get("category") or "未知")})
    rng = random.Random(SEED)
    if sample_n and len(rows) > sample_n:
        by: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by[row["category"]].append(row)
        sampled = []
        for items in by.values():
            rng.shuffle(items)
            sampled.extend(items[: max(1, round(sample_n * len(items) / len(rows)))])
        rows = sampled
    rng.shuffle(rows)
    for index, row in enumerate(rows):
        row["document_id"] = f"DOC_{index + 1:06d}"
    print(f"[1] 语料 {len(rows)} 条（{dict(Counter(r['category'] for r in rows))}）")
    return rows


def encode_all(texts: list[str], batch: int = 256) -> np.ndarray:
    import os

    import torch
    from sentence_transformers import SentenceTransformer
    device = os.environ.get("BGE_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
    path = os.environ.get("BGE_M3_PATH", str(PROJECT_ROOT / "models" / "bge-m3"))
    print(f"[2] bge-m3 编码 {len(texts)} 条 device={device} batch={batch} …")
    model = SentenceTransformer(path, device=device)
    return model.encode(
        [t[:2000] for t in texts], batch_size=batch, show_progress_bar=False,
        normalize_embeddings=True, convert_to_numpy=True,
    ).astype(np.float32)


def cohesion_of(sub: np.ndarray) -> float:
    n = len(sub)
    if n < 2:
        return 0.0
    sims = sub @ sub.T
    return float((sims.sum() - n) / (n * n - n))


def terms_by_cluster(rows: list[dict], labels: np.ndarray, max_per: int = TERMS_PER_CLUSTER) -> dict[int, list[str]]:
    """单遍分词、每簇抽样 max_per 篇，返回 {cid: 高频术语列表}。"""
    import jieba
    counters: dict[int, Counter] = defaultdict(Counter)
    taken: dict[int, int] = defaultdict(int)
    for index, cid in enumerate(labels.tolist()):
        if taken[int(cid)] >= max_per:
            continue
        taken[int(cid)] += 1
        for term in jieba.lcut(rows[index]["text"][:600]):
            term = term.strip()
            if len(term) >= 2 and term not in STOP_TERMS and not term.isdigit():
                counters[int(cid)][term] += 1
    return {cid: [t for t, _ in counter.most_common(14)] for cid, counter in counters.items()}


# ---------- 审查动作 ----------

def centroids_of(vectors: np.ndarray, labels: np.ndarray) -> dict[int, np.ndarray]:
    out = {}
    for cid in np.unique(labels):
        c = vectors[labels == cid].mean(0)
        out[int(cid)] = c / (np.linalg.norm(c) + 1e-9)
    return out


def _same_name(na: str, nb: str) -> bool:
    na, nb = na.strip(), nb.strip()
    if na == nb:
        return True
    return (na in nb or nb in na) and abs(len(na) - len(nb)) <= 3


def glm_same_topic(glm_client, na: str, ta: list[str], nb: str, tb: list[str],
                   cache: dict) -> bool:
    key = frozenset((na, nb))
    if key in cache:
        return cache[key]
    system = (
        "你是文献类目体系审查专家。判断下面两个类目是否描述同一主题"
        "（即应合并为一个类目）。相邻但可区分的方向（如'肿瘤靶向治疗'与'临床用药'）"
        "判为不同；仅当高度同义/同一对象换表述时判相同。"
        '只返回JSON：{"same": true 或 false}'
    )
    payload = {"类目A": {"名称": na, "高频术语": ta[:10]}, "类目B": {"名称": nb, "高频术语": tb[:10]}}
    verdict = False
    try:
        raw = glm_client.chat_json(system, json.dumps(payload, ensure_ascii=False),
                                   temperature=0.0, timeout=60.0, max_tokens=30)
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        verdict = bool(data.get("same"))
    except Exception:  # noqa: BLE001
        verdict = False  # 判不定=不合并（保守，防级联）
    cache[key] = verdict
    return verdict


def merge_duplicates(glm_client, vectors: np.ndarray, labels: np.ndarray,
                     label_names: dict[int, str], terms_map: dict[int, list[str]],
                     verdict_cache: dict) -> int:
    merges = 0
    cids = sorted(np.unique(labels).tolist())
    if len(cids) < 2:
        return 0
    cents = centroids_of(vectors, labels)
    matrix = np.stack([cents[c] for c in cids])
    sims = matrix @ matrix.T
    np.fill_diagonal(sims, -1.0)
    pairs = sorted(
        ((float(sims[i, j]), cids[i], cids[j])
         for i in range(len(cids)) for j in range(i + 1, len(cids))
         if sims[i, j] >= MERGE_CANDIDATE_SIM), reverse=True)
    alive = set(cids)
    for _, a, b in pairs:
        if merges >= MAX_MERGES_PER_ROUND:
            break
        if a not in alive or b not in alive:
            continue
        na, nb = label_names.get(a, ""), label_names.get(b, "")
        if _same_name(na, nb) or glm_same_topic(glm_client, na, terms_map.get(a, []), nb, terms_map.get(b, []), verdict_cache):
            labels[labels == b] = a
            alive.discard(b)
            merges += 1
    return merges


def absorb_small(vectors: np.ndarray, labels: np.ndarray) -> int:
    absorbed = 0
    while True:
        cids = np.unique(labels)
        sizes = {int(c): int((labels == c).sum()) for c in cids}
        small = [c for c, s in sizes.items() if s < ABSORB_MIN]
        if not small:
            return absorbed
        big = [c for c in cids if sizes[int(c)] >= ABSORB_MIN]
        if not big:
            return absorbed
        cents = np.stack([centroids_of(vectors, labels)[int(c)] for c in big])
        for c in small:
            idx = np.where(labels == c)[0]
            sims = vectors[idx] @ cents.T
            labels[idx] = big[int(np.bincount(sims.argmax(1)).argmax())]
            absorbed += 1


def split_heterogeneous(vectors: np.ndarray, labels: np.ndarray) -> int:
    from sklearn.cluster import MiniBatchKMeans
    splits = 0
    next_cid = int(labels.max()) + 1
    for c in sorted(np.unique(labels).tolist()):
        idx = np.where(labels == c)[0]
        if len(idx) < SPLIT_MIN_SIZE:
            continue
        sub = vectors[idx]
        if cohesion_of(sub) >= SPLIT_MAX_COHESION:
            continue
        for k2 in (2, 3, 4):
            if len(idx) < k2 * SPLIT_SUB_MIN:
                break
            km = MiniBatchKMeans(n_clusters=k2, random_state=SEED, batch_size=2048, n_init=3)
            sub_labels = km.fit_predict(sub)
            if min(np.bincount(sub_labels, minlength=k2)) < SPLIT_SUB_MIN:
                continue
            cents = km.cluster_centers_
            cents = cents / (np.linalg.norm(cents, axis=1, keepdims=True) + 1e-9)
            pair = cents @ cents.T
            np.fill_diagonal(pair, -1.0)
            if pair.max() < SPLIT_SUB_MAXSIM:
                for s in range(k2):
                    labels[idx[sub_labels == s]] = next_cid + s
                next_cid += k2
                splits += 1
                break
    return splits


def name_new_clusters(glm_client, rows, labels, cids: list[int],
                      terms_map: dict[int, list[str]]) -> dict[int, str]:
    """为指定类目命名（GLM，内容过滤降级纯术语；失败用高频术语拼接兜底）。"""

    def rename(cid: int) -> str:
        members = np.where(labels == cid)[0]
        snippets = [rows[i]["text"] for i in members[:2]]
        attempts = [
            {"高频术语": terms_map.get(cid, []), "样例片段": [s[:120] for s in snippets]},
            {"高频术语": terms_map.get(cid, [])},
        ]
        system = (
            "你是科技文献主题类目命名专家。给出一个文献簇的高频术语与样例，"
            "请命名一个具体、有区分度的中文类目名（6-14 汉字），"
            "必须点明具体研究对象/技术方向，禁止'综合研究/其他/相关技术'类无信息量命名。"
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
        return "、".join(terms_map.get(cid, [])[:3]) or f"topic_{cid}"

    with ThreadPoolExecutor(max_workers=4) as pool:
        return {cid: name for cid, name in zip(cids, pool.map(rename, cids))}


def review_loop(glm_client, rows, vectors, labels, max_rounds=3):
    history = []
    label_names: dict[int, str] = {}
    verdict_cache: dict = {}
    for round_no in range(1, max_rounds + 1):
        cids = sorted(np.unique(labels).tolist())
        unnamed = [c for c in cids if c not in label_names]
        named = name_new_clusters(glm_client, rows, labels, unnamed, terms_by_cluster(rows, labels) if unnamed else {})
        label_names.update(named)
        terms_map = terms_by_cluster(rows, labels)
        merges = merge_duplicates(glm_client, vectors, labels, label_names, terms_map, verdict_cache)
        absorbed = absorb_small(vectors, labels)
        splits = split_heterogeneous(vectors, labels)
        final_cids = sorted(np.unique(labels).tolist())
        cohesions = sorted(round(cohesion_of(vectors[labels == c]), 3) for c in final_cids)
        history.append({
            "round": round_no, "named_new": len(unnamed), "merges": merges,
            "absorbed": absorbed, "splits": splits, "categories": len(final_cids),
            "cohesion_min": cohesions[0],
            "cohesion_median": cohesions[len(cohesions) // 2],
        })
        print(f"    第{round_no}轮：命名{len(unnamed)} 合并{merges} 吸收{absorbed} 拆分{splits}"
              f" → {len(final_cids)} 类（内聚 min {cohesions[0]} / 中位 "
              f"{cohesions[len(cohesions) // 2]}）")
        if merges + absorbed + splits == 0:
            break
    return labels, history, label_names


# ---------- 匹配统计与评测 ----------

def per_doc_stats(query_np: np.ndarray, base_np: np.ndarray, base_labels: list[str],
                  loo_positions: list[int] | None = None) -> list[tuple[str, float, float]]:
    try:
        import torch
        use_torch = torch.cuda.is_available()
    except Exception:  # noqa: BLE001
        use_torch = False
    results = []
    k = min(TOP_K, base_np.shape[0])
    if use_torch:
        import torch
        base_t = torch.from_numpy(base_np).cuda()
        for start in range(0, len(query_np), 1024):
            chunk = torch.from_numpy(query_np[start:start + 1024]).cuda()
            sims = chunk @ base_t.T
            if loo_positions is not None:
                rows = torch.arange(sims.shape[0], device=sims.device)
                cols = torch.tensor(loo_positions[start:start + 1024], device=sims.device)
                sims[rows, cols] = -1.0
            topv, topi = sims.topk(k, dim=1)
            bg = sims.mean(dim=1)
            topv, topi, bg = topv.cpu().numpy(), topi.cpu().numpy(), bg.cpu().numpy()
            for r in range(len(topv)):
                votes: dict[str, float] = defaultdict(float)
                for j in range(k):
                    votes[base_labels[int(topi[r, j])]] += float(topv[r, j])
                results.append((max(votes, key=votes.get), float(topv[r].max()), float(bg[r])))
        del base_t
        torch.cuda.empty_cache()
    else:
        for start in range(0, len(query_np), 512):
            sims = query_np[start:start + 512] @ base_np.T
            for r in range(len(sims)):
                row = sims[r]
                if loo_positions is not None:
                    row = row.copy()
                    row[loo_positions[start + r]] = -1.0
                top = np.argpartition(-row, k - 1)[:k]
                votes = defaultdict(float)
                for j in top:
                    votes[base_labels[int(j)]] += float(row[j])
                results.append((max(votes, key=votes.get), float(row[top].max()), float(row.mean())))
    return results


def eval_gates(stats, golds, threshold: float, min_combined: float) -> dict:
    anchored = correct = 0
    per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    pred: Counter = Counter()
    for (label, best, bg), gold in zip(stats, golds):
        per[gold][1] += 1
        if best >= threshold and best + (best - bg) >= min_combined:
            anchored += 1
            pred[label] += 1
            if label == gold:
                correct += 1
                per[gold][0] += 1
    f1s = []
    for topic, (hit, n) in per.items():
        precision = hit / pred[topic] if pred[topic] else 0.0
        recall = hit / n
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {
        "threshold": threshold, "min_combined": min_combined,
        "coverage": round(anchored / len(golds), 4),
        "accuracy": round(correct / anchored, 4) if anchored else 0.0,
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
    }


# ---------- 主流程 ----------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus")
    parser.add_argument("--sample", type=int, default=0, help="0=全量")
    parser.add_argument("--k-list", default="100,120,150")
    parser.add_argument("--out", default="output/anchor_full")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    rows = load_corpus(Path(args.corpus), args.sample)
    vectors = encode_all([r["text"] for r in rows])

    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import silhouette_score
    k_list = [int(x) for x in args.k_list.split(",")]
    scores = {}
    for k in k_list:
        trial = MiniBatchKMeans(n_clusters=k, random_state=SEED, batch_size=4096, n_init=5
                                ).fit_predict(vectors)
        scores[k] = float(silhouette_score(vectors, trial, sample_size=5000, random_state=SEED))
        print(f"    k={k:3d} silhouette={scores[k]:.4f}")
    best_k = max(scores, key=scores.get)
    print(f"[3] 选定 k={best_k}")
    labels = MiniBatchKMeans(n_clusters=best_k, random_state=SEED, batch_size=4096, n_init=10
                             ).fit_predict(vectors).astype(np.int64)

    from infrastructure.llm.glm_client import glm_client
    print("[4] 自动审查循环（GLM 判定合并 / 吸收 / 拆分 / 命名）…")
    labels, history, label_names = review_loop(glm_client, rows, vectors, labels)

    cids = sorted(np.unique(labels).tolist(), key=lambda c: -int((labels == c).sum()))
    id_map = {int(c): f"{TOPIC_PREFIX}{i + 1:02d}" for i, c in enumerate(cids)}
    topic_names = {id_map[int(c)]: label_names.get(int(c), f"topic_{int(c)}") for c in cids}
    rng = random.Random(SEED)
    train_pos, test_pos = [], []
    for c in cids:
        members = np.where(labels == c)[0].tolist()
        rng.shuffle(members)
        cut = max(1, int(len(members) * TRAIN_RATIO))
        train_pos.extend(members[:cut])
        test_pos.extend(members[cut:])
    train_np = vectors[np.array(train_pos)]
    test_np = vectors[np.array(test_pos)]
    train_ids = [id_map[int(labels[i])] for i in train_pos]
    test_golds = [id_map[int(labels[i])] for i in test_pos]
    print(f"[5] 最终类目 {len(cids)} 个；train={len(train_pos)} test={len(test_pos)}")

    rng2 = random.Random(SEED)
    loo_idx = rng2.sample(range(len(train_pos)), min(LOO_SAMPLE, len(train_pos)))
    loo_stats = per_doc_stats(train_np[loo_idx], train_np, train_ids, loo_positions=loo_idx)
    loo_golds = [train_ids[i] for i in loo_idx]

    test_stats = per_doc_stats(test_np, train_np, train_ids)
    grid = [(t, m) for t in (0.40, 0.45, 0.50) for m in (0.60, 0.65, 0.70, 0.75, 0.80)]
    table = [eval_gates(test_stats, test_golds, t, m) for t, m in grid]
    feasible = [r for r in table if r["coverage"] >= 0.80]
    best = max(feasible or table, key=lambda r: r["macro_f1"])
    print("[6] 阈值网格（测试集）：")
    for r in table:
        mark = " ← 最优" if r is best else ""
        print(f"    thr={r['threshold']} combined={r['min_combined']}"
              f" 覆盖={r['coverage']:.2%} 准确={r['accuracy']:.2%} 宏F1={r['macro_f1']}{mark}")
    loo_at_best = eval_gates(loo_stats, loo_golds, best["threshold"], best["min_combined"])
    print(f"[7] 最优工作点 LOO（抽样{len(loo_idx)}）：覆盖={loo_at_best['coverage']:.2%}"
          f" 准确={loo_at_best['accuracy']:.2%} 宏F1={loo_at_best['macro_f1']}")

    out_dir = PROJECT_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    train_rows = [{
        "document_id": rows[i]["document_id"], "ch_name": "",
        "ch_abstract": rows[i]["text"][:1500], "keywords": [],
        "technical_cluster_id": id_map[int(labels[i])],
        "technical_cluster_name": topic_names[id_map[int(labels[i])]],
    } for i in train_pos]
    test_rows = [{
        "document_id": rows[i]["document_id"], "text": rows[i]["text"][:2000],
        "gold_topic_id": id_map[int(labels[i])],
        "gold_topic_name": topic_names[id_map[int(labels[i])]],
    } for i in test_pos]
    terms_map = terms_by_cluster(rows, labels, max_per=300)
    taxonomy = [{
        "topic_id": id_map[int(c)], "topic_name": topic_names[id_map[int(c)]],
        "size": int((labels == c).sum()),
        "cohesion": round(cohesion_of(vectors[labels == c]), 4),
        "top_terms": terms_map.get(int(c), []),
    } for c in cids]
    (out_dir / "anchor_train.json").write_text(json.dumps(train_rows, ensure_ascii=False), encoding="utf-8")
    (out_dir / "eval_test.json").write_text(json.dumps(test_rows, ensure_ascii=False), encoding="utf-8")
    (out_dir / "taxonomy.json").write_text(
        json.dumps({"topics": taxonomy}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps({
        "k_sweep": scores, "review_history": history,
        "final_categories": len(cids), "calibration_table": table,
        "operating_point": best, "loo_at_best": loo_at_best,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    with (out_dir / "review_sample.csv").open("w", encoding="utf-8") as handle:
        handle.write("topic_id,topic_name,size,cohesion,top_terms\n")
        for t in taxonomy:
            handle.write(f"{t['topic_id']},\"{t['topic_name']}\",{t['size']},{t['cohesion']},"
                         f"\"{'/'.join(t['top_terms'][:6])}\"\n")
    print(f"[8] 产出 → {out_dir}")

    if args.install:
        slot = PROJECT_ROOT / "rules" / "deep_clustering" / "gold" / "anchor_gold_current.json"
        if slot.exists():
            slot.replace(slot.with_suffix(".json.bak"))
        slot.write_text(json.dumps(train_rows, ensure_ascii=False), encoding="utf-8")
        stat = slot.stat()
        digest = hashlib.md5(
            f"{slot.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|technical".encode()).hexdigest()[:16]
        cache = PROJECT_ROOT / "rag_store" / "deep_clustering_anchor"
        cache.mkdir(parents=True, exist_ok=True)
        np.save(cache / f"anchors_{digest}.npy", train_np)
        (cache / f"anchors_{digest}.json").write_text(
            json.dumps({"labels": train_ids,
                        "doc_ids": [r["document_id"] for r in train_rows]}, ensure_ascii=False),
            encoding="utf-8")
        print(f"[9] 已装入内置槽位（{len(train_rows)} 篇 / {len(cids)} 类目），"
              f"预写缓存 anchors_{digest}.npy（{train_np.nbytes / 1e6:.0f}MB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
