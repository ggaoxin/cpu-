"""ac_domain 专业领域分类评测（两层）。

对 64 篇（32领域×2）跑管线，统计：
- 第一层：domain 精确准确率（domain_code 命中）
- 第二层：clc 学科边界命中（branch）/ 同分支（hier）/ 精确号
- 两层一致性（pred domain 与 pred clc 学科是否对应）
- 防幻觉（clc 号真实存在于 RAG）

用法：python -m training.eval_domain_classification --n 64
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from application.dto.common_dto import SemanticRequest  # noqa: E402
from application.service.semantic_service import SemanticApplicationService  # noqa: E402
from infrastructure.llm.glm_client import glm_client  # noqa: E402
from infrastructure.rule_engine.rule_loader import rule_loader  # noqa: E402
from config.settings import settings

PAPERS = str(settings.DATA_DIR / "professional_domain_classification_32x2_zh_simple.json")
GOLD = str(settings.DATA_DIR / "professional_domain_64_classification.json")
RUNS_DIR = PROJECT_ROOT / "training" / "runs"


def discipline(code: str) -> str:
    code = (code or "").strip()
    if not code:
        return ""
    return code[:2] if code[0] == "T" else code[:1]


_PARENT = {}
def _load_parent():
    if _PARENT:
        return
    for e in json.load(open(str(settings.CLC_META_FULL), encoding="utf-8")):
        _PARENT[e["clc_code"]] = e.get("parent_code")


def ancestors(code):
    _load_parent()
    seen, cur = set(), code
    while cur and cur not in seen:
        seen.add(cur); cur = _PARENT.get(cur)
    return seen


def same_branch(a, b):
    if not a or not b:
        return False
    return a in ancestors(b) or b in ancestors(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--top-k", type=int, default=25)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    papers = json.load(open(PAPERS, encoding="utf-8"))[:args.n]
    gold = json.load(open(GOLD, encoding="utf-8"))[:args.n]
    svc = SemanticApplicationService(glm_client, rule_loader)

    n_dom = n_branch = n_hier = n_clc = n_valid = n_consist = 0
    records = []
    for i, (p, g) in enumerate(zip(papers, gold), 1):
        req = SemanticRequest(text=json.dumps(p, ensure_ascii=False), params={"top_k": args.top_k})
        t0 = time.time()
        try:
            res = svc.execute("ac_domain", req)
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}/{args.n}] 异常: {exc}", flush=True)
            records.append({"id": g.get("sample_id", i), "error": str(exc)})
            continue
        dt = time.time() - t0
        if not res.success:
            print(f"[{i}/{args.n}] 失败: {res.error}", flush=True)
            records.append({"id": g.get("sample_id", i), "error": res.error})
            continue
        d = res.data or {}
        pred_dom = d.get("domain_code", "")
        pred_clc = (d.get("clc_classification") or {}).get("clc_code", "")
        gold_dom = g["domain_code"]
        gold_clc = g["clc_classification"]["clc_code"]
        align = d.get("alignment_check") or {}

        if pred_dom == gold_dom:
            n_dom += 1
        if discipline(pred_clc) == discipline(gold_clc) and pred_clc:
            n_branch += 1
        if same_branch(pred_clc, gold_clc):
            n_hier += 1
        if pred_clc == gold_clc:
            n_clc += 1
        if align.get("clc_code_exists_in_rag"):
            n_valid += 1
        # 两层一致：pred domain 与 pred clc 学科对应（用 gold domain→clc 映射粗判）
        n_consist += 1  # 占位，下面按 domain==gold_dom 且 branch 命中算

        ok = "✓" if pred_dom == gold_dom else "✗"
        okc = "=" if discipline(pred_clc) == discipline(gold_clc) else "!"
        print(f"[{i}/{args.n}] {dt:.0f}s {ok}{okc} dom={pred_dom}/{gold_dom} clc={pred_clc}/{gold_clc}", flush=True)
        records.append({"id": g.get("sample_id", i), "pred_dom": pred_dom, "gold_dom": gold_dom,
                        "pred_clc": pred_clc, "gold_clc": gold_clc,
                        "dom_correct": pred_dom == gold_dom,
                        "branch_correct": discipline(pred_clc) == discipline(gold_clc) and bool(pred_clc),
                        "hier_correct": same_branch(pred_clc, gold_clc)})

    n_ok = len([r for r in records if "error" not in r])
    summary = {
        "n": args.n, "n_ok": n_ok,
        "domain_acc": round(n_dom / max(n_ok, 1), 3),
        "clc_branch_acc": round(n_branch / max(n_ok, 1), 3),
        "clc_hier_acc": round(n_hier / max(n_ok, 1), 3),
        "clc_acc": round(n_clc / max(n_ok, 1), 3),
        "anti_hallucination_pass": round(n_valid / max(n_ok, 1), 3),
    }
    print("\n========== 汇总 ==========")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    out = args.out or str(RUNS_DIR / f"ac_domain_eval_n{args.n}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"summary": summary, "records": records}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n明细：{out}")


if __name__ == "__main__":
    main()
