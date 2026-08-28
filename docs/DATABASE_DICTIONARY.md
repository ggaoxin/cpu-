# 语义计算工具库 数据库字典(MySQL 8)

> 数据库:`semantic_toolkit`,共 52 张表。按业务域分组说明每张表的用途与字段含义。
> 生成方式:从实际 schema 自动提取,人工标注业务含义。

## 任务域

### analysis_tasks

分析任务主表:每次调用(在线测试/批量)生成一条,记录工具、输入类型、进度、成功/失败计数、错误摘要与完整请求载荷。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 任务编号(tsk_ 前缀 UUID),全链路主键 |
| workspace_id | varchar(64) | 所属工作空间 |
| tool_id | varchar(64) | 功能点标识(如 zh-abstract-move,与前端工具ID一致) |
| backend_code | varchar(64) | 后端算法代码(如 mr_zh_abstract) |
| status | varchar(32) | 任务状态:succeeded/failed/partial_failed/cancelled |
| progress | int | 进度百分比 0-100 |
| input_type | varchar(32) | 输入方式:text/texts/file/files/collection/cluster_task/upstream_records |
| request_payload | longtext | 完整原始请求(JSON):用户提交的全部参数,任务重跑的依据 |
| parameters_json | json | 解析后的算法参数(含所选资源) |
| model_version | varchar(128) | 调用时的模型版本号 |
| total | int | 输入条目总数 |
| success_count | int | 成功条数 |
| failed_count | int | 失败条数 |
| error_summary | text | 失败原因摘要(排查入口) |
| created_at | varchar(40) | 创建时间(UTC) |
| updated_at | varchar(40) | 最后更新时间 |
| completed_at | varchar(40) | 完成时间 |
| archived_at | varchar(40) | 归档时间(前端可归档历史任务) |

### record_dependencies

结果依赖关系:记录某结果的输入来自哪条上游记录(如关系抽取依赖 NER 记录)。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| record_id | varchar(64) |  |
| upstream_record_id | varchar(64) |  |
| dependency_type | varchar(64) |  |
| created_at | varchar(40) |  |

### result_records

结果记录:每篇文献每个工具的识别结果 JSON(result_json),供历史查询/上下游依赖/导出复用。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 结果记录编号(rec_ 前缀 UUID),导出/上下游依赖引用的主键 |
| task_id | varchar(64) | 所属任务编号 → analysis_tasks.id |
| task_item_id | varchar(64) | 所属任务明细 → task_items.id |
| tool_id | varchar(64) | 功能点标识(同任务) |
| backend_code | varchar(64) | 后端算法代码 |
| result_json | longtext | 完整识别结果 JSON(与 API 响应 data 一致) |
| schema_version | varchar(32) | 结果结构版本 |
| created_at | varchar(40) |  |

### task_items

任务明细:批量请求中每篇文献/每条输入一行,记录该条的处理状态与错误。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| task_id | varchar(64) |  |
| input_index | int |  |
| status | varchar(32) |  |
| source_json | json |  |
| error_message | text |  |
| created_at | varchar(40) |  |
| updated_at | varchar(40) |  |

## 语步识别

### move_results

语步识别结果头表:一篇文献一行,含语步总数、句子数、输入类型、整体置信度、文档语言。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | → result_records.id |
| document_title | varchar(1000) | 文献题目 |
| project_title | varchar(1000) | 项目名称(基金语步) |
| statistics_json | json | 各语步句子数统计 |
| move_count | int | 语步数量 |
| sentence_count | int | 句子总数 |
| input_type | varchar(64) | 输入方式 |
| overall_confidence | double | 整体置信度 0-1 |
| document_language | varchar(16) | 文档语言 zh/en |

### move_segments

语步分段明细:每个语步一行,含语步类别、句子序号、字符起止、原文、来源与置信度。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) | → result_records.id |
| move_code | varchar(128) | 语步类别代码(研究背景/研究目的/研究方法/研究结果/研究结论) |
| move_name | varchar(255) | 语步类别名称 |
| label | varchar(255) | 语步标签(同 move_name) |
| sentence_index | int | 句子序号(全文第几句) |
| start_offset | int | 起始字符位置(文本模式) |
| end_offset | int | 结束字符位置 |
| text_value | longtext | 语步原文 |
| source_json | json | 来源信息(章节路径/页码) |
| confidence | double | 该语步置信度 0-1 |

## 自动分类

### classification_candidates

分类候选明细:主分类+次分类候选,含角色、组合号、置信度与排序。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| role_name | varchar(32) |  |
| class_code | varchar(128) |  |
| class_name | varchar(500) |  |
| path_json | json |  |
| confidence | double |  |
| rank_no | int |  |

### classification_confirmations

人工确认记录:用户确认/替换主分类的审核痕迹。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| primary_code | varchar(128) |  |
| secondary_codes | json |  |
| actor_id | varchar(64) |  |
| reason | text |  |
| created_at | varchar(40) |  |

### classification_results

分类结果头表:主分类号/名称/路径/置信度、领域标签、确认状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | → result_records.id |
| primary_code | varchar(128) | 主分类号(中图法,如 TP391.41) |
| primary_name | varchar(500) | 主分类名称 |
| primary_path | json | 完整分类路径(JSON 数组) |
| primary_confidence | double | 主分类置信度 0-1 |
| selected_domain | json | 所选专业领域 |
| domain_labels | json | 领域标签 |
| taxonomy_version | varchar(128) | 分类法版本 |
| confirmation_status | varchar(32) | 人工确认状态 |

## 关键词识别

### keyword_items

关键词明细:每个关键词一行,含规范术语、权重、命中词典标记与位置。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) | → result_records.id |
| term | varchar(500) | 关键词原文 |
| normalized_term | varchar(500) | 规范术语(词典/术语库归一后) |
| score | double |  |
| rank_no | int | 排序位次 |
| source_name | varchar(255) | 来源(model=模型 / 词典名=用户词典命中) |
| source_position | json | 在原文中的位置(JSON) |
| mapping_json | json | 分类映射信息(英文关键词→中图类目) |

### keyword_results

关键词结果头表:词典使用情况与统计。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| dictionary_usage | json |  |
| statistics_json | json |  |

## 研究问题识别

### research_question_items

研究问题句明细:句子、位置、类型、置信度与章节溯源。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| item_type | varchar(32) |  |
| text_value | longtext |  |
| structured_json | json |  |
| source_position | json |  |
| confidence | double |  |

### research_question_results

研究问题结果头表与统计。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| statistics_json | json |  |

## 引用句识别

### citation_items

引用句明细:引用句、标记、上下文、被引元数据、情感/意图标签与置信度。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| citation_id | varchar(128) |  |
| sentence | longtext |  |
| label_name | varchar(255) |  |
| marker_json | json |  |
| context_json | json |  |
| source_position | json |  |
| reference_json | json |  |
| evidence_json | json |  |
| confidence | double |  |

### citation_results

引用识别结果头表:分析类型(情感/意图)与统计。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| analysis_type | varchar(32) |  |
| statistics_json | json |  |

## 概念定义识别

### definition_items

定义句明细:概念词、定义句、句式与置信度。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| concept | varchar(500) |  |
| normalized_concept | varchar(500) |  |
| definition_text | longtext |  |
| sentence | longtext |  |
| domain_name | varchar(128) |  |
| source_position | json |  |
| mapped_term_id | varchar(128) |  |
| confidence | double |  |

### definition_results

定义识别结果头表与统计。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| statistics_json | json |  |

## 命名实体识别

### entity_mentions

实体提及明细:实体文本、类型、字符位置、知识库映射与置信度。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| entity_id | varchar(128) |  |
| text_value | varchar(1000) |  |
| normalized_text | varchar(1000) |  |
| entity_type | varchar(128) |  |
| start_offset | int |  |
| end_offset | int |  |
| context_text | longtext |  |
| kb_id | varchar(255) |  |
| type_path | json |  |
| confidence | double |  |

### entity_results

实体识别结果头表:所选领域、本体版本与统计。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| selected_domain | json |  |
| ontology_version | varchar(128) |  |
| statistics_json | json |  |

## 实体关系识别

### relation_results

关系抽取结果头表与统计。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| source_records | json |  |
| statistics_json | json |  |

### relation_triples

关系三元组明细:头实体-关系-尾实体、证据上下文与置信度。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| triple_id | varchar(128) |  |
| subject_entity_id | varchar(128) |  |
| subject_text | varchar(1000) |  |
| relation_name | varchar(500) |  |
| relation_type | varchar(128) |  |
| object_entity_id | varchar(128) |  |
| object_text | varchar(1000) |  |
| evidence_json | json |  |
| confidence | double |  |

## 深度聚类

### cluster_corrections

聚类纠正明细。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| revision_id | varchar(64) |  |
| action_type | varchar(64) |  |
| action_json | json |  |
| actor_id | varchar(64) |  |
| created_at | varchar(40) |  |

### cluster_memberships

文献归属明细:每篇文献属于哪个簇、相似度。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| cluster_row_id | varchar(64) |  |
| document_id | varchar(128) |  |
| title | varchar(1000) |  |
| similarity | double |  |

### cluster_revisions

人工校正记录:用户合并/拆分/移动簇的操作痕迹。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| source_record_id | varchar(64) |  |
| version | int |  |
| status | varchar(32) |  |
| created_at | varchar(40) |  |

### cluster_runs

聚类运行头表:任务号、维度、质量指标、校正状态。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| cluster_task_id | varchar(64) |  |
| dimension_name | varchar(32) |  |
| quality_metrics | json |  |
| correction_status | varchar(32) |  |

### clusters

类簇明细:簇号、主题名、成员数与代表术语。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| cluster_id | varchar(128) |  |
| size_count | int |  |
| representative_terms | json |  |
| centroid_document_id | varchar(128) |  |
| trend_json | json |  |

## 聚类标签生成

### cluster_label_confirmations

标签人工确认记录。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| cluster_id | varchar(128) |  |
| label_text | varchar(500) |  |
| actor_id | varchar(64) |  |
| created_at | varchar(40) |  |

### cluster_label_results

标签生成结果头表:来源任务、生成报告。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| source_cluster_task_id | varchar(64) |  |
| generation_report | json |  |

### cluster_labels

标签明细:每簇的推荐标签、区分度、候选与证据术语。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| cluster_id | varchar(128) |  |
| label_text | varchar(500) |  |
| confidence | double |  |
| distinctiveness | double |  |
| alternatives | json |  |
| evidence_terms | json |  |

## 结构化综述

### review_evidence_links

证据索引:每条证据的文献编号、章节、摘录与支撑节点。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| evidence_id | varchar(128) |  |
| document_id | varchar(128) |  |
| title | varchar(1000) |  |
| page_no | int |  |
| quote_text | longtext |  |

### review_nodes

综述树节点:研究问题/研究方法/研究进展三层节点。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| node_id | varchar(128) |  |
| parent_node_id | varchar(128) |  |
| level_no | int |  |
| node_type | varchar(32) |  |
| title | longtext |  |
| content | longtext |  |
| evidence_ids | json |  |

### review_results

综述结果头表:主题、文献数、树形结构与热点分布。

| 字段 | 类型 | 说明 |
|---|---|---|
| result_record_id | varchar(64) | 主键 |
| review_id | varchar(64) |  |
| topic | varchar(1000) |  |
| traceability | tinyint(1) |  |
| trend_analysis | json |  |
| hotspots | json |  |

### review_sections

综述章节内容与证据编号。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| section_id | varchar(128) |  |
| title | varchar(1000) |  |
| content | longtext |  |
| evidence_ids | json |  |

## 资源域

### collection_documents

文献集合成员:集合与文献的多对多关联。

| 字段 | 类型 | 说明 |
|---|---|---|
| collection_id | varchar(64) | 主键 |
| document_id | varchar(64) | 主键 |
| order_no | int |  |

### dictionaries

用户词典:关键词识别的自定义术语词典。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| workspace_id | varchar(64) |  |
| name | varchar(300) |  |
| language | varchar(16) |  |
| status | varchar(32) |  |
| current_version | int |  |
| created_at | varchar(40) |  |
| updated_at | varchar(40) |  |

### dictionary_terms

词典术语明细。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| dictionary_version_id | varchar(64) |  |
| term | varchar(500) |  |
| normalized_term | varchar(500) |  |
| weight | decimal(6,4) |  |

### dictionary_versions

词典版本:每次修改生成新版本。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| dictionary_id | varchar(64) |  |
| version | int |  |
| weight_boost | decimal(5,4) |  |
| content_hash | char(64) |  |
| created_at | varchar(40) |  |

### document_collections

文献集合:深度聚类沉淀或用户自建的文献集(综述'指定文献集'的数据源)。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| workspace_id | varchar(64) |  |
| name | varchar(300) |  |
| description | text |  |
| version | int |  |
| archived_at | varchar(40) |  |
| created_at | varchar(40) |  |
| updated_at | varchar(40) |  |

### documents

文档登记:解析后的文献文本与元数据。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| workspace_id | varchar(64) |  |
| file_id | varchar(64) |  |
| language | varchar(16) |  |
| title | varchar(1000) |  |
| abstract_text | longtext |  |
| content_text | longtext |  |
| content_hash | char(64) |  |
| metadata_json | json |  |
| created_at | varchar(40) |  |
| updated_at | varchar(40) |  |

### files

上传文件登记。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| workspace_id | varchar(64) |  |
| original_name | varchar(500) |  |
| object_key | varchar(1000) |  |
| sha256 | char(64) |  |
| size_bytes | bigint |  |
| media_type | varchar(255) |  |
| parse_status | varchar(32) |  |
| created_at | varchar(40) |  |

### ontology_nodes

本体节点。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| version_id | varchar(64) |  |
| parent_id | varchar(64) |  |
| kb_id | varchar(255) |  |
| preferred_label | varchar(500) |  |
| aliases_json | json |  |
| level_no | int |  |

### ontology_versions

本体版本。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| ontology_code | varchar(64) |  |
| version | varchar(128) |  |
| node_count | int |  |
| layer_counts | json |  |
| status | varchar(32) |  |
| created_at | varchar(40) |  |

### semantic_resources

语义资源注册表:内置/用户上传的分类标准、规则库、语料、术语库等(资源下拉的数据源)。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 资源编号(内置 RES-BUNDLED-* / 上传 res_ UUID) |
| workspace_id | varchar(64) | 所属工作空间 |
| resource_key | varchar(128) | 资源类型键(如 clc_labeled_data/domain_classification_rules) |
| name | varchar(255) | 资源名称(下拉显示) |
| version | varchar(64) | 版本号 |
| language | varchar(32) | 语言(zh/en/zh-en) |
| record_count | bigint | 记录条数 |
| status | varchar(32) | 状态:current=当前可用 / history=历史版本 |
| source_type | varchar(32) | 来源:bundled=内置 / uploaded=用户上传 |
| storage_uri | varchar(1024) | 存储位置(project:// 开头为项目内路径) |
| content_hash | varchar(128) | 内容哈希(防重复上传) |
| metadata_json | json |  |
| created_at | varchar(40) |  |
| updated_at | varchar(40) |  |

### taxonomy_nodes

分类法节点。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| version_id | varchar(64) |  |
| parent_id | varchar(64) |  |
| code | varchar(128) |  |
| name_zh | varchar(500) |  |
| name_en | varchar(500) |  |
| level_no | int |  |
| path_text | text |  |

### taxonomy_versions

分类法版本。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| taxonomy_code | varchar(64) |  |
| version | varchar(128) |  |
| node_count | int |  |
| status | varchar(32) |  |
| created_at | varchar(40) |  |

## 治理域

### audit_events

审计事件:关键操作的时间线。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| workspace_id | varchar(64) |  |
| actor_id | varchar(64) |  |
| action | varchar(128) |  |
| resource_type | varchar(64) |  |
| resource_id | varchar(64) |  |
| before_json | json |  |
| after_json | json |  |
| created_at | varchar(40) |  |

### exports

导出记录:JSON/CSV/XML/RDF 导出文件与下载地址。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| workspace_id | varchar(64) |  |
| task_id | varchar(64) |  |
| result_record_id | varchar(64) |  |
| format | varchar(32) |  |
| status | varchar(32) |  |
| object_key | varchar(1000) |  |
| error_message | text |  |
| created_at | varchar(40) |  |
| expires_at | varchar(40) |  |

### external_writebacks

外部系统回写记录。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| target_system | varchar(128) |  |
| status | varchar(32) |  |
| external_record_id | varchar(255) |  |
| request_json | json |  |
| response_json | json |  |
| retry_count | int |  |
| idempotency_key | varchar(128) |  |
| error_message | text |  |
| created_at | varchar(40) |  |
| updated_at | varchar(40) |  |

### model_evaluation_runs

模型评测运行记录。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| workspace_id | varchar(64) |  |
| model_name | varchar(128) |  |
| evaluation_type | varchar(128) |  |
| status | varchar(32) |  |
| request_json | json |  |
| metrics_json | json |  |
| created_at | varchar(40) |  |
| completed_at | varchar(40) |  |

### model_versions

模型版本登记。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| tool_id | varchar(64) |  |
| version | varchar(128) |  |
| labels_schema | json |  |
| metrics | json |  |
| status | varchar(32) |  |
| created_at | varchar(40) |  |

### user_feedback

用户反馈:对结果的评分与意见。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| result_record_id | varchar(64) |  |
| feedback_type | varchar(64) |  |
| rating | int |  |
| comment | text |  |
| correction_json | json |  |
| actor_id | varchar(64) |  |
| created_at | varchar(40) |  |

### workspaces

工作空间:多租户隔离单元(默认 default)。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | varchar(64) | 主键 |
| name | varchar(200) |  |
| status | varchar(32) |  |
| created_at | varchar(40) |  |
