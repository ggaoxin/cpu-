from __future__ import annotations

import json
from unittest.mock import patch

import numpy as np

from application.dto.common_dto import SemanticRequest
from application.service import deep_clustering_service


class _FunctionalPoint:
    name = "科技文本深度聚类"


class _LocalDenseEncoder:
    """Deterministic local stand-in; production still uses the existing BGE-M3."""

    def encode(self, texts):
        rows = []
        for index, text in enumerate(texts):
            value = str(text).casefold()
            if any(term in value for term in ("clinical", "patient", "医疗", "患者")):
                row = [1.0, 0.05, 0.02, index * 0.001]
            elif any(term in value for term in ("industrial", "bearing", "工业", "轴承")):
                row = [0.04, 1.0, 0.03, index * 0.001]
            else:
                row = [0.02, 0.04, 1.0, index * 0.001]
            rows.append(row)
        return np.asarray(rows, dtype=np.float32)


def test_application_route_runs_without_glm_and_reports_local_fallback():
    documents = [
        {"id": "M1", "publication_date": "2024-01-01", "text": "Clinical patient risk prediction."},
        {"id": "M2", "publication_date": "2024-02-01", "text": "Medical patient outcome prediction."},
        {"id": "I1", "publication_date": "2024-03-01", "text": "Industrial bearing fault diagnosis."},
        {"id": "I2", "publication_date": "2024-04-01", "text": "Industrial bearing defect detection."},
        {"id": "A1", "publication_date": "2024-05-01", "text": "Agricultural crop disease monitoring."},
        {"id": "A2", "publication_date": "2024-06-01", "text": "Agricultural crop health monitoring."},
    ]
    request = SemanticRequest(
        texts=[json.dumps(item, ensure_ascii=False) for item in documents],
        params={
            "cluster_dimension": "application_scenario",
            "algorithm": "auto",
            "axis_extraction": "local",
            "rule_mode": "off",
        },
    )
    with patch.object(deep_clustering_service, "m3_encoder", _LocalDenseEncoder()):
        response = deep_clustering_service.execute_deep_clustering(
            "dc_cluster", request, _FunctionalPoint(), glm_client=None,
        )
    assert response.success is True
    assert response.data["technical_topics"] == []
    assert response.data["application_topics"]
    assert response.data["algorithm_metadata"]["selected_axis"] == "application"
    assert response.data["algorithm_metadata"]["topic_library_used"] is False
    assert response.data["axis_extraction"]["mode"] == "local_fallback"
    assert response.data["documents"][0]["publication_year"] == 2024


def test_mixed_structured_and_plain_text_inputs_return_auditable_modes_and_trend():
    structured = (
        "标题：工业轴承故障诊断\n"
        "摘要：本文面向制造装备轴承运维，采用图神经网络与振动信号融合方法完成故障诊断，"
        "并解决复杂工况下的设备异常检测问题。\n"
        "关键词：工业轴承；故障诊断；图神经网络"
    )
    documents = [
        {"id": "S1", "publication_date": "2023-01-01", "text": structured},
        {"id": "S2", "publication_date": "2023-02-01", "text": structured},
        {"id": "R1", "publication_date": "2024-01-01", "text": "科研报告采用有限元分析评估桥梁疲劳寿命。"},
        {"id": "R2", "publication_date": "2024-02-01", "text": "项目报告利用有限元仿真分析桥梁结构疲劳损伤。"},
    ]
    request = SemanticRequest(
        texts=[json.dumps(item, ensure_ascii=False) for item in documents],
        params={"cluster_dimension": "technology", "algorithm": "auto", "cluster_count": 2,
                "axis_extraction": "local", "rule_mode": "off"},
    )
    with patch.object(deep_clustering_service, "m3_encoder", _LocalDenseEncoder()), \
            patch("infrastructure.clustering.axis_router.BgeM3SparseEncoder") as sparse_cls:
        from scipy.sparse import csr_matrix

        sparse = sparse_cls.return_value
        sparse.encode_weighted_documents.return_value = csr_matrix([
            [1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9],
        ])
        sparse.metadata.return_value = {"representation": "test-sparse"}
        response = deep_clustering_service.execute_deep_clustering(
            "dc_cluster", request, _FunctionalPoint(), glm_client=None,
        )
    modes = [item["input_representation"]["mode"] for item in response.data["documents"]]
    assert modes == ["structured", "structured", "plain_text", "plain_text"]
    assert response.data["input_summary"]["structured_document_count"] == 2
    assert response.data["input_summary"]["plain_text_document_count"] == 2
    assert response.data["theme_trend_analysis"]["years"] == [2023, 2024]
    assert all(item["publication_date"] for item in response.data["document_assignments"])
    assert all(item["input_representation"] for item in response.data["document_assignments"])
