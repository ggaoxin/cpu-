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


def _prepare_vue_output(output: dict[str, Any]) -> dict[str, Any]:
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
        evidence.setdefault("named_entities", [])
        evidence.setdefault("center_sentence", "")
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
    _prepare_vue_output(output)

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
