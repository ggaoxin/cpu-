"""批量并发语步分类，加速训练评估。

GLM 单次约 20-30s，串行不可行。用线程池并发调用（IO 密集）。
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from tqdm import tqdm

from training.config import MAX_WORKERS
from training.move_classifier import classify_full
from training.rule_lib import RuleLib

logger = logging.getLogger(__name__)


def classify_batch(
    abstracts: List[str],
    rule_lib: RuleLib,
    temperature: float = 0.1,
    max_workers: int = MAX_WORKERS,
    show_progress: bool = True,
    do_review: bool = True,
) -> List[Dict[str, str]]:
    """并发对多篇摘要做语步划分，返回与 abstracts 等长的 spans 列表。"""
    full = classify_batch_full(abstracts, rule_lib, temperature=temperature,
                               max_workers=max_workers, show_progress=show_progress,
                               do_review=do_review)
    return [r["spans"] for r in full]


def classify_batch_full(
    abstracts: List[str],
    rule_lib: RuleLib,
    temperature: float = 0.1,
    max_workers: int = MAX_WORKERS,
    show_progress: bool = True,
    do_review: bool = True,
) -> List[Dict[str, Any]]:
    """并发分类，返回完整结果（spans + evidence + confidence + 冲突信息）。"""
    results: List[Dict[str, Any]] = [None] * len(abstracts)  # type: ignore

    def _work(idx, ab):
        return idx, classify_full(ab, rule_lib, temperature=temperature, do_review=do_review)

    iterator = range(len(abstracts))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_work, i, abstracts[i]): i for i in iterator}
        bar = tqdm(total=len(futures), desc="classify", disable=not show_progress)
        for fut in as_completed(futures):
            idx, res = fut.result()
            results[idx] = res
            bar.update(1)
        bar.close()
    return results
