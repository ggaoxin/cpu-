from __future__ import annotations
from pathlib import Path

from infrastructure.clustering.axis_extractor import EvidenceBoundAxisExtractor


class FakeLLM:
    def __init__(self, documents):
        self.documents = documents
        self.prompts = []

    def chat_json(self, system_prompt, user_prompt, **kwargs):
        self.prompts.append((system_prompt, user_prompt, kwargs))
        return {"documents": self.documents}


def _papers():
    return [
        {
            "document_id": "D1",
            "title": "Transformer用于临床风险预测",
            "keywords": ["Transformer", "临床风险预测"],
            "abstract": "本文采用Transformer和注意力机制，面向临床患者开展风险预测。",
        },
        {
            "document_id": "D2",
            "title": "空间回归用于区域碳排放研究",
            "keywords": ["空间回归", "碳排放"],
            "abstract": "本文使用空间回归模型研究区域碳排放。",
        },
    ]


def _extract(llm):
    return EvidenceBoundAxisExtractor(llm, model_name="fake", cache_dir=None).extract(
        _papers(),
        local_technical_views=["local-tech-1", "local-tech-2"],
        local_application_views=["local-app-1", "local-app-2"],
        local_technical_evidence=[["local-evidence-1"], ["local-evidence-2"]],
        local_application_evidence=[["local-app-evidence-1"], ["local-app-evidence-2"]],
    )


def test_verified_extraction_is_used_without_cluster_assignment():
    llm = FakeLLM([
        {
            "document_id": "D1",
            "technical_route_terms": ["Transformer", "注意力机制"],
            "technical_route_evidence": ["本文采用Transformer和注意力机制"],
            "application_scenario_terms": ["临床患者", "风险预测"],
            "application_domain_terms": ["临床"],
            "application_object_terms": ["临床患者"],
            "application_problem_terms": ["风险预测"],
            "application_task_terms": ["预测"],
            "application_scenario_evidence": ["面向临床患者开展风险预测"],
        },
        {
            "document_id": "D2",
            "technical_route_terms": ["空间回归模型"],
            "technical_route_evidence": ["本文使用空间回归模型"],
            "application_scenario_terms": ["区域碳排放"],
            "application_domain_terms": ["区域碳排放"],
            "application_object_terms": ["碳排放"],
            "application_problem_terms": ["区域碳排放"],
            "application_scenario_evidence": ["研究区域碳排放"],
        },
    ])
    result = _extract(llm)

    assert result.metadata["mode"] == "llm_verified"
    assert result.metadata["verified_document_count"] == 2
    assert result.metadata["fallback_document_count"] == 0
    assert result.metadata["llm_assigns_cluster_membership"] is False
    assert "Transformer" in result.technical_views[0]
    assert "区域碳排放" in result.application_views[1]
    assert result.application_facets[0]["problem"] == ["风险预测"]
    assert "cluster" not in llm.prompts[0][1].lower()
    assert "簇号" in llm.prompts[0][0]


def test_hallucinated_terms_or_quotes_trigger_per_document_fallback():
    llm = FakeLLM([
        {
            "document_id": "D1",
            "technical_route_terms": ["不存在的量子算法"],
            "technical_route_evidence": ["不存在的原文证据"],
            "application_scenario_terms": ["临床患者"],
            "application_scenario_evidence": ["面向临床患者开展风险预测"],
        },
        {
            "document_id": "D2",
            "technical_route_terms": ["空间回归模型"],
            "technical_route_evidence": ["本文使用空间回归模型"],
            "application_scenario_terms": ["区域碳排放"],
            "application_scenario_evidence": ["研究区域碳排放"],
        },
    ])
    result = _extract(llm)

    assert result.metadata["mode"] == "hybrid_fallback"
    assert result.metadata["verified_document_count"] == 1
    assert result.metadata["fallback_document_count"] == 1
    assert result.technical_views[0] == "local-tech-1"
    assert "空间回归模型" in result.technical_views[1]


def test_full_text_pdf_excerpt_is_available_and_evidence_is_verified():
    papers = [{
        "document_id": "PDF1",
        "title": "设备研究",
        "keywords": [],
        "abstract": "摘要未交代具体方法。",
        "full_text": "材料与方法：本文采用小波包分解分析轴承振动信号，用于设备故障诊断。" * 120,
    }]
    llm = FakeLLM([{
        "document_id": "PDF1",
        "technical_route_terms": ["小波包分解"],
        "technical_route_evidence": ["本文采用小波包分解分析轴承振动信号"],
        "application_scenario_terms": [],
        "application_scenario_evidence": [],
    }])
    result = EvidenceBoundAxisExtractor(
        llm, model_name="fake", cache_dir=None, required_axes=("technical",),
    ).extract(
        papers,
        local_technical_views=["local-tech"],
        local_application_views=["local-app"],
        local_technical_evidence=[["local-evidence"]],
        local_application_evidence=[["local-app-evidence"]],
    )
    assert result.metadata["verified_document_count"] == 1
    assert "小波包分解" in result.technical_views[0]
    assert "full_text_evidence_excerpt" in llm.prompts[0][1]


def test_cache_round_trip_preserves_application_facets():
    """Regression: cache hit must not silently drop application facets.

    The persisted cache stores facets as a nested ``application_facets`` dict,
    while live GLM JSON uses flat ``application_<facet>_terms`` keys.  A cache
    round-trip (write then read) must preserve facets — previously _validate
    only read flat keys, so every cache hit emptied all facets.
    """
    import tempfile
    cache_dir = Path(tempfile.mkdtemp())
    llm = FakeLLM([
        {"document_id": "D1",
         "technical_route_terms": ["Transformer"],
         "technical_route_evidence": ["本文采用Transformer和注意力机制"],
         "application_scenario_terms": ["临床患者", "风险预测"],
         "application_domain_terms": ["临床"],
         "application_object_terms": ["临床患者"],
         "application_problem_terms": ["风险预测"],
         "application_task_terms": ["预测"],
         "application_scenario_evidence": ["面向临床患者开展风险预测"]},
        {"document_id": "D2",
         "technical_route_terms": ["空间回归模型"],
         "technical_route_evidence": ["本文使用空间回归模型"],
         "application_scenario_terms": ["区域碳排放"],
         "application_domain_terms": ["区域碳排放"],
         "application_object_terms": ["碳排放"],
         "application_problem_terms": ["区域碳排放"],
         "application_scenario_evidence": ["研究区域碳排放"]},
    ])
    first = EvidenceBoundAxisExtractor(llm, model_name="fake", cache_dir=cache_dir).extract(
        _papers(),
        local_technical_views=["local-tech-1", "local-tech-2"],
        local_application_views=["local-app-1", "local-app-2"],
        local_technical_evidence=[["le1"], ["le2"]],
        local_application_evidence=[["lae1"], ["lae2"]],
    )

    class _FailLLM:
        def chat_json(self, *a, **k):
            raise RuntimeError("cache hit should not call the LLM")

    second = EvidenceBoundAxisExtractor(_FailLLM(), model_name="fake", cache_dir=cache_dir).extract(
        _papers(),
        local_technical_views=["local-tech-1", "local-tech-2"],
        local_application_views=["local-app-1", "local-app-2"],
        local_technical_evidence=[["le1"], ["le2"]],
        local_application_evidence=[["lae1"], ["lae2"]],
    )
    assert first.application_facets[0]["problem"] == ["风险预测"]
    assert second.application_facets[0]["problem"] == ["风险预测"], \
        f"cache round-trip dropped facets: {second.application_facets[0]}"
    assert second.application_facets[1]["object"] == ["碳排放"]
    assert second.metadata["verified_document_count"] == 2
