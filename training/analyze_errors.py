"""错例分析：用当前规则库在样本上跑，打印所有句级错判（gold≠pred）。

用法： python -m training.analyze_errors --size 30
"""
from __future__ import annotations

import argparse
import logging

from training.batch import classify_batch
from training.config import RULE_FILE
from training.data_loader import load_dataset
from training.data_split import split_dataset
from training.rule_lib import RuleLib
from training.sentence_seg import segment, assign_sentences_to_spans

logging.basicConfig(level=logging.WARNING)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=30)
    args = ap.parse_args()

    ds = load_dataset()
    holdout, _ = split_dataset(ds)
    samples = holdout[:args.size]
    lib = RuleLib.load(RULE_FILE)

    preds = classify_batch([s.abstract for s in samples], lib, show_progress=True)

    n_err = 0
    for s, pred in zip(samples, preds):
        sents = segment(s.abstract)
        gold_labels = assign_sentences_to_spans(sents, s.spans)
        pred_labels = assign_sentences_to_spans(sents, pred)
        has_err = any(g != p for g, p in zip(gold_labels, pred_labels))
        if not has_err:
            continue
        print(f"\n===== 样本 id={s.id} (错例) =====")
        print(f"摘要: {s.abstract[:120]}...")
        for sent, g, p in zip(sents, gold_labels, pred_labels):
            mark = "  " if g == p else "✗ "
            print(f"{mark}gold={g or '(无)':<6} pred={p or '(无)':<6} | {sent[:80]}")
            if g != p:
                n_err += 1
    print(f"\n共 {n_err} 个错分句")


if __name__ == "__main__":
    main()
