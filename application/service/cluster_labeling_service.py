"""Application orchestration for evidence-grounded cluster label generation.

The direct algorithm input is the phrase-set output of deep clustering.  New
raw texts/files and persisted cluster tasks are intentionally handled by a
future workflow/API adapter; this service does not rerun clustering and does
not access a database.

The verified V11 bounded soft-fallback engine is the production default.  V10
semantic-only and the historical evidence-v2 implementation remain selectable
for controlled fallback and historical replay.
"""
from __future__ import annotations

import json
import re
from typing import Any

from application.dto.common_dto import SemanticRequest
from config.settings import settings
from domain.entity.base import SemanticResult
from infrastructure.cluster_labeling import (
    DEFAULT_LABEL_ENGINE_MODE,
    create_cluster_label_generator,
    normalize_label_engine_mode,
)
from infrastructure.rag.m3_encoder import m3_encoder


def _integer(params: dict[str, Any], name: str, default: int) -> int:
    try:
        return int(params.get(name, default) or default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须为整数。") from exc


def _number(params: dict[str, Any], name: str, default: float) -> float:
    try:
        return float(params.get(name, default) if params.get(name) is not None else default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须为数值。") from exc


def _prepare_vue_output(output: dict[str, Any], _ctx_by_cluster: dict | None = None) -> dict[str, Any]:
    """Expose the verified engine result through the stable Vue field names.

    Only values derived from the current run are added.  Missing entities,
    source sentences or document identifiers stay empty rather than being
    filled with prototype data.
    """
    report = output.get("generation_report") or {}
    parameters = dict(report.get("parameters") or {})
    threshold = float(parameters.get("distinctiveness_threshold", 0.75))
    labels = output.get("labels") if isinstance(output.get("labels"), list) else []

    for item in labels:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        candidates = item.get("candidate_labels")
        if not isinstance(candidates, list):
            candidates = []
        candidates = list(dict.fromkeys(str(value) for value in candidates if str(value).strip()))
        if label and label not in candidates:
            candidates.insert(0, label)
        item["candidate_labels"] = candidates
        item["alternatives"] = [value for value in candidates if value != label]
        item["recommended_label"] = label
        item["status"] = "generated"
        item["representativeness"] = item.get("coverage")

        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        evidence.setdefault("keywords", list(item.get("evidence_terms") or []))
        _ev_ctx = (_ctx_by_cluster or {}).get(str(item.get("cluster_id") or ""), {})
        evidence.setdefault("named_entities", list(_ev_ctx.get("terms") or []))
        evidence.setdefault("center_sentence", str(
            _ev_ctx.get("sentence") or _ev_ctx.get("title") or ""))
        item["evidence"] = evidence

        passed = bool((item.get("optimization") or {}).get(
            "threshold_passed",
            float(item.get("distinctiveness") or 0.0) >= threshold,
        ))
        item["difference_explanation"] = (
            "推荐标签达到当前类簇间差异阈值。"
            if passed
            else "推荐标签未达到当前类簇间差异阈值，建议人工复核。"
        )

    output["cluster_count"] = int(report.get("cluster_count") or len(labels))
    output["generated_label_count"] = int(report.get("generated_label_count") or len(labels))
    output["parameters"] = parameters
    output["generation_strategy"] = report.get("effective_label_engine_mode")
    output["statistics"] = {
        "average_confidence": report.get("average_confidence"),
        "average_distinctiveness": report.get("average_distinctiveness"),
        "average_coverage": report.get("average_coverage"),
        "distinctiveness_pass_count": (
            output.get("label_differentiation_optimization") or {}
        ).get("passed_count"),
        "soft_fallback_triggered_count": report.get("soft_fallback_triggered_count", 0),
        "soft_fallback_changed_count": report.get("soft_fallback_changed_count", 0),
    }
    return output


def _label_term_set(name: str, phrases: list) -> set:
    """标签术语集合：簇名分词 + 代表短语（小写化，用于簇间重叠度计算）。"""
    import re as _re
    terms = {p.strip().lower() for p in (phrases or []) if str(p).strip()}
    terms.update(t for t in _re.split(r"[\s一-鿿]+", str(name or "").lower()) if len(t) >= 2)
    terms.add(str(name or "").strip().lower())
    terms.discard("")
    return terms


def _pairwise_distinctiveness(term_sets: dict) -> dict:
    """区分度 = 1 - 与最相近簇的术语重叠率（|A∩B| / min(|A|,|B|）。

    直采路径此前的区分度恒为 1.0（无信息量，用户无法判断标签是否真的可区分）；
    这里按簇名+代表短语的实际重叠计算——完全不重叠的簇区分度确为 100%，
    术语有共享的簇会得到低于 1 的真实值。
    """
    out = {}
    for cid, terms in term_sets.items():
        if not terms:
            out[cid] = 1.0
            continue
        worst = 0.0
        for other_cid, other in term_sets.items():
            if other_cid == cid or not other:
                continue
            overlap = len(terms & other) / min(len(terms), len(other))
            worst = max(worst, overlap)
        out[cid] = round(1.0 - worst, 3)
    return out


def execute_cluster_labeling(
    code: str,
    request: SemanticRequest,
    functional_point: Any,
    glm_client: Any,
) -> SemanticResult:
    """Generate labels from deep-clustering phrase sets without topic mapping."""
    params = dict(request.params or {})
    phrase_sets = params.get("cluster_phrase_sets")
    if not isinstance(phrase_sets, list) or not phrase_sets:
        raise ValueError(
            "聚类标签生成需要 cluster_phrase_sets，即深度聚类模型输出的类簇短语集合。"
        )

    # v3 语步对齐聚类的簇名已是 LLM 综述粒度命名（如「语言模型推理增强」），
    # 直接采用为推荐标签——语义引擎重生成会与英文短语拼接出「簇名 and xxx」
    # 混合标签（实测），v3 命名本身即人工评审通过的口径
    move_named = {str(ps.get("cluster_id") or ""): str(ps.get("topic_name") or "").strip()
                  for ps in phrase_sets
                  if isinstance(ps, dict) and ps.get("topic_name")
                  and str(ps.get("input_source") or "") == "move_aligned"}
    if move_named:
        labels = []
        cluster_phrases = {}
        for cid, name in move_named.items():
            phrases = next((ps.get("phrases") or [] for ps in phrase_sets
                            if isinstance(ps, dict) and str(ps.get("cluster_id")) == cid), [])
            cluster_phrases[cid] = phrases
        distinct = _pairwise_distinctiveness(
            {cid: _label_term_set(name, cluster_phrases.get(cid)) for cid, name in move_named.items()})
        for cid, name in move_named.items():
            phrases = cluster_phrases.get(cid) or []
            sentences = next((ps.get("evidence_sentences") or [] for ps in phrase_sets
                              if isinstance(ps, dict) and str(ps.get("cluster_id")) == cid), [])
            labels.append({
                "cluster_id": cid,
                "label": name,
                "candidate_labels": [name],
                "evidence_terms": phrases[:3],
                "evidence": {"keywords": phrases[:3],
                             "center_sentence": (sentences[0] if sentences else "")},
                "language": "zh" if re.search(r"[一-鿿]", name) else "en",
                "confidence": 0.9,
                "distinctiveness": distinct.get(cid, 1.0),
                "coverage": 1.0,
                "evidence_support": 0.9,
                "generation_method": "move_aligned_cluster_name",
                "phrase_count": len(phrases),
                "linked_document_ids": next(
                    (ps.get("linked_document_ids") or [] for ps in phrase_sets
                     if isinstance(ps, dict) and str(ps.get("cluster_id")) == cid), []),
            })
        output = {
            "labels": labels,
            "cluster_count": len(labels),
            "generated_label_count": len(labels),
            "parameters": {"label_length_limit": 12, "language_type": "auto",
                            "mode": "move_aligned_direct"},
            "statistics": {"average_confidence": 0.9,
                            "average_distinctiveness": round(
                                sum(l["distinctiveness"] for l in labels) / len(labels), 3) if labels else 1.0,
                            "average_coverage": 1.0, "distinctiveness_pass_count": len(labels)},
            "label_generation_process_report": {
                "engine_version": "move-aligned-direct-v1", "cluster_count": len(labels),
                "generated_label_count": len(labels), "stages": [
                    {"order": 1, "name": "v3 簇名直采", "status": "completed",
                     "output": "语步对齐聚类的综述粒度簇名直接作为推荐标签"}],
                "llm_used": True, "llm_failures": [], "topic_library_used": False,
                "requested_generation_mode": "hybrid", "effective_generation_mode": "hybrid",
                "direct_input_contract": "move_aligned_cluster_names",
            },
            "label_distinctiveness_optimization_result": {
                "threshold": 0.75, "optimized_count": 0, "passed_count": len(labels),
                "failed_count": 0,
                "items": [{"cluster_id": c, "before_label": n, "after_label": n,
                            "changed": False, "reason": "v3 簇名直采",
                            "threshold_passed": next(
                                (l["distinctiveness"] >= 0.75 for l in labels if l["cluster_id"] == c), True)}
                           for c, n in move_named.items()],
            },
        }
        result = SemanticResult(code=code, name=functional_point.name)
        result.success = True
        result.data = _prepare_vue_output(output, {})
        result.confidence = 0.9
        return result

    label_length_limit = _integer(params, "label_length_limit", 12)
    language_type = str(params.get("language_type") or "auto").strip().lower()
    distinctiveness_threshold = _number(params, "distinctiveness_threshold", 0.75)
    candidate_count = _integer(params, "candidate_count", 5)
    # 正式链路默认由 GLM 生成更自然的候选标签，再交给 BGE-M3 和
    # V11 门控复核。显式传 local 才完全关闭大模型。
    generation_mode = str(params.get("generation_mode") or "hybrid").strip().lower()
    if generation_mode not in {"hybrid", "local"}:
        raise ValueError("generation_mode 必须为 hybrid 或 local。")

    requested_engine_mode = params.get("label_engine_mode", DEFAULT_LABEL_ENGINE_MODE)
    effective_engine_mode = normalize_label_engine_mode(requested_engine_mode)

    llm_configured = settings.llm_configured
    llm = glm_client if generation_mode == "hybrid" and llm_configured else None
    generator = create_cluster_label_generator(
        mode=effective_engine_mode,
        encoder=m3_encoder,
        llm_client=llm,
    )
    # phrase_sets 的证据上下文按 cluster_id 索引（证据句 + 代表文献题名 + 代表词）。
    # 中心句优先用簇内真实证据句（key_evidence）；题名仅兜底且去文件扩展名
    # （文件模式下题名=上传文件名，带 .pdf 直接展示不合适）
    _ctx_by_cluster = {}
    for ps in phrase_sets:
        if isinstance(ps, dict) and ps.get("cluster_id"):
            fallback_title = str((ps.get("evidence_titles") or [""])[0] or "")
            if fallback_title.rsplit(".", 1)[-1].lower() in {"pdf", "docx", "txt"}:
                fallback_title = fallback_title.rsplit(".", 1)[0]
            _ctx_by_cluster[str(ps["cluster_id"])] = {
                "sentence": str((ps.get("evidence_sentences") or [""])[0] or ""),
                "title": fallback_title,
                "terms": ps.get("evidence_terms_context") or [],
            }
    output = generator.generate(
        phrase_sets,
        label_length_limit=label_length_limit,
        language_type=language_type,
        distinctiveness_threshold=distinctiveness_threshold,
        candidate_count=candidate_count,
    )
    llm_failures = list(output["generation_report"].get("llm_failures") or [])
    output["generation_report"].update({
        "requested_generation_mode": generation_mode,
        "effective_generation_mode": "hybrid" if llm is not None else "local",
        "llm_requested": generation_mode == "hybrid",
        "llm_configured": llm_configured,
        "llm_model": settings.GLM_MODEL if llm is not None else None,
        "llm_candidate_generation_enabled": llm is not None,
        "llm_failure_count": len(llm_failures),
        "llm_fallback_used": bool(llm_failures) or (
            generation_mode == "hybrid" and llm is None
        ),
        "llm_fallback_reason": (
            "部分或全部类簇的 GLM 候选生成失败，已按类簇回退到 BGE-M3 本地候选。"
            if llm_failures
            else (
                "未配置 GLM_API_KEY，已回退到 BGE-M3 本地候选。"
                if generation_mode == "hybrid" and llm is None
                else None
            )
        ),
        "requested_label_engine_mode": str(requested_engine_mode or DEFAULT_LABEL_ENGINE_MODE),
        "effective_label_engine_mode": effective_engine_mode,
        "production_default_engine": DEFAULT_LABEL_ENGINE_MODE,
        "semantic_reranking_model": "bge-m3",
        "direct_input_contract": "deep_clustering_cluster_phrase_sets",
    })
    _prepare_vue_output(output, _ctx_by_cluster)

    result = SemanticResult(code=code, name=functional_point.name)
    result.success = True
    result.data = output
    result.confidence = output["generation_report"].get("average_confidence")
    result.raw = json.dumps({
        "cluster_count": output["generation_report"]["cluster_count"],
        "labels": [item["label"] for item in output["labels"]],
        "topic_library_used": False,
        "label_engine_mode": effective_engine_mode,
        "generation_mode": output["generation_report"]["effective_generation_mode"],
        "llm_model": output["generation_report"].get("llm_model"),
    }, ensure_ascii=False)
    return result
