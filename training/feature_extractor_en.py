"""英文确定性语义特征提取（零 GLM，镜像中文 feature_extractor 的 6 维）。

特征维度与取值（与中文同构，便于共享 rule_engine）：
  research_actor: current_study | third_party | domain_fact | unknown
  fact_status:    observed | proposed | planned | expected | hypothetical | unknown
  action_type:    describe_problem | state_objective | propose_method | report_result | interpret_result | unknown
  evidence_type:  experiment | numeric | comparison | literature | method_function | none | unknown
  discourse_position: beginning | middle | ending | unknown
  clause_role:    main_clause | purpose_clause | condition_clause | result_clause | conclusion_clause | unknown
"""
from __future__ import annotations

import re
from typing import Dict, List

_THIRD_PARTY = ["previous studies", "prior work", "existing research", "earlier studies",
                "has been reported", "have been reported", "others have", "it has been",
                "previous work", "the literature", "prior research"]
_CURRENT_STUDY = ["this paper", "this study", "we ", "our ", "present work", "we present",
                  "we propose", "we investigate", "here we", "this work"]

_OBSERVED = ["showed", "demonstrated", "found", "improved", "achieved", "obtained",
             "revealed", "outperformed", "increased", "decreased", "reduced"]
_PLANNED = ["will ", "plan to", "we will", "shall"]
_EXPECTED = ["is expected", "are expected", "expected to", "can potentially", "could potentially",
             "is anticipated"]
_HYPOTHETICAL = ["if ", "when ", "assuming", "suppose"]
_PROPOSED = ["propose", "develop", "design", "employ", "introduce", "present", "construct",
             "build", "implement"]

_DESC_PROBLEM = ["remains challenging", "is limited", "suffer from", "lack of", "difficult to",
                 "however", "problem", "challenge", "gap", "few studies", "little is known"]
_STATE_OBJ = ["aim to", "in order to", "we investigate", "to investigate", "the objective",
              "goal of", "to explore", "to address"]
_REPORT_RESULT = ["showed", "demonstrated", "found", "improved", "outperformed", "results",
                  "show", "indicate", "reveal"]
_INTERPRET = ["suggest", "indicate", "imply", "we conclude", "conclude", "demonstrates",
              "may", "could lead", "paves the way", "holds promise", "implications"]

_EVIDENCE_EXPERIMENT = ["experiment", "experiments", "simulation", "simulations", "trial",
                        "trials", "benchmark", "ablation", "tested", "evaluated"]
_EVIDENCE_NUMERIC = ["%", "percent", "fold", "times", "score", "f1", "accuracy"]
_EVIDENCE_COMPARISON = ["outperform", "compared to", "higher than", "lower than", "better than",
                        "superior", "state-of-the-art", "baseline"]
_EVIDENCE_LITERATURE = ["reported", "has been reported", "previous", "prior", "literature"]
_EVIDENCE_METHOD_FUNC = ["can improve", "able to", "enables", "can achieve", "capable of",
                         "allows", "facilitates"]

_PURPOSE_CLAUSE = ["in order to", "to investigate", "to address", "aim to", "so that"]
_CONDITION_CLAUSE = ["if ", "when ", "under the condition", "assuming"]
_RESULT_CLAUSE = ["our results", "results show", "we find", "we found", "the results"]
_CONCLUSION_CLAUSE = ["we conclude", "in conclusion", "conclude that", "these findings",
                      "our study", "overall", "taken together"]

_NUMERIC_RE = re.compile(r"\d+(\.\d+)?\s*%")
_HAS_DIGIT = re.compile(r"\d")


def _any_in(text: str, words: List[str]) -> bool:
    t = text.lower()
    return any(w in t for w in words)


def _first_match(text: str, ordered: List[List[str]]) -> int:
    for i, words in enumerate(ordered):
        if _any_in(text, words):
            return i
    return -1


def extract(sentence: str, idx: int = 0, n_total: int = 1) -> Dict[str, str]:
    s = sentence or ""
    feats: Dict[str, str] = {}

    if _any_in(s, _THIRD_PARTY):
        feats["research_actor"] = "third_party"
    elif _any_in(s, _CURRENT_STUDY):
        feats["research_actor"] = "current_study"
    else:
        feats["research_actor"] = "domain_fact"

    fs_order = [_OBSERVED, _PROPOSED, _PLANNED, _EXPECTED, _HYPOTHETICAL]
    fs_names = ["observed", "proposed", "planned", "expected", "hypothetical"]
    k = _first_match(s, fs_order)
    feats["fact_status"] = fs_names[k] if k >= 0 else "unknown"

    at_order = [_DESC_PROBLEM, _STATE_OBJ, _PROPOSED, _REPORT_RESULT, _INTERPRET]
    at_names = ["describe_problem", "state_objective", "propose_method",
                "report_result", "interpret_result"]
    k = _first_match(s, at_order)
    feats["action_type"] = at_names[k] if k >= 0 else "unknown"

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

    if n_total <= 1:
        feats["discourse_position"] = "beginning"
    else:
        rel = idx / n_total
        feats["discourse_position"] = "beginning" if rel < 0.25 else ("ending" if rel > 0.75 else "middle")

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
    n = len(sentences)
    return [extract(s, i, n) for i, s in enumerate(sentences)]


if __name__ == "__main__":
    tests = [
        "Previous studies have reported that GNNs can process non-Euclidean data.",
        "Our results show that the model improves F1 by 3.2%.",
        "To address the limited generalization, we propose a multi-scale network.",
        "We conclude that this approach paves the way for future design.",
        "The module can improve classification performance.",
    ]
    for t in tests:
        print(t)
        print("  ", extract(t, 0, 5))
