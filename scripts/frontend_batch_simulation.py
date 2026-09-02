#!/usr/bin/env python3
"""模拟前端批量使用形态：随机 10 组 × 20 篇，真实 API 聚类，对照 gold 评测。

组来源：eval_test.json（50,483 篇，均不在锚点库内，带 gold 类目标签）。
两种模式各跑一遍：
  free     = 前端默认（自由聚类划分 + 锚点命名）
  aligned  = partition_strategy=anchor_aligned（类簇直接按人工类目对齐）

每组记录：覆盖率、文档级锚定准确率、簇数、锚定簇数、OUTLIER 数、
锚定簇名与成员 gold 多数类的一致率。publication_date 取随机历史日期
（仅满足接口必填，不影响聚类，仅影响趋势统计）。
"""
from __future__ import annotations

import json
import random
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path("/root/autodl-tmp/semantic_toolkit")
API = "http://127.0.0.1:8000/api/v1/cluster/deep/texts"
GROUPS = 10
BATCH = 20
MODES = ("free", "aligned")


def run_group(rows: list[dict], mode: str, arbiter: bool = True) -> dict:
    payload = {
        "input_type": "texts",
        "scientific_document_texts": [
            {"document_id": r["document_id"], "text": r["text"]} for r in rows],
        "document_metadata": [
            {"document_id": r["document_id"],
             "publication_date": f"20{14 + i % 11}-0{1 + i % 9}-1{i % 9}",
             # title 置空：与锚点库构建口径一致（库内 ch_name=""），
             # 评测输入不得携带 gold 类目名（那是答案泄露）
             "title": "", "keywords": [], "authors": [], "source": ""}
            for i, r in enumerate(rows)],
        "cluster_dimension": "technology",
        "clustering_algorithm_type": "auto",
        "cluster_count": None,
        "output_format": "JSON",
    }
    if mode == "aligned":
        payload["partition_strategy"] = "anchor_aligned"
    if not arbiter:
        payload["anchor_arbiter"] = "off"
    request = urllib.request.Request(
        API, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    started = time.time()
    response = json.load(urllib.request.urlopen(request, timeout=560))
    data = response.get("data") or {}
    elapsed = time.time() - started

    gold = {r["document_id"]: r["gold_topic_id"] for r in rows}
    assignments = data.get("document_assignments") or []
    anchored = [a for a in assignments if a.get("anchored_topic_id")]
    correct = sum(1 for a in anchored if a["anchored_topic_id"] == gold.get(a["document_id"]))
    clusters = data.get("technical_topics") or []
    anchored_clusters = [c for c in clusters if c.get("anchor_status") == "anchored"]
    # 锚定簇名 vs 成员 gold 多数类 一致率
    name_hits = name_total = 0
    member_gold: dict[str, Counter] = {}
    for a in assignments:
        member_gold.setdefault(a.get("cluster_id"), Counter())[gold.get(a["document_id"])] += 1
    for c in anchored_clusters:
        majority = member_gold.get(c.get("cluster_id"), Counter()).most_common(1)
        if majority:
            name_total += 1
            if majority[0][0] == c.get("anchored_topic_id"):
                name_hits += 1
    outliers = sum(1 for c in clusters if c.get("cluster_id") == "OUTLIER")
    return {
        "elapsed": round(elapsed),
        "n": len(assignments),
        "anchored": len(anchored),
        "coverage": round(len(anchored) / max(1, len(assignments)), 3),
        "accuracy": round(correct / len(anchored), 3) if anchored else 0.0,
        "clusters": len(clusters),
        "anchored_clusters": len(anchored_clusters),
        "outliers": outliers,
        "name_match": f"{name_hits}/{name_total}" if name_total else "-",
    }


def main() -> None:
    import sys
    arbiter = "--no-arbiter" not in sys.argv
    suffix = "" if arbiter else "_noarbiter"
    test_rows = json.loads((ROOT / "output/anchor_full/eval_test.json").read_text())
    rng = random.Random(2026)
    results = {}
    for mode in MODES:
        print(f"\n===== 模式：{mode}（判别头仲裁={'开' if arbiter else '关'}）=====", flush=True)
        mode_results = []
        groups = [rng.sample(test_rows, BATCH) for _ in range(GROUPS)]
        for gi, rows in enumerate(groups, 1):
            try:
                stat = run_group(rows, mode, arbiter=arbiter)
            except Exception as exc:  # noqa: BLE001
                stat = {"error": str(exc)[:160]}
            mode_results.append(stat)
            print(f"  组{gi:02d}: {stat}", flush=True)
        results[mode] = mode_results

    print("\n===== 汇总 =====", flush=True)
    summary = {}
    for mode, items in results.items():
        ok = [x for x in items if "error" not in x]
        if not ok:
            summary[mode] = {"all_failed": True}
            continue
        cov = sum(x["coverage"] for x in ok) / len(ok)
        acc = sum(x["accuracy"] for x in ok) / len(ok)
        summary[mode] = {
            "成功组数": f"{len(ok)}/{len(items)}",
            "平均耗时(s)": round(sum(x["elapsed"] for x in ok) / len(ok)),
            "平均覆盖率": round(cov, 3),
            "平均锚定准确率": round(acc, 3),
            "平均簇数": round(sum(x["clusters"] for x in ok) / len(ok), 1),
            "平均锚定簇数": round(sum(x["anchored_clusters"] for x in ok) / len(ok), 1),
            "平均OUTLIER": round(sum(x["outliers"] for x in ok) / len(ok), 1),
        }
        print(f"  {mode}: {summary[mode]}", flush=True)
    (ROOT / f"output/anchor_full/frontend_batch_simulation{suffix}.json").write_text(
        json.dumps({"per_group": results, "summary": summary,
                    "input_note": "title置空,与锚点库口径一致(无答案泄露)",
                    "arbiter": arbiter}, ensure_ascii=False, indent=1),
        encoding="utf-8")


if __name__ == "__main__":
    main()
