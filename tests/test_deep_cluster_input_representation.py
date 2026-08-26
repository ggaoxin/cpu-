from __future__ import annotations

import json

from application.service.tool_integration_service import ToolIntegrationService
from application.service.semantic_service import SemanticApplicationService
from application.service.deep_clustering_service import _publication_date_from_text
from config.tool_contracts import get_contract
from infrastructure.clustering.dual_axis_cluster import normalize_papers
from infrastructure.clustering.input_representation import (
    parse_labeled_structure,
    select_axis_chunks,
    source_groups,
)


def test_vue_text_and_publication_date_survive_integration_adapter():
    encoded = ToolIntegrationService._document_text({
        "document_id": "R001",
        "publication_date": "2025-03-12",
        "text": "科研报告采用有限元分析评估桥梁疲劳寿命。",
    })
    restored = json.loads(encoded)
    assert restored == {
        "document_id": "R001",
        "title": "",
        "abstract": "",
        "text": "科研报告采用有限元分析评估桥梁疲劳寿命。",
        "keywords": [],
        "authors": [],
        "institutions": [],
        "source": "",
        "doi": "",
        "published_at": None,
        "publication_date": "2025-03-12",
        "full_text": "",
    }


def test_integration_layer_rejects_over_limit_text_before_task_creation():
    error = ToolIntegrationService._payload_error(object(), get_contract("deep-cluster"), {
        "documents": [{"id": "R999", "publication_date": "2025-01-01", "text": "文" * 8001}],
    })
    assert error == "R999 的 text 清洗后不能超过8000个字符"


def test_all_manual_text_and_batch_content_are_limited_to_8000_characters():
    for tool_id, payload, expected in (
        ("rq-detect", {"input_type": "text", "text": "文" * 8001}, "text 清洗后不能超过8000个字符"),
        ("zh-keyword", {"input_type": "text", "abstract": "文" * 8001}, "abstract 清洗后不能超过8000个字符"),
        ("cluster-label", {"input_type": "texts", "texts": [{"id": "T01", "content": "文" * 8001}]}, "T01 的 content 清洗后不能超过8000个字符"),
        ("structured-review", {"input_type": "texts", "documents": [{"id": "D01", "text": "文" * 8001}]}, "D01 的 text 清洗后不能超过8000个字符"),
    ):
        assert ToolIntegrationService._payload_error(object(), get_contract(tool_id), payload) == expected


def test_classification_plain_text_is_not_wrapped_as_a_fake_abstract():
    payload = {"input_type": "text", "text": "这是一段没有显式标题摘要关键词结构的科研报告。"}
    contract = get_contract("zh-classify")
    assert ToolIntegrationService._single_text(contract, payload) == payload["text"]
    assert ToolIntegrationService._backend_text(contract, payload["text"], payload) == payload["text"]


def test_classification_parser_uses_explicit_structure_or_plain_text_fallback():
    service = SemanticApplicationService.__new__(SemanticApplicationService)
    plain = type("Request", (), {"text": "普通科技报告正文，没有字段标签。", "meta": {}})()
    title, abstract, keywords, full_text = service._parse_paper_input(plain)
    assert (title, abstract, keywords, full_text) == ("", plain.text, [], None)

    structured_text = (
        "标题：多源遥感协同分类\n"
        "摘要：本文融合光学影像、雷达数据和地形辅助信息，构建协同编码网络并在多个城市数据集上完成验证。\n"
        "关键词：遥感分类；多源数据；协同编码"
    )
    structured = type("Request", (), {"text": structured_text, "meta": {}})()
    title, abstract, keywords, full_text = service._parse_paper_input(structured)
    assert title == "多源遥感协同分类"
    assert abstract.startswith("本文融合光学影像")
    assert keywords == ["遥感分类", "多源数据", "协同编码"]
    assert full_text is None


def test_non_classification_batch_document_passes_only_its_real_text():
    contract = get_contract("rq-detect")
    encoded = ToolIntegrationService._document_text({"id": "Q01", "text": "如何提高模型的泛化能力？"})
    assert ToolIntegrationService._backend_text(contract, encoded, {}) == "如何提高模型的泛化能力？"


def test_collection_document_metadata_preserves_date_keywords_and_body():
    encoded = ToolIntegrationService._document_text({
        "id": "DB001",
        "title": "数据库中的科研报告",
        "abstract_text": "报告摘要",
        "content_text": "报告完整正文",
        "metadata_json": json.dumps({
            "publication_date": "2023-06-09",
            "keywords": ["海上风电", "运维"],
        }, ensure_ascii=False),
    })
    restored = json.loads(encoded)
    assert restored["publication_date"] == "2023-06-09"
    assert restored["keywords"] == ["海上风电", "运维"]
    assert restored["text"] == "报告完整正文"
    assert restored["full_text"] == "报告完整正文"


def test_file_date_parser_requires_publication_context():
    assert _publication_date_from_text("发布日期：2025年3月12日") == "2025年3月12日"
    assert _publication_date_from_text("Publication date: 2024-08-01") == "2024-08-01"
    assert _publication_date_from_text("Published 2023/6/9") == "2023/6/9"
    assert _publication_date_from_text("实验于2025年3月12日完成") is None


def test_plain_text_report_does_not_receive_a_pseudo_semantic_title():
    paper = normalize_papers([{
        "id": "R002",
        "publication_date": "2024/08/01",
        "text": "本报告面向海上风电运维，采用声发射与有限元仿真识别叶片裂纹。",
    }])[0]
    assert paper["input_representation"]["mode"] == "plain_text"
    assert paper["semantic_title"] == ""
    assert paper["title"] == "R002"
    assert paper["semantic_text"].startswith("本报告面向")
    assert paper["publication_year"] == 2024


def test_explicit_title_abstract_keywords_enter_structured_mode():
    text = (
        "标题：面向工业轴承的图神经网络故障诊断\n"
        "摘要：本文面向制造装备轴承故障诊断，提出图神经网络与多尺度特征融合方法，"
        "通过真实振动数据完成故障识别并提高复杂工况下的诊断准确率。\n"
        "关键词：图神经网络；轴承故障；智能制造"
    )
    parsed = parse_labeled_structure(text)
    assert parsed is not None
    paper = normalize_papers([{"id": "P001", "publication_date": "2025-01-01", "text": text}])[0]
    assert paper["input_representation"]["mode"] == "structured"
    assert paper["input_representation"]["parser"] == "explicit_label_regex"
    assert paper["semantic_title"] == "面向工业轴承的图神经网络故障诊断"
    assert paper["keywords"] == ["图神经网络", "轴承故障", "智能制造"]
    technical_groups = source_groups(paper, "technical")
    assert [item["label"] for item in technical_groups] == ["title", "abstract", "keywords"]
    assert [round(item["weight"], 2) for item in technical_groups] == [0.15, 0.65, 0.20]


def test_incomplete_paper_markers_fall_back_to_plain_text():
    paper = normalize_papers([{
        "id": "R003",
        "publication_date": "2025-01-02",
        "text": "标题：阶段性项目报告\n摘要：这是项目阶段性总结，没有提供关键词字段，但正文包含技术路线。",
    }])[0]
    assert paper["input_representation"]["mode"] == "plain_text"
    assert paper["semantic_title"] == ""
    assert paper["title"] == "R003"
    assert paper["keywords"] == []


def test_manual_text_over_8000_characters_is_rejected_without_truncation():
    try:
        normalize_papers([{
            "id": "R004",
            "publication_date": "2025-01-03",
            "text": "技" * 8001,
        }])
    except ValueError as exc:
        assert "超过允许的 8000 个字符" in str(exc)
    else:
        raise AssertionError("An over-limit text must be rejected, not truncated.")


def test_plain_text_chunk_selection_reviews_late_axis_evidence():
    text = ("背景信息。" * 700) + "本项目采用有限元仿真和现场载荷试验形成技术路线。"
    chunks = select_axis_chunks(text[:8000], "technical")
    assert chunks
    assert any("有限元仿真" in item["source_text"] for item in chunks)
    assert abs(sum(item["weight"] for item in chunks) - 1.0) < 1e-9
