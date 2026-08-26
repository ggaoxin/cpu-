"""规则归纳器（按 rule.pdf 方法论重设计）。

核心改变：
- 从"逐错例加词规则"→"受约束归纳 + 泛化验证"
- 产出新 schema 规则：必要条件 + 排除条件 + 证据维度 + 动作 + 等级
- 准入看"净纠错收益"（改对 - 改错）而非训练集准确率（第12条）
- 反例搜索：每条候选生成反例检查是否误触发（第9条）
- 复杂度惩罚（第13条）、小样本平滑（第7条）、等级分配（第8条）

成本优化：准入测量时 LLM 主调用每篇只跑一次，引擎用/不用规则做确定性对比
（冲突标志级净收益），不额外触发二次审核 GLM 调用。
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.llm.glm_client import glm_client
from training.config import (
    GLM_INDUCE_TEMPERATURE, INDUCE_BATCH_SIZE,
    CROSS_CHECK_SIZE, ENABLE_COUNTEREXAMPLE, VALIDATE_SIZE,
)
from training.data_loader import Sample
from training.profile import get_profile
from training.rule_engine import verify_and_adjust
from training.rule_lib import Rule, RuleLib

logger = logging.getLogger(__name__)




# ----------------------------------------------------------------------- #
# 错例收集
# ----------------------------------------------------------------------- #
def _llm_spans_cache(samples: List[Sample], rule_lib: RuleLib) -> Dict[int, Dict[str, str]]:
    """对样本做 GLM 主调用（不审核），返回 {sample_id: llm_spans}，跳过失败摘要。

    用于验证集的净收益测量（复用主调用结果，measure_gain 零额外 GLM）。
    """
    from training.batch import classify_batch_full
    full = classify_batch_full([s.abstract for s in samples], rule_lib,
                               show_progress=False, do_review=False)
    cache: Dict[int, Dict[str, str]] = {}
    n_skip = 0
    for s, res in zip(samples, full):
        if res.get("failed"):
            n_skip += 1
            continue
        cache[s.id] = res["llm_spans"]
    if n_skip:
        logger.info("验证集跳过 %d 篇 GLM 失败摘要", n_skip)
    return cache


def collect_errors(
    samples: List[Sample], rule_lib: RuleLib, max_samples: int
) -> Tuple[List[dict], List[Sample], float, Dict[int, Dict[str, str]]]:
    """在训练子集上跑分类（引擎、不审核），收集错分句例 + 缓存 LLM 原始输出。

    返回 (errors, used_samples, train_acc, llm_spans_cache)。
    llm_spans_cache: {sample_id: llm原始spans}，供 measure_gain 复用（省一半 GLM 调用）。
    """
    from training.batch import classify_batch_full

    sub = samples[:max_samples]
    full = classify_batch_full([s.abstract for s in sub], rule_lib,
                               show_progress=False, do_review=False)
    errors: List[dict] = []
    n_sent = n_correct = 0
    llm_spans_cache: Dict[int, Dict[str, str]] = {}
    used: List[Sample] = []
    n_skipped = 0
    for local_idx, (s, res) in enumerate(zip(sub, full)):
        # 跳过 GLM 调用失败的摘要（如内容审核拦截/超时）——空预测不是真实错例，
        # 喂给诱导器还会再次触发拦截
        if res.get("failed"):
            n_skipped += 1
            continue
        llm_spans_cache[s.id] = res["llm_spans"]
        used.append(s)
        seg = get_profile().seg
        sents = seg.segment(s.abstract)
        gold_labels = seg.assign_sentences_to_spans(sents, s.spans)
        pred_labels = seg.assign_sentences_to_spans(sents, res["spans"])
        # 重新映射 idx 到 used 中的下标
        local = len(used) - 1
        for sent, g, p in zip(sents, gold_labels, pred_labels):
            n_sent += 1
            if g == p:
                n_correct += 1
            else:
                errors.append({
                    "idx": local,
                    "abstract": s.abstract,
                    "sentence": sent,
                    "gold_move": g or "(无)",
                    "pred_move": p or "(无)",
                })
        if len(errors) >= 80:
            break
    if n_skipped:
        logger.info("跳过 %d 篇 GLM 失败摘要（内容审核/超时）", n_skipped)
    train_acc = n_correct / n_sent if n_sent else 0.0
    return errors, used, train_acc, llm_spans_cache


# ----------------------------------------------------------------------- #
# 归纳
# ----------------------------------------------------------------------- #
def induce_rules(errors: List[dict]) -> List[dict]:
    """让 GLM 从错例归纳结构化候选规则。分批避免超时。

    把每条错例的实际提取特征也喂给 GLM，使其写的 feature 条件锚定真实特征（校准对齐）。
    """
    p = get_profile()
    if not errors:
        return []
    numbered = []
    for i, e in enumerate(errors):
        feats = p.features.extract(e["sentence"], 0, 1)
        numbered.append({
            "序号": i + 1,
            "摘要片段": e["abstract"][:60],
            "错分句子": e["sentence"],
            "标准语步": e["gold_move"],
            "模型预测": e["pred_move"],
            "实际特征": feats,
        })
    user = p.induce_user_intro + json.dumps(numbered, ensure_ascii=False, indent=2)
    try:
        data = glm_client.chat_json(p.induce_system, user,
                                    temperature=GLM_INDUCE_TEMPERATURE, timeout=240)
    except Exception as exc:  # noqa: BLE001
        logger.error("规则归纳 GLM 调用失败: %s", exc)
        return []
    raw = data.get("rules", []) if isinstance(data, dict) else []
    logger.info("归纳出 %d 条候选规则", len(raw))
    return raw


# ----------------------------------------------------------------------- #
# 规则影响测量（净纠错收益，引擎级、零额外 GLM）
# ----------------------------------------------------------------------- #
def _lib_with_rule(rule_lib: RuleLib, rule: Rule) -> RuleLib:
    new_lib = copy.deepcopy(rule_lib)
    if any(r.id == rule.id for r in new_lib.pattern_rules):
        new_lib.pattern_rules = [rule if r.id == rule.id else r for r in new_lib.pattern_rules]
    else:
        new_lib.pattern_rules.append(rule)
    return new_lib


def measure_gain(
    rule: Rule,
    rule_lib: RuleLib,
    samples: List[Sample],
    llm_spans_cache: Dict[int, Dict[str, str]],
) -> Dict[str, Any]:
    """测量候选规则的净纠错收益（复用 LLM 缓存，零额外 GLM 调用）。

    直接测规则在"LLM 判错的句子"上是否指向正确标签：
    - 规则命中 + target==gold（LLM判错）→ correct（改对方向）
    - 规则命中 + target!=gold（LLM判错）→ incorrect（改错方向）
    - LLM 已判对的句子上命中 → reinforce（中性，不计净收益）
    净收益 = correct - incorrect。
    """
    from training.rule_engine import rule_fires
    p = get_profile()
    seg = p.seg

    correct = incorrect = matched = reinforce = 0
    hurt_samples = 0
    for s in samples:
        llm_spans = llm_spans_cache.get(s.id)
        if llm_spans is None:
            continue
        sents = seg.segment(s.abstract)
        feats = p.features.extract_for_sentences(sents)
        gold = seg.assign_sentences_to_spans(sents, s.spans)
        llm_labels = seg.assign_sentences_to_spans(sents, llm_spans)
        sample_hurt = False
        for i, sent in enumerate(sents):
            ctx = {"seen_moves": {}, "rel_pos": i / max(len(sents), 1), "idx": i, "n": len(sents)}
            if not rule_fires(rule, sent, feats[i], ctx):
                continue
            matched += 1
            if llm_labels[i] == gold[i]:
                # LLM 已判对，规则命中只算增强（不改标签）
                reinforce += 1
                continue
            # LLM 判错的句子上，规则指向 gold 为改对，否则改错
            if rule.target_move == gold[i]:
                correct += 1
            else:
                incorrect += 1
                sample_hurt = True
        if sample_hurt:
            hurt_samples += 1
    net_gain = correct - incorrect
    # 可靠性 = 规则在 LLM 判错句上的指向正确率（不含"增强"的中性命中）
    reliability = (correct + 1) / (correct + incorrect + 2) if (correct + incorrect) >= 0 else 0.5
    return {
        "correct": correct, "incorrect": incorrect, "matched": matched,
        "reinforce": reinforce,
        "net_gain": net_gain, "hurt_samples": hurt_samples,
        "estimated_reliability": round(reliability, 3),
        "evidence_strength": "low" if matched < 3 else ("medium" if matched < 8 else "high"),
    }


def calibrate_weights(
    rule_lib: RuleLib,
    samples: List[Sample],
    llm_spans_cache: Dict[int, Dict[str, str]],
) -> RuleLib:
    """在验证集上测量【所有规则】（含种子规则）的净收益，填 stats 供动态权重使用。

    关键：种子规则也在此被检验——太宽的种子规则净收益为负 → effective_weight=0 自动停用。
    测量是确定性的（复用 LLM 缓存，零额外 GLM 调用）。
    """
    for r in rule_lib.pattern_rules:
        g = measure_gain(r, rule_lib, samples, llm_spans_cache)
        r.stats = {
            "matched": g["matched"], "correct": g["correct"],
            "incorrect": g["incorrect"], "reinforce": g["reinforce"],
            "estimated_reliability": g["estimated_reliability"],
            "evidence_strength": g["evidence_strength"],
            "net_gain": g["net_gain"],
            "measured_on": "验证集(校准)",
        }
        r.compute_complexity()
    return rule_lib


# ----------------------------------------------------------------------- #
# 反例搜索（第9条）
# ----------------------------------------------------------------------- #
def search_counterexamples(rule: Rule) -> Dict[str, Any]:
    """让 LLM 生成反例句，检查规则是否误触发。1 次 GLM 调用。"""
    rule_desc = json.dumps({
        "target_move": rule.target_move,
        "action": rule.action,
        "necessary_conditions": rule.necessary_conditions,
        "exclusion_conditions": rule.exclusion_conditions,
    }, ensure_ascii=False)
    user = f"规则如下：\n{rule_desc}\n\n请生成该规则不应触发或应被排除的反例句。"
    p = get_profile()
    try:
        data = glm_client.chat_json(p.counterexample_system, user,
                                    temperature=GLM_INDUCE_TEMPERATURE, timeout=120)
    except Exception as exc:  # noqa: BLE001
        logger.warning("反例搜索 GLM 失败 %s: %s", rule.id, exc)
        return {"ok": True, "counterexamples": [], "misfire": False, "reason": "反例搜索失败，放行"}

    ces = data.get("counterexamples", []) if isinstance(data, dict) else []
    # 用引擎检查规则是否在反例上误触发（命中即误触发，因反例本不该触发）
    misfires: List[str] = []
    from training.rule_engine import rule_fires
    for ce in ces:
        sent = ce.get("sentence", "")
        if not sent:
            continue
        feats = p.features.extract(sent, 0, 1)
        ctx = {"seen_moves": {}, "rel_pos": 0.5, "idx": 0, "n": 1}
        if rule_fires(rule, sent, feats, ctx):
            # 触发了，但反例的真标签不是 target_move → 误触发
            if ce.get("true_move") != rule.target_move:
                misfires.append(sent)
    misfire = len(misfires) > 0
    return {"ok": not misfire, "counterexamples": ces, "misfire": misfire, "misfires": misfires}


# ----------------------------------------------------------------------- #
# 等级分配（第8条）
# ----------------------------------------------------------------------- #
def assign_level(gain: Dict[str, Any], complexity: float, counterexample_ok: bool) -> str:
    """根据净收益、可靠性、复杂度、反例结果分配等级。"""
    net = gain["net_gain"]
    rel = gain["estimated_reliability"]
    strength = gain["evidence_strength"]
    # strong 留给跨折稳定（聚合阶段升）；这里最高 soft
    if net >= 3 and rel >= 0.7 and counterexample_ok and complexity < 8 and strength != "low":
        return "soft"
    if net >= 1 and counterexample_ok:
        return "advisory"
    return "candidate"


# ----------------------------------------------------------------------- #
# 主入口
# ----------------------------------------------------------------------- #
def induce_and_validate(
    rule_lib: RuleLib,
    train_samples: List[Sample],
    induce_sample_size: int,
    validate_samples: Optional[List[Sample]] = None,
    check_size: int = 0,
    max_candidates: int = 12,
    batch_size: int = INDUCE_BATCH_SIZE,
    use_cross_check: bool = True,
) -> RuleLib:
    """一轮归纳 + 净收益准入 + 反例搜索 + 等级分配。

    关键（rule.pdf 第6条）：规则从 train_samples 归纳，净收益在 validate_samples（归纳时未见过）
    上测量——避免"用训练集既归纳又验证"的循环泄漏。validate_samples 为 None 时回退到归纳集（不推荐）。
    """
    errors, used_samples, train_acc, induce_cache = collect_errors(
        train_samples, rule_lib, induce_sample_size)
    logger.info("本轮归纳集句准确率=%.4f（当前规则库，归纳前）", train_acc)
    if not errors:
        logger.info("无错例，归纳集已拟合，跳过归纳")
        return rule_lib

    # 验证集 cache：准入净收益在验证集上测（泛化校验）
    if validate_samples:
        val_cache = _llm_spans_cache(validate_samples, rule_lib)
        measure_set, measure_cache = validate_samples, val_cache
        measure_src = "验证集(未参与归纳)"
    else:
        measure_set, measure_cache = used_samples, induce_cache
        measure_src = "归纳集(警告:循环泄漏风险)"

    # 分批归纳
    all_candidates: List[dict] = []
    for start in range(0, len(errors), batch_size):
        chunk = errors[start:start + batch_size]
        local_to_global = {i + 1: start + i + 1 for i in range(len(chunk))}
        raw = induce_rules(chunk)
        for c in raw:
            c["addresses"] = [local_to_global[s] for s in (c.get("addresses") or [])
                              if s in local_to_global]
        all_candidates.extend(raw)
        logger.info("批次 %d-%d: 累计候选 %d 条", start + 1, start + len(chunk), len(all_candidates))

    # 去重 + 统一编号
    seen, deduped = set(), []
    for c in all_candidates:
        key = json.dumps({"t": c.get("target_move"), "a": c.get("action"),
                          "n": c.get("necessary_conditions"), "e": c.get("exclusion_conditions")},
                         ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    for i, c in enumerate(deduped):
        c["id"] = f"{get_profile().rule_id_prefix}-{101 + i}"
    all_candidates = deduped[:max_candidates]
    logger.info("去重后 %d 条候选，在%s上测净纠错收益", len(all_candidates), measure_src)

    accepted: List[Rule] = []
    for c in all_candidates:
        rule = _build_rule(c)
        if rule is None:
            continue
        # 门槛1：净纠错收益 > 0（在验证集上测）
        gain = measure_gain(rule, rule_lib, measure_set, measure_cache)
        rule.stats = {
            "matched": gain["matched"], "correct": gain["correct"],
            "incorrect": gain["incorrect"],
            "estimated_reliability": gain["estimated_reliability"],
            "evidence_strength": gain["evidence_strength"],
            "net_gain": gain["net_gain"],
            "measured_on": measure_src,
        }
        rule.compute_complexity()
        logger.info("候选 %s: 改对=%d 改错=%d 净收益=%d 可靠性=%.2f 复杂度=%.1f [%s]",
                    rule.id, gain["correct"], gain["incorrect"], gain["net_gain"],
                    gain["estimated_reliability"], rule.complexity, measure_src)
        if gain["net_gain"] <= 0:
            logger.info("  %s 验证集净收益<=0 -> 拒绝(未泛化)", rule.id)
            continue
        # 门槛2：反例搜索（可选）
        ce_ok = True
        if ENABLE_COUNTEREXAMPLE:
            ce = search_counterexamples(rule)
            ce_ok = ce["ok"]
            if not ce_ok:
                logger.info("  %s 反例误触发(%d) -> 降级或拒绝", rule.id, len(ce["misfires"]))
                rule.negative_examples = [m[:60] for m in ce["misfires"][:3]]
        # 等级
        rule.level = assign_level(gain, rule.complexity, ce_ok)
        if rule.level == "candidate":
            logger.info("  %s 等级=candidate(证据不足) -> 暂不入库", rule.id)
            continue
        logger.info("  %s -> 采纳(等级=%s)", rule.id, rule.level)
        accepted.append(rule)

    if accepted:
        new_lib = _lib_with_rule(rule_lib, accepted[0])
        for r in accepted[1:]:
            new_lib = _lib_with_rule(new_lib, r)
        logger.info("本轮采纳 %d 条规则（验证集净收益+反例+等级准入）", len(accepted))
    else:
        new_lib = rule_lib
        logger.info("本轮无规则通过准入（验证集净收益均<=0）")

    # 校准所有规则（含种子）的动态权重：在验证集上测净收益，太宽的自动降权/停用
    if validate_samples:
        calibrate_weights(new_lib, validate_samples, val_cache)
        disabled = [r.id for r in new_lib.pattern_rules if r.stats and r.net_gain < 0]
        if disabled:
            logger.info("动态权重：以下规则验证集净收益<0，自动停用 -> %s", disabled)
    return new_lib


def _build_rule(c: dict) -> Optional[Rule]:
    """从归纳输出构造 Rule。"""
    cid = c.get("id", "")
    target = c.get("target_move")
    action = c.get("action", "+score")
    if not cid or not target or target not in get_profile().moves:
        # action=review 可无 target，但通常需要
        if not cid:
            return None
    nec = c.get("necessary_conditions") or []
    exc = c.get("exclusion_conditions") or []
    if not nec:
        return None
    return Rule(
        id=cid,
        layer="universal",
        scope="global",
        target_move=target,
        necessary_conditions=nec,
        exclusion_conditions=exc,
        evidence_dims=c.get("evidence_dims") or [],
        action=action if action in ("+score", "-score", "review") else "+score",
        level="candidate",
        weight=0.5,
        description=c.get("description", ""),
        positive_examples=[],
        negative_examples=[],
    )
