export type RequirementStatus = 'required' | 'optional' | 'conditional'
export type RequirementInputRow = [name: string, type: string, status: RequirementStatus, description: string]
export type RequirementOutputRow = [name: string, type: string, description: string]

export type RequirementContract = {
  inputs: RequirementInputRow[]
  outputs: RequirementOutputRow[]
}

/**
 * 各功能点请求参数定义(接口数据结构)。
 *
 * 字段命名规则:
 * - 嵌套对象/数组字段用 `field[].sub_field` 表示数组元素的字段
 * - 资源引用统一结构 `{source, resource_id}` / `{source, file}`,逐字段展开说明
 *
 * 必填状态:
 * - required:所有请求必填
 * - conditional:满足前置条件时必填(说明中注明条件)
 * - optional:可选
 */

/** 资源引用结构的公共字段说明(展开在每个资源参数之后) */
const resourceDescriptorRows = (field: string, resourceDesc: string, uploadHint: string): RequirementInputRow[] => [
  [field, 'object', 'required', resourceDesc],
  [`${field}.source`, 'string', 'required', '资源提供方式。枚举:`database`(从系统资源库选择)、`upload`(用户上传)'],
  [`${field}.resource_id`, 'string', 'conditional', '`source=database` 时必填。资源库中的资源编号(如 RES-BUNDLED-XXX)'],
  [`${field}.file`, 'file', 'conditional', '`source=upload` 时必填(仅 multipart 表单模式)。' + uploadHint],
]

export const requirementContracts: Record<string, RequirementContract> = {
  // ==================== 语步识别 ==================== #
  'zh-abstract-move': {
    inputs: [
            ['document_title', 'string | string[]', 'required', '文献题目,用于响应结果标识与可视化弹窗展示'],
            ['chinese_scientific_abstract', 'string | string[] | file | file[]', 'required', '中文科技文献摘要'],
    ],
    outputs: [
      ['move_category', 'string', '语步类别'],
      ['sentence_position', 'object', '句子位置'],
      ['original_fragment', 'string', '原文片段'],
      ['confidence', 'number', '置信度评分'],
    ],
  },
  'en-abstract-move': {
    inputs: [
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['english_scientific_abstract', 'string | string[] | file | file[]', 'required', '英文科技论文摘要(含 SCI/EI 期刊及国际会议论文)'],
    ],
    outputs: [
      ['move_type', 'string', '语步类型'],
      ['sentence_position', 'object', '句子位置'],
      ['context', 'object | string', '上下文信息'],
      ['confidence', 'number', '置信度评分'],
    ],
  },
  'fund-move': {
    inputs: [
            ['project_name', 'string | string[]', 'required', '项目名称,用于响应结果标识'],
            ['project_document_text', 'string | string[] | file | file[]', 'required', '中文基金申请书/立项书/科研项目管理文件'],
    ],
    outputs: [
      ['category_label', 'string', '项目语步类别标签'],
      ['text_position', 'object', '语步在项目材料中的文本位置;文本输入返回字符范围,文件输入返回标题路径'],
      ['original_fragment', 'string', '原文片段'],
      ['confidence', 'number', '置信度评分'],
    ],
  },

  // ==================== 自动分类 ==================== #
  'zh-classify': {
    inputs: [
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['chinese_scientific_document_text', 'string | string[] | file | file[]', 'required', '中文科技文献文本'],
      ...resourceDescriptorRows('clc_labeled_data',
        '中图分类标准数据引用。决定分类答案空间:内置资源含 40912 条中图类目及向量索引',
        '自定义分类体系 JSON 文件(类目数组,每条含 clc_code + clc_name;>50 条自动建向量索引)'),
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
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['english_scientific_document_text', 'string | string[] | file | file[]', 'required', '英文科技文献文本'],
      ...resourceDescriptorRows('clc_labeled_data',
        '中图分类标准数据引用(与中文分类共用同一资源)。内置 bge-m3 跨语言索引支持英文→中文类目直接映射',
        '自定义分类体系 JSON 文件(格式同中文)'),
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
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['domain_scientific_literature_data', 'string | string[] | file | file[]', 'required', '专业领域科技文献文本'],
      ['professional_domain', 'string', 'required', '目标专业领域编码,取值 "01"–"32"(如 "14"=材料科学与材料工程);在该领域语境下执行中图法三级分类'],
      ...resourceDescriptorRows('domain_classification_rules',
        '领域分类规则引用。定义 32 领域清单、领域与中图类号段映射、三级分类粒度要求;用户上传自定义版本可覆盖判定口径',
        '自定义规则文件(补充分类原则/强制指令,注入提示词)'),
      ...resourceDescriptorRows('manually_labeled_training_data',
        '人工标注训练数据引用。64 条标注样本(文献+领域+正确中图类号),注入提示词作 few-shot 参考校准标注风格',
        '自定义标注样本 JSON 文件(sample_id/title/abstract/domain_code/clc_classification)'),
    ],
    outputs: [
      ['multilevel_domain_classification', 'object[]', '多层级领域分类结果'],
      ['classification_confidence', 'number | object', '分类置信度'],
      ['domain_labels', 'string[]', '领域标签'],
      ['data_distribution_report', 'object', '数据分布报告'],
    ],
  },

  // ==================== 关键词识别 ==================== #
  'zh-keyword': {
    inputs: [
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['chinese_scientific_abstract', 'string | string[] | file | file[]', 'required', '中文科技文献摘要'],
      ['dictionary_id', 'string', 'optional', '用户词典编号(可选)。已保存词典的编号;词典术语在原文逐字出现时加权提升并归一到规范表达'],
      ['custom_dictionary', 'object', 'optional', '直接提交的自定义词典(与 dictionary_id 二选一)'],
      ['custom_dictionary.terms', 'string[]', 'conditional', '词典术语列表(直接提交词典时必填)'],
      ['custom_dictionary.weight_boost', 'number', 'optional', '命中加权增量,范围 0–0.5,默认 0.08'],
    ],
    outputs: [['structured_keywords', 'object[]', '结构化关键词列表']],
  },
  'en-keyword': {
    inputs: [
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['english_scientific_abstract', 'string | string[] | file | file[]', 'required', '英文科研文献摘要'],
      ...resourceDescriptorRows('domain_terminology_library',
        '领域术语库引用。英文术语归一(normalized_term)与消歧的主要来源',
        '自定义术语库 JSON 文件(domain_terms 数组,每条含 canonical + variants)'),
      ...resourceDescriptorRows('classification_standard_mapping_table',
        '分类标准映射表引用。关键词到中图类目映射(classification_mapping 字段)的来源;显式条目确定性覆盖,大表(>50条)自动建向量索引',
        '自定义映射 JSON 文件(entries 数组,每条含 term + clc_code + clc_name)'),
    ],
    outputs: [['structured_keywords_or_topic_phrases', 'object[]', '结构化关键词或主题短语列表']],
  },

  // ==================== 研究问题识别 ==================== #
  'rq-detect': {
    inputs: [
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['scientific_document_fragment', 'string | string[] | file | file[]', 'required', '科技文献文本片段或全文'],
      ['text_format_requirement', 'string', 'optional', '文本格式声明,影响溯源方式。枚举:"自动识别"(默认)、"纯文本"(跳过章节解析)、"章节结构文本"(启用标题路径溯源)、"JSON 结构文本"(按章节结构精确归属)'],
    ],
    outputs: [
      ['research_question_sentences', 'object[]', '研究问题句列表'],
      ['research_question_phrases', 'object[]', '对应研究问题短语列表'],
      ['structured_research_questions', 'object[]', '结构化研究问题数据'],
      ['research_question_statistics', 'object', '研究问题统计摘要'],
    ],
  },

  // ==================== 引用句识别 ==================== #
  'citation-sentiment': {
    inputs: [
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['scientific_document_full_text', 'string | string[] | file | file[]', 'required', '文献全文文本'],
      ['reference_entries', 'string | file', 'required', '参考文献原始条目(每行一条,支持多条)。系统据此自动解析被引文献元数据(作者/题名/年份/来源/DOI),并按引用标记号与条目序号匹配'],
      ['citation_sentence_and_context', 'object[]', 'conditional', '引用句及上下文(自动派生,无需手填)。系统从文献文本定位含引用标记的句子并取前后句;手动提供时以所填为准'],
      ['citation_sentence_and_context[].citation_sentence', 'string', 'conditional', '引用句原文(含引用标记,如 [1])'],
      ['citation_sentence_and_context[].previous_context', 'string', 'conditional', '引用句上文'],
      ['citation_sentence_and_context[].next_context', 'string', 'conditional', '引用句下文'],
      ['citation_metadata', 'object[]', 'conditional', '被引文献元数据(自动派生,无需手填)。由参考文献条目解析得到'],
      ['citation_metadata[].citation_marker', 'string', 'conditional', '引用标记,如 "[12]"'],
      ['citation_metadata[].title', 'string', 'conditional', '被引文献题名'],
      ['citation_metadata[].authors', 'string[]', 'conditional', '作者列表'],
      ['citation_metadata[].year', 'string | number', 'conditional', '发表年份'],
      ['citation_metadata[].venue', 'string', 'conditional', '期刊/会议名称'],
    ],
    outputs: [
      ['citation_sentiment_results', 'object[]', '带支持/中立/有局限性标签的引用识别结果清单'],
      ['context_fragments', 'object[]', '上下文片段'],
      ['confidence', 'number', '置信度评分'],
    ],
  },
  'citation-intent': {
    inputs: [
            ['document_title', 'string | string[]', 'required', '文献题目'],
            ['scientific_document_full_text', 'string | string[] | file | file[]', 'required', '文献全文文本或文件'],
      ['reference_entries', 'string | file', 'required', '参考文献原始条目(每行一条)。同引用情感识别'],
      ['citation_sentence_and_context', 'object[]', 'conditional', '引用句及上下文(自动派生)。结构同引用情感识别'],
      ['citation_metadata', 'object[]', 'conditional', '被引文献元数据(自动派生)。结构同引用情感识别'],
      ...resourceDescriptorRows('preprocessed_training_set',
        '预处理后的训练集引用。引用意图判定规则包:引用句抽取正则、三类意图定义(背景介绍/引入研究方法/结果比较)、关键词打分规则;注入提示词约束判定口径并在 LLM 判定后做后置校验调分(不训练模型)',
        '自定义意图规则文件(意图定义/打分关键词,注入提示词)'),
    ],
    outputs: [
      ['citation_intent_label', 'string', '引用意图标签'],
      ['citation_sentence', 'string', '对应引用句'],
      ['context_fragment', 'object | string', '上下文片段'],
      ['confidence', 'number', '置信度评分'],
    ],
  },

  // ==================== 概念定义识别 ==================== #
  'definition-detect': {
    inputs: [
      ['scientific_document_fragment_or_batch_text', 'string | string[] | file | file[]', 'required', '科技文献全文片段或文本'],
      ['domain_label', 'string', 'optional', '领域标签。枚举:"自动识别"(默认)或 "01"–"32"。注入识别提示词作为领域语境,概念判定优先考虑该领域术语;随结果返回'],
      ['output_format_requirement', 'string', 'optional', '输出格式要求。枚举:"JSON"(默认)、"CSV"(结果附 csv_content 字段)、"数据库写入结构"(结果附 database_records 字段,含 concept_id 等 DB 就绪字段)'],
    ],
    outputs: [
      ['definition_sentences', 'object[]', '概念定义句列表'],
      ['concept_terms', 'object[]', '概念词提取结果'],
      ['concept_definition_mappings', 'object[]', '结构化概念与定义映射数据'],
      ['statistical_analysis_report', 'object', '识别统计分析报告'],
    ],
  },

  // ==================== 命名实体识别 ==================== #
  'general-ner': {
    inputs: [
      ['bilingual_scientific_document_text', 'string | string[] | file | file[]', 'required', '中英文科技文献文本'],
      ...resourceDescriptorRows('general_domain_annotated_corpus',
        '通用领域标注语料引用。实体标准术语归一/映射(standard_term_mappings)的依据;用户上传自定义版本可改变实体抽取规范',
        '自定义标注语料 JSON 文件(entity_types + 标注示例,注入提示词改变实体抽取行为)'),
    ],
    outputs: [['entities', 'object[]', '包含实体类别、位置和语境片段的列表;文本输入返回字符范围,文件输入返回标题层级路径']],
  },
  'research-ner': {
    inputs: [
      ['academic_abstract_or_technical_report_text', 'string | string[] | file | file[]', 'required', '中英文学术论文摘要或技术报告文本'],
      ...resourceDescriptorRows('multi_domain_scientific_corpus',
        '多领域科研语料引用。科研实体(方法/数据集/工具/模型等)的判定规则与识别口径,注入提示词约束识别范围',
        '自定义科研语料规范 JSON 文件(实体规范 + 标注示例)'),
      ...resourceDescriptorRows('manually_labeled_data',
        '人工标注数据引用。科研实体人工标注样本,作 few-shot 参考校准实体边界与类型判定风格',
        '自定义标注样本文件'),
    ],
    outputs: [
      ['entity_type', 'string', '科研实体类型'],
      ['sentence_position', 'object', '句子位置;文本输入返回字符范围,文件输入返回标题层级路径'],
      ['associated_context', 'object | string', '关联上下文'],
      ['standard_term_mapping', 'object', '映射标准词表'],
    ],
  },
  'domain-ner': {
    inputs: [
      ['domain_scientific_document_text', 'string | string[] | file | file[]', 'required', '专业科研文献文本'],
      ...resourceDescriptorRows('ontology_classification_system',
        '本体分类体系引用。实体类型体系的答案空间:限定可识别的实体类型、类型层级与标准知识库映射(ontology_mappings)。更换本体即更换实体类型体系',
        '自定义本体 JSON 文件(entity_types 数组 + 标注规范说明)'),
      ...resourceDescriptorRows('domain_labeled_training_data',
        '领域标注训练数据引用。领域实体判定规则(各实体类型的关键词/模式),是领域实体识别与本体映射的规则来源',
        '自定义领域实体规则文件'),
    ],
    outputs: [
      ['entity_type', 'string', '按领域类别细分的实体类型'],
      ['entity_position', 'object', '实体位置;文本输入返回字符范围,文件输入返回标题层级路径'],
      ['domain_label', 'string', '领域标签'],
      ['standard_knowledge_base_mapping_id', 'string', '标准知识库映射 ID'],
    ],
  },

  // ==================== 实体关系识别 ==================== #
  'relation-extract': {
    inputs: [
      ['upstream_ner_record_id', 'string', 'required', '上游实体记录编号。数据库中已完成的命名实体识别结果记录(rec_ 前缀),后端据此读取原始句子和实体列表,在其上抽取实体间关系三元组'],
      ['dependency_parse', 'object[]', 'optional', '依存句法分析结果。选择上游实体记录后系统自动生成并展示;包含句子编号、中心词、依存关系和依存词,用于支撑关系抽取的句法分析'],
      ['dependency_parse[].sentence_id', 'string', 'optional', '句子编号(如 "SENT-001")'],
      ['dependency_parse[].head', 'string', 'optional', '中心词(依存弧的支配词)'],
      ['dependency_parse[].relation', 'string', 'optional', '依存关系类型(如"定语""主谓关系")'],
      ['dependency_parse[].dependent', 'string', 'optional', '依存词(依存弧的从属词)'],
      ['dependency_paths', 'object[]', 'optional', '实体关系三元组对应的依存句法路径,由系统自动生成'],
    ],
    outputs: [
      ['relation_triples', 'object[]', '实体关系三元组'],
      ['context_fragments', 'object[]', '上下文片段'],
      ['confidence', 'number', '置信度评分'],
      ['rdf_representation', 'string | object', '关系三元组对应的 RDF 表示'],
    ],
  },

  // ==================== 深度聚类 ==================== #
  'deep-cluster': {
    inputs: [
      ['cluster_dimension', 'string', 'required', '聚类维度。枚举:"technology"(技术路线,默认)、"application"(应用场景);决定句子特征抽取视角与聚类语义'],
      ['scientific_document_texts', 'string[] | object[]', 'conditional', '多篇科技文献文本,至少 4 篇(批量文本模式专用参数)'],
      ['documents', 'file[]', 'conditional', '批量文献文件,至少 4 个(批量文件模式专用参数)'],
      ['document_metadata', 'object[]', 'conditional', '文献元数据(文献编号+发表时间),用于趋势分析与文献集沉淀。批量文本模式必填;批量文件模式由文件解析自动补充'],
      ['document_metadata[].document_id', 'string', 'conditional', '文献编号(批量文本模式必填),如 "DOC001"'],
      ['document_metadata[].publication_date', 'string', 'conditional', '发表时间(批量文本模式必填),格式 "YYYY-MM-DD"'],
      ['document_metadata[].title', 'string', 'optional', '文献题目'],
      ['clustering_algorithm_type', 'string', 'optional', '聚类算法类型。枚举:"auto"(默认)、"kmeans"、"spectral"、"agglomerative"、"hierarchical"、"hdbscan"'],
      ['cluster_count', 'integer', 'optional', '类簇数量(>=2)。不指定时算法自动选 k;hdbscan 不允许指定'],
      ['output_format', 'string', 'optional', '输出格式(默认 JSON)'],
    ],
    outputs: [
      ['cluster_results', 'object[]', '聚类结果类簇'],
      ['cluster_feature_statistics', 'object', '类簇特征统计'],
      ['topic_trend_analysis', 'object', '主题趋势分析结果'],
    ],
  },

  // ==================== 聚类标签生成 ==================== #
  'cluster-label': {
    inputs: [
      ['cluster_task_id', 'string', 'required', '已完成的深度聚类任务编号(tsk_ 前缀)。后端读取该任务的类簇短语集合生成标签;与 cluster_phrase_sets 二选一'],
      ['cluster_phrase_sets', 'object[]', 'conditional', '直接提供深度聚类输出的类簇短语集合(API 调用路径;与 cluster_task_id 二选一)'],
      ['label_length_limit', 'integer', 'optional', '标签长度限制(默认 12)'],
      ['language_type', 'string', 'optional', '标签语言。枚举:"auto"(默认)、"zh"、"en"'],
      ['distinctiveness_threshold', 'number', 'optional', '差异度阈值,范围 0-1(默认 0.75)。低于该阈值的候选标签被过滤;值越高候选越少越保守'],
    ],
    outputs: [
      ['cluster_labels', 'object[]', '类簇标签集合'],
      ['label_generation_process_report', 'object', '标签生成过程报告'],
      ['label_distinctiveness_optimization_result', 'object', '标签差异化优化结果'],
    ],
  },

  // ==================== 结构化自动综述 ==================== #
  'structured-review': {
    inputs: [
      ['topic_or_keywords', 'string | string[]', 'required', '研究主题或关键词。限定综述的研究范围'],
      ['document_set', 'string[] | file[] | object', 'conditional', '文献集,至少 3 篇。批量文本模式传文本数组;批量文件模式传文件;指定文献集模式传集合引用对象'],
      ['document_set.collection_id', 'string', 'conditional', '指定文献集模式时的集合编号(col_ 前缀)'],
      ['document_metadata', 'object[]', 'conditional', '文献元数据。批量文本模式需逐篇提供;文件/文献集模式自动解析'],
      ['document_metadata[].document_id', 'string', 'conditional', '文献编号(批量文本模式必填)'],
      ['document_metadata[].publication_date', 'string', 'optional', '发表时间(YYYY-MM-DD)。用于趋势热点分析;缺失时从文献全文自动抽取'],
    ],
    outputs: [
      ['three_level_review_tree', 'object[]', '研究问题-研究方法-研究进展三层树形结构综述视图'],
      ['cluster_induction_results', 'object', '聚类及类簇归纳结果'],
      ['structured_text_review_report', 'object', '结构化文本综述报告'],
      ['trend_and_hotspot_distribution', 'object', '趋势分析与研究热点分布图'],
    ],
  },
}

export const requirementInputsFor = (toolId: string) => requirementContracts[toolId]?.inputs || []
export const requirementOutputsFor = (toolId: string) => requirementContracts[toolId]?.outputs || []
