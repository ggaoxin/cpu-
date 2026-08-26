"""确定性语义特征提取（零 GLM 调用）。

把句子抽象成语义特征，而非直接匹配关键词。不同文字同机制可共用同一条规则（rule.pdf 第14条）。

特征维度与取值：
  research_actor: current_study | third_party | domain_fact | unknown
  fact_status:    observed | proposed | planned | expected | hypothetical | unknown
  action_type:    describe_problem | state_objective | propose_method | report_result | interpret_result | unknown
  evidence_type:  experiment | numeric | comparison | literature | method_function | none | unknown
  discourse_position: beginning | middle | ending | unknown
  clause_role:    main_clause | purpose_clause | condition_clause | result_clause | conclusion_clause | unknown
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

# ---- 关键词表（确定性匹配，仅作特征证据，不直接决定标签）----
_THIRD_PARTY = ["已有研究", "相关文献", "其他学者", "先前研究", "前人", "传统方法", "现有研究",
                "已有研究表", "以往研究", "现有方法"]
_CURRENT_STUDY = ["本文", "本研究", "所提", "我们", "笔者"]

_OBSERVED = ["表明", "发现", "显示", "提高", "降低", "获得", "验证了", "证明了", "提升了", "降低了",
             "呈现", "递减", "递增", "体现", "反映", "满足"]
_PLANNED = ["拟", "计划", "将", "准备", "未来将"]
_EXPECTED = ["有望", "预期", "预计", "将成为", "可望"]
_HYPOTHETICAL = ["若", "如果", "假设", "假定"]
_PROPOSED = ["提出", "构建", "设计", "采用", "引入", "利用", "建立", "开发"]

_DESC_PROBLEM = ["存在", "不足", "问题", "挑战", "难以", "无法", "制约", "缺陷", "局限", "欠缺"]
_STATE_OBJ = ["旨在", "为了", "目的", "以期", "致力于", "目标是"]
_REPORT_RESULT = ["表明", "显示", "发现", "提高", "降低", "优于", "结果", "呈现", "递减", "递增", "反映"]
_INTERPRET = ["说明", "证实", "建议", "应", "需要", "据此", "综上", "具有重要意义", "具有应用价值",
              "有利于", "有助于", "可为", "促进", "推动"]

_EVIDENCE_EXPERIMENT = ["实验", "仿真", "算例", "试验", "实证", "样本", "数据集", "测试集"]
_EVIDENCE_NUMERIC = ["%", "百分比", "系数", "显著", "比率", "倍", "个百分点"]
_EVIDENCE_COMPARISON = ["优于", "相比", "对比", "高于", "低于", "提升", "超过"]
_EVIDENCE_LITERATURE = ["已有研究", "文献", "先前", "以往"]
_EVIDENCE_METHOD_FUNC = ["能够", "可以", "用于", "旨在改善", "用以"]

# 复合句从句标记
_PURPOSE_CLAUSE = ["针对", "为了", "为解决", "旨在", "以"]
_CONDITION_CLAUSE = ["若", "如果", "在...条件下", "当"]
_RESULT_CLAUSE = ["结果表明", "结果显示", "实验表明", "分析表明"]
_CONCLUSION_CLAUSE = ["据此", "综上", "因此", "进一步"]

_NUMERIC_RE = re.compile(r"\d+(\.\d+)?\s*[%％]")
_HAS_DIGIT = re.compile(r"\d")


def _any_in(text: str, words: List[str]) -> bool:
    return any(w in text for w in words)


def _first_match(text: str, ordered: List[List[str]]) -> str:
    """按优先级返回第一个命中的词组所属类别（用于 action_type/fact_status 等多类别判定）。"""
    for i, words in enumerate(ordered):
        if _any_in(text, words):
            return i
    return -1


def extract(sentence: str, idx: int = 0, n_total: int = 1) -> Dict[str, str]:
    """提取单句语义特征。

    idx: 该句在摘要中的位置（0-based）；n_total: 摘要总句数。
    返回六个维度的特征 dict。
    """
    s = sentence or ""
    feats: Dict[str, str] = {}

    # research_actor
    if _any_in(s, _THIRD_PARTY):
        feats["research_actor"] = "third_party"
    elif _any_in(s, _CURRENT_STUDY):
        feats["research_actor"] = "current_study"
    else:
        feats["research_actor"] = "domain_fact"

    # fact_status（优先级：observed > proposed > planned > expected > hypothetical）
    fs_order = [_OBSERVED, _PROPOSED, _PLANNED, _EXPECTED, _HYPOTHETICAL]
    fs_names = ["observed", "proposed", "planned", "expected", "hypothetical"]
    k = _first_match(s, fs_order)
    feats["fact_status"] = fs_names[k] if k >= 0 else "unknown"

    # action_type
    at_order = [_DESC_PROBLEM, _STATE_OBJ, _PROPOSED, _REPORT_RESULT, _INTERPRET]
    at_names = ["describe_problem", "state_objective", "propose_method",
                "report_result", "interpret_result"]
    k = _first_match(s, at_order)
    feats["action_type"] = at_names[k] if k >= 0 else "unknown"

    # evidence_type（可多类，取最强优先级：experiment > numeric > comparison > literature > method_function）
    if _any_in(s, _EVIDENCE_EXPERIMENT):
        feats["evidence_type"] = "experiment"
    elif _NUMERIC_RE.search(s) or (_HAS_DIGIT.search(s) and _any_in(s, _EVIDENCE_NUMERIC)):
        feats["evidence_type"] = "numeric"
    elif _any_in(s, _EVIDENCE_COMPARISON):
        feats["evidence_type"] = "comparison"
    elif _any_in(s, _EVIDENCE_LITERATURE):
        feats["evidence_type"] = "literature"
    elif _any_in(s, _EVIDENCE_METHOD_FUNC):
        feats["evidence_type"] = "method_function"
    else:
        feats["evidence_type"] = "none"

    # discourse_position
    if n_total <= 1:
        feats["discourse_position"] = "beginning"
    else:
        rel = idx / n_total
        if rel < 0.25:
            feats["discourse_position"] = "beginning"
        elif rel > 0.75:
            feats["discourse_position"] = "ending"
        else:
            feats["discourse_position"] = "middle"

    # clause_role
    if _any_in(s, _RESULT_CLAUSE):
        feats["clause_role"] = "result_clause"
    elif _any_in(s, _CONCLUSION_CLAUSE):
        feats["clause_role"] = "conclusion_clause"
    elif _any_in(s, _PURPOSE_CLAUSE):
        feats["clause_role"] = "purpose_clause"
    elif _any_in(s, _CONDITION_CLAUSE):
        feats["clause_role"] = "condition_clause"
    else:
        feats["clause_role"] = "main_clause"

    return feats


def extract_for_sentences(sentences: List[str]) -> List[Dict[str, str]]:
    """批量提取特征，自动传入位置上下文。"""
    n = len(sentences)
    return [extract(s, i, n) for i, s in enumerate(sentences)]


if __name__ == "__main__":
    tests = [
        "已有研究表明，图神经网络能够有效处理非欧氏结构数据。",
        "实验结果显示，该模块使F1值提高了3.2%。",
        "针对现有模型泛化能力不足的问题，本文提出一种多尺度网络。",
        "据此，本文提出应从理论层面转向应用研究。",
        "该模块能够提高分类性能。",
    ]
    for t in tests:
        print(t)
        print("  ", extract(t, 0, 5))
