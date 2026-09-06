#!/usr/bin/env python3
"""gold 子集语步提取：91 类 × 每类 ≤N 篇摘要 → 方法/背景/目的句库（v2 双轴底座）。

产出 /tmp/gold_moves.json：
  [{idx, method:[...], background:[...], purpose:[...], tech_label, app_label}]
提取用生产语步引擎（中文摘要语步识别管线），线程池并发。
"""
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD_JSON = ROOT / "rules/deep_clustering/gold/anchor_gold_current.json"
PER_CLASS = 30          # 每类抽取篇数
MAX_WORKERS = 8

def main():
    from training.move_classifier import classify_full
    from training.rule_lib import RuleLib

    docs = json.loads(GOLD_JSON.read_text(encoding="utf-8"))
    rng = __import__("random").Random(2026)
    by_tech = defaultdict(list)
    for i, d in enumerate(docs):
        if d.get("technical_cluster_id") and str(d.get("ch_abstract") or "").strip():
            by_tech[d["technical_cluster_id"]].append(i)
    chosen = []
    for label, idx_list in by_tech.items():
        chosen.extend(rng.sample(idx_list, min(PER_CLASS, len(idx_list))))
    print(f"91 类抽样: {len(chosen)} 篇", flush=True)

    rule_lib = RuleLib.load(ROOT / "rules/move_recognition/mr_zh_abstract.yaml")

    def one(i):
        abstract = str(docs[i]["ch_abstract"]).strip()
        try:
            res = classify_full(abstract, rule_lib, do_review=False)
            pairs = [(s.get("text") or "", s.get("llm_label") or "")
                     for s in (res.get("evidence") or []) if s.get("llm_label")]
        except Exception:  # noqa: BLE001
            pairs = []
        return {
            "idx": i,
            "method": [s for s, mv in pairs if mv == "研究方法"],
            "background": [s for s, mv in pairs if mv == "研究背景"],
            "purpose": [s for s, mv in pairs if mv == "研究目的"],
            "tech_label": docs[i]["technical_cluster_id"],
            "app_label": docs[i].get("application_cluster_id"),
        }

    results, done = [], 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for row in pool.map(one, chosen):
            results.append(row)
            done += 1
            if done % 200 == 0:
                hit_m = sum(1 for r in results if r["method"])
                hit_s = sum(1 for r in results if r["background"] or r["purpose"])
                print(f"[{done}/{len(chosen)}] 方法句覆盖 {hit_m}/{done} 场景句覆盖 {hit_s}/{done}", flush=True)

    Path("/tmp/gold_moves.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    hit_m = sum(1 for r in results if r["method"])
    hit_s = sum(1 for r in results if r["background"] or r["purpose"])
    print(f"\n完成: {len(results)} 篇 | 方法句覆盖 {hit_m} | 场景句覆盖 {hit_s}")
    print("已存 /tmp/gold_moves.json")

if __name__ == "__main__":
    main()
