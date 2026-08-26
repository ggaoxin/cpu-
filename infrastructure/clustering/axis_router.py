"""Route the user-selected semantic axis to its most suitable engine."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np

from infrastructure.clustering.application_dense import (
    build_core3_representation,
    load_application_config,
    cluster_application_dense,
    materialize_application_representation,
    prepare_application_features,
)
from infrastructure.clustering.bge_m3_sparse import BgeM3SparseEncoder, cluster_technical_sparse
from infrastructure.clustering.evidence_rule_engine import (
    adaptive_semantic_weights,
    augment_axis_views,
    blend_dense_semantic_representations,
    blend_sparse_semantic_features,
    EvidenceRuleEngine,
    merge_application_rule_facets,
)
from infrastructure.clustering.dual_axis_cluster import (
    build_dual_views,
    normalize_papers,
    _sentences,
    _view_text,
)
from infrastructure.clustering.input_representation import source_groups, split_keywords


def _technical_focused_source_groups(
    paper: dict[str, Any],
    groups: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Focus every weighted source independently before sparse fusion."""
    focused: list[dict[str, Any]] = []
    for group in groups:
        label = str(group.get("label") or "text")
        source_text = str(group.get("source_text") or "")
        temporary = {
            **paper,
            "semantic_title": source_text if label == "title" else "",
            "semantic_text": source_text,
            "keywords": split_keywords(source_text) if label == "keywords" else [],
        }
        view, _ = _view_text(temporary, "technical")
        focused.append({**group, "source_text": view or source_text})
    return focused


def run_selected_axis_clustering(
    items: Sequence[dict[str, Any] | str],
    dense_encoder: Any,
    *,
    selected_axis: str,
    model_path: Path,
    application_extractor: Any | None = None,
    technical_extractor: Any | None = None,
    algorithm: str = "auto",
    cluster_count: int | None = None,
    min_cluster_size: int = 2,
    similarity_threshold: float | None = None,
    random_state: int = 42,
    rule_mode: str = "off",
    rule_path: Path | None = None,
    technical_rule_weight: float = 0.12,
    technical_rule_policy: str = "fallback_only",
    application_rule_weight: float = 0.16,
    application_rule_policy: str = "fallback_only",
) -> dict[str, Any]:
    """Execute only the axis selected by the Vue request."""
    axis = "application" if selected_axis in {"application", "application_scenario"} else "technical"
    papers = normalize_papers(items)
    if not papers:
        raise ValueError("At least one scientific document is required.")
    local_tech, local_app, local_tech_evidence, local_app_evidence = build_dual_views(papers)
    selected_source_groups = [source_groups(paper, axis) for paper in papers]
    weighted_axis_groups = (
        [_technical_focused_source_groups(paper, groups) for paper, groups in zip(papers, selected_source_groups)]
        if axis == "technical" else selected_source_groups
    )
    for paper, groups in zip(papers, selected_source_groups):
        audit = paper["input_representation"]
        audit["selected_axis"] = axis
        audit["source_groups"] = [
            {"label": group["label"], "weight": round(float(group["weight"]), 6),
             "text_length": len(str(group["source_text"]))}
            for group in groups
        ]
        audit["chunk_count"] = len(groups) if audit["mode"] == "plain_text" else None
        audit["selected_chunk_count"] = len(groups) if audit["mode"] == "plain_text" else None
        audit["field_weights"] = (
            {group["label"]: round(float(group["weight"]), 6) for group in groups}
            if audit["mode"] == "structured" else None
        )
    normalized_rule_mode = str(rule_mode or "off").strip().lower()
    if normalized_rule_mode not in {"off", "audit", "enhance"}:
        raise ValueError("rule_mode must be off, audit, or enhance")
    normalized_rule_policy = str(application_rule_policy or "fallback_only").strip().lower()
    if normalized_rule_policy not in {"fallback_only", "all"}:
        raise ValueError("application_rule_policy must be fallback_only or all")
    normalized_technical_rule_policy = str(technical_rule_policy or "fallback_only").strip().lower()
    if normalized_technical_rule_policy not in {"fallback_only", "all"}:
        raise ValueError("technical_rule_policy must be fallback_only or all")
    rule_batch = None
    rule_metadata: dict[str, Any] = {
        "mode": normalized_rule_mode,
        "enabled": normalized_rule_mode != "off",
        "affects_clustering": normalized_rule_mode == "enhance",
        "topic_library_used": False,
        "rules_assign_cluster_membership": False,
        "application_rule_policy": normalized_rule_policy,
        "technical_rule_policy": normalized_technical_rule_policy,
    }
    if normalized_rule_mode != "off":
        if rule_path is None:
            rule_path = Path(__file__).resolve().parents[2] / "rules" / "deep_clustering" / "evidence_rules_v1.json"
        rule_batch = EvidenceRuleEngine(rule_path).apply(papers)
        rule_metadata.update(rule_batch.summary())
        rule_metadata["documents"] = [
            rule_batch.document_audit(index) for index in range(len(papers))
        ]

    if axis == "technical":
        if technical_extractor is not None:
            extracted = technical_extractor.extract(
                papers,
                local_technical_views=local_tech,
                local_application_views=local_app,
                local_technical_evidence=local_tech_evidence,
                local_application_evidence=local_app_evidence,
            )
            technical_views = extracted.technical_views
            technical_evidence = extracted.technical_evidence
            extraction = extracted.metadata
        else:
            technical_views = local_tech
            technical_evidence = local_tech_evidence
            extraction = {
                "mode": "local_sparse_axis_view",
                "required_axes": ["technical"],
                "document_count": len(papers),
                "verified_document_count": 0,
                "fallback_document_count": 0,
                "local_document_count": len(papers),
                "llm_used": False,
                "llm_assigns_cluster_membership": False,
                "topic_library_used": False,
                "document_sources": ["local"] * len(papers),
            }
        sparse_encoder = BgeM3SparseEncoder(dense_encoder, model_path)
        sparse_matrix = sparse_encoder.encode_weighted_documents(weighted_axis_groups)
        if normalized_rule_mode == "enhance" and rule_batch is not None:
            document_sources = extraction.get("document_sources") or ["local"] * len(papers)
            rule_active = [
                bool(rule_batch.technical_terms(index, papers[index]["language"]))
                and (
                    normalized_technical_rule_policy == "all"
                    or document_sources[index] != "llm_verified"
                )
                for index in range(len(papers))
            ]
            augmented_tech = augment_axis_views(
                technical_views, papers, rule_batch, axis="technical", active_mask=rule_active,
            )
            augmented_sparse = sparse_encoder.encode(augmented_tech)
            effective_weights, input_profiles = adaptive_semantic_weights(
                papers, technical_rule_weight, maximum=0.40, active_mask=rule_active,
            )
            sparse_matrix = blend_sparse_semantic_features(
                sparse_matrix, augmented_sparse,
                rule_weight=effective_weights,
                active_mask=rule_active,
            )
            technical_evidence = [
                list(dict.fromkeys(technical_evidence[index] + rule_batch.evidence(index, "technical")))[:5]
                for index in range(len(papers))
            ]
            rule_metadata["input_evidence_profiles"] = input_profiles
            rule_metadata["effective_document_weights"] = [round(float(value), 6) for value in effective_weights]
        selected = cluster_technical_sparse(
            sparse_matrix, papers, technical_views, technical_evidence,
            algorithm=algorithm, cluster_count=cluster_count,
            min_cluster_size=min_cluster_size, similarity_threshold=similarity_threshold,
            random_state=random_state,
        )
        representation = sparse_encoder.metadata()
        if normalized_rule_mode == "enhance":
            representation.update({
                "representation": "bge-m3-native-sparse-plus-evidence-rules",
                "rule_feature_weight": round(float(max(0.0, min(technical_rule_weight, 0.40))), 6),
                "fusion": "original_bge_sparse_plus_rule_expanded_bge_sparse",
                "rule_id_affinity_used": False,
                "adaptive_weighting": "input_completeness_only",
                "rule_policy": normalized_technical_rule_policy,
            })
            selected["quality"]["representation"] = representation["representation"]
    else:
        if application_extractor is not None:
            extracted = application_extractor.extract(
                papers,
                local_technical_views=local_tech,
                local_application_views=local_app,
                local_technical_evidence=local_tech_evidence,
                local_application_evidence=local_app_evidence,
            )
            views = extracted.application_views
            evidence = extracted.application_evidence
            facets = extracted.application_facets
            extraction = extracted.metadata
        else:
            views = local_app
            evidence = local_app_evidence
            facets = [
                {"domain": [], "object": [], "problem": [], "task": [], "environment": [], "general": [view]}
                for view in views
            ]
            extraction = {
                "mode": "local_fallback",
                "required_axes": ["application"],
                "document_count": len(papers),
                "verified_document_count": 0,
                "fallback_document_count": len(papers),
                "llm_used": False,
                "llm_assigns_cluster_membership": False,
                "topic_library_used": False,
            }
        application_rule_active = np.zeros(len(papers), dtype=np.float32)
        original_facets = facets
        if normalized_rule_mode == "enhance" and rule_batch is not None:
            document_sources = extraction.get("document_sources") or ["local_fallback"] * len(papers)
            for index, row in enumerate(facets):
                core_count = sum(bool(row.get(name)) for name in ("domain", "object", "problem"))
                fallback = document_sources[index] != "llm_verified"
                rule_context_valid = rule_batch.application_context_strength(index)["eligible_for_semantic_expansion"]
                application_rule_active[index] = float(
                    rule_context_valid
                    and (normalized_rule_policy == "all" or fallback or core_count < 2)
                )
            facets = merge_application_rule_facets(
                facets, papers, rule_batch, fill_only=True,
                active_mask=application_rule_active,
            )
            evidence = [
                list(dict.fromkeys(
                    list(evidence[index])
                    + (rule_batch.evidence(index, "application") if application_rule_active[index] else [])
                ))[:5]
                for index in range(len(papers))
            ]
            effective_application_weights, input_profiles = adaptive_semantic_weights(
                papers,
                application_rule_weight,
                maximum=0.35,
                active_mask=application_rule_active,
            )
            rule_metadata["input_evidence_profiles"] = input_profiles
            rule_metadata["effective_document_weights"] = [
                round(float(value), 6) for value in effective_application_weights
            ]
        config = load_application_config()
        base_matrix, base_affinity, base_representation = build_core3_representation(
            dense_encoder, views, original_facets, source_groups_by_document=weighted_axis_groups,
        )
        matrix, affinity, representation = build_core3_representation(
            dense_encoder, views, facets, source_groups_by_document=weighted_axis_groups,
        )
        if normalized_rule_mode == "enhance" and rule_batch is not None:
            matrix, affinity = blend_dense_semantic_representations(
                base_matrix, matrix, base_affinity, affinity,
                rule_weight=effective_application_weights,
                active_mask=application_rule_active,
            )
            representation.update({
                "representation": "bge-m3-application-core3-rule-expanded-semantic-space",
                "rule_semantic_weight": round(float(max(0.0, min(application_rule_weight, 0.35))), 6),
                "rule_policy": normalized_rule_policy,
                "rule_active_document_count": int(application_rule_active.sum()),
                "rule_id_affinity_used": False,
                "fusion": "original_bge_application_space_plus_rule_expanded_bge_application_space",
                "adaptive_weighting": "input_completeness_only",
            })
        else:
            matrix, affinity, representation = base_matrix, base_affinity, base_representation
        representation["profile_name"] = "core3_domain_object_problem"
        representation["selected_on"] = config["selected_on"]
        selected = cluster_application_dense(
            matrix, papers, views, evidence,
            affinity=affinity, representation=representation,
            algorithm=algorithm, cluster_count=cluster_count,
            min_cluster_size=min_cluster_size, similarity_threshold=similarity_threshold,
            random_state=random_state, configured_method=config["clustering_method"],
            graph_neighbors=config["graph_neighbors"],
        )

    return {
        "papers": papers,
        "selected_axis": axis,
        "selected": selected,
        "axis_extraction": extraction,
        "representation": representation,
        "rule_evidence": rule_metadata,
        "technical": selected if axis == "technical" else None,
        "application": selected if axis == "application" else None,
        # 技术轴判 k 校准用：返回算法实际聚类的 axis views（全文按技术 cue 浓缩），
        # 供 service 层喂 GLM 判簇数——论文/基金/报告通用，不依赖 abstract/keywords。
        "axis_views": technical_views if axis == "technical" else views,
        "parsed_sentence_count": sum(len(_sentences(paper["semantic_text"])) for paper in papers),
    }
