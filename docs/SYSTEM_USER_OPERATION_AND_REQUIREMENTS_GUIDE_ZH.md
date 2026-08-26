# 语义计算工具库系统使用、输入输出与数据库需求说明书

> 适用版本：V7.74 全栈工程  
> 适用目录：`semantic_toolkit_final`  
> 读者：系统使用人员、产品经理、前端/后端开发人员，以及接手服务器部署和联调的 Claude  
> 权威依据：当前 Vue 在线测试页面、`frontend/src/data/requirement-contracts.ts`、`config/vue_contracts.py`、FastAPI 校验与结果归一化代码。

## 1. 文档目的

本说明书回答以下问题：

1. 用户如何在界面中使用19个功能点。
2. 每个请求参数的作用，以及为什么需要用户提供。
3. 哪些参数是必填、条件必填或选填。
4. 必填参数没有填写时，前端和后端应如何提示。
5. 成功后可视化弹窗应接收哪些响应字段，各字段是什么意思。
6. 哪些功能需要数据库，数据库在其中承担什么职责。
7. 正式服务器需要配置哪些运行环境、模型、数据库和文档解析能力。

本系统不使用原型演示数据冒充真实算法结果。预览可视化弹窗只用于检查界面；用户点击“开始测试”后，弹窗必须展示 FastAPI 返回的真实结果。

---

## 2. 正式运行环境要求

### 2.1 统一技术环境

| 组件 | 正式要求 | 作用 |
|---|---|---|
| 操作系统 | 推荐 Linux 服务器 | 部署 FastAPI、Vue、MySQL、模型和 MinerU |
| Python | Python 3.10 及以上，Docker 镜像使用 Python 3.12 | 运行 DDD 后端、算法、SDK 和数据库访问层 |
| Node.js | Node.js 22 | 构建 Vue 3 + Vite 前端 |
| Web 前端 | Vue 3 + Vite，生产环境由 Nginx 托管 | 在线测试、API/SDK说明、结果可视化 |
| 后端 | FastAPI + Uvicorn | 提供19个功能的 RESTful API |
| 大模型 | **统一使用 GLM-5.2** | 语步、分类、研究问题、引用、实体、标签、综述等需要语义理解或生成的环节 |
| 数据库 | **统一使用 MySQL 8**，建议 MySQL 8.4 | 保存任务、输入、结果、资源、历史依赖、词典、人工确认和评测数据 |
| 字符集 | `utf8mb4`，排序规则建议 `utf8mb4_0900_ai_ci` | 完整保存中文、英文及特殊符号 |
| 向量模型 | 服务器现有 BGE-M3；兼容 BGE small/large 配置 | 深度聚类、语义相似度、候选复核和检索 |
| PDF解析 | MinerU | 将论文、基金项目和科技报告 PDF 转换为结构化文本和章节路径 |
| 文档格式 | PDF、DOCX、TXT | 在线测试文件输入 |

### 2.2 正式环境变量

从 `config/.env.example` 创建 `config/.env`，正式环境至少配置：

```env
GLM_API_KEY=真实GLM密钥
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
GLM_MODEL=glm-5.2
GLM_REQUIRED_AT_STARTUP=true

DATABASE_URL=mysql+pymysql://semantic_app:数据库密码@127.0.0.1:3306/semantic_toolkit?charset=utf8mb4
DATABASE_AUTO_CREATE=true
DATABASE_REQUIRED=true

BGE_M3_PATH=/服务器模型目录/bge-m3
BGE_SMALL_PATH=/服务器模型目录/bge-small-zh-v1.5
BGE_LARGE_PATH=/服务器模型目录/bge-large-zh-v1.5
MINERU_BIN=mineru

CORS_ORIGINS=http://前端服务器地址
```

正式环境必须设置 `GLM_REQUIRED_AT_STARTUP=true` 和 `DATABASE_REQUIRED=true`。这样缺少大模型密钥或数据库连接失败时，系统会在启动或健康检查阶段明确暴露问题，避免带病运行。

### 2.3 服务与健康检查

- FastAPI：默认 `http://服务器:8000`。
- Vue开发环境：默认 `http://服务器:5173`。
- Docker生产前端：默认 `http://服务器:8080`。
- 接口文档：`/docs`。
- 健康检查：`GET /health`。
- 正式验收时 `/health` 应满足：
  - `status = ok`；
  - `database.connected = true`；
  - `llm_configured = true`；
  - `llm_model = glm-5.2`。

---

## 3. 参数状态、输入方式与错误提示规则

### 3.1 三种参数状态

| 状态 | 含义 |
|---|---|
| 必填 | 不提供就无法形成有效算法输入，系统不得开始测试 |
| 条件必填 | 只在指定输入方式或业务条件下由用户提供；其他模式由文件解析或数据库自动提供 |
| 选填 | 不提供不阻断算法，使用默认值、自动识别或只缺少结果标识信息 |

### 3.2 通用输入方式

| 页面模式 | 含义 |
|---|---|
| 单文本 | 用户输入一条文本，通常最多8000个清洗后字符 |
| 批量文本 | 用户添加多条独立文本；题目、项目名称和元数据必须逐条绑定 |
| 单文件 | 上传一个 PDF、DOCX 或 TXT 文件 |
| 批量文件 | 上传多个文件，每个文件形成独立结果或参与集合算法 |
| 历史结果 | 从数据库选择已经完成的上游任务结果 |
| 指定文献集 | 从数据库选择已经保存的文献集合 |

通用文件限制为单文件最大50 MB；结构化自动综述文件可放宽至80 MB。普通批量功能最多20条；深度聚类和结构化综述最多50篇。

### 3.3 通用前端提示

前端验证失败时统一显示：

```text
必填参数未完成：具体原因
```

常见具体原因包括：

- `请输入××。`
- `请至少添加一条文本。`
- `请输入文本N的内容。`
- `请选择一个文件。`
- `请至少上传一个文件。`
- `请配置必填资源“资源说明”。`

后端再次进行相同或更严格的验证。验证失败返回 HTTP 422，业务码为 `42201`，不会创建伪造的成功结果。

### 3.4 通用响应结构

单条成功响应：

```json
{
  "code": 0,
  "message": "success",
  "data": { "功能业务结果": "..." },
  "meta": {
    "task_id": "任务编号",
    "record_id": "结果记录编号",
    "input_type": "输入方式",
    "success_count": 1,
    "failed_count": 0
  }
}
```

批量成功响应中，`data.results[]` 每一项包含 `index`、`record_id`、`status` 和独立的 `result`。批量文献之间的题目、元数据、引用上下文和结果禁止串用。

### 3.5 文本位置与文件位置

- 文本输入：位置输出为字符范围，例如 `字符 72—98`。
- 文件输入：位置输出为章节标题路径，例如 `（一）立项依据 > 3．国内外研究现状 > 3.4 当前研究存在的不足`。
- 中英文摘要语步识别继续使用摘要句子位置。

### 3.6 “字段存在”和“结果有效”的区别

可视化合同要求字段必须存在，但正式业务验收还应满足：

- 输入中确实存在目标对象时，核心结果列表不能只返回空数组。
- 输入中确实不存在引用、定义、实体等对象时，允许结果列表为空，但统计字段必须明确返回0，并说明未识别到目标，而不是伪造结果。
- 趋势分析只有在文献包含真实发表时间时才应生成；缺少时间时允许为空。
- 深度聚类普通运行没有执行Gold评测时，`training_evaluation` 应明确为“未评测”，不能伪造 ARI、NMI 或专家一致率。

---

## 4. 数据库总体需求

### 4.1 为什么必须使用数据库

数据库不是只保存最终 JSON，而是承担六类业务职责：

1. 保存任务状态，使批量任务可以查询进度、失败原因和历史记录。
2. 保存每一条输入与结果的绑定关系，防止批量结果串用。
3. 保存分类标准、标注语料、术语库、本体等当前资源版本。
4. 保存跨功能依赖，例如实体关系识别复用哪一条NER结果。
5. 保存用户词典、文献集合、人工确认、修正和反馈。
6. 将结果投影到可查询业务表，支持筛选、统计、导出和系统集成。

### 4.2 所有19个功能共同使用的表

| 表 | 作用 |
|---|---|
| `analysis_tasks` | 保存工具、输入方式、请求参数、状态、进度、成功/失败数量 |
| `task_items` | 保存批量任务中每个输入项及其顺序 |
| `result_records` | 保存每条统一业务结果JSON及其版本 |
| `record_dependencies` | 保存上游与下游结果关系 |
| `exports` | 保存JSON、CSV、XML、RDF或报告导出记录 |
| `audit_events` | 保存关键操作审计日志 |
| `user_feedback` | 保存用户评价、问题反馈和纠正内容 |
| `model_versions` | 标记任务使用的模型版本 |

### 4.3 数据库资源表

`semantic_resources` 保存以下当前资源或用户上传版本：中图分类标注数据、分类映射规则、领域分类规则、人工标注数据、领域术语库、引用意图训练集、NER标注语料、本体分类体系等。资源记录包含类型、版本、来源、存储地址和内容哈希，保证历史任务可复现。

---

## 5. 19个功能点使用说明

## 5.1 中文摘要语步识别

**功能ID：** `zh-abstract-move`  
**接口：** `/api/v1/move/abstract/zh/{text|texts|file|files}`  
**用户目的：** 将中文摘要拆分为研究背景、目的、方法、结果、结论等语步。

### 操作流程

1. 选择单文本、批量文本、单文件或批量文件。
2. 输入中文摘要或上传包含摘要的文件。
3. 点击开始测试，查看语步结构化结果。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `chinese_scientific_abstract` | 必填 | 唯一待分析的中文摘要 | 单文本提示“请输入中文科技文献摘要”；批量提示具体第N条；文件提示选择文件 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 当前摘要的标题、语言和输入标识 |
| `moves[]` | 语步列表；每项包含语步类别、原文片段、句子位置和置信度 |
| `move_count` | 识别出的语步数量 |
| `sentence_count` | 参与分析的摘要句子数量 |

### 数据库

使用通用任务表，并写入 `move_results`、`move_segments`。数据库用于保存每句语步、位置和置信度，便于历史查询及批量导出。

## 5.2 英文摘要语步识别

**功能ID：** `en-abstract-move`  
**接口：** `/api/v1/move/abstract/en/{text|texts|file|files}`  
**用户目的：** 识别SCI/EI期刊或国际会议论文英文摘要的语步结构。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `english_scientific_abstract` | 必填 | 提供英文摘要，用于英文分句、上下文和语步判别 | 提示输入英文摘要或选择文件 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 文档和语言信息 |
| `moves[]` | 语步类型、摘要原句、句子位置、上下文和置信度 |
| `move_count` | 语步数量 |
| `sentence_count` | 英文摘要句子数量 |

### 数据库

写入 `move_results`、`move_segments`，用途与中文摘要语步识别一致。

## 5.3 中文基金项目语步识别

**功能ID：** `fund-move`  
**接口：** `/api/v1/move/fund/zh/{text|texts|file|files}`  
**用户目的：** 识别基金申请书、立项书或科研项目材料中的立项依据、研究目标、研究内容、方法、创新点等语步。

### 请求参数

| 参数 | 状态 | 作用 | 不提供的结果/提示 |
|---|---|---|---|
| `project_document_text` | 必填 | 项目材料正文，是语步识别对象 | 提示输入项目文本或选择文件 |
| `project_name` | 选填 | 标识文本结果；批量模式逐项目填写 | 不影响识别；缺省时使用系统记录名或文件名 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 项目名称、输入类型等信息 |
| `moves[]` | 项目语步类别、原文片段、文本/章节位置和置信度 |
| `move_count` | 项目语步数量 |
| `input_type` | `text`、`texts`、`file` 或 `files`，用于决定位置展示方式 |

### 数据库

写入 `move_results`、`move_segments`。如后续需要将结构化语步回写科研项目管理系统，可由 `external_writebacks` 保存回写状态。

## 5.4 中文科技文献自动分类

**功能ID：** `zh-classify`  
**接口：** `/api/v1/classify/clc/zh/{text|texts|file|files}`  
**用户目的：** 判断中文科技文本的中图分类号；先判断是否跨学科，再输出主分类、次分类及人工确认候选。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `chinese_scientific_document_text` | 必填 | 待分类的论文、会议稿、科技报告或政策文本 | 提示输入文本或选择文件 |
| `document_title` | 选填 | 标识结果，批量模式与文本逐篇绑定 | 不影响分类；可为空或由文件解析 |
| `clc_labeled_data` | 必填资源 | 当前标准中图分类号标注数据 | “请配置必填资源‘标准中图分类号标注数据’”；后端拒绝不存在或非当前版本资源 |

必填资源可以从数据库选择当前版本，也可以上传新的资源文件。资源类型不匹配时不得运行。

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `is_interdisciplinary` | 是否判断为跨学科 |
| `classifications[]` | 正式首选分类；跨学科时包含主分类和次分类，非跨学科时只有主分类 |
| `classification_confidence` | 总体及分类层级置信度 |
| `domain_labels[]` | 从分类结果派生的应用场景/领域标签 |
| `candidate_classifications[]` | 按置信度排序的候选；跨学科候选必须是另一组完整主次组合 |

### 数据库

- `semantic_resources`：保存中图分类号标注数据版本。
- `taxonomy_versions`、`taxonomy_nodes`：保存正式分类体系。
- `classification_results`、`classification_candidates`：保存首选和候选分类。
- `classification_confirmations`：保存用户最终确认的分类。

## 5.5 英文科技文献自动分类

**功能ID：** `en-classify`  
**接口：** `/api/v1/classify/clc/en/{text|texts|file|files}`  
**用户目的：** 将英文科技文献跨语言映射到中图分类体系，并支持跨学科主次分类。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `english_scientific_document_text` | 必填 | 英文论文、会议稿或科研项目文本 | 提示输入文本或选择文件 |
| `document_title` | 选填 | 标识文献结果 | 不影响算法 |
| `clc_standard_and_mapping_rules` | 必填资源 | 提供中图分类标准和英文术语到中图分类的映射规则 | 提示配置必填映射资源 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `is_interdisciplinary` | 是否跨学科 |
| `classifications[]` | 正式主/次分类结果 |
| `classification_confidence` | 分类置信度 |
| `cross_language_mapping[]` | 英文术语、英文类别与中图分类号之间的映射证据 |
| `domain_labels[]` | 领域标签 |
| `candidate_classifications[]` | 其他可供人工确认的分类或主次组合 |
| `literature_distribution_analysis_report` | 当前批次的分类数量和类别分布报告 |

### 数据库

使用 `semantic_resources` 保存映射规则，分类结果写入 `classification_results`、`classification_candidates`，人工确认写入 `classification_confirmations`。

## 5.6 专业领域科技文献分类

**功能ID：** `domain-classify`  
**接口：** `/api/v1/classify/domain/{text|texts|file|files}`  
**用户目的：** 在用户已经确定的专业大领域内部继续进行多层级细分，不允许跨出所选专业领域。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `domain_scientific_literature_data` | 必填 | 待细分的专业科技文本或文件 | 提示输入文本或上传文件 |
| `document_title` | 选填 | 标识文献结果 | 不影响分类 |
| `professional_domain` | 必填 | 限定分类搜索空间，例如材料科学、医学影像 | “请选择专业领域。”；后端返回 `domain 为必填项` |
| `domain_classification_rules` | 必填资源 | 定义领域内部三级类目和判断规则 | 提示配置必填资源 |
| `manually_labeled_training_data` | 必填资源 | 提供领域内边界样例和低置信结果校验依据 | 提示配置必填资源 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `professional_domain` | 用户选择的目标专业领域，必须与输出一致 |
| `multilevel_classification_results[]` | 该专业领域内的一级、二级、三级分类路径 |
| `classification_confidence` | 各层级及总体置信度 |
| `domain_labels[]` | 领域标签和细分类标签 |
| `candidate_classifications[]` | 同一专业大领域内的候选路径，用于人工确认 |
| `data_distribution_report` | 批量数据在各级分类中的数量和比例 |

### 数据库

资源写入 `semantic_resources`，分类结果写入 `classification_results`、`classification_candidates`，人工选择写入 `classification_confirmations`。

## 5.7 中文关键词识别

**功能ID：** `zh-keyword`  
**接口：** `/api/v1/keywords/zh/{text|texts|file|files}`  
**用户目的：** 从中文科技文本中提取结构化关键词，并允许用户词典增强术语命中。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示/默认行为 |
|---|---|---|---|
| `chinese_scientific_abstract` | 必填 | 待提取关键词的中文干净文本；字段名沿用需规，实际可提交普通科技文本 | 提示输入文本或文件 |
| `document_title` | 选填 | 标识文献 | 不影响关键词提取 |
| `domain_terminology_dictionary` | 选填 | 选择系统词典、数据库用户词典，或新建/上传用户词典 | 不提供时使用系统默认词典 |

当用户选择“自定义领域词典”时，词典术语或词典文件变为条件必填；都没有提供时提示：“已选择自定义领域词典，请填写词典术语或上传词典文件。”

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 文献标识信息 |
| `keywords[]` | 关键词、规范词、权重/置信度、来源位置、词典命中和映射信息 |
| `keyword_count` | 关键词数量 |

### 数据库

- `dictionaries`、`dictionary_versions`、`dictionary_terms`：保存用户自定义词典及版本。
- `keyword_results`、`keyword_items`：保存关键词和排名。
- 数据库保证后续任务可以继续选择用户已经建立的词典。

## 5.8 英文关键词识别

**功能ID：** `en-keyword`  
**接口：** `/api/v1/keywords/en/{text|texts|file|files}`  
**用户目的：** 提取英文关键词或主题短语，并规范缩写、词形及分类标签。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `english_scientific_abstract` | 必填 | 待处理英文科技文本 | 提示输入文本或文件 |
| `document_title` | 选填 | 标识文献结果 | 不影响识别 |
| `domain_terminology_library` | 必填资源 | 处理术语、缩写、别名和规范表达 | 提示配置领域术语库 |
| `classification_standard_mapping_table` | 必填资源 | 把英文术语映射为科研分类标签 | 提示配置分类标准映射表 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 文献信息 |
| `keywords_or_topic_phrases[]` | 英文关键词/短语、规范形式、权重、来源和分类映射 |
| `term_count` | 识别出的术语或主题短语数量 |

### 数据库

术语库和映射表由 `semantic_resources` 管理，结果写入 `keyword_results`、`keyword_items`。

## 5.9 研究问题识别

**功能ID：** `rq-detect`  
**接口：** `/api/v1/research-question/{text|texts|file|files}`  
**用户目的：** 识别显式或隐式研究问题，提取问题短语并形成结构化问题。

### 请求参数

| 参数 | 状态 | 作用 | 默认行为/提示 |
|---|---|---|---|
| `scientific_document_fragment` | 必填 | 待识别研究问题的科技文本 | 提示输入文本或选择文件 |
| `document_title` | 选填 | 使批量结果归属于正确文献 | 不影响算法；可为空或从文件解析 |
| `text_format_requirement` | 选填 | 指定纯文本、章节文本或JSON格式 | 默认自动识别 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 文献标题和输入标识 |
| `research_question_sentences[]` | 原文中的显式/隐式研究问题句、表达方式、位置和置信度 |
| `research_question_phrases[]` | 从问题句提炼的研究问题短语 |
| `structured_research_questions[]` | 规范化问题、问题类型、约束条件及置信度 |
| `research_question_statistics` | 问题句、问题短语、显式/隐式分布等统计 |

### 数据库

写入 `research_question_results`、`research_question_items`。保存句、短语、结构化问题及其文献归属，解决批量结果无法追踪来源的问题。

## 5.10 引用情感识别

**功能ID：** `citation-sentiment`  
**接口：** `/api/v1/citation-sentiment/{text|texts|file|files}`  
**用户目的：** 判断引用句对被引研究的态度属于支持、中立或指出局限性。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示/文件模式行为 |
|---|---|---|---|
| `scientific_document_full_text` | 必填 | 引用句所属的文献文本；用于识别语境 | 文本模式提示“请输入文献文本”；文件模式上传文献 |
| `citation_sentence_and_context` | 文本模式条件必填 | 每条包含引用句、前一句和后一句 | 缺引用句提示“请输入引用句文本”；缺上下文提示“请同时填写引用句上文和下文”；文件模式由系统抽取 |
| `citation_metadata` | 文本模式条件必填；文件模式自动解析 | 被引文献元数据，可粘贴原始参考文献条目后解析，也可上传元数据 | 文本模式提示提供被引文献元数据；文件模式从参考文献列表解析，失败时用户补充 |

批量文本中，文献全文、引用句、前后文和参考文献元数据必须逐条对应。批量元数据不是合法JSON时提示：“批量参考文献元数据必须是合法的 JSON 数组，或改为上传元数据文件。”

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 当前文献信息 |
| `citation_sentiment_results[]` | 引用句、前后文、情感标签、判定证据和置信度 |
| `citation_sentiment_statistics` | 引用句总数以及支持、中立、有局限性等数量分布 |

### 数据库

写入 `citation_results`、`citation_items`。数据库保存引用句、标签、上下文、元数据、证据和置信度，便于按文献或情感类型检索。

## 5.11 引用意图识别

**功能ID：** `citation-intent`  
**接口：** `/api/v1/citation-intent/{text|texts|file|files}`  
**用户目的：** 判断引用的用途，如背景介绍、方法引入、结果比较等。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示/文件模式行为 |
|---|---|---|---|
| `citation_sentence_and_context` | 文本模式条件必填 | 引用句、上文和下文，是意图判断的主要输入 | 提示填写引用句和前后文；文件模式自动抽取 |
| `citation_metadata` | 文本模式条件必填；文件模式自动解析 | 关联被引文献 | 文本模式必须提供；文件解析失败时补充 |
| `preprocessed_training_set` | 必填资源 | 约束背景介绍、方法引入、结果比较等标签边界 | 提示配置预处理训练集 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 当前文献信息 |
| `citation_intent_results[]` | 引用句、上下文、意图标签、判断证据和置信度 |
| `citation_intent_statistics` | 各类引用意图的数量统计；不是训练集摘要 |

### 数据库

训练集由 `semantic_resources` 管理，结果写入 `citation_results`、`citation_items`。

## 5.12 概念定义识别

**功能ID：** `definition-detect`  
**接口：** `/api/v1/concept-definition/{text|texts|file|files}`  
**用户目的：** 识别定义句、概念词并建立“概念—定义”映射。

### 请求参数

| 参数 | 状态 | 作用 | 默认行为/提示 |
|---|---|---|---|
| `scientific_document_fragment_or_batch_text` | 必填 | 待提取概念和定义的文本或文件 | 提示输入文本或选择文件 |
| `domain_label` | 选填 | 限定同名概念的专业语境 | 默认自动识别领域 |
| `output_format_requirement` | 选填 | 指定JSON、CSV或数据库结构 | 默认JSON |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 当前文献信息；批量结果必须与输入逐篇对应 |
| `definitions[]` | 定义句、概念、定义内容、位置及置信度 |
| `concept_definition_mappings[]` | 美观展示的概念—定义对应关系；不额外要求来源和置信度 |
| `statistical_analysis_report` | 定义句数量、概念数量、映射数量和位置/章节分布报告 |

### 数据库

写入 `definition_results`、`definition_items`，用于按概念检索定义并追溯到原文位置。

## 5.13 中英文通用领域命名实体识别

**功能ID：** `general-ner`  
**接口：** `/api/v1/ner/general/{text|texts|file|files}`  
**用户目的：** 从中英文科技文本中识别人名、地名、机构、事件等通用实体。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `bilingual_scientific_document_text` | 必填 | 中英文科技文本 | 提示输入文本或文件 |
| `general_domain_annotated_corpus` | 必填资源 | 提供通用实体类别和标注样例 | 提示配置通用领域标注语料 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 当前文本/文件信息 |
| `entities[]` | 实体表达、实体类别、字符/章节位置、语境片段和置信度；不输出需规未要求的缩写和别名 |
| `summary` | 实体总数及按类别统计 |

### 数据库

语料由 `semantic_resources` 管理，结果写入 `entity_results`、`entity_mentions`。每条NER结果还可成为实体关系识别的上游记录。

## 5.14 中英文通用科研实体识别

**功能ID：** `research-ner`  
**接口：** `/api/v1/ner/research/{text|texts|file|files}`  
**用户目的：** 识别研究方法、科研任务、数据资料、仪器设备等科研实体，并映射规范词。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `academic_abstract_or_technical_report_text` | 必填 | 学术论文摘要、科技报告或其他科研文本 | 提示输入文本或文件 |
| `multi_domain_scientific_corpus` | 必填资源 | 覆盖不同学科科研表达，提升跨领域识别能力 | 提示配置多领域科研语料 |
| `manually_labeled_data` | 必填资源 | 监督科研实体边界、类型和规范词映射 | 提示配置人工标注数据 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 文献信息 |
| `entities[]` | 当前识别表达、科研实体类型、位置、上下文和置信度 |
| `standard_term_mappings[]` | 科研实体到规范术语的映射；不显示无需求的“当前识别表达”说明列 |
| `summary` | 实体数量和类型分布 |

### 数据库

资源由 `semantic_resources` 管理，实体和规范映射写入 `entity_results`、`entity_mentions`。

## 5.15 专业领域科研实体识别

**功能ID：** `domain-ner`  
**接口：** `/api/v1/ner/domain/{text|texts|file|files}`  
**用户目的：** 在专业本体约束下识别细粒度实体，并映射标准知识库编号。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `domain_scientific_document_text` | 必填 | 专业科研文献文本 | 提示输入文本或文件 |
| `ontology_classification_system` | 必填资源 | 定义实体类型和本体分类路径 | 提示配置当前本体分类体系 |
| `domain_labeled_training_data` | 必填资源 | 提供专业实体边界和类型标注样例 | 提示配置领域标注训练数据 |

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `document` | 文献信息 |
| `selected_domain` | 识别采用的专业领域 |
| `entities[]` | 当前识别表达、领域标签、实体类型、位置、语境、知识库ID、映射状态和置信度 |
| `ontology_mappings[]` | 实体到本体分类路径和知识库节点的映射 |
| `summary` | 实体及映射统计 |

没有真实知识库编号时应明确显示“未映射”，不得伪造编号。

### 数据库

- `semantic_resources`：保存本体和标注数据资源版本。
- `ontology_versions`、`ontology_nodes`：保存可查询本体结构。
- `entity_results`、`entity_mentions`：保存实体及映射。

## 5.16 实体关系识别

**功能ID：** `relation-extract`  
**接口：** `/api/v1/relation/from-ner-record`  
**用户目的：** 在已完成NER结果基础上识别实体之间的关系，并生成依存句法证据和RDF。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示 |
|---|---|---|---|
| `upstream_ner_record_id` | 必填历史记录 | 用户从数据库选择一条已完成的NER结果；后端自动读取原句和实体列表 | “请选择一条已完成的命名实体识别记录。” |

用户不需要手工输入原始句子、实体列表或依存句法。依存句法由实体关系工具内部执行。批量NER中的每条结果通过 `task_item_id` 精确绑定自己的原文，选择不同记录必须得到对应文本和实体。

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `upstream_ner_record_id` | 本次关系识别使用的NER结果编号 |
| `original_sentence` | 从该NER记录读取的原始句子/文本 |
| `dependency_parse[]` | 句子编号、中心词、依存关系和依存词 |
| `dependency_paths[]` | 每个关系三元组对应的依存路径 |
| `relation_triples[]` | 主体—关系—客体、上下文证据和置信度 |
| `context_fragments[]` | 支撑关系判断的上下文片段 |
| `rdf_representation` | 三元组的RDF表示 |

### 数据库

- 从 `analysis_tasks`、`task_items`、`result_records` 读取NER历史结果。
- `record_dependencies` 记录关系结果来源于哪条NER记录。
- `relation_results`、`relation_triples` 保存关系及证据。

数据库是该功能的必要前提，没有历史NER记录就不能开始测试。

## 5.17 深度聚类

**功能ID：** `deep-cluster`  
**接口：** `/api/v1/cluster/deep/texts`、`/api/v1/cluster/deep/files`  
**独立评测接口：** `/api/v1/cluster/deep/evaluate`  
**用户目的：** 按技术路线或应用场景，将多篇科技文本聚合为语义类簇。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示/默认行为 |
|---|---|---|---|
| `scientific_document_texts` | 必填集合 | 至少4篇文本或4个文件；可以是论文、科技报告等 | 少于4篇提示“深度聚类至少需要4篇……” |
| `document_metadata` | 必填 | 与每篇内容一一对应；文献编号和发表时间必填，题名、作者、来源、关键词选填 | 提示完整填写第N篇的文献编号、发表时间和文本；后端检查数量一一对应 |
| `cluster_dimension` | 必填 | 选择技术路线或应用场景；两条路线使用各自适合的语义表示和聚类策略 | “请选择聚类维度。” |
| `clustering_algorithm_type` | 选填 | 自动选择、K-Means、HDBSCAN或层次聚类 | 默认自动选择 |
| `cluster_count` | 选填 | 用户指定类簇数量 | 不提供时自动估计 |
| `output_format` | 选填 | JSON、CSV或数据库结构 | 默认JSON |

技术路线关注方法、模型、算法和实验技术；应用场景关注任务、对象、行业、环境和应用目标。

### 独立评测资源

`training_samples` 和 `manually_labeled_category_data` 只用于独立模型性能评测，从数据库选择当前资源。它们不属于普通用户上传文献的聚类请求，不提供也不影响日常聚类。

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `cluster_dimension` | `technology` 或 `application_scenario` |
| `cluster_dimension_name` | 技术路线聚类或应用场景聚类 |
| `input_summary` | 文献数量、解析句子数量等输入摘要 |
| `clustering_quality` | 类簇数量、簇内相似度、簇间区分度、语义密度等当前任务质量指标 |
| `training_evaluation` | 独立评测结果；未运行评测时必须明确“未评测” |
| `clusters[]` | 类簇编号、规模、占比、代表术语、代表文献和特征统计 |
| `document_assignments[]` | 每篇文献所属类簇、相似度和关键证据 |
| `semantic_projection` | 可视化散点图坐标及文献—类簇关系 |
| `theme_trend_analysis` | 有真实年份时生成各类簇年度趋势；无年份允许为空 |

### 数据库

- `cluster_runs`：每次聚类运行。
- `clusters`：类簇及代表术语。
- `cluster_memberships`：文献与类簇归属。
- `cluster_revisions`、`cluster_corrections`：人工调整和修正。
- `model_evaluation_runs`：独立记录Gold版本、样本量、ARI、NMI、轮廓系数等真实指标。

## 5.18 聚类标签生成

**功能ID：** `cluster-label`  
**接口：** `/api/v1/cluster-labels/generate`、`/api/v1/cluster-labels/from-cluster-task`  
**用户目的：** 为深度聚类输出的每个类簇生成简短、代表性强且相互可区分的标签。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示/默认行为 |
|---|---|---|---|
| `cluster_phrase_sets` | 必填历史数据 | 深度聚类每个类簇的代表短语集合；Vue中由用户选择已完成的深度聚类任务，系统自动读取 | “请选择一项已完成的深度聚类任务”；任务无短语时提示“没有可用的类簇短语集合” |
| `label_length_limit` | 选填 | 限制标签长度 | 默认12 |
| `language_type` | 选填 | 自动、中文或英文 | 默认自动 |
| `distinctiveness_threshold` | 选填 | 控制不同类簇标签的最低区分要求，数值控件限制0—1 | 默认0.75 |

API/SDK可以直接提交 `cluster_phrase_sets`；普通Vue用户不手工编写，而是从数据库历史聚类任务中选择。

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `cluster_count` | 输入类簇数量 |
| `generated_label_count` | 成功生成标签的类簇数量 |
| `parameters` | 本次标签长度、语言和差异度阈值 |
| `labels[]` | 类簇编号、推荐标签、置信度、区分度、候选标签、关联文献和证据 |
| `statistics` | 标签长度、语言、质量等统计 |
| `label_generation_process_report` | 特征汇总、候选生成、差异化筛选和推荐标签输出过程报告 |
| `label_distinctiveness_optimization_result` | 标签间重复/近义检查、调整前后对比和优化说明 |

### 数据库

- 从 `cluster_runs`、`clusters`、`cluster_memberships` 读取深度聚类结果。
- `record_dependencies` 保存标签任务与聚类任务关系。
- `cluster_label_results`、`cluster_labels` 保存标签、候选和证据。
- `cluster_label_confirmations` 保存用户最终确认标签。

## 5.19 结构化自动综述

**功能ID：** `structured-review`  
**接口：** `/api/v1/review/structured/texts`、`/api/v1/review/structured/files`、`/api/v1/review/structured/collections`  
**用户目的：** 对文献集进行研究问题聚类，匹配研究方法，归纳研究进展，并生成可溯源的结构化综述。

### 请求参数

| 参数 | 状态 | 作用 | 未填写提示/不同模式行为 |
|---|---|---|---|
| `document_set` | 必填集合 | 至少3篇批量文本、3个文件或数据库指定文献集 | 文本/文件少于3篇时提示；集合模式未选择时提示“请选择指定文献集” |
| `topic_or_keywords` | 必填 | 限定本次综述要回答的主题范围，不等于人为指定聚类标签 | “请输入研究主题或关键词。” |
| `document_metadata` | 条件必填 | 文本模式逐篇提供文献编号，题名、作者、机构、年份、来源、关键词可选；文件模式解析或上传；集合模式从数据库读取 | 文本模式元数据必须与文献逐篇对应；文件解析失败时补充 |

批量文本每篇必须填写文献编号和文本。题名不是算法必填项，但建议填写以增强报告可读性和证据溯源。

### 弹窗响应

| 字段 | 含义 |
|---|---|
| `review_id` | 综述任务业务编号 |
| `topic` | 本次研究主题或关键词 |
| `document_count` | 参与综述的文献数量 |
| `statistics` | 研究问题、方法节点和证据句数量 |
| `tree[]` | 研究问题—研究方法—研究进展三层结构；每个研究问题下同一证据文献只保留必要引用 |
| `cluster_induction_results` | 研究问题聚类及类簇归纳结果 |
| `structured_report` | 报告形式的标题、概述和分节正文 |
| `trend_hotspot_distribution` | 有真实时间元数据时形成趋势与热点分布 |
| `evidence_index[]` | 节点到原始文献及关键句段的溯源索引 |

结构化自动综述不要求用户关联历史深度聚类任务。其内部可以对研究问题进行语义聚类，但这是综述算法自己的步骤。

### 数据库

- `documents`：保存文献内容和元数据。
- `document_collections`、`collection_documents`：保存可供用户选择的已有文献集。
- `review_results`：保存综述主题和总体结果。
- `review_nodes`：保存研究问题、研究方法、研究进展树节点。
- `review_sections`：保存结构化文本报告章节。
- `review_evidence_links`：保存每个节点关联的原文证据。

数据库使用户可以直接选择已有文献集，并保证综述的任意节点都能回溯到原始文献。

---

## 6. 数据库与功能点对应总表

| 功能点 | 必须使用的业务表 | 数据库主要作用 |
|---|---|---|
| 中英文摘要、基金项目语步识别 | `move_results`、`move_segments` | 保存语步及位置 |
| 三类自动分类 | `classification_results`、`classification_candidates`、`classification_confirmations` | 保存首选、候选和人工确认 |
| 中文关键词 | `dictionaries`、`dictionary_versions`、`dictionary_terms`、`keyword_results`、`keyword_items` | 保存用户词典和关键词 |
| 英文关键词 | `semantic_resources`、`keyword_results`、`keyword_items` | 保存术语映射资源和关键词 |
| 研究问题 | `research_question_results`、`research_question_items` | 保存问题句、短语和结构化问题 |
| 引用情感、引用意图 | `citation_results`、`citation_items` | 保存引用句、上下文、标签和元数据 |
| 概念定义 | `definition_results`、`definition_items` | 保存概念、定义及位置 |
| 三类NER | `entity_results`、`entity_mentions` | 保存实体、类型、映射和语境 |
| 实体关系 | `record_dependencies`、`relation_results`、`relation_triples` | 读取指定NER历史并保存关系 |
| 深度聚类 | `cluster_runs`、`clusters`、`cluster_memberships`、`model_evaluation_runs` | 保存类簇、成员、趋势和评测 |
| 聚类标签 | `record_dependencies`、`cluster_label_results`、`cluster_labels`、`cluster_label_confirmations` | 从历史类簇生成并确认标签 |
| 结构化综述 | `documents`、`document_collections`、`collection_documents`、`review_*` | 选择文献集、保存树、报告和证据 |

分类标准、语料、训练数据、本体等资源统一由 `semantic_resources` 管理，不应在业务请求中硬编码虚假版本。

---

## 7. 给服务器接手开发人员或 Claude 的强制实现规则

1. 以 `config/vue_contracts.py` 中的公共字段名为准，不把内部算法DTO字段暴露给Vue。
2. API、SDK、在线测试必须覆盖相同的业务参数；调用写法可以不同，但含义和必填规则必须一致。
3. 前端验证不能替代后端验证，FastAPI必须对必填项、资源版本、数量、范围和逐篇对应关系再次检查。
4. 真实在线测试禁止读取 `demo-data`、原型响应或预览数据。
5. 可视化字段缺失时不能用虚假业务内容补齐；允许为空的字段必须有明确业务原因。
6. 批量任务必须按 `task_items.input_index` 和 `task_item_id` 绑定输入、结果和上游历史，禁止总是读取第一篇文本。
7. 资源输入只能是数据库当前资源或用户上传资源；无效、类型不匹配或过期资源必须返回422。
8. 关系识别只接收NER历史编号；聚类标签优先读取深度聚类历史；结构化综述直接接收文献集，不依赖历史深度聚类。
9. 文本位置使用字符范围，文件位置使用章节标题路径。
10. 正式服务器统一使用 GLM-5.2 和 MySQL 8；本地降级只能用于开发测试，不能作为甲方验收结果。
11. 每个成功任务必须保存 `analysis_tasks`、`task_items`、`result_records`，并写入相应业务投影表。
12. 真实验收不能只断言字段存在，还必须验证核心结果非空、内容与输入一致、批量不串用、数据库记录可回查。

---

## 8. 正式上线验收清单

- [ ] `/health` 显示 MySQL 已连接、GLM-5.2 已配置。
- [ ] 19个功能均完成至少一次真实GLM/真实模型调用。
- [ ] 所有单文本、批量文本、单文件、批量文件和数据库模式均按页面支持范围测试。
- [ ] 每个必填参数缺失时，前端显示明确提示，后端返回HTTP 422。
- [ ] 所有核心弹窗字段有真实内容，或有合理的空结果说明。
- [ ] 批量结果逐篇对应，没有题目、元数据、引用上下文或结果串用。
- [ ] 文件结果返回章节路径，文本结果返回字符位置。
- [ ] 必填资源从MySQL读取当前版本，上传资源能登记版本和哈希。
- [ ] 实体关系可以切换不同NER历史记录，并得到对应原文结果。
- [ ] 聚类标签能从所选深度聚类任务读取真实类簇短语。
- [ ] 结构化综述能从MySQL选择已有文献集并回溯证据。
- [ ] MySQL中的任务表、结果表和业务投影表均有对应记录。
- [ ] 预览数据没有进入真实接口响应或数据库。

