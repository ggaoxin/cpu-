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
    # v3 语步对齐双轴聚类契约（2026-09-08 更新断言）：无 GLM 时走本地回退，
    # algorithm_used 标记 move_vector_fallback；clusters/semantic_projection 仍产出
    # （前端可视化不空），代表词留空（代表词需 LLM）。
    assert response.success is True
    assert response.data["clusters"], "本地回退仍应产出聚类"
    assert response.data["clustering_quality"]["algorithm_used"] == "move_vector_fallback"
    assert response.data["clustering_quality"]["cluster_count"] >= 2
    projection = response.data["semantic_projection"]
    assert projection and all({"x", "y", "document_id"} <= set(item) for item in projection)
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
    # v3 统一语步对齐表示（2026-09-08 更新断言）：不再区分 structured/plain_text，
    # 全部走 move_aligned 模式；文档数与趋势年份仍可审计。
    modes = [item["input_representation"]["mode"] for item in response.data["documents"]]
    assert modes == ["move_aligned"] * 4
    assert response.data["input_summary"]["document_count"] == 4
    assert response.data["theme_trend_analysis"]["years"] == [2023, 2024]
    assert all(item["publication_date"] for item in response.data["document_assignments"])


_EXPLICIT_ALGORITHM_DOCUMENTS = [
    {"id": "M1", "title": "临床患者风险预测", "publication_date": "2024-01-01",
     "text": "Clinical patient risk prediction for hospital care."},
    {"id": "M2", "title": "医疗患者结局预后研究", "publication_date": "2024-02-01",
     "text": "Medical patient outcome modeling study."},
    {"id": "I1", "title": "工业轴承故障诊断方法", "publication_date": "2024-03-01",
     "text": "Industrial bearing fault diagnosis approach."},
    {"id": "I2", "title": "工业轴承缺陷检测技术", "publication_date": "2024-04-01",
     "text": "Industrial bearing defect detection technique."},
    {"id": "A1", "title": "农业作物病害监测系统", "publication_date": "2024-05-01",
     "text": "Agricultural crop disease monitoring system."},
    {"id": "A2", "title": "农业作物长势遥感监测", "publication_date": "2024-06-01",
     "text": "Agricultural crop health remote sensing."},
]


def _run_explicit_algorithm(algorithm: str, cluster_count=None):
    params = {"cluster_dimension": "technology", "algorithm": algorithm}
    if cluster_count is not None:
        params["cluster_count"] = cluster_count
    request = SemanticRequest(
        texts=[json.dumps(item, ensure_ascii=False) for item in _EXPLICIT_ALGORITHM_DOCUMENTS],
        params=params,
    )
    with patch.object(deep_clustering_service, "m3_encoder", _LocalDenseEncoder()):
        return deep_clustering_service.execute_deep_clustering(
            "dc_cluster", request, _FunctionalPoint(), glm_client=None,
        )


def test_explicit_kmeans_algorithm_uses_vector_path():
    # 2026-10-09 起显式算法真实生效：非 auto 跳过 LLM 语义分组，走轴句向量 +
    # 所选算法（glm 缺失不受影响——向量路径不调 LLM 分组，题名兜底特征）。
    response = _run_explicit_algorithm("kmeans")
    assert response.success is True
    assert response.data["clustering_quality"]["algorithm_requested"] == "kmeans"
    assert response.data["clustering_quality"]["algorithm_used"] == "vector_kmeans"
    # 局部编码器三主题两两成组：自动 k（轮廓系数搜索）应得 3 簇
    assert response.data["clustering_quality"]["cluster_count"] == 3
    assert sum(c["size"] for c in response.data["clusters"]) == 6


def test_explicit_kmeans_respects_exact_cluster_count():
    # 向量算法路径 cluster_count 为精确簇数（kmeans k=2 → 恰 2 簇，区别于
    # auto/LLM 路径的 ±1 软约束）
    response = _run_explicit_algorithm("kmeans", cluster_count=2)
    assert response.success is True
    assert response.data["clustering_quality"]["algorithm_used"] == "vector_kmeans"
    assert response.data["clustering_quality"]["cluster_count"] == 2
    assert sum(c["size"] for c in response.data["clusters"]) == 6


def test_explicit_hdbscan_and_spectral_algorithms_produce_clusters():
    # hdbscan 无 k 参数（密度聚类，噪声点并入最近簇）；spectral 用余弦亲和矩阵
    # ——两者均应成功产出全覆盖分组并标记真实算法
    for algorithm in ("hdbscan", "spectral"):
        response = _run_explicit_algorithm(algorithm)
        assert response.success is True, algorithm
        assert response.data["clustering_quality"]["algorithm_used"] == f"vector_{algorithm}"
        assert response.data["clusters"], algorithm
        assert sum(c["size"] for c in response.data["clusters"]) == 6, algorithm
