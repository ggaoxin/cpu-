"""kw_zh/kw_en 关键词识别训练 + 5 折交叉验证（中英双语）。

训练（仅用训练集，防过拟合）：网格校准特征权重 + 选 few-shot + 写模型文件（与管线解耦）。
验证（测试集 vs author keywords）：精确 + 部分(子串/Jaccard≥0.6) P/R/F1 + 未命中分析。

用法：
  python -m training.run_keyword_training --lang zh --folds 5
  python -m training.run_keyword_training --lang en --folds 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List
from config.settings import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 语言配置
LANG_CFG = {
    "zh": {
        "papers": str(settings.DATA_DIR / "random_50_chinese_papers.json"),
        "model": PROJECT_ROOT / "rules" / "keyword_recognition" / "kw_zh_model.json",
        "code": "kw_zh",
        "default_weights": {"in_title": 1.0, "freq": 0.6, "position": 0.4, "length": 0.2},
    },
    "en": {
        "papers": str(settings.DATA_DIR / "english_abstracts_keywords_original_preserved.json"),
        "model": PROJECT_ROOT / "rules" / "keyword_recognition" / "kw_en_model.json",
        "code": "kw_en",
        "default_weights": {"freq": 0.6, "position": 0.5, "length": 0.3},  # 英文无 in_title
    },
}

WEIGHT_GRID_ZH = [
    {"in_title": it, "freq": fr, "position": po, "length": le}
    for it in [0.5, 1.0, 2.0] for fr in [0.3, 0.6, 1.0] for po in [0.2, 0.5, 0.8] for le in [0.1, 0.3]
]
WEIGHT_GRID_EN = [
    {"freq": fr, "position": po, "length": le}
    for fr in [0.3, 0.6, 1.0] for po in [0.2, 0.5, 0.8] for le in [0.1, 0.3, 0.6]
]


def get_mine(lang):
    if lang == "en":
        from training.keyword_phrase_miner_en import mine_candidates, score_candidates
        def mine(p):
            return mine_candidates(p.get("en_abstract") or p.get("abstract", ""))
    else:
        from training.keyword_phrase_miner import mine_candidates, score_candidates
        def mine(p):
            return mine_candidates(p.get("ch_name", ""), p.get("ch_abstract", ""))
    return mine, score_candidates


def _abstract(p, lang):
    if lang == "en":
        return p.get("en_abstract") or p.get("abstract", "")
    return (p.get("ch_name", "") + "。" + p.get("ch_abstract", ""))


def gold_of(p, lang):
    """返回 paper 的 author 关键词列表（兼容 字符串列表 / {en_name} / {ch_name}）。"""
    kws = p["keywords"]
    if isinstance(kws, str):
        kws = json.loads(kws)
    if lang == "en":
        return [k.get("en_name", "") if isinstance(k, dict) else k for k in kws
                if (k.get("en_name", "") if isinstance(k, dict) else k)]
    return [k.get("ch_name", "") if isinstance(k, dict) else k for k in kws
            if (k.get("ch_name", "") if isinstance(k, dict) else k)]


def gold_in_candidates(gold: str, cands: List[str]) -> bool:
    gl = gold.lower()
    return any(gl == c.lower() or gl in c.lower() or c.lower() in gl for c in cands)


def recall_at_k(papers, weights, mine, score, k=25):
    hit = tot = 0
    for p in papers:
        cands = score(mine(p), weights)
        top = [c["phrase"] for c in cands[:k]]
        for g in gold_of(p, LANG):
            tot += 1
            if gold_in_candidates(g, top):
                hit += 1
    return hit / max(tot, 1)


def calibrate_weights(train, mine, score):
    grid = WEIGHT_GRID_EN if LANG == "en" else WEIGHT_GRID_ZH
    best, best_r = LANG_CFG[LANG]["default_weights"], -1.0
    for w in grid:
        r = recall_at_k(train, w, mine, score, 25)
        if r > best_r:
            best_r, best = r, w
    return best, best_r


def select_few_shot(train, n=2):
    cand = [p for p in train if 3 <= len(gold_of(p, LANG)) <= 6]
    out = []
    for p in cand[:n]:
        out.append({"abstract": _abstract(p, LANG), "keywords": gold_of(p, LANG)})
    return out


def jaccard(a, b):
    sa, sb = set(a.lower().split()), set(b.lower().split())
    return len(sa & sb) / max(len(sa | sb), 1)


def match(pred_list, gold_list):
    mp, mg = set(), set()
    for i, pr in enumerate(pred_list):
        for j, g in enumerate(gold_list):
            if pr.lower() == g.lower() or pr.lower() in g.lower() or g.lower() in pr.lower() or jaccard(pr, g) >= 0.6:
                mp.add(i); mg.add(j)
    return mp, mg


def prf(mp, mg, n_pred, n_gold):
    p = len(mp) / max(n_pred, 1); r = len(mg) / max(n_gold, 1)
    return round(p, 3), round(r, 3), round(2 * p * r / max(p + r, 1e-9), 3)


def _closest(g, kw):
    best, bs = None, 0
    for k in kw:
        s = 2 * len(set(g.lower().split()) & set(k.lower().split())) / max(len(set(g.lower().split()) | set(k.lower().split())), 1)
        if s > bs:
            bs, best = s, k
    return best


def run_pipeline_on(papers, glm):
    from application.dto.common_dto import SemanticRequest
    from application.service.semantic_service import SemanticApplicationService
    from infrastructure.rule_engine.rule_loader import rule_loader
    svc = SemanticApplicationService(glm, rule_loader)
    code = LANG_CFG[LANG]["code"]
    records = []
    for i, p in enumerate(papers, 1):
        text = _abstract(p, LANG)
        try:
            res = svc.execute(code, SemanticRequest(text=text))
            kw = [k["keyword"] for k in res.data] if res.success else []
        except Exception as e:  # noqa: BLE001
            print(f"  ERR: {e}", flush=True); kw = []
        gold = gold_of(p, LANG)
        mp_idx, mg_idx = match(kw, gold)
        gold_stat = [{"gold": g, "matched": j in mg_idx, "pred_closest": _closest(g, kw)} for j, g in enumerate(gold)]
        records.append({"pred": kw, "gold": gold, "gold_stat": gold_stat})
        print(f"  [{i}/{len(papers)}] pred={kw} gold={gold}", flush=True)
    return records


def evaluate(records):
    pe = re_ = fe = pp = rp = fp = 0
    n = len(records)
    for r in records:
        kw, gold = r["pred"], r["gold"]
        mp = {i for i, k in enumerate(kw) if k.lower() in {g.lower() for g in gold}}
        mg = {j for j, g in enumerate(gold) if g.lower() in {k.lower() for k in kw}}
        p, rv, f = prf(mp, mg, len(kw), len(gold)); pe += p; re_ += rv; fe += f
        mp, mg = match(kw, gold)
        p, rv, f = prf(mp, mg, len(kw), len(gold)); pp += p; rp += rv; fp += f
    return {"exact_P": round(pe/n, 3), "exact_R": round(re_/n, 3), "exact_F1": round(fe/n, 3),
            "partial_P": round(pp/n, 3), "partial_R": round(rp/n, 3), "partial_F1": round(fp/n, 3), "n": n}


def mismatch_analysis(records):
    not_in = []  # 英文无"不在原文"概念（author kw 多在 abstract），统一列未命中
    unmatched = []
    for r in records:
        for gs in r["gold_stat"]:
            if not gs["matched"]:
                unmatched.append({"gold": gs["gold"], "pred_closest": gs["pred_closest"]})
    return unmatched


# 全局语言（由 main 设置）
LANG = "zh"


def main():
    global LANG
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["zh", "en"], default="zh")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--few-shot", type=int, default=2)
    ap.add_argument("--single-fold", action="store_true")
    ap.add_argument("--papers", type=str, default=None, help="覆盖默认数据集路径")
    args = ap.parse_args()
    LANG = args.lang
    cfg = LANG_CFG[LANG]

    from infrastructure.llm.glm_client import glm_client
    papers_file = args.papers or cfg["papers"]
    papers = json.load(open(papers_file, encoding="utf-8"))
    n = len(papers); folds = args.folds; fold_size = n // folds
    mine, score = get_mine(LANG)

    results = []
    fold_ids = [0] if args.single_fold else range(folds)
    for fi in fold_ids:
        test_idx = list(range(fi * fold_size, (fi + 1) * fold_size))
        train_idx = [i for i in range(n) if i not in test_idx]
        train = [papers[i] for i in train_idx]; test = [papers[i] for i in test_idx]
        print(f"\n===== [{LANG}] Fold {fi+1}/{folds}  train={len(train)} test={len(test)} =====", flush=True)
        w, r_train = calibrate_weights(train, mine, score)
        fs = select_few_shot(train, args.few_shot)
        print(f"  校准权重={w} 召回@25={r_train:.3f} few_shot={len(fs)}", flush=True)
        json.dump({"feature_weights": w, "few_shot": fs, "domain_terms": []},
                  open(cfg["model"], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        records = run_pipeline_on(test, glm_client)
        m = evaluate(records); m["fold"] = fi + 1; m["weights"] = w
        results.append(m)
        print(f"  Fold{fi+1}: {m}", flush=True)
        um = mismatch_analysis(records)
        print(f"  未命中 gold({len(um)}): " + "; ".join(f"{u['gold']}~{u['pred_closest']}" for u in um[:10]), flush=True)

    print("\n========== 汇总 ==========")
    agg = {}
    for k in ["exact_P", "exact_R", "exact_F1", "partial_P", "partial_R", "partial_F1"]:
        agg[k] = round(sum(r[k] for r in results) / len(results), 3)
    agg["folds"] = len(results); agg["lang"] = LANG
    for k, v in agg.items():
        print(f"  {k}: {v}")
    out = PROJECT_ROOT / "training" / "runs" / f"kw_{LANG}_{folds}fold.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"summary": agg, "folds": results}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n明细：{out}")


if __name__ == "__main__":
    main()
