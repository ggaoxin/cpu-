# 19 个 Vue 功能输入输出与数据库复用矩阵

所有输出均位于统一响应的 `data.results[].result`。

| Vue 功能 | 主要接口 | Vue 输入 | 后端稳定输出 | 历史/数据库用途 |
|---|---|---|---|---|
| `zh-abstract-move` | `/move/abstract/zh/{text,texts,file,files}` | 中文摘要、置信度与聚合选项 | `moves`, `move_statistics` | 保存任务/结果，供文献结构索引和导出 |
| `en-abstract-move` | `/move/abstract/en/{text,texts,file,files}` | 英文摘要 | `moves`, `move_statistics` | 同上，保存语言与模型版本 |
| `fund-move` | `/move/fund/zh/{file,files}` | 基金申报文件 | `moves`, `move_statistics`, `writeback` | 为外部项目写回保存可审计来源 |
| `zh-classify` | `/classify/clc/zh/{text,texts,file,files}` | 标题/摘要至少一项、关键词 | `classifications`, `candidates`, `domain_labels` | 分类候选确认、分类体系版本、批量统计 |
| `en-classify` | `/classify/clc/en/{text,texts,file,files}` | 英文标题/摘要/关键词 | 同上 | 支持 JSON/CSV/XML 导出和人工确认 |
| `domain-classify` | `/classify/domain/{text,texts,file,files}` | 专业领域、标题/摘要/关键词 | `classifications`, `domain_labels`, 原领域字段 | 保存专业体系路径和候选确认 |
| `zh-keyword` | `/keywords/zh/{text,texts,file,files}` | 摘要、数量、顺序、可选用户词典 | `keywords`, `statistics` | 词典版本、命中来源、关键词历史 |
| `en-keyword` | `/keywords/en/{text,texts,file,files}` | 英文摘要、规范化、用户词典 | `keywords`, `statistics` | 支持规范词和 XML 导出 |
| `rq-detect` | `/research-question/{text,texts,file,files}` | 文本/文档与识别范围参数 | `research_question_sentences`, `research_question_phrases`, `structured_research_questions`, `statistics` | 可为结构化综述提供研究问题数据 |
| `citation-sentiment` | `/citation/sentiment/{file,files}` | 全文文件、上下文窗口与返回选项 | `citations`, `citation_sentiment_results`, `statistics` | 保存引用、上下文、位置与三类统计 |
| `citation-intent` | `/citation/intent/{file,files}` | 全文文件、训练证据与返回选项 | `citations`, `citation_intent_results`, `statistics` | 保存背景/方法/比较三类结果 |
| `definition-detect` | `/concept-definition/{text,texts,file,files}` | 科技文本/文件、领域和最低置信度 | `definitions`, `statistics` | 概念规范化、定义历史与统计 |
| `general-ner` | `/ner/general/{text,texts,file,files}` | 中英文文本、实体类型 | `entities`, `statistics` | 可作为关系识别的上游实体记录 |
| `research-ner` | `/ner/research/{text,texts,file,files}` | 科研文本、领域、最低置信度 | `entities`, `statistics` | 同上，保存科研实体与本体映射 |
| `domain-ner` | `/ner/domain/{text,texts,file,files}` | 专业文本、领域、最低置信度 | `entities`, `statistics` | 同上，保存专业本体版本 |
| `relation-extract` | `/relation/{text,texts,file,files,from-records}` | 原文，或实体记录 ID + 依存记录 ID | `triples`, `statistics` | `record_dependencies` 保存两条上游血缘；支持 RDF |
| `deep-cluster` | `/cluster/deep/{texts,files,collection}` | 多文献、聚类维度或集合 ID | `clusters`, `dimension`, 原聚类统计 | 下游标签/综述按任务 ID 复用 |
| `cluster-label` | `/cluster-labels/{texts,files,from-cluster-task}` | 多文献或聚类任务 ID、标签长度/语言/差异阈值 | `labels`, `generation_report` | 保存聚类依赖和标签人工确认 |
| `structured-review` | `/review/structured/{texts,files}` 或 `/collections/{id}` | 多文献/集合、可选聚类任务、主题、语言、溯源 | `tree`, `topic`, `traceability` 及原综述字段 | 复用集合和聚类，生成 JSON/CSV/报告 |

## 输入模式与任务策略

| 输入模式 | 请求格式 | 默认策略 |
|---|---|---|
| `text` | JSON | 同步返回，但仍保存任务和结果 |
| `texts` | JSON | Vue 请求后台执行并轮询 |
| `file` / `files` | multipart | 后台执行并轮询；解析文本保存到任务快照供下游复用 |
| `collection` | JSON + `collection_id` | 后台执行，读取数据库真实文献 |
| `cluster_task` / `upstream_records` | JSON + 真实 ID | 校验成功记录并保存结果血缘 |

## 外部后端向本项目提供依存句法结果

```http
POST /api/v1/upstream-records/dependency
Content-Type: application/json

{
  "text": "模型使用知识图谱。",
  "source_system": "dependency-parser",
  "model_version": "parser-1.0",
  "dependencies": [
    { "head": "使用", "dependent": "知识图谱", "relation": "VOB" }
  ]
}
```

响应返回真实 `task_id` 和 `record_id`。实体关系页会通过 `/history/compatible` 自动显示该记录，不需要用户记忆编号。
