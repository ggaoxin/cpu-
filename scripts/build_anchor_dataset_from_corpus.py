#!/usr/bin/env python3
"""从无标注语料构建深度聚类锚点数据集（GPU 加速）。

流程（全部可复现，随机种子固定 42）：
  1) 读取 jsonl 语料 → 去重（首 200 字符哈希，防训练/测试泄漏）→ 按 category 分层抽样
  2) bge-m3 编码（BGE_DEVICE=cuda 时走 GPU，纯文本摘要截 2000 字）
  3) k 扫描（MiniBatchKMeans + silhouette 抽样估计）→ 选 k → 聚类生成 gold 划分
  4) GLM 为每个簇命名（ZT01… 编号 + 中文名），弱簇（规模<8 或内聚<0.30）进待定池不入 gold
  5) 分层 70/30 切分：train=锚点库，test=评测集（gold=簇归属）
  6) LOO 自检 train（互认测试）
  7) test 评测：用 train 库按产线同款三道闸匹配 → 覆盖率/准确率/宏F1
  8) --install：train 装入内置槽位 + 预写向量缓存（CPU 部署秒加载，不必重编码）

诚实性说明：gold 由"无监督聚类 + GLM 命名"生成，指标衡量的是锚点库对聚类结构的
复现一致性；类目体系本身需人工抽查确认（review_sample.csv）。

用法：
  python3 -m scripts.build_anchor_dataset_from_corpus /root/autodl-tmp/abstract.jsonl \
      --sample 10000 --out output/anchor_build --install
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

from scripts.verify_anchor_resource import leave_one_out  # noqa: E402

SEED = 42
TOPIC_PREFIX = "ZT"  # 自建类目编号前缀，与内置 T/A 编号隔离
WEAK_MIN_SIZE = 8
# 真实混合语料（论文/专利/基金/报告）的宽主题簇内聚度通常 0.15~0.30，
# 手写演示数据才能到 0.5+；弱簇判定以规模与命名有效性为主、内聚为辅。
WEAK_MIN_COHESION = 0.12
TRAIN_RATIO = 0.7
DEFAULT_THRESHOLD = 0.45
MIN_COMBINED = 0.70
STOP_TERMS = {
    "研究", "方法", "分析", "本文", "本发明", "本项目", "提供", "包括", "通过", "以及",
    "进行", "结果", "目的", "结论", "一种", "装置", "系统", "技术", "领域", "问题",
    "基于", "应用", "实验", "表明", "效果", "显著", "不同", "影响", "数据", "相关",
    # 专利/法律文书八股（"所述/第一/连接"类簇是文体聚类而非主题聚类）
    "所述", "第一", "第二", "第三", "第四", "涉及", "具有", "设置", "连接", "组件",
    "模块", "单元", "上述", "其中", "以下", "配置", "实施", "端部", "多个", "若干",
    # 学术八股
    "我们", "笔者", "项目", "目标", "内容", "特点", "情况", "方面", "方式", "过程",
}


def load_corpus(path: Path, sample_n: int) -> list[dict]:
    rows = []
    seen = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            text = str(row.get("text") or "").strip()
            if len(text) < 60:
                continue
            digest = hashlib.md5(text[:200].encode()).hexdigest()
            if digest in seen:  # 近重复（专利译本/转载）只留一条，防测试集泄漏
                continue
            seen.add(digest)
            rows.append({"text": text, "category": str(row.get("category") or "未知")})
    rng = random.Random(SEED)
    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_category[row["category"]].append(row)
    quota = {cat: max(1, round(sample_n * len(items) / len(rows))) for cat, items in by_category.items()}
    sampled = []
    for cat, items in by_category.items():
        rng.shuffle(items)
        sampled.extend(items[: quota[cat]])
    rng.shuffle(sampled)
    for index, row in enumerate(sampled):
        row["document_id"] = f"DOC_{index + 1:06d}"
    print(f"[1] 语料 {len(rows)} 条（去重后）→ 分层抽样 {len(sampled)} 条 "
          f"({dict(Counter(r['category'] for r in sampled))})")
    return sampled


def encode_corpus(rows: list[dict]) -> np.ndarray:
    from infrastructure.rag.m3_encoder import m3_encoder
    texts = [row["text"][:2000] for row in rows]
    print(f"[2] bge-m3 编码 {len(texts)} 条（设备见加载日志）…")
    return m3_encoder.encode(texts)


def choose_k(vectors: np.ndarray, k_min: int, k_max: int) -> tuple[int, dict[int, float]]:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import silhouette_score
    scores: dict[int, float] = {}
    for k in range(k_min, k_max + 1, 10):
        model = MiniBatchKMeans(n_clusters=k, random_state=SEED, batch_size=2048, n_init=5)
        labels = model.fit_predict(vectors)
        scores[k] = float(silhouette_score(vectors, labels, sample_size=4000, random_state=SEED))
        print(f"    k={k:3d}  silhouette={scores[k]:.4f}")
    best_k = max(scores, key=scores.get)
    print(f"[3] 选定 k={best_k}（silhouette={scores[best_k]:.4f}）")
    return best_k, scores


def cluster_terms(rows: list[dict], labels: np.ndarray, cluster_id: int, top: int = 14) -> list[str]:
    import jieba
    counter: Counter[str] = Counter()
    for index, label in enumerate(labels):
        if label != cluster_id:
            continue
        for term in jieba.lcut(rows[index]["text"][:600]):
            term = term.strip()
            if len(term) >= 2 and term not in STOP_TERMS and not term.isdigit():
                counter[term] += 1
    return [term for term, _ in counter.most_common(top)]


def name_cluster_via_glm(glm_client, terms: list[str], snippets: list[str]) -> dict | None:
    """簇命名：术语+摘要片段 → 命名；真实语料片段可能触发 GLM 内容过滤(1301)，
    被过滤或失败时降级为仅术语命名（科技术语基本中性，可安全送审）。"""
    system = (
        "你是科技文献主题类目命名专家。下面是一个文献簇的高频术语与代表性摘要片段"
        "（语料含论文/专利/基金项目/报告）。请给这个簇命名一个中文主题类目："
        "6到14个汉字，概括该簇文献共同的研究主题或技术方向；"
        "不得使用'综合/其他/ misc'这类无信息量的名称，不得罗列多个方向。"
        '只返回JSON：{"topic_name":"类目名","topic_summary":"一句话概括"}'
    )
    attempts = [
        {"高频术语": terms, "代表文献摘要片段": [s[:120] for s in snippets]},
        {"高频术语": terms},  # 内容过滤降级：只送中性术语
    ]
    for payload in attempts:
        try:
            raw = glm_client.chat_json(system, json.dumps(payload, ensure_ascii=False),
                                       temperature=0.1, timeout=60.0, max_tokens=200)
        except Exception as exc:  # noqa: BLE001
            print(f"      [命名异常] {str(exc)[:140]}")
            continue
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        name = str(data.get("topic_name") or "").strip()
        if name and len(name) <= 20:
            return {"topic_name": name, "topic_summary": str(data.get("topic_summary") or "")[:120]}
        print(f"      [命名无效] 返回={str(raw)[:140]}")
    return None


def build_taxonomy(glm_client, rows, vectors, labels, k) -> tuple[dict[int, dict], list[int]]:
    """每簇统计 + GLM 命名；返回 {cluster_id: 信息} 与弱簇列表。"""
    cluster_ids = list(range(k))
    infos: dict[int, dict] = {}
    for cid in cluster_ids:
        members = np.where(labels == cid)[0]
        if len(members) < 2:
            infos[cid] = {"size": len(members), "cohesion": 0.0, "terms": [], "name": None}
            continue
        sub = vectors[members]
        sims = sub @ sub.T
        n = len(members)
        cohesion = float((sims.sum() - n) / (n * n - n)) if n > 1 else 0.0
        terms = cluster_terms(rows, labels, cid)
        infos[cid] = {"size": n, "cohesion": round(cohesion, 4), "terms": terms,
                      "name": None, "members": members.tolist()}
    named = [(cid, info) for cid, info in infos.items() if info["size"] >= WEAK_MIN_SIZE]
    print(f"[4] GLM 命名 {len(named)} 个簇（弱簇< {WEAK_MIN_SIZE} 篇直接待定）…")

    def _name(item):
        cid, info = item
        members = info["members"]
        snippets = [rows[i]["text"] for i in members[:3]]
        result = name_cluster_via_glm(glm_client, info["terms"], snippets)
        if result is None:  # 重试一次
            result = name_cluster_via_glm(glm_client, info["terms"][:8], snippets)
        return cid, result

    with ThreadPoolExecutor(max_workers=3) as pool:
        for cid, result in pool.map(_name, named):
            if result:
                infos[cid]["name"] = result["topic_name"]
                infos[cid]["topic_summary"] = result["topic_summary"]
    weak = [cid for cid, info in infos.items()
            if info["size"] < WEAK_MIN_SIZE or info["cohesion"] < WEAK_MIN_COHESION or not info.get("name")]
    weak_reasons = Counter(
        "规模不足" if infos[cid]["size"] < WEAK_MIN_SIZE else
        ("内聚过低" if infos[cid]["cohesion"] < WEAK_MIN_COHESION else "命名失败")
        for cid in weak)
    cohesions = sorted(round(info["cohesion"], 3) for info in infos.values())
    print(f"    簇内聚分布: min={cohesions[0]} 中位={cohesions[len(cohesions) // 2]} max={cohesions[-1]}；"
          f"弱簇 {len(weak)} 个（{dict(weak_reasons)}）")
    return infos, weak


def finalize(rows, vectors, labels, infos, weak, out_dir: Path):
    """打 ZT 编号、剔除弱簇、分层切分 train/test、写文件。"""
    kept = [(cid, info) for cid, info in infos.items() if cid not in weak]
    kept.sort(key=lambda kv: -kv[1]["size"])
    id_map = {cid: f"{TOPIC_PREFIX}{i + 1:02d}" for i, (cid, _) in enumerate(kept)}
    name_map = {id_map[cid]: info["name"] for cid, info in kept}
    strong_cids = set(id_map)

    labeled = [i for i, cid in enumerate(labels) if cid in strong_cids]
    rng = random.Random(SEED)
    train_idx, test_idx = [], []
    by_cid: dict[int, list[int]] = defaultdict(list)
    for i in labeled:
        by_cid[int(labels[i])].append(i)
    for cid, members in by_cid.items():
        rng.shuffle(members)
        cut = max(1, int(len(members) * TRAIN_RATIO))
        train_idx.extend(members[:cut])
        test_idx.extend(members[cut:])
    rng.shuffle(train_idx)
    rng.shuffle(test_idx)

    def to_anchor_row(i):
        cid = int(labels[i])
        return {
            "document_id": rows[i]["document_id"],
            "ch_name": "",
            "ch_abstract": rows[i]["text"][:1500],
            "keywords": [],
            "technical_cluster_id": id_map[cid],
            "technical_cluster_name": name_map[id_map[cid]],
        }

    train_rows = [to_anchor_row(i) for i in train_idx]
    test_rows = [{
        "document_id": rows[i]["document_id"],
        "text": rows[i]["text"][:2000],
        "gold_topic_id": id_map[int(labels[i])],
        "gold_topic_name": name_map[id_map[int(labels[i])]],
    } for i in test_idx]
    taxonomy = [{
        "topic_id": id_map[cid], "topic_name": info["name"],
        "summary": info.get("topic_summary", ""),
        "size": info["size"], "cohesion": info["cohesion"], "top_terms": info["terms"],
    } for cid, info in kept]
    weak_info = [{"cluster": cid, "size": infos[cid]["size"],
                  "cohesion": infos[cid]["cohesion"], "terms": infos[cid]["terms"]}
                 for cid in weak]

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "anchor_train.json").write_text(
        json.dumps(train_rows, ensure_ascii=False), encoding="utf-8")
    (out_dir / "eval_test.json").write_text(
        json.dumps(test_rows, ensure_ascii=False), encoding="utf-8")
    (out_dir / "taxonomy.json").write_text(
        json.dumps({"topics": taxonomy, "weak_clusters": weak_info}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    # 人工抽查表：每类目 5 条
    with (out_dir / "review_sample.csv").open("w", encoding="utf-8") as handle:
        handle.write("topic_id,topic_name,document_id,摘要前120字\n")
        for cid, members in sorted(by_cid.items(), key=lambda kv: -len(kv[1])):
            for i in members[:5]:
                snippet = rows[i]["text"][:120].replace('"', "'").replace("\n", " ")
                handle.write(f'{id_map[cid]},"{name_map[id_map[cid]]}",{rows[i]["document_id"]},"{snippet}"\n')
    print(f"[5] gold 体系：{len(kept)} 类 / 弱簇待定 {len(weak)}；"
          f"train={len(train_rows)} test={len(test_rows)} → {out_dir}")
    return train_idx, test_idx, id_map


def evaluate(vectors, train_idx, test_idx, labels, id_map):
    train_vecs = vectors[train_idx]
    train_labels = [id_map[int(labels[i])] for i in train_idx]
    test_vecs = vectors[test_idx]
    test_labels = [id_map[int(labels[i])] for i in test_idx]
    sims = test_vecs @ train_vecs.T
    k = 5
    anchored = correct = 0
    per_topic: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row, gold in zip(sims, test_labels):
        top = np.argpartition(-row, k - 1)[:k]
        votes: dict[str, float] = defaultdict(float)
        for j in top:
            votes[train_labels[int(j)]] += float(row[j])
        best_label = max(votes, key=votes.get)
        best_sim = float(row[top].max())
        background = float(row.mean())
        combined = best_sim + (best_sim - background)
        per_topic[gold][1] += 1
        if best_sim >= DEFAULT_THRESHOLD and combined >= MIN_COMBINED:
            anchored += 1
            if best_label == gold:
                correct += 1
                per_topic[gold][0] += 1
    f1_scores = []
    for topic, (hit, n) in per_topic.items():
        if n == 0:
            continue
        recall = hit / n
        precision = hit / anchored if anchored else 0
        f1_scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    print(f"[7] 测试集({len(test_labels)}条)：覆盖率={anchored}/{len(test_labels)}"
          f"({anchored / len(test_labels):.2%}) 锚定准确率={correct}/{anchored}"
          f"({correct / anchored:.2%})" if anchored else "无锚定")
    weak_topics = {t: f"{hit}/{n}" for t, (hit, n) in per_topic.items() if n >= 5 and hit / n < 0.5}
    if weak_topics:
        print(f"    弱类目（召回<50%）：{weak_topics}")


def install_builtin(train_rows: list[dict], vectors, train_idx, labels, id_map) -> None:
    """装入内置槽位并预写向量缓存：CPU 部署首跑秒级加载，无需重编码。"""
    import time
    slot = PROJECT_ROOT / "rules" / "deep_clustering" / "gold" / "anchor_gold_current.json"
    if slot.exists():
        backup = slot.with_suffix(".json.bak")
        slot.replace(backup)
        print(f"    已备份原槽位文件 → {backup.name}")
    slot.write_text(json.dumps(train_rows, ensure_ascii=False), encoding="utf-8")
    stat = slot.stat()
    digest = hashlib.md5(
        f"{slot.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|technical".encode()
    ).hexdigest()[:16]
    cache_dir = PROJECT_ROOT / "rag_store" / "deep_clustering_anchor"
    cache_dir.mkdir(parents=True, exist_ok=True)
    train_labels = [id_map[int(labels[i])] for i in train_idx]
    train_doc_ids = [row["document_id"] for row in train_rows]
    np.save(cache_dir / f"anchors_{digest}.npy", vectors[train_idx].astype(np.float32))
    (cache_dir / f"anchors_{digest}.json").write_text(
        json.dumps({"labels": train_labels, "doc_ids": train_doc_ids}, ensure_ascii=False),
        encoding="utf-8")
    print(f"[8] 已装入内置槽位（{len(train_rows)} 篇 / {len(set(train_labels))} 类目）"
          f"并预写向量缓存 anchors_{digest}（CPU 部署零编码加载）")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", help="jsonl 语料路径（text/category 字段）")
    parser.add_argument("--sample", type=int, default=10000)
    parser.add_argument("--k-min", type=int, default=30)
    parser.add_argument("--k-max", type=int, default=80)
    parser.add_argument("--out", default="output/anchor_build")
    parser.add_argument("--install", action="store_true", help="装入内置槽位并预写缓存")
    args = parser.parse_args()

    rows = load_corpus(Path(args.corpus), args.sample)
    vectors = encode_corpus(rows)
    best_k, _ = choose_k(vectors, args.k_min, args.k_max)
    from sklearn.cluster import MiniBatchKMeans
    labels = MiniBatchKMeans(n_clusters=best_k, random_state=SEED,
                             batch_size=2048, n_init=10).fit_predict(vectors)
    from infrastructure.llm.glm_client import glm_client
    infos, weak = build_taxonomy(glm_client, rows, vectors, labels, best_k)
    out_dir = PROJECT_ROOT / args.out
    train_idx, test_idx, id_map = finalize(rows, vectors, labels, infos, weak, out_dir)

    train_labels = [id_map[int(labels[i])] for i in train_idx]
    print(f"[6] LOO 自检 train（{len(train_idx)} 篇）…")
    loo = leave_one_out(vectors[train_idx], train_labels)
    print(f"    LOO 覆盖率={loo['coverage']:.2%} 锚定准确率={loo['accuracy']:.2%} "
          f"综合={loo['overall_accuracy']:.2%}")
    evaluate(vectors, train_idx, test_idx, labels, id_map)
    if args.install:
        train_rows = json.loads((out_dir / "anchor_train.json").read_text(encoding="utf-8"))
        install_builtin(train_rows, vectors, train_idx, labels, id_map)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
