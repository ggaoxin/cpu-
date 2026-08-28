# 用户上传资源测试用例手册

> 用途:验证"内置 vs 用户上传"两种资源场景下,各功能点行为是否符合预期。
> 使用方式:按各节步骤操作,对照"预期结果"核对。所有数据可直接复制使用。

---

## 通用操作说明

**上传资源入口**:前端资源选择器切"用户上传资源",或直接调 API:

```bash
curl -X POST http://<host>:8000/api/v1/semantic-resources/upload \
  -F "resource_key=<资源字段名>" \
  -F "upload=@<文件>"
```

返回 `resource_id`,请求功能点时用 `{"source": "database", "resource_id": "<id>"}` 引用。

---

## 用例 1:自定义中图分类体系(自动分类工具)

**目的**:验证用户上传自己的类目体系后,分类结果落到自定义类目(而非内置中图法)。

**测试数据** `custom_taxonomy.json`:

```json
[
  {"clc_code": "A",  "clc_name": "内部管理制度文件"},
  {"clc_code": "A1", "clc_name": "行政管理制度"},
  {"clc_code": "A2", "clc_name": "财务与审计制度"},
  {"clc_code": "B",  "clc_name": "科技项目过程材料"},
  {"clc_code": "B1", "clc_name": "项目申报与立项材料"},
  {"clc_code": "B2", "clc_name": "项目结题与验收材料"},
  {"clc_code": "C",  "clc_name": "科研数据与技术报告"},
  {"clc_code": "C1", "clc_name": "实验数据与数据集说明"},
  {"clc_code": "C2", "clc_name": "技术调研与综述报告"},
  {"clc_code": "D",  "clc_name": "对外合作与交流材料"}
]
```

> 注:>50 条的完整分类树会自动构建向量索引(推荐 50+ 条以获得检索能力)。
> 生成 50+ 条的方法:按上述结构扩展,保持 `clc_code` 前缀层级(如 B1/B2 属于 B)。

**步骤**:
1. 上传(resource_key=`clc_labeled_data`),等待约 10 秒(异步建索引)
2. 用自定义资源跑分类:
```json
{"text": "本报告总结2024年度专项课题执行情况,完成全部研究内容,通过结题验收。",
 "document_title": "结题报告",
 "clc_labeled_data": {"source": "database", "resource_id": "<上传返回的ID>"}}
```

**预期**:主分类 = `B2 项目结题与验收材料`(自定义体系内);内置对照跑同文本应返回中图法类目(如 G64x)。

---

## 用例 2:自定义中文术语词典(中文关键词识别)

**目的**:验证用户词典中的术语被加权并进入识别结果。

**创建词典**(API):
```json
POST /api/v1/dictionaries
{"name": "动物行为学术语测试词典", "language": "zh",
 "terms": ["领地范围", "猎物密度", "活动模式"], "weight_boost": 0.3}
```

**步骤**:识别时带 `dictionary_id`:
```json
{"text": "本文研究了东北虎的冬季捕食行为与领地范围,通过红外相机跟踪了12只个体两个冬季的活动模式,分析了捕食成功率与猎物密度的关系。",
 "document_title": "东北虎研究", "dictionary_id": "<词典ID>"}
```

**预期**:词典术语(领地范围/活动模式等)出现在关键词结果中;不带词典的对照结果不同。
**注意**:术语必须在原文中**逐字出现**才会命中加权。

---

## 用例 3:自定义分类标准映射表(英文关键词识别)

**目的**:验证用户映射表的显式条目直接决定关键词的中图类目映射。

### 3a. 小表(显式命中,任意规模)

`small_mapping_table.json`:
```json
[
  {"term": "attention mechanism", "clc_code": "TP183", "clc_name": "人工神经网络与计算"},
  {"term": "protein structure prediction", "clc_code": "Q5", "clc_name": "生物化学"}
]
```

**步骤**:上传(resource_key=`classification_standard_mapping_table`)后识别:
```json
{"text": "This paper applies attention mechanism to protein structure prediction.",
 "document_title": "Protein",
 "domain_terminology_library": {"source": "database", "resource_id": "RES-BUNDLED-EN-TERM"},
 "classification_standard_mapping_table": {"source": "database", "resource_id": "<上传ID>"}}
```

**预期**:attention mechanism 的 `classification_mapping.code = TP183`、`mapping_engine = user_resource_direct`(置信度 1.0)。

### 3b. 大表(>50 条,自动建向量索引)

`big_mapping_table.json`(条目格式同上,扩展到 60 条以上):
```json
[
  {"term": "neural network", "clc_code": "TP183", "clc_name": "人工神经网络与计算"},
  {"term": "deep learning", "clc_code": "TP183", "clc_name": "人工神经网络与计算"},
  ... 共 60+ 条 ...
]
```

**预期**:不在显式条目中的关键词,若与某用户术语向量相似度 ≥0.62,映射到该条目的类目(`mapping_engine = user_resource_index`)。

---

## 用例 4:自定义领域分类规则(专业领域分类)

**目的**:验证用户规则的补充指令影响分类判定口径(软约束)。

`custom_domain_rules.json`:
```json
{"principles": "补充强制规则:凡文本提及'神经网络'或'深度学习'的,主分类号必须归入 TP18(人工智能理论),优先级高于任何领域映射。",
 "note": "用户单位领域分类规则 v2"}
```

**步骤**:上传(resource_key=`domain_classification_rules`),选 14 材料领域跑分类:
```json
{"text": "本文提出基于神经网络的电网故障诊断方法,利用深度学习模型识别输变电设备缺陷。",
 "professional_domain": "materials_science",
 "domain_classification_rules": {"source": "database", "resource_id": "<上传ID>"},
 "manually_labeled_training_data": {"source": "database", "resource_id": "RES-BUNDLED-DOMAIN-GOLD"}}
```

**预期**:分类结果分布与内置规则不同(软约束,GLM 权衡采纳);资源内容确认进入提示词。

---

## 用例 5:自定义人工标注训练数据(专业领域分类)

`custom_domain_gold.json`:
```json
[
  {"sample_id": 1, "title": "神经网络电网故障诊断",
   "abstract": "本文提出基于神经网络的电网故障诊断方法。",
   "domain_code": "14", "domain_name": "14 材料科学与材料工程",
   "clc_classification": "TP18", "alignment_check": "算法主导文本归人工智能"},
  {"sample_id": 2, "title": "结构材料疲劳分析",
   "abstract": "分析结构材料疲劳性能的研究。",
   "domain_code": "14", "domain_name": "14 材料科学与材料工程",
   "clc_classification": "TG113", "alignment_check": ""}
]
```

**预期**:请求成功(code=0);样本注入提示词作 few-shot 参考,校准标注风格。

---

## 用例 6:自定义通用 NER 语料(通用命名实体识别)

`custom_ner_corpus.json`:
```json
{
  "entity_types": ["人物", "机构", "数据库"],
  "note": "用户单位实体标注规范:'PEER数据库'整体作为一个数据库实体,不拆分;人物实体须带职称全称",
  "examples": [
    {"text": "李明研究员在国家超级计算中心使用CNKI数据库检索文献。",
     "entities": [
       {"text": "李明研究员", "type": "人物"},
       {"text": "国家超级计算中心", "type": "机构"},
       {"text": "CNKI数据库", "type": "数据库"}
     ]}
  ]
}
```

**步骤**:上传(resource_key=`general_domain_annotated_corpus`)后识别:
```json
{"text": "张伟教授在清华大学使用PEER数据库开展了地震动记录研究。",
 "general_domain_annotated_corpus": {"source": "database", "resource_id": "<上传ID>"}}
```

**预期**:基线输出"张伟";上传后按规范输出"**张伟教授**"(带职称全称)。

---

## 用例 7:自定义本体+领域规则(专业领域 NER)

`custom_ontology.json`:
```json
{
  "entity_types": ["电力设备", "检测指标", "缺陷类型"],
  "note": "用户单位本体:乙炔、氢气等油中溶解气体须识别为'检测指标'类型;变压器/绕组为'电力设备'"
}
```

**步骤**:两个资源都上传(ontology_classification_system + domain_labeled_training_data,可用同一文件),识别:
```json
{"text": "变压器绝缘油色谱分析显示乙炔超标,需结合局部放电检测判断绕组缺陷。",
 "ontology_classification_system": {"source": "database", "resource_id": "<本体ID>"},
 "domain_labeled_training_data": {"source": "database", "resource_id": "<规则ID>"}}
```

**预期**:实体类型变为自定义的"**电力设备/检测指标/缺陷类型**"(基线是内置类型)。

---

## 用例 8:自定义引用意图训练集(引用意图识别)

`custom_intent_rules.json`:
```json
{
  "intent_definitions": "引用意图自定义口径(用户单位规则):凡引用句含'采用/借鉴/沿用'且引用对象是方法,一律判为'方法论引用';含'对比/相比'判为'比较性引用';其余为'背景性引用'。",
  "note": "三类意图名称以本资源为准"
}
```

**步骤**:上传(resource_key=`preprocessed_training_set`),跑引用意图识别(文献文本+参考文献条目)。

**预期**:请求成功;意图标签口径受资源影响(软约束)。

---

## 用例 9:自定义英文术语库(英文关键词识别)

`custom_en_terms.json`:
```json
{
  "domain_terms": [
    {"canonical": "注意力机制", "variants": ["attention mechanism", "attention"]},
    {"canonical": "蛋白质结构预测", "variants": ["protein structure prediction"]},
    {"canonical": "分子性质预测", "variants": ["molecular property prediction"]}
  ],
  "note": "用户单位术语规范:以上英文术语一律输出对应中文规范名"
}
```

**预期**:关键词集合与基线不同(术语库影响候选与排序)。

---

## 用例 10:自定义科研 NER 语料(科研实体识别)

`custom_research_corpus.json`:
```json
{
  "note": "用户单位科研实体规范:模型名须带'模型'后缀;数据集名须带'数据集'后缀",
  "examples": [
    {"text": "使用GPT模型在SQuAD数据集上实验",
     "entities": [
       {"text": "GPT模型", "type": "MODEL"},
       {"text": "SQuAD数据集", "type": "DATASET"}
     ]}
  ]
}
```

上传到 `multi_domain_scientific_corpus` 和 `manually_labeled_data` 两个字段。

**预期**:请求成功;实体抽取行为受规范影响(如"BERT模型"带后缀输出)。

---

## 验证结论速查表

| 用例 | 资源 | 影响类型 | 验证要点 |
|---|---|---|---|
| 1 | 中图分类数据 | **确定性**(索引替换) | 分类号落在自定义体系 |
| 2 | 中文术语词典 | **确定性**(加权) | 词典术语进入结果 |
| 3a | 映射表(显式) | **确定性**(直接覆盖) | mapping_engine=user_resource_direct |
| 3b | 映射表(大表) | **确定性**(向量索引) | mapping_engine=user_resource_index |
| 4 | 领域分类规则 | 软约束(提示词) | 分类分布变化 |
| 5 | 领域标注数据 | 辅助(few-shot) | 请求成功,风格校准 |
| 6 | 通用 NER 语料 | **行为影响** | 实体抽取按新规范 |
| 7 | 领域 NER 本体 | **行为影响** | 实体类型用自定义体系 |
| 8 | 引用意图训练集 | 软约束 | 意图口径受资源影响 |
| 9 | 英文术语库 | 行为影响 | 关键词集合变化 |
| 10 | 科研 NER 语料 | 行为影响 | 实体格式按规范 |
