"""把统一结果 JSON 投影到可查询的功能专用表。"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Iterable, Optional

from domain.entity.analysis_task import ResultRecord


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _number(value: Any) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def save_result_projection(session: Any, record: ResultRecord) -> None:
    result = record.result if isinstance(record.result, dict) else {}
    dispatch = {
        "zh-abstract-move": _save_moves,
        "en-abstract-move": _save_moves,
        "fund-move": _save_moves,
        "zh-classify": _save_classification,
        "en-classify": _save_classification,
        "domain-classify": _save_classification,
        "zh-keyword": _save_keywords,
        "en-keyword": _save_keywords,
        "rq-detect": _save_research_questions,
        "citation-sentiment": _save_citations,
        "citation-intent": _save_citations,
        "definition-detect": _save_definitions,
        "general-ner": _save_entities,
        "research-ner": _save_entities,
        "domain-ner": _save_entities,
        "relation-extract": _save_relations,
        "deep-cluster": _save_clusters,
        "cluster-label": _save_labels,
        "structured-review": _save_review,
    }
    handler = dispatch.get(record.tool_id)
    if handler:
        handler(session, record.id, result, record.tool_id)


def _save_moves(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    document = result.get("document") if isinstance(result.get("document"), dict) else {}
    session.execute(
        "INSERT INTO move_results (result_record_id, document_title, project_title, statistics_json, move_count, sentence_count, input_type, overall_confidence, document_language) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (record_id, document.get("title") or result.get("document_title"), result.get("project_title"),
         _dump(result.get("move_statistics") or {}), result.get("move_count"), result.get("sentence_count"),
         result.get("input_type"), _number(result.get("confidence")), document.get("language")),
    )
    for move in _list(result.get("moves")):
        if not isinstance(move, dict):
            continue
        source = {
            "sections": move.get("source_sections") or move.get("source_section"),
            "pages": move.get("source_pages") or move.get("page"),
            "sources": move.get("sources"),
        }
        session.execute(
            """INSERT INTO move_segments
            (id, result_record_id, move_code, move_name, label, sentence_index, start_offset,
             end_offset, text_value, source_json, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id("mvs"), record_id, move.get("move_code"), move.get("move_name") or move.get("label"),
             move.get("label"),
             move.get("sentence_index"), move.get("start"), move.get("end"),
             move.get("text") or move.get("content"), _dump(source), _number(move.get("confidence"))),
        )


def _save_classification(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    primary = result.get("primary_classification") if isinstance(result.get("primary_classification"), dict) else {}
    session.execute(
        """INSERT INTO classification_results
        (result_record_id, primary_code, primary_name, primary_path, primary_confidence,
         selected_domain, domain_labels, taxonomy_version, confirmation_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (record_id, primary.get("clc_code") or primary.get("code"), primary.get("name") or primary.get("label"),
         _dump(primary.get("path") or primary.get("classification_path") or []),
         _number(primary.get("confidence") or primary.get("score")), _dump(result.get("selected_domain")),
         _dump(result.get("domain_labels") or []), result.get("taxonomy_version"), result.get("confirmation_status")),
    )
    values = []
    values.extend(item for item in _list(result.get("classifications")) if isinstance(item, dict))
    values.extend(item for item in _list(result.get("candidates")) if isinstance(item, dict))
    for index, item in enumerate(values):
        session.execute(
            """INSERT INTO classification_candidates
            (id, result_record_id, role_name, class_code, class_name, path_json, confidence, rank_no)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id("clc"), record_id, item.get("role") or ("candidate" if index else "primary"),
             item.get("clc_code") or item.get("code"), item.get("name") or item.get("label") or item.get("category_name"),
             _dump(item.get("path") or item.get("classification_path") or []),
             _number(item.get("confidence") or item.get("score")), item.get("rank") or index + 1),
        )


def _save_keywords(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    session.execute(
        "INSERT INTO keyword_results (result_record_id, dictionary_usage, statistics_json) VALUES (?, ?, ?)",
        (record_id, _dump(result.get("dictionary_usage")), _dump(result.get("statistics") or {})),
    )
    for item in _list(result.get("keywords")):
        if not isinstance(item, dict):
            continue
        session.execute(
            """INSERT INTO keyword_items
            (id, result_record_id, term, normalized_term, score, rank_no, source_name, source_position, mapping_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id("kwi"), record_id, item.get("term") or item.get("keyword") or "",
             item.get("normalized_term"), _number(item.get("score") or item.get("confidence") or item.get("weight")),
             item.get("rank"), item.get("source") or item.get("terminology_source"),
             _dump(item.get("source_position")), _dump(item.get("clc_mappings") or [])),
        )


def _save_research_questions(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    session.execute("INSERT INTO research_question_results (result_record_id, statistics_json) VALUES (?, ?)",
                    (record_id, _dump(result.get("statistics") or {})))
    groups = (
        ("sentence", result.get("research_question_sentences"), ("text", "sentence")),
        ("phrase", result.get("research_question_phrases"), ("text", "phrase")),
        ("structured", result.get("structured_research_questions"), ("question", "normalized_question")),
    )
    for item_type, items, text_keys in groups:
        for item in _list(items):
            if not isinstance(item, dict):
                continue
            text_value = next((item.get(key) for key in text_keys if item.get(key)), None)
            position = item.get("source_position") or item.get("position") or {
                "start": item.get("start"), "end": item.get("end"), "page": item.get("page"),
            }
            session.execute(
                """INSERT INTO research_question_items
                (id, result_record_id, item_type, text_value, structured_json, source_position, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (_id("rqi"), record_id, item_type, text_value, _dump(item), _dump(position), _number(item.get("confidence"))),
            )


def _save_citations(session: Any, record_id: str, result: Dict[str, Any], tool_id: str) -> None:
    analysis_type = "sentiment" if tool_id == "citation-sentiment" else "intent"
    session.execute("INSERT INTO citation_results (result_record_id, analysis_type, statistics_json) VALUES (?, ?, ?)",
                    (record_id, analysis_type, _dump(result.get("statistics") or {})))
    for item in _list(result.get("citations")):
        if not isinstance(item, dict):
            continue
        session.execute(
            """INSERT INTO citation_items
            (id, result_record_id, citation_id, sentence, label_name, marker_json, context_json,
             source_position, reference_json, evidence_json, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id("cit"), record_id, item.get("citation_id"), item.get("citation_sentence") or item.get("sentence"),
             item.get("sentiment") or item.get("intent"), _dump(item.get("citation_markers") or item.get("citation_marker")),
             _dump(item.get("context")), _dump(item.get("source_position") or item.get("position")),
             _dump(item.get("reference") or item.get("citation_metadata")), _dump(item.get("evidence")),
             _number(item.get("confidence"))),
        )


def _save_definitions(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    session.execute("INSERT INTO definition_results (result_record_id, statistics_json) VALUES (?, ?)",
                    (record_id, _dump(result.get("statistics") or {})))
    for item in _list(result.get("definitions")):
        if not isinstance(item, dict):
            continue
        session.execute(
            """INSERT INTO definition_items
            (id, result_record_id, concept, normalized_concept, definition_text, sentence,
             domain_name, source_position, mapped_term_id, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id("dfn"), record_id, item.get("concept"), item.get("normalized_concept"), item.get("definition"),
             item.get("sentence"), item.get("domain"), _dump(item.get("source_position") or item.get("position")),
             item.get("mapped_term_id"), _number(item.get("confidence"))),
        )


def _save_entities(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    session.execute(
        "INSERT INTO entity_results (result_record_id, selected_domain, ontology_version, statistics_json) VALUES (?, ?, ?, ?)",
        (record_id, _dump(result.get("selected_domain")), result.get("ontology_version"), _dump(result.get("statistics") or {})),
    )
    for item in _list(result.get("entities")):
        if not isinstance(item, dict):
            continue
        session.execute(
            """INSERT INTO entity_mentions
            (id, result_record_id, entity_id, text_value, normalized_text, entity_type, start_offset,
             end_offset, context_text, kb_id, type_path, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id("ent"), record_id, item.get("entity_id"), item.get("text") or item.get("entity"),
             item.get("normalized_text") or item.get("standard_term"), item.get("type") or item.get("entity_type"),
             item.get("start"), item.get("end"), item.get("context"), item.get("kb_id"),
             _dump(item.get("type_path") or []), _number(item.get("confidence"))),
        )


def _save_relations(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    session.execute("INSERT INTO relation_results (result_record_id, source_records, statistics_json) VALUES (?, ?, ?)",
                    (record_id, _dump(result.get("source_records")), _dump(result.get("statistics") or {})))
    for item in _list(result.get("triples")):
        if not isinstance(item, dict):
            continue
        session.execute(
            """INSERT INTO relation_triples
            (id, result_record_id, triple_id, subject_entity_id, subject_text, relation_name,
             relation_type, object_entity_id, object_text, evidence_json, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id("tri"), record_id, item.get("triple_id"), item.get("subject_entity_id"), item.get("subject"),
             item.get("relation") or item.get("predicate"), item.get("relation_type"), item.get("object_entity_id"),
             item.get("object"), _dump(item.get("evidence")), _number(item.get("confidence"))),
        )


def _save_clusters(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    session.execute(
        "INSERT INTO cluster_runs (result_record_id, cluster_task_id, dimension_name, quality_metrics, correction_status) VALUES (?, ?, ?, ?, ?)",
        (record_id, result.get("cluster_task_id"), result.get("dimension"), _dump(result.get("quality_metrics")), result.get("correction_status")),
    )
    for item in _list(result.get("clusters")):
        if not isinstance(item, dict):
            continue
        cluster_row_id = _id("clu")
        members = _list(item.get("members"))
        session.execute(
            """INSERT INTO clusters
            (id, result_record_id, cluster_id, size_count, representative_terms, centroid_document_id, trend_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cluster_row_id, record_id, item.get("cluster_id"), item.get("size") or len(members),
             _dump(item.get("representative_terms") or []), item.get("centroid_document_id"), _dump(item.get("trend") or [])),
        )
        for member in members:
            if not isinstance(member, dict):
                continue
            session.execute(
                "INSERT INTO cluster_memberships (id, cluster_row_id, document_id, title, similarity) VALUES (?, ?, ?, ?, ?)",
                (_id("clm"), cluster_row_id, member.get("document_id"), member.get("title"), _number(member.get("similarity"))),
            )


def _save_labels(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    session.execute(
        "INSERT INTO cluster_label_results (result_record_id, source_cluster_task_id, generation_report) VALUES (?, ?, ?)",
        (record_id, result.get("source_cluster_task_id"), _dump(result.get("generation_report") or {})),
    )
    for item in _list(result.get("labels")):
        if not isinstance(item, dict):
            continue
        session.execute(
            """INSERT INTO cluster_labels
            (id, result_record_id, cluster_id, label_text, confidence, distinctiveness, alternatives, evidence_terms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (_id("lbl"), record_id, item.get("cluster_id"), item.get("label"), _number(item.get("confidence")),
             _number(item.get("distinctiveness")),
             _dump(item.get("alternatives") or item.get("candidate_labels") or []),
             _dump(item.get("evidence_terms") or [])),
        )


def _save_review(session: Any, record_id: str, result: Dict[str, Any], _: str) -> None:
    trend_hotspot = result.get("trend_hotspot_distribution") or {}
    session.execute(
        """INSERT INTO review_results
        (result_record_id, review_id, topic, traceability, trend_analysis, hotspots)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (record_id, result.get("review_id"), result.get("topic"), True,
         _dump(trend_hotspot), _dump(trend_hotspot.get("hotspots") or [])),
    )

    def save_nodes(nodes: Iterable[Any], parent_id: Optional[str] = None, level: int = 1) -> None:
        for index, item in enumerate(nodes):
            if not isinstance(item, dict):
                continue
            node_id = (item.get("node_id") or item.get("question_id") or item.get("rq_id")
                       or item.get("method_id") or f"node_{level}_{index + 1}")
            title = item.get("research_question") or item.get("method") or item.get("title")
            content = (item.get("progress") or item.get("content") or item.get("summary")
                       or item.get("question_summary"))
            if isinstance(content, (list, dict)):
                content = _dump(content)
            node_type = "research_question" if level == 1 else "method" if level == 2 else "progress"
            session.execute(
                """INSERT INTO review_nodes
                (id, result_record_id, node_id, parent_node_id, level_no, node_type, title, content, evidence_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (_id("rvn"), record_id, node_id, parent_id, level, node_type, title, content,
                 _dump(item.get("evidence_ids") or item.get("evidence") or [])),
            )
            children = item.get("children") or item.get("methods") or item.get("progress") or []
            save_nodes(_list(children), node_id, level + 1)

    save_nodes(_list(result.get("tree")))
    report = result.get("structured_report") if isinstance(result.get("structured_report"), dict) else {}
    for item in _list(report.get("sections") or result.get("sections")):
        if isinstance(item, dict):
            session.execute(
                """INSERT INTO review_sections
                (id, result_record_id, section_id, title, content, evidence_ids) VALUES (?, ?, ?, ?, ?, ?)""",
                (_id("rvs"), record_id, item.get("section_id"), item.get("title"), item.get("content"),
                 _dump(item.get("evidence_ids") or [])),
            )
    for item in _list(result.get("evidence")):
        if isinstance(item, dict):
            session.execute(
                """INSERT INTO review_evidence_links
                (id, result_record_id, evidence_id, document_id, title, page_no, quote_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (_id("rve"), record_id, item.get("evidence_id"), item.get("document_id"),
                 item.get("title"), item.get("page"), item.get("quote") or item.get("evidence_excerpt")),
            )
