CREATE TABLE IF NOT EXISTS workspaces (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at VARCHAR(40) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO workspaces (id, name, status, created_at)
VALUES ('default', '默认工作空间', 'active', '2026-08-04T00:00:00+00:00');

CREATE TABLE IF NOT EXISTS model_versions (
    id VARCHAR(64) PRIMARY KEY,
    tool_id VARCHAR(64) NOT NULL,
    version VARCHAR(128) NOT NULL,
    labels_schema JSON NULL,
    metrics JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at VARCHAR(40) NOT NULL,
    UNIQUE KEY uk_model_tool_version (tool_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS files (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    original_name VARCHAR(500) NOT NULL,
    object_key VARCHAR(1000) NULL,
    sha256 CHAR(64) NULL,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    media_type VARCHAR(255) NULL,
    parse_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_files_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    KEY idx_files_hash (workspace_id, sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    file_id VARCHAR(64) NULL,
    language VARCHAR(16) NULL,
    title VARCHAR(1000) NULL,
    abstract_text LONGTEXT NULL,
    content_text LONGTEXT NULL,
    content_hash CHAR(64) NULL,
    metadata_json JSON NULL,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_documents_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_documents_file FOREIGN KEY (file_id) REFERENCES files(id),
    KEY idx_documents_hash (workspace_id, content_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS document_collections (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    name VARCHAR(300) NOT NULL,
    description TEXT NULL,
    version INT NOT NULL DEFAULT 1,
    archived_at VARCHAR(40) NULL,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_collections_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    KEY idx_collections_workspace (workspace_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS collection_documents (
    collection_id VARCHAR(64) NOT NULL,
    document_id VARCHAR(64) NOT NULL,
    order_no INT NOT NULL DEFAULT 0,
    PRIMARY KEY (collection_id, document_id),
    CONSTRAINT fk_collection_docs_collection FOREIGN KEY (collection_id) REFERENCES document_collections(id),
    CONSTRAINT fk_collection_docs_document FOREIGN KEY (document_id) REFERENCES documents(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS analysis_tasks (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    tool_id VARCHAR(64) NOT NULL,
    backend_code VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    progress INT NOT NULL DEFAULT 0,
    input_type VARCHAR(32) NOT NULL,
    request_payload LONGTEXT NOT NULL,
    parameters_json JSON NOT NULL,
    model_version VARCHAR(128) NULL,
    total INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    failed_count INT NOT NULL DEFAULT 0,
    error_summary TEXT NULL,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    completed_at VARCHAR(40) NULL,
    archived_at VARCHAR(40) NULL,
    CONSTRAINT fk_tasks_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    KEY idx_tasks_history (workspace_id, tool_id, status, created_at),
    KEY idx_tasks_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS task_items (
    id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    input_index INT NOT NULL,
    status VARCHAR(32) NOT NULL,
    source_json JSON NOT NULL,
    error_message TEXT NULL,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_task_items_task FOREIGN KEY (task_id) REFERENCES analysis_tasks(id),
    KEY idx_task_items_task (task_id, input_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS result_records (
    id VARCHAR(64) PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL,
    task_item_id VARCHAR(64) NULL,
    tool_id VARCHAR(64) NOT NULL,
    backend_code VARCHAR(64) NOT NULL,
    result_json LONGTEXT NOT NULL,
    schema_version VARCHAR(32) NOT NULL DEFAULT '1.0',
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_results_task FOREIGN KEY (task_id) REFERENCES analysis_tasks(id),
    CONSTRAINT fk_results_item FOREIGN KEY (task_item_id) REFERENCES task_items(id),
    KEY idx_results_task (task_id, created_at),
    KEY idx_results_tool (tool_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS record_dependencies (
    id VARCHAR(64) PRIMARY KEY,
    record_id VARCHAR(64) NOT NULL,
    upstream_record_id VARCHAR(64) NOT NULL,
    dependency_type VARCHAR(64) NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_dependencies_record FOREIGN KEY (record_id) REFERENCES result_records(id),
    CONSTRAINT fk_dependencies_upstream FOREIGN KEY (upstream_record_id) REFERENCES result_records(id),
    UNIQUE KEY uk_record_upstream (record_id, upstream_record_id, dependency_type),
    KEY idx_dependencies_upstream (upstream_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dictionaries (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    name VARCHAR(300) NOT NULL,
    language VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    current_version INT NOT NULL DEFAULT 1,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_dictionaries_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    UNIQUE KEY uk_dictionary_name (workspace_id, name, language)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dictionary_versions (
    id VARCHAR(64) PRIMARY KEY,
    dictionary_id VARCHAR(64) NOT NULL,
    version INT NOT NULL,
    weight_boost DECIMAL(5,4) NOT NULL DEFAULT 0,
    content_hash CHAR(64) NULL,
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_dictionary_versions_dictionary FOREIGN KEY (dictionary_id) REFERENCES dictionaries(id),
    UNIQUE KEY uk_dictionary_version (dictionary_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dictionary_terms (
    id VARCHAR(64) PRIMARY KEY,
    dictionary_version_id VARCHAR(64) NOT NULL,
    term VARCHAR(500) NOT NULL,
    normalized_term VARCHAR(500) NULL,
    weight DECIMAL(6,4) NOT NULL DEFAULT 1,
    CONSTRAINT fk_dictionary_terms_version FOREIGN KEY (dictionary_version_id) REFERENCES dictionary_versions(id),
    UNIQUE KEY uk_dictionary_term (dictionary_version_id, term)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS semantic_resources (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    resource_key VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(64) NOT NULL,
    language VARCHAR(32) NULL,
    record_count BIGINT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'current',
    source_type VARCHAR(32) NOT NULL DEFAULT 'bundled',
    storage_uri VARCHAR(1024) NULL,
    content_hash VARCHAR(128) NULL,
    metadata_json JSON NULL,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_semantic_resources_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    UNIQUE KEY uk_semantic_resource_version (workspace_id, resource_key, version),
    KEY idx_semantic_resources_lookup (workspace_id, resource_key, status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS model_evaluation_runs (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    evaluation_type VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    request_json JSON NOT NULL,
    metrics_json JSON NULL,
    created_at VARCHAR(40) NOT NULL,
    completed_at VARCHAR(40) NULL,
    CONSTRAINT fk_model_evaluation_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    KEY idx_model_evaluation_runs_lookup (workspace_id, evaluation_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS taxonomy_versions (
    id VARCHAR(64) PRIMARY KEY,
    taxonomy_code VARCHAR(64) NOT NULL,
    version VARCHAR(128) NOT NULL,
    node_count INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at VARCHAR(40) NOT NULL,
    UNIQUE KEY uk_taxonomy_version (taxonomy_code, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS taxonomy_nodes (
    id VARCHAR(64) PRIMARY KEY,
    version_id VARCHAR(64) NOT NULL,
    parent_id VARCHAR(64) NULL,
    code VARCHAR(128) NOT NULL,
    name_zh VARCHAR(500) NULL,
    name_en VARCHAR(500) NULL,
    level_no INT NULL,
    path_text TEXT NULL,
    CONSTRAINT fk_taxonomy_nodes_version FOREIGN KEY (version_id) REFERENCES taxonomy_versions(id),
    UNIQUE KEY uk_taxonomy_code (version_id, code),
    KEY idx_taxonomy_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ontology_versions (
    id VARCHAR(64) PRIMARY KEY,
    ontology_code VARCHAR(64) NOT NULL,
    version VARCHAR(128) NOT NULL,
    node_count INT NOT NULL DEFAULT 0,
    layer_counts JSON NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at VARCHAR(40) NOT NULL,
    UNIQUE KEY uk_ontology_version (ontology_code, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ontology_nodes (
    id VARCHAR(64) PRIMARY KEY,
    version_id VARCHAR(64) NOT NULL,
    parent_id VARCHAR(64) NULL,
    kb_id VARCHAR(255) NULL,
    preferred_label VARCHAR(500) NOT NULL,
    aliases_json JSON NULL,
    level_no INT NULL,
    CONSTRAINT fk_ontology_nodes_version FOREIGN KEY (version_id) REFERENCES ontology_versions(id),
    KEY idx_ontology_parent (parent_id),
    KEY idx_ontology_kb (version_id, kb_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS classification_confirmations (
    id VARCHAR(64) PRIMARY KEY,
    result_record_id VARCHAR(64) NOT NULL,
    primary_code VARCHAR(128) NOT NULL,
    secondary_codes JSON NULL,
    actor_id VARCHAR(64) NULL,
    reason TEXT NULL,
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_classification_confirmation_result FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cluster_revisions (
    id VARCHAR(64) PRIMARY KEY,
    source_record_id VARCHAR(64) NOT NULL,
    version INT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_cluster_revision_result FOREIGN KEY (source_record_id) REFERENCES result_records(id),
    UNIQUE KEY uk_cluster_revision (source_record_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cluster_corrections (
    id VARCHAR(64) PRIMARY KEY,
    revision_id VARCHAR(64) NOT NULL,
    action_type VARCHAR(64) NOT NULL,
    action_json JSON NOT NULL,
    actor_id VARCHAR(64) NULL,
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_cluster_correction_revision FOREIGN KEY (revision_id) REFERENCES cluster_revisions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cluster_label_confirmations (
    id VARCHAR(64) PRIMARY KEY,
    result_record_id VARCHAR(64) NOT NULL,
    cluster_id VARCHAR(128) NOT NULL,
    label_text VARCHAR(500) NOT NULL,
    actor_id VARCHAR(64) NULL,
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_label_confirmation_result FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS exports (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    task_id VARCHAR(64) NULL,
    result_record_id VARCHAR(64) NULL,
    format VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    object_key VARCHAR(1000) NULL,
    error_message TEXT NULL,
    created_at VARCHAR(40) NOT NULL,
    expires_at VARCHAR(40) NULL,
    CONSTRAINT fk_exports_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    CONSTRAINT fk_exports_task FOREIGN KEY (task_id) REFERENCES analysis_tasks(id),
    CONSTRAINT fk_exports_result FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS external_writebacks (
    id VARCHAR(64) PRIMARY KEY,
    result_record_id VARCHAR(64) NOT NULL,
    target_system VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    external_record_id VARCHAR(255) NULL,
    request_json JSON NULL,
    response_json JSON NULL,
    retry_count INT NOT NULL DEFAULT 0,
    idempotency_key VARCHAR(128) NOT NULL,
    error_message TEXT NULL,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_writeback_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    UNIQUE KEY uk_writeback_idempotency (idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(64) PRIMARY KEY,
    workspace_id VARCHAR(64) NOT NULL,
    actor_id VARCHAR(64) NULL,
    action VARCHAR(128) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    before_json JSON NULL,
    after_json JSON NULL,
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_audit_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
    KEY idx_audit_resource (resource_type, resource_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_feedback (
    id VARCHAR(64) PRIMARY KEY,
    result_record_id VARCHAR(64) NOT NULL,
    feedback_type VARCHAR(64) NOT NULL,
    rating INT NULL,
    comment TEXT NULL,
    correction_json JSON NULL,
    actor_id VARCHAR(64) NULL,
    created_at VARCHAR(40) NOT NULL,
    CONSTRAINT fk_feedback_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_feedback_result (result_record_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Vue 可视化与跨功能复用需要的结果投影表。result_records 保留完整 JSON，
-- 下列表保存需要检索、统计、确认和建立外键的字段。
CREATE TABLE IF NOT EXISTS move_results (
    result_record_id VARCHAR(64) PRIMARY KEY, document_title VARCHAR(1000) NULL,
    project_title VARCHAR(1000) NULL, statistics_json JSON NULL,
    move_count INT NULL, sentence_count INT NULL, input_type VARCHAR(64) NULL,
    overall_confidence DOUBLE NULL, document_language VARCHAR(16) NULL,
    CONSTRAINT fk_move_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS move_segments (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL,
    move_code VARCHAR(128) NULL, move_name VARCHAR(255) NULL, label VARCHAR(255) NULL,
    sentence_index INT NULL,
    start_offset INT NULL, end_offset INT NULL, text_value LONGTEXT NULL,
    source_json JSON NULL, confidence DOUBLE NULL,
    CONSTRAINT fk_move_segment_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_move_segments_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS classification_results (
    result_record_id VARCHAR(64) PRIMARY KEY, primary_code VARCHAR(128) NULL,
    primary_name VARCHAR(500) NULL, primary_path JSON NULL, primary_confidence DOUBLE NULL,
    selected_domain JSON NULL, domain_labels JSON NULL, taxonomy_version VARCHAR(128) NULL,
    confirmation_status VARCHAR(32) NULL,
    CONSTRAINT fk_classification_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS classification_candidates (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL,
    role_name VARCHAR(32) NULL, class_code VARCHAR(128) NULL, class_name VARCHAR(500) NULL,
    path_json JSON NULL, confidence DOUBLE NULL, rank_no INT NULL,
    CONSTRAINT fk_classification_candidate_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_classification_candidates_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS keyword_results (
    result_record_id VARCHAR(64) PRIMARY KEY, dictionary_usage JSON NULL, statistics_json JSON NULL,
    CONSTRAINT fk_keyword_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS keyword_items (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL,
    term VARCHAR(500) NOT NULL, normalized_term VARCHAR(500) NULL, score DOUBLE NULL,
    rank_no INT NULL, source_name VARCHAR(255) NULL, source_position JSON NULL,
    mapping_json JSON NULL,
    CONSTRAINT fk_keyword_item_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_keyword_items_result (result_record_id), KEY idx_keyword_items_term (normalized_term)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS research_question_results (
    result_record_id VARCHAR(64) PRIMARY KEY, statistics_json JSON NULL,
    CONSTRAINT fk_rq_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS research_question_items (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL, item_type VARCHAR(32) NOT NULL,
    text_value LONGTEXT NULL, structured_json JSON NULL, source_position JSON NULL, confidence DOUBLE NULL,
    CONSTRAINT fk_rq_item_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_rq_items_result (result_record_id, item_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS citation_results (
    result_record_id VARCHAR(64) PRIMARY KEY, analysis_type VARCHAR(32) NOT NULL,
    statistics_json JSON NULL,
    CONSTRAINT fk_citation_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS citation_items (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL,
    citation_id VARCHAR(128) NULL, sentence LONGTEXT NULL, label_name VARCHAR(255) NULL,
    marker_json JSON NULL, context_json JSON NULL, source_position JSON NULL,
    reference_json JSON NULL, evidence_json JSON NULL, confidence DOUBLE NULL,
    CONSTRAINT fk_citation_item_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_citation_items_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS definition_results (
    result_record_id VARCHAR(64) PRIMARY KEY, statistics_json JSON NULL,
    CONSTRAINT fk_definition_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS definition_items (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL,
    concept VARCHAR(500) NULL, normalized_concept VARCHAR(500) NULL,
    definition_text LONGTEXT NULL, sentence LONGTEXT NULL, domain_name VARCHAR(128) NULL,
    source_position JSON NULL, mapped_term_id VARCHAR(128) NULL, confidence DOUBLE NULL,
    CONSTRAINT fk_definition_item_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_definition_items_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS entity_results (
    result_record_id VARCHAR(64) PRIMARY KEY, selected_domain JSON NULL,
    ontology_version VARCHAR(128) NULL, statistics_json JSON NULL,
    CONSTRAINT fk_entity_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS entity_mentions (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL,
    entity_id VARCHAR(128) NULL, text_value VARCHAR(1000) NULL, normalized_text VARCHAR(1000) NULL,
    entity_type VARCHAR(128) NULL, start_offset INT NULL, end_offset INT NULL,
    context_text LONGTEXT NULL, kb_id VARCHAR(255) NULL, type_path JSON NULL, confidence DOUBLE NULL,
    CONSTRAINT fk_entity_mention_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_entity_mentions_result (result_record_id), KEY idx_entity_mentions_type (entity_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS relation_results (
    result_record_id VARCHAR(64) PRIMARY KEY, source_records JSON NULL, statistics_json JSON NULL,
    CONSTRAINT fk_relation_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS relation_triples (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL,
    triple_id VARCHAR(128) NULL, subject_entity_id VARCHAR(128) NULL, subject_text VARCHAR(1000) NULL,
    relation_name VARCHAR(500) NULL, relation_type VARCHAR(128) NULL,
    object_entity_id VARCHAR(128) NULL, object_text VARCHAR(1000) NULL,
    evidence_json JSON NULL, confidence DOUBLE NULL,
    CONSTRAINT fk_relation_triple_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_relation_triples_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cluster_runs (
    result_record_id VARCHAR(64) PRIMARY KEY, cluster_task_id VARCHAR(64) NULL,
    dimension_name VARCHAR(32) NULL, quality_metrics JSON NULL, correction_status VARCHAR(32) NULL,
    CONSTRAINT fk_cluster_run_result FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS clusters (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL, cluster_id VARCHAR(128) NULL,
    size_count INT NULL, representative_terms JSON NULL, centroid_document_id VARCHAR(128) NULL,
    trend_json JSON NULL,
    CONSTRAINT fk_cluster_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_clusters_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS cluster_memberships (
    id VARCHAR(64) PRIMARY KEY, cluster_row_id VARCHAR(64) NOT NULL, document_id VARCHAR(128) NULL,
    title VARCHAR(1000) NULL, similarity DOUBLE NULL,
    CONSTRAINT fk_cluster_membership_cluster FOREIGN KEY (cluster_row_id) REFERENCES clusters(id),
    KEY idx_cluster_memberships_cluster (cluster_row_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cluster_label_results (
    result_record_id VARCHAR(64) PRIMARY KEY, source_cluster_task_id VARCHAR(64) NULL,
    generation_report JSON NULL,
    CONSTRAINT fk_cluster_label_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS cluster_labels (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL, cluster_id VARCHAR(128) NULL,
    label_text VARCHAR(500) NULL, confidence DOUBLE NULL, distinctiveness DOUBLE NULL,
    alternatives JSON NULL, evidence_terms JSON NULL,
    CONSTRAINT fk_cluster_label_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_cluster_labels_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS review_results (
    result_record_id VARCHAR(64) PRIMARY KEY, review_id VARCHAR(64) NULL, topic VARCHAR(1000) NULL,
    traceability BOOLEAN NOT NULL DEFAULT TRUE, trend_analysis JSON NULL, hotspots JSON NULL,
    CONSTRAINT fk_review_result_record FOREIGN KEY (result_record_id) REFERENCES result_records(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS review_nodes (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL, node_id VARCHAR(128) NULL,
    parent_node_id VARCHAR(128) NULL, level_no INT NULL, node_type VARCHAR(32) NULL,
    title LONGTEXT NULL, content LONGTEXT NULL, evidence_ids JSON NULL,
    CONSTRAINT fk_review_node_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_review_nodes_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS review_sections (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL, section_id VARCHAR(128) NULL,
    title VARCHAR(1000) NULL, content LONGTEXT NULL, evidence_ids JSON NULL,
    CONSTRAINT fk_review_section_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_review_sections_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS review_evidence_links (
    id VARCHAR(64) PRIMARY KEY, result_record_id VARCHAR(64) NOT NULL, evidence_id VARCHAR(128) NULL,
    document_id VARCHAR(128) NULL, title VARCHAR(1000) NULL, page_no INT NULL,
    quote_text LONGTEXT NULL,
    CONSTRAINT fk_review_evidence_result FOREIGN KEY (result_record_id) REFERENCES result_records(id),
    KEY idx_review_evidence_result (result_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
