"""中文科技文献分类（ac_zh）基线评测。

对 50 篇留出集跑 RAG→LLM→校验 管线，统计：
- 主分类号精确准确率（main_acc）
- 主分类号大类准确率（top-level 首字母命中，main_top_acc）
- 主或辅助命中 gold 主（main_or_aux_hit）
- 辅助分类匹配（gold 有辅助时，pred 辅助是否命中 gold 辅助）
- 交叉学科准确率与 F1（inter_acc / inter_f1）
- 防幻觉校验通过率（alignment_check 全真且号真实存在于知识库）

用法：
  python -m training.eval_classification --n 50 --top-k 20
  python -m training.eval_classification --n 10 --out runs/ac_zh_eval.json
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

PAPERS = str(settings.DATA_DIR / "random_50_chinese_papers.json")
# v3 标准：基于完整 CLC 知识库(40912条)的自主判定，细码优先；v2 为旧粗码对照
GOLD = str(settings.DATA_DIR / "random_50_chinese_papers_clc_classification_v3.json")
RUNS_DIR = PROJECT_ROOT / "training" / "runs"


def top_level(code: str) -> str:
    """中图法大类：分类号首字母（如 TP311→T，F291.1→F）。"""
    return (code or "").strip()[:1]


def discipline(code: str) -> str:
    """学科边界：T 大类取前两字符（TM/TP/TQ/TU…），其余取首字母。

    与 ac_zh 交叉学科判定准则一致——衡量"是否判对学科"比精确号更公允
    （GLM 提议的细码经 resolve_code 上溯后可能与 gold 粒度不同但同分支）。
    """
    code = (code or "").strip()
    if not code:
        return ""
    if code[0] == "T":
        return code[:2]
    return code[:1]


# 父链索引（用于层级匹配：pred 是 gold 的下位/上位/相等即算对）
_PARENT = {}
def _load_parent():
    if _PARENT:
        return
    import json as _j
    for e in _j.load(open(str(settings.CLC_META_FULL), encoding="utf-8")):
        _PARENT[e["clc_code"]] = e.get("parent_code")


def ancestors(code: str) -> set:
    """code 的全部祖先（含自身）。"""
    _load_parent()
    seen, cur = set(), code
    while cur and cur not in seen:
        seen.add(cur)
        cur = _PARENT.get(cur)
    return seen


def same_branch(a: str, b: str) -> bool:
    """a 与 b 在同一分支（其一为另一个的祖先/相等）。"""
    if not a or not b:
        return False
    return a in ancestors(b) or b in ancestors(a)


def evaluate(n: int, top_k: int, out_path: str | None, code: str = "ac_zh",
             papers_file: str = PAPERS, gold_file: str = GOLD):
    papers = json.load(open(papers_file, encoding="utf-8"))[:n]
    gold = json.load(open(gold_file, encoding="utf-8"))[:n]

    svc = SemanticApplicationService(glm_client, rule_loader)

    n_main = n_hier = n_branch = n_top = n_main_or_aux = 0
    n_aux_gold = n_aux_hit = 0
    n_inter_tp = n_inter_fp = n_inter_fn = n_inter_tn = 0
    n_valid = 0
    records = []

    for i, (p, g) in enumerate(zip(papers, gold), 1):
        req = SemanticRequest(text=json.dumps(p, ensure_ascii=False),
                              params={"top_k": top_k})
        t0 = time.time()
        try:
            res = svc.execute(code, req)
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}/{n}] 异常: {exc}", flush=True)
            records.append({"sample_id": g.get("sample_id", i), "error": str(exc)})
            continue
        dt = time.time() - t0

        if not res.success:
            print(f"[{i}/{n}] 失败: {res.error}", flush=True)
            records.append({"sample_id": g.get("sample_id", i), "error": res.error})
            continue

        data = res.data or {}
        pred_main = (data.get("main_classification") or {}).get("clc_code", "")
        pred_aux = [a["clc_code"] for a in (data.get("auxiliary_classifications") or [])]
        pred_inter = bool(data.get("is_interdisciplinary"))
        align = data.get("alignment_check") or {}

        gold_main = g["main_classification"]["clc_code"]
        gold_aux = [a["clc_code"] for a in g.get("auxiliary_classifications", [])]
        gold_inter = bool(g.get("is_interdisciplinary"))

        # 主分类
        if pred_main == gold_main:
            n_main += 1
        if same_branch(pred_main, gold_main):
            n_hier += 1
        if discipline(pred_main) == discipline(gold_main) and pred_main:
            n_branch += 1
        if top_level(pred_main) == top_level(gold_main) and pred_main:
            n_top += 1
        if gold_main in ({pred_main} | set(pred_aux)):
            n_main_or_aux += 1
        # 辅助：gold 辅助与 pred 辅助同分支即算命中
        if gold_aux:
            n_aux_gold += 1
            if any(any(same_branch(ga, pa) for pa in pred_aux) for ga in gold_aux):
                n_aux_hit += 1
        # 交叉学科
        if pred_inter and gold_inter:
            n_inter_tp += 1
        elif pred_inter and not gold_inter:
            n_inter_fp += 1
        elif not pred_inter and gold_inter:
            n_inter_fn += 1
        else:
            n_inter_tn += 1
        # 防幻觉
        if align.get("all_codes_exist_in_clc_meta") and align.get("paths_copied_from_clc_meta"):
            n_valid += 1

        ok_main = "✓" if pred_main == gold_main else ("≈" if same_branch(pred_main, gold_main) else "✗")
        print(f"[{i}/{n}] {dt:.1f}s {ok_main} pred={pred_main or '-'} gold={gold_main} "
              f"inter={pred_inter}/{gold_inter} aux={pred_aux}/{gold_aux}", flush=True)
        records.append({
            "sample_id": g.get("sample_id", i),
            "pred_main": pred_main, "gold_main": gold_main,
            "pred_aux": pred_aux, "gold_aux": gold_aux,
            "pred_inter": pred_inter, "gold_inter": gold_inter,
            "main_correct": pred_main == gold_main,
            "hier_correct": same_branch(pred_main, gold_main),
            "branch_correct": discipline(pred_main) == discipline(gold_main) and bool(pred_main),
            "alignment_ok": bool(align.get("all_codes_exist_in_clc_meta")),
            "selection_reason": data.get("selection_reason", ""),
        })

    n_ok = len([r for r in records if "error" not in r])
    inter_prec = n_inter_tp / max(n_inter_tp + n_inter_fp, 1)
    inter_rec = n_inter_tp / max(n_inter_tp + n_inter_fn, 1)
    inter_f1 = 2 * inter_prec * inter_rec / max(inter_prec + inter_rec, 1e-9)

    summary = {
        "n": n, "n_ok": n_ok, "top_k": top_k,
        "main_acc": round(n_main / max(n_ok, 1), 3),
        "main_hier_acc": round(n_hier / max(n_ok, 1), 3),
        "main_branch_acc": round(n_branch / max(n_ok, 1), 3),
        "main_top_acc": round(n_top / max(n_ok, 1), 3),
        "main_or_aux_hit": round(n_main_or_aux / max(n_ok, 1), 3),
        "aux_match": round(n_aux_hit / max(n_aux_gold, 1), 3),
        "aux_gold_count": n_aux_gold,
        "inter_acc": round((n_inter_tp + n_inter_tn) / max(n_ok, 1), 3),
        "inter_precision": round(inter_prec, 3),
        "inter_recall": round(inter_rec, 3),
        "inter_f1": round(inter_f1, 3),
        "anti_hallucination_pass": round(n_valid / max(n_ok, 1), 3),
    }
    print("\n========== 汇总 ==========")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        json.dump({"summary": summary, "records": records},
                  open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n明细已保存：{out_path}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--top-k", type=int, default=25)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--code", type=str, default="ac_zh")
    ap.add_argument("--papers", type=str, default=PAPERS)
    ap.add_argument("--gold", type=str, default=GOLD)
    args = ap.parse_args()
    out = args.out or str(RUNS_DIR / f"{args.code}_eval_n{args.n}.json")
    evaluate(args.n, args.top_k, out, code=args.code, papers_file=args.papers, gold_file=args.gold)
