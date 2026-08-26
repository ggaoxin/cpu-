"""GLM 自动审核候选主题（四层判断，替代人工）。

四层：
① 语义相似度阈值：新提案名 vs 现有主题名，>=阈值 → 归已有（use_existing）
② <阈值 → GLM 判断是否真新主题（accept）或可能重复
③ GLM 认为可能重复 → GLM 从已有主题列表挑最像的（use_existing）
④ 都不确定 → pending_review（记录，等人工加，不自动）

decision 取值：
- accept：真新主题，入库
- use_existing：与已有重复，归入已有主题（final_name=已有名）
- pending：不确定，待人工审核
"""
from __future__ import annotations

from difflib import SequenceMatcher

from infrastructure.llm.glm_client import glm_client

REVIEW_SYSP = """你是科技文献主题聚类审核专家。审核一个候选主题提案。

看代表性文献+证据关键词+同父类已有主题列表，判断：
1. accept：真新主题（边界清晰、代表性文献同类、不与已有重复）。final_name 用提案名或更专业的改名。
2. use_existing：与已有主题重复。existing_match 给出最像的已有主题名，final_name=该已有名。
3. pending：不确定（边界模糊，或无法判断是否与已有重复）。标记待人工审核。

输出JSON：{"data":{"decision":"accept|use_existing|pending","final_name":"主题名","existing_match":"已有主题名或空","reason":"简短理由"}}
"""


def _name_sim(a: str, b: str) -> float:
    """两个主题名的字符相似度（0-1）。"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_similar_topic(proposal_name: str, existing_names: list, threshold: float = 0.6):
    """步骤①：在现有主题名里找最相似的。返回 (best_name, sim)。"""
    best, best_sim = None, 0.0
    for n in existing_names:
        s = _name_sim(proposal_name, n)
        if s > best_sim:
            best, best_sim = n, s
    return best, best_sim


def review_proposal(proposal: dict, existing_topic_names: list,
                    prototype_abstracts: list | None = None,
                    sim_threshold: float = 0.6) -> dict:
    """四层审核候选主题提案。

    Returns: {decision, final_name, reason, existing_match, sim}
        decision: accept（新主题入库）/ use_existing（归已有）/ pending（待人工）
    """
    proposed_name = proposal.get("proposed_name", "")

    # ① 相似度阈值：新提案名 vs 现有主题名
    if existing_topic_names:
        best, sim = find_similar_topic(proposed_name, existing_topic_names, sim_threshold)
        if sim >= sim_threshold:
            return {"decision": "use_existing", "final_name": best,
                    "reason": f"与已有主题'{best}'相似度{sim:.2f}≥{sim_threshold}，归入已有",
                    "existing_match": best, "sim": round(sim, 2)}

    # ②③ GLM 判断 + 查表
    docs = prototype_abstracts or []
    user = (
        f"候选主题：{proposed_name}\n"
        f"轴：{proposal.get('axis', '')}  父类：{proposal.get('parent_category_id', '')}  "
        f"语言：{proposal.get('language', '')}\n"
        f"支持文献数：{proposal.get('support_count', 0)}\n"
        f"证据关键词：{proposal.get('positive_evidence', [])}\n"
        f"同父类已有主题：{existing_topic_names}\n"
        f"代表性文献标题：{proposal.get('prototype_titles', [])}\n"
        f"代表性文献摘要：{docs}"
    )
    try:
        d = glm_client.chat_json(REVIEW_SYSP, user, timeout=60.0, max_tokens=200, temperature=0.0)
        d = d.get("data", d) if isinstance(d, dict) else {}
        decision = (d.get("decision") or "pending").strip()
        if decision not in ("accept", "use_existing", "pending"):
            decision = "pending"
        final_name = (d.get("final_name") or proposed_name).strip()
        existing_match = (d.get("existing_match") or "").strip()
        reason = (d.get("reason") or "").strip()
        return {"decision": decision, "final_name": final_name, "reason": reason,
                "existing_match": existing_match, "sim": 0.0}
    except Exception as e:  # noqa: BLE001
        return {"decision": "pending", "final_name": proposed_name, "reason": f"GLM审核异常: {e}",
                "existing_match": "", "sim": 0.0}
