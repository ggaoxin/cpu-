"""结构化自动综述应用服务。

负责把统一 DTO 转为领域对象，并编排证据抽取、研究问题聚类和报告生成。
"""
from __future__ import annotations

import json
from typing import Any

from application.dto.common_dto import SemanticRequest
from domain.entity.base import SemanticResult
from infrastructure.rag.m3_encoder import m3_encoder
from infrastructure.structured_review.engine import StructuredReviewEngine


def execute_structured_review(
    code: str,
    request: SemanticRequest,
    functional_point: Any,
    glm: Any,
) -> SemanticResult:
    """执行第一阶段结构化自动综述。

    正式输入仅包括：文献集、研究主题或关键词、文献元数据。
    不读取也不接受历史深度聚类任务。
    """
    result = SemanticResult(code=code, name=functional_point.name)
    params = request.params or {}
    raw_documents = request.texts or []
    if not raw_documents:
        raise ValueError("结构化自动综述需提供 document_set 文献集")
    if len(raw_documents) < 3:
        raise ValueError("结构化自动综述至少需要3篇文献")
    if len(raw_documents) > 50:
        raise ValueError("结构化自动综述一次最多处理50篇文献")

    raw_topic = params.get("topic_or_keywords")
    if isinstance(raw_topic, list):
        topic = "；".join(str(item).strip() for item in raw_topic if str(item).strip())
    else:
        topic = str(raw_topic or params.get("topic") or "").strip()
    if not topic:
        raise ValueError("结构化自动综述需提供 topic_or_keywords")

    metadata = params.get("document_metadata") or []
    source_mode = str((request.meta or {}).get("source") or "texts")
    if source_mode not in {"file", "files", "collection"} and not metadata:
        raise ValueError("批量文本模式需提供与 document_set 对应的 document_metadata")
    engine = StructuredReviewEngine(glm=glm, encoder=m3_encoder)
    documents = engine.normalize_documents(raw_documents, metadata)
    if metadata and isinstance(metadata, list):
        metadata_ids = {
            str(item.get("document_id") or item.get("id")) for item in metadata
            if isinstance(item, dict) and (item.get("document_id") or item.get("id"))
        }
        missing_ids = [item.document_id for item in documents if item.document_id not in metadata_ids]
        if missing_ids:
            raise ValueError(
                "document_metadata 缺少以下文献编号：" + "、".join(missing_ids)
            )
    output = engine.run(documents, topic)

    result.success = True
    result.data = output
    result.evidence = output.get("evidence_index", [])
    result.raw = json.dumps({
        "document_count": output.get("document_count", 0),
        "research_question_count": output.get("statistics", {}).get("research_question_count", 0),
        "cluster_count": output.get("cluster_induction_results", {}).get("cluster_count", 0),
        "trend_hotspot_status": "not_computed_in_phase_1",
    }, ensure_ascii=False)
    return result
