"""引用句后置规则引擎：校验 + 调分 + 冲突检测。

复用 rule_engine.py 的核心匹配逻辑（match_condition/rule_fires/effective_weight），
适配引用句场景（句子级别打标签，不需要分句/特征/位置）。

和 verify_and_adjust 的区别：
- 输入：引用句列表 + LLM标签（不是span划分）
- 不需要分句器/特征提取器/确定性校验（引用句已抽取好）
- 输出：调分后标签 + 冲突列表（供conflict_review二次审核）
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from training.rule_lib import RuleLib, Rule
from training.citation_profile import get_citation_profile

# 和 rule_engine.py 一致的常量
LLM_BASE_SCORE = 0.70
CONFLICT_MIN_SUPPORT = 0.12
CONSENSUS_MIN_DIMS = 1  # 引用句规则维度少（只有keyword/regex），共识门槛降为1


def match_condition(cond: Dict[str, Any], sentence: str) -> bool:
    """判定单个条件是否满足（简化版，不需要feats/ctx）。"""
    kind = cond.get("kind", "")
    if kind == "keyword":
        if "any_of" in cond:
            return any(re.search(w, sentence) for w in (cond["any_of"] or []))
        if "all_of" in cond:
            return all(w in sentence for w in (cond["all_of"] or []))
        return False
    if kind == "regex":
        return re.search(cond.get("pattern", ""), sentence) is not None
    return False


def rule_fires(rule: Rule, sentence: str) -> bool:
    """规则命中：所有必要条件满足且无排除条件命中。"""
    if not all(match_condition(c, sentence) for c in rule.necessary_conditions):
        return False
    if any(match_condition(c, sentence) for c in rule.exclusion_conditions):
        return False
    return True


def matched_sources(rule: Rule, sentence: str) -> set:
    """返回命中的必要条件的证据来源集合。"""
    sources = set()
    for c in rule.necessary_conditions:
        if match_condition(c, sentence):
            sources.add(c.get("kind", "unknown"))
    return sources


def verify_and_adjust_citations(
    citations: List[Dict[str, Any]],
    rule_lib: RuleLib,
) -> Dict[str, Any]:
    """引用句后置规则引擎：校验 + 调分 + 冲突检测。

    Args:
        citations: [{sentence, sentiment/intent, confidence, ...}] LLM标注后的引用句
        rule_lib: RuleLib（从yaml加载，含pattern_rules）
    Returns:
        {
            "adjusted": [{...同输入, label可能被调分, confidence更新, evidence, adjustments}],
            "conflicts": [待二次审核的索引],
        }
    """
    p = get_citation_profile()
    labels = p.labels
    label_field = p.label_field
    rules = rule_lib.pattern_rules

    adjusted = []
    conflicts = []

    for idx, item in enumerate(citations):
        sent = item.get("sentence", "")
        llm_label = item.get(label_field, "")
        llm_conf = float(item.get("confidence", 0.5) or 0.5)

        # 初始分数：LLM判定给基础分
        scores: Dict[str, float] = {m: 0.0 for m in labels}
        if llm_label in scores:
            scores[llm_label] = LLM_BASE_SCORE * llm_conf

        evidence = []
        support_sources: Dict[str, set] = {m: set() for m in labels}
        penalize_sources: Dict[str, set] = {m: set() for m in labels}
        adjustments = []

        for rule in rules:
            if not rule_fires(rule, sent):
                continue
            tm = rule.target_move
            if tm not in scores:
                continue
            w = rule.effective_weight
            src = matched_sources(rule, sent)
            if rule.action == "+score":
                scores[tm] += w
                support_sources[tm].update(src)
                adjustments.append({"rule": rule.id, "action": "+score", "label": tm, "delta": round(w, 3)})
            elif rule.action == "-score":
                scores[tm] -= w
                penalize_sources[tm].update(src)
                adjustments.append({"rule": rule.id, "action": "-score", "label": tm, "delta": round(-w, 3)})
            elif rule.action == "review":
                adjustments.append({"rule": rule.id, "action": "review", "label": tm})
            evidence.append({"rule": rule.id, "target": tm, "sources": sorted(src),
                             "level": rule.level, "description": rule.description})

        # 规则建议 = 最高分标签
        rule_suggestion = max(scores, key=scores.get)
        rule_score = scores[rule_suggestion]

        # 备选标签 = 除LLM标签外最高分
        alt_candidates = {m: v for m, v in scores.items() if m != llm_label}
        alt_move = max(alt_candidates, key=alt_candidates.get) if alt_candidates else rule_suggestion
        alt_support = alt_candidates.get(alt_move, 0.0)
        alt_consensus = len(support_sources.get(alt_move, set())) >= CONSENSUS_MIN_DIMS

        # LLM标签的净惩罚
        llm_penalty = sum(-a["delta"] for a in adjustments
                          if a.get("action") == "-score" and a.get("label") == llm_label)
        llm_pen_consensus = len(penalize_sources.get(llm_label, set())) >= CONSENSUS_MIN_DIMS

        # 冲突 = 有共识证据支持别的标签，或共识证据惩罚LLM的标签
        conflict = ((alt_consensus and alt_move != llm_label and alt_support >= CONFLICT_MIN_SUPPORT)
                    or (llm_pen_consensus and llm_penalty >= CONFLICT_MIN_SUPPORT))

        # 最终标签：无冲突→LLM标签（规则增强置信度）；有冲突→待二次审核
        final_label = llm_label
        final_conf = llm_conf
        if not conflict:
            # 规则增强或惩罚LLM标签
            llm_boost = sum(a["delta"] for a in adjustments
                           if a.get("action") == "+score" and a.get("label") == llm_label)
            final_conf = max(0.1, min(1.0, llm_conf + llm_boost - llm_penalty * 0.5))
        else:
            # 冲突 → 规则建议指向备选标签（供二次审核参考）
            rule_suggestion = alt_move

        out_item = dict(item)
        out_item[label_field] = final_label
        out_item["confidence"] = round(final_conf, 3)
        out_item["rule_suggestion"] = rule_suggestion if conflict else None
        out_item["rule_scores"] = {m: round(v, 3) for m, v in scores.items()}
        out_item["evidence"] = evidence
        out_item["adjustments"] = adjustments
        out_item["conflict"] = conflict
        adjusted.append(out_item)
        if conflict:
            conflicts.append(idx)

    return {"adjusted": adjusted, "conflicts": conflicts}
