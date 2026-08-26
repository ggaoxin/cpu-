"""rq_identify 研究问题句识别评测（句级 + 短语级 P/R/F1）。

对 gold（72篇）跑管线，统计：
- 句级：预测 RQ 句 vs gold RQ 句（精确或包含匹配）
- 短语级：预测短语 vs gold 短语（精确或子串）
- 防幻觉通过率（句子是摘要字面子串、短语是句子字面子串）
中英分别统计。

用法：python -m training.eval_rq
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

GOLD = str(settings.DATA_DIR / "rq_sample_72_gold_broad.json")  # 放宽版（gap+目标句）
RUNS_DIR = PROJECT_ROOT / "training" / "runs"

# LLM 裁判：pred 句未命中 gold 时，判其是否也是合理 RQ 句
_judge_cache = {}


def judge_rq(glm, abstract, sentence):
    """GLM 裁判 sentence 是否为该摘要的合理研究问题句（问题/缺口/目标）。"""
    key = (sentence[:60],)
    if key in _judge_cache:
        return _judge_cache[key]
    sysp = ("你是科技文献研究问题识别裁判。判断给定句子是否为该摘要的研究问题句"
            "（表达本文要解决的问题/缺口/探究对象/目标）。只回答JSON：{\"is_rq\":true/false}")
    usr = f"摘要：{abstract}\n待判句子：{sentence}\n该句是否为研究问题句？"
    try:
        d = glm.chat_json(sysp, usr, timeout=60.0, max_tokens=50)
        d = d.get("data", d) if isinstance(d, dict) else d
        is_rq = bool(d.get("is_rq")) if isinstance(d, dict) else False
    except Exception:  # noqa: BLE001
        is_rq = False
    _judge_cache[key] = is_rq
    return is_rq


def _norm(s):
    return (s or "").strip()


def sent_match(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    # 字符重叠率
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa | sb), 1) >= 0.8


def phrase_match(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return False
    return a == b or a in b or b in a


def prf(tp, n_pred, n_gold):
    p = tp / max(n_pred, 1); r = tp / max(n_gold, 1)
    return round(p, 3), round(r, 3), round(2 * p * r / max(p + r, 1e-9), 3)


def eval_set(records, glm=None):
    # 句级：P 用"pred 有效(命中gold或裁判认可)"，R 用"gold 被命中"，分开避免 R>1
    sent_tp_p = sent_tp_r = sent_np = sent_ng = 0
    ph_tp = ph_np = ph_ng = 0
    n_valid = 0
    n_judged_tp = 0
    for r in records:
        pred = r["pred"]; gold = r["gold"]
        sent_np += len(pred); sent_ng += len(gold)
        ph_np += sum(1 for p in pred if p.get("phrase")); ph_ng += sum(1 for g in gold if g.get("phrase"))
        abs_ = r["abstract"]
        g_used = [False] * len(gold)
        for p in pred:
            ps = p.get("sentence", "")
            matched = False
            for j, g in enumerate(gold):
                if not g_used[j] and sent_match(ps, g.get("sentence")):
                    g_used[j] = True; matched = True; break
            if matched:
                sent_tp_p += 1
            elif glm is not None and ps and judge_rq(glm, abs_, ps):
                sent_tp_p += 1; n_judged_tp += 1  # 裁判认可→有效 pred（提 P），不计 R
        sent_tp_r += sum(g_used)  # gold 被命中数（用于 R）
        # 短语匹配
        g_ph_used = [False] * len(gold)
        for p in pred:
            ph = p.get("phrase")
            if not ph:
                continue
            for j, g in enumerate(gold):
                if not g_ph_used[j] and g.get("phrase") and phrase_match(ph, g.get("phrase")):
                    ph_tp += 1; g_ph_used[j] = True; break
        for p in pred:
            if p.get("sentence") in abs_ and (not p.get("phrase") or p["phrase"] in p["sentence"]):
                n_valid += 1
    n_pred_total = sum(len(r["pred"]) for r in records)
    sp = round(sent_tp_p / max(sent_np, 1), 3)
    sr = round(sent_tp_r / max(sent_ng, 1), 3)
    sf = round(2 * sp * sr / max(sp + sr, 1e-9), 3)
    pp, pr_, pf = prf(ph_tp, ph_np, ph_ng)
    # 篇章级召回：模型是否找到≥1个有效RQ（匹配gold或裁判认可）
    papers_with_gold = sum(1 for r in records if r["gold"])
    papers_hit = 0
    for r in records:
        if not r["gold"]:
            continue
        abs_ = r["abstract"]
        hit = any(sent_match(p.get("sentence"), g.get("sentence")) for p in r["pred"] for g in r["gold"])
        if not hit and glm is not None:
            hit = any(judge_rq(glm, abs_, p.get("sentence", "")) for p in r["pred"])
        if hit:
            papers_hit += 1
    paper_recall = round(papers_hit / max(papers_with_gold, 1), 3)
    return {"sent_P": sp, "sent_R": sr, "sent_F1": sf, "paper_recall": paper_recall,
            "phrase_P": pp, "phrase_R": pr_, "phrase_F1": pf,
            "n": len(records), "anti_hallucination": round(n_valid / max(n_pred_total, 1), 3),
            "n_judged_tp": n_judged_tp}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=72)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--no-judge", action="store_true", help="禁用 LLM 裁判（仅 verbatim 匹配）")
    args = ap.parse_args()
    gold = json.load(open(GOLD, encoding="utf-8"))[:args.n]
    svc = SemanticApplicationService(glm_client, rule_loader)
    judge_glm = None if args.no_judge else glm_client

    records = []
    for i, g in enumerate(gold, 1):
        lang = g["lang"]
        req = SemanticRequest(text=g["abstract"], params={"lang": lang})
        t0 = time.time()
        try:
            res = svc.execute("rq_identify", req)
            pred = res.data if res.success else []
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}/{args.n}] ERR: {exc}", flush=True)
            pred = []
        dt = time.time() - t0
        gold_rq = [{"sentence": r["sentence"], "phrase": r.get("phrase", "")} for r in g["rq"]]
        ok = "✓" if any(sent_match(p.get("sentence"), gr.get("sentence")) for p in pred for gr in gold_rq) else ("∅" if not gold_rq else "✗")
        print(f"[{i}/{args.n}] {dt:.0f}s {ok}({lang}) pred={len(pred)} gold={len(gold_rq)} "
              f"ph_pred={sum(1 for p in pred if p.get('phrase'))}", flush=True)
        records.append({"abstract": g["abstract"], "lang": lang, "pred": pred, "gold": gold_rq})

    zh = [r for r in records if r["lang"] == "zh"]
    en = [r for r in records if r["lang"] == "en"]
    summary = {"all": eval_set(records, judge_glm), "zh": eval_set(zh, judge_glm), "en": eval_set(en, judge_glm)}
    print("\n========== 汇总 ==========")
    for k in ["all", "zh", "en"]:
        s = summary[k]
        print(f"  [{k}] 句F1={s['sent_F1']}(P{s['sent_P']}/R{s['sent_R']}) "
              f"篇章召回={s.get('paper_recall','-')} 短语F1={s['phrase_F1']}(P{s['phrase_P']}/R{s['phrase_R']}) "
              f"防幻觉={s['anti_hallucination']} 裁判TP={s.get('n_judged_tp',0)} n={s['n']}")
    out = args.out or str(RUNS_DIR / "rq_eval.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"summary": summary, "records": records}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n明细：{out}")


if __name__ == "__main__":
    main()
