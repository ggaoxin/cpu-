"""基线评测：用当前规则库（不调优）在留出集上测准确率。

用法：
    python -m training.eval_baseline --size 50
    python -m training.eval_baseline --size 400   # 全留出集
"""
from __future__ import annotations

import argparse
import json
import logging
import time

from training.batch import classify_batch
from training.config import RULE_FILE, RUNS_DIR
from training.data_loader import load_dataset
from training.data_split import split_dataset
from training.evaluator import evaluate_preds
from training.rule_lib import RuleLib

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("eval")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=50, help="留出集评测篇数")
    args = ap.parse_args()

    ds = load_dataset()
    holdout, _ = split_dataset(ds)
    eval_set = holdout[:args.size]
    logger.info("基线评测：留出集 %d 篇（共 %d）", len(eval_set), len(holdout))

    lib = RuleLib.load(RULE_FILE)
    logger.info("当前规则库规则数=%d", len(lib.rules))

    t0 = time.time()
    preds = classify_batch([s.abstract for s in eval_set], lib, show_progress=True)
    report = evaluate_preds(eval_set, preds)
    logger.info("评测完成，耗时 %.1fs", time.time() - t0)
    print("\n===== 基线评测结果 =====")
    print(report.summary())

    out = RUNS_DIR / f"baseline_eval_{int(t0)}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "size": len(eval_set),
            "rule_count": len(lib.rules),
            "accuracy": report.accuracy,
            "macro_f1": report.macro_f1,
            "per_move": report.per_move,
            "elapsed_sec": round(time.time() - t0, 1),
        }, f, ensure_ascii=False, indent=2)
    logger.info("结果已保存: %s", out)


if __name__ == "__main__":
    main()
