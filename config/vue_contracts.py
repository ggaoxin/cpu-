"""V7.74 Vue-first public contracts for all 19 semantic tools.

Names in this module are the public HTTP fields shown by the Vue online tester
and API/SDK documentation. Algorithm DTO names are adapted in the application
layer and must not leak back into this contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class VueContract:
    tool_id: str
    input_modes: Tuple[str, ...]
    request_fields: Tuple[str, ...]
    result_fields: Tuple[str, ...]
    primary_input_field: str


def _contract(tool_id: str, modes: str, request: str, result: str, primary: str) -> VueContract:
    return VueContract(
        tool_id=tool_id,
        input_modes=tuple(modes.split()),
        request_fields=tuple(request.split()),
        result_fields=tuple(result.split()),
        primary_input_field=primary,
    )


CONTRACTS = (
    _contract("zh-abstract-move", "text batch-text file batch", "chinese_scientific_abstract", "document moves sentence_count", "chinese_scientific_abstract"),
    _contract("en-abstract-move", "text batch-text file batch", "english_scientific_abstract", "document moves sentence_count", "english_scientific_abstract"),
    _contract("fund-move", "text batch-text file batch", "project_name project_document_text", "document moves", "project_document_text"),
    _contract("zh-classify", "text batch-text file batch", "chinese_scientific_document_text document_title clc_labeled_data", "is_interdisciplinary classifications domain_labels candidate_classifications", "chinese_scientific_document_text"),
    _contract("en-classify", "text batch-text file batch", "english_scientific_document_text document_title clc_labeled_data", "is_interdisciplinary classifications cross_language_mapping domain_labels candidate_classifications literature_distribution_analysis_report", "english_scientific_document_text"),
    _contract("domain-classify", "text batch-text file batch", "domain_scientific_literature_data document_title professional_domain domain_classification_rules manually_labeled_training_data", "professional_domain multilevel_classification_results classification_confidence domain_labels candidate_classifications", "domain_scientific_literature_data"),
    _contract("zh-keyword", "text batch-text file batch", "chinese_scientific_abstract document_title domain_terminology_dictionary", "document keywords", "chinese_scientific_abstract"),
    _contract("en-keyword", "text batch-text file batch", "english_scientific_abstract document_title domain_terminology_library classification_standard_mapping_table", "document keywords_or_topic_phrases", "english_scientific_abstract"),
    _contract("rq-detect", "text batch-text file batch", "scientific_document_fragment document_title text_format_requirement", "document research_question_sentences research_question_phrases structured_research_questions research_question_statistics", "scientific_document_fragment"),
    _contract("citation-sentiment", "text batch-text file batch", "scientific_document_full_text citation_sentence_and_context citation_metadata", "document citation_sentiment_results", "scientific_document_full_text"),
    _contract("citation-intent", "text batch-text file batch", "citation_sentence_and_context citation_metadata preprocessed_training_set", "document citation_intent_results", "citation_sentence_and_context"),
    _contract("definition-detect", "text batch-text file batch", "scientific_document_fragment_or_batch_text domain_label output_format_requirement", "document definitions concept_definition_mappings statistical_analysis_report", "scientific_document_fragment_or_batch_text"),
    _contract("general-ner", "text batch-text file batch", "bilingual_scientific_document_text general_domain_annotated_corpus", "document entities summary", "bilingual_scientific_document_text"),
    _contract("research-ner", "text batch-text file batch", "academic_abstract_or_technical_report_text multi_domain_scientific_corpus manually_labeled_data", "document entities standard_term_mappings summary", "academic_abstract_or_technical_report_text"),
    _contract("domain-ner", "text batch-text file batch", "domain_scientific_document_text ontology_classification_system domain_labeled_training_data", "document selected_domain entities ontology_mappings summary", "domain_scientific_document_text"),
    _contract("relation-extract", "existing-result", "upstream_ner_record_id", "dependency_parse dependency_paths relation_triples", "upstream_ner_record_id"),
    _contract("deep-cluster", "batch-text batch", "scientific_document_texts document_metadata cluster_dimension clustering_algorithm_type cluster_count output_format", "cluster_dimension_name input_summary clustering_quality training_evaluation clusters document_assignments semantic_projection theme_trend_analysis", "scientific_document_texts"),
    _contract("cluster-label", "batch-text", "cluster_phrase_sets label_length_limit language_type distinctiveness_threshold", "cluster_count generated_label_count parameters labels statistics label_generation_process_report label_distinctiveness_optimization_result", "cluster_phrase_sets"),
    _contract("structured-review", "batch-text batch collection", "document_set topic_or_keywords document_metadata", "tree cluster_induction_results structured_report trend_hotspot_distribution", "document_set"),
)

BY_TOOL_ID: Dict[str, VueContract] = {item.tool_id: item for item in CONTRACTS}


def get_vue_contract(tool_id: str) -> VueContract:
    try:
        return BY_TOOL_ID[tool_id]
    except KeyError as exc:
        raise ValueError(f"未知 Vue 工具 ID：{tool_id}") from exc
