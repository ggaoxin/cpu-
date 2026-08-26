"""应用 gold 审查修正（Agent 输出的 corrections），生成 v2 gold。

读 gold_corrections_technical.json + gold_corrections_application.json，
修正 gold_zh_model_reviewed_round3_1000.csv 的父类标注，输出 gold_zh_reviewed_v2.csv。
"""
from __future__ import annotations

import csv
import json
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

ROOT = settings.RULES_DIR / "deep_clustering"
FIELD = {"technical": "technical_cluster_id", "application": "application_cluster_id"}


def main() -> None:
    # 读修正
    corrections = {}  # (num, axis) -> correct_id
    for axis, fname in [("technical", "gold_corrections_technical.json"),
                        ("application", "gold_corrections_application.json")]:
        p = ROOT / "v7_reference" / "gold" / fname
        if not p.exists():
            print(f"缺 {fname}，跳过 {axis}", flush=True)
            continue
        n = 0
        for c in json.load(open(p, encoding="utf-8")):
            try:
                num = int(str(c["document_id"]).split("_")[-1])
            except Exception:
                continue
            cid = str(c.get("correct_id", "")).strip()
            if cid and cid != c.get("gold"):
                corrections[(num, axis)] = cid
                n += 1
        print(f"{axis}: {n} 处修正", flush=True)

    # 应用到 gold csv
    gold_path = ROOT / "v7_reference" / "gold" / "gold_zh_model_reviewed_round3_1000.csv"
    v2_path = ROOT / "v7_reference" / "gold" / "gold_zh_reviewed_v2.csv"
    rows = list(csv.DictReader(open(gold_path, encoding="utf-8-sig")))
    n_applied = 0
    for r in rows:
        try:
            num = int(r["document_id"].split("_")[-1])
        except Exception:
            continue
        for axis in ("technical", "application"):
            if (num, axis) in corrections:
                r[FIELD[axis]] = corrections[(num, axis)]
                n_applied += 1
    with open(v2_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"\n应用 {n_applied} 处修正 → {v2_path}", flush=True)
    print(f"重跑对照: python -m scripts.clustering_eval_gold", flush=True)


if __name__ == "__main__":
    main()
