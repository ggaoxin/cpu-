# V7.74 前后端交互与数据库字段矩阵

本文档以当前 `frontend/src/data/requirement-contracts.ts`、`config/vue_contracts.py` 和 Vue 在线测试页面为唯一业务依据，说明 19 个功能点的真实输入、运行逻辑、输出和数据库关系。前端预览弹窗中的数据只用于界面审查；点击“在线测试”后只展示 FastAPI 的真实响应。

## 一、全局约定

- `required`：不提供时无法形成有效算法输入，后端返回 422，且不会创建分析任务。
- `optional`：不提供不阻断任务；后端使用明确默认值、自动识别或从文件解析，绝不补造演示内容。
- 文本输入最长 8000 个清洗后字符；文件和数据库文献集可保留全文，由算法分段处理。
- 批量文本中的题目、项目名称和文献编号逐条绑定，不能在批次内串用。
- 文本位置使用字符范围；文件位置使用“一级标题—二级标题—三级标题”章节路径。中英文摘要语步识别仍使用摘要句子位置。
- 每次成功或失败的执行都会写入 `analysis_tasks` 和 `task_items`；成功结果写入 `result_records`，并投影到对应业务表。
- 所有数据库资源选择均使用 `semantic_resources` 的当前版本；用户上传的新资源同样登记版本和内容哈希。

## 二、逐功能说明

### 1. 中文摘要语步识别 `zh-abstract-move`

接口：`/api/v1/move/abstract/zh/{text|texts|file|files}`。

| 输入 | 必填 | 用户提供什么、为什么需要 | 不提供的结果 |
|---|---|---|---|
| `chinese_scientific_abstract` | 是 | 中文摘要文本，或包含摘要的单/批文件；它是分句和语步判断的唯一语义对象 | 无法识别，返回 422 |

输出：`document`、`moves[]`、`move_count`、`sentence_count`。每个 `moves[]` 项承载需规中的语步类别、句子位置、原文片段和置信度。数据库投影：`move_results`、`move_segments`。

### 2. 英文摘要语步识别 `en-abstract-move`

接口：`/api/v1/move/abstract/en/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `english_scientific_abstract` | 是 | SCI/EI 或会议论文英文摘要，用于英文分句、上下文和语步判别 | 返回 422 |

输出：`document`、`moves[]`、`move_count`、`sentence_count`；`moves[]` 内含语步类型、位置、上下文和置信度。数据库投影同语步识别表。

### 3. 中文基金项目语步识别 `fund-move`

接口：`/api/v1/move/fund/zh/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `project_document_text` | 是 | 基金申请书、立项书或项目管理材料；用于识别立项依据、目标、内容、方法等项目语步 | 返回 422 |
| `project_name` | 否 | 标识文本任务和弹窗结果；文件模式可从文件名/文件内容解析 | 不影响识别，系统使用记录名或文件名 |

输出：`document`、`moves[]`、`move_count`、`input_type`。文本结果返回字符位置，文件结果返回章节路径。数据库投影：`move_results`、`move_segments`；如后续执行回写，状态保存在结果的 `writeback` 中。

### 4. 中文科技文献自动分类 `zh-classify`

接口：`/api/v1/classify/clc/zh/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `chinese_scientific_document_text` | 是 | 待分类的论文、会议稿、科技报告或政策文本 | 返回 422 |
| `document_title` | 否 | 标识单篇/批量结果；文件模式可自动解析 | 分类可继续，但结果标题为空或使用文件名 |
| `clc_labeled_data` | 是 | 当前标准中图分类号标注资源，用于分类号约束和真实性校验 | 返回 422，避免无标准分类 |

输出：`is_interdisciplinary`、`classifications[]`、`classification_confidence`、`domain_labels[]`、`candidate_classifications[]`。跨学科首选和候选均按“主分类+次分类”组合输出；非跨学科只含主分类。数据库投影：`classification_results`、`classification_candidates`，人工确认写入 `classification_confirmations`。

### 5. 英文科技文献自动分类 `en-classify`

接口：`/api/v1/classify/clc/en/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `english_scientific_document_text` | 是 | 英文论文、会议稿或科研项目文本 | 返回 422 |
| `document_title` | 否 | 标识文献结果 | 不影响算法，标题可能为空/取文件名 |
| `clc_standard_and_mapping_rules` | 是 | 中图分类标准及英文到中图分类的映射规则 | 返回 422 |

输出：`is_interdisciplinary`、`classifications[]`、`classification_confidence`、`cross_language_mapping[]`、`domain_labels[]`、`candidate_classifications[]`、`literature_distribution_analysis_report`。数据库投影同自动分类表。

### 6. 专业领域科技文献分类 `domain-classify`

接口：`/api/v1/classify/domain/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `domain_scientific_literature_data` | 是 | 待进行专业领域内部细分的科技文本或文件 | 返回 422 |
| `document_title` | 否 | 标识结果 | 不影响分类 |
| `professional_domain` | 是 | 用户先确定的大专业领域，算法只在该领域内做三级细分 | 返回 422；不会跨专业大类猜测 |
| `domain_classification_rules` | 是 | 当前领域分类规则 | 返回 422 |
| `manually_labeled_training_data` | 是 | 当前人工标注训练/校验资源，为领域内边界提供依据 | 返回 422 |

输出：`professional_domain`、`multilevel_classification_results[]`、`classification_confidence`、`domain_labels[]`、`candidate_classifications[]`、`data_distribution_report`。候选只能位于所选专业大类内，供人工确认。数据库投影同分类表及确认表。

### 7. 中文关键词识别 `zh-keyword`

接口：`/api/v1/keywords/zh/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `chinese_scientific_abstract` | 是 | 实际待提取关键词的中文文本；字段名沿用需规，但可提交普通干净文本 | 返回 422 |
| `document_title` | 否 | 标识结果 | 不影响提取 |
| `domain_terminology_dictionary` | 否 | 可使用系统词典、数据库已保存用户词典，或新建/上传用户词典，以增强领域术语命中 | 使用系统默认词典，不影响运行 |

输出：`document`、`keywords[]`、`keyword_count`。用户词典的版本、命中和权重记录在 `dictionary_usage`。数据库除通用结果表外使用 `dictionaries`、`dictionary_versions`、`dictionary_terms`、`keyword_results`、`keyword_items`。

### 8. 英文关键词识别 `en-keyword`

接口：`/api/v1/keywords/en/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `english_scientific_abstract` | 是 | 待提取英文关键词/主题短语的文本 | 返回 422 |
| `document_title` | 否 | 标识结果 | 不影响提取 |
| `domain_terminology_library` | 是 | 当前英文领域术语库，处理缩写、词形和规范术语 | 返回 422 |
| `classification_standard_mapping_table` | 是 | 将英文术语映射为科研分类标签的当前映射表 | 返回 422 |

输出：`document`、`keywords_or_topic_phrases[]`、`term_count`。数据库投影：`keyword_results`、`keyword_items`。

### 9. 研究问题识别 `rq-detect`

接口：`/api/v1/research-question/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `scientific_document_fragment` | 是 | 待识别研究问题的科技文本，可为完整文献片段 | 返回 422 |
| `document_title` | 否 | 将批量问题结果归属到正确文献 | 不影响识别，但文献标识为空/取文件名 |
| `text_format_requirement` | 否 | 告知系统是纯文本、章节文本或 JSON；默认自动识别 | 自动识别格式 |

输出：`document`、`research_question_sentences[]`、`research_question_phrases[]`、`structured_research_questions[]`、`research_question_statistics`。数据库投影：`research_question_results`、`research_question_items`。

### 10. 引用情感识别 `citation-sentiment`

接口：`/api/v1/citation-sentiment/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `scientific_document_full_text` | 是 | 文本模式提供当前文献文本；文件模式由系统解析全文 | 返回 422 |
| `citation_sentence_and_context` | 文本模式是 | 明确给出引用句、前一句和后一句，避免脱离语境判断支持/中立/有局限性 | 文本模式返回 422；文件模式自动抽取 |
| `citation_metadata` | 是 | 文本模式粘贴/上传参考文献条目并解析；文件模式从参考文献列表自动解析，失败时可补充 | 文本模式返回 422；文件模式允许自动解析描述符 |

输出：`document`、`citation_sentiment_results[]`、`citation_sentiment_statistics`。每个结果包含引用句、上下文、情感标签和置信度；不输出不需要的引文来源列或引文标记列。数据库投影：`citation_results`、`citation_items`。

### 11. 引用意图识别 `citation-intent`

接口：`/api/v1/citation-intent/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `citation_sentence_and_context` | 文本模式是 | 指定引用句及前后文，用于判断背景介绍、方法引入或结果比较 | 返回 422；文件模式自动抽取 |
| `citation_metadata` | 是 | 关联被引文献；获取逻辑同引用情感识别 | 文本模式返回 422 |
| `preprocessed_training_set` | 是 | 当前引用意图训练/校验资源，约束意图标签边界 | 返回 422 |

输出：`document`、`citation_intent_results[]`、`citation_intent_statistics`。数据库投影同引用结果表。

### 12. 概念定义识别 `definition-detect`

接口：`/api/v1/concept-definition/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `scientific_document_fragment_or_batch_text` | 是 | 单/批科技文本或文件，作为概念和定义句提取对象 | 返回 422 |
| `domain_label` | 否 | 缩小同名概念的解释语境 | 自动识别领域 |
| `output_format_requirement` | 否 | 指定 JSON、CSV 或数据库写入结构 | 默认 JSON |

输出：`document`、`definitions[]`、`concept_definition_mappings[]`、`statistical_analysis_report`。映射页不额外伪造来源或置信度。数据库投影：`definition_results`、`definition_items`。

### 13. 中英文通用领域命名实体识别 `general-ner`

接口：`/api/v1/ner/general/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `bilingual_scientific_document_text` | 是 | 中英文科技文本 | 返回 422 |
| `general_domain_annotated_corpus` | 是 | 当前通用领域标注语料，约束人名、地名、机构、事件等类别 | 返回 422 |

输出：`document`、`entities[]`、`summary`；实体包含类别、位置和语境片段，不输出需规未要求的缩写/别名。数据库投影：`entity_results`、`entity_mentions`。

### 14. 中英文通用科研实体识别 `research-ner`

接口：`/api/v1/ner/research/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `academic_abstract_or_technical_report_text` | 是 | 学术文本或技术报告文本 | 返回 422 |
| `multi_domain_scientific_corpus` | 是 | 覆盖多学科科研表达，帮助识别跨领域术语 | 返回 422 |
| `manually_labeled_data` | 是 | 当前人工标注数据，约束科研实体类型和标准词映射 | 返回 422 |

输出：`document`、`entities[]`、`standard_term_mappings[]`、`summary`。数据库投影同实体表。

### 15. 专业领域科研实体识别 `domain-ner`

接口：`/api/v1/ner/domain/{text|texts|file|files}`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `domain_scientific_document_text` | 是 | 专业领域科技文本 | 返回 422 |
| `ontology_classification_system` | 是 | 当前本体分类体系，决定实体所属本体路径和可映射知识库类别 | 返回 422 |
| `domain_labeled_training_data` | 是 | 当前领域标注数据，提供专业实体边界和类型样例 | 返回 422 |

输出：`document`、`selected_domain`、`entities[]`、`ontology_mappings[]`、`summary`。实体结果区分当前识别表达、领域标签、实体类型、知识库 ID 和映射状态。数据库投影同实体表，并预留 `ontology_versions`、`ontology_nodes` 保存正式本体版本。

### 16. 实体关系识别 `relation-extract`

接口：`/api/v1/relation/from-ner-record`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `upstream_ner_record_id` | 是 | 用户从数据库选择一条已完成的 NER 结果；后端读取原始句子和实体列表，再内部执行依存句法分析 | 返回 422 |

用户不手工输入原始句子、实体列表或依存句法结果。输出：`upstream_ner_record_id`、`original_sentence`、`dependency_parse[]`、`dependency_paths[]`、`relation_triples[]`、`context_fragments[]`、`rdf_representation`。数据库通过 `record_dependencies` 记录来源 NER 结果，投影到 `relation_results`、`relation_triples`。

### 17. 深度聚类 `deep-cluster`

接口：`/api/v1/cluster/deep/texts`、`/api/v1/cluster/deep/files`；独立评测接口：`/api/v1/cluster/deep/evaluate`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `scientific_document_texts` | 是 | 至少 4 篇文本或文件；普通文本、科技报告和论文均可 | 少于 4 篇返回 422 |
| `document_metadata` | 是 | 与每篇内容一一对应的文献编号和发表时间，题名、作者、来源、关键词可选；用于溯源和趋势统计，不用于强行预分类 | 编号/日期缺失或数量不一致时返回 422 |
| `cluster_dimension` | 是 | 用户选择技术路线或应用场景，两种维度走各自适合的聚类路线 | 返回 422 |
| `clustering_algorithm_type` | 否 | 自动选择、K-Means、HDBSCAN 或层次聚类 | 默认自动选择 |
| `cluster_count` | 否 | 指定类簇数 | 系统自动估计 |
| `output_format` | 否 | JSON、CSV 或数据库结构 | 默认 JSON |

输出：`cluster_dimension`、`cluster_dimension_name`、`input_summary`、`clustering_quality`、`training_evaluation`、`clusters[]`、`document_assignments[]`、`semantic_projection`、`theme_trend_analysis`。普通聚类不依赖训练样本或 Gold；模型性能评测是独立操作，选择训练样本与人工标注资源后计算真实 ARI、NMI、轮廓系数等并写入 `model_evaluation_runs`。聚类结果投影：`cluster_runs`、`clusters`、`cluster_memberships`，人工调整使用 `cluster_revisions`、`cluster_corrections`。

### 18. 聚类标签生成 `cluster-label`

接口：`/api/v1/cluster-labels/generate`；历史任务直连接口：`/api/v1/cluster-labels/from-cluster-task`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `cluster_phrase_sets` | 是 | 深度聚类每个类簇的代表短语集合；在线测试从已完成的聚类任务读取，不要求用户手工编写 | 无类簇短语时返回 422 |
| `label_length_limit` | 否 | 限制标签长度 | 默认 12 |
| `language_type` | 否 | 自动、中文或英文 | 默认自动 |
| `distinctiveness_threshold` | 否 | 控制不同类簇标签的区分要求 | 默认 0.75 |

输出：`cluster_count`、`generated_label_count`、`parameters`、`labels[]`、`statistics`、`label_generation_process_report`、`label_distinctiveness_optimization_result`。正式路线先由 GLM 生成自然候选，再由 BGE-M3 与 V11 自适应软规则门控复核；GLM 失败时逐类簇回退并记录原因。数据库投影：`cluster_label_results`、`cluster_labels`，来源依赖写入 `record_dependencies`，人工确认写入 `cluster_label_confirmations`。

### 19. 结构化自动综述 `structured-review`

接口：`/api/v1/review/structured/texts`、`/api/v1/review/structured/files`、`/api/v1/review/structured/collections`。

| 输入 | 必填 | 作用 | 不提供的结果 |
|---|---|---|---|
| `document_set` | 是 | 至少 3 篇批量文本、文件，或数据库已有文献集 | 返回 422 |
| `topic_or_keywords` | 是 | 限定综述要回答的主题范围，不等同于人工指定聚类标签 | 返回 422 |
| `document_metadata` | 是 | 文献编号、题名、作者/团队、年份、来源、关键词等；文本逐篇填写，文件自动解析/补充，数据库文献集随集合读取 | 文本模式缺失或对应不上时返回 422 |

运行逻辑：从当前文献集抽取研究问题，按语义相似度聚类问题，匹配每簇研究方法，再归纳阶段进展和结论；所有节点保留证据索引。它不要求关联历史深度聚类任务。输出：`review_id`、`topic`、`document_count`、`statistics`、`tree[]`、`cluster_induction_results`、`structured_report`、`trend_hotspot_distribution`、`evidence_index[]`。数据库文献集使用 `documents`、`document_collections`、`collection_documents`；结果投影：`review_results`、`review_nodes`、`review_sections`、`review_evidence_links`。

## 三、数据库为什么需要这些表

| 数据类别 | 表 | 原因 |
|---|---|---|
| 任务审计 | `analysis_tasks`、`task_items`、`result_records`、`audit_events` | 支持批量进度、失败定位、历史查询、导出和审计 |
| 上下游关系 | `record_dependencies` | 保证实体关系结果可追溯至 NER，标签结果可追溯至深度聚类 |
| 文献集 | `documents`、`document_collections`、`collection_documents` | 支持结构化综述直接选择已有文献集，避免重复上传 |
| 用户词典 | `dictionaries`、`dictionary_versions`、`dictionary_terms` | 保存用户自定义词典及版本，保证任务可复现 |
| 算法资源 | `semantic_resources` | 保存分类标准、术语库、标注数据、本体等当前版本或上传版本 |
| 模型评测 | `model_evaluation_runs` | 独立记录 Gold、样本量、算法参数与 ARI/NMI 等真实指标 |
| 业务结果 | `move_*`、`classification_*`、`keyword_*`、`research_question_*`、`citation_*`、`definition_*`、`entity_*`、`relation_*`、`cluster_*`、`review_*` | 避免只保存一坨 JSON，使检索、筛选、人工确认、统计和系统集成可直接查询 |

## 四、当前自动核验范围

- 19 个功能、67 种 Vue 输入方式与 API/SDK 参数审查。
- 所有单文本、批量文本、单文件、批量文件公共字段路由。
- 深度聚类批量文件元数据逐篇对应。
- 结构化综述批量文件元数据与数据库文献集读取。
- 批量题名、基金项目名、引用句上下文和引文元数据隔离。
- 批量 NER 的历史记录逐条绑定原文，实体关系识别选择哪条记录就复用哪条文本。
- 聚类标签的类簇短语能够进入正式标签生成器，历史聚类任务接口可恢复短语集合。
- 结果写入通用表和 19 类业务投影表。
