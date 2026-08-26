"""NER 评测 + 错误驱动实体映射表更新。

机制（用户定）：
- 对每篇文档：LLM 抽实体（pred），对照 Claude gold（带变体分组）。
- 对每个 gold 实体 G：
    llm_hit = pred 里有 G 的任一变体且类型对 → LLM 识别对
    entry   = 映射表里是否已有 G（canonical 或任一变体命中）
    若 entry 无 且 LLM 漏/错（not llm_hit）→ 新建表条目（存 correct G + variants）  ← 错误驱动入库
    若 entry 有 → 追加 G 的新变体（去重）；LLM 漏/错则 fail_count++              ← 变体积累
- 指标：entity-level P/R/F1；记录 FP（pred 多余）/FN（gold 漏）。
- 映射表原地更新（追加新条目/新变体）。

用法：
  python -m training.eval_ner --type ner_general
  python -m training.eval_ner --type ner_research --no-update-table   # 只评测不写表
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from application.dto.common_dto import SemanticRequest  # noqa: E402
from application.service.semantic_service import SemanticApplicationService  # noqa: E402
from infrastructure.llm.glm_client import glm_client  # noqa: E402
from infrastructure.rule_engine.rule_loader import rule_loader  # noqa: E402

GOLD_DIR = PROJECT / "data" / "ner"
MAP_DIR = PROJECT / "rules" / "ner" / "mappings"
RUNS_DIR = PROJECT / "training" / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# NER 功能点 → API code
TYPE_TO_CODE = {
    "ner_general": "ner_general",
    "ner_research": "ner_research",
    "ner_domain": "ner_domain",
    "ner_relation": "ner_relation",
}


def _norm(s: str) -> str:
    """归一化：去空格、小写，便于跨表达匹配（中文/英文/缩写）。"""
    return "".join((s or "").split()).lower()


def prf(tp, n_pred, n_gold):
    p = tp / max(n_pred, 1)
    r = tp / max(n_gold, 1)
    return round(p, 3), round(r, 3), round(2 * p * r / max(p + r, 1e-9), 3)


# ======================== ner_relation：关系级评测（无表） ======================== #
def _ent_variant_map(entities: list) -> dict:
    """canonical -> 归一化变体集合（含 canonical）。"""
    m = {}
    for e in entities:
        vs = {_norm(v) for v in e.get("variants", []) if v} | {_norm(e.get("canonical", ""))}
        vs.discard("")
        m[e["canonical"]] = vs
    return m


def _match_ent(text: str, canon: str, ent_map: dict) -> bool:
    """text 是否匹配 canon 实体（归一化后相等或包含，容错中英文/缩写）。"""
    pt = _norm(text)
    if len(pt) < 2:
        return False
    return any(v and (pt == v or pt in v or v in pt) for v in ent_map.get(canon, []))


def _match_rel(pred_rel: dict, gold_rel: dict, ent_map: dict) -> bool:
    """pred 关系是否匹配 gold：relation 归一化包含 + head/tail 变体容错。"""
    r = _norm(pred_rel.get("relation", ""))
    gr = _norm(gold_rel.get("relation", ""))
    if not (r and gr and (r == gr or gr in r or r in gr)):
        return False
    return (_match_ent(pred_rel.get("head", ""), gold_rel["head"], ent_map)
            and _match_ent(pred_rel.get("tail", ""), gold_rel["tail"], ent_map))


_rel_judge_cache = {}


def _edge_text(rel: dict) -> str:
    """边的文本表示（head relation tail），用于语义相似度。"""
    return f"{rel.get('head', '')} {rel.get('relation', '')} {rel.get('tail', '')}".strip()


def _embed_edges(rels: list):
    """批量嵌入边文本，返回 (N, dim) 归一化向量；空或编码器不可用则 None。"""
    texts = [_edge_text(r) for r in rels if r.get("relation")]
    if not texts:
        return None
    try:
        from infrastructure.rag.m3_encoder import m3_encoder  # noqa: PLC0415
        return m3_encoder.encode(texts)
    except Exception:  # noqa: BLE001
        return None


def judge_relation(glm, ph, pr, pt, gh, gr, gt) -> bool:
    """LLM 裁判 pred 关系与 gold 关系是否语义相同（容错同义关系名，如 属于≈任职于、赋能≈应用于）。

    泛化判定，不枚举同义词；缓存避免重复调用。
    """
    key = (_norm(ph), _norm(pr), _norm(pt), _norm(gr))
    if key in _rel_judge_cache:
        return _rel_judge_cache[key]
    sysp = ("你是关系语义判定裁判。判断两个关系三元组是否表达同一语义关系"
            "（头尾实体指代相同、关系语义一致，允许关系名是同义/近义表达如 属于≈任职于、赋能≈应用于）。"
            "只回答JSON：{\"same\":true/false}")
    usr = (f"关系1：{ph} --{pr}--> {pt}\n关系2：{gh} --{gr}--> {gt}\n两者是否为同一语义关系？")
    try:
        d = glm.chat_json(sysp, usr, timeout=60.0, max_tokens=50)
        d = d.get("data", d) if isinstance(d, dict) else d
        same = bool(d.get("same")) if isinstance(d, dict) else False
    except Exception:  # noqa: BLE001
        same = False
    _rel_judge_cache[key] = same
    return same


def _rel_head_tail_match(pred_rel: dict, gold_rel: dict, ent_map: dict) -> bool:
    """head/tail 实体匹配（不论关系名），用于筛语义相似候选。"""
    return (_match_ent(pred_rel.get("head", ""), gold_rel["head"], ent_map)
            and _match_ent(pred_rel.get("tail", ""), gold_rel["tail"], ent_map))


def expand_variants_llm(glm, canonical: str, etype: str, observed: list) -> list:
    """LLM 主动补全实体的中/英/缩写变体（标记为 generated，区别于 observed 实测）。

    实体入库时调用：不等到文档里出现该变体，LLM 直接列出常见其他表达。
    存入 llm_variants 字段（待验证），与 variants（实测可信）分开。
    """
    sysp = ("你是实体别名扩展专家。给定一个命名实体及其已观察到的表达，列出它在真实世界中"
            "常见的其他表达方式（中文名、英文名、缩写）。只返回确实通用存在的表达，"
            "不要臆造；不确定就少给或空。只输出JSON：{\"variants\":[\"...\",\"...\"]}")
    usr = (f"实体：{canonical}\n类型：{etype}\n已观察到：{observed}\n"
           f"请列出该实体其他常见表达（中文/英文/缩写），勿重复已观察到的：")
    try:
        d = glm.chat_json(sysp, usr, timeout=60.0, max_tokens=200, temperature=0.0)
        d = d.get("data", d) if isinstance(d, dict) else d
        vs = d.get("variants", []) if isinstance(d, dict) else []
        obs_norm = {_norm(v) for v in observed} | {_norm(canonical)}
        return [v.strip() for v in vs
                if v and v.strip() and _norm(v.strip()) not in obs_norm]
    except Exception:  # noqa: BLE001
        return []


def llm_hits(gold_ent: dict, preds: list) -> bool:
    """LLM 是否识别对了 gold 实体 G：pred 里有 G 的任一变体（归一化后相等或包含）且类型对。"""
    g_type = gold_ent.get("type", "")
    g_vars = {_norm(v) for v in gold_ent.get("variants", []) if v}
    g_vars.add(_norm(gold_ent.get("canonical", "")))
    g_vars.discard("")
    for p in preds:
        if p.get("type", "") != g_type:
            continue
        pt = _norm(p.get("text", ""))
        if len(pt) < 2:
            continue
        for v in g_vars:
            if v and (pt == v or pt in v or v in pt):
                return True
    return False


def find_entry(gold_ent: dict, table: list):
    """在映射表里找 gold 实体 G 对应的条目：canonical 或任一变体双向命中。"""
    g_vars = {_norm(v) for v in gold_ent.get("variants", []) if v}
    g_vars.add(_norm(gold_ent.get("canonical", "")))
    g_vars.discard("")
    for e in table:
        e_vars = {_norm(v) for v in e.get("variants", []) if v} | \
                 {_norm(v) for v in e.get("llm_variants", []) if v}
        e_vars.add(_norm(e.get("canonical", "")))
        e_vars.discard("")
        if g_vars & e_vars:
            return e
    return None


def load_table(t: str) -> list:
    p = MAP_DIR / f"{t}_mapping.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_table(t: str, table: list):
    p = MAP_DIR / f"{t}_mapping.json"
    p.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")


def eval_relations(t: str, code: str, gold_docs: list, svc, args):
    """ner_relation 评测：关系级 P/R/F1 + 漏例记录（无映射表）。

    关系是开放语义断言，不建表；漏例用于分析 LLM 在哪类关系（尤其含蓄表达）上失败 → 补泛化规则。
    """
    tp = fp = fn = 0
    records = []
    for gi, gdoc in enumerate(gold_docs, 1):
        doc_id = gdoc["doc_id"]
        gold_ents = gdoc["entities"]
        gold_rels = gdoc["relations"]
        ent_map = _ent_variant_map(gold_ents)
        text = _load_doc_text(doc_id)
        if not text:
            print(f"[{gi}] {doc_id} 无原文，跳过", flush=True)
            continue
        req = SemanticRequest(text=text)
        t0 = time.time()
        try:
            res = svc.execute(code, req)
        except Exception as exc:  # noqa: BLE001
            print(f"[{gi}] {doc_id} 异常: {exc}", flush=True)
            continue
        dt = time.time() - t0
        if not res.success:
            print(f"[{gi}] {doc_id} 失败: {res.error[:120]}", flush=True)
            continue
        data = res.data if isinstance(res.data, dict) else {}
        pred_rels = data.get("relations", []) if isinstance(data, dict) else []
        # 批量嵌入边向量（用于同义关系名的语义相似度匹配）
        pred_vecs = _embed_edges(pred_rels) if not args.no_sim else None
        gold_vecs = _embed_edges(gold_rels) if not args.no_sim else None

        doc_tp, doc_fn, doc_fp = [], [], []
        for gi, gr in enumerate(gold_rels):
            # ① 精确匹配（关系名子串 + 实体变体）
            hit = any(_match_rel(pr, gr, ent_map) for pr in pred_rels)
            # ② 精确未中 → head/tail 匹配的候选算边语义相似度（同义关系名容错）
            if not hit and gold_vecs is not None and pred_vecs is not None:
                gvec = gold_vecs[gi]
                for pi, pr in enumerate(pred_rels):
                    if _rel_head_tail_match(pr, gr, ent_map):
                        cos = float(np.dot(gvec, pred_vecs[pi]))  # 均已 L2 归一化
                        if cos >= args.threshold:
                            hit = True
                            break
            if hit:
                tp += 1
                doc_tp.append(gr)
            else:
                fn += 1
                doc_fn.append(gr)
        for pi, pr in enumerate(pred_rels):
            # FP：pred 不匹配任何 gold（精确或相似度）
            is_fp = True
            for gi, gr in enumerate(gold_rels):
                if _match_rel(pr, gr, ent_map):
                    is_fp = False
                    break
                if (gold_vecs is not None and pred_vecs is not None
                        and _rel_head_tail_match(pr, gr, ent_map)
                        and float(np.dot(gold_vecs[gi], pred_vecs[pi])) >= args.threshold):
                    is_fp = False
                    break
            if is_fp:
                fp += 1
                doc_fp.append(pr)

        records.append({
            "doc_id": doc_id, "n_pred_rel": len(pred_rels), "n_gold_rel": len(gold_rels),
            "tp": len(doc_tp), "fp": len(doc_fp), "fn": len(doc_fn), "dt_s": round(dt, 1),
            "missed": [{"head": r["head"], "relation": r["relation"], "tail": r["tail"],
                        "context": r.get("context", "")} for r in doc_fn],
            "extra": [{"head": p.get("head", ""), "relation": p.get("relation", ""),
                       "tail": p.get("tail", "")} for p in doc_fp],
            "pred_relations": [{"head": p.get("head", ""), "relation": p.get("relation", ""),
                                "tail": p.get("tail", "")} for p in pred_rels],
            "gold_relations": gold_rels,
        })
        print(f"[{gi}/{len(gold_docs)}] {doc_id} {dt:.1f}s pred_rel={len(pred_rels)} "
              f"gold_rel={len(gold_rels)} tp={len(doc_tp)} fp={len(doc_fp)} fn={len(doc_fn)}", flush=True)

    p, r, f = prf(tp, tp + fp, tp + fn)
    summary = {"type": t, "n_docs": len(records),
               "relation_precision": p, "relation_recall": r, "relation_f1": f,
               "tp": tp, "fp": fp, "fn": fn}
    print("\n========== 汇总 ==========")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    out = args.out or str(RUNS_DIR / f"ner_{t}_eval.json")
    json.dump({"summary": summary, "records": records},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"评测详情 → {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", required=True, choices=list(TYPE_TO_CODE.keys()))
    ap.add_argument("--no-update-table", action="store_true", help="只评测不写映射表")
    ap.add_argument("--no-llm-expand", action="store_true", help="禁用 LLM 主动变体扩展")
    ap.add_argument("--no-sim", action="store_true", help="ner_relation: 禁用边语义相似度匹配（仅精确匹配）")
    ap.add_argument("--threshold", type=float, default=0.75, help="ner_relation 边语义相似度阈值")
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    t = args.type
    code = TYPE_TO_CODE[t]
    gold_path = GOLD_DIR / f"{t}_gold.json"
    if not gold_path.exists():
        print(f"[{t}] gold 文件不存在（{gold_path}），先标注 gold：")
        print(f"  python -m scripts.author_ner_standard --type {t}")
        return
    gold_docs = json.loads(gold_path.read_text(encoding="utf-8"))
    if not gold_docs:
        print(f"[{t}] gold 为空，先在 scripts/author_ner_standard.py 标注后重跑")
        return

    # ner_relation：关系级评测，不建映射表（关系是开放语义断言，非有限字典）
    if t == "ner_relation":
        svc = SemanticApplicationService(glm_client, rule_loader)
        eval_relations(t, code, gold_docs, svc, args)
        return

    table = load_table(t)
    n_table_before = len(table)
    svc = SemanticApplicationService(glm_client, rule_loader)

    tp = fp = fn = 0
    records = []
    new_entries = []
    variant_added = []

    for gi, gdoc in enumerate(gold_docs, 1):
        doc_id = gdoc["doc_id"]
        gold_ents = gdoc["entities"]
        # 取原文：从 author_ner_standard 的 DOCS 读，或 gold 里没存原文则用 doc_id 兜底
        text = _load_doc_text(doc_id)
        if not text:
            print(f"[{gi}/{len(gold_docs)}] {doc_id}: 无原文，跳过", flush=True)
            continue
        params = {}
        if t == "ner_domain":
            params["domain"] = gdoc.get("domain", "医学")
        req = SemanticRequest(text=text, params=params)
        t0 = time.time()
        try:
            res = svc.execute(code, req)
        except Exception as exc:  # noqa: BLE001
            print(f"[{gi}] {doc_id} 执行异常: {exc}", flush=True)
            continue
        dt = time.time() - t0
        if not res.success:
            print(f"[{gi}] {doc_id} 失败: {res.error[:120]}", flush=True)
            continue
        preds = res.data if isinstance(res.data, list) else []

        # 逐 gold 实体对照
        doc_fp, doc_fn, doc_tp = [], [], []
        for g in gold_ents:
            hit = llm_hits(g, preds)
            entry = find_entry(g, table)
            if hit:
                tp += 1
                doc_tp.append(g["canonical"])
            else:
                fn += 1
                doc_fn.append({"canonical": g["canonical"], "type": g.get("type", ""),
                               "variants": g["variants"]})
            # —— 映射表更新 —— #
            if entry is None:
                if not hit:
                    # 错误驱动入库：LLM 漏/错的正确实体存入表
                    llm_vars = []
                    if not args.no_llm_expand:
                        llm_vars = expand_variants_llm(
                            glm_client, g["canonical"], g.get("type", ""), g["variants"])
                    ne = {
                        "canonical": g["canonical"],
                        "type": g.get("type", ""),
                        "variants": list(g["variants"]),       # observed（实测可信）
                        "llm_variants": llm_vars,               # LLM 生成（待验证）
                        "n_docs": 1, "source_docs": [doc_id],
                        "llm_fail_count": 1, "first_seen": doc_id,
                    }
                    table.append(ne)
                    new_entries.append(ne)
            else:
                # 已入库 → 追加新变体（去重）；LLM 漏/错则 fail_count++
                for v in g["variants"]:
                    if _norm(v) not in {_norm(x) for x in entry["variants"]} and v:
                        entry["variants"].append(v)
                        variant_added.append({"canonical": entry["canonical"], "new_variant": v, "doc": doc_id})
                if doc_id not in entry.get("source_docs", []):
                    entry.setdefault("source_docs", []).append(doc_id)
                    entry["n_docs"] = entry.get("n_docs", 0) + 1
                if not hit:
                    entry["llm_fail_count"] = entry.get("llm_fail_count", 0) + 1

        # FP：pred 不匹配任何 gold
        for p in preds:
            pt = _norm(p.get("text", ""))
            if len(pt) < 2:
                continue
            matched = False
            for g in gold_ents:
                if p.get("type", "") != g.get("type", ""):
                    continue
                g_vars = {_norm(v) for v in g.get("variants", [])} | {_norm(g.get("canonical", ""))}
                if any(pt == v or pt in v or v in pt for v in g_vars if v):
                    matched = True
                    break
            if not matched:
                fp += 1
                doc_fp.append({"text": p.get("text", ""), "type": p.get("type", "")})

        records.append({
            "doc_id": doc_id, "n_pred": len(preds), "n_gold": len(gold_ents),
            "tp": len(doc_tp), "fp": len(doc_fp), "fn": len(doc_fn),
            "dt_s": round(dt, 1),
            "missed_or_wrong": doc_fn, "extra": doc_fp,
        })
        print(f"[{gi}/{len(gold_docs)}] {doc_id} {dt:.1f}s pred={len(preds)} gold={len(gold_ents)} "
              f"tp={len(doc_tp)} fp={len(doc_fp)} fn={len(doc_fn)}", flush=True)

    n_pred = tp + fp
    n_gold = tp + fn
    p, r, f = prf(tp, n_pred, n_gold)
    summary = {
        "type": t, "n_docs": len(records),
        "entity_precision": p, "entity_recall": r, "entity_f1": f,
        "tp": tp, "fp": fp, "fn": fn,
        "table_before": n_table_before, "table_after": len(table),
        "new_entries": len(new_entries), "variant_added": len(variant_added),
    }
    print("\n========== 汇总 ==========")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    if not args.no_update_table:
        save_table(t, table)
        print(f"映射表已更新：{MAP_DIR / (t + '_mapping.json')}")

    out = args.out or str(RUNS_DIR / f"ner_{t}_eval.json")
    json.dump({"summary": summary, "records": records,
               "new_entries": new_entries, "variant_added": variant_added},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"评测详情 → {out}")


def _load_doc_text(doc_id: str) -> str:
    """从 author_ner_standard 的 DOCS 读原文（与 gold 同源）。"""
    import re as _re
    try:
        from scripts.author_ner_standard import DOCS, _clean
        if doc_id in DOCS:
            return _clean(DOCS[doc_id].read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return ""


if __name__ == "__main__":
    main()
