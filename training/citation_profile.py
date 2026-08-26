"""引用句识别 Profile（情感/意图）。

类似 training/profile.py 的语言Profile，但针对引用句识别：
- 中英文共用一套标签（不需要语言切换）
- 两个子Profile：cr_sentiment（情感3类）和 cr_intent（意图3类）
- 不需要分句器/特征提取器（引用句已由规则抽取，句子级别打标签）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from config.settings import settings


@dataclass
class CitationProfile:
    """引用句识别Profile（情感或意图）。"""
    code: str                              # cr_sentiment | cr_intent
    label_field: str                       # sentiment | intent
    labels: List[str]                      # 标签列表
    rule_file: str                         # yaml相对路径
    rule_id_prefix: str                    # CR-SENT | CR-INT
    induce_system: str = ""                # 归纳prompt（训练时用）
    counterexample_system: str = ""        # 反例搜索prompt
    review_system: str = ""                # 冲突审核prompt


# 两个Profile定义
PROFILES = {
    "cr_sentiment": CitationProfile(
        code="cr_sentiment",
        label_field="sentiment",
        labels=["支持", "中立", "有局限性"],
        rule_file="citation_recognition/cr_sentiment.yaml",
        rule_id_prefix="CR-SENT",
        induce_system=(
            "你是学术引用情感分析专家。给定一批引用句及其正确情感标签（gold）和LLM的错误判定，"
            "归纳出能纠正LLM错误的规则。每条规则需含：必要条件（关键词/正则）、排除条件、目标标签、理由。\n"
            "情感标签：支持（肯定价值）、中立（客观陈述）、有局限性（指出不足）。"
        ),
        counterexample_system=(
            "你是学术引用情感分析专家。给定一条规则，搜索它可能误判的反例（规则命中但实际标签不对的句子）。\n"
            "情感标签：支持/中立/有局限性。"
        ),
        review_system=(
            "你是学术引用情感分析专家。给定引用句、LLM判定和规则建议（含证据），判断最终情感标签。\n"
            "情感标签：支持/中立/有局限性。只输出JSON：{\"final_label\":\"...\",\"reason\":\"...\"}"
        ),
    ),
    "cr_intent": CitationProfile(
        code="cr_intent",
        label_field="intent",
        labels=["用于背景介绍", "用于引入研究方法", "用于结果比较"],
        rule_file="citation_recognition/cr_intent.yaml",
        rule_id_prefix="CR-INT",
        induce_system=(
            "你是学术引用意图分析专家。给定一批引用句及其正确意图标签（gold）和LLM的错误判定，"
            "归纳出能纠正LLM错误的规则。每条规则需含：必要条件（关键词/正则）、排除条件、目标标签、理由。\n"
            "意图标签：用于背景介绍（铺垫领域现状）、用于引入研究方法（借用方法/工具）、用于结果比较（与本文结果对比）。"
        ),
        counterexample_system=(
            "你是学术引用意图分析专家。给定一条规则，搜索它可能误判的反例。\n"
            "意图标签：用于背景介绍/用于引入研究方法/用于结果比较。"
        ),
        review_system=(
            "你是学术引用意图分析专家。给定引用句、LLM判定和规则建议（含证据），判断最终意图标签。\n"
            "意图标签：用于背景介绍/用于引入研究方法/用于结果比较。只输出JSON：{\"final_label\":\"...\",\"reason\":\"...\"}"
        ),
    ),
    "cd_identify": CitationProfile(
        code="cd_identify",
        label_field="is_definition",
        labels=["定义句", "非定义句"],
        rule_file="concept_definition/cd_identify.yaml",
        rule_id_prefix="CD",
        induce_system=(
            "你是科技文献概念定义识别专家。给定一批句子及其正确标签（定义句/非定义句）和LLM的错误判定，"
            "归纳出能纠正LLM错误的规则。每条规则需含：必要条件（关键词/正则）、排除条件、目标标签、理由。\n"
            "定义句：明确给出概念定义的句子（含'是指''被称为''定义为'等标志）。"
        ),
        counterexample_system=(
            "你是科技文献概念定义识别专家。给定一条规则，搜索它可能误判的反例（规则命中但实际不是定义句）。\n"
            "标签：定义句/非定义句。"
        ),
        review_system=(
            "你是科技文献概念定义识别专家。给定句子、LLM判定和规则建议（含证据），判断是否定义句。\n"
            "标签：定义句/非定义句。只输出JSON：{\"final_label\":\"...\",\"reason\":\"...\"}"
        ),
    ),
}

# 当前Profile（类似profile.py的get_profile）
_current: Optional[CitationProfile] = None


def get_citation_profile() -> CitationProfile:
    if _current is None:
        raise RuntimeError("未设置CitationProfile，请先调 set_citation_profile_by_code()")
    return _current


def set_citation_profile_by_code(code: str) -> CitationProfile:
    global _current
    if code not in PROFILES:
        raise ValueError(f"未知引用句功能点: {code}（支持: {list(PROFILES.keys())}）")
    _current = PROFILES[code]
    return _current


def rule_path(code: str) -> Path:
    """返回规则库yaml完整路径。"""
    return settings.RULES_DIR / PROFILES[code].rule_file
