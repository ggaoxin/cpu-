"""字段映射审查：逐工具调用 Vue 接口，检查契约 result_fields 是否被真实数据填充。

判定逻辑：
- 空：None / [] / {} / "" / 0（当该字段本应有内容时）
- 填充：有真实内容
- 可疑映射断裂：契约字段为空，但响应 data 里存在【非契约键】持有真实内容
  （即 GLM 输出了数据，但归一化器没把它映射到契约字段 —— 正是语步识别那种 bug）
"""
import json
import sys
import httpx

BASE = "http://127.0.0.1:8000/api/v1"
TIMEOUT = 120.0

# (tool_id, route, payload)
TEXT_ABSTRACT = "为提升科技文献检索精度，本文提出一种基于深度语义的匹配方法，融合预训练语言模型与规则特征。实验表明F1提升5%。"

CASES = [
    ("zh-abstract-move", "/move/abstract/zh/text", {"chinese_scientific_abstract": "为提升科技文献检索精度，本文提出一种基于深度语义的匹配方法，融合预训练语言模型与规则特征。首先构建双塔检索架构，随后在自建数据集上评测。实验表明F1提升5%。研究表明该方法显著优于基线。综上，深度语义方法可有效提升检索精度。", "document_title": "语义匹配研究"}),
    ("en-abstract-move", "/move/abstract/en/text", {"english_scientific_abstract": "To improve retrieval accuracy, we propose a deep semantic matching method combining pretrained models with rule features. We first build a dual-tower retrieval architecture, then evaluate on a dataset. Experiments show F1 improved by 5%. The results indicate our method outperforms baselines. In conclusion, deep semantic matching effectively improves retrieval precision.", "document_title": "Semantic Matching Research"}),
    ("fund-move", "/move/fund/zh/text", {"project_name": "深度语义检索关键技术研究", "project_document_text": "## 立项依据\n当前科技文献检索精度不足，长尾查询召回率低，亟需深度语义方法突破。## 研究目标\n提出基于深度语义的匹配方法，显著提升检索F1。## 技术方案\n融合预训练语言模型与规则特征，构建双塔检索架构。## 预期成果\n在自建数据集上F1提升5%，申请发明专利2项。## 应用价值\n成果可部署于科技文献服务平台，服务千万级用户检索。"}),
    ("zh-classify", "/classify/clc/zh/text", {"chinese_scientific_document_text": "本文针对科技文献检索问题，提出基于深度语义的匹配方法，结合BERT与规则特征，在自建数据集上F1提升5%。", "document_title": "深度语义匹配方法研究", "clc_labeled_data": {"source": "database", "resource_id": "RES-BUNDLED-CLC-ZH"}}),
    ("en-classify", "/classify/clc/en/text", {"english_scientific_document_text": "We propose a deep semantic matching method for scientific literature retrieval, combining BERT with rule features. F1 improved by 5%.", "document_title": "Deep Semantic Matching", "clc_labeled_data": {"source": "database", "resource_id": "RES-BUNDLED-CLC-ZH"}}),
    ("domain-classify", "/classify/domain/text", {"domain_scientific_literature_data": "本文研究锂离子电池正极材料，采用三元材料NCM811，通过掺杂改性提升循环寿命，容量保持率提高12%。", "document_title": "NCM811正极材料改性", "domain": "materials_science", "domain_classification_rules": {"source": "database", "resource_id": "RES-BUNDLED-DOMAIN-RULE"}, "manually_labeled_training_data": {"source": "database", "resource_id": "RES-BUNDLED-DOMAIN-GOLD"}}),
    ("zh-keyword", "/keywords/zh/text", {"chinese_scientific_abstract": "为提升科技文献检索精度，本文提出基于深度语义的匹配方法，结合预训练语言模型与规则特征，实验表明F1提升5%。"}),
    ("en-keyword", "/keywords/en/text", {"english_scientific_abstract": "To improve retrieval accuracy, we propose a deep semantic matching method combining pretrained models with rule features. F1 improved by 5%.", "domain_terminology_library": {"source": "database", "resource_id": "RES-BUNDLED-EN-TERM"}, "classification_standard_mapping_table": {"source": "database", "resource_id": "RES-BUNDLED-EN-CLASS-MAP"}}),
    ("rq-detect", "/research-question/text", {"document_title":"语义匹配研究","scientific_document_fragment": "如何在大规模科技文献中实现高精度语义匹配？现有方法在长尾查询上表现不佳。本文探究深度语义模型能否缓解该问题。"}),
    ("citation-sentiment", "/citation-sentiment/text", {"document_title":"语义检索对比研究","scientific_document_full_text": "已有研究[1]提出基于词袋的检索方法，但精度有限。本文方法优于该工作[1]，F1提升5%。", "citation_sentence_and_context": [{"citation_sentence": "本文方法优于该工作[1]，F1提升5%。", "previous_context": "已有研究[1]提出基于词袋的检索方法，但精度有限。", "next_context": "这验证了深度语义方法的有效性。"}], "citation_metadata": [{"marker": "[1]", "title": "Bag-of-words retrieval", "year": 2020}]}),
    ("citation-intent", "/citation-intent/text", {"document_title":"注意力机制扩展研究","citation_sentence_and_context": [{"citation_sentence": "本文借鉴Smith[2]的注意力机制，将其扩展至语义匹配。", "previous_context": "在相关工作部分，", "next_context": "从而实现端到端的语义建模。"}], "citation_metadata": [{"marker": "[2]", "title": "Attention mechanism", "year": 2019}], "preprocessed_training_set": {"source": "database", "resource_id": "RES-BUNDLED-CITATION-INTENT"}}),
    ("definition-detect", "/concept-definition/text", {"document_title":"语义匹配概念定义","scientific_document_fragment_or_batch_text": "语义匹配是指通过计算文本深层语义相似度来匹配查询与文档的技术。深度语义模型基于Transformer架构，能够捕获上下文语义。"}),
    ("general-ner", "/ner/general/text", {"document_title":"BERT训练实验","bilingual_scientific_document_text": "本文由张三于清华大学完成，与Google合作，在斯坦福大学交流期间使用TPU集群训练BERT模型。Zhang San worked at Tsinghua University and Google.", "general_domain_annotated_corpus": {"source": "database", "resource_id": "RES-BUNDLED-NER-GENERAL"}}),
    ("research-ner", "/ner/research/text", {"document_title":"对比学习科研实体","academic_abstract_or_technical_report_text": "本研究采用对比学习方法，使用ResNet-50作为骨干网络，在CIFAR-10数据集上实验，工具为TensorFlow。", "multi_domain_scientific_corpus": {"source": "database", "resource_id": "RES-BUNDLED-NER-RESEARCH"}, "manually_labeled_data": {"source": "database", "resource_id": "RES-BUNDLED-NER-RESEARCH-GOLD"}}),
    ("domain-ner", "/ner/domain/text", {"document_title":"电网负荷预测","domain_scientific_document_text": "本文研究电网负荷预测，采用LSTM模型，使用省级电网调度数据，部署于国产DCS控制系统。", "domain": "电力工程", "ontology_classification_system": {"source": "database", "resource_id": "RES-BUNDLED-ONTOLOGY"}, "domain_labeled_training_data": {"source": "database", "resource_id": "RES-BUNDLED-DOMAIN-NER-GOLD"}}),
    # batch-text 工具
    ("deep-cluster", "/cluster/deep/texts", {"scientific_document_texts": ["本文提出深度语义匹配方法，结合BERT。", "本研究采用知识图谱增强检索，使用TransE。", "我们基于对比学习优化向量召回，采用SimCSE。", "本文设计交互式语义匹配网络，基于RoBERTa。"], "document_metadata": [{"document_id": "DOC001", "publication_date": "2023-01-15", "title": "doc1"}, {"document_id": "DOC002", "publication_date": "2023-03-20", "title": "doc2"}, {"document_id": "DOC003", "publication_date": "2023-06-10", "title": "doc3"}, {"document_id": "DOC004", "publication_date": "2023-09-01", "title": "doc4"}], "cluster_dimension": "technology", "cluster_count": 2}),
    ("cluster-label", "/cluster-labels/texts", {"cluster_phrase_sets": [{"cluster_id": "C1", "phrases": ["深度语义", "BERT", "语义匹配"]}, {"cluster_id": "C2", "phrases": ["知识图谱", "TransE", "图检索"]}]}),
    ("structured-review", "/review/structured/texts", {"document_set": ["本文提出深度语义匹配方法，结合BERT与规则，F1提升5%。", "本研究采用知识图谱增强检索，TransE建模，召回率提升8%。", "我们基于对比学习优化向量召回，SimCSE方法。"], "document_metadata": [{"document_id": "text1", "publication_date": "2023-01-15"}, {"document_id": "text2", "publication_date": "2023-03-20"}, {"document_id": "text3", "publication_date": "2023-06-10"}], "topic_or_keywords": "语义检索"}),
]

# relation-extract 单独处理（需要 upstream NER record_id）
RELATION_CASE = ("relation-extract", "/relation/from-ner-record", None)

# 契约 result_fields（从 capabilities 同步）
RESULT_FIELDS = {
    "zh-abstract-move": ["document", "moves", "move_count", "sentence_count", "input_type"],
    "en-abstract-move": ["document", "moves", "move_count", "sentence_count", "input_type"],
    "fund-move": ["document", "moves", "move_count", "input_type"],
    "zh-classify": ["is_interdisciplinary", "classifications", "classification_confidence", "domain_labels", "candidate_classifications"],
    "en-classify": ["is_interdisciplinary", "classifications", "classification_confidence", "cross_language_mapping", "domain_labels", "candidate_classifications", "literature_distribution_analysis_report"],
    "domain-classify": ["professional_domain", "multilevel_classification_results", "classification_confidence", "domain_labels", "candidate_classifications", "data_distribution_report"],
    "zh-keyword": ["document", "keywords", "keyword_count"],
    "en-keyword": ["document", "keywords_or_topic_phrases", "term_count"],
    "rq-detect": ["document", "research_question_sentences", "research_question_phrases", "structured_research_questions", "research_question_statistics"],
    "citation-sentiment": ["document", "citation_sentiment_results", "citation_sentiment_statistics"],
    "citation-intent": ["document", "citation_intent_results", "citation_intent_statistics"],
    "definition-detect": ["document", "definitions", "concept_definition_mappings", "statistical_analysis_report"],
    "general-ner": ["document", "entities", "summary"],
    "research-ner": ["document", "entities", "standard_term_mappings", "summary"],
    "domain-ner": ["document", "selected_domain", "entities", "ontology_mappings", "summary"],
    "relation-extract": ["upstream_ner_record_id", "original_sentence", "dependency_parse", "dependency_paths", "relation_triples", "context_fragments", "rdf_representation"],
    "deep-cluster": ["cluster_dimension", "cluster_dimension_name", "input_summary", "clustering_quality", "training_evaluation", "clusters", "document_assignments", "semantic_projection", "theme_trend_analysis"],
    "cluster-label": ["cluster_count", "generated_label_count", "parameters", "labels", "statistics", "label_generation_process_report", "label_distinctiveness_optimization_result"],
    "structured-review": ["review_id", "topic", "document_count", "statistics", "tree", "cluster_induction_results", "structured_report", "trend_hotspot_distribution", "evidence_index"],
}

# 已知的「合法非契约附加键」（归一化器主动加的兼容/元信息键，不算映射断裂）
KNOWN_EXTRA = {
    "input_type", "document", "statistics", "evidence", "confidence", "raw",
    "distribution_report", "cross_language_mapping",
    "move_statistics", "move_count", "sentence_count", "moves",
    "classifications", "primary_classification", "candidates", "confirmation_status",
    "manual_confirmation", "domain_labels", "levels", "selected_domain",
    "keywords", "keywords_or_topic_phrases", "keyword_count", "term_count", "dictionary_usage",
    "entities", "entity_results", "mappings", "entity_mappings", "ontology_mappings", "standard_term_mappings", "summary",
    "citations", "statistics",
    "definitions", "definition_results", "mappings", "concept_definition_mappings",
    "triples", "relation_triples", "relation_results", "relations", "source_records",
    "dependency_parse_executed_internally", "statistics",
    "clusters", "labels", "dimension", "quality_metrics", "correction_status",
    "generation_report", "alternatives", "evidence",
    "cluster_count", "generated_label_count",
    "writeback", "taxonomy_version", "ontology_version",
    "document_title",
}


def is_empty(v):
    if v is None: return True
    if isinstance(v, (list, dict, str)) and len(v) == 0: return True
    return False


def has_real_content(v):
    """递归判断是否含真实内容（非空且非纯占位）。"""
    if is_empty(v): return False
    if isinstance(v, str): return v.strip() not in ("", "—", "-", "null", "None")
    if isinstance(v, (int, float)): return True
    if isinstance(v, list): return any(has_real_content(x) for x in v)
    if isinstance(v, dict): return any(has_real_content(x) for x in v.values())
    return bool(v)


def call(route, payload, client):
    r = client.post(BASE + route, json=payload, timeout=TIMEOUT)
    return r.json()


def analyze(tool_id, resp):
    if resp.get("code") != 0:
        return f"  [调用失败] code={resp.get('code')} msg={resp.get('message')}"
    data = resp.get("data") or {}
    fields = RESULT_FIELDS[tool_id]
    lines = []
    empty_fields = []
    for f in fields:
        v = data.get(f)
        status = "空" if is_empty(v) else ("有内容" if has_real_content(v) else "占位")
        if is_empty(v) or not has_real_content(v):
            empty_fields.append(f)
        lines.append(f"    {f:42s} {status}")
    # 检测未映射的原始键：data 中有真实内容、但不属于契约字段、也不在已知附加键里
    contract_set = set(fields)
    unmapped = []
    for k, v in data.items():
        if k in contract_set or k in KNOWN_EXTRA:
            continue
        if has_real_content(v):
            preview = json.dumps(v, ensure_ascii=False)[:60]
            unmapped.append(f"{k}={preview}")
    verdict = "OK" if not empty_fields else f"空字段:{empty_fields}"
    if unmapped:
        verdict += f"  ⚠️未映射原始键:{unmapped}"
    lines.append(f"  --> {verdict}")
    return "\n".join(lines)


def main():
    client = httpx.Client()
    # relation-extract: 先跑 general-ner 拿 record_id
    relation_record = None
    for tool_id, route, payload in CASES:
        try:
            resp = call(route, payload, client)
            print(f"\n=== {tool_id} ({route}) ===")
            print(analyze(tool_id, resp))
            if tool_id == "general-ner":
                # 从 meta 拿 record_id 供 relation-extract 用
                meta = resp.get("meta") or {}
                relation_record = meta.get("record_id")
                # batch 模式可能在 results 里
                if not relation_record and isinstance(resp.get("data"), dict):
                    results = resp["data"].get("results") or []
                    relation_record = results[0].get("record_id") if results else None
        except Exception as e:
            print(f"\n=== {tool_id} ({route}) ===\n  [异常] {e}")

    # relation-extract
    if relation_record:
        try:
            resp = call(RELATION_CASE[1], {"upstream_ner_record_id": relation_record, "upstream_entity_record_id": relation_record}, client)
            print(f"\n=== relation-extract ({RELATION_CASE[1]}) record={relation_record} ===")
            print(analyze("relation-extract", resp))
        except Exception as e:
            print(f"\n=== relation-extract ===\n  [异常] {e}")
    else:
        print("\n=== relation-extract ===\n  跳过：未拿到 upstream NER record_id")


if __name__ == "__main__":
    main()
