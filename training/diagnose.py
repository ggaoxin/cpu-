"""诊断：在同一批留出集上对比 基线10 / 单折最佳(折2) / 聚合22，定位泛化问题来源。

用法： python -m training.diagnose --size 100
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from training.batch import classify_batch
from training.config import RULE_FILE
from training.data_loader import load_dataset
from training.data_split import split_dataset
from training.evaluator import evaluate_preds
from training.rule_lib import RuleLib

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("diag")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = PROJECT_ROOT / "training" / "runs" / "run_1785320294"
LIBS = {
    "基线10条": PROJECT_ROOT / "training" / "runs" / "baseline10.yaml",
    "单折最佳(折2)": RUN_DIR / "fold_2" / "rule_lib.yaml",
    "聚合22条(运行时)": PROJECT_ROOT / "rules" / "move_recognition" / "mr_zh_abstract.yaml",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=100)
    args = ap.parse_args()

    ds = load_dataset()
    holdout, _ = split_dataset(ds)
    eval_set = holdout[:args.size]
    logger.info("诊断评测：留出集 %d 篇", len(eval_set))

    results = {}
    for name, path in LIBS.items():
        lib = RuleLib.load(path)
        logger.info("\n>>> 评测 %s（规则数=%d）", name, len(lib.rules))
        t0 = time.time()
        preds = classify_batch([s.abstract for s in eval_set], lib, show_progress=True)
        rep = evaluate_preds(eval_set, preds)
        logger.info("%s 完成 acc=%.4f macroF1=%.4f 耗时%.0fs",
                    name, rep.accuracy, rep.macro_f1, time.time() - t0)
        results[name] = rep

    print("\n================ 诊断对比（留出集 %d 篇）================" % len(eval_set))
    print(f"{'规则库':<16}{'规则数':<8}{'acc':<10}{'macroF1':<10}{'背景':<8}{'目的':<8}{'方法':<8}{'结果':<8}{'结论':<8}")
    for name, path in LIBS.items():
        lib = RuleLib.load(path)
        r = results[name]
        f1 = {m: r.per_move.get(m, {}).get("f1", 0) for m in ["研究背景", "研究目的", "研究方法", "研究结果", "研究结论"]}
        print(f"{name:<16}{len(lib.rules):<8}{r.accuracy:<10.4f}{r.macro_f1:<10.4f}"
              f"{f1['研究背景']:<8.3f}{f1['研究目的']:<8.3f}{f1['研究方法']:<8.3f}{f1['研究结果']:<8.3f}{f1['研究结论']:<8.3f}")


if __name__ == "__main__":
    main()
