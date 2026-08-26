"""语言 Profile：把语言相关配置（moves/分句/特征/prompt/路径/规则ID前缀）集中。

共享核心（rule_engine/aggregator/dynamic weight/...）通过 get_profile() 取当前语言配置，
中文为默认（保持已交付系统不变），英文挂 EN_PROFILE。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

from training import sentence_seg, sentence_seg_en, feature_extractor, feature_extractor_en

from config.settings import settings as _settings
DATASETS_DIR = _settings.DATA_DIR
RULES_DIR = _settings.PROJECT_ROOT / "rules" / "move_recognition"


@dataclass
class Profile:
    lang: str
    moves: List[str]
    abstract_key: str
    abstracts_file: Path
    results_file: Path
    rule_file: Path
    fp_code: str
    rule_id_prefix: str                       # "MR-ZH" | "MR-EN"
    baseline_rule_ids: Set[str]
    seg: object                               # sentence_seg | sentence_seg_en
    features: object                          # feature_extractor | feature_extractor_en
    induce_system: str
    counterexample_system: str
    review_system: str
    classify_user_prompt: str                 # 主调用 user prompt 模板（{abstract} 占位）
    induce_user_intro: str                    # 归纳 user prompt 开头语


# ----------------------------- 中文 prompt ----------------------------- #
_ZH_INDUCE_SYSTEM = """你是中文摘要语步识别的规则归纳专家。
下面给你一批"模型预测错误"的句例（每条含 序号、错分句子、标准语步、模型预测语步、该句实际提取的语义特征）。

你要归纳的是【语言机制规则】，不是背个案：从错例抽象出可泛化的判定机制，
禁止照搬某篇专有术语原文。

规则用结构化条件表达，由后置规则引擎执行。条件格式（优先用 keyword/regex/position，feature 仅作辅助）：
- {kind: keyword, any_of: [词1,词2]}    任一关键词出现即命中（最常用，你能从句子原文直接看出来，写得准）
- {kind: keyword, all_of: [词1,词2]}    全部出现才命中
- {kind: regex, pattern: "正则"}         正则命中（用于结构化模式，如"呈现.*递减"）
- {kind: position, after_move: 研究结果}  该 move 已在前文出现
- {kind: position, before_move: 研究方法} 该 move 尚未出现
- {kind: feature, dim: <维度>, in: [值]}  语义特征命中（仅当特征值明确可靠时用；unknown/none 不可靠，勿依赖）

语义特征维度与取值（系统预提取，仅供参考；很多句会是 unknown/none，此时不要用 feature 条件）：
- research_actor: current_study | third_party | domain_fact | unknown
- fact_status: observed | proposed | planned | expected | hypothetical | unknown
- action_type: describe_problem | state_objective | propose_method | report_result | interpret_result | unknown
- evidence_type: experiment | numeric | comparison | literature | method_function | none | unknown
- discourse_position: beginning | middle | ending
- clause_role: main_clause | purpose_clause | condition_clause | result_clause | conclusion_clause

【归纳方法——严格三步】
1. 先拟合：针对错例写一条能纠正该错句的规则。优先用 keyword/regex 锚定错因的典型话术/结构
   （如"有利于…发展""呈现…递减""据此…应"），这些能从句子原文直接看出来，写得准。
2. 组合≥2种条件求共识：尽量让必要条件包含 2 种不同 kind（如 keyword + position、keyword + regex），
   多维证据共识才足以翻转 LLM 判定，单一线索不够。
3. 加排除条件防误触发：用 exclusion_conditions 排除易混情形（泛化来源）。

【规则字段】
- target_move: 该规则支持的语步（研究背景/目的/方法/结果/结论）
- action: +score（支持该 move）/ -score（削弱该 move）/ review（仅标记待复核）
- necessary_conditions: 必要条件列表（全部满足才触发）
- exclusion_conditions: 排除条件列表（任一满足即不触发）
- description: 见到…→判为…，理由…
- addresses: 该规则针对的错例序号列表

【要求】
- 每个错例至少被一条规则覆盖（addresses 里写序号）；
- 规则针对话术/结构机制，禁止照搬专有术语；不要写"X与Y须区分"空话；
- 优先 keyword/regex/position；feature 仅在特征值明确可靠时辅助；
- 必要条件尽量组合≥2种 kind 求共识；exclusion_conditions 越完整泛化越好。

【输出格式】仅输出 JSON：
{"analysis":"错因机制分析",
 "rules":[{"id":"MR-ZH-1xx","target_move":"...","action":"+score",
           "necessary_conditions":[...],"exclusion_conditions":[...],
           "description":"...","addresses":[序号]}]}"""

_ZH_COUNTEREXAMPLE_SYSTEM = """你是规则反例测试专家。下面给你一条语步识别规则。
请生成 5 个【该规则不应触发或应被排除】的反例句子，覆盖：同义改写、否定表达、
第三方研究主体、预测性/预期性表达、复合句。每条给一句话和它真正所属的语步。
仅输出 JSON：{"counterexamples":[{"sentence":"...","true_move":"研究背景"}, ...]}"""

_ZH_REVIEW_SYSTEM = (
    "你是中文摘要语步识别的冲突审核专家。下面给你一个句子及其上下文，"
    "模型原先将其判定为某语步，但规则引擎基于语义证据给出了不同建议。"
    "请结合句子的研究主体、事实状态、证据类型和上下文，裁定该句最终属于哪个语步。\n"
    "语步类别：研究背景、研究目的、研究方法、研究结果、研究结论。\n"
    "判定要点：\n"
    "- 含『已有研究/相关文献』等第三方主体的发现句，通常属研究背景而非本文结果；\n"
    "- 仅描述方法功能（能够/可以+效果）且无实验数据支撑的，不判为研究结果；\n"
    "- 结论通常排在结果之后，含对策/建议/意义升华；\n"
    "- 复合句应识别语步边界，『针对…问题』为目的从句，『本文提出…方法』为方法主句。\n"
    "输出 JSON：{\"final_label\": \"语步类别\", \"reason\": \"简短理由\"}。仅输出 JSON。"
)

# ----------------------------- 英文 prompt ----------------------------- #
_EN_INDUCE_SYSTEM = """You are a rule induction expert for English abstract move recognition.
Below are misclassified sentence examples (each with: index, sentence, gold move, predicted move, extracted semantic features).

Induce LANGUAGE-MECHANISM rules (not case-memorization): abstract generalizable decision mechanisms from errors. Do not copy paper-specific terms.

Rules use structured conditions executed by the post-output engine. Condition formats (prefer keyword/regex/position; feature only as auxiliary):
- {kind: keyword, any_of: [w1,w2]}    any keyword present (most reliable; you can see it in the sentence)
- {kind: keyword, all_of: [w1,w2]}    all keywords present
- {kind: regex, pattern: "regex"}      regex match (e.g. "improved.*by")
- {kind: position, after_move: Results}   the move already appeared earlier
- {kind: position, before_move: Methods}  the move has not appeared yet
- {kind: feature, dim: <dim>, in: [vals]} semantic feature match (only when the value is clear/reliable; not unknown/none)

Semantic feature dimensions and values (system-extracted, for reference; many will be unknown/none — do not rely on feature then):
- research_actor: current_study | third_party | domain_fact | unknown
- fact_status: observed | proposed | planned | expected | hypothetical | unknown
- action_type: describe_problem | state_objective | propose_method | report_result | interpret_result | unknown
- evidence_type: experiment | numeric | comparison | literature | method_function | none | unknown
- discourse_position: beginning | middle | ending
- clause_role: main_clause | purpose_clause | condition_clause | result_clause | conclusion_clause

Method (strict three steps):
1. Fit: write a rule that corrects the error. Prefer keyword/regex anchoring the typical cue/structure (e.g. "paves the way", "outperform", "we conclude").
2. Combine >=2 condition kinds for consensus (e.g. keyword + position, keyword + regex); multi-evidence consensus is needed to flip the LLM decision.
3. Add exclusion conditions to prevent mis-firing (generalization comes from exclusions).

Fields:
- target_move: Background | Objective | Methods | Results | Conclusion
- action: +score (support) | -score (penalize) | review (flag)
- necessary_conditions: all must match to fire
- exclusion_conditions: any match suppresses
- description: cue -> move, reason
- addresses: error indices this rule targets

Output JSON only:
{"analysis":"error mechanism analysis",
 "rules":[{"id":"MR-EN-1xx","target_move":"...","action":"+score",
           "necessary_conditions":[...],"exclusion_conditions":[...],
           "description":"...","addresses":[idx]}]}"""

_EN_COUNTEREXAMPLE_SYSTEM = """You are a counterexample tester for move-recognition rules.
Given a rule, generate 5 sentences where the rule should NOT fire or should be excluded, covering: paraphrase, negation, third-party research actor, predictive/expected expressions, compound sentences. For each give a sentence and its true move.
Output JSON only: {"counterexamples":[{"sentence":"...","true_move":"Background"}, ...]}"""

_EN_REVIEW_SYSTEM = (
    "You are a conflict-review expert for English abstract move recognition. Given a sentence and its context, "
    "the model labeled it with a move, but the rule engine suggests otherwise based on semantic evidence. "
    "Decide the final move based on research actor, tense/fact status, evidence type, and context.\n"
    "Moves: Background, Objective, Methods, Results, Conclusion.\n"
    "Notes:\n"
    "- A finding sentence with a third-party actor (previous studies/prior work) is usually Background, not this paper's Result.\n"
    "- A mere method-function description (can/able to + effect) without experimental data is not a Result.\n"
    "- Conclusion usually follows Results and contains interpretation/implications/suggestions.\n"
    "- In compound sentences, recognize the clause boundary (purpose clause vs method main clause).\n"
    "Output JSON: {\"final_label\": \"move\", \"reason\": \"brief reason\"}. Output JSON only."
)


# ----------------------------- Profile 实例 ----------------------------- #
ZH_PROFILE = Profile(
    lang="zh",
    moves=["研究背景", "研究目的", "研究方法", "研究结果", "研究结论"],
    abstract_key="ch_abstract",
    abstracts_file=DATASETS_DIR / "chinese_abstracts.json",
    results_file=DATASETS_DIR / "chinese_abstract_move_results.json",
    rule_file=RULES_DIR / "mr_zh_abstract.yaml",
    fp_code="mr_zh_abstract",
    rule_id_prefix="MR-ZH",
    baseline_rule_ids={f"MR-ZH-{i:03d}" for i in range(1, 6)},
    seg=sentence_seg,
    features=feature_extractor,
    induce_system=_ZH_INDUCE_SYSTEM,
    counterexample_system=_ZH_COUNTEREXAMPLE_SYSTEM,
    review_system=_ZH_REVIEW_SYSTEM,
    classify_user_prompt="请对以下中文论文摘要进行语步划分并输出 JSON：\n{abstract}",
    induce_user_intro="错分句例如下：\n",
)

EN_PROFILE = Profile(
    lang="en",
    moves=["Background", "Objective", "Methods", "Results", "Conclusion"],
    abstract_key="en_abstract",
    abstracts_file=DATASETS_DIR / "clean_english_abstracts.json",
    results_file=DATASETS_DIR / "clean_english_abstract_move_results.json",
    rule_file=RULES_DIR / "mr_en_abstract.yaml",
    fp_code="mr_en_abstract",
    rule_id_prefix="MR-EN",
    baseline_rule_ids={f"MR-EN-{i:03d}" for i in range(1, 6)},
    seg=sentence_seg_en,
    features=feature_extractor_en,
    induce_system=_EN_INDUCE_SYSTEM,
    counterexample_system=_EN_COUNTEREXAMPLE_SYSTEM,
    review_system=_EN_REVIEW_SYSTEM,
    classify_user_prompt="Perform move segmentation on the following English abstract and output JSON:\n{abstract}",
    induce_user_intro="Misclassified examples:\n",
)

_BY_CODE = {"mr_zh_abstract": ZH_PROFILE, "mr_en_abstract": EN_PROFILE}
_BY_LANG = {"zh": ZH_PROFILE, "en": EN_PROFILE}

_current: Profile = ZH_PROFILE


def get_profile() -> Profile:
    return _current


def set_profile(p: Profile) -> None:
    global _current
    _current = p


def set_profile_by_code(code: str) -> Profile:
    p = _BY_CODE.get(code, ZH_PROFILE)
    set_profile(p)
    return p


def set_profile_by_lang(lang: str) -> Profile:
    p = _BY_LANG.get(lang, ZH_PROFILE)
    set_profile(p)
    return p
