"""5 折交叉验证编排：逐折迭代调优。

每折流程：
1. 从基线规则库出发；
2. 每轮：在训练子集上归纳+泛化校验规则 → 在测试集上评估；
3. 若测试准确率不再提升则早停；
4. 保存该折最终规则库与评估报告。

测试集严格隔离，绝不参与归纳/校验。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from training.batch import classify_batch
from training.config import (
    EVAL_SAMPLE_SIZE, INDUCE_SAMPLE_SIZE, MAX_ITERATIONS, GENERALIZE_CHECK_SIZE,
    RUNS_DIR, EVAL_DO_REVIEW, VALIDATE_SIZE,
)
from training.profile import get_profile
from training.data_loader import Sample
from training.data_split import Fold
from training.evaluator import evaluate_preds
from training.rule_inducer import induce_and_validate
from training.rule_lib import RuleLib

logger = logging.getLogger(__name__)


@dataclass
class FoldResult:
    fold_id: int
    iterations: int
    best_test_acc: float
    best_macro_f1: float
    rule_count: int
    per_iteration: List[dict] = field(default_factory=list)
    rule_lib: RuleLib = None  # type: ignore


def run_fold(
    fold: Fold,
    run_dir: Path,
    eval_size: int = EVAL_SAMPLE_SIZE,
    induce_size: int = INDUCE_SAMPLE_SIZE,
    max_iterations: int = MAX_ITERATIONS,
    check_size: int = GENERALIZE_CHECK_SIZE,
    validate_size: int = VALIDATE_SIZE,
) -> FoldResult:
    logger.info("===== 折 %d: train=%d test=%d =====", fold.fold_id, len(fold.train), len(fold.test))
    rule_lib = RuleLib.load(get_profile().rule_file)  # 每折从同一基线出发
    # 开发集再切：归纳集(产出规则) + 验证集(准入净收益，归纳时未见过) —— rule.pdf 第6条
    induce_train = fold.train[:induce_size]
    validate_train = fold.train[induce_size:induce_size + validate_size]
    eval_test = fold.test[:eval_size] if eval_size else fold.test
    logger.info("折%d 开发集切分: 归纳=%d 验证=%d 测试=%d",
                fold.fold_id, len(induce_train), len(validate_train), len(eval_test))

    best_acc = -1.0
    best_lib = rule_lib
    best_report = None
    history: List[dict] = []

    for it in range(1, max_iterations + 1):
        logger.info("折%d 迭代 %d/%d：归纳规则...", fold.fold_id, it, max_iterations)
        rule_lib = induce_and_validate(
            rule_lib, induce_train, induce_size,
            validate_samples=validate_train, check_size=check_size)

        logger.info("折%d 迭代 %d：测试集评估...", fold.fold_id, it)
        preds = classify_batch([s.abstract for s in eval_test], rule_lib,
                               show_progress=False, do_review=EVAL_DO_REVIEW)
        report = evaluate_preds(eval_test, preds)
        logger.info("折%d 迭代%d 测试 acc=%.4f macroF1=%.4f 规则数=%d",
                    fold.fold_id, it, report.accuracy, report.macro_f1, len(rule_lib.rules))

        level_dist = {}
        for r in rule_lib.rules:
            level_dist[r.level] = level_dist.get(r.level, 0) + 1
        history.append({
            "iteration": it,
            "test_acc": report.accuracy,
            "macro_f1": report.macro_f1,
            "rule_count": len(rule_lib.rules),
            "level_dist": level_dist,
        })

        if report.accuracy > best_acc:
            best_acc = report.accuracy
            best_lib = rule_lib
            best_report = report
        else:
            # 准确率不再提升，早停（保留最佳规则库）
            logger.info("折%d 迭代%d 未提升，早停", fold.fold_id, it)
            break

    # 保存该折规则库
    fold_dir = run_dir / f"fold_{fold.fold_id}"
    fold_dir.mkdir(parents=True, exist_ok=True)
    best_lib.save(fold_dir / "rule_lib.yaml")
    with open(fold_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump({
            "fold_id": fold.fold_id,
            "best_test_acc": best_acc,
            "best_macro_f1": best_report.macro_f1 if best_report else 0,
            "history": history,
            "rule_count": len(best_lib.rules),
        }, f, ensure_ascii=False, indent=2)

    return FoldResult(
        fold_id=fold.fold_id,
        iterations=len(history),
        best_test_acc=best_acc,
        best_macro_f1=best_report.macro_f1 if best_report else 0,
        rule_count=len(best_lib.rules),
        per_iteration=history,
        rule_lib=best_lib,
    )


def run_cv(
    folds: List[Fold],
    run_dir: Path,
    eval_size: int = EVAL_SAMPLE_SIZE,
    induce_size: int = INDUCE_SAMPLE_SIZE,
    max_iterations: int = MAX_ITERATIONS,
    check_size: int = GENERALIZE_CHECK_SIZE,
    validate_size: int = VALIDATE_SIZE,
) -> List[FoldResult]:
    results: List[FoldResult] = []
    for fold in folds:
        r = run_fold(fold, run_dir, eval_size=eval_size, induce_size=induce_size,
                     max_iterations=max_iterations, check_size=check_size,
                     validate_size=validate_size)
        results.append(r)
    mean_acc = sum(r.best_test_acc for r in results) / len(results)
    logger.info("===== CV 完成：平均测试准确率=%.4f =====", mean_acc)
    return results
