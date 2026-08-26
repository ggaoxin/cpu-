"""训练入口：留出集 + 5折CV + 聚合 + 最终评测。

用法：
    # 小样本快速联调
    python -m training.run_training --smoke

    # 正式运行
    python -m training.run_training

    # 断点续跑：复用 run_dir 下已保存的 fold_*/rule_lib.yaml，只跑缺失的折，再聚合+评测
    python -m training.run_training --resume training/runs/run_1785320294

    # 自定义规模
    python -m training.run_training --eval-size 100 --induce-size 80 --iterations 3
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from training.aggregator import aggregate
from training.batch import classify_batch
from training.config import (
    EVAL_SAMPLE_SIZE, INDUCE_SAMPLE_SIZE, MAX_ITERATIONS, GENERALIZE_CHECK_SIZE,
    HOLDOUT_EVAL_SIZE, RUNS_DIR,
)
from training.cross_validator import FoldResult, run_cv
from training.data_loader import load_dataset
from training.data_split import make_folds, split_dataset
from training.profile import get_profile
from training.evaluator import evaluate_preds
from training.rule_lib import RuleLib

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("train")


def load_existing_fold_result(run_dir: Path, fold_id: int) -> FoldResult | None:
    """从 run_dir/fold_{id}/ 加载已保存的折结果（规则库 + 指标）。不存在返回 None。"""
    fold_dir = run_dir / f"fold_{fold_id}"
    lib_path = fold_dir / "rule_lib.yaml"
    rep_path = fold_dir / "report.json"
    if not lib_path.exists():
        return None
    rule_lib = RuleLib.load(lib_path)
    best_acc = best_f1 = 0.0
    rule_count = len(rule_lib.rules)
    iterations = 0
    if rep_path.exists():
        with open(rep_path, "r", encoding="utf-8") as f:
            rep = json.load(f)
        best_acc = rep.get("best_test_acc", 0.0)
        best_f1 = rep.get("best_macro_f1", 0.0)
        rule_count = rep.get("rule_count", rule_count)
        iterations = rep.get("history", rep.get("iterations", 0))
        iterations = len(iterations) if isinstance(iterations, list) else iterations
    return FoldResult(
        fold_id=fold_id, iterations=iterations, best_test_acc=best_acc,
        best_macro_f1=best_f1, rule_count=rule_count, rule_lib=rule_lib,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="小样本端到端联调")
    ap.add_argument("--eval-size", type=int, default=EVAL_SAMPLE_SIZE)
    ap.add_argument("--induce-size", type=int, default=INDUCE_SAMPLE_SIZE)
    ap.add_argument("--iterations", type=int, default=MAX_ITERATIONS)
    ap.add_argument("--holdout", type=int, default=HOLDOUT_EVAL_SIZE,
                    help="最终留出集评测篇数（默认 HOLDOUT_EVAL_SIZE）")
    ap.add_argument("--resume", type=str, default=None,
                    help="断点续跑：指定 run_dir，复用已保存的 fold_*/rule_lib.yaml，只跑缺失的折")
    ap.add_argument("--no-review", action="store_true",
                    help="评估时不触发冲突二次审核（省 GLM，只测 LLM+引擎）")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh", help="语言（zh中文/en英文）")
    args = ap.parse_args()

    import training.config as cfg
    from training.profile import set_profile_by_lang
    set_profile_by_lang(args.lang)
    if args.no_review:
        cfg.EVAL_DO_REVIEW = False
    if args.smoke:
        eval_size = 4
        induce_size = 4
        iterations = 1
        check_size = 4
        holdout_eval_size = 6
    else:
        eval_size = args.eval_size
        induce_size = args.induce_size
        iterations = args.iterations
        check_size = cfg.GENERALIZE_CHECK_SIZE
        holdout_eval_size = args.holdout

    t0 = time.time()
    logger.info("加载数据集...")
    ds = load_dataset()
    holdout, rest = split_dataset(ds)
    folds = make_folds(rest)
    if args.smoke:
        folds = folds[:2]  # 联调只跑 2 折
    logger.info("留出=%d 训练池=%d 折数=%d (induce=%d eval=%d iter=%d check=%d)",
                len(holdout), len(rest), len(folds), induce_size, eval_size, iterations, check_size)

    # 运行目录：续跑则复用指定 run_dir，否则新建
    if args.resume:
        run_dir = Path(args.resume)
        if not run_dir.exists():
            raise SystemExit(f"续跑目录不存在: {run_dir}")
        logger.info("续跑模式，运行目录: %s", run_dir)
    else:
        run_dir = RUNS_DIR / f"run_{int(t0)}"
        run_dir.mkdir(parents=True, exist_ok=True)
        logger.info("运行目录: %s", run_dir)

    # 1. 5折CV：续跑时复用已保存的折，只跑缺失的
    existing_results: list[FoldResult] = []
    missing_folds = []
    for f in folds:
        if args.resume:
            ex = load_existing_fold_result(run_dir, f.fold_id)
            if ex is not None:
                logger.info("复用已保存折 %d（规则数=%d acc=%.4f）", f.fold_id, ex.rule_count, ex.best_test_acc)
                existing_results.append(ex)
                continue
        missing_folds.append(f)

    new_results = []
    if missing_folds:
        logger.info("需新跑 %d 折: %s", len(missing_folds), [f.fold_id for f in missing_folds])
        new_results = run_cv(
            missing_folds, run_dir, eval_size=eval_size, induce_size=induce_size,
            max_iterations=iterations, check_size=check_size,
            validate_size=cfg.VALIDATE_SIZE,
        )
    else:
        logger.info("所有折均已保存，跳过 CV 训练")

    fold_results = existing_results + new_results
    fold_results.sort(key=lambda r: r.fold_id)
    fold_libs = [r.rule_lib for r in fold_results]

    # 2. 聚合
    baseline = RuleLib.load(get_profile().rule_file)
    final_lib = aggregate(fold_libs, baseline)
    final_lib.save(run_dir / "final_rule_lib.yaml")

    # 3. 在留出集上做最终评测（冻结测试集，只跑一次）
    logger.info("===== 最终留出集评测 =====")
    holdout_eval = holdout[:holdout_eval_size] if holdout_eval_size else holdout
    preds = classify_batch([s.abstract for s in holdout_eval], final_lib,
                           show_progress=True, do_review=cfg.EVAL_DO_REVIEW)
    report = evaluate_preds(holdout_eval, preds)
    logger.info("留出集结果:\n%s", report.summary())

    # 4. 汇总报告
    summary = {
        "run_dir": str(run_dir),
        "resume": bool(args.resume),
        "elapsed_sec": round(time.time() - t0, 1),
        "folds": [
            {"fold_id": r.fold_id, "best_test_acc": r.best_test_acc,
             "best_macro_f1": r.best_macro_f1, "rule_count": r.rule_count,
             "iterations": r.iterations}
            for r in fold_results
        ],
        "cv_mean_acc": sum(r.best_test_acc for r in fold_results) / len(fold_results),
        "holdout_acc": report.accuracy,
        "holdout_macro_f1": report.macro_f1,
        "final_rule_count": len(final_lib.rules),
    }
    with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info("汇总: %s", json.dumps(summary, ensure_ascii=False))

    # 5. 写入运行时规则库（smoke 模式不覆盖）
    if not args.smoke:
        logger.info("将最终规则库写入运行时 %s", get_profile().rule_file)
        final_lib.save(get_profile().rule_file)

    logger.info("完成，耗时 %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
