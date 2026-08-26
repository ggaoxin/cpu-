"""验证改进的准入准则（源摘要+跨篇双校验）+ 研究目的攻关 是否有希望提升测试准确率。

流程（仅用前 20 篇）：
  1. 14 篇训练 / 6 篇测试（固定种子）；
  2. 基线10条 在测试集上评测；
  3. 用【双校验】准入在 14 篇训练集上归纳2轮 → 改进规则库；
  4. 改进规则库 在测试集上评测；
  5. 对比 acc / macroF1 / 各语步F1，重点看研究目的。

用法： python -m training.validate_improved
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

from training.batch import classify_batch
from training.config import RULE_FILE
from training.data_loader import load_dataset
from training.evaluator import evaluate_preds
from training.rule_inducer import induce_and_validate
from training.rule_lib import RuleLib

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("validate")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_LIB = PROJECT_ROOT / "training" / "runs" / "baseline10.yaml"


def main():
    ds = load_dataset(limit=20)
    rng = random.Random(7)
    idx = list(range(len(ds))); rng.shuffle(idx)
    train = [ds[i] for i in idx[:14]]
    test = [ds[i] for i in idx[14:]]
    logger.info("验证集：训练 %d 篇 / 测试 %d 篇", len(train), len(test))

    # 1. 基线评测
    base_lib = RuleLib.load(BASELINE_LIB)
    logger.info(">>> 基线10条 测试集评测（规则数=%d）", len(base_lib.rules))
    preds = classify_batch([s.abstract for s in test], base_lib, show_progress=True)
    base_rep = evaluate_preds(test, preds)

    # 2. 改进规则库：双校验归纳2轮
    lib = RuleLib.load(BASELINE_LIB)  # 从基线出发
    for it in range(1, 3):
        logger.info(">>> 改进归纳 第%d轮（双校验）", it)
        lib = induce_and_validate(lib, train, induce_sample_size=14, use_cross_check=True)

    logger.info(">>> 改进规则库 测试集评测（规则数=%d）", len(lib.rules))
    preds2 = classify_batch([s.abstract for s in test], lib, show_progress=True)
    new_rep = evaluate_preds(test, preds2)

    # 3. 对比
    moves = ["研究背景", "研究目的", "研究方法", "研究结果", "研究结论"]
    print("\n================ 验证对比（测试集 %d 篇）================" % len(test))
    print(f"{'规则库':<14}{'规则数':<8}{'acc':<10}{'macroF1':<10}{'背景':<8}{'目的':<8}{'方法':<8}{'结果':<8}{'结论':<8}")
    for name, r, n in [("基线10条", base_rep, 10), ("改进(双校验)", new_rep, len(lib.rules))]:
        f1 = {m: r.per_move.get(m, {}).get("f1", 0) for m in moves}
        print(f"{name:<14}{n:<8}{r.accuracy:<10.4f}{r.macro_f1:<10.4f}"
              f"{f1['研究背景']:<8.3f}{f1['研究目的']:<8.3f}{f1['研究方法']:<8.3f}{f1['研究结果']:<8.3f}{f1['研究结论']:<8.3f}")

    # 判定是否有希望
    delta_acc = new_rep.accuracy - base_rep.accuracy
    delta_purpose = (new_rep.per_move.get("研究目的", {}).get("f1", 0)
                     - base_rep.per_move.get("研究目的", {}).get("f1", 0))
    print(f"\nΔacc={delta_acc:+.4f}  Δ研究目的F1={delta_purpose:+.4f}")
    if delta_acc >= 0 and delta_purpose >= 0:
        print("=> 有希望：改进未降低整体准确率且研究目的不退化，可推进 200 篇训练")
    elif delta_acc >= -0.02:
        print("=> 基本持平：过拟合已被控制（不再像之前那样掉点），可谨慎推进 200 篇")
    else:
        print("=> 无希望：改进仍降低准确率，需进一步调整策略")


if __name__ == "__main__":
    main()
