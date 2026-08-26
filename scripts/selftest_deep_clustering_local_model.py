"""Run both production clustering routes with the bundled local BGE-M3 model.

This is an integration smoke test, not a benchmark.  It deliberately forces
``axis_extraction=local`` so no GLM request or API key is used.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.dto.common_dto import SemanticRequest
from application.service.deep_clustering_service import execute_deep_clustering


class _FunctionalPoint:
    name = "科技文本深度聚类"


TECHNICAL_DOCUMENTS = [
    {"id": "T01", "publication_date": "2023-01-01", "text": "Title: Transformer temporal modelling\nAbstract: A Transformer with multi-head attention models long-range temporal dependencies and learns sequence representations for robust forecasting experiments.\nKeywords: Transformer; multi-head attention; temporal modelling"},
    {"id": "T02", "publication_date": "2023-02-01", "text": "Title: Self-attention sequence representation\nAbstract: The method uses self-attention and a Transformer encoder to learn long sequence representations and evaluates the proposed technical pipeline in controlled experiments.\nKeywords: self-attention; Transformer encoder; sequence representation"},
    {"id": "T03", "publication_date": "2023-03-01", "text": "Finite element analysis and structural simulation estimate fatigue damage."},
    {"id": "T04", "publication_date": "2023-04-01", "text": "A finite-element numerical model simulates stress and crack propagation."},
    {"id": "T05", "publication_date": "2023-05-01", "text": "Graph neural networks aggregate neighbourhood messages for representation learning."},
    {"id": "T06", "publication_date": "2023-06-01", "text": "A graph convolutional network performs message passing over connected nodes."},
]

APPLICATION_DOCUMENTS = [
    {"id": "A01", "publication_date": "2024-01-01", "text": "Title: Clinical deterioration prediction\nAbstract: The system predicts clinical deterioration for hospital patients and supports early intervention for high-risk inpatient care.\nKeywords: hospital patients; clinical deterioration; risk prediction"},
    {"id": "A02", "publication_date": "2024-02-01", "text": "Title: Hospital patient risk assessment\nAbstract: Hospital patient risk prediction supports clinical decision making and identifies deterioration in inpatient healthcare environments.\nKeywords: clinical decision; patient risk; hospital care"},
    {"id": "A03", "publication_date": "2024-03-01", "text": "The system detects industrial bearing faults in manufacturing equipment."},
    {"id": "A04", "publication_date": "2024-04-01", "text": "Industrial bearing defect detection supports factory maintenance."},
    {"id": "A05", "publication_date": "2024-05-01", "text": "Crop disease monitoring supports agricultural production management."},
    {"id": "A06", "publication_date": "2024-06-01", "text": "Agricultural crop health monitoring identifies field disease risk."},
]


def _run(axis: str, documents: list[dict]) -> dict:
    request = SemanticRequest(
        texts=[json.dumps(item, ensure_ascii=False) for item in documents],
        params={
            "cluster_dimension": axis,
            "algorithm": "auto",
            "cluster_count": None,
            "minimum_cluster_size": 2,
            "similarity_metric": "cosine",
            "axis_extraction": "local",
            "rule_mode": "off",
            "random_state": 42,
        },
    )
    response = execute_deep_clustering(
        "dc_cluster", request, _FunctionalPoint(), glm_client=None,
    )
    assert response.success is True
    data = response.data
    assert data["n"] == len(documents)
    assert len(data["documents"]) == len(documents)
    assert len(data["semantic_projection"]) == len(documents)
    assert data["clustering_quality"]["topic_library_used"] is False
    assert data["algorithm_metadata"]["llm_assigns_cluster_membership"] is False
    assert data["algorithm_metadata"]["selected_axis"] in {"technical", "application"}
    modes = [item["input_representation"]["mode"] for item in data["documents"]]
    assert modes[:2] == ["structured", "structured"]
    assert modes[2:] == ["plain_text", "plain_text", "plain_text", "plain_text"]
    assert data["input_summary"]["structured_document_count"] == 2
    assert data["input_summary"]["plain_text_document_count"] == 4
    return data


def main() -> None:
    technical = _run("technology", TECHNICAL_DOCUMENTS)
    print(json.dumps({
        "route": "technical",
        "axis_engine": technical["algorithm_metadata"]["axis_engine"],
        "algorithm": technical["algorithm_metadata"]["effective_algorithm"],
        "cluster_count": technical["clustering_quality"]["cluster_count"],
        "representation": technical["representation_metadata"]["representation"],
    }, ensure_ascii=False))

    application = _run("application_scenario", APPLICATION_DOCUMENTS)
    print(json.dumps({
        "route": "application",
        "axis_engine": application["algorithm_metadata"]["axis_engine"],
        "algorithm": application["algorithm_metadata"]["effective_algorithm"],
        "cluster_count": application["clustering_quality"]["cluster_count"],
        "representation": application["representation_metadata"]["representation"],
        "extraction_mode": application["axis_extraction"]["mode"],
    }, ensure_ascii=False))
    print("DUAL_AXIS_LOCAL_BGE_M3_SELFTEST_PASS count=2 glm_used=false")


if __name__ == "__main__":
    main()
