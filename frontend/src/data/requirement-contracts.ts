export type RequirementStatus = 'required' | 'optional' | 'conditional'
export type RequirementInputRow = [name: string, type: string, status: RequirementStatus, description: string]
export type RequirementOutputRow = [name: string, type: string, description: string]

export type RequirementContract = {
  inputs: RequirementInputRow[]
  outputs: RequirementOutputRow[]
}

/**
 * 业务字段唯一依据：
 * 《智慧认知大脑-语义计算工具库（张老师提出意见修改）》评审表中的
 * “算法输入与输出”与“差异项/缺失项”。
 */
export const requirementContracts: Record<string, RequirementContract> = {
  'zh-abstract-move': {
    inputs: [['chinese_scientific_abstract', 'string|file|object[]', 'required', '中文科技文献摘要文本']],
    outputs: [
      ['move_category', 'string', '语步类别'],
      ['sentence_position', 'object', '句子位置'],
      ['original_fragment', 'string', '原文片段'],
      ['confidence', 'number', '置信度评分'],
    ],
  },
  'en-abstract-move': {
    inputs: [['english_scientific_abstract', 'string|file|object[]', 'required', '英文科技论文摘要，包括 SCI/EI 期刊及国际会议论文文本']],
    outputs: [
      ['move_type', 'string', '语步类型'],
      ['sentence_position', 'object', '句子位置'],
      ['context', 'object|string', '上下文信息'],
      ['confidence', 'number', '置信度评分'],
    ],
  },
  'fund-move': {
    inputs: [
      ['project_document_text', 'string|file|object[]', 'required', '中文基金申请书、立项书或科研项目管理文件文本'],
      ['project_name', 'string', 'optional', '可用于标识结果；缺省时由系统生成记录名称或从文件解析'],
    ],
    outputs: [
      ['category_label', 'string', '项目语步类别标签'],
      ['text_position', 'object', '语步在项目材料中的文本位置；文本输入返回字符范围，文件输入返回一级、二级、三级标题路径'],
      ['original_fragment', 'string', '原文片段'],
      ['confidence', 'number', '置信度评分'],
    ],
  },
  'zh-classify': {
    inputs: [
      ['chinese_scientific_document_text', 'string|file|object[]', 'required', '中文期刊论文、会议文稿、科技报告或政策文件文本'],
      ['document_title', 'string|string[]', 'optional', '可用于标识结果；文件输入时可由系统解析'],
      ['clc_labeled_data', 'resource|file', 'required', '标准中图分类号标注数据'],
    ],
    outputs: [
      ['clc_prediction', 'object', '每篇文献的中图分类号预测结果'],
      ['classification_confidence', 'number', '分类置信度'],
      ['domain_labels', 'string[]', '领域标签'],
      ['classification_statistics_table', 'object[]', '归类统计表'],
    ],
  },
  'en-classify': {
    inputs: [
      ['english_scientific_document_text', 'string|file|object[]', 'required', '英文期刊论文、会议文稿或科研项目摘要'],
      ['document_title', 'string|string[]', 'optional', '可用于标识结果；文件输入时可由系统解析'],
      ['clc_labeled_data', 'resource|file', 'required', '标准中图分类号标注数据'],
    ],
    outputs: [
      ['clc_prediction', 'object', '中图分类号预测结果'],
      ['cross_language_category_mapping', 'object[]', '跨语言类目映射表'],
      ['domain_labels', 'string[]', '领域标签'],
      ['literature_distribution_analysis_report', 'object', '文献分布分析报告'],
    ],
  },
  'domain-classify': {
    inputs: [
      ['domain_scientific_literature_data', 'object[]|file[]|resource', 'required', '领域专业科技文献数据'],
      ['document_title', 'string|string[]', 'optional', '可用于标识结果；文件输入时可由系统解析'],
      ['professional_domain', 'string', 'required', '在线测试中由用户选择的目标专业领域'],
      ['domain_classification_rules', 'resource|file', 'required', '领域分类规则'],
      ['manually_labeled_training_data', 'resource|file', 'required', '人工标注训练数据'],
    ],
    outputs: [
      ['multilevel_domain_classification', 'object[]', '多层级领域分类结果'],
      ['classification_confidence', 'number|object', '分类置信度'],
      ['domain_labels', 'string[]', '领域标签'],
      ['data_distribution_report', 'object', '数据分布报告'],
    ],
  },
  'zh-keyword': {
    inputs: [
      ['chinese_scientific_abstract', 'string|file|object[]', 'required', '中文科技文献摘要'],
      ['document_title', 'string|string[]', 'optional', '可用于标识结果；文件输入时可由系统解析'],
      ['domain_terminology_dictionary', 'resource|file', 'optional', '可选领域术语词典'],
    ],
    outputs: [['structured_keywords', 'object[]', '结构化关键词列表']],
  },
  'en-keyword': {
    inputs: [
      ['english_scientific_abstract', 'string|file|object[]', 'required', '英文科研文献摘要'],
      ['document_title', 'string|string[]', 'optional', '可用于标识结果；文件输入时可由系统解析'],
      ['domain_terminology_library', 'resource|file', 'required', '领域术语库'],
      ['classification_standard_mapping_table', 'resource|file', 'required', '分类标准映射表'],
    ],
    outputs: [['structured_keywords_or_topic_phrases', 'object[]', '结构化关键词或主题短语列表']],
  },
  'rq-detect': {
    inputs: [
      ['scientific_document_fragment', 'string|file|object[]', 'required', '科技文献文本片段'],
      ['document_title', 'string|string[]', 'optional', '可用于标识结果；文件输入时可由系统解析'],
      ['text_format_requirement', 'string', 'optional', '文本格式要求；未提供时由系统自动识别'],
    ],
    outputs: [
      ['research_question_sentences', 'object[]', '研究问题句列表'],
      ['research_question_phrases', 'object[]', '对应研究问题短语列表'],
      ['structured_research_questions', 'object[]', '结构化研究问题数据'],
      ['research_question_statistics', 'object', '研究问题统计摘要'],
    ],
  },
  'citation-sentiment': {
    inputs: [
      ['scientific_document_full_text', 'string|file|object[]', 'required', '科技文献全文数据'],
      ['citation_sentence_and_context', 'object|object[]', 'required', '引用句及其上下文'],
      ['citation_metadata', 'object|object[]|file', 'required', '被引文献元数据'],
    ],
    outputs: [
      ['citation_sentiment_results', 'object[]', '带支持、中立或有局限性标签的引用识别结果清单'],
      ['context_fragments', 'object[]', '上下文片段'],
      ['confidence', 'number', '置信度评分'],
    ],
  },
  'citation-intent': {
    inputs: [
      ['citation_sentence_and_context', 'object|object[]', 'required', '引用句文本与上下文'],
      ['citation_metadata', 'object|object[]|file', 'required', '被引文献元数据'],
      ['preprocessed_training_set', 'resource|file', 'required', '预处理后的训练集'],
    ],
    outputs: [
      ['citation_intent_label', 'string', '引用意图标签'],
      ['citation_sentence', 'string', '对应引用句'],
      ['context_fragment', 'object|string', '上下文片段'],
      ['confidence', 'number', '置信度评分'],
    ],
  },
  'definition-detect': {
    inputs: [
      ['scientific_document_fragment_or_batch_text', 'string|object[]|file|file[]', 'required', '待处理科技文献全文片段或批量文本数据'],
      ['domain_label', 'string', 'optional', '可选领域标签'],
      ['output_format_requirement', 'string', 'optional', '输出格式要求'],
    ],
    outputs: [
      ['definition_sentences', 'object[]', '概念定义句列表'],
      ['concept_terms', 'object[]', '概念词提取结果'],
      ['concept_definition_mappings', 'object[]', '结构化概念—定义映射数据'],
      ['statistical_analysis_report', 'object', '识别统计分析报告'],
    ],
  },
  'general-ner': {
    inputs: [
      ['bilingual_scientific_document_text', 'string|object[]|file|file[]', 'required', '中英文科技文献文本'],
      ['general_domain_annotated_corpus', 'resource|file', 'required', '通用领域标注语料'],
    ],
    outputs: [['entities', 'object[]', '包含实体类别、位置和语境片段的列表；文本输入返回字符范围，文件输入返回标题层级路径']],
  },
  'research-ner': {
    inputs: [
      ['academic_abstract_or_technical_report_text', 'string|object[]|file|file[]', 'required', '中英文学术论文摘要或技术报告文本'],
      ['multi_domain_scientific_corpus', 'resource|file', 'required', '多领域科研语料'],
      ['manually_labeled_data', 'resource|file', 'required', '人工标注数据'],
    ],
    outputs: [
      ['entity_type', 'string', '科研实体类型'],
      ['sentence_position', 'object', '句子位置；文本输入返回字符范围，文件输入返回一级、二级、三级标题路径'],
      ['associated_context', 'object|string', '关联上下文'],
      ['standard_term_mapping', 'object', '映射标准词表'],
    ],
  },
  'domain-ner': {
    inputs: [
      ['domain_scientific_document_text', 'string|object[]|file|file[]', 'required', '专业科研文献文本'],
      ['ontology_classification_system', 'resource|file', 'required', '本体分类体系'],
      ['domain_labeled_training_data', 'resource|file', 'required', '领域标注训练数据'],
    ],
    outputs: [
      ['entity_type', 'string', '按领域类别细分的实体类型'],
      ['entity_position', 'object', '实体位置；文本输入返回字符范围，文件输入返回一级、二级、三级标题路径'],
      ['domain_label', 'string', '领域标签'],
      ['standard_knowledge_base_mapping_id', 'string', '标准知识库映射 ID'],
    ],
  },
  'relation-extract': {
    inputs: [
      ['upstream_ner_record_id', 'string', 'required', '数据库中已完成的命名实体识别历史记录编号；后端据此读取原始句子和实体列表'],
    ],
    outputs: [
      ['relation_triples', 'object[]', '实体关系三元组'],
      ['dependency_parse', 'object[]', '工具内部生成的依存句法分析结果，包含句子编号、中心词、依存关系和依存词'],
      ['dependency_paths', 'object[]', '实体关系三元组对应的依存句法路径'],
      ['context_fragments', 'object[]', '上下文片段'],
      ['confidence', 'number', '置信度评分'],
      ['rdf_representation', 'string|object', '关系三元组对应的 RDF 表示'],
    ],
  },
  'deep-cluster': {
    inputs: [
      ['scientific_document_texts', 'object[]|file[]', 'required', '用户上传的多篇科技文献文本或文件'],
      ['document_metadata', 'object[]', 'required', '用户随每篇文本或文件填写的对应文献元数据，与待聚类内容一一关联'],
      ['cluster_dimension', 'string', 'required', '在线测试选择的聚类维度：技术路线或应用场景'],
      ['clustering_algorithm_type', 'string', 'optional', '调用时可指定聚类算法类型'],
      ['cluster_count', 'integer', 'optional', '调用时可指定类簇数量'],
      ['output_format', 'string', 'optional', '调用时可指定输出格式'],
    ],
    outputs: [
      ['cluster_results', 'object[]', '聚类结果类簇'],
      ['cluster_feature_statistics', 'object', '类簇特征统计'],
      ['topic_trend_analysis', 'object', '主题趋势分析结果'],
    ],
  },
  'cluster-label': {
    inputs: [
      ['cluster_phrase_sets', 'object[]', 'required', '深度聚类模型输出的类簇短语集合'],
      ['label_length_limit', 'integer', 'optional', '标签长度限制'],
      ['language_type', 'string', 'optional', '语言类型'],
      ['distinctiveness_threshold', 'number', 'optional', '差异度阈值，范围 0—1'],
    ],
    outputs: [
      ['cluster_labels', 'object[]', '类簇标签集合'],
      ['label_generation_process_report', 'object', '标签生成过程报告'],
      ['label_distinctiveness_optimization_result', 'object', '标签差异化优化结果'],
    ],
  },
  'structured-review': {
    inputs: [
      ['document_set', 'object[]|file[]|resource', 'required', '科技文献检索结果集或指定文献集'],
      ['topic_or_keywords', 'string|string[]', 'required', '研究主题或关键词'],
      ['document_metadata', 'object[]|resource|file', 'required', '文献元数据'],
    ],
    outputs: [
      ['three_level_review_tree', 'object[]', '研究问题—研究方法—研究进展三层树形结构综述视图'],
      ['cluster_induction_results', 'object', '聚类及类簇归纳结果'],
      ['structured_text_review_report', 'object', '结构化文本综述报告'],
      ['trend_and_hotspot_distribution', 'object', '趋势分析与研究热点分布图'],
    ],
  },
}

export const requirementInputsFor = (toolId: string) => requirementContracts[toolId]?.inputs || []
export const requirementOutputsFor = (toolId: string) => requirementContracts[toolId]?.outputs || []


