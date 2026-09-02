#!/usr/bin/env python3
"""深度聚类锚点资源生效性自检。

用途：在把"训练样本/人工标注类目数据"接入深度聚类之前，先验证这份资源
**真的能起作用**——格式能不能被正确解析、类目能不能被投票选中。

两层检查：
1. 格式校验：行数、类目标签字段、文本长度（≥30字）、跳过行统计、
   类目在内置主题映射表中的中文名解析情况。
2. 留一法自匹配（LOO）：锚点文献互认测试——每篇文献只在"其余文献构成的
   锚点库"上做匹配（排除自身，防止 sim=1.0 自带作弊），用与产线完全相同
   的投票+门槛逻辑（threshold=0.45、组合分≥0.70）判定锚定类目是否等于
   自己的人工标注类目。LOO 准确率高 ⇒ 这份标注数据内部一致、可区分，
   接入后对真实文献的锚定才有意义；LOO 低 ⇒ 类目体系重叠或标注矛盾，
   先修数据再接入。

用法：
  python -m scripts.verify_anchor_resource <gold.json> [--axis both] [--sample 120]
退出码：0=通过  1=不通过（可接入 CI / 前置门禁）
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.clustering.anchor_labeling import (  # noqa: E402
    GoldAnchorIndex,
    _anchor_text,
    _DEFAULT_MATCH_THRESHOLD,
    _MIN_COMBINED_MATCH,
)

PASS_ACCURACY = 0.70   # LOO 锚定准确率下限（已锚定样本中）
PASS_COVERAGE = 0.50   # LOO 覆盖率下限（多少文献至少能通过门槛）


def validate_format(rows: list[dict], axis: str) -> dict:
    label_field = "technical_cluster_id" if axis == "technical" else "application_cluster_id"
    skipped = {"no_label": 0, "short_text": 0}
    labels, texts = [], []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            skipped["no_label"] += 1
            continue
        label = str(row.get(label_field) or "").strip()
        text = _anchor_text(
            row.get("ch_name") or row.get("title") or "",
            row.get("ch_abstract") or row.get("abstract") or "",
            row.get("keywords") or [],
        )
        if not label:
            skipped["no_label"] += 1
            continue
        if len(text.strip()) < 30:
            skipped["short_text"] += 1
            continue
        labels.append(label)
        texts.append((str(row.get("document_id") or f"ROW{index + 1}"), label, text))
    return {"label_field": label_field, "valid": len(labels), "skipped": skipped,
            "labels": labels, "texts": texts}


def leave_one_out(vectors: np.ndarray, labels: list[str], *, top_k: int = 5) -> dict:
    """与产线 match_documents 相同的投票+门槛逻辑，但排除自身相似度。"""
    sims = vectors @ vectors.T
    np.fill_diagonal(sims, -1.0)  # 自身不参与投票与统计
    total = len(labels)
    anchored = correct = 0
    per_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # label -> [命中, 参与]
    for i in range(total):
        row = sims[i]
        k = max(1, min(top_k, total - 1))
        top = np.argpartition(-row, k - 1)[:k]
        votes: dict[str, float] = defaultdict(float)
        for j in top:
            votes[labels[int(j)]] += float(row[j])
        best_label = max(votes, key=votes.get)
        best_sim = float(row[top].max())
        background = float(np.delete(row, i).mean())  # 背景均值同样排除自身
        combined = best_sim + (best_sim - background)
        per_category[labels[i]][1] += 1
        if best_sim >= _DEFAULT_MATCH_THRESHOLD and combined >= _MIN_COMBINED_MATCH:
            anchored += 1
            if best_label == labels[i]:
                correct += 1
                per_category[labels[i]][0] += 1
    return {
        "total": total,
        "anchored": anchored,
        "coverage": round(anchored / total, 4) if total else 0.0,
        "correct": correct,
        "accuracy": round(correct / anchored, 4) if anchored else 0.0,
        "overall_accuracy": round(correct / total, 4) if total else 0.0,
        "per_category": {
            label: {"hit": hit, "n": n, "acc": round(hit / n, 3) if n else 0.0}
            for label, (hit, n) in sorted(per_category.items(), key=lambda kv: -kv[1][1])
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold", help="标注数据 JSON/JSONL 文件路径")
    parser.add_argument("--axis", choices=["technical", "application", "both"], default="both")
    parser.add_argument("--sample", type=int, default=120, help="LOO 抽样上限（控制时长，0=全量）")
    args = parser.parse_args()

    path = Path(args.gold)
    if not path.is_file():
        print(f"❌ 文件不存在：{path}")
        return 1
    raw = path.read_text(encoding="utf-8-sig")
    rows = (
        [json.loads(line) for line in raw.splitlines() if line.strip()]
        if path.suffix.lower() in {".jsonl", ".ndjson"} else json.loads(raw)
    )
    if isinstance(rows, dict):
        rows = next((rows[k] for k in ("data", "documents", "records") if isinstance(rows.get(k), list)), [])
    if not isinstance(rows, list) or not rows:
        print("❌ 不是非空的 JSON 数组 / JSONL")
        return 1

    axes = ["technical", "application"] if args.axis == "both" else [args.axis]
    overall_pass = True
    for axis in axes:
        print(f"\n========== 轴：{axis} ==========")
        fmt = validate_format(rows, axis)
        print(f"总行数 {len(rows)} | 有效 {fmt['valid']} | 跳过 {fmt['skipped']}"
              f"（依据字段 {fmt['label_field']}）")
        if not fmt["valid"]:
            print(f"❌ [{axis}] 没有任何有效行——接入后将触发空库保护，锚点不会生效")
            overall_pass = False
            continue
        distribution = Counter(fmt["labels"])
        print(f"类目数 {len(distribution)} | 最大类 {distribution.most_common(3)}")

        index = GoldAnchorIndex.get(path, axis)
        stats = index.stats()
        unnamed = stats.get("unnamed_categories") or []
        if unnamed:
            print(f"⚠️  {len(unnamed)} 个类目在主题映射表无中文名（锚定后显示裸ID）: {unnamed[:8]}")
        else:
            print("✓ 全部类目可解析中文名")

        loo_rows = fmt["texts"]
        if args.sample and len(loo_rows) > args.sample:
            step = max(1, len(loo_rows) // args.sample)
            loo_rows = loo_rows[::step][: args.sample]
            print(f"LOO 抽样 {len(loo_rows)} 篇")
        from infrastructure.rag.m3_encoder import m3_encoder
        vectors = m3_encoder.encode([text for _, _, text in loo_rows])
        result = leave_one_out(vectors, [label for _, label, _ in loo_rows])

        print(f"LOO 覆盖率   : {result['coverage']}（{result['anchored']}/{result['total']} 通过门槛）")
        print(f"LOO 锚定准确率: {result['accuracy']}（{result['correct']}/{result['anchored']} 锚定正确）")
        print(f"综合准确率    : {result['overall_accuracy']}")
        weak = {label: v for label, v in result["per_category"].items() if v["n"] >= 3 and v["acc"] < 0.5}
        if weak:
            print(f"⚠️  弱类目（<3 篇样本且准确率<50%，建议补样本或与相邻类目合并）:")
            for label, v in list(weak.items())[:8]:
                print(f"    {label}: {v['hit']}/{v['n']}")
        passed = result["accuracy"] >= PASS_ACCURACY and result["coverage"] >= PASS_COVERAGE
        print(("✅ 通过" if passed else "❌ 不通过")
              + f"（门槛：准确率≥{PASS_ACCURACY} 且 覆盖率≥{PASS_COVERAGE}）")
        overall_pass = overall_pass and passed
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
