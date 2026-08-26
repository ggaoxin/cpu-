from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

from infrastructure.clustering.evidence_rule_engine import (
    adaptive_semantic_weights,
    EvidenceRuleEngine,
    fuse_sparse_rule_features,
    merge_application_rule_facets,
)


RULE_PATH = Path(__file__).resolve().parents[1] / "rules" / "deep_clustering" / "evidence_rules_v1.json"


def _paper(document_id: str, title: str, abstract: str, keywords=None):
    return {
        "document_id": document_id,
        "title": title,
        "abstract": abstract,
        "keywords": keywords or [],
        "language": "zh",
    }


def test_rules_extract_evidence_but_never_membership_fields():
    payload = json.loads(RULE_PATH.read_text(encoding="utf-8"))
    assert payload["can_assign_cluster_membership"] is False
    forbidden = {"cluster_id", "class_id", "gold_label", "target_k"}
    assert not any(forbidden & set(row) for row in payload["rules"])
    engine = EvidenceRuleEngine(RULE_PATH)
    batch = engine.apply([_paper(
        "D1",
        "基于Transformer的电网故障诊断",
        "本文采用Transformer多头注意力模型，用于配电网故障诊断。",
        ["Transformer", "配电网", "故障诊断"],
    )])
    audit = batch.document_audit(0)
    ids = {row["rule_id"] for row in audit["hits"]}
    assert "tech_transformer" in ids
    assert "app_power_grid" in ids
    assert "app_fault" in ids
    assert all(row["evidence"] for row in audit["hits"])
    assert batch.summary()["rules_assign_cluster_membership"] is False


def test_negated_or_related_work_technical_mentions_are_not_adopted():
    engine = EvidenceRuleEngine(RULE_PATH)
    related = _paper(
        "D2", "传统回归分析研究",
        "相关工作采用Transformer模型。本文使用线性回归分析影响因素。",
    )
    negated = _paper(
        "D3", "临床风险研究",
        "本研究未采用卷积神经网络，而是使用逻辑回归预测临床风险。",
    )
    batch = engine.apply([related, negated])
    related_ids = {hit.rule_id for hit in batch.hits_by_document[0]}
    negated_ids = {hit.rule_id for hit in batch.hits_by_document[1]}
    assert "tech_transformer" not in related_ids
    assert "tech_cnn" not in negated_ids
    assert "tech_regression" in related_ids | negated_ids


def test_rule_feature_fusion_is_bounded_and_row_adaptive():
    base = csr_matrix(np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
    augmented = csr_matrix(np.asarray([[0.8, 0.2], [0.0, 1.0]], dtype=np.float32))
    fused = fuse_sparse_rule_features(
        base, augmented, rule_weight=0.20, active_mask=[True, False]
    ).toarray()
    assert fused.shape == (2, 4)
    assert np.allclose(np.linalg.norm(fused, axis=1), 1.0)
    assert fused[0, 2] > 0
    assert fused[1, 2] == 0
    assert np.allclose(fused[1, :2], base.toarray()[1])


def test_application_rules_fill_missing_facets_only_for_active_rows():
    engine = EvidenceRuleEngine(RULE_PATH)
    papers = [
        _paper("D4", "水稻精准农业监测", "用于水稻精准农业实时监测。", ["水稻", "精准农业"]),
        _paper("D5", "电网故障诊断", "面向配电网开展故障诊断。", ["配电网", "故障诊断"]),
    ]
    batch = engine.apply(papers)
    facets = [
        {"domain": [], "object": [], "problem": [], "task": [], "environment": [], "general": []},
        {"domain": ["大模型已验证领域"], "object": [], "problem": [], "task": [], "environment": [], "general": []},
    ]
    merged = merge_application_rule_facets(
        facets, papers, batch, fill_only=True, active_mask=[True, False],
    )
    assert merged[0]["domain"] or merged[0]["object"]
    assert merged[1]["domain"] == ["大模型已验证领域"]
    assert not merged[1]["problem"]


def test_single_broad_application_hit_cannot_expand_semantic_space():
    engine = EvidenceRuleEngine(RULE_PATH)
    batch = engine.apply([_paper(
        "D6", "癌症相关研究", "本文讨论癌症的分子机制。", ["癌症"]
    )])
    strength = batch.application_context_strength(0)
    assert strength["distinct_facet_count"] == 1
    assert strength["eligible_for_semantic_expansion"] is False
    assert not any(batch.application_facets(0, "zh").values())


def test_full_text_inputs_receive_less_semantic_expansion_weight():
    papers = [
        {
            **_paper("D7", "简短题录", "采用图神经网络开展设备故障诊断。", ["图神经网络"]),
            "full_text": "",
        },
        {
            **_paper("D8", "完整论文", "采用图神经网络开展设备故障诊断。", ["图神经网络"]),
            "full_text": "完整实验方法与应用证据。" * 150,
        },
    ]
    weights, profiles = adaptive_semantic_weights(
        papers, 0.20, maximum=0.40, active_mask=[True, True],
    )
    assert profiles[0]["level"] == "brief_text_record"
    assert profiles[1]["level"] == "full_text"
    assert weights[0] == np.float32(0.20)
    assert weights[1] < weights[0]


def test_per_document_sparse_weights_are_supported():
    base = csr_matrix(np.eye(2, dtype=np.float32))
    augmented = csr_matrix(np.asarray([[0.8, 0.2], [0.2, 0.8]], dtype=np.float32))
    fused = fuse_sparse_rule_features(
        base, augmented, rule_weight=[0.20, 0.05], active_mask=[True, True]
    ).toarray()
    assert fused.shape == (2, 4)
    assert fused[0, 2] > fused[1, 2]
