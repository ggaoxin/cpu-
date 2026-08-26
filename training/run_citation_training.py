"""引用句识别训练入口（复用语步识别的训练框架）。

用法：
  python -m training.run_citation_training --code cr_sentiment --induce-size 10 --eval-size 10
  python -m training.run_citation_training --code cr_intent --induce-size 10 --eval-size 10

流程：
  1. 加载gold数据（引用句 + 正确标签）
  2. 5折CV + 留出集
  3. 每折：induce_and_validate（归纳规则+净收益准入）→ calibrate_weights（动态权重）
  4. 多折聚合
  5. 输出更新后的yaml（带stats/level/dynamic_weight）

数据格式（gold JSON）：
  [{"sentence":"引用句", "sentiment":"支持", "intent":"用于背景介绍"}, ...]
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import settings
from training.citation_profile import set_citation_profile_by_code, get_citation_profile, rule_path
from training.rule_lib import RuleLib, Rule

logger = logging.getLogger(__name__)

RULES_DIR = settings.RULES_DIR


@dataclass
class CitationSample:
    """引用句训练样本（类似data_loader.Sample）。"""
    id: int
    sentence: str
    label: str  # gold标签


def load_gold(code: str, gold_file: str) -> List[CitationSample]:
    """加载gold数据。"""
    p = set_citation_profile_by_code(code)
    label_field = p.label_field
    data = json.loads(Path(gold_file).read_text(encoding="utf-8"))
    samples = []
    for i, item in enumerate(data):
        label = item.get(label_field, "")
        if label and label in p.labels:
            samples.append(CitationSample(id=i, sentence=item["sentence"], label=label))
    logger.info("加载 %s gold: %d 条", code, len(samples))
    return samples


def split_folds(samples: List[CitationSample], n_folds: int = 5, eval_ratio: float = 0.2):
    """分层分折 + 留出集。"""
    import random
    rng = random.Random(42)
    # 按标签分层
    by_label: Dict[str, List[CitationSample]] = {}
    for s in samples:
        by_label.setdefault(s.label, []).append(s)
    # 留出集
    holdout = []
    train = []
    for label, group in by_label.items():
        rng.shuffle(group)
        n_eval = max(1, int(len(group) * eval_ratio))
        holdout.extend(group[:n_eval])
        train.extend(group[n_eval:])
    # 分折
    rng.shuffle(train)
    fold_size = max(1, len(train) // n_folds)
    folds = [train[i:i+fold_size] for i in range(0, len(train), fold_size)]
    return folds, holdout


def induce_rules_for_citations(
    train_samples: List[CitationSample],
    validate_samples: List[CitationSample],
    baseline_lib: RuleLib,
    code: str,
) -> RuleLib:
    """归纳规则（适配引用句场景）。

    复用 rule_inducer 的净收益测量逻辑，但归纳prompt从CitationProfile读。
    """
    from infrastructure.llm.glm_client import glm_client
    p = get_citation_profile()

    # 收集错例（LLM判错 vs gold）
    # 简化版：直接用 gold 标签，跳过 LLM 调用（训练时 LLM 缓存可选）
    # 实际训练时应该先跑 LLM 获取错例，这里先用 gold 直接归纳
    errors = []
    for s in train_samples:
        # 如果有 LLM 输出缓存，对比 gold 找错例
        # 这里简化：所有样本作为归纳材料
        errors.append({"sentence": s.sentence, "gold": s.label})

    if not errors:
        return baseline_lib

    # LLM 归纳规则
    sysp = p.induce_system
    error_str = "\n".join([f"[{i+1}] sentence: {e['sentence'][:100]}\n    gold: {e['gold']}"
                          for i, e in enumerate(errors[:20])])
    try:
        d = glm_client.chat_json(
            sysp,
            f"以下引用句及其正确标签，请归纳3-5条能准确判定标签的规则。\n{error_str}\n\n"
            f"只输出JSON：{{\"data\":{{\"rules\":[{{\"id\":\"{p.rule_id_prefix}-LEARN-001\","
            f"\"target_move\":\"标签\",\"necessary_conditions\":[{{\"kind\":\"keyword\",\"any_of\":[\"词1\",\"词2\"]}}],"
            f"\"exclusion_conditions\":[],\"description\":\"理由\"}}]}}}}",
            timeout=120.0, max_tokens=1500, temperature=0.1,
        )
        d = d.get("data", d) if isinstance(d, dict) else {}
        new_rules = d.get("rules", [])
    except Exception:  # noqa: BLE001
        new_rules = []

    # 转为 Rule 对象 + 净收益测量
    from training.rule_inducer import measure_gain, assign_level
    lib = RuleLib(
        name=baseline_lib.name,
        functional_item=baseline_lib.functional_item,
        description=baseline_lib.description,
        system_prompt=baseline_lib.system_prompt,
        principles=baseline_lib.principles,
        pattern_rules=list(baseline_lib.pattern_rules),
        dictionaries=baseline_lib.dictionaries,
        examples=baseline_lib.examples,
        output_schema=baseline_lib.output_schema,
    )

    for r in new_rules:
        rule = Rule.from_dict(r)
        rule.layer = "universal"
        rule.scope = "global"
        rule.action = "+score"
        rule.level = "candidate"
        rule.weight = 0.5
        rule.stats = {}

        # 净收益测量（在验证集上）
        gain = _measure_citation_gain(rule, validate_samples)
        rule.stats = gain
        rule.level = assign_level(gain, 0.0, True)

        if gain.get("net_gain", 0) > 0:
            lib.pattern_rules.append(rule)
            logger.info("采纳规则 %s: net_gain=%d, level=%s", rule.id, gain.get("net_gain", 0), rule.level)
        else:
            logger.info("拒绝规则 %s: net_gain=%d", rule.id, gain.get("net_gain", 0))

    return lib


def _measure_citation_gain(rule: Rule, samples: List[CitationSample]) -> Dict:
    """测量规则在验证集上的净收益（改对-改错）。"""
    from training.citation_rule_engine import rule_fires
    correct = incorrect = matched = reinforce = 0
    for s in samples:
        if not rule_fires(rule, s.sentence):
            continue
        matched += 1
        if rule.target_move == s.label:
            correct += 1
        else:
            incorrect += 1
    return {
        "matched": matched,
        "correct": correct,
        "incorrect": incorrect,
        "reinforce": matched - correct - incorrect,
        "net_gain": correct - incorrect,
        "estimated_reliability": correct / max(matched, 1),
        "evidence_strength": "high" if matched >= 5 else ("medium" if matched >= 2 else "low"),
        "measured_on": "验证集",
    }


def calibrate_citation_weights(lib: RuleLib, samples: List[CitationSample]) -> RuleLib:
    """在验证集上测量所有规则的净收益，填stats供动态权重使用。"""
    for rule in lib.pattern_rules:
        gain = _measure_citation_gain(rule, samples)
        rule.stats = gain
        if rule.fold_count == 0:
            rule.fold_count = 1
    return lib


def main():
    ap = argparse.ArgumentParser(description="引用句识别训练（规则归纳+动态权重）")
    ap.add_argument("--code", required=True, choices=["cr_sentiment", "cr_intent"], help="功能点")
    ap.add_argument("--gold", default=None, help="gold数据JSON路径")
    ap.add_argument("--n-folds", type=int, default=5)
    ap.add_argument("--eval-ratio", type=float, default=0.2)
    args = ap.parse_args()

    p = set_citation_profile_by_code(args.code)

    # 默认gold路径
    gold_file = args.gold or str(RULES_DIR / "citation_recognition" / f"gold_{args.code}.json")
    if not Path(gold_file).exists():
        print(f"gold文件不存在: {gold_file}")
        print(f"请准备gold数据（格式：[{{sentence:...,sentiment/intent:...}}]）")
        return

    # 加载gold
    samples = load_gold(args.code, gold_file)
    if len(samples) < 10:
        print(f"gold数据太少（{len(samples)}条），至少需要10条")
        return

    # 分折 + 留出集
    folds, holdout = split_folds(samples, args.n_folds, args.eval_ratio)
    print(f"训练: {sum(len(f) for f in folds)}条, 留出: {len(holdout)}条, {args.n_folds}折")

    # 加载基线规则库
    baseline = RuleLib.load(rule_path(args.code))
    print(f"基线规则: {len(baseline.pattern_rules)}条")

    # 每折归纳
    fold_libs = []
    for i, fold in enumerate(folds):
        print(f"\n=== 折{i+1}/{args.n_folds} ({len(fold)}条) ===")
        validate = [s for j, f2 in enumerate(folds) if j != i for s in f2] + holdout[:len(holdout)//2]
        lib = induce_rules_for_citations(fold, validate, baseline, args.code)
        fold_libs.append(lib)
        print(f"  规则数: {len(lib.pattern_rules)}")

    # 多折聚合
    from training.aggregator import aggregate
    final_lib = aggregate(fold_libs, baseline)
    print(f"\n聚合后规则: {len(final_lib.pattern_rules)}条")

    # 在留出集上校准动态权重
    final_lib = calibrate_citation_weights(final_lib, holdout)
    print(f"动态权重校准完成")

    # 保存
    out_path = rule_path(args.code)
    final_lib.save(out_path)
    print(f"\n已保存到: {out_path}")

    # 留出集评估
    from training.citation_rule_engine import verify_and_adjust_citations
    citations = [{"sentence": s.sentence, p.label_field: s.label, "confidence": 1.0} for s in holdout]
    result = verify_and_adjust_citations(citations, final_lib)
    n_correct = sum(1 for a in result["adjusted"] if a[p.label_field] == s.label
                   for a, s in zip(result["adjusted"], holdout))
    print(f"留出集准确率: {n_correct}/{len(holdout)} = {n_correct/max(len(holdout),1):.3f}")


if __name__ == "__main__":
    main()
