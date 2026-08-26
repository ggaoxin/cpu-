# Vue—后端输出字段差异与补充记录

版本：2026-08-04  
依据：《语义计算工具 Vue 前后端与数据库设计方案》、当前 Vue 19 个功能页面、`SemanticApplicationService` 的实际结果组装代码。

## 1. 记录规则

| 状态 | 含义 |
|---|---|
| 已补充 | 后端已有真实原始数据，或可由真实原文/结果确定性计算，已在后端结果代码中补齐 |
| 已映射 | 后端已有同义字段，仅在应用层统一名称和层级，不改变算法结果 |
| 空值占位 | 为保证 Vue schema 稳定返回 `null`、`[]` 或 `{}`，不使用演示数据 |
| 待算法提供 | 只有算法重新计算或模型额外输出才能获得，当前不能可靠推导 |
| 待外部资源 | 依赖正式分类体系、本体、文献数据库或外部业务系统 |

统一响应 `code/message/data/meta`、`task_id`、`record_id`、任务状态、批量计数、模型版本、耗时和导出格式由 `ToolIntegrationService` 统一补充，适用于全部 19 个功能。

## 2. 19 个功能输出对接总表

| 所属功能 | Vue 工具 ID | 原项目核心输出 | Vue 稳定结果字段 | 已完成的后端处理 | 尚缺真实来源的字段 |
|---|---|---|---|---|---|
| 中文摘要语步识别 | `zh-abstract-move` | `spans[]` | `moves[]`, `move_statistics` | 映射语步代码/名称、句序、文本、章节、页码、置信度并统计 | 原算法未返回时的精确 `start/end` |
| 英文摘要语步识别 | `en-abstract-move` | `spans[]` | `moves[]`, `move_statistics` | 与中文语步使用同一稳定结构 | 原算法未返回时的上下文和精确字符位置 |
| 中文基金项目语步识别 | `fund-move` | `move_type/content/sources/text_location` | `project_title`, `project_metadata`, `moves[]`, `move_statistics`, `writeback` | 补充语步置信度、来源片段和统计；写回默认状态明确为未请求 | 项目编号/申请人、真实章节页码、外部项目记录 ID |
| 中文科技文献分类 | `zh-classify` | `main_classification`, `auxiliary_classifications`, `rag_top_k_candidates` | `primary_classification`, `classifications[]`, `candidates[]`, `domain_labels`, `confirmation_status`, `taxonomy_version` | 映射主/辅分类、候选、路径和确认状态 | 正式 CLC 版本编号与完整覆盖证明 |
| 英文科技文献分类 | `en-classify` | 同中文分类 | 中文分类字段 + `cross_language_mapping`, `distribution_report` | 主分类、辅分类和候选已统一 | 跨语言映射明细、正式映射规则版本；需算法/资源提供 |
| 专业领域科技文献分类 | `domain-classify` | `domain_code/name`, `clc_classification`, `rag_top_k_candidates` | `selected_domain`, `levels[]`, `primary_classification`, `candidates[]`, `domain_labels` | 映射用户领域、CLC 结果和多层展示结构 | 正式专业分类体系版本和节点覆盖数据 |
| 中文关键词识别 | `zh-keyword` | `keyword`, `weight` | `keywords[]`, `dictionary_usage`, `statistics` | 补充排序/位置；已接入词典保存、版本选择、候选合并、权重增量、命中词条 ID 和命中统计 | 无正式用户词表时不返回命中；系统预置词表版本尚未数据化 |
| 英文关键词识别 | `en-keyword` | `keyword`, `weight` | 中文关键词字段 + 规范词和 CLC 映射 | 与中文共用可版本化用户词典链路，按语言隔离 | 词形归一结果、`clc_mappings` 和映射规则版本 |
| 研究问题句及短语识别 | `rq-detect` | `sentence/phrase/implication` | 问题句、问题短语、结构化问题、统计 | 后端补充句/短语字符位置、序号、置信度透传，并拆成三组视图数据 | 章节、页码、显式/隐式类型（算法未输出时） |
| 引用情感识别 | `citation-sentiment` | `sentence/marker/context/sentiment/confidence` | `citations[]`, `citation_sentiment_results[]`, `statistics` | 后端补充引用 ID、字符位置、统一上下文和三类统计 | 页码、章节、完整参考文献元数据 |
| 引用意图识别 | `citation-intent` | `sentence/marker/context/intent/confidence` | `citations[]`, `citation_intent_results[]`, `statistics` | 与引用情感使用同一稳定引用结构 | 训练证据 ID、页码、章节、完整参考文献元数据 |
| 概念定义识别 | `definition-detect` | `sentence/concept/pattern/context/confidence` | `definitions[]`, `statistics` | 后端补充 `definition`、`normalized_concept`、字符位置和统计 | 独立的定义内容边界、知识库映射 ID、页码/章节 |
| 通用领域实体识别 | `general-ner` | 模型返回实体列表 | `entities[]`, `statistics` | 统一 `entity_id/text/type/confidence` 别名和类型统计 | 模型未返回时的规范实体 ID、位置和上下文 |
| 通用科研实体识别 | `research-ner` | 模型返回科研实体列表 | `entities[]`, `statistics` | 保留模型全部字段并统一展示别名 | 受版本控制的实体类型 schema、标准术语和词表 ID |
| 专业领域实体识别 | `domain-ner` | 模型返回专业实体列表 | `selected_domain`, `ontology_version`, `entities[]`, `statistics` | 透传用户领域/本体版本并统一实体结构 | 正式 ScienceWISE 节点、`kb_id/type_path/standard_term` |
| 实体关系识别 | `relation-extract` | 模型返回关系/三元组列表 | `source_records`, `triples[]`, `statistics` | 映射主语/谓语/宾语别名，补充真实上游记录 ID 和统计 | 依存 token/边、实体 mention 外键、算法未给出的证据位置 |
| 科技文献深度聚类 | `deep-cluster` | `documents`, `technical_topics`, `application_topics` | `cluster_task_id`, `dimension`, `clusters[]`, `quality_metrics`, `correction_status` | 生成真实任务 ID；按所选轴转换类簇，并从文档映射构造成员 | 轮廓系数、DB 指数、二维投影；当前算法未计算 |
| 类簇标签自动生成 | `cluster-label` | `clusters[{cluster_id,label,doc_indices,n}]` | `source_cluster_task_id`, `labels[]`, `generation_report` | 关联真实聚类任务，统一标签列表和生成数量 | `confidence/distinctiveness/alternatives/evidence_terms` 需标签算法输出 |
| 结构化自动综述 | `structured-review` | `background`, `tree[rq/method/progress/conclusion/doc_indices]`, `problems`, `trends` | `review_id`, `topic`, `tree`, `sections`, `evidence`, `trend_analysis`, `hotspots`, `traceability` | 生成真实综述记录 ID；转换三层树，构造真实文献引用关系和背景章节 | 证据页码/原文 quote、热点权重；需文档解析或算法返回 |

## 3. 已修改的后端字段明细

| 所属功能 | 补充字段 | 修改文件 | 字段来源 | 修改原因 |
|---|---|---|---|---|
| 中英文关键词 | `term`, `normalized_term`, `score`, `confidence`, `rank`, `source`, `source_position` | `application/service/semantic_service.py` | 关键词、真实权重、原始输入文本 | Vue 需要排序、权重和原文位置；原项目只返回 `keyword/weight` |
| 中英文关键词 | `dictionary_id`, `dictionary_version`, `custom_dictionary`, `custom_dictionary_hit`, `matched_dictionary_term_id`, `dictionary_usage` | `frontend/src/components/ToolRequestExtras.vue`、`application/service/tool_integration_service.py`、`application/service/semantic_service.py` | 用户保存的指定词典版本、术语及真实原文命中 | 原 Vue 只能在浏览器临时导入词表，后端算法无法复用和追溯；现已改为版本化数据库资源并在候选阶段生效 |
| 研究问题 | `sentence_index`, `start/end`, `phrase_start/phrase_end`, `confidence` | `application/service/semantic_service.py` | 原问题句、短语和原文确定性查找 | 支持问题句/短语列表以及原文定位 |
| 基金语步 | `source_sections`, `confidence` | `application/service/semantic_service.py` | 已有分段来源和片段置信度 | Vue 语步溯源表需要来源与置信度 |
| 引用情感/意图 | `citation_id`, `source_position` | `application/service/semantic_service.py` | 引用句及原文字符位置 | Vue 引用列表和定位需要稳定 ID 与位置 |
| 概念定义 | `definition`, `normalized_concept`, `source_position` | `application/service/semantic_service.py` | 真实定义句、概念和原文位置 | 原输出没有 Vue 直接读取的 `definition` 字段 |
| 全部 19 功能 | 工具专属字段别名、统计、数组层级 | `application/service/result_normalizer.py` | 原算法真实结果 | 统一不同算法的字段命名，供 Vue 可视化直接读取 |
| 深度聚类/标签/综述 | `cluster_task_id`, `source_cluster_task_id`, `review_id` | `application/service/tool_integration_service.py` | 数据库真实任务/结果编号 | 下游历史选择和结果血缘必须使用真实稳定 ID |
| 全部 19 功能 | 缺失字段的 `null/[]/{}` schema 占位 | `application/service/tool_integration_service.py` | 无业务值，仅固定响应结构 | 避免 Vue 因字段不存在报错；空值不代表算法已实现 |
| 全部 19 功能 | 输入模式、请求字段、结果字段能力清单 | `config/vue_contracts.py`、`GET /api/v1/capabilities` | Vue 页面与设计方案 | 以 Vue 为接口基线，避免后端 DTO 反向限制页面 |

## 4. 当前不能在输出代码中伪造的字段

| 字段类别 | 涉及功能 | 缺少原因 | 正确补齐方式 |
|---|---|---|---|
| 正式分类体系版本与覆盖 | 三个分类功能 | 项目未装载经确认的 CLC/专业体系版本数据 | 导入正式 `taxonomy_versions/taxonomy_nodes` 后由任务记录引用版本 |
| 本体节点与知识库 ID | 专业实体识别 | 未提供正式 ScienceWISE 数据及版本 | 导入 `ontology_versions/ontology_nodes`，由实体算法返回节点 ID |
| PDF 页码、章节和精确证据 quote | 基金、引用、定义、综述 | 当前文本抽取链没有把页码/章节偏移完整传到算法结果 | 文档解析阶段保存结构化段落和页码，再让结果引用段落 ID |
| 聚类质量指标和二维投影 | 深度聚类 | 当前实现是主题映射，未执行相应指标/降维计算 | 聚类服务增加真实指标计算后返回，不用前端随机图形 |
| 标签差异度、候选和证据词 | 类簇标签 | 当前标签服务只生成主标签 | 修改标签算法输出 schema，并基于类簇词项实际计算 |
| 引用元数据和训练证据 | 两个引用功能 | 当前只从正文抽取引用标记和上下文 | 接入参考文献解析、文献数据库和训练证据索引 |
| 外部项目写回 ID | 基金语步 | 未提供目标数据库、字段映射和认证 | 业务确认后通过 `external_writebacks` 执行，不在分析请求中假定成功 |

## 5. 用户自定义词表交互与数据库方案

用户自定义词表只用于 `zh-keyword` 和 `en-keyword`。实体类型选择、专业分类体系和本体节点不是词表，仍按各自的配置与版本表管理。

| 环节 | Vue/接口输入 | 后端与数据库处理 | Vue 可读取输出 | 建库原因 |
|---|---|---|---|---|
| 新建词表 | `name`, `language`, `weight_boost`, `terms[]` | `POST /api/v1/dictionaries`；写入 `dictionaries`、`dictionary_versions`、`dictionary_terms` | `id`, `version_id`, `version`, `term_count` | 词表需要跨会话、跨任务复用，不能只保存在浏览器内存 |
| 保存新版本 | 同名、同语言再次保存 | 保留旧版本并递增 `current_version`，不覆盖历史术语 | 新版本号和当前术语数 | 历史关键词结果必须能复现当时使用的词表 |
| 选择词表 | `dictionary_id` | `GET /api/v1/dictionaries/{id}` 读取当前版本和版本清单 | 名称、当前版本、`versions[]`、`terms[]` | Vue 需要展示数据库中的真实资源，而非固定下拉示例 |
| 选择历史版本 | `dictionary_id`, `dictionary_version` | 读取指定 `dictionary_versions.version` 对应术语 | 该版本权重和术语列表 | 支持对比、复跑以及结果追溯 |
| 执行关键词任务 | 上述 ID/版本，或未保存的 `custom_dictionary` | 应用层加载指定版本；算法在候选合并阶段匹配原文、加权并排序 | `keywords[].custom_dictionary_hit`、`matched_dictionary_term_id`、`dictionary_usage` | 命中必须来自真实原文与真实词条，不能由输出适配器伪造 |

## 6. 验收要求

1. 19 个工具响应都必须包含 `data.results[].result`。
2. `config/vue_contracts.py` 声明的每个结果字段都必须存在。
3. Vue 可视化只读取当前真实响应；演示数据只在明确的演示预览中使用。
4. 空值字段必须能追溯到本文件中的缺口，不得用固定示例值冒充。
5. 新增真实算法字段后，同时更新本表、契约测试和可视化验收截图。
