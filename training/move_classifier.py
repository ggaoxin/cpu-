"""语步分类器（分层式混合架构）。

流程（rule.pdf 第11条：规则不直接覆盖 LLM，只调分/触发复核）：
  摘要 → [Prompt: 抽象原则] → GLM 主调用 → 5 段划分
       → [后置规则引擎: 确定性校验 + pattern 证据 + 调分 + 冲突检测]
       → 冲突句 → [二次审核: 结构化证据送 GLM 裁定]
       → 重拼最终 spans + 证据 + 置信度
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from infrastructure.llm.glm_client import glm_client
from training.config import GLM_TEMPERATURE
from training.conflict_review import review as conflict_review
from training.profile import get_profile
from training.rule_engine import reassemble_spans, verify_and_adjust
from training.rule_lib import RuleLib

logger = logging.getLogger(__name__)


def _call_llm(abstract: str, rule_lib: RuleLib, temperature: float, client=None) -> tuple:
    """GLM 主调用（prompt 只含抽象判定原则，不逐条拼规则）。

    返回 (spans, ok)。GLM 调用失败时直接抛出异常，不使用本地规则代替。
    """
    p = get_profile()
    system_prompt = rule_lib.render_principles_prompt() + rule_lib.render_few_shot()
    user_prompt = p.classify_user_prompt.format(abstract=abstract)
    model_client = client or glm_client
    data = model_client.chat_json(system_prompt, user_prompt, temperature=temperature)
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        data = data["data"]
    spans: Dict[str, str] = {}
    for m in p.moves:
        v = data.get(m, "") if isinstance(data, dict) else ""
        spans[m] = str(v).strip() if v else ""
    # LLM 自评的语步级置信度（含判空确信度），作为梯度置信度的基础分，替代固定 0.70
    llm_conf = data.get("move_confidence", {}) if isinstance(data, dict) else {}
    if not isinstance(llm_conf, dict):
        llm_conf = {}
    llm_conf = {m: float(llm_conf[m]) for m in p.moves
                if isinstance(llm_conf.get(m), (int, float)) and 0.0 <= float(llm_conf[m]) <= 1.0}
    ok = any(spans.values())
    return spans, ok, llm_conf


def classify_full(
    abstract: str,
    rule_lib: RuleLib,
    temperature: float = GLM_TEMPERATURE,
    do_review: bool = True,
    domain: Optional[str] = None,
    client=None,
) -> Dict[str, Any]:
    """完整分类流程，返回 spans + 证据 + 置信度。

    do_review: 是否对冲突句触发二次审核（训练批量评估时可关闭以省调用，
               但默认开启以测量真实系统效果）。
    """
    model_client = client or glm_client
    spans_llm, llm_ok, llm_conf = _call_llm(abstract, rule_lib, temperature, model_client)
    res = verify_and_adjust(abstract, spans_llm, rule_lib, domain=domain)

    sent_analysis = res["sentences"]
    sentences = get_profile().seg.segment(abstract)
    final_labels: List[str] = [sa["llm_label"] for sa in sent_analysis]

    n_conflicts = 0
    n_reviewed = 0
    if do_review and res["conflicts"]:
        for i in res["conflicts"]:
            sa = sent_analysis[i]
            ctx = sentences[max(0, i - 1): i + 2]
            r = conflict_review(
                sentence=sa["text"],
                context=ctx,
                llm_label=sa["llm_label"],
                rule_suggestion=sa["rule_suggestion"],
                evidence=sa["evidence"],
                temperature=temperature,
                client=model_client,
                strict=True,
            )
            final_labels[i] = r["final_label"]
            sa["review_label"] = r["final_label"]
            sa["review_reason"] = r["reason"]
            n_reviewed += 1
            if r["final_label"] != sa["llm_label"]:
                n_conflicts += 1
    else:
        # 未触发审核时，冲突标记仍保留供诊断
        n_conflicts = len(res["conflicts"])

    final_spans = reassemble_spans(abstract, final_labels)
    n_sent = max(1, len(sentences))
    confidence = round((n_sent - len(res["conflicts"])) / n_sent, 3)

    return {
        "spans": final_spans,
        "evidence": sent_analysis,
        "confidence": confidence,
        "n_conflicts": n_conflicts,
        "n_reviewed": n_reviewed,
        "deterministic_issues": res["deterministic_issues"],
        "llm_spans": spans_llm,
        "llm_confidence": llm_conf,
        "failed": not llm_ok,
    }


def classify(abstract: str, rule_lib: RuleLib, temperature: float = GLM_TEMPERATURE,
             do_review: bool = True) -> Dict[str, str]:
    """向后兼容：只返回 spans。"""
    return classify_full(abstract, rule_lib, temperature=temperature, do_review=do_review)["spans"]


def make_predict_fn(rule_lib: RuleLib, temperature: float = GLM_TEMPERATURE,
                    do_review: bool = True):
    """返回闭包 predict_fn(abstract)->spans，供 evaluator 使用。"""
    def _predict(abstract: str) -> Dict[str, str]:
        return classify(abstract, rule_lib, temperature=temperature, do_review=do_review)
    return _predict
