"""聚合器：把多折规则库合并、去重、等级重评，得到最终规则库（新 schema）。

策略（rule.pdf 第8/16条）：
- 收集所有折的 pattern_rules，按 id 统计 fold_count；
- 按 target_move+action+必要条件相似度去重，保留跨折频次高者；
- 通用基线规则（种子 MR-ZH-001~005）始终保留；
- 跨折稳定性升级/降级等级：多折稳定→strong/soft，单折→advisory（不丢弃，应纳尽纳）；
- 保留 baseline 的 principles / dictionaries / system_prompt / output_schema。
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List

from training.profile import get_profile
from training.rule_lib import Rule, RuleLib

logger = logging.getLogger(__name__)


@dataclass
class AggRule:
    rule: Rule
    fold_count: int


def _cond_key(rule: Rule) -> str:
    """规则的条件签名（用于相似去重）。"""
    return json.dumps({
        "target": rule.target_move,
        "action": rule.action,
        "nec": rule.necessary_conditions,
        "excl": rule.exclusion_conditions,
    }, ensure_ascii=False, sort_keys=True)


def _rules_similar(a: Rule, b: Rule) -> bool:
    """两条规则是否相似：同 target+action 且条件签名相同/包含。"""
    if a.target_move != b.target_move or a.action != b.action:
        return False
    ka, kb = _cond_key(a), _cond_key(b)
    return ka == kb


def _relevel(rule: Rule, fold_count: int, n_folds: int) -> str:
    """根据跨折稳定性重评等级（第8条）。"""
    if rule.id in get_profile().baseline_rule_ids:
        return "soft"  # 基线种子规则
    net = rule.net_gain
    # 跨多折稳定 + 净收益高 → strong
    if fold_count >= 3 and net >= 2 and rule.level in ("soft", "strong"):
        return "strong"
    if fold_count >= 2 and net >= 1:
        return "soft"
    # 单折出现：保留但降级为 advisory（不丢弃）
    return "advisory"


def aggregate(fold_libs: List[RuleLib], baseline: RuleLib) -> RuleLib:
    """聚合多折规则库，返回最终规则库。"""
    n_folds = len(fold_libs)
    fold_count: Counter = Counter()
    # 跨折累加每条规则的 stats（改对/改错/命中/增强），用于动态权重
    acc_stats: Dict[str, Dict[str, float]] = {}
    latest: Dict[str, Rule] = {}
    for lib in fold_libs:
        seen_in_fold = set()
        for r in lib.pattern_rules:
            seen_in_fold.add(r.id)
            latest[r.id] = r
            s = r.stats or {}
            a = acc_stats.setdefault(r.id, {"correct": 0, "incorrect": 0,
                                            "matched": 0, "reinforce": 0})
            a["correct"] += int(s.get("correct", 0))
            a["incorrect"] += int(s.get("incorrect", 0))
            a["matched"] += int(s.get("matched", 0))
            a["reinforce"] += int(s.get("reinforce", 0))
        for rid in seen_in_fold:
            fold_count[rid] += 1

    # 把累加后的 stats 写回 latest 规则
    for rid, r in latest.items():
        a = acc_stats[rid]
        r.stats = dict(r.stats or {})
        r.stats.update({
            "correct": a["correct"], "incorrect": a["incorrect"],
            "matched": a["matched"], "reinforce": a["reinforce"],
            "net_gain": a["correct"] - a["incorrect"],
            "estimated_reliability": round((a["correct"] + 1) / (a["correct"] + a["incorrect"] + 2), 3)
                if (a["correct"] + a["incorrect"]) >= 0 else 0.5,
            "measured_on": "验证集(跨折累加)",
        })

    agg_rules: List[AggRule] = [AggRule(rule=latest[rid], fold_count=fold_count[rid])
                                for rid in latest]

    # 相似去重：保留跨折频次高者
    kept: List[AggRule] = []
    for ar in sorted(agg_rules, key=lambda x: (-x.fold_count, x.rule.id)):
        if any(_rules_similar(ar.rule, k.rule) for k in kept):
            continue
        kept.append(ar)

    # 等级重评 + 设置 fold_count
    final_rules: List[Rule] = []
    for ar in kept:
        ar.rule.fold_count = ar.fold_count
        ar.rule.level = _relevel(ar.rule, ar.fold_count, n_folds)
        final_rules.append(ar.rule)

    final = RuleLib(
        name=baseline.name,
        functional_item=baseline.functional_item,
        description=baseline.description,
        system_prompt=baseline.system_prompt,
        principles=baseline.principles,
        pattern_rules=final_rules,
        dictionaries=baseline.dictionaries,
        examples=baseline.examples,
        output_schema=baseline.output_schema,
    )
    level_dist: Counter = Counter(r.level for r in final_rules)
    logger.info("聚合完成：共 %d 条规则（去重前 %d），等级分布 %s",
                len(final_rules), len(by_id), dict(level_dist))
    for ar in kept:
        logger.info("  %s  采纳折数=%d  等级=%s  净收益=%d  %s",
                    ar.rule.id, ar.fold_count, ar.rule.level,
                    ar.rule.net_gain, ar.rule.description[:30])
    return final
