PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL
);
INSERT OR IGNORE INTO workspaces (id, name, status, created_at)
VALUES ('default', '默认工作空间', 'active', '2026-08-04T00:00:00+00:00');

CREATE TABLE IF NOT EXISTS model_versions (
    id TEXT PRIMARY KEY, tool_id TEXT NOT NULL, version TEXT NOT NULL, labels_schema TEXT,
    metrics TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL,
    UNIQUE(tool_id, version)
);
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, original_name TEXT NOT NULL, object_key TEXT,
    sha256 TEXT, size_bytes INTEGER NOT NULL DEFAULT 0, media_type TEXT, parse_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL, FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(workspace_id, sha256);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, file_id TEXT, language TEXT, title TEXT,
    abstract_text TEXT, content_text TEXT, content_hash TEXT, metadata_json TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(file_id) REFERENCES files(id)
);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(workspace_id, content_hash);
CREATE TABLE IF NOT EXISTS document_collections (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT,
    version INTEGER NOT NULL DEFAULT 1, archived_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);
CREATE TABLE IF NOT EXISTS collection_documents (
    collection_id TEXT NOT NULL, document_id TEXT NOT NULL, order_no INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(collection_id, document_id),
    FOREIGN KEY(collection_id) REFERENCES document_collections(id), FOREIGN KEY(document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS analysis_tasks (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, tool_id TEXT NOT NULL, backend_code TEXT NOT NULL,
    status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, input_type TEXT NOT NULL,
    request_payload TEXT NOT NULL, parameters_json TEXT NOT NULL, model_version TEXT,
    total INTEGER NOT NULL DEFAULT 0, success_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0, error_summary TEXT, created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL, completed_at TEXT, archived_at TEXT,
    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_history ON analysis_tasks(workspace_id, tool_id, status, created_at);
CREATE TABLE IF NOT EXISTS task_items (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, input_index INTEGER NOT NULL, status TEXT NOT NULL,
    source_json TEXT NOT NULL, error_message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES analysis_tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_task_items_task ON task_items(task_id, input_index);
CREATE TABLE IF NOT EXISTS result_records (
    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, task_item_id TEXT, tool_id TEXT NOT NULL,
    backend_code TEXT NOT NULL, result_json TEXT NOT NULL, schema_version TEXT NOT NULL DEFAULT '1.0',
    created_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES analysis_tasks(id),
    FOREIGN KEY(task_item_id) REFERENCES task_items(id)
);
CREATE INDEX IF NOT EXISTS idx_results_task ON result_records(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_results_tool ON result_records(tool_id, created_at);
CREATE TABLE IF NOT EXISTS record_dependencies (
    id TEXT PRIMARY KEY, record_id TEXT NOT NULL, upstream_record_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL, created_at TEXT NOT NULL,
    FOREIGN KEY(record_id) REFERENCES result_records(id), FOREIGN KEY(upstream_record_id) REFERENCES result_records(id),
    UNIQUE(record_id, upstream_record_id, dependency_type)
);
CREATE TABLE IF NOT EXISTS dictionaries (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, name TEXT NOT NULL, language TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active', current_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
    UNIQUE(workspace_id, name, language)
);
CREATE TABLE IF NOT EXISTS dictionary_versions (
    id TEXT PRIMARY KEY, dictionary_id TEXT NOT NULL, version INTEGER NOT NULL, weight_boost REAL NOT NULL DEFAULT 0,
    content_hash TEXT, created_at TEXT NOT NULL, FOREIGN KEY(dictionary_id) REFERENCES dictionaries(id),
    UNIQUE(dictionary_id, version)
);
CREATE TABLE IF NOT EXISTS dictionary_terms (
    id TEXT PRIMARY KEY, dictionary_version_id TEXT NOT NULL, term TEXT NOT NULL,
    normalized_term TEXT, weight REAL NOT NULL DEFAULT 1,
    FOREIGN KEY(dictionary_version_id) REFERENCES dictionary_versions(id), UNIQUE(dictionary_version_id, term)
);

CREATE TABLE IF NOT EXISTS semantic_resources (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    resource_key TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    language TEXT,
    record_count INTEGER,
    status TEXT NOT NULL DEFAULT 'current',
    source_type TEXT NOT NULL DEFAULT 'bundled',
    storage_uri TEXT,
    content_hash TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, resource_key, version),
    FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);

CREATE TABLE IF NOT EXISTS model_evaluation_runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    evaluation_type TEXT NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    metrics_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
);
CREATE INDEX IF NOT EXISTS idx_model_evaluation_runs_lookup
    ON model_evaluation_runs(workspace_id, evaluation_type, created_at);
CREATE INDEX IF NOT EXISTS idx_semantic_resources_lookup
    ON semantic_resources(workspace_id, resource_key, status, updated_at);
CREATE TABLE IF NOT EXISTS taxonomy_versions (
    id TEXT PRIMARY KEY, taxonomy_code TEXT NOT NULL, version TEXT NOT NULL, node_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, UNIQUE(taxonomy_code, version)
);
CREATE TABLE IF NOT EXISTS taxonomy_nodes (
    id TEXT PRIMARY KEY, version_id TEXT NOT NULL, parent_id TEXT, code TEXT NOT NULL,
    name_zh TEXT, name_en TEXT, level_no INTEGER, path_text TEXT,
    FOREIGN KEY(version_id) REFERENCES taxonomy_versions(id), UNIQUE(version_id, code)
);
CREATE TABLE IF NOT EXISTS ontology_versions (
    id TEXT PRIMARY KEY, ontology_code TEXT NOT NULL, version TEXT NOT NULL, node_count INTEGER NOT NULL DEFAULT 0,
    layer_counts TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL,
    UNIQUE(ontology_code, version)
);
CREATE TABLE IF NOT EXISTS ontology_nodes (
    id TEXT PRIMARY KEY, version_id TEXT NOT NULL, parent_id TEXT, kb_id TEXT, preferred_label TEXT NOT NULL,
    aliases_json TEXT, level_no INTEGER, FOREIGN KEY(version_id) REFERENCES ontology_versions(id)
);
CREATE TABLE IF NOT EXISTS classification_confirmations (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, primary_code TEXT NOT NULL, secondary_codes TEXT,
    actor_id TEXT, reason TEXT, created_at TEXT NOT NULL, FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS cluster_revisions (
    id TEXT PRIMARY KEY, source_record_id TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL, FOREIGN KEY(source_record_id) REFERENCES result_records(id), UNIQUE(source_record_id, version)
);
CREATE TABLE IF NOT EXISTS cluster_corrections (
    id TEXT PRIMARY KEY, revision_id TEXT NOT NULL, action_type TEXT NOT NULL, action_json TEXT NOT NULL,
    actor_id TEXT, created_at TEXT NOT NULL, FOREIGN KEY(revision_id) REFERENCES cluster_revisions(id)
);
CREATE TABLE IF NOT EXISTS cluster_label_confirmations (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, cluster_id TEXT NOT NULL, label_text TEXT NOT NULL,
    actor_id TEXT, created_at TEXT NOT NULL, FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS exports (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, task_id TEXT, result_record_id TEXT, format TEXT NOT NULL,
    status TEXT NOT NULL, object_key TEXT, error_message TEXT, created_at TEXT NOT NULL, expires_at TEXT,
    FOREIGN KEY(workspace_id) REFERENCES workspaces(id), FOREIGN KEY(task_id) REFERENCES analysis_tasks(id),
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS external_writebacks (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, target_system TEXT NOT NULL, status TEXT NOT NULL,
    external_record_id TEXT, request_json TEXT, response_json TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL UNIQUE, error_message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, actor_id TEXT, action TEXT NOT NULL,
    resource_type TEXT NOT NULL, resource_id TEXT NOT NULL, before_json TEXT, after_json TEXT,
    created_at TEXT NOT NULL, FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);
CREATE TABLE IF NOT EXISTS user_feedback (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, feedback_type TEXT NOT NULL,
    rating INTEGER, comment TEXT, correction_json TEXT, actor_id TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);

-- 功能专用结果投影；完整响应仍保存在 result_records.result_json。
CREATE TABLE IF NOT EXISTS move_results (
    result_record_id TEXT PRIMARY KEY, document_title TEXT, project_title TEXT, statistics_json TEXT,
    move_count INTEGER, sentence_count INTEGER, input_type TEXT,
    overall_confidence REAL, document_language TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS move_segments (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, move_code TEXT, move_name TEXT, label TEXT,
    sentence_index INTEGER, start_offset INTEGER, end_offset INTEGER, text_value TEXT,
    source_json TEXT, confidence REAL, FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS classification_results (
    result_record_id TEXT PRIMARY KEY, primary_code TEXT, primary_name TEXT, primary_path TEXT,
    primary_confidence REAL, selected_domain TEXT, domain_labels TEXT, taxonomy_version TEXT,
    confirmation_status TEXT, FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS classification_candidates (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, role_name TEXT, class_code TEXT,
    class_name TEXT, path_json TEXT, confidence REAL, rank_no INTEGER,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS keyword_results (
    result_record_id TEXT PRIMARY KEY, dictionary_usage TEXT, statistics_json TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS keyword_items (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, term TEXT NOT NULL, normalized_term TEXT,
    score REAL, rank_no INTEGER, source_name TEXT, source_position TEXT, mapping_json TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS research_question_results (
    result_record_id TEXT PRIMARY KEY, statistics_json TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS research_question_items (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, item_type TEXT NOT NULL,
    text_value TEXT, structured_json TEXT, source_position TEXT, confidence REAL,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS citation_results (
    result_record_id TEXT PRIMARY KEY, analysis_type TEXT NOT NULL, statistics_json TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS citation_items (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, citation_id TEXT, sentence TEXT,
    label_name TEXT, marker_json TEXT, context_json TEXT, source_position TEXT,
    reference_json TEXT, evidence_json TEXT, confidence REAL,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS definition_results (
    result_record_id TEXT PRIMARY KEY, statistics_json TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS definition_items (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, concept TEXT, normalized_concept TEXT,
    definition_text TEXT, sentence TEXT, domain_name TEXT, source_position TEXT,
    mapped_term_id TEXT, confidence REAL, FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS entity_results (
    result_record_id TEXT PRIMARY KEY, selected_domain TEXT, ontology_version TEXT, statistics_json TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS entity_mentions (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, entity_id TEXT, text_value TEXT,
    normalized_text TEXT, entity_type TEXT, start_offset INTEGER, end_offset INTEGER,
    context_text TEXT, kb_id TEXT, type_path TEXT, confidence REAL,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS relation_results (
    result_record_id TEXT PRIMARY KEY, source_records TEXT, statistics_json TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS relation_triples (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, triple_id TEXT, subject_entity_id TEXT,
    subject_text TEXT, relation_name TEXT, relation_type TEXT, object_entity_id TEXT,
    object_text TEXT, evidence_json TEXT, confidence REAL,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS cluster_runs (
    result_record_id TEXT PRIMARY KEY, cluster_task_id TEXT, dimension_name TEXT,
    quality_metrics TEXT, correction_status TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, cluster_id TEXT, size_count INTEGER,
    representative_terms TEXT, centroid_document_id TEXT, trend_json TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS cluster_memberships (
    id TEXT PRIMARY KEY, cluster_row_id TEXT NOT NULL, document_id TEXT, title TEXT, similarity REAL,
    FOREIGN KEY(cluster_row_id) REFERENCES clusters(id)
);
CREATE TABLE IF NOT EXISTS cluster_label_results (
    result_record_id TEXT PRIMARY KEY, source_cluster_task_id TEXT, generation_report TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS cluster_labels (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, cluster_id TEXT, label_text TEXT,
    confidence REAL, distinctiveness REAL, alternatives TEXT, evidence_terms TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS review_results (
    result_record_id TEXT PRIMARY KEY, review_id TEXT, topic TEXT, traceability INTEGER NOT NULL DEFAULT 1,
    trend_analysis TEXT, hotspots TEXT, FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS review_nodes (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, node_id TEXT, parent_node_id TEXT,
    level_no INTEGER, node_type TEXT, title TEXT, content TEXT, evidence_ids TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS review_sections (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, section_id TEXT, title TEXT,
    content TEXT, evidence_ids TEXT, FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);
CREATE TABLE IF NOT EXISTS review_evidence_links (
    id TEXT PRIMARY KEY, result_record_id TEXT NOT NULL, evidence_id TEXT, document_id TEXT,
    title TEXT, page_no INTEGER, quote_text TEXT,
    FOREIGN KEY(result_record_id) REFERENCES result_records(id)
);

CREATE INDEX IF NOT EXISTS idx_move_segments_result ON move_segments(result_record_id);
CREATE INDEX IF NOT EXISTS idx_classification_candidates_result ON classification_candidates(result_record_id);
CREATE INDEX IF NOT EXISTS idx_keyword_items_result ON keyword_items(result_record_id);
CREATE INDEX IF NOT EXISTS idx_rq_items_result ON research_question_items(result_record_id, item_type);
CREATE INDEX IF NOT EXISTS idx_citation_items_result ON citation_items(result_record_id);
CREATE INDEX IF NOT EXISTS idx_definition_items_result ON definition_items(result_record_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_result ON entity_mentions(result_record_id);
CREATE INDEX IF NOT EXISTS idx_relation_triples_result ON relation_triples(result_record_id);
CREATE INDEX IF NOT EXISTS idx_clusters_result ON clusters(result_record_id);
CREATE INDEX IF NOT EXISTS idx_cluster_labels_result ON cluster_labels(result_record_id);
CREATE INDEX IF NOT EXISTS idx_review_nodes_result ON review_nodes(result_record_id);
CREATE INDEX IF NOT EXISTS idx_feedback_result ON user_feedback(result_record_id, created_at);
