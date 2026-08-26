# 结构化自动综述第一阶段实现说明

## 1. 实现范围

第一阶段实现以下真实业务链路：

1. 从每篇文献的 `text` 抽取研究问题和研究方法；
2. 验证模型返回的证据片段能够逐字定位到原文；
3. 使用 BGE-M3 对“研究问题 + 原文证据”进行语义表示；
4. 自动确定研究问题类簇数量并执行层次聚类；
5. 归纳类簇名称和类簇摘要；
6. 生成结构化文本综述，并为章节绑定证据编号；
7. 将结果和证据关系持久化到任务、综述节点及证据表。

研究进展、时间趋势和热点分布不属于第一阶段验收内容。接口保留
`trend_hotspot_distribution`，当前固定返回 `{ "time_range": null, "hotspots": [] }`，
不使用原型演示数据填充。

## 2. 输入合同

```json
{
  "input_type": "texts",
  "document_set": [
    {"document_id": "DOC001", "text": "文献或科技报告文本，最多8000字"},
    {"document_id": "DOC002", "text": "另一篇文献文本"},
    {"document_id": "DOC003", "text": "第三篇文献文本"}
  ],
  "topic_or_keywords": "研究主题；关键词1、关键词2",
  "document_metadata": [
    {
      "document_id": "DOC001",
      "title": "可选题名",
      "authors": [],
      "institutions": [],
      "publication_date": null,
      "source": "",
      "keywords": []
    }
  ]
}
```

批量文件接口：`POST /api/v1/review/structured/files`。

数据库文献集接口：`POST /api/v1/review/structured/collections`，请求体提交
`collection_id`、`topic_or_keywords`；系统从数据库读取文献 `text` 和元数据。

不再接收 `cluster_task_id`、`cluster_dimension`、`language` 或
`enable_traceability`。溯源是强制业务能力，不由用户关闭。

## 3. 四项业务输出

```json
{
  "tree": [],
  "cluster_induction_results": {},
  "structured_report": {},
  "trend_hotspot_distribution": {"time_range": null, "hotspots": []}
}
```

`tree` 与 `structured_report` 内部携带 `evidence_ids`；响应同时提供
`evidence_index` 作为证据定位索引，包含文献编号、题名、原文片段和字符偏移。

## 4. 失败与降级原则

- GLM可用：执行有证据约束的研究问题/方法抽取、类簇归纳和报告写作。
- GLM不可用：从原文线索句抽取，输出仍可溯源，但不冒充大模型结果。
- BGE-M3可用：使用BGE-M3语义向量聚类。
- BGE-M3不可用：使用字符级TF-IDF表示，并在诊断字段中标记
  `tfidf-fallback`。
- 模型给出的证据无法在原文定位：直接丢弃该候选，不写入结果。

