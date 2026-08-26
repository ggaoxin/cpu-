"""数据划分：400 篇最终留出集 + 剩余 1600 篇 5 折 CV。

- 留出集：固定取出 400 篇，全程不参与训练；
- 5 折：在 1600 篇上按语步构成分层，构造 5 个互不重叠的测试折，每折 320 篇；
- 每折的训练集 = 其余 1280 篇；
- 主种子 42 派生每折种子，保证可复现。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from training.config import HOLDOUT_SIZE, N_FOLDS, RANDOM_SEED, STRATIFY
from training.data_loader import Sample


@dataclass
class Fold:
    fold_id: int
    train: List[Sample]
    test: List[Sample]


def split_dataset(samples: List[Sample]) -> Tuple[List[Sample], List[Sample]]:
    """返回 (holdout, rest)。留出集 = min(HOLDOUT_SIZE, 20% 数据)，全程不参与训练。

    数据少时（如 200 篇）按 20% 留出，避免留出集吃掉全部数据导致 CV 无训练集。
    三集分离（rule.pdf 第6条）：fold.train=开发集(生成规则)、fold.test=验证集(早停选规则)、
    holdout=最终冻结测试集(只在最后跑一次，不可据其改规则)。
    """
    rng = random.Random(RANDOM_SEED)
    idx = list(range(len(samples)))
    rng.shuffle(idx)
    h = min(HOLDOUT_SIZE, max(int(0.2 * len(samples)), 1))
    holdout_idx = idx[:h]
    rest_idx = idx[h:]
    holdout = [samples[i] for i in holdout_idx]
    rest = [samples[i] for i in rest_idx]
    return holdout, rest


def make_folds(rest: List[Sample]) -> List[Fold]:
    """对 rest 做 N 折分层 CV。

    分层：按 move_profile 分组，每组轮流把样本分发到各折，保证各折语步构成相近。
    """
    rng = random.Random(RANDOM_SEED + 1)

    # 按 profile 分桶
    buckets: Dict[str, List[Sample]] = {}
    for s in rest:
        key = s.move_profile() if STRATIFY else "_all_"
        buckets.setdefault(key, []).append(s)

    # 每桶内部打乱，再轮流分发到 N 折
    fold_test: List[List[Sample]] = [[] for _ in range(N_FOLDS)]
    for key in sorted(buckets.keys()):
        bucket = buckets[key][:]
        rng.shuffle(bucket)
        for i, s in enumerate(bucket):
            fold_test[i % N_FOLDS].append(s)

    folds: List[Fold] = []
    for fid in range(N_FOLDS):
        test = fold_test[fid]
        test_ids = {s.id for s in test}
        train = [s for s in rest if s.id not in test_ids]
        folds.append(Fold(fold_id=fid, train=train, test=test))
    return folds


if __name__ == "__main__":
    from training.data_loader import load_dataset
    ds = load_dataset()
    holdout, rest = split_dataset(ds)
    folds = make_folds(rest)
    print(f"总数={len(ds)} 留出={len(holdout)} 训练池={len(rest)}")
    for f in folds:
        print(f"  折{f.fold_id}: train={len(f.train)} test={len(f.test)}")
    # 检查测试折互不重叠
    all_test_ids = []
    for f in folds:
        all_test_ids += [s.id for s in f.test]
    print("测试折互不重叠:", len(all_test_ids) == len(set(all_test_ids)) == len(rest))
