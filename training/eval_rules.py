"""规则库评测脚本：在留出集上评测指定规则库的 acc/macroF1/各语步F1。

用于 20 篇验证里程碑：对比基线(principles+种子规则) vs 改进(训练后)规则库。

用法：
    # 评测当前运行时规则库（基线）
    python -m training.eval_rules --n 20

    # 评测某次训练产物
    python -m training.eval_rules --n 20 --lib training/runs/run_xxx/final_rule_lib.yaml

    # 纯 principles（无 pattern_rules）对照
    python -m training.eval_rules --n 20 --no-rules
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from training.batch import classify_batch
from training.config import EVAL_DO_REVIEW
from training.data_loader import load_dataset
from training.data_split import split_dataset
from training.evaluator import evaluate_preds
from training.profile import get_profile, set_profile_by_lang
from training.rule_lib import RuleLib

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("eval")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="评测篇数")
    ap.add_argument("--lib", type=str, default=None, help="规则库 YAML 路径（默认运行时）")
    ap.add_argument("--no-rules", action="store_true", help="清空 pattern_rules，只留 principles（纯LLM对照）")
    ap.add_argument("--no-review", action="store_true", help="不触发冲突二次审核")
    ap.add_argument("--lang", choices=["zh", "en"], default="zh", help="语言（zh中文/en英文）")
    args = ap.parse_args()

    set_profile_by_lang(args.lang)
    lib_path = Path(args.lib) if args.lib else get_profile().rule_file
    lib = RuleLib.load(lib_path)
    if args.no_rules:
        lib.pattern_rules = []
        print("模式: 纯 principles（无 pattern_rules）")
    else:
        print(f"规则库: {lib_path} (pattern_rules={len(lib.pattern_rules)})")

    ds = load_dataset()
    holdout, _ = split_dataset(ds)
    samples = holdout[:args.n]
    print(f"评测 {len(samples)} 篇留出集摘要...")

    preds = classify_batch([s.abstract for s in samples], lib,
                           show_progress=True, do_review=not args.no_review)
    report = evaluate_preds(samples, preds)
    print("\n===== 评测结果 =====")
    print(report.summary())


if __name__ == "__main__":
    main()
