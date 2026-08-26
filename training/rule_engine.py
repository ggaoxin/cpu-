"""后置规则引擎（运行时 + 训练共用，确定性、零 GLM 调用）。

LLM 输出 5 段划分后，本引擎做：
1. 确定性校验：标签合法、原文逐字未改、无遗漏/重复句子、语步顺序异常
2. 逐句 pattern 规则匹配 → 收集证据 → 对 5 语步分数做有限调整（受等级上限约束）
3. 冲突检测：规则建议 ≠ LLM 判定 且超过阈值 → 标记待二次审核

设计原则（rule.pdf 第11/15条）：
- 规则不直接覆盖 LLM，只调分数或触发复核
- 改标签需 ≥2 个独立证据维度共识
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from training.profile import get_profile
from training.rule_lib import Rule, RuleLib

# LLM 判定的基础分（代表 LLM 的选择，规则在其上做有限调整）
LLM_BASE_SCORE = 0.70
# 冲突触发：非 LLM 标签的备选 move 获得共识支持且加分超过此值 → 触发二次审核
# （规则不与 LLM 比拼绝对分数高低，而是看是否有共识证据反对 LLM 判定）
CONFLICT_MIN_SUPPORT = 0.12
# 共识要求：至少 N 个独立证据维度支持才视为强建议
CONSENSUS_MIN_DIMS = 2


def match_condition(cond: Dict[str, Any], sentence: str, feats: Dict[str, str],
                    ctx: Dict[str, Any]) -> bool:
    """判定单个条件是否满足。"""
    kind = cond.get("kind", "")
    if kind == "keyword":
        if "any_of" in cond:
            return any(w in sentence for w in (cond["any_of"] or []))
        if "all_of" in cond:
            return all(w in sentence for w in (cond["all_of"] or []))
        return False
    if kind == "regex":
        return re.search(cond.get("pattern", ""), sentence) is not None
    if kind == "feature":
        dim = cond.get("dim", "")
        val = feats.get(dim, "unknown")
        if "in" in cond:
            return val in (cond["in"] or [])
        if "not_in" in cond:
            return val not in (cond["not_in"] or [])
        return False
    if kind == "position":
        if "after_move" in cond:
            return ctx["seen_moves"].get(cond["after_move"], False)
        if "before_move" in cond:
            return not ctx["seen_moves"].get(cond["before_move"], False)
        if "rel_min" in cond or "rel_max" in cond:
            rel = ctx["rel_pos"]
            lo = cond.get("rel_min", 0.0)
            hi = cond.get("rel_max", 1.0)
            return lo <= rel <= hi
        return False
    return False


def rule_fires(rule: Rule, sentence: str, feats: Dict[str, str], ctx: Dict[str, Any]) -> bool:
    """规则命中：所有必要条件满足 且 无排除条件命中。"""
    if not all(match_condition(c, sentence, feats, ctx) for c in rule.necessary_conditions):
        return False
    if any(match_condition(c, sentence, feats, ctx) for c in rule.exclusion_conditions):
        return False
    return True


def matched_sources(rule: Rule, sentence: str, feats: Dict[str, str], ctx: Dict[str, Any]) -> set:
    """返回该规则命中的必要条件所提供的"证据来源"集合。

    用于共识判定（rule.pdf 第15条：改标签需≥2独立证据维度）：
    - feature 条件贡献其 dim（如 research_actor）
    - keyword/regex/position 条件贡献其 kind
    不同来源视为独立证据维度。
    """
    sources: set = set()
    for c in rule.necessary_conditions:
        if not match_condition(c, sentence, feats, ctx):
            continue
        if c.get("kind") == "feature":
            sources.add(c.get("dim", "feature"))
        else:
            sources.add(c.get("kind", ""))
    return sources


def _deterministic_checks(abstract: str, sentences: List[str], spans: Dict[str, str]) -> List[str]:
    """确定性校验，返回发现的问题清单（可自动修正的在此处修正并记录）。"""
    p = get_profile()
    moves = p.moves
    issues: List[str] = []
    # 1. 标签合法
    bad = [k for k in spans if k not in moves]
    if bad:
        issues.append(f"非法语步键: {bad}")
    # 2. 原文逐字未改（span 应为 abstract 子串，忽略空白）
    abs_norm = re.sub(r"\s+", "", abstract)
    for m, sp in spans.items():
        if sp and re.sub(r"\s+", "", sp) not in abs_norm:
            issues.append(f"{m} 段非原文逐字摘录（可能被改写）")
    # 3. 遗漏句子：所有句应被某段覆盖
    covered = [False] * len(sentences)
    for i, s in enumerate(sentences):
        s_norm = s.strip()
        for sp in spans.values():
            if sp and s_norm and s_norm in sp:
                covered[i] = True
                break
    missing = [sentences[i] for i, c in enumerate(covered) if not c]
    if missing:
        issues.append(f"遗漏句子({len(missing)}句): {missing[:2]}")
    # 4. 重复句子：一句出现在多段
    for i, s in enumerate(sentences):
        s_norm = s.strip()
        cnt = sum(1 for sp in spans.values() if sp and s_norm and s_norm in sp)
        if cnt > 1:
            issues.append(f"句子重复出现在多段: {s_norm[:20]}")
    # 5. 语步顺序：结论不应在结果之前出现（moves[-1]=结论, moves[-2]=结果）
    order_idx: Dict[str, int] = {}
    for i, s in enumerate(sentences):
        s_norm = s.strip()
        for m, sp in spans.items():
            if sp and s_norm and s_norm in sp and m not in order_idx:
                order_idx[m] = i
    conc, res = moves[-1], moves[-2]
    if conc in order_idx and res in order_idx and order_idx[conc] < order_idx[res]:
        issues.append(f"语步顺序异常：{conc}出现在{res}之前")
    return issues


def verify_and_adjust(
    abstract: str,
    llm_output: Dict[str, str],
    rule_lib: RuleLib,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """主入口：校验 + 调分 + 冲突检测。

    返回:
      final_spans: 确定性修正后的 spans（不含规则覆盖；规则覆盖经冲突审核后由调用方回填）
      sentences: 逐句分析 [{text, llm_label, rule_suggestion, scores, evidence, conflict, consensus, adjustments}]
      conflicts: 待二次审核的句子索引列表
      deterministic_issues: 确定性校验发现的问题
    """
    p = get_profile()
    moves = p.moves
    spans = {m: (llm_output.get(m) or "") for m in moves}
    sentences = p.seg.segment(abstract)
    n = len(sentences)
    llm_labels = p.seg.assign_sentences_to_spans(sentences, spans)
    feats_list = p.features.extract_for_sentences(sentences)
    rules = rule_lib.engine_rules(domain)

    seen_moves: Dict[str, bool] = {}
    sent_analysis: List[Dict[str, Any]] = []
    conflicts: List[int] = []

    for i, (sent, feats, llm_lab) in enumerate(zip(sentences, feats_list, llm_labels)):
        rel_pos = (i / n) if n else 0.0
        ctx = {"seen_moves": seen_moves, "rel_pos": rel_pos, "idx": i, "n": n}

        # 初始分数：LLM 判定给基础分
        scores: Dict[str, float] = {m: 0.0 for m in moves}
        if llm_lab in scores:
            scores[llm_lab] = LLM_BASE_SCORE

        evidence: List[Dict[str, Any]] = []
        support_sources: Dict[str, set] = {m: set() for m in moves}
        penalize_sources: Dict[str, set] = {m: set() for m in moves}
        adjustments: List[Dict[str, Any]] = []

        for rule in rules:
            if not rule_fires(rule, sent, feats, ctx):
                continue
            tm = rule.target_move
            w = rule.effective_weight
            src = matched_sources(rule, sent, feats, ctx)
            if rule.action == "+score" and tm in scores:
                scores[tm] += w
                support_sources[tm].update(src)
                adjustments.append({"rule": rule.id, "action": "+score", "move": tm, "delta": round(w, 3)})
            elif rule.action == "-score" and tm in scores:
                scores[tm] -= w
                penalize_sources[tm].update(src)
                adjustments.append({"rule": rule.id, "action": "-score", "move": tm, "delta": round(-w, 3)})
            elif rule.action == "review":
                adjustments.append({"rule": rule.id, "action": "review", "move": tm})
            evidence.append({"rule": rule.id, "target": tm, "sources": sorted(src),
                             "level": rule.level, "description": rule.description})

        rule_suggestion = max(scores, key=scores.get)
        rule_score = scores[rule_suggestion]
        # 备选 move = 除 LLM 标签外得分最高的 move
        alt_candidates = {m: v for m, v in scores.items() if m != llm_lab}
        alt_move = max(alt_candidates, key=alt_candidates.get) if alt_candidates else rule_suggestion
        alt_support = alt_candidates.get(alt_move, 0.0)
        alt_consensus = len(support_sources.get(alt_move, set())) >= CONSENSUS_MIN_DIMS
        # 规则对 LLM 标签的净惩罚（-score 之和）及其共识
        llm_penalty = sum(-a["delta"] for a in adjustments
                          if a.get("action") == "-score" and a.get("move") == llm_lab)
        llm_pen_consensus = len(penalize_sources.get(llm_lab, set())) >= CONSENSUS_MIN_DIMS
        # 冲突 = 有共识证据支持别的 move，或共识证据惩罚 LLM 的 move
        conflict = (alt_consensus and alt_move != llm_lab and alt_support >= CONFLICT_MIN_SUPPORT) \
            or (llm_pen_consensus and llm_penalty >= CONFLICT_MIN_SUPPORT)
        consensus = alt_consensus or llm_pen_consensus
        # 冲突时，规则建议指向共识支持的备选 move（供二次审核参考）
        if conflict:
            rule_suggestion = alt_move

        sent_analysis.append({
            "text": sent,
            "llm_label": llm_lab,
            "rule_suggestion": rule_suggestion,
            "scores": {m: round(v, 3) for m, v in scores.items()},
            "evidence": evidence,
            "adjustments": adjustments,
            "consensus": consensus,
            "conflict": conflict,
        })
        if conflict:
            conflicts.append(i)

        if llm_lab:
            seen_moves[llm_lab] = True

    issues = _deterministic_checks(abstract, sentences, spans)

    return {
        "final_spans": spans,            # 确定性修正后（暂未做规则覆盖）
        "sentences": sent_analysis,
        "conflicts": conflicts,
        "deterministic_issues": issues,
    }


def reassemble_spans(abstract: str, sentence_labels: List[str]) -> Dict[str, str]:
    """按逐句标签重新拼装 spans（冲突审核回填后用）。保持句子原序。"""
    p = get_profile()
    sentences = p.seg.segment(abstract)
    buckets: Dict[str, List[str]] = {m: [] for m in p.moves}
    for s, lab in zip(sentences, sentence_labels):
        if lab in buckets:
            buckets[lab].append(s)
    return {m: "".join(buckets[m]) for m in p.moves}


if __name__ == "__main__":
    from pathlib import Path
    lib = RuleLib.load(Path("rules/move_recognition/mr_zh_abstract.yaml"))
    abstract = ("已有研究表明，图神经网络能够处理非欧氏数据。"
                "针对泛化能力不足的问题，本文提出一种多尺度网络。"
                "实验结果显示，该模型使F1值提高了3.2%。"
                "据此，本文建议在更多任务中验证该方法。")
    llm_out = {"研究背景": "已有研究表明，图神经网络能够处理非欧氏数据。",
               "研究目的": "针对泛化能力不足的问题，",
               "研究方法": "本文提出一种多尺度网络。",
               "研究结果": "实验结果显示，该模型使F1值提高了3.2%。",
               "研究结论": "据此，本文建议在更多任务中验证该方法。"}
    res = verify_and_adjust(abstract, llm_out, lib)
    print("确定性问题:", res["deterministic_issues"])
    print("冲突句:", res["conflicts"])
    for sa in res["sentences"]:
        flag = " ⚠冲突" if sa["conflict"] else ""
        print(f"  [{sa['llm_label']}→{sa['rule_suggestion']}{flag}] {sa['text'][:30]}")
        if sa["adjustments"]:
            print("      调整:", sa["adjustments"])
