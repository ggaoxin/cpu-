from __future__ import annotations

import json

from application.dto.common_dto import SemanticRequest
from application.service.deep_clustering_service import _input_documents


def _document_text_payload(document):
    content = document.get("text") or document.get("abstract") or document.get("full_text") or ""
    return json.dumps({
        "id": document.get("id"),
        "title": document.get("title", ""),
        "abstract": document.get("abstract") or "",
        "text": document.get("text") or content,
        "keywords": document.get("keywords") or [],
        "published_at": document.get("published_at") or document.get("publication_date"),
        "publication_date": document.get("publication_date") or document.get("published_at"),
    }, ensure_ascii=False)


def test_semantic_request_preserves_structured_json_documents():
    document = {
        "id": "P001",
        "title": "图神经网络设备诊断",
        "abstract": "本文采用图神经网络识别轴承故障。",
        "keywords": ["图神经网络", "轴承故障"],
        "publication_date": "2025-01-01",
    }
    request = SemanticRequest(texts=[_document_text_payload(document)])
    restored = json.loads(request.texts[0])
    assert restored["keywords"] == document["keywords"]
    assert restored["publication_date"] == document["publication_date"]


def test_document_adapter_does_not_drop_title_abstract_keywords_or_date():
    document = {
        "id": "P002",
        "title": "临床风险预测",
        "abstract": "使用Transformer预测临床患者风险。",
        "keywords": ["Transformer", "临床风险"],
        "published_at": "2024-08-01",
    }
    encoded = _document_text_payload(document)
    decoded = json.loads(encoded)
    assert decoded["title"] == document["title"]
    assert decoded["abstract"] == document["abstract"]
    assert decoded["keywords"] == document["keywords"]
    assert decoded["published_at"] == document["published_at"]


def test_deep_cluster_semantic_request_keeps_item_source_object():
    document = {
        "id": "P003",
        "title": "风机叶片裂纹检测",
        "abstract": "本文采用声发射方法检测风机叶片裂纹。",
        "keywords": ["声发射", "裂纹检测"],
        "publication_date": "2023-06-01",
    }
    serialized = _document_text_payload(document)
    request = SemanticRequest(texts=[serialized])
    restored = _input_documents(request.texts)[0]
    assert restored["title"] == document["title"]
    assert restored["publication_date"] == document["publication_date"]


def test_generic_scientific_report_text_is_a_first_class_input():
    report = {
        "id": "R001",
        "publication_date": "2025-04-15",
        "text": "本报告采用有限元仿真与现场载荷试验评估海上风机基础疲劳寿命。",
    }
    encoded = _document_text_payload(report)
    decoded = json.loads(encoded)
    assert decoded["text"] == report["text"]
    assert decoded["abstract"] == ""
    assert decoded["publication_date"] == report["publication_date"]
