"""Truthful resource registrations bundled with this source distribution.

Counts are intentionally omitted.  Deployments may register larger server-side
datasets through ``POST /api/v1/semantic-resources`` without changing Vue.
"""

BUNDLED_SEMANTIC_RESOURCES = (
    ("RES-BUNDLED-CLC-ZH", "clc_labeled_data", "内置中图分类标注与检索资源", "project://rag_store/clc_rag", "zh-en"),
    ("RES-BUNDLED-DOMAIN-RULE", "domain_classification_rules", "内置专业领域分类规则", "project://rules/auto_classification/ac_domain.yaml", "zh-en"),
    ("RES-BUNDLED-DOMAIN-GOLD", "manually_labeled_training_data", "内置专业领域标注样本", "project://data/datasets/professional_domain_64_classification.json", "zh-en"),
    ("RES-BUNDLED-EN-TERM", "domain_terminology_library", "内置英文科技术语资源", "project://rules/keyword_recognition/kw_en_model.json", "en"),
    ("RES-BUNDLED-EN-CLASS-MAP", "classification_standard_mapping_table", "内置英文术语分类映射资源", "project://rag_store/clc_rag", "zh-en"),
    ("RES-BUNDLED-CITATION-INTENT", "preprocessed_training_set", "内置引用意图规则与训练配置", "project://rules/citation_recognition/cr_intent.yaml", "zh-en"),
    ("RES-BUNDLED-NER-GENERAL", "general_domain_annotated_corpus", "内置通用实体标注与映射资源", "project://data/ner/ner_general_gold.json", "zh-en"),
    ("RES-BUNDLED-NER-RESEARCH", "multi_domain_scientific_corpus", "内置多领域科研实体语料配置", "project://rules/ner/ner_research.yaml", "zh-en"),
    ("RES-BUNDLED-NER-RESEARCH-GOLD", "manually_labeled_data", "内置科研实体人工标注数据", "project://data/ner/ner_research_gold.json", "zh-en"),
    ("RES-BUNDLED-ONTOLOGY", "ontology_classification_system", "内置专业领域本体映射体系", "project://rules/ner/mappings/ner_domain_mapping.json", "zh-en"),
    ("RES-BUNDLED-DOMAIN-NER-GOLD", "domain_labeled_training_data", "内置专业领域实体标注配置", "project://rules/ner/ner_domain.yaml", "zh-en"),
    ("RES-BUNDLED-CLUSTER-TRAIN", "training_samples", "内置深度聚类训练样本", "project://rules/deep_clustering/v7_reference/gold/gold_zh_model_reviewed_round3_1000.json", "zh"),
    ("RES-BUNDLED-CLUSTER-GOLD", "manually_labeled_category_data", "内置深度聚类人工标注类目标签数据", "project://rules/deep_clustering/v7_reference/gold/gold_zh_model_reviewed_round3_1000.json", "zh"),
)
