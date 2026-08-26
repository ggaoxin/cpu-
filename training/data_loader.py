"""数据加载与对齐。

读取两份 JSON（摘要 / 标准语步结果），按顺序一一对齐，归一化为统一样本结构：
    {
        "id": int,
        "abstract": str,                       # 原摘要
        "spans": {"研究背景": str, ...5个语步},  # 标准划分（空语步为 ""）
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List

from training.config import DATA_DIR, DATASET_LIMIT
from training.profile import get_profile


@dataclass
class Sample:
    id: int
    abstract: str
    spans: Dict[str, str] = field(default_factory=dict)

    def nonempty_moves(self) -> List[str]:
        return [m for m in get_profile().moves if self.spans.get(m, "").strip()]

    def move_profile(self) -> str:
        """语步构成指纹，用于分层抽样。如 '研究目的|研究方法|研究结果'。"""
        return "|".join(self.nonempty_moves())


def load_dataset(limit: int = None) -> List[Sample]:
    """加载并对齐数据集，可只用前 limit 篇。按当前 profile 选语言，缓存到 data/dataset_<lang>.json。"""
    if limit is None:
        limit = DATASET_LIMIT
    p = get_profile()
    cache = DATA_DIR / f"dataset_{p.lang}.json"
    if cache.exists():
        with open(cache, "r", encoding="utf-8") as f:
            raw = json.load(f)
        samples = [Sample(id=r["id"], abstract=r["abstract"], spans=r["spans"]) for r in raw]
        return samples[:limit] if limit else samples

    with open(p.abstracts_file, "r", encoding="utf-8") as f:
        abstracts = json.load(f)
    with open(p.results_file, "r", encoding="utf-8") as f:
        moves = json.load(f)

    if len(abstracts) != len(moves):
        raise ValueError(f"两份数据数量不一致: {len(abstracts)} vs {len(moves)}")

    samples: List[Sample] = []
    for i, (a, m) in enumerate(zip(abstracts, moves)):
        abstract = a.get(p.abstract_key) or m.get(p.abstract_key) or m.get("abstract", "")
        spans = {k: (m.get("move_results", {}).get(k, "") or "") for k in p.moves}
        samples.append(Sample(id=i, abstract=abstract, spans=spans))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(
            [{"id": s.id, "abstract": s.abstract, "spans": s.spans} for s in samples],
            f, ensure_ascii=False,
        )
    return samples[:limit] if limit else samples


if __name__ == "__main__":
    ds = load_dataset()
    print(f"加载 {len(ds)} 篇")
    print("样本0 spans keys:", list(ds[0].spans.keys()))
    print("样本0 非空语步:", ds[0].nonempty_moves())
    print("样本0 profile:", ds[0].move_profile())
