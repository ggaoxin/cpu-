"""冲突二次审核（rule.pdf 第11条：规则与 LLM 冲突时，把结构化证据送二次审核 prompt）。

仅对后置引擎标记为冲突的句子调用一次 GLM，在"LLM 原判 vs 规则建议"间裁定。
证据不足时不破坏 LLM 原判（回退到 llm_label）。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from infrastructure.llm.glm_client import glm_client
from training.config import GLM_TEMPERATURE
from training.profile import get_profile

logger = logging.getLogger(__name__)


def review(
    sentence: str,
    context: Optional[List[str]] = None,
    llm_label: str = "",
    rule_suggestion: str = "",
    evidence: Optional[List[Dict[str, Any]]] = None,
    temperature: float = GLM_TEMPERATURE,
    client=None,
    strict: bool = False,
    review_system: str = "",
    valid_labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """对冲突句做二次审核。

    返回 {final_label, reason}。strict=True 时，GLM 失败或返回非法标签会直接抛错。
    """
    context = context or []
    evidence = evidence or []

    ev_lines = []
    for e in evidence:
        ev_lines.append(
            f"- 规则 {e.get('rule')} 建议判【{e.get('target')}】"
            f"（证据维度：{e.get('dims')}，等级：{e.get('level')}）：{e.get('description')}"
        )
    ev_text = "\n".join(ev_lines) if ev_lines else "（无规则证据）"

    ctx_text = ""
    if context:
        ctx_text = "上下文（前后句）：\n" + "\n".join(context) + "\n\n"

    user_prompt = (
        f"{ctx_text}"
        f"待判定句子：{sentence}\n\n"
        f"模型原判：【{llm_label or '未判定'}】\n"
        f"规则建议：【{rule_suggestion or '无'}】\n"
        f"规则证据：\n{ev_text}\n\n"
        f"请裁定该句最终语步标签。"
    )

    try:
        system_prompt = review_system or get_profile().review_system
        data = (client or glm_client).chat_json(system_prompt, user_prompt, temperature=temperature)
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise RuntimeError("冲突审核 GLM-5.2 调用失败") from exc
        logger.warning("冲突审核 GLM 调用失败，回退 LLM 原判 %s: %s", llm_label, exc)
        return {"final_label": llm_label, "reason": "审核失败，回退 LLM 原判"}

    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        data = data["data"]

    final = str(data.get("final_label", "")).strip() if isinstance(data, dict) else ""
    reason = str(data.get("reason", "")).strip() if isinstance(data, dict) else ""

    allowed_labels = set(valid_labels or get_profile().moves)
    if final not in allowed_labels:
        if strict:
            raise RuntimeError(f"冲突审核 GLM-5.2 返回非法标签: {final!r}")
        logger.warning("冲突审核返回非法标签 %r，回退 LLM 原判 %s", final, llm_label)
        return {"final_label": llm_label, "reason": f"审核返回非法标签，回退原判。{reason}"}

    return {"final_label": final, "reason": reason}


if __name__ == "__main__":
    # 不实际调用 GLM，仅打印 prompt 样例
    user = (
        "上下文（前后句）：\n已有研究表明，图神经网络能够处理非欧氏数据。\n\n"
        "待判定句子：已有研究表明，图神经网络能够处理非欧氏数据。\n\n"
        "模型原判：【研究结果】\n规则建议：【研究背景】\n"
        "规则证据：\n- 规则 MR-ZH-002 建议判【研究背景】（证据维度：['research_actor','evidence_type']，等级：soft）\n\n"
        "请裁定该句最终语步标签。"
    )
    print("=== 二次审核 user prompt 样例 ===")
    print(user)
