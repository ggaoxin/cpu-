"""关键词召回语义评估（2026-09-09）：字面 + 语义双口径离线重算。

用法：python3 scripts/tools/keyword_eval_semantic.py [eval_result.jsonl]
（默认取最近一次 /tmp/eval_rescue2.jsonl；JSONL 每行含 label/gold/preds/hits）

字面口径：双向子串匹配（eval_ab 同款）。
语义口径：bge-m3 本地编码，未字面命中的 gold 与全部 pred 算余弦相似度，
≥ 阈值（默认 0.65）计"主题相关命中"。阈值由对照组校准：随机跨文档配对
400 对的中位 0.431 / P95 0.564，0.65 有充足安全边际；0.6 约新增 3~4 个
边界误配（self-play↔Self-Harmony 类"相关但不等同"），0.65 以上基本干净。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

THRESHOLD = 0.65


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s).casefold()


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/eval_rescue2.jsonl"
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    ok = [r for r in rows if r.get("status") == "ok"]

    from infrastructure.rag.m3_encoder import m3_encoder
    import numpy as np
    terms = list(dict.fromkeys(
        t for r in ok for t in list(r["preds"]) + list(r["gold"]) if norm(t)))
    idx = {t: i for i, t in enumerate(terms)}
    vecs = np.asarray(m3_encoder.encode(terms))
    vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)

    lit_recalls, sem_recalls, gained = [], [], []
    for r in ok:
        hits = set(r["hits"])
        lit_recalls.append(len(hits) / len(r["gold"]))
        for g in r["gold"]:
            if g in hits or norm(g) not in idx:
                continue
            sims = [float(vecs[idx[g]] @ vecs[idx[p]]) for p in r["preds"] if norm(p) in idx]
            if sims and max(sims) >= THRESHOLD:
                hits.add(g)
                gained.append((r["label"], g, r["preds"][sims.index(max(sims))], round(max(sims), 2)))
        sem_recalls.append(len(hits) / len(r["gold"]))

    print(f"样本 {len(ok)} 篇 | 字面宏召回 {sum(lit_recalls)/len(ok):.3f} | "
          f"语义@{THRESHOLD} 宏召回 {sum(sem_recalls)/len(ok):.3f}（新增 {len(gained)}）")
    for lbl, g, p, s in sorted(gained, key=lambda x: -x[3])[:12]:
        print(f"  {lbl}: {g!r} ← {p!r} ({s})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
