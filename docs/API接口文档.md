# 语义计算工具库 API 接口文档

> 版本：2026-10-27 · 覆盖 19 个功能点、67 组"功能点 × 输入方式"接口
> 本文档全部请求示例与响应示例均来自对运行中服务的**真实调用验证**（81 次实测，字段与真实响应逐一对齐）。

## 1. 通用约定

### 1.1 服务地址

| 环境 | Base URL |
|---|---|
| 本机部署 | `http://localhost:8000` |
| 服务器部署 | `http://<服务器IP>:8000` |

### 1.2 鉴权

默认关闭。服务端开启 `API_AUTH_ENABLED` 后，所有请求需携带请求头：

```
X-API-Key: <你的API密钥>
```

### 1.3 统一响应信封

所有接口返回 JSON，顶层结构统一为：

| 字段 | 类型 | 说明 |
|---|---|---|
| code | integer | 0=成功；非 0 见错误码表 |
| message | string | 状态说明；失败时为可直接展示的原因 |
| data | object | 业务数据（结构随功能点而异） |

### 1.4 批量接口响应信封

批量文本/批量文件接口的 `data` 为批次信封：

| 字段 | 类型 | 说明 |
|---|---|---|
| batch_id | string | 批次号 |
| input_type | string | texts / files |
| total | integer | 总篇数 |
| success_count | integer | 成功篇数 |
| failed_count | integer | 失败篇数 |
| error_summary | string\|null | 失败原因汇总（全成功为 null） |
| results | array | 逐篇结果：`{index, status(succeeded/failed), code, record_id, result}`，失败项带 `error` 字段 |

### 1.5 错误码

| code | 含义 | 常见触发 |
|---|---|---|
| 0 | 成功 | — |
| 42201 | 输入不满足业务校验 | 语言不匹配（中文功能点收到英文文本/文件）；deep-cluster 少于 4 篇；citation 卡片字段缺失 |
| 50001 | 处理失败 | 大模型输出解析失败；fund-move 收到非基金文档；文件解析失败 |
| HTTP 422 | 参数校验失败 | 缺必填字段、类型错误（FastAPI 校验层） |
| HTTP 401 | 鉴权失败 | 开启鉴权后未带/带错 X-API-Key |

### 1.6 输入方式与请求构造

| 输入方式 | Content-Type | 主字段形态 |
|---|---|---|
| 单文本 | application/json | 业务字段为 string |
| 批量文本 | application/json | 业务字段为对象数组（每篇含 id/title/text） |
| 单文件 | multipart/form-data | 业务字段承载文件（字段名见各接口参数表） |
| 批量文件 | multipart/form-data | 业务字段承载多个同名文件部件；其余对象/数组字段以 JSON 字符串提交 |

> 文件模式下其余对象/数组参数以 `JSON 字符串` 作为表单值提交（`-F 'key={"…"}'`），标量直接传值。

## 2. 功能点索引

| # | 功能点 | 工具ID | 输入方式 |
|---|---|---|---|
| 1 | [中文摘要语步识别](#1-zh-abstract-move) | zh-abstract-move | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 2 | [英文摘要语步识别](#2-en-abstract-move) | en-abstract-move | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 3 | [中文基金项目语步识别](#3-fund-move) | fund-move | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 4 | [中文科技文献分类](#4-zh-classify) | zh-classify | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 5 | [英文科技文献分类](#5-en-classify) | en-classify | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 6 | [专业领域科技文献分类](#6-domain-classify) | domain-classify | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 7 | [中文科技文献关键词识别](#7-zh-keyword) | zh-keyword | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 8 | [英文科技文献关键词识别](#8-en-keyword) | en-keyword | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 9 | [研究问题识别工具](#9-rq-detect) | rq-detect | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 10 | [引用情感识别](#10-citation-sentiment) | citation-sentiment | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 11 | [引用意图识别](#11-citation-intent) | citation-intent | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 12 | [概念定义句识别工具](#12-definition-detect) | definition-detect | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 13 | [中英文通用领域命名实体识别](#13-general-ner) | general-ner | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 14 | [中英文通用科研实体识别](#14-research-ner) | research-ner | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 15 | [专业领域科研实体识别](#15-domain-ner) | domain-ner | 单文本 / 批量文本 / 单文件 / 批量文件 |
| 16 | [实体关系识别](#16-relation-extract) | relation-extract | 历史识别记录 |
| 17 | [深度聚类工具](#17-deep-cluster) | deep-cluster | 批量文本 / 批量文件 |
| 18 | [聚类标签生成工具](#18-cluster-label) | cluster-label | 批量文本 |
| 19 | [结构化自动综述工具](#19-structured-review) | structured-review | 批量文本 / 批量文件 / 已有文献集合 |

---

## 1. 中文摘要语步识别

**工具ID**：`zh-abstract-move`

自动识别中文科技文献摘要中的研究背景、研究目的、研究方法、研究结果和研究结论，支持单文本、批量文本、单文件和批量文件四种调用方式。

**功能特点**：摘要五类语步识别，批量文本与文件，置信度输出

**适用场景**：中文摘要解析与批量处理

### 1.1 单文本

- **接口**：`POST /api/v1/move/abstract/zh/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,用于响应结果标识与可视化弹窗展示 |
| `chinese_scientific_abstract` | string | 必填 | 中文科技文献摘要 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/move/abstract/zh/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "科技文献题目",
  "chinese_scientific_abstract": "高校体育场馆管理正由经验管理向数据驱动的智慧治理转变，但仍面临数据孤岛与决策滞后等现实困境。本研究探究大数据赋能高校体育场馆智慧化建设的作用机理、现实困境与实现路径。采用文献资料法和逻辑分析法，围绕数据治理与运营协同开展归纳分析。研究发现，数据要素汇聚能够重塑管理决策并优化资源配置，但数据治理体系与协同机制仍不完善。由此提出应构建数据治理体系并创新运营管理机制，以促进高校体育场馆可持续发展。"
}
```

#### 响应字段（data）

```
- data: object
  - sentence_count: number，示例 5
  - document_title: string，示例 "科技文献题目"
  - document: object
    - title: string，示例 "科技文献题目"
    - language: string，示例 "zh"
    - abstract: string，示例 "高校体育场馆管理正由经验管理向数据驱动的智慧治理转变，但仍面临数据孤岛与决策滞后…"
  - moves: array<object>（5 项）
    - []: object
      - label: string，示例 "研究背景"
      - text: string，示例 "高校体育场馆管理正由经验管理向数据驱动的智慧治理转变，但仍面临数据孤岛与决策滞后…"
      - start: number，示例 0
      - end: number，示例 46
      - confidence: number，示例 0.93
      - sentence_indices: array<number>
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "sentence_count": 5,
    "document_title": "科技文献题目",
    "document": {
      "title": "科技文献题目",
      "language": "zh",
      "abstract": "高校体育场馆管理正由经验管理向数据驱动的智慧治理转变，但仍面临数据孤岛与决策滞后等现实困境。本研究探究大数据赋能高校体育场馆智慧化建设的作用机理、现实困境与实现路径。采用文献资料法和逻辑分析法，围绕数据治理与运营协同开展归纳分析。研究发现，数据要素汇聚能够重塑管理决策并优化资源配置，但数据治理体系与协同机制仍不完善。由…"
    },
    "moves": [
      {
        "label": "研究背景",
        "text": "高校体育场馆管理正由经验管理向数据驱动的智慧治理转变，但仍面临数据孤岛与决策滞后等现实困境。",
        "start": 0,
        "end": 46,
        "confidence": 0.93,
        "sentence_indices": [
          0
        ]
      },
      {
        "label": "研究目的",
        "text": "本研究探究大数据赋能高校体育场馆智慧化建设的作用机理、现实困境与实现路径。",
        "start": 46,
        "end": 83,
        "confidence": 0.92,
        "sentence_indices": [
          1
        ]
      },
      "…（共 5 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_e045803dc0e54309b28438dcd231310a",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 3658,
    "created_at": "2026-10-28T00:46:52.358727+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_926f5b43b40b467489a35a4da11a37eb",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_42d4731c6a97418f9b53c635ccf7d5a9",
    "file_name": null
  }
}
```

### 1.2 批量文本

- **接口**：`POST /api/v1/move/abstract/zh/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,用于响应结果标识与可视化弹窗展示 |
| `chinese_scientific_abstract` | object[] | 必填 | 中文科技文献摘要 |
| `chinese_scientific_abstract[].id` | string | 选填 | 批量文本条目编号 |
| `chinese_scientific_abstract[].title` | string | 选填 | 文献题名 |
| `chinese_scientific_abstract[].text` | string | 必填 | 用户输入的文本内容 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/move/abstract/zh/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "地震动记录选取的新视角：大数据与机器学习",
    "糖尿病肾病关键基因识别与潜在靶点分析",
    "融合多尺度特征的工业表面微小缺陷检测"
  ],
  "chinese_scientific_abstract": [
    {
      "id": "DEMO_1",
      "title": "地震动记录选取的新视角：大数据与机器学习",
      "text": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取的一致性，并为工程结构时程分析提供更可靠的输入。"
    },
    {
      "id": "DEMO_2",
      "title": "糖尿病肾病关键基因识别与潜在靶点分析",
      "text": "糖尿病肾病是糖尿病常见的微血管并发症。研究从 GEO 数据库获取相关转录组数据，利用加权基因共表达网络分析识别关键模块，并整合多种机器学习方法筛选特征基因。随后通过通路富集、免疫微环境关联和分子对接分析验证候选基因的诊断及治疗价值。结果表明，VWF 等基因具有较高的识别能力和潜在靶向价值，可为糖尿病肾病的精准诊疗提供参考。"
    },
    {
      "id": "DEMO_3",
      "title": "融合多尺度特征的工业表面微小缺陷检测",
      "text": "复杂工业表面中的裂纹、划痕和孔洞通常具有尺度差异大、边缘模糊及背景纹理干扰强等特点。本文提出融合多尺度特征增强和局部注意力的微小缺陷检测方法，通过跨层特征融合改善缺陷区域表征。多个公开数据集上的实验结果表明，该方法能够提高检测准确率与召回率，同时保持较低的推理延迟，适用于智能制造在线质量检测。"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_d49942d936cd450992703d40d4ccf7b2"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_ce58f04dfe7e4ce0af9e68ebda36e8fc"
      - result: object
        - sentence_count: number，示例 4
        - document_title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
        - document: object
          - title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
          - language: string，示例 "zh"
          - abstract: string，示例 "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别…"
        - moves: array<object>（5 项）
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_d49942d936cd450992703d40d4ccf7b2",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_ce58f04dfe7e4ce0af9e68ebda36e8fc",
        "result": {
          "sentence_count": 4,
          "document_title": "地震动记录选取的新视角：大数据与机器学习",
          "document": {
            "title": "地震动记录选取的新视角：大数据与机器学习",
            "language": "zh",
            "abstract": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取…"
          },
          "moves": [
            {
              "label": "研究背景",
              "text": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。",
              "start": 0,
              "end": 63,
              "confidence": 0.9,
              "sentence_indices": [
                0,
                1
              ]
            },
            {
              "label": "研究目的",
              "text": "本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。",
              "start": 63,
              "end": 142,
              "confidence": 0.65,
              "sentence_indices": [
                2
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_83686bc51cf743e69eb669569d78f111",
        "result": {
          "sentence_count": 4,
          "document_title": "糖尿病肾病关键基因识别与潜在靶点分析",
          "document": {
            "title": "糖尿病肾病关键基因识别与潜在靶点分析",
            "language": "zh",
            "abstract": "糖尿病肾病是糖尿病常见的微血管并发症。研究从 GEO 数据库获取相关转录组数据，利用加权基因共表达网络分析识别关键模块，并整合多种机器学习方法筛选特征基因。随后通过通路富集、免疫微环境关联和分子对接分析验证候选基因的诊断及治疗价值。结果表明，VWF 等基因具有较高的识别能力和潜在靶向价值，可为糖尿病肾病的精准诊疗提供参…"
          },
          "moves": [
            {
              "label": "研究背景",
              "text": "糖尿病肾病是糖尿病常见的微血管并发症。",
              "start": 0,
              "end": 19,
              "confidence": 0.9,
              "sentence_indices": [
                0
              ]
            },
            {
              "label": "研究目的",
              "text": "",
              "start": null,
              "end": null,
              "confidence": 0.6
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_07041c16569f432a913cdd4c09cebd9a",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 4158,
    "created_at": "2026-10-28T00:46:56.549581+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_d49942d936cd450992703d40d4ccf7b2",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 1.3 单文件

- **接口**：`POST /api/v1/move/abstract/zh/file`
- **Content-Type**：multipart/form-data

> 上传中文文献 PDF/DOCX/TXT（英文文献会被 42201 语言门拒绝）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chinese_scientific_abstract` | file | 必填 | 中文科技文献文件（上传 PDF/DOCX/TXT） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/move/abstract/zh/file' \
  -F 'chinese_scientific_abstract=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - sentence_count: number，示例 4
  - document_title: string，示例 "融合大数据分析与机器学习的光伏电站运维管理系统设计"
  - document: object
    - title: string，示例 "融合大数据分析与机器学习的光伏电站运维管理系统设计"
    - language: string，示例 "zh"
    - abstract: string，示例 "针对光伏电站运维管理面临的数据复杂性和决策智能化不足等挑战，本文设计了一套融合大…"
  - moves: array<object>（5 项）
    - []: object
      - label: string，示例 "研究背景"
      - text: string，示例 ""
      - start: null（本示例中为空）
      - end: null（本示例中为空）
      - confidence: number，示例 0.75
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "sentence_count": 4,
    "document_title": "融合大数据分析与机器学习的光伏电站运维管理系统设计",
    "document": {
      "title": "融合大数据分析与机器学习的光伏电站运维管理系统设计",
      "language": "zh",
      "abstract": "针对光伏电站运维管理面临的数据复杂性和决策智能化不足等挑战，本文设计了一套融合大数据分析与机器学习的光伏电站运维管理系统。通过深入分析光伏电站运维数据的海量异构、多维关联和时变特征，构建了融合Hadoop生态、机器学习和实时计算技术的四层架构系统。系统采用Kafka+Storm流处理架构实现实时数据采集与处理，结合支持…"
    },
    "moves": [
      {
        "label": "研究背景",
        "text": "",
        "start": null,
        "end": null,
        "confidence": 0.75
      },
      {
        "label": "研究目的",
        "text": "针对光伏电站运维管理面临的数据复杂性和决策智能化不足等挑战，本文设计了一套融合大数据分析与机器学习的光伏电站运维管理系统。",
        "start": 0,
        "end": 61,
        "confidence": 0.85,
        "sentence_indices": [
          0
        ]
      },
      "…（共 5 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_7362490cd1c64af69556cdc6e01ae099",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 6829,
    "created_at": "2026-10-27T22:33:45.028756+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_0b6422c10d8a463d9bc421a447177b0f",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_14eeafef883243fa88ded819f626a6b6",
    "file_name": "zh1.pdf"
  }
}
```

### 1.4 批量文件

- **接口**：`POST /api/v1/move/abstract/zh/files`
- **Content-Type**：multipart/form-data

> 上传中文文献 PDF/DOCX/TXT（英文文献会被 42201 语言门拒绝）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chinese_scientific_abstract` | file[] | 必填 | 中文科技文献文件（上传 PDF/DOCX/TXT） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/move/abstract/zh/files' \
  -F 'chinese_scientific_abstract=@paper_01.pdf' \
  -F 'chinese_scientific_abstract=@paper_02.docx' \
  -F 'chinese_scientific_abstract=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_5a43d1f3480f43be9230a8e76d67fbd6"
  - input_type: string，示例 "files"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "zh1.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_3e983dd265494ca581041e00b6ba951f"
      - result: object
        - sentence_count: number，示例 4
        - document_title: string，示例 "融合大数据分析与机器学习的光伏电站运维管理系统设计"
        - document: object
          - title: string，示例 "融合大数据分析与机器学习的光伏电站运维管理系统设计"
          - language: string，示例 "zh"
          - abstract: string，示例 "针对光伏电站运维管理面临的数据复杂性和决策智能化不足等挑战，本文设计了一套融合大…"
        - moves: array<object>（5 项）
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_5a43d1f3480f43be9230a8e76d67fbd6",
    "input_type": "files",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "zh1.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_3e983dd265494ca581041e00b6ba951f",
        "result": {
          "sentence_count": 4,
          "document_title": "融合大数据分析与机器学习的光伏电站运维管理系统设计",
          "document": {
            "title": "融合大数据分析与机器学习的光伏电站运维管理系统设计",
            "language": "zh",
            "abstract": "针对光伏电站运维管理面临的数据复杂性和决策智能化不足等挑战，本文设计了一套融合大数据分析与机器学习的光伏电站运维管理系统。通过深入分析光伏电站运维数据的海量异构、多维关联和时变特征，构建了融合Hadoop生态、机器学习和实时计算技术的四层架构系统。系统采用Kafka+Storm流处理架构实现实时数据采集与处理，结合支持…"
          },
          "moves": [
            {
              "label": "研究背景",
              "text": "",
              "start": null,
              "end": null,
              "confidence": 0.85
            },
            {
              "label": "研究目的",
              "text": "针对光伏电站运维管理面临的数据复杂性和决策智能化不足等挑战，本文设计了一套融合大数据分析与机器学习的光伏电站运维管理系统。",
              "start": 0,
              "end": 61,
              "confidence": 0.88,
              "sentence_indices": [
                0
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      },
      {
        "index": 1,
        "file_name": "zh2.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_e32b61351caf4d59898e10a967134fe8",
        "result": {
          "sentence_count": 10,
          "document_title": "地震动记录选取的新视角：大数据与机器学习",
          "document": {
            "title": "地震动记录选取的新视角：大数据与机器学习",
            "language": "zh",
            "abstract": "合理选取地震动记录已成为基于性能抗震设计的关键。由于地震动在时间和空间均具有随机性，为了探索不同地震动记录之间频谱特性的差异，地震动记录分类与选取方法，亟需从经验和物理相结合的传统模式，过渡到依赖大数据和机器学习的智能方法。传统方法只能考虑固定震级和距离分组，需提前根据专家经验给出不同分组之间的界限，不能客观反映地震动…"
          },
          "moves": [
            {
              "label": "研究背景",
              "text": "合理选取地震动记录已成为基于性能抗震设计的关键。由于地震动在时间和空间均具有随机性，为了探索不同地震动记录之间频谱特性的差异，地震动记录分类与选取方法，亟需从经验和物理相结合的传统模式，过渡到依赖大数据和机器学习的智能方法。传统方法只能考虑固定震级和距离分组，需提前根据专家经验给出不同分组之间的界限，不能客观反映地震动…",
              "start": 0,
              "end": 172,
              "confidence": 0.9,
              "sentence_indices": [
                0,
                1,
                "…（共 3 项，示例保留前 2 项）"
              ]
            },
            {
              "label": "研究目的",
              "text": "鉴于此，本文将地震动记录按照震级、距离进行聚类分析，然后基于主成分分析对不同场地类别和聚类分组的地震动记录进行排序，提出了一种聚类与主成分分析相结合的自适应地震动记录选取方法。",
              "start": 172,
              "end": 260,
              "confidence": 0.9,
              "sentence_indices": [
                3
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_b6b583f8c2de431da3f8f60d17196a64",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 9199,
    "created_at": "2026-10-27T22:34:23.014884+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_5a43d1f3480f43be9230a8e76d67fbd6",
    "input_type": "files",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

---

## 2. 英文摘要语步识别

**工具ID**：`en-abstract-move`

自动识别英文科技文献摘要中的 Background、Objective、Method、Result 和 Conclusion，支持单文本、批量文本、单文件和批量文件四种调用方式。

**功能特点**：英文摘要五类语步识别，批量处理，置信度输出

**适用场景**：英文摘要解析与批量处理

### 2.1 单文本

- **接口**：`POST /api/v1/move/abstract/en/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `english_scientific_abstract` | string | 必填 | 英文科技论文摘要(含 SCI/EI 期刊及国际会议论文) |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/move/abstract/en/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "科技文献题目",
  "english_scientific_abstract": "Reinforcement learning can enhance vision-language model reasoning, but the effective mechanisms and limitations of multi-step sampling remain underexplored. This study investigates the behavioral difference between reinforcement-learning models and their base counterparts. Training dynamics and multi-sampling behavior are compared, followed by Multi-Group Policy Optimization. GRPO shows diversity collapse, while MUPO improves reasoning diversity and benchmark performance. Encouraging divergent solution paths improves the balance between accuracy and scalability."
}
```

#### 响应字段（data）

```
- data: object
  - sentence_count: number，示例 5
  - document_title: string，示例 "科技文献题目"
  - document: object
    - title: string，示例 "科技文献题目"
    - language: string，示例 "en"
    - abstract: string，示例 "Reinforcement learning can enhance visio…"
  - moves: array<object>（5 项）
    - []: object
      - label: string，示例 "背景"
      - text: string，示例 "Reinforcement learning can enhance visio…"
      - start: number，示例 0
      - end: number，示例 157
      - confidence: number，示例 0.9
      - sentence_indices: array<number>
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "sentence_count": 5,
    "document_title": "科技文献题目",
    "document": {
      "title": "科技文献题目",
      "language": "en",
      "abstract": "Reinforcement learning can enhance vision-language model reasoning, but the effective mechanisms and limitations of multi-step sampling remain underexplored. Th…"
    },
    "moves": [
      {
        "label": "背景",
        "text": "Reinforcement learning can enhance vision-language model reasoning, but the effective mechanisms and limitations of multi-step sampling remain underexplored.",
        "start": 0,
        "end": 157,
        "confidence": 0.9,
        "sentence_indices": [
          0
        ]
      },
      {
        "label": "目的",
        "text": "This study investigates the behavioral difference between reinforcement-learning models and their base counterparts.",
        "start": 158,
        "end": 274,
        "confidence": 0.88,
        "sentence_indices": [
          1
        ]
      },
      "…（共 5 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_861e3c5dc1784e31ad908a003db03da5",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 4631,
    "created_at": "2026-10-28T00:47:01.419991+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_8d0e7f17cb704256abaecc490bdc3ffe",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_94a26835d9754d62a6731d45123a8646",
    "file_name": null
  }
}
```

### 2.2 批量文本

- **接口**：`POST /api/v1/move/abstract/en/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `english_scientific_abstract` | object[] | 必填 | 英文科技论文摘要(含 SCI/EI 期刊及国际会议论文) |
| `english_scientific_abstract[].id` | string | 选填 | 批量文本条目编号 |
| `english_scientific_abstract[].title` | string | 选填 | 文献题名 |
| `english_scientific_abstract[].text` | string | 必填 | 用户输入的文本内容 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/move/abstract/en/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
    "Timestep-Aware Block Masking for Efficient Diffusion Inference",
    "Adaptive Temporal Graph Learning for Multivariate Anomaly Detection"
  ],
  "english_scientific_abstract": [
    {
      "id": "DEMO_1",
      "title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
      "text": "Reinforcement learning can improve the reasoning performance of vision-language models, but it may also reduce the diversity of their reasoning paths. This study compares reinforcement-learning models with their base counterparts and finds that the former reason more deeply along a narrow set of strategies, while the latter explore broader alternatives. The proposed Multi-Group Policy Optimization method encourages diverse solutions during training. Experiments on established benchmarks show improved reasoning diversity and a better balance between accuracy and scalability."
    },
    {
      "id": "DEMO_2",
      "title": "Timestep-Aware Block Masking for Efficient Diffusion Inference",
      "text": "Diffusion models produce high-quality samples but require repeated denoising and therefore incur substantial inference cost. This study proposes timestep-aware block masking, which learns which network blocks should be executed or reused at each denoising step. Independent optimization and knowledge-guided mask refinement reduce memory consumption while preserving generation quality. Experiments across several diffusion architectures demonstrate consistent acceleration with limited quality loss."
    },
    {
      "id": "DEMO_3",
      "title": "Adaptive Temporal Graph Learning for Multivariate Anomaly Detection",
      "text": "Multivariate time-series anomaly detection is difficult because sensor noise, missing observations and operating-condition shifts can hide weak fault patterns. This study proposes a temporal graph framework that combines adaptive dependency learning, multi-scale temporal encoding and consistency regularization. Experiments on public industrial datasets show lower false-alarm rates and improved detection performance under heterogeneous operating conditions."
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_c48be01ecd394933ad4ecf42baec7414"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_92c679a98b9044f18b8f9a40576bbbfd"
      - result: object
        - sentence_count: number，示例 4
        - document_title: string，示例 "Divergent Thinking Through Reinforcement…"
        - document: object
          - title: string，示例 "Divergent Thinking Through Reinforcement…"
          - language: string，示例 "en"
          - abstract: string，示例 "Reinforcement learning can improve the r…"
        - moves: array<object>（5 项）
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_c48be01ecd394933ad4ecf42baec7414",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_92c679a98b9044f18b8f9a40576bbbfd",
        "result": {
          "sentence_count": 4,
          "document_title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
          "document": {
            "title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
            "language": "en",
            "abstract": "Reinforcement learning can improve the reasoning performance of vision-language models, but it may also reduce the diversity of their reasoning paths. This stud…"
          },
          "moves": [
            {
              "label": "背景",
              "text": "Reinforcement learning can improve the reasoning performance of vision-language models, but it may also reduce the diversity of their reasoning paths.",
              "start": 0,
              "end": 150,
              "confidence": 0.9,
              "sentence_indices": [
                0
              ]
            },
            {
              "label": "目的",
              "text": "The proposed Multi-Group Policy Optimization method encourages diverse solutions during training. Experiments on established benchmarks show improved reasoning …",
              "start": 356,
              "end": 580,
              "confidence": 0.88,
              "sentence_indices": [
                2
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_e2a71569d5224212803687b972a26814",
        "result": {
          "sentence_count": 4,
          "document_title": "Timestep-Aware Block Masking for Efficient Diffusion Inference",
          "document": {
            "title": "Timestep-Aware Block Masking for Efficient Diffusion Inference",
            "language": "en",
            "abstract": "Diffusion models produce high-quality samples but require repeated denoising and therefore incur substantial inference cost. This study proposes timestep-aware …"
          },
          "moves": [
            {
              "label": "背景",
              "text": "Diffusion models produce high-quality samples but require repeated denoising and therefore incur substantial inference cost.",
              "start": 0,
              "end": 124,
              "confidence": 0.9,
              "sentence_indices": [
                0
              ]
            },
            {
              "label": "目的",
              "text": "This study proposes timestep-aware block masking, which learns which network blocks should be executed or reused at each denoising step.",
              "start": 125,
              "end": 261,
              "confidence": 0.96,
              "sentence_indices": [
                1
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_517e53126560421788a1988b91630457",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 6622,
    "created_at": "2026-10-28T00:47:08.074505+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_c48be01ecd394933ad4ecf42baec7414",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 2.3 单文件

- **接口**：`POST /api/v1/move/abstract/en/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `english_scientific_abstract` | file | 必填 | 英文科技论文(含 SCI/EI 期刊及国际会议论文)文件（上传 PDF/DOCX/TXT） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/move/abstract/en/file' \
  -F 'english_scientific_abstract=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - sentence_count: number，示例 9
  - document_title: string，示例 "Learning from Synthetic Data: Limitation…"
  - document: object
    - title: string，示例 "Learning from Synthetic Data: Limitation…"
    - language: string，示例 "en"
    - abstract: string，示例 "The prevalence and low cost of LLMs have…"
  - moves: array<object>（5 项）
    - []: object
      - label: string，示例 "背景"
      - text: string，示例 "The prevalence and low cost of LLMs have…"
      - start: number，示例 0
      - end: number，示例 237
      - confidence: number，示例 0.95
      - sentence_indices: array<number>（2 项）
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "sentence_count": 9,
    "document_title": "Learning from Synthetic Data: Limitations of ERM",
    "document": {
      "title": "Learning from Synthetic Data: Limitations of ERM",
      "language": "en",
      "abstract": "The prevalence and low cost of LLMs have led to a rise of synthetic content. From review sites to court documents, \"natural\" content has been contaminated by da…"
    },
    "moves": [
      {
        "label": "背景",
        "text": "The prevalence and low cost of LLMs have led to a rise of synthetic content. From review sites to court documents, \"natural\" content has been contaminated by da…",
        "start": 0,
        "end": 237,
        "confidence": 0.95,
        "sentence_indices": [
          0,
          1
        ]
      },
      {
        "label": "目的",
        "text": "In this work we revisit fundamental learning theory questions in this, now ubiquitous, setting.",
        "start": 238,
        "end": 333,
        "confidence": 0.8,
        "sentence_indices": [
          2,
          4
        ]
      },
      "…（共 5 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_3ff03b166a744136a99bd1fca39ae2da",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 16915,
    "created_at": "2026-10-27T22:18:38.705635+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_3a097e05443f484a8b0d921d397b5731",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_8486dac83cb34547b79718ad06c4a5df",
    "file_name": "7.pdf"
  }
}
```

### 2.4 批量文件

- **接口**：`POST /api/v1/move/abstract/en/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `english_scientific_abstract` | file[] | 必填 | 英文科技论文(含 SCI/EI 期刊及国际会议论文)文件（上传 PDF/DOCX/TXT） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/move/abstract/en/files' \
  -F 'english_scientific_abstract=@paper_01.pdf' \
  -F 'english_scientific_abstract=@paper_02.docx' \
  -F 'english_scientific_abstract=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_d1c5738375d544f58b36801cb3fb541c"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_7b7a97a50ad64f2e8618bbe7a724f923"
      - result: object
        - sentence_count: number，示例 9
        - document_title: string，示例 "Learning from Synthetic Data: Limitation…"
        - document: object
          - title: string，示例 "Learning from Synthetic Data: Limitation…"
          - language: string，示例 "en"
          - abstract: string，示例 "The prevalence and low cost of LLMs have…"
        - moves: array<object>（5 项）
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_d1c5738375d544f58b36801cb3fb541c",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_7b7a97a50ad64f2e8618bbe7a724f923",
        "result": {
          "sentence_count": 9,
          "document_title": "Learning from Synthetic Data: Limitations of ERM",
          "document": {
            "title": "Learning from Synthetic Data: Limitations of ERM",
            "language": "en",
            "abstract": "The prevalence and low cost of LLMs have led to a rise of synthetic content. From review sites to court documents, \"natural\" content has been contaminated by da…"
          },
          "moves": [
            {
              "label": "背景",
              "text": "The prevalence and low cost of LLMs have led to a rise of synthetic content. From review sites to court documents, \"natural\" content has been contaminated by da…",
              "start": 0,
              "end": 237,
              "confidence": 0.9,
              "sentence_indices": [
                0,
                1
              ]
            },
            {
              "label": "目的",
              "text": "In this work we revisit fundamental learning theory questions in this, now ubiquitous, setting.",
              "start": 238,
              "end": 333,
              "confidence": 0.88,
              "sentence_indices": [
                2
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_88c774864ccf498a94b602dca5069d82",
        "result": {
          "sentence_count": 9,
          "document_title": "Learning from Synthetic Data: Limitations of ERM",
          "document": {
            "title": "Learning from Synthetic Data: Limitations of ERM",
            "language": "en",
            "abstract": "The prevalence and low cost of LLMs have led to a rise of synthetic content. From review sites to court documents, \"natural\" content has been contaminated by da…"
          },
          "moves": [
            {
              "label": "背景",
              "text": "The prevalence and low cost of LLMs have led to a rise of synthetic content. From review sites to court documents, \"natural\" content has been contaminated by da…",
              "start": 0,
              "end": 237,
              "confidence": 0.92,
              "sentence_indices": [
                0,
                1
              ]
            },
            {
              "label": "目的",
              "text": "In this work we revisit fundamental learning theory questions in this, now ubiquitous, setting.",
              "start": 238,
              "end": 333,
              "confidence": 0.9,
              "sentence_indices": [
                2
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_1e621d98e35844ee9dd86368223ca042",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 7137,
    "created_at": "2026-10-27T22:19:07.201436+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_d1c5738375d544f58b36801cb3fb541c",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 3. 中文基金项目语步识别

**工具ID**：`fund-move`

识别基金申请书、立项书或科研项目管理文件中的立项依据、研究目标、技术实施方案、预期成果和应用价值，支持单文本、批量文本、单文件和批量文件。

**功能特点**：基金语步分类，章节溯源，文本文件批处理

**适用场景**：基金申请书与结题材料解析

### 3.1 单文本

- **接口**：`POST /api/v1/move/fund/zh/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_name` | string | 必填 | 项目名称,用于响应结果标识 |
| `project_document_text` | string | 必填 | 中文基金申请书/立项书/科研项目管理文件 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/move/fund/zh/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "project_name": "面向低资源场景的跨模态知识图谱构建关键技术",
  "project_document_text": "一、立项依据\n知识图谱构建在低资源场景面临语料稀缺与模态对齐困难的双重挑战，现有方法依赖大规模标注数据，难以迁移到垂直领域，亟需面向低资源场景的新方法。\n二、研究目标与研究内容\n本项目研究跨模态语义对齐与远程监督相结合的知识图谱构建方法，研究内容包括实体识别、关系抽取与跨模态对齐三个部分，技术路线为预训练模型微调结合弱监督学习。\n三、预期成果与考核指标\n预期成果为形成发明专利三项、学术论文五篇及原型系统一套，考核指标为实体对齐准确率不低于百分之八十五。"
}
```

#### 响应字段（data）

```
- data: object
  - moves: array<object>（5 项）
    - []: object
      - source_sections: array<string>
      - confidence: number，示例 1
      - start: number，示例 7
      - end: number，示例 76
      - label: string，示例 "立项依据"
      - text: string，示例 "知识图谱构建在低资源场景面临语料稀缺与模态对齐困难的双重挑战，现有方法依赖大规模…"
  - document: object
    - title: string，示例 "一、立项依据"
    - language: string，示例 "zh"
    - abstract: string，示例 "一、立项依据\n知识图谱构建在低资源场景面临语料稀缺与模态对齐困难的双重挑战，现有…"
  - document_title: string，示例 "面向低资源场景的跨模态知识图谱构建关键技术"
  - input_type: string，示例 "text"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "moves": [
      {
        "source_sections": [
          "一、立项依据"
        ],
        "confidence": 1,
        "start": 7,
        "end": 76,
        "label": "立项依据",
        "text": "知识图谱构建在低资源场景面临语料稀缺与模态对齐困难的双重挑战，现有方法依赖大规模标注数据，难以迁移到垂直领域，亟需面向低资源场景的新方法。"
      },
      {
        "source_sections": [
          "二、研究目标与研究内容"
        ],
        "confidence": 1,
        "start": 89,
        "end": 119,
        "label": "研究目标",
        "text": "本项目研究跨模态语义对齐与远程监督相结合的知识图谱构建方法，实现低资源场景下的知识图谱构建。"
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "document": {
      "title": "一、立项依据",
      "language": "zh",
      "abstract": "一、立项依据\n知识图谱构建在低资源场景面临语料稀缺与模态对齐困难的双重挑战，现有方法依赖大规模标注数据，难以迁移到垂直领域，亟需面向低资源场景的新方法。\n二、研究目标与研究内容\n本项目研究跨模态语义对齐与远程监督相结合的知识图谱构建方法，研究内容包括实体识别、关系抽取与跨模态对齐三个部分，技术路线为预训练模型微调结合弱…"
    },
    "document_title": "面向低资源场景的跨模态知识图谱构建关键技术",
    "input_type": "text"
  },
  "meta": {
    "request_id": "req_43e9f4b8b9484ce5bd2c3170aa8688bc",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 9156,
    "created_at": "2026-10-27T22:02:14.125188+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_f9416806275e4cf4875058ee6dff7b9a",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_385b785b2b084c129923704cd2e7be68",
    "file_name": null
  }
}
```

### 3.2 批量文本

- **接口**：`POST /api/v1/move/fund/zh/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_document_text` | object[] | 必填 | 中文基金申请书/立项书/科研项目管理文件 |
| `project_document_text[].project_name` | string | 条件必填 | 基金项目名称 |
| `project_document_text[].text` | string | 必填 | 用户输入的文本内容 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/move/fund/zh/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "project_document_text": [
    {
      "project_name": "TiAl合金中氢原子团簇的第一性原理计算及实验研究",
      "text": "国家自然科学基金项目申请书。项目名称：面向低资源场景的跨模态知识图谱构建关键技术研究。\n（一）立项依据：\n1．研究背景与动机\n多模态数据规模持续增长，跨模态知识图谱构建面临语义歧义与数据稀疏的双重挑战，现有方法难以支撑行业知识服务需求。\n2．研究意义\n本项目成果可服务于智能制造与科技情报分析，为行业知识服务平台落地提供技术支撑，推动知识工程迈向自动构建。\n（二）研究内容：\n3．研究目标\n构建覆盖典型领域的跨模态知识图谱，实体对齐准确率提升15%以上，形成可复用的构建方法体系。\n4．研究方案\n采用预训练语言模型与图神经网络混合架构，分阶段引入领域自适应与提示学习策略。\n6．预期研究成果\n发表高水平论文8篇，申请发明专利3项，形成可部署的开源系统一套。"
    },
    {
      "project_name": "大规模通用隐式非线性有限元分析软件研发",
      "text": "国家自然科学基金项目申请书。项目名称：面向高噪声场景的多模态知识图谱构建关键技术研究。\n（一）立项依据：\n1．研究背景与动机\n多模态数据规模持续增长，多模态知识图谱构建面临语义歧义与数据稀疏的双重挑战，现有方法难以支撑行业知识服务需求。\n2．研究意义\n本项目成果可服务于智能制造与科技情报分析，为行业知识服务平台落地提供技术支撑，推动知识工程迈向自动构建。\n（二）研究内容：\n3．研究目标\n构建覆盖典型领域的多模态知识图谱，实体对齐准确率提升15%以上，形成可复用的构建方法体系。\n4．研究方案\n采用预训练语言模型与图神经网络混合架构，分阶段引入领域自适应与提示学习策略。\n6．预期研究成果\n发表高水平论文8篇，申请发明专利3项，形成可部署的开源系统一套。"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_fc558d847b9f47c8aa2c5a6c4ec573c5"
  - input_type: string，示例 "texts"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_f0ae83ace4074a0ab7ef3b169421692c"
      - result: object
        - moves: array<object>（5 项）
          - []: object
        - document: object
          - title: string，示例 "面向低资源场景的跨模态知识图谱构建关键技术研究"
          - language: string，示例 "zh"
          - abstract: string，示例 "国家自然科学基金项目申请书。项目名称：面向低资源场景的跨模态知识图谱构建关键技术…"
        - input_type: string，示例 "texts"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_fc558d847b9f47c8aa2c5a6c4ec573c5",
    "input_type": "texts",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_f0ae83ace4074a0ab7ef3b169421692c",
        "result": {
          "moves": [
            {
              "source_sections": [
                "1．研究背景与动机"
              ],
              "confidence": 1,
              "start": 63,
              "end": 117,
              "label": "立项依据",
              "text": "多模态数据规模持续增长，跨模态知识图谱构建面临语义歧义与数据稀疏的双重挑战，现有方法难以支撑行业知识服务需求，亟需开展面向低资源场景的跨模态知识图谱构建关键技术研究。"
            },
            {
              "source_sections": [
                "3．研究目标"
              ],
              "confidence": 1,
              "start": 27,
              "end": 240,
              "label": "研究目标",
              "text": "构建覆盖典型领域的跨模态知识图谱，实现实体对齐准确率提升15%以上，形成可复用的跨模态知识图谱构建方法体系。"
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "面向低资源场景的跨模态知识图谱构建关键技术研究",
            "language": "zh",
            "abstract": "国家自然科学基金项目申请书。项目名称：面向低资源场景的跨模态知识图谱构建关键技术研究。\n（一）立项依据：\n1．研究背景与动机\n多模态数据规模持续增长，跨模态知识图谱构建面临语义歧义与数据稀疏的双重挑战，现有方法难以支撑行业知识服务需求。\n2．研究意义\n本项目成果可服务于智能制造与科技情报分析，为行业知识服务平台落地提供…"
          },
          "input_type": "texts"
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_7ea7c697ba1c49f8bfd19aa997ab0ef5",
        "result": {
          "moves": [
            {
              "source_sections": [
                "1．研究背景与动机"
              ],
              "confidence": 1,
              "start": 63,
              "end": 118,
              "label": "立项依据",
              "text": "多模态数据规模持续增长，多模态知识图谱构建面临语义歧义与数据稀疏的双重挑战，现有方法难以支撑行业知识服务需求。"
            },
            {
              "source_sections": [
                "3．研究目标"
              ],
              "confidence": 1,
              "start": 195,
              "end": 240,
              "label": "研究目标",
              "text": "构建覆盖典型领域的多模态知识图谱，实体对齐准确率提升15%以上，形成可复用的构建方法体系。"
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "面向高噪声场景的多模态知识图谱构建关键技术研究",
            "language": "zh",
            "abstract": "国家自然科学基金项目申请书。项目名称：面向高噪声场景的多模态知识图谱构建关键技术研究。\n（一）立项依据：\n1．研究背景与动机\n多模态数据规模持续增长，多模态知识图谱构建面临语义歧义与数据稀疏的双重挑战，现有方法难以支撑行业知识服务需求。\n2．研究意义\n本项目成果可服务于智能制造与科技情报分析，为行业知识服务平台落地提供…"
          },
          "input_type": "texts"
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_ed9d563b52cf4158b7ff78d60e6fc6d4",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 14812,
    "created_at": "2026-10-27T22:02:28.952932+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_fc558d847b9f47c8aa2c5a6c4ec573c5",
    "input_type": "texts",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

### 3.3 单文件

- **接口**：`POST /api/v1/move/fund/zh/file`
- **Content-Type**：multipart/form-data

> 必须上传基金项目文档（申请书/进展报告/结题报告；普通论文会被 50001 拒收"未检出基金文档特征"）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_document_text` | file | 必填 | 中文基金申请书/立项书/科研项目管理文件（上传 PDF/DOCX/TXT） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/move/fund/zh/file' \
  -F 'project_document_text=@fund_project.pdf'
```

#### 响应字段（data）

```
- data: object
  - moves: array<object>（5 项）
    - []: object
      - source_sections: array<string>
      - confidence: number，示例 0.85
      - start: number，示例 2068
      - end: number，示例 5330
      - label: string，示例 "立项依据"
      - text: string，示例 "TiAl合金作为一种轻质高强结构材料，在汽车及航空航天等领域具有广阔的应用前景。…"
  - document: object
    - title: string，示例 "TiA1合金中氢原子团簇的第一性原理计算及实验研究"
    - language: string，示例 "zh"
    - abstract: string，示例 "## TiAI合金中氢原子团簇的第一性原理计算及实验研究\n\n![](images…"
  - document_title: string，示例 "project1.pdf"
  - input_type: string，示例 "file"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "moves": [
      {
        "source_sections": [
          "中文摘要（对项目的背景、主要研究内容、重要结果、关键数据及其科学意义等做简单概述）"
        ],
        "confidence": 0.85,
        "start": 2068,
        "end": 5330,
        "label": "立项依据",
        "text": "TiAl合金作为一种轻质高强结构材料，在汽车及航空航天等领域具有广阔的应用前景。尽管已有大量研究针对其本征低温脆性问题进行了深入探讨，但对于制造和使用过程中可能面临的氢脆问题，仍缺乏系统性研究，这成为亟待解决的关键科学问题之一。"
      },
      {
        "source_sections": [
          "1. 研究计划执行情况概述。 / （2）研究目标完成情况。"
        ],
        "confidence": 0.85,
        "start": 5793,
        "end": 6005,
        "label": "研究目标",
        "text": "利用第一性原理计算对氢原子在α2相、γ相及α2/γ界面的固溶行为开展研究，系统分析不同缺陷、缺陷簇及合金元素对氢原子固溶行为的影响，明确氢原子在钛铝合金α2相、γ相及α2/γ界面的占位及团簇聚集行为特点，提出适于金属间化合物的缺陷、元素对氢原子固溶行为影响的机制。项目按计划完成了申请书中的研究目标。"
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "document": {
      "title": "TiA1合金中氢原子团簇的第一性原理计算及实验研究",
      "language": "zh",
      "abstract": "## TiAI合金中氢原子团簇的第一性原理计算及实验研究\n\n![](images/8907e4aa6119db84b359f3dda141fd25d96bed3f0248dc1179643fd42963551b.jpg)\n\n项目批准号 52101024  \n申请代码 E0101  \n归口管理部门  \n收件日期\n\n![]…"
    },
    "document_title": "project1.pdf",
    "input_type": "file"
  },
  "meta": {
    "request_id": "req_ee4f5eca170640a5bcd64b175682f7ef",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 92997,
    "created_at": "2026-10-27T22:41:15.345099+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_6d9fefd68ad44d70b78a6edb85556440",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_8e9e04592ba44bd58fd510a65f149310",
    "file_name": "project1.pdf"
  }
}
```

### 3.4 批量文件

- **接口**：`POST /api/v1/move/fund/zh/files`
- **Content-Type**：multipart/form-data

> 必须上传基金项目文档（申请书/进展报告/结题报告；普通论文会被 50001 拒收"未检出基金文档特征"）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `project_document_text` | file[] | 必填 | 中文基金申请书/立项书/科研项目管理文件（上传 PDF/DOCX/TXT） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/move/fund/zh/files' \
  -F 'project_document_text=@fund_project_01.pdf' \
  -F 'project_document_text=@fund_project_02.docx'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_e7111c35b7704133bf8280c40df6e69f"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "project1.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_95fe1222a0bc416685f24a701f16a7de"
      - result: object
        - moves: array<object>（5 项）
          - []: object
        - document: object
          - title: string，示例 "TiA1合金中氢原子团簇的第一性原理计算及实验研究"
          - language: string，示例 "zh"
          - abstract: string，示例 "## TiAI合金中氢原子团簇的第一性原理计算及实验研究\n\n![](images…"
        - document_title: string，示例 "project1.pdf"
        - input_type: string，示例 "files"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_e7111c35b7704133bf8280c40df6e69f",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "project1.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_95fe1222a0bc416685f24a701f16a7de",
        "result": {
          "moves": [
            {
              "source_sections": [
                "中文摘要（对项目的背景、主要研究内容、重要结果、关键数据及其科学意义等做简单概述）"
              ],
              "confidence": 0.9,
              "start": 2068,
              "end": 5330,
              "label": "立项依据",
              "text": "TiAl合金作为一种轻质高强结构材料，在汽车及航空航天等领域具有广阔的应用前景。尽管已有大量研究针对其本征低温脆性问题进行了深入探讨，但对于制造和使用过程中可能面临的氢脆问题，仍缺乏系统性研究，这成为亟待解决的关键科学问题之一。"
            },
            {
              "source_sections": [
                "1. 研究计划执行情况概述。 / （2）研究目标完成情况。"
              ],
              "confidence": 0.85,
              "start": 615,
              "end": 6018,
              "label": "研究目标",
              "text": "利用第一性原理计算对氢原子在α2相、γ相及α2/γ界面的固溶行为开展研究，系统分析不同缺陷、缺陷簇及合金元素对氢原子固溶行为的影响，明确氢原子的占位及团簇聚集行为特点，提出适于金属间化合物缺陷、元素对氢原子固溶行为影响的机制，完成了申请书中的研究目标。"
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "TiA1合金中氢原子团簇的第一性原理计算及实验研究",
            "language": "zh",
            "abstract": "## TiAI合金中氢原子团簇的第一性原理计算及实验研究\n\n![](images/8907e4aa6119db84b359f3dda141fd25d96bed3f0248dc1179643fd42963551b.jpg)\n\n项目批准号 52101024  \n申请代码 E0101  \n归口管理部门  \n收件日期\n\n![]…"
          },
          "document_title": "project1.pdf",
          "input_type": "files"
        }
      },
      {
        "index": 1,
        "file_name": "project2.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_86ddf70bafe847efabafe327cb1ecc43",
        "result": {
          "moves": [
            {
              "source_sections": [],
              "confidence": 0.75,
              "start": null,
              "end": null,
              "label": "立项依据",
              "text": ""
            },
            {
              "source_sections": [
                "中文摘要",
                "1. 研究计划执行情况概述。 / (2)研究目标完成情况。"
              ],
              "confidence": 0.85,
              "start": 644,
              "end": 6657,
              "label": "研究目标",
              "text": "计划构建静/动力隐式非线性有限元数值算法库，提出可动态装配的\"迭代控制+数值算法+数据模型\"的非线性求解设计模式，构建具有开放性、灵活性和支持模块动态装配的几何非线性单元计算和材料非线性本构计算框架，以及便于二次开发的统一接口标准，以提高非线性问题求解精度及效率。项目自立项至今，已完成既定研究内容并达到预期目标，研发了…"
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "大规模通用隐式非线性有限元分析软件研发",
            "language": "zh",
            "abstract": "## 大规模通用隐式非线性有限元分析软件研发\n\n![](images/99dea4d7fb7cbb0d7e12e98c208abf39bca959577da0003fb8087811f8b09a8b.jpg)\n\n项目批准号 12072059  \n申请代码 A0813  \n归口管理部门  \n收件日期\n\n![](image…"
          },
          "document_title": "project2.pdf",
          "input_type": "files"
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_01938b26475c469db3654df582ce6b3e",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 108740,
    "created_at": "2026-10-27T22:43:04.600471+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_e7111c35b7704133bf8280c40df6e69f",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 4. 中文科技文献分类

**工具ID**：`zh-classify`

依据中图分类法自动分类中文科技文献，支持文本与文件的单篇和批量处理；输出分类号、置信度、领域标签及批量统计。

**功能特点**：中图分类号预测，领域标签，跨学科判断，批量处理

**适用场景**：中文论文归类与报告编目

### 4.1 单文本

- **接口**：`POST /api/v1/classify/clc/zh/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `chinese_scientific_document_text` | string | 必填 | 中文科技文献文本 |
| `clc_labeled_data` | file (.json) | 选填 | 可选上传资源：中图分类标注数据（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/clc/zh/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "地震动记录选取的新视角：大数据与机器学习",
  "chinese_scientific_document_text": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取的一致性，并为工程结构时程分析提供更可靠的输入。"
}
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
  - is_interdisciplinary: boolean，示例 true
  - classifications: array<object>（2 项）
    - []: object
      - clc_code: string，示例 "P315"
      - classification_path: string，示例 "P 天文学、地球科学 > P3 地球物理学 > P31 大地（岩石界）物理学（固…"
      - confidence: number，示例 0.9
      - role: string，示例 "primary"
      - label: string，示例 "地震学"
  - domain_labels: array<object>（2 项）
    - []: object
      - label: string，示例 "地球物理学"
      - confidence: number，示例 0.9
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "地震动记录选取的新视角：大数据与机器学习",
    "is_interdisciplinary": true,
    "classifications": [
      {
        "clc_code": "P315",
        "classification_path": "P 天文学、地球科学 > P3 地球物理学 > P31 大地（岩石界）物理学（固体地球物理学） > P315 地震学",
        "confidence": 0.9,
        "role": "primary",
        "label": "地震学"
      },
      {
        "clc_code": "TP181",
        "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习",
        "confidence": 0.9,
        "role": "secondary",
        "label": "自动推理、机器学习"
      }
    ],
    "domain_labels": [
      {
        "label": "地球物理学",
        "confidence": 0.9
      },
      {
        "label": "自动化技术、计算机技术",
        "confidence": 0.9
      }
    ]
  },
  "meta": {
    "request_id": "req_a1e09127eeea428ba7b20246ea5f394d",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 5741,
    "created_at": "2026-10-27T22:02:34.710841+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_163b2801d0c448c4bdbd90f9aab91e72",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_34e835a65eb9447f8025be6d5ad56a86",
    "file_name": null
  }
}
```

### 4.2 批量文本

- **接口**：`POST /api/v1/classify/clc/zh/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `chinese_scientific_document_text` | object[] | 必填 | 中文科技文献文本 |
| `chinese_scientific_document_text[].id` | string | 选填 | 批量文本条目编号 |
| `chinese_scientific_document_text[].title` | string | 选填 | 文献题名 |
| `chinese_scientific_document_text[].text` | string | 必填 | 用户输入的文本内容 |
| `clc_labeled_data` | file (.json) | 选填 | 可选上传资源：中图分类标注数据（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/clc/zh/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "地震动记录选取的新视角：大数据与机器学习",
    "糖尿病肾病关键基因识别与潜在靶点分析",
    "融合多尺度特征的工业表面微小缺陷检测"
  ],
  "chinese_scientific_document_text": [
    {
      "id": "DEMO_1",
      "title": "地震动记录选取的新视角：大数据与机器学习",
      "text": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取的一致性，并为工程结构时程分析提供更可靠的输入。"
    },
    {
      "id": "DEMO_2",
      "title": "糖尿病肾病关键基因识别与潜在靶点分析",
      "text": "糖尿病肾病是糖尿病常见的微血管并发症。研究从 GEO 数据库获取相关转录组数据，利用加权基因共表达网络分析识别关键模块，并整合多种机器学习方法筛选特征基因。随后通过通路富集、免疫微环境关联和分子对接分析验证候选基因的诊断及治疗价值。结果表明，VWF 等基因具有较高的识别能力和潜在靶向价值，可为糖尿病肾病的精准诊疗提供参考。"
    },
    {
      "id": "DEMO_3",
      "title": "融合多尺度特征的工业表面微小缺陷检测",
      "text": "复杂工业表面中的裂纹、划痕和孔洞通常具有尺度差异大、边缘模糊及背景纹理干扰强等特点。本文提出融合多尺度特征增强和局部注意力的微小缺陷检测方法，通过跨层特征融合改善缺陷区域表征。多个公开数据集上的实验结果表明，该方法能够提高检测准确率与召回率，同时保持较低的推理延迟，适用于智能制造在线质量检测。"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_ec891d24b092424c978929723a5dea8d"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_26135e9d05e1466fa06ad500a7e32765"
      - result: object
        - document_title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
        - is_interdisciplinary: boolean，示例 true
        - classifications: array<object>（2 项）
          - []: object
        - domain_labels: array<object>（2 项）
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_ec891d24b092424c978929723a5dea8d",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_26135e9d05e1466fa06ad500a7e32765",
        "result": {
          "document_title": "地震动记录选取的新视角：大数据与机器学习",
          "is_interdisciplinary": true,
          "classifications": [
            {
              "clc_code": "P315",
              "classification_path": "P 天文学、地球科学 > P3 地球物理学 > P31 大地（岩石界）物理学（固体地球物理学） > P315 地震学",
              "confidence": 0.85,
              "role": "primary",
              "label": "地震学"
            },
            {
              "clc_code": "TP181",
              "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习",
              "confidence": 0.85,
              "role": "secondary",
              "label": "自动推理、机器学习"
            }
          ],
          "domain_labels": [
            {
              "label": "地球物理学",
              "confidence": 0.85
            },
            {
              "label": "自动化技术、计算机技术",
              "confidence": 0.85
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_5831c7027af9455c878d3fc0af40fc9a",
        "result": {
          "document_title": "糖尿病肾病关键基因识别与潜在靶点分析",
          "is_interdisciplinary": false,
          "classifications": [
            {
              "clc_code": "R587.2",
              "classification_path": "R 医药、卫生 > R5 内科学 > R58 内分泌腺疾病及代谢病 > R587 胰岛疾病 > R587.2 糖尿病性昏迷及其他并发症",
              "confidence": 0.9,
              "role": "primary",
              "label": "糖尿病性昏迷及其他并发症"
            }
          ],
          "domain_labels": [
            {
              "label": "内科学",
              "confidence": 0.9
            }
          ]
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_91f18eb798f741d6a454f6697aa3610b",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 10668,
    "created_at": "2026-10-27T22:02:45.391543+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_ec891d24b092424c978929723a5dea8d",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 4.3 单文件

- **接口**：`POST /api/v1/classify/clc/zh/file`
- **Content-Type**：multipart/form-data

> 上传中文文献 PDF/DOCX/TXT（英文文献会被 42201 语言门拒绝）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chinese_scientific_document_text` | file | 必填 | 中文科技文献文件（上传 PDF/DOCX/TXT） |
| `clc_labeled_data` | file (.json) | 选填 | 可选上传资源：中图分类标注数据（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/clc/zh/file' \
  -F 'chinese_scientific_document_text=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "融合大数据分析与机器学习的光伏电站运维管理系统设计"
  - is_interdisciplinary: boolean，示例 true
  - classifications: array<object>（2 项）
    - []: object
      - clc_code: string，示例 "TM615"
      - classification_path: string，示例 "T 工业技术 > TM 电工技术 > TM6 发电、发电厂 > TM61 各种发…"
      - confidence: number，示例 0.9
      - role: string，示例 "primary"
      - label: string，示例 "太阳能发电"
  - domain_labels: array<object>（2 项）
    - []: object
      - label: string，示例 "电工技术"
      - confidence: number，示例 0.9
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "融合大数据分析与机器学习的光伏电站运维管理系统设计",
    "is_interdisciplinary": true,
    "classifications": [
      {
        "clc_code": "TM615",
        "classification_path": "T 工业技术 > TM 电工技术 > TM6 发电、发电厂 > TM61 各种发电 > TM615 太阳能发电",
        "confidence": 0.9,
        "role": "primary",
        "label": "太阳能发电"
      },
      {
        "clc_code": "TP18",
        "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论",
        "confidence": 0.9,
        "role": "secondary",
        "label": "人工智能理论"
      }
    ],
    "domain_labels": [
      {
        "label": "电工技术",
        "confidence": 0.9
      },
      {
        "label": "自动化技术、计算机技术",
        "confidence": 0.9
      }
    ]
  },
  "meta": {
    "request_id": "req_db7c843d2f974d818b99a59d5b6e9183",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 26779,
    "created_at": "2026-10-27T22:35:20.989579+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_583581bf6e264a0e982dea955f59815c",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_ac12d53d204c4bdba9f59b9f8b058898",
    "file_name": "zh1.pdf"
  }
}
```

### 4.4 批量文件

- **接口**：`POST /api/v1/classify/clc/zh/files`
- **Content-Type**：multipart/form-data

> 上传中文文献 PDF/DOCX/TXT（英文文献会被 42201 语言门拒绝）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chinese_scientific_document_text` | file[] | 必填 | 中文科技文献文件（上传 PDF/DOCX/TXT） |
| `clc_labeled_data` | file (.json) | 选填 | 可选上传资源：中图分类标注数据（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/clc/zh/files' \
  -F 'chinese_scientific_document_text=@paper_01.pdf' \
  -F 'chinese_scientific_document_text=@paper_02.docx' \
  -F 'chinese_scientific_document_text=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_2d4ae1e68306451197e72a98bc7aff00"
  - input_type: string，示例 "files"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "zh1.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_d02828987aa04686abde228b5889d71a"
      - result: object
        - document_title: string，示例 "融合大数据分析与机器学习的光伏电站运维管理系统设计"
        - is_interdisciplinary: boolean，示例 true
        - classifications: array<object>（2 项）
          - []: object
        - domain_labels: array<object>（2 项）
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_2d4ae1e68306451197e72a98bc7aff00",
    "input_type": "files",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "zh1.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_d02828987aa04686abde228b5889d71a",
        "result": {
          "document_title": "融合大数据分析与机器学习的光伏电站运维管理系统设计",
          "is_interdisciplinary": true,
          "classifications": [
            {
              "clc_code": "TM615",
              "classification_path": "T 工业技术 > TM 电工技术 > TM6 发电、发电厂 > TM61 各种发电 > TM615 太阳能发电",
              "confidence": 0.9,
              "role": "primary",
              "label": "太阳能发电"
            },
            {
              "clc_code": "TP277",
              "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP2 自动化技术及设备 > TP27 自动化系统 > TP277 监视、报警、故障诊断系统",
              "confidence": 0.9,
              "role": "secondary",
              "label": "监视、报警、故障诊断系统"
            }
          ],
          "domain_labels": [
            {
              "label": "电工技术",
              "confidence": 0.9
            },
            {
              "label": "自动化技术、计算机技术",
              "confidence": 0.9
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": "zh2.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_22456b40cee24a5b8fece4db6bd9476b",
        "result": {
          "document_title": "地震动记录选取的新视角：大数据与机器学习",
          "is_interdisciplinary": true,
          "classifications": [
            {
              "clc_code": "P315",
              "classification_path": "P 天文学、地球科学 > P3 地球物理学 > P31 大地（岩石界）物理学（固体地球物理学） > P315 地震学",
              "confidence": 0.9,
              "role": "primary",
              "label": "地震学"
            },
            {
              "clc_code": "TP181",
              "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习",
              "confidence": 0.9,
              "role": "secondary",
              "label": "自动推理、机器学习"
            }
          ],
          "domain_labels": [
            {
              "label": "地球物理学",
              "confidence": 0.9
            },
            {
              "label": "自动化技术、计算机技术",
              "confidence": 0.9
            }
          ]
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_eaf2f7a91eaa4125b685dc2140e0f97b",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 46509,
    "created_at": "2026-10-27T22:36:07.545632+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_2d4ae1e68306451197e72a98bc7aff00",
    "input_type": "files",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

---

## 5. 英文科技文献分类

**工具ID**：`en-classify`

依据中图分类法对英文科技文献进行跨语言自动分类。单篇任务输出中图分类号预测结果和一个主领域标签；批量任务额外输出中图分类号分布及主领域标签分布分析报告。

**功能特点**：跨语言类目映射，分类号预测，批量分布报告

**适用场景**：SCI/EI文献分类与编目

### 5.1 单文本

- **接口**：`POST /api/v1/classify/clc/en/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `english_scientific_document_text` | string | 必填 | 英文科技文献文本 |
| `clc_labeled_data` | file (.json) | 必填 | 必填；用户可手动上传。中图分类标准（.json：中图分类号 + 类目名称） |
| `classification_standard_mapping_table` | file (.json) | 必填 | 必填；用户可手动上传。映射规则（.json：英文术语 + 中文术语） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/clc/en/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
  "english_scientific_document_text": "Reinforcement learning can improve the reasoning performance of vision-language models, but it may also reduce the diversity of their reasoning paths. This study compares reinforcement-learning models with their base counterparts and finds that the former reason more deeply along a narrow set of strategies, while the latter explore broader alternatives. The proposed Multi-Group Policy Optimization method encourages diverse solutions during training. Experiments on established benchmarks show improved reasoning diversity and a better balance between accuracy and scalability."
}
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "Divergent Thinking Through Reinforcement…"
  - is_interdisciplinary: boolean，示例 false
  - classifications: array<object>
    - []: object
      - clc_code: string，示例 "TP181"
      - classification_path: string，示例 "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > …"
      - confidence: number，示例 0.9
      - role: string，示例 "primary"
      - label: string，示例 "自动推理、机器学习"
  - domain_labels: array<object>
    - []: object
      - label: string，示例 "自动化技术、计算机技术"
      - confidence: number，示例 0.9
  - literature_distribution_analysis_report: object
    - document_count: number，示例 1
    - classified_document_count: number，示例 1
    - clc_category_count: number，示例 1
    - domain_label_count: number，示例 1
    - by_clc_category: array<object>
      - []: object
        - clc_code: string，示例 "TP181"
        - category_name: string，示例 "自动推理、机器学习"
        - classification_path: array<string>
        - document_count: number，示例 1
        - document_ratio: number，示例 1
        - document_percentage: number，示例 100
        - average_confidence: number，示例 0.9
    - by_domain_label: array<object>
      - []: object
        - label: string，示例 "自动化技术、计算机技术"
        - document_count: number，示例 1
        - document_percentage: number，示例 100
        - average_confidence: number，示例 0.9
    - domain_label_scope: string，示例 "primary_only"
  - cross_language_mapping: object
    - status: string，示例 "内置向量映射"
    - source_language: string，示例 "en"
    - target_language: string，示例 "zh"
    - source_terms: array<undefined>
    - source_term: string，示例 "reinforcement learning"
    - zh_term: string，示例 "强化学习"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
    "is_interdisciplinary": false,
    "classifications": [
      {
        "clc_code": "TP181",
        "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习",
        "confidence": 0.9,
        "role": "primary",
        "label": "自动推理、机器学习"
      }
    ],
    "domain_labels": [
      {
        "label": "自动化技术、计算机技术",
        "confidence": 0.9
      }
    ],
    "literature_distribution_analysis_report": {
      "document_count": 1,
      "classified_document_count": 1,
      "clc_category_count": 1,
      "domain_label_count": 1,
      "by_clc_category": [
        {
          "clc_code": "TP181",
          "category_name": "自动推理、机器学习",
          "classification_path": [
            "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习"
          ],
          "document_count": 1,
          "document_ratio": 1,
          "document_percentage": 100,
          "average_confidence": 0.9
        }
      ],
      "by_domain_label": [
        {
          "label": "自动化技术、计算机技术",
          "document_count": 1,
          "document_percentage": 100,
          "average_confidence": 0.9
        }
      ],
      "domain_label_scope": "primary_only"
    },
    "cross_language_mapping": {
      "status": "内置向量映射",
      "source_language": "en",
      "target_language": "zh",
      "source_terms": [],
      "source_term": "reinforcement learning",
      "zh_term": "强化学习"
    }
  },
  "meta": {
    "request_id": "req_b7dff391c55b49abb0d9b01bbb0decfc",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 12262,
    "created_at": "2026-10-27T22:02:57.666396+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_8b031fddb1194a989c3d65364c2bc46c",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_fc4ab3138ea842989c82910e65dd22a1",
    "file_name": null
  }
}
```

### 5.2 批量文本

- **接口**：`POST /api/v1/classify/clc/en/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `english_scientific_document_text` | object[] | 必填 | 英文科技文献文本 |
| `english_scientific_document_text[].id` | string | 选填 | 批量文本条目编号 |
| `english_scientific_document_text[].title` | string | 选填 | 文献题名 |
| `english_scientific_document_text[].text` | string | 必填 | 用户输入的文本内容 |
| `clc_labeled_data` | file (.json) | 必填 | 必填；用户可手动上传。中图分类标准（.json：中图分类号 + 类目名称） |
| `classification_standard_mapping_table` | file (.json) | 必填 | 必填；用户可手动上传。映射规则（.json：英文术语 + 中文术语） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/clc/en/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
    "Timestep-Aware Block Masking for Efficient Diffusion Inference",
    "Adaptive Temporal Graph Learning for Multivariate Anomaly Detection"
  ],
  "english_scientific_document_text": [
    {
      "id": "DEMO_1",
      "title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
      "text": "Reinforcement learning can improve the reasoning performance of vision-language models, but it may also reduce the diversity of their reasoning paths. This study compares reinforcement-learning models with their base counterparts and finds that the former reason more deeply along a narrow set of strategies, while the latter explore broader alternatives. The proposed Multi-Group Policy Optimization method encourages diverse solutions during training. Experiments on established benchmarks show improved reasoning diversity and a better balance between accuracy and scalability."
    },
    {
      "id": "DEMO_2",
      "title": "Timestep-Aware Block Masking for Efficient Diffusion Inference",
      "text": "Diffusion models produce high-quality samples but require repeated denoising and therefore incur substantial inference cost. This study proposes timestep-aware block masking, which learns which network blocks should be executed or reused at each denoising step. Independent optimization and knowledge-guided mask refinement reduce memory consumption while preserving generation quality. Experiments across several diffusion architectures demonstrate consistent acceleration with limited quality loss."
    },
    {
      "id": "DEMO_3",
      "title": "Adaptive Temporal Graph Learning for Multivariate Anomaly Detection",
      "text": "Multivariate time-series anomaly detection is difficult because sensor noise, missing observations and operating-condition shifts can hide weak fault patterns. This study proposes a temporal graph framework that combines adaptive dependency learning, multi-scale temporal encoding and consistency regularization. Experiments on public industrial datasets show lower false-alarm rates and improved detection performance under heterogeneous operating conditions."
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_833442666b22476392f4494eaed803ab"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_721bc4e87ee948a9a176debc3ff623e6"
      - result: object
        - document_title: string，示例 "Divergent Thinking Through Reinforcement…"
        - is_interdisciplinary: boolean，示例 false
        - classifications: array<object>
          - []: object
        - domain_labels: array<object>
          - []: object
        - literature_distribution_analysis_report: object
          - document_count: number，示例 1
          - classified_document_count: number，示例 1
          - clc_category_count: number，示例 1
          - domain_label_count: number，示例 1
          - by_clc_category: array<object>
          - by_domain_label: array<object>
          - domain_label_scope: string，示例 "primary_only"
        - cross_language_mapping: object
          - status: string，示例 "内置向量映射"
          - source_language: string，示例 "en"
          - target_language: string，示例 "zh"
          - source_terms: array<undefined>
          - source_term: string，示例 "reinforcement learning"
          - zh_term: string，示例 "强化学习"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_833442666b22476392f4494eaed803ab",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_721bc4e87ee948a9a176debc3ff623e6",
        "result": {
          "document_title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
          "is_interdisciplinary": false,
          "classifications": [
            {
              "clc_code": "TP391",
              "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP3 计算技术、计算机技术 > TP39 计算机的应用 > TP391 信息处理（信息加工）",
              "confidence": 0.9,
              "role": "primary",
              "label": "信息处理（信息加工）"
            }
          ],
          "domain_labels": [
            {
              "label": "自动化技术、计算机技术",
              "confidence": 0.9
            }
          ],
          "literature_distribution_analysis_report": {
            "document_count": 1,
            "classified_document_count": 1,
            "clc_category_count": 1,
            "domain_label_count": 1,
            "by_clc_category": [
              {
                "clc_code": "TP391",
                "category_name": "信息处理（信息加工）",
                "classification_path": [
                  "T 工业技术 > TP 自动化技术、计算机技术 > TP3 计算技术、计算机技术 > TP39 计算机的应用 > TP391 信息处理（信息加工）"
                ],
                "document_count": 1,
                "document_ratio": 1,
                "document_percentage": 100,
                "average_confidence": 0.9
              }
            ],
            "by_domain_label": [
              {
                "label": "自动化技术、计算机技术",
                "document_count": 1,
                "document_percentage": 100,
                "average_confidence": 0.9
              }
            ],
            "domain_label_scope": "primary_only"
          },
          "cross_language_mapping": {
            "status": "内置向量映射",
            "source_language": "en",
            "target_language": "zh",
            "source_terms": [],
            "source_term": "reinforcement learning",
            "zh_term": "强化学习"
          }
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_11c4f92a114845fd96310771014fa8b8",
        "result": {
          "document_title": "Timestep-Aware Block Masking for Efficient Diffusion Inference",
          "is_interdisciplinary": false,
          "classifications": [
            {
              "clc_code": "TP183",
              "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP183 人工神经网络与计算",
              "confidence": 0.9,
              "role": "primary",
              "label": "人工神经网络与计算"
            }
          ],
          "domain_labels": [
            {
              "label": "自动化技术、计算机技术",
              "confidence": 0.9
            }
          ],
          "literature_distribution_analysis_report": {
            "document_count": 1,
            "classified_document_count": 1,
            "clc_category_count": 1,
            "domain_label_count": 1,
            "by_clc_category": [
              {
                "clc_code": "TP183",
                "category_name": "人工神经网络与计算",
                "classification_path": [
                  "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP183 人工神经网络与计算"
                ],
                "document_count": 1,
                "document_ratio": 1,
                "document_percentage": 100,
                "average_confidence": 0.9
              }
            ],
            "by_domain_label": [
              {
                "label": "自动化技术、计算机技术",
                "document_count": 1,
                "document_percentage": 100,
                "average_confidence": 0.9
              }
            ],
            "domain_label_scope": "primary_only"
          },
          "cross_language_mapping": {
            "status": "内置向量映射",
            "source_language": "en",
            "target_language": "zh",
            "source_terms": [],
            "source_term": "diffusion model",
            "zh_term": "扩散模型"
          }
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_3aa1afb9bcae4f30a85806637b1db550",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 27562,
    "created_at": "2026-10-27T22:03:25.239510+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_833442666b22476392f4494eaed803ab",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 5.3 单文件

- **接口**：`POST /api/v1/classify/clc/en/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `english_scientific_document_text` | file | 必填 | 英文科技文献文件（上传 PDF/DOCX/TXT） |
| `clc_labeled_data` | file (.json) | 必填 | 必填；用户可手动上传。中图分类标准（.json：中图分类号 + 类目名称） |
| `classification_standard_mapping_table` | file (.json) | 必填 | 必填；用户可手动上传。映射规则（.json：英文术语 + 中文术语） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/clc/en/file' \
  -F 'english_scientific_document_text=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "Kareem Amin     Alex Bie    Weiwei Kong …"
  - is_interdisciplinary: boolean，示例 false
  - classifications: array<object>
    - []: object
      - clc_code: string，示例 "TP181"
      - classification_path: string，示例 "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > …"
      - confidence: number，示例 0.9
      - role: string，示例 "primary"
      - label: string，示例 "自动推理、机器学习"
  - domain_labels: array<object>
    - []: object
      - label: string，示例 "自动化技术、计算机技术"
      - confidence: number，示例 0.9
  - literature_distribution_analysis_report: object
    - document_count: number，示例 1
    - classified_document_count: number，示例 1
    - clc_category_count: number，示例 1
    - domain_label_count: number，示例 1
    - by_clc_category: array<object>
      - []: object
        - clc_code: string，示例 "TP181"
        - category_name: string，示例 "自动推理、机器学习"
        - classification_path: array<string>
        - document_count: number，示例 1
        - document_ratio: number，示例 1
        - document_percentage: number，示例 100
        - average_confidence: number，示例 0.9
    - by_domain_label: array<object>
      - []: object
        - label: string，示例 "自动化技术、计算机技术"
        - document_count: number，示例 1
        - document_percentage: number，示例 100
        - average_confidence: number，示例 0.9
    - domain_label_scope: string，示例 "primary_only"
  - cross_language_mapping: object
    - status: string，示例 "内置向量映射"
    - source_language: string，示例 "en"
    - target_language: string，示例 "zh"
    - source_terms: array<undefined>
    - source_term: string，示例 ""
    - zh_term: string，示例 ""
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "Kareem Amin     Alex Bie    Weiwei Kong    Umar Syed     Sergei Vassilvitskii",
    "is_interdisciplinary": false,
    "classifications": [
      {
        "clc_code": "TP181",
        "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习",
        "confidence": 0.9,
        "role": "primary",
        "label": "自动推理、机器学习"
      }
    ],
    "domain_labels": [
      {
        "label": "自动化技术、计算机技术",
        "confidence": 0.9
      }
    ],
    "literature_distribution_analysis_report": {
      "document_count": 1,
      "classified_document_count": 1,
      "clc_category_count": 1,
      "domain_label_count": 1,
      "by_clc_category": [
        {
          "clc_code": "TP181",
          "category_name": "自动推理、机器学习",
          "classification_path": [
            "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习"
          ],
          "document_count": 1,
          "document_ratio": 1,
          "document_percentage": 100,
          "average_confidence": 0.9
        }
      ],
      "by_domain_label": [
        {
          "label": "自动化技术、计算机技术",
          "document_count": 1,
          "document_percentage": 100,
          "average_confidence": 0.9
        }
      ],
      "domain_label_scope": "primary_only"
    },
    "cross_language_mapping": {
      "status": "内置向量映射",
      "source_language": "en",
      "target_language": "zh",
      "source_terms": [],
      "source_term": "",
      "zh_term": ""
    }
  },
  "meta": {
    "request_id": "req_d569a477c2ae4ef4ba6b6c378bdaa274",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 35730,
    "created_at": "2026-10-27T22:19:48.250574+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_c416d5e1b0e94965b4ba784ca0fe78d9",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_22e180578c9a492f95f2293198c6aa88",
    "file_name": "7.pdf"
  }
}
```

### 5.4 批量文件

- **接口**：`POST /api/v1/classify/clc/en/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `english_scientific_document_text` | file[] | 必填 | 英文科技文献文件（上传 PDF/DOCX/TXT） |
| `clc_labeled_data` | file (.json) | 必填 | 必填；用户可手动上传。中图分类标准（.json：中图分类号 + 类目名称） |
| `classification_standard_mapping_table` | file (.json) | 必填 | 必填；用户可手动上传。映射规则（.json：英文术语 + 中文术语） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/clc/en/files' \
  -F 'english_scientific_document_text=@paper_01.pdf' \
  -F 'english_scientific_document_text=@paper_02.docx' \
  -F 'english_scientific_document_text=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_de7e4c3dda9a456dbe7488d2a95df110"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_5c739a6b4a4644bbb930fac42a6b5bf0"
      - result: object
        - document_title: string，示例 "Kareem Amin     Alex Bie    Weiwei Kong …"
        - is_interdisciplinary: boolean，示例 false
        - classifications: array<object>
          - []: object
        - domain_labels: array<object>
          - []: object
        - literature_distribution_analysis_report: object
          - document_count: number，示例 1
          - classified_document_count: number，示例 1
          - clc_category_count: number，示例 1
          - domain_label_count: number，示例 1
          - by_clc_category: array<object>
          - by_domain_label: array<object>
          - domain_label_scope: string，示例 "primary_only"
        - cross_language_mapping: object
          - status: string，示例 "内置向量映射"
          - source_language: string，示例 "en"
          - target_language: string，示例 "zh"
          - source_terms: array<undefined>
          - source_term: string，示例 "PAC learning"
          - zh_term: string，示例 "可能近似正确学习"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_de7e4c3dda9a456dbe7488d2a95df110",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_5c739a6b4a4644bbb930fac42a6b5bf0",
        "result": {
          "document_title": "Kareem Amin     Alex Bie    Weiwei Kong    Umar Syed     Sergei Vassilvitskii",
          "is_interdisciplinary": false,
          "classifications": [
            {
              "clc_code": "TP181",
              "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习",
              "confidence": 0.9,
              "role": "primary",
              "label": "自动推理、机器学习"
            }
          ],
          "domain_labels": [
            {
              "label": "自动化技术、计算机技术",
              "confidence": 0.9
            }
          ],
          "literature_distribution_analysis_report": {
            "document_count": 1,
            "classified_document_count": 1,
            "clc_category_count": 1,
            "domain_label_count": 1,
            "by_clc_category": [
              {
                "clc_code": "TP181",
                "category_name": "自动推理、机器学习",
                "classification_path": [
                  "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习"
                ],
                "document_count": 1,
                "document_ratio": 1,
                "document_percentage": 100,
                "average_confidence": 0.9
              }
            ],
            "by_domain_label": [
              {
                "label": "自动化技术、计算机技术",
                "document_count": 1,
                "document_percentage": 100,
                "average_confidence": 0.9
              }
            ],
            "domain_label_scope": "primary_only"
          },
          "cross_language_mapping": {
            "status": "内置向量映射",
            "source_language": "en",
            "target_language": "zh",
            "source_terms": [],
            "source_term": "PAC learning",
            "zh_term": "可能近似正确学习"
          }
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_93201a52c1f94cbb9974c6ca42808339",
        "result": {
          "document_title": "Kareem Amin     Alex Bie    Weiwei Kong    Umar Syed     Sergei Vassilvitskii",
          "is_interdisciplinary": false,
          "classifications": [
            {
              "clc_code": "TP181",
              "classification_path": "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习",
              "confidence": 0.92,
              "role": "primary",
              "label": "自动推理、机器学习"
            }
          ],
          "domain_labels": [
            {
              "label": "自动化技术、计算机技术",
              "confidence": 0.92
            }
          ],
          "literature_distribution_analysis_report": {
            "document_count": 1,
            "classified_document_count": 1,
            "clc_category_count": 1,
            "domain_label_count": 1,
            "by_clc_category": [
              {
                "clc_code": "TP181",
                "category_name": "自动推理、机器学习",
                "classification_path": [
                  "T 工业技术 > TP 自动化技术、计算机技术 > TP1 自动化基础理论 > TP18 人工智能理论 > TP181 自动推理、机器学习"
                ],
                "document_count": 1,
                "document_ratio": 1,
                "document_percentage": 100,
                "average_confidence": 0.92
              }
            ],
            "by_domain_label": [
              {
                "label": "自动化技术、计算机技术",
                "document_count": 1,
                "document_percentage": 100,
                "average_confidence": 0.92
              }
            ],
            "domain_label_scope": "primary_only"
          },
          "cross_language_mapping": {
            "status": "内置向量映射",
            "source_language": "en",
            "target_language": "zh",
            "source_terms": [],
            "source_term": "",
            "zh_term": ""
          }
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_539ed34ab309417d965107b4a6172591",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 14015,
    "created_at": "2026-10-27T22:20:02.289125+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_de7e4c3dda9a456dbe7488d2a95df110",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 6. 专业领域科技文献分类

**工具ID**：`domain-classify`

用户先选择专业领域，再在该领域分类体系内进行多层级细分。输出严格包括多层级领域分类结果、分类置信度、领域标签和数据分布报告。

**功能特点**：领域自动判断，三级分类，置信度与批量统计

**适用场景**：专题文献组织与领域建库

### 6.1 单文本

- **接口**：`POST /api/v1/classify/domain/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `domain_scientific_literature_data` | string | 必填 | 专业领域科技文献文本 |
| `professional_domain` | string | 选填 | 选填;目标专业领域编码,取值 "01"–"32"。不传由系统按文本自动判定领域(默认行为,前端不提供选择) |
| `domain_classification_rules` | file (.json) | 选填 | 可选上传资源：领域分类规则（.json） |
| `manually_labeled_training_data` | file (.json) | 选填 | 可选上传资源：人工标注训练数据（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/domain/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因",
  "domain_scientific_literature_data": "研究从GEO数据库获取糖尿病肾病转录组数据，利用WGCNA构建共表达网络，整合113种机器学习算法筛选特征基因，鉴定出VWF等关键基因。"
}
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因"
  - document: object
    - document_id: null（本示例中为空）
    - title: string，示例 "基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因"
    - abstract: string，示例 ""
    - keywords: array<undefined>
    - language: null（本示例中为空）
    - source_file: null（本示例中为空）
  - selected_domain: object
    - code: string，示例 "10"
    - name: string，示例 "医学与卫生健康"
    - auto_judged: boolean，示例 true
  - professional_domain: string，示例 "医学与卫生健康"
  - domain_match_result: object
    - selected_domain: object
      - code: string，示例 "10"
      - name: string，示例 "医学与卫生健康"
      - auto_judged: boolean，示例 true
    - status: string，示例 "matched"
    - match_score: number，示例 0.91
    - message: string，示例 "文献分类号已成功解析，与所选领域「医学与卫生健康」匹配"
    - evidence: array<undefined>
  - multilevel_classification_results: array<object>
    - []: object
      - role: string，示例 "main"
      - level_1: string，示例 "R 医药、卫生"
      - level_2: string，示例 "R5 内科学"
      - level_3: string，示例 "R58 内分泌腺疾病及代谢病"
      - classification_path: array<string>（3 项）
      - clc_code: string，示例 "R58"
      - category_name: string，示例 "内分泌腺疾病及代谢病"
      - confidence: number，示例 0.91
  - classification_confidence: object
    - overall: number，示例 0.91
    - level_1: number，示例 0.91
    - level_2: number，示例 0.91
    - level_3: number，示例 0.91
  - domain_labels: array<object>（2 项）
    - []: object
      - label: string，示例 "医学与卫生健康"
      - confidence: number，示例 0.91
  - classifications: array<object>
    - []: object
      - role: string，示例 "main"
      - level_1: string，示例 "R 医药、卫生"
      - level_2: string，示例 "R5 内科学"
      - level_3: string，示例 "R58 内分泌腺疾病及代谢病"
      - classification_path: array<string>（3 项）
      - clc_code: string，示例 "R58"
      - category_name: string，示例 "内分泌腺疾病及代谢病"
      - confidence: number，示例 0.91
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因",
    "document": {
      "document_id": null,
      "title": "基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因",
      "abstract": "",
      "keywords": [],
      "language": null,
      "source_file": null
    },
    "selected_domain": {
      "code": "10",
      "name": "医学与卫生健康",
      "auto_judged": true
    },
    "professional_domain": "医学与卫生健康",
    "domain_match_result": {
      "selected_domain": {
        "code": "10",
        "name": "医学与卫生健康",
        "auto_judged": true
      },
      "status": "matched",
      "match_score": 0.91,
      "message": "文献分类号已成功解析，与所选领域「医学与卫生健康」匹配",
      "evidence": []
    },
    "multilevel_classification_results": [
      {
        "role": "main",
        "level_1": "R 医药、卫生",
        "level_2": "R5 内科学",
        "level_3": "R58 内分泌腺疾病及代谢病",
        "classification_path": [
          "R 医药、卫生",
          "R5 内科学",
          "…（共 3 项，示例保留前 2 项）"
        ],
        "clc_code": "R58",
        "category_name": "内分泌腺疾病及代谢病",
        "confidence": 0.91
      }
    ],
    "classification_confidence": {
      "overall": 0.91,
      "level_1": 0.91,
      "level_2": 0.91,
      "level_3": 0.91
    },
    "domain_labels": [
      {
        "label": "医学与卫生健康",
        "confidence": 0.91
      },
      {
        "label": "内分泌腺疾病及代谢病",
        "confidence": 0.91
      }
    ],
    "classifications": [
      {
        "role": "main",
        "level_1": "R 医药、卫生",
        "level_2": "R5 内科学",
        "level_3": "R58 内分泌腺疾病及代谢病",
        "classification_path": [
          "R 医药、卫生",
          "R5 内科学",
          "…（共 3 项，示例保留前 2 项）"
        ],
        "clc_code": "R58",
        "category_name": "内分泌腺疾病及代谢病",
        "confidence": 0.91
      }
    ]
  },
  "meta": {
    "request_id": "req_43e69b9948514247aa0fea4dd25b36e5",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 8890,
    "created_at": "2026-10-27T22:03:34.143946+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_b7d851a976124d72aa55bb8d4e884435",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_afbae8bae33a40b68fe7855a3ddcca34",
    "file_name": null
  }
}
```

### 6.2 批量文本

- **接口**：`POST /api/v1/classify/domain/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `domain_scientific_literature_data` | object[] | 必填 | 专业领域科技文献文本 |
| `domain_scientific_literature_data[].id` | string | 选填 | 批量文本条目编号 |
| `domain_scientific_literature_data[].text` | string | 必填 | 用户输入的文本内容 |
| `domain_scientific_literature_data[].title` | string | 选填 | 文献题名 |
| `domain_classification_rules` | object | 选填 | 领域分类规则引用。定义 32 领域清单、领域与中图类号段映射、三级分类粒度要求;用户上传自定义版本可覆盖判定口径 |
| `domain_classification_rules.source` | string | 选填 | 资源来源或文献来源 |
| `domain_classification_rules.resource_id` | string | 条件必填 | 数据库资源编号 |
| `manually_labeled_training_data` | object | 选填 | 人工标注训练数据引用。64 条标注样本(文献+领域+正确中图类号),注入提示词作 few-shot 参考校准标注风格 |
| `manually_labeled_training_data.source` | string | 选填 | 资源来源或文献来源 |
| `manually_labeled_training_data.resource_id` | string | 条件必填 | 数据库资源编号 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/domain/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "糖尿病肾病基因研究",
    "工业表面缺陷检测"
  ],
  "domain_scientific_literature_data": [
    {
      "id": "DOC1",
      "text": "研究从GEO数据库获取糖尿病肾病转录组数据，利用WGCNA构建共表达网络，整合113种机器学习算法筛选特征基因，鉴定出VWF等关键基因。",
      "title": "糖尿病肾病基因研究"
    },
    {
      "id": "DOC2",
      "text": "提出融合轻量级卷积网络和动态注意力机制的缺陷检测模型，通过多尺度特征聚合增强缺陷表征，在工业缺陷数据集上提高检测精度。",
      "title": "工业表面缺陷检测"
    }
  ],
  "domain_classification_rules": {
    "source": "database",
    "resource_id": "RES-BUNDLED-DOMAIN-RULE"
  },
  "manually_labeled_training_data": {
    "source": "database",
    "resource_id": "RES-BUNDLED-DOMAIN-GOLD"
  }
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_7ca83946b8c74d888f37bc19097155a7"
  - input_type: string，示例 "texts"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_89754c50403b4f5bb1361d7d8bc7b728"
      - result: object
        - document_title: string，示例 "糖尿病肾病基因研究"
        - document: object
          - document_id: null（本示例中为空）
          - title: string，示例 "糖尿病肾病基因研究"
          - abstract: string，示例 ""
          - keywords: array<undefined>
          - language: null（本示例中为空）
          - source_file: null（本示例中为空）
        - selected_domain: object
          - code: string，示例 "10"
          - name: string，示例 "医学与卫生健康"
          - auto_judged: boolean，示例 true
        - professional_domain: string，示例 "医学与卫生健康"
        - domain_match_result: object
          - selected_domain: object
          - status: string，示例 "matched"
          - match_score: number，示例 0.95
          - message: string，示例 "文献分类号已成功解析，与所选领域「医学与卫生健康」匹配"
          - evidence: array<undefined>
        - multilevel_classification_results: array<object>
          - []: object
        - classification_confidence: object
          - overall: number，示例 0.95
          - level_1: number，示例 0.95
          - level_2: number，示例 0.95
          - level_3: number，示例 0.95
        - domain_labels: array<object>（2 项）
          - []: object
        - classifications: array<object>
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_7ca83946b8c74d888f37bc19097155a7",
    "input_type": "texts",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_89754c50403b4f5bb1361d7d8bc7b728",
        "result": {
          "document_title": "糖尿病肾病基因研究",
          "document": {
            "document_id": null,
            "title": "糖尿病肾病基因研究",
            "abstract": "",
            "keywords": [],
            "language": null,
            "source_file": null
          },
          "selected_domain": {
            "code": "10",
            "name": "医学与卫生健康",
            "auto_judged": true
          },
          "professional_domain": "医学与卫生健康",
          "domain_match_result": {
            "selected_domain": {
              "code": "10",
              "name": "医学与卫生健康",
              "auto_judged": true
            },
            "status": "matched",
            "match_score": 0.95,
            "message": "文献分类号已成功解析，与所选领域「医学与卫生健康」匹配",
            "evidence": []
          },
          "multilevel_classification_results": [
            {
              "role": "main",
              "level_1": "R 医药、卫生",
              "level_2": "R5 内科学",
              "level_3": "R58 内分泌腺疾病及代谢病",
              "classification_path": [
                "R 医药、卫生",
                "R5 内科学",
                "…（共 3 项，示例保留前 2 项）"
              ],
              "clc_code": "R58",
              "category_name": "内分泌腺疾病及代谢病",
              "confidence": 0.95
            }
          ],
          "classification_confidence": {
            "overall": 0.95,
            "level_1": 0.95,
            "level_2": 0.95,
            "level_3": 0.95
          },
          "domain_labels": [
            {
              "label": "医学与卫生健康",
              "confidence": 0.95
            },
            {
              "label": "内分泌腺疾病及代谢病",
              "confidence": 0.95
            }
          ],
          "classifications": [
            {
              "role": "main",
              "level_1": "R 医药、卫生",
              "level_2": "R5 内科学",
              "level_3": "R58 内分泌腺疾病及代谢病",
              "classification_path": [
                "R 医药、卫生",
                "R5 内科学",
                "…（共 3 项，示例保留前 2 项）"
              ],
              "clc_code": "R58",
              "category_name": "内分泌腺疾病及代谢病",
              "confidence": 0.95
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_c00a18b893f44c79bb96af8027e2f320",
        "result": {
          "document_title": "工业表面缺陷检测",
          "document": {
            "document_id": null,
            "title": "工业表面缺陷检测",
            "abstract": "",
            "keywords": [],
            "language": null,
            "source_file": null
          },
          "selected_domain": {
            "code": "25",
            "name": "人工智能与计算机技术",
            "auto_judged": true
          },
          "professional_domain": "人工智能与计算机技术",
          "domain_match_result": {
            "selected_domain": {
              "code": "25",
              "name": "人工智能与计算机技术",
              "auto_judged": true
            },
            "status": "matched",
            "match_score": 0.85,
            "message": "文献分类号已成功解析，与所选领域「人工智能与计算机技术」匹配",
            "evidence": []
          },
          "multilevel_classification_results": [
            {
              "role": "main",
              "level_1": "T 工业技术",
              "level_2": "TP 自动化技术、计算机技术",
              "level_3": "TP3 计算技术、计算机技术",
              "classification_path": [
                "T 工业技术",
                "TP 自动化技术、计算机技术",
                "…（共 3 项，示例保留前 2 项）"
              ],
              "clc_code": "TP3",
              "category_name": "计算技术、计算机技术",
              "confidence": 0.85
            }
          ],
          "classification_confidence": {
            "overall": 0.85,
            "level_1": 0.85,
            "level_2": 0.85,
            "level_3": 0.85
          },
          "domain_labels": [
            {
              "label": "人工智能与计算机技术",
              "confidence": 0.85
            },
            {
              "label": "计算技术、计算机技术",
              "confidence": 0.85
            }
          ],
          "classifications": [
            {
              "role": "main",
              "level_1": "T 工业技术",
              "level_2": "TP 自动化技术、计算机技术",
              "level_3": "TP3 计算技术、计算机技术",
              "classification_path": [
                "T 工业技术",
                "TP 自动化技术、计算机技术",
                "…（共 3 项，示例保留前 2 项）"
              ],
              "clc_code": "TP3",
              "category_name": "计算技术、计算机技术",
              "confidence": 0.85
            }
          ]
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_ffcb79551ad2427983214665f4edf697",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 9845,
    "created_at": "2026-10-27T22:03:44.000921+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_7ca83946b8c74d888f37bc19097155a7",
    "input_type": "texts",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

### 6.3 单文件

- **接口**：`POST /api/v1/classify/domain/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `domain_scientific_literature_data` | file | 必填 | 专业领域科技文献文件（上传 PDF/DOCX/TXT） |
| `professional_domain` | string | 选填 | 选填;目标专业领域编码,取值 "01"–"32"。不传由系统按文本自动判定领域(默认行为,前端不提供选择) |
| `domain_classification_rules` | file (.json) | 选填 | 可选上传资源：领域分类规则（.json） |
| `manually_labeled_training_data` | file (.json) | 选填 | 可选上传资源：人工标注训练数据（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/domain/file' \
  -F 'domain_scientific_literature_data=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "Kareem Amin     Alex Bie    Weiwei Kong …"
  - document: object
    - document_id: null（本示例中为空）
    - title: string，示例 "7.pdf"
    - abstract: string，示例 ""
    - keywords: array<undefined>
    - language: null（本示例中为空）
    - source_file: string，示例 "7.pdf"
  - selected_domain: object
    - code: string，示例 "25"
    - name: string，示例 "人工智能与计算机技术"
    - auto_judged: boolean，示例 true
  - professional_domain: string，示例 "人工智能与计算机技术"
  - domain_match_result: object
    - selected_domain: object
      - code: string，示例 "25"
      - name: string，示例 "人工智能与计算机技术"
      - auto_judged: boolean，示例 true
    - status: string，示例 "matched"
    - match_score: number，示例 0.85
    - message: string，示例 "文献分类号已成功解析，与所选领域「人工智能与计算机技术」匹配"
    - evidence: array<undefined>
  - multilevel_classification_results: array<object>
    - []: object
      - role: string，示例 "main"
      - level_1: string，示例 "T 工业技术"
      - level_2: string，示例 "TP 自动化技术、计算机技术"
      - level_3: string，示例 "TP1 自动化基础理论"
      - classification_path: array<string>（3 项）
      - clc_code: string，示例 "TP1"
      - category_name: string，示例 "自动化基础理论"
      - confidence: number，示例 0.85
  - classification_confidence: object
    - overall: number，示例 0.85
    - level_1: number，示例 0.85
    - level_2: number，示例 0.85
    - level_3: number，示例 0.85
  - domain_labels: array<object>（2 项）
    - []: object
      - label: string，示例 "人工智能与计算机技术"
      - confidence: number，示例 0.85
  - classifications: array<object>
    - []: object
      - role: string，示例 "main"
      - level_1: string，示例 "T 工业技术"
      - level_2: string，示例 "TP 自动化技术、计算机技术"
      - level_3: string，示例 "TP1 自动化基础理论"
      - classification_path: array<string>（3 项）
      - clc_code: string，示例 "TP1"
      - category_name: string，示例 "自动化基础理论"
      - confidence: number，示例 0.85
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "Kareem Amin     Alex Bie    Weiwei Kong    Umar Syed     Sergei Vassilvitskii",
    "document": {
      "document_id": null,
      "title": "7.pdf",
      "abstract": "",
      "keywords": [],
      "language": null,
      "source_file": "7.pdf"
    },
    "selected_domain": {
      "code": "25",
      "name": "人工智能与计算机技术",
      "auto_judged": true
    },
    "professional_domain": "人工智能与计算机技术",
    "domain_match_result": {
      "selected_domain": {
        "code": "25",
        "name": "人工智能与计算机技术",
        "auto_judged": true
      },
      "status": "matched",
      "match_score": 0.85,
      "message": "文献分类号已成功解析，与所选领域「人工智能与计算机技术」匹配",
      "evidence": []
    },
    "multilevel_classification_results": [
      {
        "role": "main",
        "level_1": "T 工业技术",
        "level_2": "TP 自动化技术、计算机技术",
        "level_3": "TP1 自动化基础理论",
        "classification_path": [
          "T 工业技术",
          "TP 自动化技术、计算机技术",
          "…（共 3 项，示例保留前 2 项）"
        ],
        "clc_code": "TP1",
        "category_name": "自动化基础理论",
        "confidence": 0.85
      }
    ],
    "classification_confidence": {
      "overall": 0.85,
      "level_1": 0.85,
      "level_2": 0.85,
      "level_3": 0.85
    },
    "domain_labels": [
      {
        "label": "人工智能与计算机技术",
        "confidence": 0.85
      },
      {
        "label": "自动化基础理论",
        "confidence": 0.85
      }
    ],
    "classifications": [
      {
        "role": "main",
        "level_1": "T 工业技术",
        "level_2": "TP 自动化技术、计算机技术",
        "level_3": "TP1 自动化基础理论",
        "classification_path": [
          "T 工业技术",
          "TP 自动化技术、计算机技术",
          "…（共 3 项，示例保留前 2 项）"
        ],
        "clc_code": "TP1",
        "category_name": "自动化基础理论",
        "confidence": 0.85
      }
    ]
  },
  "meta": {
    "request_id": "req_03bbd8d245a64f60ac290483a5f82e27",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 9621,
    "created_at": "2026-10-27T22:20:11.928017+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_cfdd14a0525342d5af0fbd3e958eff58",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_9fe299cf7b344b8b9bd01b93ee93c312",
    "file_name": "7.pdf"
  }
}
```

### 6.4 批量文件

- **接口**：`POST /api/v1/classify/domain/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `domain_scientific_literature_data` | file[] | 必填 | 专业领域科技文献文件（上传 PDF/DOCX/TXT） |
| `professional_domain` | string | 选填 | 选填;目标专业领域编码,取值 "01"–"32"。不传由系统按文本自动判定领域(默认行为,前端不提供选择) |
| `domain_classification_rules` | file (.json) | 选填 | 可选上传资源：领域分类规则（.json） |
| `manually_labeled_training_data` | file (.json) | 选填 | 可选上传资源：人工标注训练数据（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/classify/domain/files' \
  -F 'domain_scientific_literature_data=@paper_01.pdf' \
  -F 'domain_scientific_literature_data=@paper_02.docx' \
  -F 'domain_scientific_literature_data=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_33839c3fcf624b289fbac26a08e35a52"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_42bfd000a67d41c8b0e52e04e7fb6763"
      - result: object
        - document_title: string，示例 "Kareem Amin     Alex Bie    Weiwei Kong …"
        - document: object
          - document_id: null（本示例中为空）
          - title: string，示例 "7.pdf"
          - abstract: string，示例 ""
          - keywords: array<undefined>
          - language: null（本示例中为空）
          - source_file: string，示例 "7.pdf"
        - selected_domain: object
          - code: string，示例 "25"
          - name: string，示例 "人工智能与计算机技术"
          - auto_judged: boolean，示例 true
        - professional_domain: string，示例 "人工智能与计算机技术"
        - domain_match_result: object
          - selected_domain: object
          - status: string，示例 "matched"
          - match_score: number，示例 0.85
          - message: string，示例 "文献分类号已成功解析，与所选领域「人工智能与计算机技术」匹配"
          - evidence: array<undefined>
        - multilevel_classification_results: array<object>
          - []: object
        - classification_confidence: object
          - overall: number，示例 0.85
          - level_1: number，示例 0.85
          - level_2: number，示例 0.85
          - level_3: number，示例 0.85
        - domain_labels: array<object>（2 项）
          - []: object
        - classifications: array<object>
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_33839c3fcf624b289fbac26a08e35a52",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_42bfd000a67d41c8b0e52e04e7fb6763",
        "result": {
          "document_title": "Kareem Amin     Alex Bie    Weiwei Kong    Umar Syed     Sergei Vassilvitskii",
          "document": {
            "document_id": null,
            "title": "7.pdf",
            "abstract": "",
            "keywords": [],
            "language": null,
            "source_file": "7.pdf"
          },
          "selected_domain": {
            "code": "25",
            "name": "人工智能与计算机技术",
            "auto_judged": true
          },
          "professional_domain": "人工智能与计算机技术",
          "domain_match_result": {
            "selected_domain": {
              "code": "25",
              "name": "人工智能与计算机技术",
              "auto_judged": true
            },
            "status": "matched",
            "match_score": 0.85,
            "message": "文献分类号已成功解析，与所选领域「人工智能与计算机技术」匹配",
            "evidence": []
          },
          "multilevel_classification_results": [
            {
              "role": "main",
              "level_1": "T 工业技术",
              "level_2": "TP 自动化技术、计算机技术",
              "level_3": "TP1 自动化基础理论",
              "classification_path": [
                "T 工业技术",
                "TP 自动化技术、计算机技术",
                "…（共 3 项，示例保留前 2 项）"
              ],
              "clc_code": "TP1",
              "category_name": "自动化基础理论",
              "confidence": 0.85
            }
          ],
          "classification_confidence": {
            "overall": 0.85,
            "level_1": 0.85,
            "level_2": 0.85,
            "level_3": 0.85
          },
          "domain_labels": [
            {
              "label": "人工智能与计算机技术",
              "confidence": 0.85
            },
            {
              "label": "自动化基础理论",
              "confidence": 0.85
            }
          ],
          "classifications": [
            {
              "role": "main",
              "level_1": "T 工业技术",
              "level_2": "TP 自动化技术、计算机技术",
              "level_3": "TP1 自动化基础理论",
              "classification_path": [
                "T 工业技术",
                "TP 自动化技术、计算机技术",
                "…（共 3 项，示例保留前 2 项）"
              ],
              "clc_code": "TP1",
              "category_name": "自动化基础理论",
              "confidence": 0.85
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_d822d6dfa9df40c58048e9db2956caae",
        "result": {
          "document_title": "Kareem Amin     Alex Bie    Weiwei Kong    Umar Syed     Sergei Vassilvitskii",
          "document": {
            "document_id": null,
            "title": "35.pdf",
            "abstract": "",
            "keywords": [],
            "language": null,
            "source_file": "35.pdf"
          },
          "selected_domain": {
            "code": "25",
            "name": "人工智能与计算机技术",
            "auto_judged": true
          },
          "professional_domain": "人工智能与计算机技术",
          "domain_match_result": {
            "selected_domain": {
              "code": "25",
              "name": "人工智能与计算机技术",
              "auto_judged": true
            },
            "status": "matched",
            "match_score": 0.85,
            "message": "文献分类号已成功解析，与所选领域「人工智能与计算机技术」匹配",
            "evidence": []
          },
          "multilevel_classification_results": [
            {
              "role": "main",
              "level_1": "T 工业技术",
              "level_2": "TP 自动化技术、计算机技术",
              "level_3": "TP1 自动化基础理论",
              "classification_path": [
                "T 工业技术",
                "TP 自动化技术、计算机技术",
                "…（共 3 项，示例保留前 2 项）"
              ],
              "clc_code": "TP1",
              "category_name": "自动化基础理论",
              "confidence": 0.85
            }
          ],
          "classification_confidence": {
            "overall": 0.85,
            "level_1": 0.85,
            "level_2": 0.85,
            "level_3": 0.85
          },
          "domain_labels": [
            {
              "label": "人工智能与计算机技术",
              "confidence": 0.85
            },
            {
              "label": "自动化基础理论",
              "confidence": 0.85
            }
          ],
          "classifications": [
            {
              "role": "main",
              "level_1": "T 工业技术",
              "level_2": "TP 自动化技术、计算机技术",
              "level_3": "TP1 自动化基础理论",
              "classification_path": [
                "T 工业技术",
                "TP 自动化技术、计算机技术",
                "…（共 3 项，示例保留前 2 项）"
              ],
              "clc_code": "TP1",
              "category_name": "自动化基础理论",
              "confidence": 0.85
            }
          ]
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_85decb4e2a154072b78c45789df72d98",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 11026,
    "created_at": "2026-10-27T22:20:22.972923+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_33839c3fcf624b289fbac26a08e35a52",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 7. 中文科技文献关键词识别

**工具ID**：`zh-keyword`

面向医学、工程、材料科学等多领域中文科技语料，从科技文献摘要中提取核心关键词或关键短语。支持单文本、批量文本、单文件和批量文件；文件模式仅解析并使用摘要。系统自动识别文献领域，并在算法内部自适应调用领域术语资源与动态词权模型，无需用户上传或维护词典。

**功能特点**：摘要定位，领域识别，术语资源与自适应词权

**适用场景**：中文论文标引与术语抽取

### 7.1 单文本

- **接口**：`POST /api/v1/keywords/zh/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `chinese_scientific_abstract` | string | 必填 | 中文科技文献摘要 |
| `dictionary_id` | string | 选填 | 用户词典编号(可选)。已保存词典的编号;词典术语在原文逐字出现时加权提升并归一到规范表达 |
| `custom_dictionary` | object | 选填 | 直接提交的自定义词典(与 dictionary_id 二选一) |
| `custom_dictionary.terms` | string[] | 条件必填 | 词典术语列表(直接提交词典时必填) |
| `custom_dictionary.weight_boost` | number | 选填 | 命中加权增量,范围 0–0.5,默认 0.08 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/keywords/zh/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "地震动记录选取的新视角：大数据与机器学习",
  "chinese_scientific_abstract": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取的一致性，并为工程结构时程分析提供更可靠的输入。",
  "dictionary_id": "",
  "custom_dictionary": {},
  "custom_dictionary.terms": "",
  "custom_dictionary.weight_boost": 0.75
}
```

#### 响应字段（data）

```
- data: object
  - keywords: array<object>（2 项）
    - []: object
      - keyword: string，示例 "地震动记录"
      - term: string，示例 "地震动记录"
      - normalized_term: string，示例 "地震动记录"
      - confidence: number，示例 0.95
      - rank: number，示例 1
      - terminology_source: string，示例 "model"
      - source: string，示例 "model"
      - custom_dictionary_hit: boolean，示例 false
      - weight_change: number，示例 0
      - classification_mapping: null（本示例中为空）
  - document: object
    - title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
    - language: string，示例 "zh"
  - document_title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "keywords": [
      {
        "keyword": "地震动记录",
        "term": "地震动记录",
        "normalized_term": "地震动记录",
        "confidence": 0.95,
        "rank": 1,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": null
      },
      {
        "keyword": "结构抗震分析",
        "term": "结构抗震分析",
        "normalized_term": "结构抗震分析",
        "confidence": 0.9,
        "rank": 2,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": null
      }
    ],
    "document": {
      "title": "地震动记录选取的新视角：大数据与机器学习",
      "language": "zh"
    },
    "document_title": "地震动记录选取的新视角：大数据与机器学习"
  },
  "meta": {
    "request_id": "req_c92d00a49230470d9a52bf8437147ef8",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 9869,
    "created_at": "2026-10-27T22:03:53.877616+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_2a2dbf078316407c8fd7d2d19dca052b",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_5fbb9fdc1ed748208ed9471aff9e2cb5",
    "file_name": null
  }
}
```

### 7.2 批量文本

- **接口**：`POST /api/v1/keywords/zh/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `chinese_scientific_abstract` | object[] | 必填 | 中文科技文献摘要 |
| `chinese_scientific_abstract[].id` | string | 选填 | 批量文本条目编号 |
| `chinese_scientific_abstract[].title` | string | 选填 | 文献题名 |
| `chinese_scientific_abstract[].text` | string | 必填 | 用户输入的文本内容 |
| `dictionary_id` | string | 选填 | 用户词典编号(可选)。已保存词典的编号;词典术语在原文逐字出现时加权提升并归一到规范表达 |
| `custom_dictionary` | object | 选填 | 直接提交的自定义词典(与 dictionary_id 二选一) |
| `custom_dictionary.terms` | string[] | 条件必填 | 词典术语列表(直接提交词典时必填) |
| `custom_dictionary.weight_boost` | number | 选填 | 命中加权增量,范围 0–0.5,默认 0.08 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/keywords/zh/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "地震动记录选取的新视角：大数据与机器学习",
    "糖尿病肾病关键基因识别与潜在靶点分析",
    "融合多尺度特征的工业表面微小缺陷检测"
  ],
  "chinese_scientific_abstract": [
    {
      "id": "DEMO_1",
      "title": "地震动记录选取的新视角：大数据与机器学习",
      "text": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取的一致性，并为工程结构时程分析提供更可靠的输入。"
    },
    {
      "id": "DEMO_2",
      "title": "糖尿病肾病关键基因识别与潜在靶点分析",
      "text": "糖尿病肾病是糖尿病常见的微血管并发症。研究从 GEO 数据库获取相关转录组数据，利用加权基因共表达网络分析识别关键模块，并整合多种机器学习方法筛选特征基因。随后通过通路富集、免疫微环境关联和分子对接分析验证候选基因的诊断及治疗价值。结果表明，VWF 等基因具有较高的识别能力和潜在靶向价值，可为糖尿病肾病的精准诊疗提供参考。"
    },
    {
      "id": "DEMO_3",
      "title": "融合多尺度特征的工业表面微小缺陷检测",
      "text": "复杂工业表面中的裂纹、划痕和孔洞通常具有尺度差异大、边缘模糊及背景纹理干扰强等特点。本文提出融合多尺度特征增强和局部注意力的微小缺陷检测方法，通过跨层特征融合改善缺陷区域表征。多个公开数据集上的实验结果表明，该方法能够提高检测准确率与召回率，同时保持较低的推理延迟，适用于智能制造在线质量检测。"
    }
  ],
  "dictionary_id": "",
  "custom_dictionary": {},
  "custom_dictionary.terms": "",
  "custom_dictionary.weight_boost": 0.75
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_517ff6cb0de540ef86c39b1892172eb5"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_892ed24359144a72b14b27890edef597"
      - result: object
        - keywords: array<object>（2 项）
          - []: object
        - document: object
          - title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
          - language: string，示例 "zh"
        - document_title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_517ff6cb0de540ef86c39b1892172eb5",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_892ed24359144a72b14b27890edef597",
        "result": {
          "keywords": [
            {
              "keyword": "地震动记录",
              "term": "地震动记录",
              "normalized_term": "地震动记录",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": null
            },
            {
              "keyword": "结构抗震分析",
              "term": "结构抗震分析",
              "normalized_term": "结构抗震分析",
              "confidence": 0.9,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": null
            }
          ],
          "document": {
            "title": "地震动记录选取的新视角：大数据与机器学习",
            "language": "zh"
          },
          "document_title": "地震动记录选取的新视角：大数据与机器学习"
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_4aca9583b5904bbc913e51811d01ccb8",
        "result": {
          "keywords": [
            {
              "keyword": "糖尿病肾病",
              "term": "糖尿病肾病",
              "normalized_term": "糖尿病肾病",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": null
            },
            {
              "keyword": "加权基因共表达网络分析",
              "term": "加权基因共表达网络分析",
              "normalized_term": "加权基因共表达网络分析",
              "confidence": 0.85,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": null
            },
            "…（共 4 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "糖尿病肾病关键基因识别与潜在靶点分析",
            "language": "zh"
          },
          "document_title": "糖尿病肾病关键基因识别与潜在靶点分析"
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_4636268fc155448eae4a03a9af4eaf11",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 10915,
    "created_at": "2026-10-27T22:04:04.801477+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_517ff6cb0de540ef86c39b1892172eb5",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 7.3 单文件

- **接口**：`POST /api/v1/keywords/zh/file`
- **Content-Type**：multipart/form-data

> 上传中文文献 PDF/DOCX/TXT（英文文献会被 42201 语言门拒绝）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chinese_scientific_abstract` | file | 必填 | 中文科技文献文件（上传 PDF/DOCX/TXT） |
| `dictionary_id` | string | 选填 | 用户词典编号(可选)。已保存词典的编号;词典术语在原文逐字出现时加权提升并归一到规范表达 |
| `custom_dictionary` | object | 选填 | 直接提交的自定义词典(与 dictionary_id 二选一) |
| `custom_dictionary.terms` | string[] | 条件必填 | 词典术语列表(直接提交词典时必填) |
| `custom_dictionary.weight_boost` | number | 选填 | 命中加权增量,范围 0–0.5,默认 0.08 |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/keywords/zh/file' \
  -F 'chinese_scientific_abstract=@paper.pdf' \
  -F 'dictionary_id=' \
  -F 'custom_dictionary={}' \
  -F 'custom_dictionary.terms=' \
  -F 'custom_dictionary.weight_boost=0.75'
```

#### 响应字段（data）

```
- data: object
  - keywords: array<object>（4 项）
    - []: object
      - keyword: string，示例 "光伏电站运维管理"
      - term: string，示例 "光伏电站运维管理"
      - normalized_term: string，示例 "光伏电站运维管理"
      - confidence: number，示例 0.95
      - rank: number，示例 1
      - terminology_source: string，示例 "model"
      - source: string，示例 "model"
      - custom_dictionary_hit: boolean，示例 false
      - weight_change: number，示例 0
      - classification_mapping: null（本示例中为空）
  - document: object
    - title: string，示例 "zh1.pdf"
    - language: string，示例 "zh"
  - document_title: string，示例 "zh1.pdf"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "keywords": [
      {
        "keyword": "光伏电站运维管理",
        "term": "光伏电站运维管理",
        "normalized_term": "光伏电站运维管理",
        "confidence": 0.95,
        "rank": 1,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": null
      },
      {
        "keyword": "大数据分析",
        "term": "大数据分析",
        "normalized_term": "大数据分析",
        "confidence": 0.85,
        "rank": 2,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": null
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "document": {
      "title": "zh1.pdf",
      "language": "zh"
    },
    "document_title": "zh1.pdf"
  },
  "meta": {
    "request_id": "req_b60e18cf68a54c6182745b2682406453",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 17529,
    "created_at": "2026-10-27T22:36:25.087818+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_48e12cde3cf543119e126af879318e22",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_0da6b7d1fc1b4a4aafaa0cb07e619ebe",
    "file_name": "zh1.pdf"
  }
}
```

### 7.4 批量文件

- **接口**：`POST /api/v1/keywords/zh/files`
- **Content-Type**：multipart/form-data

> 上传中文文献 PDF/DOCX/TXT（英文文献会被 42201 语言门拒绝）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `chinese_scientific_abstract` | file[] | 必填 | 中文科技文献文件（上传 PDF/DOCX/TXT） |
| `dictionary_id` | string | 选填 | 用户词典编号(可选)。已保存词典的编号;词典术语在原文逐字出现时加权提升并归一到规范表达 |
| `custom_dictionary` | object | 选填 | 直接提交的自定义词典(与 dictionary_id 二选一) |
| `custom_dictionary.terms` | string[] | 条件必填 | 词典术语列表(直接提交词典时必填) |
| `custom_dictionary.weight_boost` | number | 选填 | 命中加权增量,范围 0–0.5,默认 0.08 |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/keywords/zh/files' \
  -F 'chinese_scientific_abstract=@paper_01.pdf' \
  -F 'chinese_scientific_abstract=@paper_02.docx' \
  -F 'chinese_scientific_abstract=@paper_03.pdf' \
  -F 'dictionary_id=' \
  -F 'custom_dictionary={}' \
  -F 'custom_dictionary.terms=' \
  -F 'custom_dictionary.weight_boost=0.75'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_0d730312e4fb4c508b3199e8d6308ced"
  - input_type: string，示例 "files"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "zh1.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_ae225bdf041f4a799ead3e6b50503944"
      - result: object
        - keywords: array<object>（4 项）
          - []: object
        - document: object
          - title: string，示例 "zh1.pdf"
          - language: string，示例 "zh"
        - document_title: string，示例 "zh1.pdf"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_0d730312e4fb4c508b3199e8d6308ced",
    "input_type": "files",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "zh1.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_ae225bdf041f4a799ead3e6b50503944",
        "result": {
          "keywords": [
            {
              "keyword": "光伏电站运维管理",
              "term": "光伏电站运维管理",
              "normalized_term": "光伏电站运维管理",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": null
            },
            {
              "keyword": "大数据分析",
              "term": "大数据分析",
              "normalized_term": "大数据分析",
              "confidence": 0.9,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": null
            },
            "…（共 4 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "zh1.pdf",
            "language": "zh"
          },
          "document_title": "zh1.pdf"
        }
      },
      {
        "index": 1,
        "file_name": "zh2.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_58cd1188128a425b91e62a224e90e2d5",
        "result": {
          "keywords": [
            {
              "keyword": "地震动记录",
              "term": "地震动记录",
              "normalized_term": "地震动记录",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": null
            },
            {
              "keyword": "聚类分析",
              "term": "聚类分析",
              "normalized_term": "聚类分析",
              "confidence": 0.9,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": null
            },
            "…（共 4 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "zh2.pdf",
            "language": "en"
          },
          "document_title": "zh2.pdf"
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_b8ea2b2c03a74b0eae6b58cb296975d8",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 32099,
    "created_at": "2026-10-27T22:36:57.216163+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_0d730312e4fb4c508b3199e8d6308ced",
    "input_type": "files",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

---

## 8. 英文科技文献关键词识别

**工具ID**：`en-keyword`

从英文科研文献摘要中抽取专业关键词、缩写和主题短语。系统自动识别研究领域，并在算法内部自适应调用英文领域术语资源和标准术语映射规则，完成缩写识别、术语规范化与主题一致性校验；用户无需输入领域术语库或分类标准映射表。支持单文本、批量文本、单文件和批量文件。

**功能特点**：英文摘要定位，缩写识别，术语规范化映射

**适用场景**：英文文献标引与术语规范

### 8.1 单文本

- **接口**：`POST /api/v1/keywords/en/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `english_scientific_abstract` | string | 必填 | 英文科研文献摘要 |
| `domain_terminology_library` | file (.json) | 选填 | 可选上传资源：领域术语库（.json） |
| `classification_standard_mapping_table` | file (.json) | 选填 | 可选上传资源：分类标准映射表（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/keywords/en/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
  "english_scientific_abstract": "Reinforcement learning can improve the reasoning performance of vision-language models, but it may also reduce the diversity of their reasoning paths. This study compares reinforcement-learning models with their base counterparts and finds that the former reason more deeply along a narrow set of strategies, while the latter explore broader alternatives. The proposed Multi-Group Policy Optimization method encourages diverse solutions during training. Experiments on established benchmarks show improved reasoning diversity and a better balance between accuracy and scalability."
}
```

#### 响应字段（data）

```
- data: object
  - keywords: array<object>（4 项）
    - []: object
      - keyword: string，示例 "vision-language models"
      - term: string，示例 "vision-language models"
      - normalized_term: string，示例 "vision-language models"
      - confidence: number，示例 0.95
      - rank: number，示例 1
      - terminology_source: string，示例 "model"
      - source: string，示例 "model"
      - custom_dictionary_hit: boolean，示例 false
      - weight_change: number，示例 0
      - classification_mapping: object
        - system: string，示例 "CLC"
        - code: string，示例 "TP18"
        - label: string，示例 "人工智能理论"
        - classification_path: array<string>（4 项）
        - confidence: number，示例 0.9
        - mapping_engine: string，示例 "clc_retriever+batch_rerank"
        - dense_score: number，示例 0.5638
        - scene: string，示例 "视觉语言模型的多模态推理性能研究"
  - document: object
    - title: string，示例 "Divergent Thinking Through Reinforcement…"
    - language: string，示例 "en"
  - document_title: string，示例 "Divergent Thinking Through Reinforcement…"
  - keywords_or_topic_phrases: array<object>（4 项）
    - []: object
      - keyword: string，示例 "vision-language models"
      - term: string，示例 "vision-language models"
      - normalized_term: string，示例 "vision-language models"
      - confidence: number，示例 0.95
      - rank: number，示例 1
      - terminology_source: string，示例 "model"
      - source: string，示例 "model"
      - custom_dictionary_hit: boolean，示例 false
      - weight_change: number，示例 0
      - classification_mapping: object
        - system: string，示例 "CLC"
        - code: string，示例 "TP18"
        - label: string，示例 "人工智能理论"
        - classification_path: array<string>（4 项）
        - confidence: number，示例 0.9
        - mapping_engine: string，示例 "clc_retriever+batch_rerank"
        - dense_score: number，示例 0.5638
        - scene: string，示例 "视觉语言模型的多模态推理性能研究"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "keywords": [
      {
        "keyword": "vision-language models",
        "term": "vision-language models",
        "normalized_term": "vision-language models",
        "confidence": 0.95,
        "rank": 1,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": {
          "system": "CLC",
          "code": "TP18",
          "label": "人工智能理论",
          "classification_path": [
            "工业技术",
            "自动化技术、计算机技术",
            "…（共 4 项，示例保留前 2 项）"
          ],
          "confidence": 0.9,
          "mapping_engine": "clc_retriever+batch_rerank",
          "dense_score": 0.5638,
          "scene": "视觉语言模型的多模态推理性能研究"
        }
      },
      {
        "keyword": "reinforcement learning",
        "term": "reinforcement learning",
        "normalized_term": "reinforcement learning",
        "confidence": 0.9,
        "rank": 2,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": {
          "system": "CLC",
          "code": "TP18",
          "label": "人工智能理论",
          "classification_path": [
            "工业技术",
            "自动化技术、计算机技术",
            "…（共 4 项，示例保留前 2 项）"
          ],
          "confidence": 0.85,
          "mapping_engine": "clc_retriever+batch_rerank",
          "dense_score": 0.6213,
          "scene": "用强化学习训练提升模型推理能力"
        }
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "document": {
      "title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
      "language": "en"
    },
    "document_title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
    "keywords_or_topic_phrases": [
      {
        "keyword": "vision-language models",
        "term": "vision-language models",
        "normalized_term": "vision-language models",
        "confidence": 0.95,
        "rank": 1,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": {
          "system": "CLC",
          "code": "TP18",
          "label": "人工智能理论",
          "classification_path": [
            "工业技术",
            "自动化技术、计算机技术",
            "…（共 4 项，示例保留前 2 项）"
          ],
          "confidence": 0.9,
          "mapping_engine": "clc_retriever+batch_rerank",
          "dense_score": 0.5638,
          "scene": "视觉语言模型的多模态推理性能研究"
        }
      },
      {
        "keyword": "reinforcement learning",
        "term": "reinforcement learning",
        "normalized_term": "reinforcement learning",
        "confidence": 0.9,
        "rank": 2,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": {
          "system": "CLC",
          "code": "TP18",
          "label": "人工智能理论",
          "classification_path": [
            "工业技术",
            "自动化技术、计算机技术",
            "…（共 4 项，示例保留前 2 项）"
          ],
          "confidence": 0.85,
          "mapping_engine": "clc_retriever+batch_rerank",
          "dense_score": 0.6213,
          "scene": "用强化学习训练提升模型推理能力"
        }
      },
      "…（共 4 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_df0f471e6e704c7088b7e3a321548815",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 15163,
    "created_at": "2026-10-27T22:04:20.009728+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_2fe15ffc030c49e3b1b2c9697c736a75",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_25ed16f2a8cf4af0b901dde5ff1ecae2",
    "file_name": null
  }
}
```

### 8.2 批量文本

- **接口**：`POST /api/v1/keywords/en/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `english_scientific_abstract` | object[] | 必填 | 英文科研文献摘要 |
| `english_scientific_abstract[].id` | string | 选填 | 批量文本条目编号 |
| `english_scientific_abstract[].title` | string | 选填 | 文献题名 |
| `english_scientific_abstract[].text` | string | 必填 | 用户输入的文本内容 |
| `domain_terminology_library` | file (.json) | 选填 | 可选上传资源：领域术语库（.json） |
| `classification_standard_mapping_table` | file (.json) | 选填 | 可选上传资源：分类标准映射表（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/keywords/en/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
    "Timestep-Aware Block Masking for Efficient Diffusion Inference",
    "Adaptive Temporal Graph Learning for Multivariate Anomaly Detection"
  ],
  "english_scientific_abstract": [
    {
      "id": "DEMO_1",
      "title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
      "text": "Reinforcement learning can improve the reasoning performance of vision-language models, but it may also reduce the diversity of their reasoning paths. This study compares reinforcement-learning models with their base counterparts and finds that the former reason more deeply along a narrow set of strategies, while the latter explore broader alternatives. The proposed Multi-Group Policy Optimization method encourages diverse solutions during training. Experiments on established benchmarks show improved reasoning diversity and a better balance between accuracy and scalability."
    },
    {
      "id": "DEMO_2",
      "title": "Timestep-Aware Block Masking for Efficient Diffusion Inference",
      "text": "Diffusion models produce high-quality samples but require repeated denoising and therefore incur substantial inference cost. This study proposes timestep-aware block masking, which learns which network blocks should be executed or reused at each denoising step. Independent optimization and knowledge-guided mask refinement reduce memory consumption while preserving generation quality. Experiments across several diffusion architectures demonstrate consistent acceleration with limited quality loss."
    },
    {
      "id": "DEMO_3",
      "title": "Adaptive Temporal Graph Learning for Multivariate Anomaly Detection",
      "text": "Multivariate time-series anomaly detection is difficult because sensor noise, missing observations and operating-condition shifts can hide weak fault patterns. This study proposes a temporal graph framework that combines adaptive dependency learning, multi-scale temporal encoding and consistency regularization. Experiments on public industrial datasets show lower false-alarm rates and improved detection performance under heterogeneous operating conditions."
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_42b97e7224f14aaa92230ceee9984565"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_e584bdbbd9d542f7b6f88bda0276e902"
      - result: object
        - keywords: array<object>（5 项）
          - []: object
        - document: object
          - title: string，示例 "Divergent Thinking Through Reinforcement…"
          - language: string，示例 "en"
        - document_title: string，示例 "Divergent Thinking Through Reinforcement…"
        - keywords_or_topic_phrases: array<object>（5 项）
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_42b97e7224f14aaa92230ceee9984565",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_e584bdbbd9d542f7b6f88bda0276e902",
        "result": {
          "keywords": [
            {
              "keyword": "reinforcement learning",
              "term": "reinforcement learning",
              "normalized_term": "reinforcement learning",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.8,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.6213,
                "scene": "用强化学习方法提升视觉-语言模型推理性能与推理路径多样性的训练技术"
              }
            },
            {
              "keyword": "vision-language models",
              "term": "vision-language models",
              "normalized_term": "vision-language models",
              "confidence": 0.95,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP391.413",
                "label": "图像识别",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 6 项，示例保留前 2 项）"
                ],
                "confidence": 0.7,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5643,
                "scene": "视觉-语言模型在强化学习下的推理性能研究，多模态人工智能推理任务"
              }
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
            "language": "en"
          },
          "document_title": "Divergent Thinking Through Reinforcement Learning in Vision-Language Models",
          "keywords_or_topic_phrases": [
            {
              "keyword": "reinforcement learning",
              "term": "reinforcement learning",
              "normalized_term": "reinforcement learning",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.8,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.6213,
                "scene": "用强化学习方法提升视觉-语言模型推理性能与推理路径多样性的训练技术"
              }
            },
            {
              "keyword": "vision-language models",
              "term": "vision-language models",
              "normalized_term": "vision-language models",
              "confidence": 0.95,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP391.413",
                "label": "图像识别",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 6 项，示例保留前 2 项）"
                ],
                "confidence": 0.7,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5643,
                "scene": "视觉-语言模型在强化学习下的推理性能研究，多模态人工智能推理任务"
              }
            },
            "…（共 5 项，示例保留前 2 项）"
          ]
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_641b953f901a446091c269eb5281a125",
        "result": {
          "keywords": [
            {
              "keyword": "diffusion models",
              "term": "diffusion models",
              "normalized_term": "diffusion models",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.9,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.588,
                "scene": "扩散生成模型的高质量样本生成与推理加速研究"
              }
            },
            {
              "keyword": "timestep-aware block masking",
              "term": "timestep-aware block masking",
              "normalized_term": "timestep-aware block masking",
              "confidence": 0.95,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.85,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5428,
                "scene": "扩散模型按去噪时间步选择性执行/复用网络模块的加速方法"
              }
            },
            "…（共 3 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "Timestep-Aware Block Masking for Efficient Diffusion Inference",
            "language": "en"
          },
          "document_title": "Timestep-Aware Block Masking for Efficient Diffusion Inference",
          "keywords_or_topic_phrases": [
            {
              "keyword": "diffusion models",
              "term": "diffusion models",
              "normalized_term": "diffusion models",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.9,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.588,
                "scene": "扩散生成模型的高质量样本生成与推理加速研究"
              }
            },
            {
              "keyword": "timestep-aware block masking",
              "term": "timestep-aware block masking",
              "normalized_term": "timestep-aware block masking",
              "confidence": 0.95,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.85,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5428,
                "scene": "扩散模型按去噪时间步选择性执行/复用网络模块的加速方法"
              }
            },
            "…（共 3 项，示例保留前 2 项）"
          ]
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_dd425beead5a498984918d3250129d7e",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 19159,
    "created_at": "2026-10-27T22:04:39.183692+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_42b97e7224f14aaa92230ceee9984565",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 8.3 单文件

- **接口**：`POST /api/v1/keywords/en/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `english_scientific_abstract` | file | 必填 | 英文科研文献文件（上传 PDF/DOCX/TXT） |
| `domain_terminology_library` | file (.json) | 选填 | 可选上传资源：领域术语库（.json） |
| `classification_standard_mapping_table` | file (.json) | 选填 | 可选上传资源：分类标准映射表（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/keywords/en/file' \
  -F 'english_scientific_abstract=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - keywords: array<object>（2 项）
    - []: object
      - keyword: string，示例 "synthetic data"
      - term: string，示例 "synthetic data"
      - normalized_term: string，示例 "synthetic data"
      - confidence: number，示例 0.95
      - rank: number，示例 1
      - terminology_source: string，示例 "model"
      - source: string，示例 "model"
      - custom_dictionary_hit: boolean，示例 false
      - weight_change: number，示例 0
      - classification_mapping: object
        - system: string，示例 "CLC"
        - code: string，示例 "TP18"
        - label: string，示例 "人工智能理论"
        - classification_path: array<string>（4 项）
        - confidence: number，示例 0.8
        - mapping_engine: string，示例 "clc_retriever+batch_rerank"
        - dense_score: number，示例 0.5984
        - scene: string，示例 "LLM生成合成数据污染真实训练数据的机器学习理论研究"
  - document: object
    - title: string，示例 "7.pdf"
    - language: string，示例 "en"
  - document_title: string，示例 "7.pdf"
  - keywords_or_topic_phrases: array<object>（2 项）
    - []: object
      - keyword: string，示例 "synthetic data"
      - term: string，示例 "synthetic data"
      - normalized_term: string，示例 "synthetic data"
      - confidence: number，示例 0.95
      - rank: number，示例 1
      - terminology_source: string，示例 "model"
      - source: string，示例 "model"
      - custom_dictionary_hit: boolean，示例 false
      - weight_change: number，示例 0
      - classification_mapping: object
        - system: string，示例 "CLC"
        - code: string，示例 "TP18"
        - label: string，示例 "人工智能理论"
        - classification_path: array<string>（4 项）
        - confidence: number，示例 0.8
        - mapping_engine: string，示例 "clc_retriever+batch_rerank"
        - dense_score: number，示例 0.5984
        - scene: string，示例 "LLM生成合成数据污染真实训练数据的机器学习理论研究"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "keywords": [
      {
        "keyword": "synthetic data",
        "term": "synthetic data",
        "normalized_term": "synthetic data",
        "confidence": 0.95,
        "rank": 1,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": {
          "system": "CLC",
          "code": "TP18",
          "label": "人工智能理论",
          "classification_path": [
            "工业技术",
            "自动化技术、计算机技术",
            "…（共 4 项，示例保留前 2 项）"
          ],
          "confidence": 0.8,
          "mapping_engine": "clc_retriever+batch_rerank",
          "dense_score": 0.5984,
          "scene": "LLM生成合成数据污染真实训练数据的机器学习理论研究"
        }
      },
      {
        "keyword": "empirical risk minimization",
        "term": "empirical risk minimization",
        "normalized_term": "empirical risk minimization",
        "confidence": 0.9,
        "rank": 2,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": {
          "system": "CLC",
          "code": "TP181",
          "label": "自动推理、机器学习",
          "classification_path": [
            "工业技术",
            "自动化技术、计算机技术",
            "…（共 5 项，示例保留前 2 项）"
          ],
          "confidence": 0.9,
          "mapping_engine": "clc_retriever+batch_rerank",
          "dense_score": 0.5757,
          "scene": "在含合成数据污染的场景下分析ERM学习算法收敛性的理论研究"
        }
      }
    ],
    "document": {
      "title": "7.pdf",
      "language": "en"
    },
    "document_title": "7.pdf",
    "keywords_or_topic_phrases": [
      {
        "keyword": "synthetic data",
        "term": "synthetic data",
        "normalized_term": "synthetic data",
        "confidence": 0.95,
        "rank": 1,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": {
          "system": "CLC",
          "code": "TP18",
          "label": "人工智能理论",
          "classification_path": [
            "工业技术",
            "自动化技术、计算机技术",
            "…（共 4 项，示例保留前 2 项）"
          ],
          "confidence": 0.8,
          "mapping_engine": "clc_retriever+batch_rerank",
          "dense_score": 0.5984,
          "scene": "LLM生成合成数据污染真实训练数据的机器学习理论研究"
        }
      },
      {
        "keyword": "empirical risk minimization",
        "term": "empirical risk minimization",
        "normalized_term": "empirical risk minimization",
        "confidence": 0.9,
        "rank": 2,
        "terminology_source": "model",
        "source": "model",
        "custom_dictionary_hit": false,
        "weight_change": 0,
        "classification_mapping": {
          "system": "CLC",
          "code": "TP181",
          "label": "自动推理、机器学习",
          "classification_path": [
            "工业技术",
            "自动化技术、计算机技术",
            "…（共 5 项，示例保留前 2 项）"
          ],
          "confidence": 0.9,
          "mapping_engine": "clc_retriever+batch_rerank",
          "dense_score": 0.5757,
          "scene": "在含合成数据污染的场景下分析ERM学习算法收敛性的理论研究"
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_86e59dbd91bc45748ea33fd1f1e5cd49",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 17165,
    "created_at": "2026-10-27T22:20:43.105666+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_2c0154b054f44955ba2d0f6d54c1b1e7",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_fd0ae319290643d3ba8fd3d131ccaa6d",
    "file_name": "7.pdf"
  }
}
```

### 8.4 批量文件

- **接口**：`POST /api/v1/keywords/en/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `english_scientific_abstract` | file[] | 必填 | 英文科研文献文件（上传 PDF/DOCX/TXT） |
| `domain_terminology_library` | file (.json) | 选填 | 可选上传资源：领域术语库（.json） |
| `classification_standard_mapping_table` | file (.json) | 选填 | 可选上传资源：分类标准映射表（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/keywords/en/files' \
  -F 'english_scientific_abstract=@paper_01.pdf' \
  -F 'english_scientific_abstract=@paper_02.docx' \
  -F 'english_scientific_abstract=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_4517cc7522b1420db1c7387871377ac8"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_db5d757cae8e460380f3b078806db241"
      - result: object
        - keywords: array<object>（2 项）
          - []: object
        - document: object
          - title: string，示例 "7.pdf"
          - language: string，示例 "en"
        - document_title: string，示例 "7.pdf"
        - keywords_or_topic_phrases: array<object>（2 项）
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_4517cc7522b1420db1c7387871377ac8",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_db5d757cae8e460380f3b078806db241",
        "result": {
          "keywords": [
            {
              "keyword": "synthetic data",
              "term": "synthetic data",
              "normalized_term": "synthetic data",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.85,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5984,
                "scene": "论文核心研究对象：用LLM生成的合成数据训练模型的理论局限性"
              }
            },
            {
              "keyword": "empirical risk minimization",
              "term": "empirical risk minimization",
              "normalized_term": "empirical risk minimization",
              "confidence": 0.9,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP181",
                "label": "自动推理、机器学习",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 5 项，示例保留前 2 项）"
                ],
                "confidence": 0.9,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5757,
                "scene": "作为学习算法在合成数据污染场景下收敛性分析的对象"
              }
            }
          ],
          "document": {
            "title": "7.pdf",
            "language": "en"
          },
          "document_title": "7.pdf",
          "keywords_or_topic_phrases": [
            {
              "keyword": "synthetic data",
              "term": "synthetic data",
              "normalized_term": "synthetic data",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.85,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5984,
                "scene": "论文核心研究对象：用LLM生成的合成数据训练模型的理论局限性"
              }
            },
            {
              "keyword": "empirical risk minimization",
              "term": "empirical risk minimization",
              "normalized_term": "empirical risk minimization",
              "confidence": 0.9,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP181",
                "label": "自动推理、机器学习",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 5 项，示例保留前 2 项）"
                ],
                "confidence": 0.9,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5757,
                "scene": "作为学习算法在合成数据污染场景下收敛性分析的对象"
              }
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_e3e97fd4d6104207aecde4cd32df03d4",
        "result": {
          "keywords": [
            {
              "keyword": "synthetic data",
              "term": "synthetic data",
              "normalized_term": "synthetic data",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.85,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5984,
                "scene": "LLM生成合成数据对模型训练与学习算法收敛性的影响研究"
              }
            },
            {
              "keyword": "empirical risk minimization",
              "term": "empirical risk minimization",
              "normalized_term": "empirical risk minimization",
              "confidence": 0.9,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP181",
                "label": "自动推理、机器学习",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 5 项，示例保留前 2 项）"
                ],
                "confidence": 0.9,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5757,
                "scene": "在合成数据污染场景下分析ERM算法能否收敛到真实概念的理论研究"
              }
            },
            "…（共 4 项，示例保留前 2 项）"
          ],
          "document": {
            "title": "35.pdf",
            "language": "en"
          },
          "document_title": "35.pdf",
          "keywords_or_topic_phrases": [
            {
              "keyword": "synthetic data",
              "term": "synthetic data",
              "normalized_term": "synthetic data",
              "confidence": 0.95,
              "rank": 1,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP18",
                "label": "人工智能理论",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "confidence": 0.85,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5984,
                "scene": "LLM生成合成数据对模型训练与学习算法收敛性的影响研究"
              }
            },
            {
              "keyword": "empirical risk minimization",
              "term": "empirical risk minimization",
              "normalized_term": "empirical risk minimization",
              "confidence": 0.9,
              "rank": 2,
              "terminology_source": "model",
              "source": "model",
              "custom_dictionary_hit": false,
              "weight_change": 0,
              "classification_mapping": {
                "system": "CLC",
                "code": "TP181",
                "label": "自动推理、机器学习",
                "classification_path": [
                  "工业技术",
                  "自动化技术、计算机技术",
                  "…（共 5 项，示例保留前 2 项）"
                ],
                "confidence": 0.9,
                "mapping_engine": "clc_retriever+batch_rerank",
                "dense_score": 0.5757,
                "scene": "在合成数据污染场景下分析ERM算法能否收敛到真实概念的理论研究"
              }
            },
            "…（共 4 项，示例保留前 2 项）"
          ]
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_bf9050fa147a49d78861996308feba56",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 34902,
    "created_at": "2026-10-27T22:21:18.023383+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_4517cc7522b1420db1c7387871377ac8",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 9. 研究问题识别工具

**工具ID**：`rq-detect`

从科技文献文件中识别研究空白、技术难点、核心任务和待解决问题，提取研究问题句与问题短语，并完成问题归并、主次关系组织、类型判定和统计分析。支持单文件和批量文件。

**功能特点**：显式与隐式问题识别，主子问题，章节溯源

**适用场景**：论文问题提炼与批量分析

### 9.1 单文本

- **接口**：`POST /api/v1/research-question/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `scientific_document_fragment` | string | 必填 | 科技文献文本片段或全文 |
| `text_format_requirement` | string | 选填 | 文本格式声明,影响溯源方式。枚举:"自动识别"(默认)、"纯文本"(跳过章节解析)、"章节结构文本"(启用标题路径溯源)、"JSON 结构文本"(按章节结构精确归属) |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/research-question/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "地震动记录选取的新视角：大数据与机器学习",
  "scientific_document_fragment": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取的一致性，并为工程结构时程分析提供更可靠的输入。",
  "text_format_requirement": "章节结构文本"
}
```

#### 响应字段（data）

```
- data: object
  - document: object
    - title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
  - document_title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
  - research_question_sentences: array<object>
    - []: object
      - sentence: string，示例 "本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，…"
      - text: string，示例 "本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，…"
      - id: string，示例 "RQS1"
      - expression_type: string，示例 "implicit"
      - confidence: number，示例 0.75
  - research_question_phrases: array<object>
    - []: object
      - id: string，示例 "RQP1"
      - text: string，示例 "形成自适应地震动记录推荐方法"
      - sentence_id: string，示例 "RQS1"
      - normalized_question: string，示例 "如何利用模糊聚类与主成分分析构建自适应的地震动记录推荐方法？"
      - confidence: number，示例 0.75
  - structured_research_questions: array<object>
    - []: object
      - research_question_id: string，示例 "RQ1"
      - question: string，示例 "如何利用模糊聚类与主成分分析构建自适应的地震动记录推荐方法？"
      - normalized_question: string，示例 "如何利用模糊聚类与主成分分析构建自适应的地震动记录推荐方法？"
      - question_type: string，示例 "method"
      - research_object: string，示例 "地震动记录"
      - constraints: array<string>（3 项）
      - role: string，示例 "main"
      - parent_id: string，示例 ""
      - confidence: number，示例 0.75
  - statistics: object
    - sentence_count: number，示例 1
    - phrase_count: number，示例 1
    - expression_types: array<object>（2 项）
      - []: object
        - type: string，示例 "显式（explicit）"
        - count: number，示例 0
        - ratio: number，示例 0
  - research_question_statistics: object
    - sentence_count: number，示例 1
    - phrase_count: number，示例 1
    - expression_types: array<object>（2 项）
      - []: object
        - type: string，示例 "显式（explicit）"
        - count: number，示例 0
        - ratio: number，示例 0
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document": {
      "title": "地震动记录选取的新视角：大数据与机器学习"
    },
    "document_title": "地震动记录选取的新视角：大数据与机器学习",
    "research_question_sentences": [
      {
        "sentence": "本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。",
        "text": "本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。",
        "id": "RQS1",
        "expression_type": "implicit",
        "confidence": 0.75
      }
    ],
    "research_question_phrases": [
      {
        "id": "RQP1",
        "text": "形成自适应地震动记录推荐方法",
        "sentence_id": "RQS1",
        "normalized_question": "如何利用模糊聚类与主成分分析构建自适应的地震动记录推荐方法？",
        "confidence": 0.75
      }
    ],
    "structured_research_questions": [
      {
        "research_question_id": "RQ1",
        "question": "如何利用模糊聚类与主成分分析构建自适应的地震动记录推荐方法？",
        "normalized_question": "如何利用模糊聚类与主成分分析构建自适应的地震动记录推荐方法？",
        "question_type": "method",
        "research_object": "地震动记录",
        "constraints": [
          "PEER 数据库",
          "震级与距离特征",
          "…（共 3 项，示例保留前 2 项）"
        ],
        "role": "main",
        "parent_id": "",
        "confidence": 0.75
      }
    ],
    "statistics": {
      "sentence_count": 1,
      "phrase_count": 1,
      "expression_types": [
        {
          "type": "显式（explicit）",
          "count": 0,
          "ratio": 0
        },
        {
          "type": "隐式（implicit）",
          "count": 1,
          "ratio": 1
        }
      ]
    },
    "research_question_statistics": {
      "sentence_count": 1,
      "phrase_count": 1,
      "expression_types": [
        {
          "type": "显式（explicit）",
          "count": 0,
          "ratio": 0
        },
        {
          "type": "隐式（implicit）",
          "count": 1,
          "ratio": 1
        }
      ]
    }
  },
  "meta": {
    "request_id": "req_b973d55f6ada49c2802fd629798341f1",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 4996,
    "created_at": "2026-10-27T22:04:44.192377+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_a4e8a722e27244b68b3ec65c9ad55a5e",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_69113bcdff154092a71f9d737d76c652",
    "file_name": null
  }
}
```

### 9.2 批量文本

- **接口**：`POST /api/v1/research-question/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `scientific_document_fragment` | object[] | 必填 | 科技文献文本片段或全文 |
| `scientific_document_fragment[].id` | string | 选填 | 批量文本条目编号 |
| `scientific_document_fragment[].title` | string | 选填 | 文献题名 |
| `scientific_document_fragment[].text` | string | 必填 | 用户输入的文本内容 |
| `text_format_requirement` | string | 选填 | 文本格式声明,影响溯源方式。枚举:"自动识别"(默认)、"纯文本"(跳过章节解析)、"章节结构文本"(启用标题路径溯源)、"JSON 结构文本"(按章节结构精确归属) |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/research-question/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "地震动记录选取的新视角：大数据与机器学习",
    "糖尿病肾病关键基因识别与潜在靶点分析",
    "融合多尺度特征的工业表面微小缺陷检测"
  ],
  "scientific_document_fragment": [
    {
      "id": "DEMO_1",
      "title": "地震动记录选取的新视角：大数据与机器学习",
      "text": "合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取的一致性，并为工程结构时程分析提供更可靠的输入。"
    },
    {
      "id": "DEMO_2",
      "title": "糖尿病肾病关键基因识别与潜在靶点分析",
      "text": "糖尿病肾病是糖尿病常见的微血管并发症。研究从 GEO 数据库获取相关转录组数据，利用加权基因共表达网络分析识别关键模块，并整合多种机器学习方法筛选特征基因。随后通过通路富集、免疫微环境关联和分子对接分析验证候选基因的诊断及治疗价值。结果表明，VWF 等基因具有较高的识别能力和潜在靶向价值，可为糖尿病肾病的精准诊疗提供参考。"
    },
    {
      "id": "DEMO_3",
      "title": "融合多尺度特征的工业表面微小缺陷检测",
      "text": "复杂工业表面中的裂纹、划痕和孔洞通常具有尺度差异大、边缘模糊及背景纹理干扰强等特点。本文提出融合多尺度特征增强和局部注意力的微小缺陷检测方法，通过跨层特征融合改善缺陷区域表征。多个公开数据集上的实验结果表明，该方法能够提高检测准确率与召回率，同时保持较低的推理延迟，适用于智能制造在线质量检测。"
    }
  ],
  "text_format_requirement": "章节结构文本"
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_917dd70dbeb646ca9a43407f06be84ef"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_c337fbe1b13b47ac8e22582fb4b38e44"
      - result: object
        - document: object
          - title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
        - document_title: string，示例 "地震动记录选取的新视角：大数据与机器学习"
        - research_question_sentences: array<object>
          - []: object
        - research_question_phrases: array<object>
          - []: object
        - structured_research_questions: array<object>
          - []: object
        - statistics: object
          - sentence_count: number，示例 1
          - phrase_count: number，示例 1
          - expression_types: array<object>（2 项）
        - research_question_statistics: object
          - sentence_count: number，示例 1
          - phrase_count: number，示例 1
          - expression_types: array<object>（2 项）
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_917dd70dbeb646ca9a43407f06be84ef",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_c337fbe1b13b47ac8e22582fb4b38e44",
        "result": {
          "document": {
            "title": "地震动记录选取的新视角：大数据与机器学习"
          },
          "document_title": "地震动记录选取的新视角：大数据与机器学习",
          "research_question_sentences": [
            {
              "sentence": "本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。",
              "text": "本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。",
              "id": "RQS1",
              "expression_type": "implicit",
              "confidence": 0.7
            }
          ],
          "research_question_phrases": [
            {
              "id": "RQP1",
              "text": "形成自适应地震动记录推荐方法",
              "sentence_id": "RQS1",
              "normalized_question": "如何构建一种自适应的地震动记录推荐方法，以客观刻画记录间的频谱差异并提高选取一致性？",
              "confidence": 0.7
            }
          ],
          "structured_research_questions": [
            {
              "research_question_id": "RQ1",
              "question": "如何构建一种自适应的地震动记录推荐方法，以客观刻画记录间的频谱差异并提高选取一致性？",
              "normalized_question": "如何构建一种自适应的地震动记录推荐方法，以客观刻画记录间的频谱差异并提高选取一致性？",
              "question_type": "method",
              "research_object": "地震动记录",
              "constraints": [
                "PEER 数据库",
                "震级、距离与场地类别特征"
              ],
              "role": "main",
              "parent_id": "",
              "confidence": 0.7
            }
          ],
          "statistics": {
            "sentence_count": 1,
            "phrase_count": 1,
            "expression_types": [
              {
                "type": "显式（explicit）",
                "count": 0,
                "ratio": 0
              },
              {
                "type": "隐式（implicit）",
                "count": 1,
                "ratio": 1
              }
            ]
          },
          "research_question_statistics": {
            "sentence_count": 1,
            "phrase_count": 1,
            "expression_types": [
              {
                "type": "显式（explicit）",
                "count": 0,
                "ratio": 0
              },
              {
                "type": "隐式（implicit）",
                "count": 1,
                "ratio": 1
              }
            ]
          }
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_3823a7d6dfdc448a98d404dd56dc84ac",
        "result": {
          "document": {
            "title": "糖尿病肾病关键基因识别与潜在靶点分析"
          },
          "document_title": "糖尿病肾病关键基因识别与潜在靶点分析",
          "research_question_sentences": [
            {
              "sentence": "随后通过通路富集、免疫微环境关联和分子对接分析验证候选基因的诊断及治疗价值。",
              "text": "随后通过通路富集、免疫微环境关联和分子对接分析验证候选基因的诊断及治疗价值。",
              "id": "RQS1",
              "expression_type": "implicit",
              "confidence": 0.6
            }
          ],
          "research_question_phrases": [
            {
              "id": "RQP1",
              "text": "验证候选基因的诊断及治疗价值",
              "sentence_id": "RQS1",
              "normalized_question": "筛选出的候选基因在糖尿病肾病中是否具有诊断价值和潜在治疗（靶向）价值？",
              "confidence": 0.6
            }
          ],
          "structured_research_questions": [
            {
              "research_question_id": "RQ1",
              "question": "筛选出的候选基因在糖尿病肾病中是否具有诊断价值和潜在治疗（靶向）价值？",
              "normalized_question": "筛选出的候选基因在糖尿病肾病中是否具有诊断价值和潜在治疗（靶向）价值？",
              "question_type": "validation",
              "research_object": "候选基因",
              "constraints": [
                "糖尿病肾病",
                "转录组数据与机器学习筛选背景"
              ],
              "role": "main",
              "parent_id": "",
              "confidence": 0.6
            }
          ],
          "statistics": {
            "sentence_count": 1,
            "phrase_count": 1,
            "expression_types": [
              {
                "type": "显式（explicit）",
                "count": 0,
                "ratio": 0
              },
              {
                "type": "隐式（implicit）",
                "count": 1,
                "ratio": 1
              }
            ]
          },
          "research_question_statistics": {
            "sentence_count": 1,
            "phrase_count": 1,
            "expression_types": [
              {
                "type": "显式（explicit）",
                "count": 0,
                "ratio": 0
              },
              {
                "type": "隐式（implicit）",
                "count": 1,
                "ratio": 1
              }
            ]
          }
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_5a96b2f61b3f47af95f0615249c31084",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 8184,
    "created_at": "2026-10-27T22:04:52.388157+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_917dd70dbeb646ca9a43407f06be84ef",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 9.3 单文件

- **接口**：`POST /api/v1/research-question/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scientific_document_fragment` | file | 必填 | 科技文献片段或全文文件（上传 PDF/DOCX/TXT） |
| `text_format_requirement` | string | 选填 | 文本格式声明,影响溯源方式。枚举:"自动识别"(默认)、"纯文本"(跳过章节解析)、"章节结构文本"(启用标题路径溯源)、"JSON 结构文本"(按章节结构精确归属) |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/research-question/file' \
  -F 'scientific_document_fragment=@paper.pdf' \
  -F 'text_format_requirement=章节结构文本'
```

#### 响应字段（data）

```
- data: object
  - document: object
    - title: string，示例 "7.pdf"
  - document_title: string，示例 "7.pdf"
  - research_question_sentences: array<object>（3 项）
    - []: object
      - sentence: string，示例 "We study the possibilities and limitatio…"
      - text: string，示例 "We study the possibilities and limitatio…"
      - id: string，示例 "RQS1"
      - expression_type: string，示例 "implicit"
      - confidence: number，示例 0.9
  - research_question_phrases: array<object>（3 项）
    - []: object
      - id: string，示例 "RQP1"
      - text: string，示例 "the possibilities and limitations of ERM…"
      - sentence_id: string，示例 "RQS1"
      - normalized_question: string，示例 "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？"
      - confidence: number，示例 0.9
  - structured_research_questions: array<object>（3 项）
    - []: object
      - research_question_id: string，示例 "RQ1"
      - question: string，示例 "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？"
      - normalized_question: string，示例 "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？"
      - question_type: string，示例 "mechanism"
      - research_object: string，示例 "ERM"
      - constraints: array<string>（2 项）
      - role: string，示例 "main"
      - parent_id: string，示例 ""
      - confidence: number，示例 0.9
  - statistics: object
    - sentence_count: number，示例 3
    - phrase_count: number，示例 3
    - expression_types: array<object>（2 项）
      - []: object
        - type: string，示例 "显式（explicit）"
        - count: number，示例 0
        - ratio: number，示例 0
  - research_question_statistics: object
    - sentence_count: number，示例 3
    - phrase_count: number，示例 3
    - expression_types: array<object>（2 项）
      - []: object
        - type: string，示例 "显式（explicit）"
        - count: number，示例 0
        - ratio: number，示例 0
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document": {
      "title": "7.pdf"
    },
    "document_title": "7.pdf",
    "research_question_sentences": [
      {
        "sentence": "We study the possibilities and limitations of ERM in this setting.",
        "text": "We study the possibilities and limitations of ERM in this setting.",
        "id": "RQS1",
        "expression_type": "implicit",
        "confidence": 0.9
      },
      {
        "sentence": "Faced with this contaminated data, our goal is to find a learning algorithm which outputs models that continuously improve generalization error in every iterati…",
        "text": "Faced with this contaminated data, our goal is to find a learning algorithm which outputs models that continuously improve generalization error in every iterati…",
        "id": "RQS2",
        "expression_type": "implicit",
        "confidence": 0.8
      },
      "…（共 3 项，示例保留前 2 项）"
    ],
    "research_question_phrases": [
      {
        "id": "RQP1",
        "text": "the possibilities and limitations of ERM in this setting",
        "sentence_id": "RQS1",
        "normalized_question": "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？",
        "confidence": 0.9
      },
      {
        "id": "RQP2",
        "text": "find a learning algorithm which outputs models that continuously improve generalization error in every iteration",
        "sentence_id": "RQS2",
        "normalized_question": "如何在数据持续被合成内容污染的迭代式学习过程中，找到使模型泛化误差每轮都持续改善的学习算法？",
        "confidence": 0.8
      },
      "…（共 3 项，示例保留前 2 项）"
    ],
    "structured_research_questions": [
      {
        "research_question_id": "RQ1",
        "question": "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？",
        "normalized_question": "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？",
        "question_type": "mechanism",
        "research_object": "ERM",
        "constraints": [
          "自然与合成数据混合的场景",
          "学习算法对数据来源不可知"
        ],
        "role": "main",
        "parent_id": "",
        "confidence": 0.9
      },
      {
        "research_question_id": "RQ2",
        "question": "如何在数据持续被合成内容污染的迭代式学习过程中，找到使模型泛化误差每轮都持续改善的学习算法？",
        "normalized_question": "如何在数据持续被合成内容污染的迭代式学习过程中，找到使模型泛化误差每轮都持续改善的学习算法？",
        "question_type": "objective",
        "research_object": "learning algorithm",
        "constraints": [
          "数据被合成数据持续污染",
          "迭代式学习过程"
        ],
        "role": "sub",
        "parent_id": "RQ1",
        "confidence": 0.8
      },
      "…（共 3 项，示例保留前 2 项）"
    ],
    "statistics": {
      "sentence_count": 3,
      "phrase_count": 3,
      "expression_types": [
        {
          "type": "显式（explicit）",
          "count": 0,
          "ratio": 0
        },
        {
          "type": "隐式（implicit）",
          "count": 3,
          "ratio": 1
        }
      ]
    },
    "research_question_statistics": {
      "sentence_count": 3,
      "phrase_count": 3,
      "expression_types": [
        {
          "type": "显式（explicit）",
          "count": 0,
          "ratio": 0
        },
        {
          "type": "隐式（implicit）",
          "count": 3,
          "ratio": 1
        }
      ]
    }
  },
  "meta": {
    "request_id": "req_0484fb21080946d891864c47e1b3b839",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 12185,
    "created_at": "2026-10-27T22:21:30.233294+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_9c357481832f432c81c19291609d1d40",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_16c9365b20e540f287b25e2ff4dccdee",
    "file_name": "7.pdf"
  }
}
```

### 9.4 批量文件

- **接口**：`POST /api/v1/research-question/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scientific_document_fragment` | file[] | 必填 | 科技文献片段或全文文件（上传 PDF/DOCX/TXT） |
| `text_format_requirement` | string | 选填 | 文本格式声明,影响溯源方式。枚举:"自动识别"(默认)、"纯文本"(跳过章节解析)、"章节结构文本"(启用标题路径溯源)、"JSON 结构文本"(按章节结构精确归属) |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/research-question/files' \
  -F 'scientific_document_fragment=@paper_01.pdf' \
  -F 'scientific_document_fragment=@paper_02.docx' \
  -F 'scientific_document_fragment=@paper_03.pdf' \
  -F 'text_format_requirement=章节结构文本'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_e4dcde4fd4aa48759b2b3782ebe79072"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_b49b58b317054b2aa4fadb91acda5519"
      - result: object
        - document: object
          - title: string，示例 "7.pdf"
        - document_title: string，示例 "7.pdf"
        - research_question_sentences: array<object>（2 项）
          - []: object
        - research_question_phrases: array<object>（2 项）
          - []: object
        - structured_research_questions: array<object>（2 项）
          - []: object
        - statistics: object
          - sentence_count: number，示例 2
          - phrase_count: number，示例 2
          - expression_types: array<object>（2 项）
        - research_question_statistics: object
          - sentence_count: number，示例 2
          - phrase_count: number，示例 2
          - expression_types: array<object>（2 项）
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_e4dcde4fd4aa48759b2b3782ebe79072",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_b49b58b317054b2aa4fadb91acda5519",
        "result": {
          "document": {
            "title": "7.pdf"
          },
          "document_title": "7.pdf",
          "research_question_sentences": [
            {
              "sentence": "We study the possibilities and limitations of ERM in this setting.",
              "text": "We study the possibilities and limitations of ERM in this setting.",
              "id": "RQS1",
              "expression_type": "implicit",
              "confidence": 0.9
            },
            {
              "sentence": "Faced with this contaminated data, our goal is to find a learning algorithm which outputs models that continuously improve generalization error in every iterati…",
              "text": "Faced with this contaminated data, our goal is to find a learning algorithm which outputs models that continuously improve generalization error in every iterati…",
              "id": "RQS2",
              "expression_type": "implicit",
              "confidence": 0.75
            }
          ],
          "research_question_phrases": [
            {
              "id": "RQP1",
              "text": "the possibilities and limitations of ERM in this setting",
              "sentence_id": "RQS1",
              "normalized_question": "在自然与合成数据混合且来源不可辨识的学习场景下，ERM 学习能力的可能性与局限性是什么？",
              "confidence": 0.9
            },
            {
              "id": "RQP2",
              "text": "find a learning algorithm which outputs models that continuously improve generalization error in every iteration",
              "sentence_id": "RQS2",
              "normalized_question": "在数据被合成内容反复污染的场景下，如何设计能在每轮迭代中持续改善泛化误差的学习算法？",
              "confidence": 0.75
            }
          ],
          "structured_research_questions": [
            {
              "research_question_id": "RQ1",
              "question": "在自然与合成数据混合且来源不可辨识的学习场景下，ERM 学习能力的可能性与局限性是什么？",
              "normalized_question": "在自然与合成数据混合且来源不可辨识的学习场景下，ERM 学习能力的可能性与局限性是什么？",
              "question_type": "mechanism",
              "research_object": "ERM",
              "constraints": [
                "自然数据与合成数据混合",
                "学习算法对数据来源不可知"
              ],
              "role": "main",
              "parent_id": "",
              "confidence": 0.9
            },
            {
              "research_question_id": "RQ2",
              "question": "在数据被合成内容反复污染的场景下，如何设计能在每轮迭代中持续改善泛化误差的学习算法？",
              "normalized_question": "在数据被合成内容反复污染的场景下，如何设计能在每轮迭代中持续改善泛化误差的学习算法？",
              "question_type": "objective",
              "research_object": "learning algorithm",
              "constraints": [
                "contaminated data",
                "每一迭代持续添加污染数据"
              ],
              "role": "sub",
              "parent_id": "RQ1",
              "confidence": 0.75
            }
          ],
          "statistics": {
            "sentence_count": 2,
            "phrase_count": 2,
            "expression_types": [
              {
                "type": "显式（explicit）",
                "count": 0,
                "ratio": 0
              },
              {
                "type": "隐式（implicit）",
                "count": 2,
                "ratio": 1
              }
            ]
          },
          "research_question_statistics": {
            "sentence_count": 2,
            "phrase_count": 2,
            "expression_types": [
              {
                "type": "显式（explicit）",
                "count": 0,
                "ratio": 0
              },
              {
                "type": "隐式（implicit）",
                "count": 2,
                "ratio": 1
              }
            ]
          }
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_5b8edf9f2376456396a1e351b6a09c22",
        "result": {
          "document": {
            "title": "35.pdf"
          },
          "document_title": "35.pdf",
          "research_question_sentences": [
            {
              "sentence": "We study the possibilities and limitations of ERM in this setting.",
              "text": "We study the possibilities and limitations of ERM in this setting.",
              "id": "RQS1",
              "expression_type": "implicit",
              "confidence": 0.9
            },
            {
              "sentence": "Faced with this contaminated data, our goal is to find a learning algorithm which outputs models that continuously improve generalization error in every iterati…",
              "text": "Faced with this contaminated data, our goal is to find a learning algorithm which outputs models that continuously improve generalization error in every iterati…",
              "id": "RQS2",
              "expression_type": "implicit",
              "confidence": 0.75
            }
          ],
          "research_question_phrases": [
            {
              "id": "RQP1",
              "text": "the possibilities and limitations of ERM in this setting",
              "sentence_id": "RQS1",
              "normalized_question": "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？",
              "confidence": 0.9
            },
            {
              "id": "RQP2",
              "text": "find a learning algorithm which outputs models that continuously improve generalization error in every iteration",
              "sentence_id": "RQS2",
              "normalized_question": "如何设计一种在持续合成数据污染下每轮迭代都能改进泛化误差的学习算法？",
              "confidence": 0.75
            }
          ],
          "structured_research_questions": [
            {
              "research_question_id": "RQ1",
              "question": "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？",
              "normalized_question": "在自然数据与合成数据混合且来源不可辨的学习场景下，ERM 的能力与局限是什么？",
              "question_type": "mechanism",
              "research_object": "ERM",
              "constraints": [
                "自然与合成数据混合的学习任务",
                "学习算法对数据来源不可知"
              ],
              "role": "main",
              "parent_id": "",
              "confidence": 0.9
            },
            {
              "research_question_id": "RQ2",
              "question": "如何设计一种在持续合成数据污染下每轮迭代都能改进泛化误差的学习算法？",
              "normalized_question": "如何设计一种在持续合成数据污染下每轮迭代都能改进泛化误差的学习算法？",
              "question_type": "objective",
              "research_object": "learning algorithm",
              "constraints": [
                "自然训练数据被合成数据污染",
                "迭代式持续训练"
              ],
              "role": "sub",
              "parent_id": "RQ1",
              "confidence": 0.75
            }
          ],
          "statistics": {
            "sentence_count": 2,
            "phrase_count": 2,
            "expression_types": [
              {
                "type": "显式（explicit）",
                "count": 0,
                "ratio": 0
              },
              {
                "type": "隐式（implicit）",
                "count": 2,
                "ratio": 1
              }
            ]
          },
          "research_question_statistics": {
            "sentence_count": 2,
            "phrase_count": 2,
            "expression_types": [
              {
                "type": "显式（explicit）",
                "count": 0,
                "ratio": 0
              },
              {
                "type": "隐式（implicit）",
                "count": 2,
                "ratio": 1
              }
            ]
          }
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_262f09993b364993b6c9b22965d392da",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 10209,
    "created_at": "2026-10-27T22:21:40.458421+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_e4dcde4fd4aa48759b2b3782ebe79072",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 10. 引用情感识别

**工具ID**：`citation-sentiment`

从科技文献全文中自动识别带有引文标记的句子，结合引用句上下文和引文元数据，判断原文作者对被引研究价值的态度属于支持、中立或有局限性。

**功能特点**：引用句抽取，元数据匹配，三分类与证据

**适用场景**：引文价值评价与影响力分析

### 10.1 单文本

- **接口**：`POST /api/v1/citation-sentiment/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `scientific_document_full_text` | string | 必填 | 文献全文文本 |
| `reference_entries` | string | 选填 | 参考文献原始条目(每行一条,选填)。提供时作为判定辅助因素,不填不影响功能 |
| `citation_sentence_and_context` | object[] | 条件必填 | 引用句及上下文(自动派生,无需手填)。系统从文献文本定位含引用标记的句子并取前后句;手动提供时以所填为准 |
| `citation_sentence_and_context[].citation_sentence` | string | 必填 | 引用句文本 |
| `citation_sentence_and_context[].previous_context` | string | 必填 | 引用句上文 |
| `citation_sentence_and_context[].next_context` | string | 必填 | 引用句下文 |
| `citation_sentence_and_context[].citation_marker` | string | 必填 | 引文标记 |
| `citation_sentence_and_context[].citation_sub_span` | string | 条件必填 | 句内多引用拆分后该条引用对应的局部子片段 |
| `citation_metadata` | object[] | 条件必填 | 被引文献元数据(自动派生,无需手填)。由参考文献条目解析得到 |
| `citation_metadata[].raw_reference` | string | 条件必填 | 用户粘贴或上传的参考文献原始条目 |
| `citation_metadata[].citation_marker` | string | 必填 | 引文标记 |
| `citation_metadata[].publication_year` | string | 选填 | 被引文献发表年份 |
| `citation_metadata[].authors` | string[] | 选填 | 作者列表 |
| `citation_metadata[].work_name` | string | 选填 | 被引文献题名 |
| `citation_metadata[].venue` | string | 选填 | 期刊或会议名称 |
| `citation_metadata[].doi` | string | 选填 | 被引文献 DOI |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/citation-sentiment/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "多尺度注意力图像分类研究",
  "scientific_document_full_text": "本文围绕图像分类中的注意力机制展开研究。已有研究表明该方法在小样本场景下泛化能力不足[1]。因此本文提出新的数据增强策略。Smith等人[2]的工作证实了注意力机制能提升检测精度。受此启发，我们设计了多尺度注意力模块。早期研究已将图模型引入结构化数据建模[5]。近年来图神经网络进一步拓展了该路线。然而该策略在长序列场景下的稳定性仍缺乏充分验证[8]。这一不足构成了本文的动机之一。",
  "reference_entries": "",
  "citation_sentence_and_context": [
    {
      "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
      "previous_context": "本文围绕图像分类中的注意力机制展开研究。",
      "next_context": "因此本文提出新的数据增强策略。",
      "citation_marker": "[1]",
      "citation_sub_span": "已有研究表明该方法在小样本场景下泛化能力不足。"
    },
    {
      "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
      "previous_context": "因此本文提出新的数据增强策略。",
      "next_context": "受此启发，我们设计了多尺度注意力模块。",
      "citation_marker": "[2]",
      "citation_sub_span": "Smith等人的工作证实了注意力机制能提升检测精度。"
    },
    {
      "citation_sentence": "早期研究已将图模型引入结构化数据建模[5]。",
      "previous_context": "受此启发，我们设计了多尺度注意力模块。",
      "next_context": "近年来图神经网络进一步拓展了该路线。",
      "citation_marker": "[5]",
      "citation_sub_span": "早期研究已将图模型引入结构化数据建模。"
    },
    {
      "citation_sentence": "然而该策略在长序列场景下的稳定性仍缺乏充分验证[8]。",
      "previous_context": "近年来图神经网络进一步拓展了该路线。",
      "next_context": "这一不足构成了本文的动机之一。",
      "citation_marker": "[8]",
      "citation_sub_span": "然而该策略在长序列场景下的稳定性仍缺乏充分验证。"
    }
  ],
  "citation_metadata": [
    {
      "raw_reference": "[12] 作者甲. 被引文献题名[J]. 情报学报, 2024, 43(2): 120-130.",
      "citation_marker": "[12]",
      "publication_year": "2024",
      "authors": [
        "作者甲"
      ],
      "work_name": "被引文献题名",
      "venue": "情报学报",
      "doi": "10.1234/example.2024.001"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "多尺度注意力图像分类研究"
  - document: object
    - title: string，示例 "多尺度注意力图像分类研究"
  - citations: array<object>（4 项）
    - []: object
      - citation_id: string，示例 "CIT1"
      - sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
      - citation_marker: string，示例 "[1]"
      - citation_markers: array<string>
      - sentiment: string，示例 "有局限性"
      - confidence: number，示例 0.9
      - citation_sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
      - context: object
        - before: string，示例 "本文围绕图像分类中的注意力机制展开研究。"
        - current_sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
        - after: string，示例 "因此本文提出新的数据增强策略。"
  - citation_sentiment_results: array<object>（4 项）
    - []: object
      - citation_id: string，示例 "CIT1"
      - sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
      - citation_marker: string，示例 "[1]"
      - citation_markers: array<string>
      - sentiment: string，示例 "有局限性"
      - confidence: number，示例 0.9
      - citation_sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
      - context: object
        - before: string，示例 "本文围绕图像分类中的注意力机制展开研究。"
        - current_sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
        - after: string，示例 "因此本文提出新的数据增强策略。"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "多尺度注意力图像分类研究",
    "document": {
      "title": "多尺度注意力图像分类研究"
    },
    "citations": [
      {
        "citation_id": "CIT1",
        "sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
        "citation_marker": "[1]",
        "citation_markers": [
          "[1]"
        ],
        "sentiment": "有局限性",
        "confidence": 0.9,
        "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
        "context": {
          "before": "本文围绕图像分类中的注意力机制展开研究。",
          "current_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
          "after": "因此本文提出新的数据增强策略。"
        }
      },
      {
        "citation_id": "CIT2",
        "sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
        "citation_marker": "[2]",
        "citation_markers": [
          "[2]"
        ],
        "sentiment": "支持",
        "confidence": 0.7,
        "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
        "context": {
          "before": "因此本文提出新的数据增强策略。",
          "current_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
          "after": "受此启发，我们设计了多尺度注意力模块。"
        }
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "citation_sentiment_results": [
      {
        "citation_id": "CIT1",
        "sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
        "citation_marker": "[1]",
        "citation_markers": [
          "[1]"
        ],
        "sentiment": "有局限性",
        "confidence": 0.9,
        "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
        "context": {
          "before": "本文围绕图像分类中的注意力机制展开研究。",
          "current_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
          "after": "因此本文提出新的数据增强策略。"
        }
      },
      {
        "citation_id": "CIT2",
        "sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
        "citation_marker": "[2]",
        "citation_markers": [
          "[2]"
        ],
        "sentiment": "支持",
        "confidence": 0.7,
        "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
        "context": {
          "before": "因此本文提出新的数据增强策略。",
          "current_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
          "after": "受此启发，我们设计了多尺度注意力模块。"
        }
      },
      "…（共 4 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_88e59721289c42b6b95c365ba5cd65f5",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 9186,
    "created_at": "2026-10-27T22:05:01.594717+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_9a912277054d49a69c168ad0b4fec5a7",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_6539aede5afa4fada5af699fd09316d0",
    "file_name": null
  }
}
```

### 10.2 批量文本

- **接口**：`POST /api/v1/citation-sentiment/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `citation_sentence_and_context` | object[] | 条件必填 | 引用句及上下文(自动派生,无需手填)。系统从文献文本定位含引用标记的句子并取前后句;手动提供时以所填为准 |
| `citation_sentence_and_context[].citation_sentence` | string | 必填 | 引用句文本 |
| `citation_sentence_and_context[].previous_context` | string | 必填 | 引用句上文 |
| `citation_sentence_and_context[].next_context` | string | 必填 | 引用句下文 |
| `citation_sentence_and_context[].citation_marker` | string | 必填 | 引文标记 |
| `citation_metadata` | object[] | 条件必填 | 被引文献元数据(自动派生,无需手填)。由参考文献条目解析得到 |
| `reference_entries` | object[] | 选填 | 可选：参考文献原始条目（字符串数组，逐条与引用数据对位） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/citation-sentiment/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "文献A",
    "文献B"
  ],
  "citation_sentence_and_context": [
    {
      "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
      "previous_context": "针对图像分类任务，",
      "next_context": "因此本文提出新的数据增强策略。",
      "citation_marker": "[1]"
    },
    {
      "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
      "previous_context": "在目标检测领域，",
      "next_context": "受此启发，我们设计了多尺度注意力模块。",
      "citation_marker": "[2]"
    }
  ],
  "citation_metadata": [
    [
      {
        "citation_marker": "[1]",
        "authors": "张三",
        "work_name": "图像分类方法研究",
        "publication_year": "2024"
      }
    ],
    [
      {
        "citation_marker": "[2]",
        "authors": "Smith J",
        "work_name": "Attention for detection",
        "publication_year": "2023"
      }
    ]
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_fa674cd719c945f2b35257c2c91148ad"
  - input_type: string，示例 "texts"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_253f1f7e6384474dab3019858d34f4cb"
      - result: object
        - document_title: string，示例 "文献A"
        - document: object
          - title: string，示例 "文献A"
        - citations: array<object>
          - []: object
        - citation_sentiment_results: array<object>
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_fa674cd719c945f2b35257c2c91148ad",
    "input_type": "texts",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_253f1f7e6384474dab3019858d34f4cb",
        "result": {
          "document_title": "文献A",
          "document": {
            "title": "文献A"
          },
          "citations": [
            {
              "citation_id": "CIT1",
              "sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
              "citation_marker": "[1]",
              "citation_markers": [
                "[1]"
              ],
              "sentiment": "有局限性",
              "confidence": 0.92,
              "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
              "context": {
                "before": "针对图像分类任务，",
                "current_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
                "after": "因此本文提出新的数据增强策略。"
              }
            }
          ],
          "citation_sentiment_results": [
            {
              "citation_id": "CIT1",
              "sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
              "citation_marker": "[1]",
              "citation_markers": [
                "[1]"
              ],
              "sentiment": "有局限性",
              "confidence": 0.92,
              "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
              "context": {
                "before": "针对图像分类任务，",
                "current_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
                "after": "因此本文提出新的数据增强策略。"
              }
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_b193cfaee1294e35830cd2338986b56f",
        "result": {
          "document_title": "文献B",
          "document": {
            "title": "文献B"
          },
          "citations": [
            {
              "citation_id": "CIT1",
              "sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
              "citation_marker": "[2]",
              "citation_markers": [
                "[2]"
              ],
              "sentiment": "支持",
              "confidence": 0.75,
              "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
              "context": {
                "before": "在目标检测领域，",
                "current_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
                "after": "受此启发，我们设计了多尺度注意力模块。"
              }
            }
          ],
          "citation_sentiment_results": [
            {
              "citation_id": "CIT1",
              "sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
              "citation_marker": "[2]",
              "citation_markers": [
                "[2]"
              ],
              "sentiment": "支持",
              "confidence": 0.75,
              "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
              "context": {
                "before": "在目标检测领域，",
                "current_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
                "after": "受此启发，我们设计了多尺度注意力模块。"
              }
            }
          ]
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_70cef34c4ce74bfd88c54eebe5125075",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 8080,
    "created_at": "2026-10-27T22:05:09.685984+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_fa674cd719c945f2b35257c2c91148ad",
    "input_type": "texts",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

### 10.3 单文件

- **接口**：`POST /api/v1/citation-sentiment/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 必填 | file |
| `citation_sentence_and_context` | object[] | 选填 | 可选：引用句卡片数组（完整一整句为一条）。提供时走信任卡片路径：输出引用句数=卡片数；不提供由后端自动抽取 |
| `citation_metadata` | object[] | 选填 | 可选：被引文献元数据数组（标记/作者/题名/年份/来源），作为意图/情感判定的辅助因素 |
| `reference_entries` | object[] | 选填 | 可选：参考文献原始条目（每行一条）。与解析出的元数据一并提供，作判定辅助因素 |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/citation-sentiment/file' \
  -F 'file=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "7.pdf"
  - document: object
    - title: string，示例 "7.pdf"
  - citations: array<object>
    - []: object
      - citation_id: string，示例 "CIT1"
      - sentence: string，示例 "This results in a far worse estimator, w…"
      - citation_marker: string，示例 "[2024]"
      - citation_markers: array<string>
      - sentiment: string，示例 "中立"
      - confidence: number，示例 0.9
      - citation_sentence: string，示例 "This results in a far worse estimator, w…"
      - context: object
        - before: string，示例 "When $\\alpha = 1$ we instantiate a pure …"
        - current_sentence: string，示例 "This results in a far worse estimator, w…"
        - after: string，示例 "Remark 2."
  - citation_sentiment_results: array<object>
    - []: object
      - citation_id: string，示例 "CIT1"
      - sentence: string，示例 "This results in a far worse estimator, w…"
      - citation_marker: string，示例 "[2024]"
      - citation_markers: array<string>
      - sentiment: string，示例 "中立"
      - confidence: number，示例 0.9
      - citation_sentence: string，示例 "This results in a far worse estimator, w…"
      - context: object
        - before: string，示例 "When $\\alpha = 1$ we instantiate a pure …"
        - current_sentence: string，示例 "This results in a far worse estimator, w…"
        - after: string，示例 "Remark 2."
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "7.pdf",
    "document": {
      "title": "7.pdf"
    },
    "citations": [
      {
        "citation_id": "CIT1",
        "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
        "citation_marker": "[2024]",
        "citation_markers": [
          "[2024]"
        ],
        "sentiment": "中立",
        "confidence": 0.9,
        "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
        "context": {
          "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
          "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
          "after": "Remark 2."
        }
      }
    ],
    "citation_sentiment_results": [
      {
        "citation_id": "CIT1",
        "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
        "citation_marker": "[2024]",
        "citation_markers": [
          "[2024]"
        ],
        "sentiment": "中立",
        "confidence": 0.9,
        "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
        "context": {
          "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
          "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
          "after": "Remark 2."
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_9b7e89950e71462aaf1d67ffd3fa3a2a",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 30414,
    "created_at": "2026-10-27T22:22:10.886205+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_4a8e8a7957664f3291617377bcdbc545",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_3950307b8cc04afa81301913857749d3",
    "file_name": "7.pdf"
  }
}
```

### 10.4 批量文件

- **接口**：`POST /api/v1/citation-sentiment/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `files` | file[] | 必填 | files |
| `citation_contexts_by_file` | object[] | 选填 | 可选：逐文件引用句卡片（数组的数组，外层下标=文件序）。提供时各文件输出引用句数=该文件卡片数 |
| `citation_metadata_by_file` | object[] | 选填 | 可选：逐文件被引文献元数据（数组的数组，与文件对位） |
| `reference_entries_by_file` | string[] | 选填 | 可选：逐文件参考文献原始条目（字符串数组，与文件对位） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/citation-sentiment/files' \
  -F 'files=@paper_01.pdf' \
  -F 'files=@paper_02.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_84993a327b5b468fa01d072604faf16a"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_1d34f63c966c4f6c97d9699aa31ae8e7"
      - result: object
        - document_title: string，示例 "7.pdf"
        - document: object
          - title: string，示例 "7.pdf"
        - citations: array<object>
          - []: object
        - citation_sentiment_results: array<object>
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_84993a327b5b468fa01d072604faf16a",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_1d34f63c966c4f6c97d9699aa31ae8e7",
        "result": {
          "document_title": "7.pdf",
          "document": {
            "title": "7.pdf"
          },
          "citations": [
            {
              "citation_id": "CIT1",
              "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "citation_marker": "[2024]",
              "citation_markers": [
                "[2024]"
              ],
              "sentiment": "中立",
              "confidence": 0.9,
              "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "context": {
                "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
                "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
                "after": "Remark 2."
              }
            }
          ],
          "citation_sentiment_results": [
            {
              "citation_id": "CIT1",
              "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "citation_marker": "[2024]",
              "citation_markers": [
                "[2024]"
              ],
              "sentiment": "中立",
              "confidence": 0.9,
              "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "context": {
                "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
                "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
                "after": "Remark 2."
              }
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_fa7cd06222024c4e902f37b3829e7116",
        "result": {
          "document_title": "35.pdf",
          "document": {
            "title": "35.pdf"
          },
          "citations": [
            {
              "citation_id": "CIT1",
              "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "citation_marker": "[2024]",
              "citation_markers": [
                "[2024]"
              ],
              "sentiment": "中立",
              "confidence": 0.85,
              "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "context": {
                "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
                "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
                "after": "Remark 2."
              }
            }
          ],
          "citation_sentiment_results": [
            {
              "citation_id": "CIT1",
              "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "citation_marker": "[2024]",
              "citation_markers": [
                "[2024]"
              ],
              "sentiment": "中立",
              "confidence": 0.85,
              "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "context": {
                "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
                "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
                "after": "Remark 2."
              }
            }
          ]
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_f73a5c8f931342eaae834d5192a0a016",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 44989,
    "created_at": "2026-10-27T22:22:55.897632+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_84993a327b5b468fa01d072604faf16a",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 11. 引用意图识别

**工具ID**：`citation-intent`

从科技文献全文文件中自动抽取引用句及其前后文，匹配引文元数据，并结合预处理后的训练集判断作者引用他人研究的动机。引用意图分为用于背景介绍、用于引入研究方法和用于结果比较三类。

**功能特点**：引用句抽取，三类意图识别，证据与评分

**适用场景**：综述结构分析与引文网络

### 11.1 单文本

- **接口**：`POST /api/v1/citation-intent/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `scientific_document_full_text` | string | 必填 | 文献全文文本或文件 |
| `reference_entries` | string | 选填 | 参考文献原始条目(每行一条,选填)。提供时作为判定辅助因素,不填不影响功能 |
| `citation_sentence_and_context` | object[] | 条件必填 | 引用句及上下文(自动派生)。结构同引用情感识别 |
| `citation_sentence_and_context[].citation_sentence` | string | 必填 | 引用句文本 |
| `citation_sentence_and_context[].previous_context` | string | 必填 | 引用句上文 |
| `citation_sentence_and_context[].next_context` | string | 必填 | 引用句下文 |
| `citation_sentence_and_context[].citation_marker` | string | 必填 | 引文标记 |
| `citation_sentence_and_context[].citation_sub_span` | string | 条件必填 | 句内多引用拆分后该条引用对应的局部子片段 |
| `citation_metadata` | object[] | 条件必填 | 被引文献元数据(自动派生)。结构同引用情感识别 |
| `citation_metadata[].raw_reference` | string | 条件必填 | 用户粘贴或上传的参考文献原始条目 |
| `citation_metadata[].citation_marker` | string | 必填 | 引文标记 |
| `citation_metadata[].publication_year` | string | 选填 | 被引文献发表年份 |
| `citation_metadata[].authors` | string[] | 选填 | 作者列表 |
| `citation_metadata[].work_name` | string | 选填 | 被引文献题名 |
| `citation_metadata[].venue` | string | 选填 | 期刊或会议名称 |
| `citation_metadata[].doi` | string | 选填 | 被引文献 DOI |
| `preprocessed_training_set` | file (.json) | 选填 | 可选上传资源：引用预处理训练集（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/citation-intent/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "多尺度注意力图像分类研究",
  "scientific_document_full_text": "本文围绕图像分类中的注意力机制展开研究。已有研究表明该方法在小样本场景下泛化能力不足[1]。因此本文提出新的数据增强策略。Smith等人[2]的工作证实了注意力机制能提升检测精度。受此启发，我们设计了多尺度注意力模块。早期研究已将图模型引入结构化数据建模[5]。近年来图神经网络进一步拓展了该路线。然而该策略在长序列场景下的稳定性仍缺乏充分验证[8]。这一不足构成了本文的动机之一。",
  "reference_entries": "",
  "citation_sentence_and_context": [
    {
      "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
      "previous_context": "本文围绕图像分类中的注意力机制展开研究。",
      "next_context": "因此本文提出新的数据增强策略。",
      "citation_marker": "[1]",
      "citation_sub_span": "已有研究表明该方法在小样本场景下泛化能力不足。"
    },
    {
      "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
      "previous_context": "因此本文提出新的数据增强策略。",
      "next_context": "受此启发，我们设计了多尺度注意力模块。",
      "citation_marker": "[2]",
      "citation_sub_span": "Smith等人的工作证实了注意力机制能提升检测精度。"
    },
    {
      "citation_sentence": "早期研究已将图模型引入结构化数据建模[5]。",
      "previous_context": "受此启发，我们设计了多尺度注意力模块。",
      "next_context": "近年来图神经网络进一步拓展了该路线。",
      "citation_marker": "[5]",
      "citation_sub_span": "早期研究已将图模型引入结构化数据建模。"
    },
    {
      "citation_sentence": "然而该策略在长序列场景下的稳定性仍缺乏充分验证[8]。",
      "previous_context": "近年来图神经网络进一步拓展了该路线。",
      "next_context": "这一不足构成了本文的动机之一。",
      "citation_marker": "[8]",
      "citation_sub_span": "然而该策略在长序列场景下的稳定性仍缺乏充分验证。"
    }
  ],
  "citation_metadata": [
    {
      "raw_reference": "[12] 作者甲. 被引文献题名[J]. 情报学报, 2024, 43(2): 120-130.",
      "citation_marker": "[12]",
      "publication_year": "2024",
      "authors": [
        "作者甲"
      ],
      "work_name": "被引文献题名",
      "venue": "情报学报",
      "doi": "10.1234/example.2024.001"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "多尺度注意力图像分类研究"
  - document: object
    - title: string，示例 "多尺度注意力图像分类研究"
  - citations: array<object>（4 项）
    - []: object
      - citation_id: string，示例 "CIT1"
      - sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
      - citation_marker: string，示例 "[1]"
      - citation_markers: array<string>
      - intent: string，示例 "用于背景介绍"
      - confidence: number，示例 1
      - citation_sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
      - context: object
        - before: string，示例 "本文围绕图像分类中的注意力机制展开研究。"
        - current_sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
        - after: string，示例 "因此本文提出新的数据增强策略。"
  - citation_intent_results: array<object>（4 项）
    - []: object
      - citation_id: string，示例 "CIT1"
      - sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
      - citation_marker: string，示例 "[1]"
      - citation_markers: array<string>
      - intent: string，示例 "用于背景介绍"
      - confidence: number，示例 1
      - citation_sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
      - context: object
        - before: string，示例 "本文围绕图像分类中的注意力机制展开研究。"
        - current_sentence: string，示例 "已有研究表明该方法在小样本场景下泛化能力不足[1]。"
        - after: string，示例 "因此本文提出新的数据增强策略。"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "多尺度注意力图像分类研究",
    "document": {
      "title": "多尺度注意力图像分类研究"
    },
    "citations": [
      {
        "citation_id": "CIT1",
        "sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
        "citation_marker": "[1]",
        "citation_markers": [
          "[1]"
        ],
        "intent": "用于背景介绍",
        "confidence": 1,
        "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
        "context": {
          "before": "本文围绕图像分类中的注意力机制展开研究。",
          "current_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
          "after": "因此本文提出新的数据增强策略。"
        }
      },
      {
        "citation_id": "CIT2",
        "sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
        "citation_marker": "[2]",
        "citation_markers": [
          "[2]"
        ],
        "intent": "用于背景介绍",
        "confidence": 0.9,
        "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
        "context": {
          "before": "因此本文提出新的数据增强策略。",
          "current_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
          "after": "受此启发，我们设计了多尺度注意力模块。"
        }
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "citation_intent_results": [
      {
        "citation_id": "CIT1",
        "sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
        "citation_marker": "[1]",
        "citation_markers": [
          "[1]"
        ],
        "intent": "用于背景介绍",
        "confidence": 1,
        "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
        "context": {
          "before": "本文围绕图像分类中的注意力机制展开研究。",
          "current_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
          "after": "因此本文提出新的数据增强策略。"
        }
      },
      {
        "citation_id": "CIT2",
        "sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
        "citation_marker": "[2]",
        "citation_markers": [
          "[2]"
        ],
        "intent": "用于背景介绍",
        "confidence": 0.9,
        "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
        "context": {
          "before": "因此本文提出新的数据增强策略。",
          "current_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
          "after": "受此启发，我们设计了多尺度注意力模块。"
        }
      },
      "…（共 4 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_8836a284c89444c695ca54a642399cff",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 2542,
    "created_at": "2026-10-27T22:05:12.236174+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_57be964a0a504661be377baca387d081",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_fc1e5acd981849b09d6c54279d80bfa9",
    "file_name": null
  }
}
```

### 11.2 批量文本

- **接口**：`POST /api/v1/citation-intent/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `citation_sentence_and_context` | object[] | 条件必填 | 引用句及上下文(自动派生)。结构同引用情感识别 |
| `citation_sentence_and_context[].citation_sentence` | string | 必填 | 引用句文本 |
| `citation_sentence_and_context[].previous_context` | string | 必填 | 引用句上文 |
| `citation_sentence_and_context[].next_context` | string | 必填 | 引用句下文 |
| `citation_sentence_and_context[].citation_marker` | string | 必填 | 引文标记 |
| `citation_metadata` | object[] | 条件必填 | 被引文献元数据(自动派生)。结构同引用情感识别 |
| `preprocessed_training_set` | object | 选填 | 预处理后的训练集引用。引用意图判定规则包:引用句抽取正则、三类意图定义(背景介绍/引入研究方法/结果比较)、关键词打分规则;注入提示词约束判定口径并在 LLM 判定后做后置校验调分(不训练模型) |
| `preprocessed_training_set.source` | string | 选填 | 资源来源或文献来源 |
| `preprocessed_training_set.resource_id` | string | 条件必填 | 数据库资源编号 |
| `reference_entries` | object[] | 选填 | 可选：参考文献原始条目（字符串数组，逐条与引用数据对位） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/citation-intent/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "文献A",
    "文献B"
  ],
  "citation_sentence_and_context": [
    {
      "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
      "previous_context": "针对图像分类任务，",
      "next_context": "因此本文提出新的数据增强策略。",
      "citation_marker": "[1]"
    },
    {
      "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
      "previous_context": "在目标检测领域，",
      "next_context": "受此启发，我们设计了多尺度注意力模块。",
      "citation_marker": "[2]"
    }
  ],
  "citation_metadata": [
    [
      {
        "citation_marker": "[1]",
        "authors": "张三",
        "work_name": "图像分类方法研究",
        "publication_year": "2024"
      }
    ],
    [
      {
        "citation_marker": "[2]",
        "authors": "Smith J",
        "work_name": "Attention for detection",
        "publication_year": "2023"
      }
    ]
  ],
  "preprocessed_training_set": {
    "source": "database",
    "resource_id": "RES-BUNDLED-CITATION-INTENT"
  }
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_c48b751655a44b12940c7c9f2c794170"
  - input_type: string，示例 "texts"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_97748b7ea7634220af6d9593a34e7ba0"
      - result: object
        - document_title: string，示例 "文献A"
        - document: object
          - title: string，示例 "文献A"
        - citations: array<object>
          - []: object
        - citation_intent_results: array<object>
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_c48b751655a44b12940c7c9f2c794170",
    "input_type": "texts",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_97748b7ea7634220af6d9593a34e7ba0",
        "result": {
          "document_title": "文献A",
          "document": {
            "title": "文献A"
          },
          "citations": [
            {
              "citation_id": "CIT1",
              "sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
              "citation_marker": "[1]",
              "citation_markers": [
                "[1]"
              ],
              "intent": "用于背景介绍",
              "confidence": 1,
              "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
              "context": {
                "before": "针对图像分类任务，",
                "current_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
                "after": "因此本文提出新的数据增强策略。"
              }
            }
          ],
          "citation_intent_results": [
            {
              "citation_id": "CIT1",
              "sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
              "citation_marker": "[1]",
              "citation_markers": [
                "[1]"
              ],
              "intent": "用于背景介绍",
              "confidence": 1,
              "citation_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
              "context": {
                "before": "针对图像分类任务，",
                "current_sentence": "已有研究表明该方法在小样本场景下泛化能力不足[1]。",
                "after": "因此本文提出新的数据增强策略。"
              }
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_ebc4ac225b3240b5b17cd87460dffc3c",
        "result": {
          "document_title": "文献B",
          "document": {
            "title": "文献B"
          },
          "citations": [
            {
              "citation_id": "CIT1",
              "sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
              "citation_marker": "[2]",
              "citation_markers": [
                "[2]"
              ],
              "intent": "用于背景介绍",
              "confidence": 0.75,
              "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
              "context": {
                "before": "在目标检测领域，",
                "current_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
                "after": "受此启发，我们设计了多尺度注意力模块。"
              }
            }
          ],
          "citation_intent_results": [
            {
              "citation_id": "CIT1",
              "sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
              "citation_marker": "[2]",
              "citation_markers": [
                "[2]"
              ],
              "intent": "用于背景介绍",
              "confidence": 0.75,
              "citation_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
              "context": {
                "before": "在目标检测领域，",
                "current_sentence": "Smith等人[2]的工作证实了注意力机制能提升检测精度。",
                "after": "受此启发，我们设计了多尺度注意力模块。"
              }
            }
          ]
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_c3bf4f4c50f9445ea149bb2749952f22",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 3694,
    "created_at": "2026-10-27T22:05:15.940872+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_c48b751655a44b12940c7c9f2c794170",
    "input_type": "texts",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

### 11.3 单文件

- **接口**：`POST /api/v1/citation-intent/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 必填 | file |
| `preprocessed_training_set` | file (.json) | 选填 | 可选上传资源：引用预处理训练集（.json） |
| `citation_sentence_and_context` | object[] | 选填 | 可选：引用句卡片数组（完整一整句为一条）。提供时走信任卡片路径：输出引用句数=卡片数；不提供由后端自动抽取 |
| `citation_metadata` | object[] | 选填 | 可选：被引文献元数据数组（标记/作者/题名/年份/来源），作为意图/情感判定的辅助因素 |
| `reference_entries` | object[] | 选填 | 可选：参考文献原始条目（每行一条）。与解析出的元数据一并提供，作判定辅助因素 |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/citation-intent/file' \
  -F 'file=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "7.pdf"
  - document: object
    - title: string，示例 "7.pdf"
  - citations: array<object>
    - []: object
      - citation_id: string，示例 "CIT1"
      - sentence: string，示例 "This results in a far worse estimator, w…"
      - citation_marker: string，示例 "[2024]"
      - citation_markers: array<string>
      - intent: string，示例 "用于结果比较"
      - confidence: number，示例 0.85
      - citation_sentence: string，示例 "This results in a far worse estimator, w…"
      - context: object
        - before: string，示例 "When $\\alpha = 1$ we instantiate a pure …"
        - current_sentence: string，示例 "This results in a far worse estimator, w…"
        - after: string，示例 "Remark 2."
  - citation_intent_results: array<object>
    - []: object
      - citation_id: string，示例 "CIT1"
      - sentence: string，示例 "This results in a far worse estimator, w…"
      - citation_marker: string，示例 "[2024]"
      - citation_markers: array<string>
      - intent: string，示例 "用于结果比较"
      - confidence: number，示例 0.85
      - citation_sentence: string，示例 "This results in a far worse estimator, w…"
      - context: object
        - before: string，示例 "When $\\alpha = 1$ we instantiate a pure …"
        - current_sentence: string，示例 "This results in a far worse estimator, w…"
        - after: string，示例 "Remark 2."
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "7.pdf",
    "document": {
      "title": "7.pdf"
    },
    "citations": [
      {
        "citation_id": "CIT1",
        "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
        "citation_marker": "[2024]",
        "citation_markers": [
          "[2024]"
        ],
        "intent": "用于结果比较",
        "confidence": 0.85,
        "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
        "context": {
          "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
          "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
          "after": "Remark 2."
        }
      }
    ],
    "citation_intent_results": [
      {
        "citation_id": "CIT1",
        "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
        "citation_marker": "[2024]",
        "citation_markers": [
          "[2024]"
        ],
        "intent": "用于结果比较",
        "confidence": 0.85,
        "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
        "context": {
          "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
          "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
          "after": "Remark 2."
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_66a6f4bf8c53446c9e770575d8fb52cb",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 29380,
    "created_at": "2026-10-27T22:23:25.298559+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_19e00ebf60534ff39302614bcb38f4b8",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_5c36f2916d444fbc9dada6c01e02ec09",
    "file_name": "7.pdf"
  }
}
```

### 11.4 批量文件

- **接口**：`POST /api/v1/citation-intent/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `files` | file[] | 必填 | files |
| `preprocessed_training_set` | file (.json) | 选填 | 可选上传资源：引用预处理训练集（.json） |
| `citation_contexts_by_file` | object[] | 选填 | 可选：逐文件引用句卡片（数组的数组，外层下标=文件序）。提供时各文件输出引用句数=该文件卡片数 |
| `citation_metadata_by_file` | object[] | 选填 | 可选：逐文件被引文献元数据（数组的数组，与文件对位） |
| `reference_entries_by_file` | string[] | 选填 | 可选：逐文件参考文献原始条目（字符串数组，与文件对位） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/citation-intent/files' \
  -F 'files=@paper_01.pdf' \
  -F 'files=@paper_02.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_4bf1a08f29234a25962c66563175b930"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_d2f99a8d4cd64a40aeb6e291a4c61fd6"
      - result: object
        - document_title: string，示例 "7.pdf"
        - document: object
          - title: string，示例 "7.pdf"
        - citations: array<object>
          - []: object
        - citation_intent_results: array<object>
          - []: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_4bf1a08f29234a25962c66563175b930",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_d2f99a8d4cd64a40aeb6e291a4c61fd6",
        "result": {
          "document_title": "7.pdf",
          "document": {
            "title": "7.pdf"
          },
          "citations": [
            {
              "citation_id": "CIT1",
              "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "citation_marker": "[2024]",
              "citation_markers": [
                "[2024]"
              ],
              "intent": "用于结果比较",
              "confidence": 0.8,
              "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "context": {
                "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
                "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
                "after": "Remark 2."
              }
            }
          ],
          "citation_intent_results": [
            {
              "citation_id": "CIT1",
              "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "citation_marker": "[2024]",
              "citation_markers": [
                "[2024]"
              ],
              "intent": "用于结果比较",
              "confidence": 0.8,
              "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "context": {
                "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
                "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
                "after": "Remark 2."
              }
            }
          ]
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_d6e736b47f81443489454972f3b165af",
        "result": {
          "document_title": "35.pdf",
          "document": {
            "title": "35.pdf"
          },
          "citations": [
            {
              "citation_id": "CIT1",
              "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "citation_marker": "[2024]",
              "citation_markers": [
                "[2024]"
              ],
              "intent": "用于结果比较",
              "confidence": 0.85,
              "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "context": {
                "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
                "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
                "after": "Remark 2."
              }
            }
          ],
          "citation_intent_results": [
            {
              "citation_id": "CIT1",
              "sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "citation_marker": "[2024]",
              "citation_markers": [
                "[2024]"
              ],
              "intent": "用于结果比较",
              "confidence": 0.85,
              "citation_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
              "context": {
                "before": "When $\\alpha = 1$ we instantiate a pure recursive learning setting, where the learner has access to natural data only on one round, and subsequently re-trains o…",
                "current_sentence": "This results in a far worse estimator, which has constant error regardless of how many rounds elapse, recovering the $\\pi ^ { 2 } / 6$ constant observed by Dey …",
                "after": "Remark 2."
              }
            }
          ]
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_2bacabd45397424185f69acbc4b62800",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 46851,
    "created_at": "2026-10-27T22:24:12.165209+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_4bf1a08f29234a25962c66563175b930",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 12. 概念定义句识别工具

**工具ID**：`definition-detect`

识别包含概念定义表述的句子，并抽取被定义的核心概念词，形成“概念—定义”结构化映射。

**功能特点**：定义句识别，概念词抽取，术语映射统计

**适用场景**：概念梳理与领域术语库建设

### 12.1 单文本

- **接口**：`POST /api/v1/concept-definition/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `scientific_document_fragment_or_batch_text` | string | 必填 | 科技文献全文片段或文本 |
| `domain_label` | string | 选填 | 领域标签。枚举:"自动识别"(默认)或 "01"–"32"。注入识别提示词作为领域语境,概念判定优先考虑该领域术语;随结果返回 |
| `output_format_requirement` | string | 选填 | 输出格式要求。枚举:"JSON"(默认)、"CSV"(结果附 csv_content 字段)、"数据库写入结构"(结果附 database_records 字段,含 concept_id 等 DB 就绪字段) |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/concept-definition/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "科技文献题目",
  "scientific_document_fragment_or_batch_text": "高校体育场馆的智慧化建设需要明确核心治理概念。智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。上述概念共同构成场馆数字化运营的理论基础。",
  "domain_label": "",
  "output_format_requirement": "JSON"
}
```

#### 响应字段（data）

```
- data: object
  - definitions: array<object>（2 项）
    - []: object
      - concept: string，示例 "智慧治理"
      - definition_count: number，示例 1
      - definitions: array<object>
        - []: object
          - sentence: string，示例 "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运…"
          - definition: string，示例 "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运…"
          - pattern: string，示例 "是"
          - source_position: object
          - confidence: number，示例 0.95
  - definition_results: array<object>（2 项）
    - []: object
      - concept: string，示例 "智慧治理"
      - definition_count: number，示例 1
      - definitions: array<object>
        - []: object
          - sentence: string，示例 "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运…"
          - definition: string，示例 "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运…"
          - pattern: string，示例 "是"
          - source_position: object
          - confidence: number，示例 0.95
  - mappings: array<object>（2 项）
    - []: object
      - concept: string，示例 "智慧治理"
      - definition: string，示例 "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运…"
  - concept_definition_mappings: array<object>（2 项）
    - []: object
      - concept: string，示例 "智慧治理"
      - definition: string，示例 "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运…"
  - statistical_analysis_report: object
    - definition_sentence_count: number，示例 2
    - concept_count: number，示例 2
    - mapping_count: number，示例 2
    - section_distribution: array<undefined>
  - document: object
    - title: string，示例 "科技文献题目"
  - document_title: string，示例 "科技文献题目"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "definitions": [
      {
        "concept": "智慧治理",
        "definition_count": 1,
        "definitions": [
          {
            "sentence": "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。",
            "definition": "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。",
            "pattern": "是",
            "source_position": {
              "start": 23,
              "end": 77
            },
            "confidence": 0.95
          }
        ]
      },
      {
        "concept": "数据驱动决策",
        "definition_count": 1,
        "definitions": [
          {
            "sentence": "数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。",
            "definition": "数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。",
            "pattern": "是",
            "source_position": {
              "start": 77,
              "end": 119
            },
            "confidence": 0.95
          }
        ]
      }
    ],
    "definition_results": [
      {
        "concept": "智慧治理",
        "definition_count": 1,
        "definitions": [
          {
            "sentence": "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。",
            "definition": "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。",
            "pattern": "是",
            "source_position": {
              "start": 23,
              "end": 77
            },
            "confidence": 0.95
          }
        ]
      },
      {
        "concept": "数据驱动决策",
        "definition_count": 1,
        "definitions": [
          {
            "sentence": "数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。",
            "definition": "数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。",
            "pattern": "是",
            "source_position": {
              "start": 77,
              "end": 119
            },
            "confidence": 0.95
          }
        ]
      }
    ],
    "mappings": [
      {
        "concept": "智慧治理",
        "definition": "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。"
      },
      {
        "concept": "数据驱动决策",
        "definition": "数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。"
      }
    ],
    "concept_definition_mappings": [
      {
        "concept": "智慧治理",
        "definition": "智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。"
      },
      {
        "concept": "数据驱动决策",
        "definition": "数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。"
      }
    ],
    "statistical_analysis_report": {
      "definition_sentence_count": 2,
      "concept_count": 2,
      "mapping_count": 2,
      "section_distribution": []
    },
    "document": {
      "title": "科技文献题目"
    },
    "document_title": "科技文献题目"
  },
  "meta": {
    "request_id": "req_9492b3ccf5a24261869f898599df5c0e",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 4865,
    "created_at": "2026-10-27T22:05:20.817320+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_996002fb01224737a6fc6e6ba9a2e608",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_970ac2fb20f94052806119e606e1217a",
    "file_name": null
  }
}
```

### 12.2 批量文本

- **接口**：`POST /api/v1/concept-definition/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `scientific_document_fragment_or_batch_text` | object[] | 必填 | 科技文献全文片段或文本 |
| `scientific_document_fragment_or_batch_text[].id` | string | 选填 | 批量文本条目编号 |
| `scientific_document_fragment_or_batch_text[].text` | string | 必填 | 用户输入的文本内容 |
| `scientific_document_fragment_or_batch_text[].title` | string | 选填 | 文献题名 |
| `domain_label` | string | 选填 | 领域标签。枚举:"自动识别"(默认)或 "01"–"32"。注入识别提示词作为领域语境,概念判定优先考虑该领域术语;随结果返回 |
| `output_format_requirement` | string | 选填 | 输出格式要求。枚举:"JSON"(默认)、"CSV"(结果附 csv_content 字段)、"数据库写入结构"(结果附 database_records 字段,含 concept_id 等 DB 就绪字段) |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/concept-definition/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "第 1 篇文献题目",
    "第 2 篇文献题目",
    "第 3 篇文献题目"
  ],
  "scientific_document_fragment_or_batch_text": [
    {
      "id": "DEMO_1",
      "text": "地震动记录选取需要兼顾记录间的相似性和频谱信息。模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。两种方法结合后可提高地震动记录选取的一致性。",
      "title": "第 1 篇文献题目"
    },
    {
      "id": "DEMO_2",
      "text": "糖尿病肾病研究需要从高维转录组数据中识别具有诊疗价值的分子特征。加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。研究据此筛选并验证VWF等候选基因。",
      "title": "第 2 篇文献题目"
    },
    {
      "id": "DEMO_3",
      "text": "复杂工业表面的微小缺陷容易受到尺度变化和背景纹理干扰。多尺度特征增强是融合不同分辨率层级的视觉特征，以提高模型对尺度差异明显和微小缺陷表征能力的方法。跨层特征融合是联合建模浅层细节特征与深层语义特征，以改善复杂背景下缺陷区域表达的方法。两种机制共同提升了微小缺陷检测的准确率与召回率。",
      "title": "第 3 篇文献题目"
    }
  ],
  "domain_label": "",
  "output_format_requirement": "JSON"
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_484b94744c074257b2c3664fe2fb3026"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_29470c9a7a624b13aa8b3cc18fd7699b"
      - result: object
        - definitions: array<object>（2 项）
          - []: object
        - definition_results: array<object>（2 项）
          - []: object
        - mappings: array<object>（2 项）
          - []: object
        - concept_definition_mappings: array<object>（2 项）
          - []: object
        - statistical_analysis_report: object
          - definition_sentence_count: number，示例 2
          - concept_count: number，示例 2
          - mapping_count: number，示例 2
          - section_distribution: array<undefined>
        - document: object
          - title: string，示例 "第 1 篇文献题目"
        - document_title: string，示例 "第 1 篇文献题目"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_484b94744c074257b2c3664fe2fb3026",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_29470c9a7a624b13aa8b3cc18fd7699b",
        "result": {
          "definitions": [
            {
              "concept": "模糊C-均值聚类",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。",
                  "definition": "模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。",
                  "pattern": "是...的方法",
                  "source_position": {
                    "start": 24,
                    "end": 68
                  },
                  "confidence": 0.95
                }
              ]
            },
            {
              "concept": "主成分分析",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。",
                  "definition": "主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。",
                  "pattern": "是...的方法",
                  "source_position": {
                    "start": 68,
                    "end": 110
                  },
                  "confidence": 0.95
                }
              ]
            }
          ],
          "definition_results": [
            {
              "concept": "模糊C-均值聚类",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。",
                  "definition": "模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。",
                  "pattern": "是...的方法",
                  "source_position": {
                    "start": 24,
                    "end": 68
                  },
                  "confidence": 0.95
                }
              ]
            },
            {
              "concept": "主成分分析",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。",
                  "definition": "主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。",
                  "pattern": "是...的方法",
                  "source_position": {
                    "start": 68,
                    "end": 110
                  },
                  "confidence": 0.95
                }
              ]
            }
          ],
          "mappings": [
            {
              "concept": "模糊C-均值聚类",
              "definition": "模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。"
            },
            {
              "concept": "主成分分析",
              "definition": "主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。"
            }
          ],
          "concept_definition_mappings": [
            {
              "concept": "模糊C-均值聚类",
              "definition": "模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。"
            },
            {
              "concept": "主成分分析",
              "definition": "主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。"
            }
          ],
          "statistical_analysis_report": {
            "definition_sentence_count": 2,
            "concept_count": 2,
            "mapping_count": 2,
            "section_distribution": []
          },
          "document": {
            "title": "第 1 篇文献题目"
          },
          "document_title": "第 1 篇文献题目"
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_e040d63b414341ebaf17b6b180c626ec",
        "result": {
          "definitions": [
            {
              "concept": "加权基因共表达网络分析",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。",
                  "definition": "加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。",
                  "pattern": "是",
                  "source_position": {
                    "start": 32,
                    "end": 73
                  },
                  "confidence": 0.9
                }
              ]
            },
            {
              "concept": "特征基因",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。",
                  "definition": "特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。",
                  "pattern": "是",
                  "source_position": {
                    "start": 73,
                    "end": 118
                  },
                  "confidence": 0.85
                }
              ]
            }
          ],
          "definition_results": [
            {
              "concept": "加权基因共表达网络分析",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。",
                  "definition": "加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。",
                  "pattern": "是",
                  "source_position": {
                    "start": 32,
                    "end": 73
                  },
                  "confidence": 0.9
                }
              ]
            },
            {
              "concept": "特征基因",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。",
                  "definition": "特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。",
                  "pattern": "是",
                  "source_position": {
                    "start": 73,
                    "end": 118
                  },
                  "confidence": 0.85
                }
              ]
            }
          ],
          "mappings": [
            {
              "concept": "加权基因共表达网络分析",
              "definition": "加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。"
            },
            {
              "concept": "特征基因",
              "definition": "特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。"
            }
          ],
          "concept_definition_mappings": [
            {
              "concept": "加权基因共表达网络分析",
              "definition": "加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。"
            },
            {
              "concept": "特征基因",
              "definition": "特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。"
            }
          ],
          "statistical_analysis_report": {
            "definition_sentence_count": 2,
            "concept_count": 2,
            "mapping_count": 2,
            "section_distribution": []
          },
          "document": {
            "title": "第 2 篇文献题目"
          },
          "document_title": "第 2 篇文献题目"
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_39804e58460041edac09843748e5311d",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 7365,
    "created_at": "2026-10-27T22:05:28.196910+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_484b94744c074257b2c3664fe2fb3026",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 12.3 单文件

- **接口**：`POST /api/v1/concept-definition/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scientific_document_fragment_or_batch_text` | file | 必填 | 科技文献全文片段或文件（上传 PDF/DOCX/TXT） |
| `domain_label` | string | 选填 | 领域标签。枚举:"自动识别"(默认)或 "01"–"32"。注入识别提示词作为领域语境,概念判定优先考虑该领域术语;随结果返回 |
| `output_format_requirement` | string | 选填 | 输出格式要求。枚举:"JSON"(默认)、"CSV"(结果附 csv_content 字段)、"数据库写入结构"(结果附 database_records 字段,含 concept_id 等 DB 就绪字段) |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/concept-definition/file' \
  -F 'scientific_document_fragment_or_batch_text=@paper.pdf' \
  -F 'domain_label=' \
  -F 'output_format_requirement=JSON'
```

#### 响应字段（data）

```
- data: object
  - definitions: array<object>（6 项）
    - []: object
      - concept: string，示例 "augmentation workflow / uniform weightin…"
      - definition_count: number，示例 1
      - definitions: array<object>
        - []: object
          - sentence: string，示例 "In the synthetic data and model collapse…"
          - definition: string，示例 "In the synthetic data and model collapse…"
          - pattern: string，示例 "称为"
          - source_position: object
          - confidence: number，示例 0.85
  - definition_results: array<object>（6 项）
    - []: object
      - concept: string，示例 "augmentation workflow / uniform weightin…"
      - definition_count: number，示例 1
      - definitions: array<object>
        - []: object
          - sentence: string，示例 "In the synthetic data and model collapse…"
          - definition: string，示例 "In the synthetic data and model collapse…"
          - pattern: string，示例 "称为"
          - source_position: object
          - confidence: number，示例 0.85
  - mappings: array<object>（6 项）
    - []: object
      - concept: string，示例 "augmentation workflow / uniform weightin…"
      - definition: string，示例 "In the synthetic data and model collapse…"
  - concept_definition_mappings: array<object>（6 项）
    - []: object
      - concept: string，示例 "augmentation workflow / uniform weightin…"
      - definition: string，示例 "In the synthetic data and model collapse…"
  - statistical_analysis_report: object
    - definition_sentence_count: number，示例 6
    - concept_count: number，示例 6
    - mapping_count: number，示例 6
    - section_distribution: array<undefined>
  - document: object
    - title: string，示例 "7.pdf"
  - document_title: string，示例 "7.pdf"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "definitions": [
      {
        "concept": "augmentation workflow / uniform weighting",
        "definition_count": 1,
        "definitions": [
          {
            "sentence": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…",
            "definition": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…",
            "pattern": "称为",
            "source_position": {
              "start": 5189,
              "end": 5448
            },
            "confidence": 0.85
          }
        ]
      },
      {
        "concept": "learning algorithm",
        "definition_count": 1,
        "definitions": [
          {
            "sentence": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )*→{0, 1}X .",
            "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )*→{0, 1}X .",
            "pattern": "定义为",
            "source_position": {
              "start": 20892,
              "end": 21009
            },
            "confidence": 0.95
          }
        ]
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "definition_results": [
      {
        "concept": "augmentation workflow / uniform weighting",
        "definition_count": 1,
        "definitions": [
          {
            "sentence": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…",
            "definition": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…",
            "pattern": "称为",
            "source_position": {
              "start": 5189,
              "end": 5448
            },
            "confidence": 0.85
          }
        ]
      },
      {
        "concept": "learning algorithm",
        "definition_count": 1,
        "definitions": [
          {
            "sentence": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )*→{0, 1}X .",
            "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )*→{0, 1}X .",
            "pattern": "定义为",
            "source_position": {
              "start": 20892,
              "end": 21009
            },
            "confidence": 0.95
          }
        ]
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "mappings": [
      {
        "concept": "augmentation workflow / uniform weighting",
        "definition": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…"
      },
      {
        "concept": "learning algorithm",
        "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )*→{0, 1}X ."
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "concept_definition_mappings": [
      {
        "concept": "augmentation workflow / uniform weighting",
        "definition": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…"
      },
      {
        "concept": "learning algorithm",
        "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )*→{0, 1}X ."
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "statistical_analysis_report": {
      "definition_sentence_count": 6,
      "concept_count": 6,
      "mapping_count": 6,
      "section_distribution": []
    },
    "document": {
      "title": "7.pdf"
    },
    "document_title": "7.pdf"
  },
  "meta": {
    "request_id": "req_69802fee935e4bf58996046a3f2629ef",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 15107,
    "created_at": "2026-10-27T22:24:27.295098+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_b51a046d06144bd2aa00abe60eab1518",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_599eff95afbc446a80d91d8c9d1a8e9e",
    "file_name": "7.pdf"
  }
}
```

### 12.4 批量文件

- **接口**：`POST /api/v1/concept-definition/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scientific_document_fragment_or_batch_text` | file[] | 必填 | 科技文献全文片段或文件（上传 PDF/DOCX/TXT） |
| `domain_label` | string | 选填 | 领域标签。枚举:"自动识别"(默认)或 "01"–"32"。注入识别提示词作为领域语境,概念判定优先考虑该领域术语;随结果返回 |
| `output_format_requirement` | string | 选填 | 输出格式要求。枚举:"JSON"(默认)、"CSV"(结果附 csv_content 字段)、"数据库写入结构"(结果附 database_records 字段,含 concept_id 等 DB 就绪字段) |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/concept-definition/files' \
  -F 'scientific_document_fragment_or_batch_text=@paper_01.pdf' \
  -F 'scientific_document_fragment_or_batch_text=@paper_02.docx' \
  -F 'scientific_document_fragment_or_batch_text=@paper_03.pdf' \
  -F 'domain_label=' \
  -F 'output_format_requirement=JSON'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_f505b425c8364f0b9e809e94be888383"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_c600f50ae232419fb6387dd3a4f8f62b"
      - result: object
        - definitions: array<object>（5 项）
          - []: object
        - definition_results: array<object>（5 项）
          - []: object
        - mappings: array<object>（5 项）
          - []: object
        - concept_definition_mappings: array<object>（5 项）
          - []: object
        - statistical_analysis_report: object
          - definition_sentence_count: number，示例 5
          - concept_count: number，示例 5
          - mapping_count: number，示例 5
          - section_distribution: array<undefined>
        - document: object
          - title: string，示例 "7.pdf"
        - document_title: string，示例 "7.pdf"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_f505b425c8364f0b9e809e94be888383",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_c600f50ae232419fb6387dd3a4f8f62b",
        "result": {
          "definitions": [
            {
              "concept": "augmentation workflow / uniform weighting",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…",
                  "definition": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…",
                  "pattern": "称为",
                  "source_position": {
                    "start": 5189,
                    "end": 5461
                  },
                  "confidence": 0.75
                }
              ]
            },
            {
              "concept": "learning algorithm",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X .",
                  "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X .",
                  "pattern": "定义为",
                  "source_position": {
                    "start": 20892,
                    "end": 21010
                  },
                  "confidence": 0.95
                }
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "definition_results": [
            {
              "concept": "augmentation workflow / uniform weighting",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…",
                  "definition": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…",
                  "pattern": "称为",
                  "source_position": {
                    "start": 5189,
                    "end": 5461
                  },
                  "confidence": 0.75
                }
              ]
            },
            {
              "concept": "learning algorithm",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X .",
                  "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X .",
                  "pattern": "定义为",
                  "source_position": {
                    "start": 20892,
                    "end": 21010
                  },
                  "confidence": 0.95
                }
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "concept": "augmentation workflow / uniform weighting",
              "definition": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…"
            },
            {
              "concept": "learning algorithm",
              "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X ."
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "concept_definition_mappings": [
            {
              "concept": "augmentation workflow / uniform weighting",
              "definition": "In the synthetic data and model collapse literature this approach, gathering a dataset across multiple generations of models and weighing its examples uniformly…"
            },
            {
              "concept": "learning algorithm",
              "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X ."
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "statistical_analysis_report": {
            "definition_sentence_count": 5,
            "concept_count": 5,
            "mapping_count": 5,
            "section_distribution": []
          },
          "document": {
            "title": "7.pdf"
          },
          "document_title": "7.pdf"
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_9af3968de3334844822eddd2da7a19ba",
        "result": {
          "definitions": [
            {
              "concept": "learning algorithm",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X .",
                  "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X .",
                  "pattern": "定义为（define ... to be）",
                  "source_position": {
                    "start": 20892,
                    "end": 21010
                  },
                  "confidence": 0.95
                }
              ]
            },
            {
              "concept": "empirical risk minimization",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "A common learning algorithm is empirical risk minimization, denoted AERM, and defined AERM(S, f0, . . . , ft−1) = arg min ˆL(f, S).",
                  "definition": "A common learning algorithm is empirical risk minimization, denoted AERM, and defined AERM(S, f0, . . . , ft−1) = arg min ˆL(f, S).",
                  "pattern": "定义为/称为（denoted）",
                  "source_position": {
                    "start": 21638,
                    "end": 21791
                  },
                  "confidence": 0.9
                }
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "definition_results": [
            {
              "concept": "learning algorithm",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X .",
                  "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X .",
                  "pattern": "定义为（define ... to be）",
                  "source_position": {
                    "start": 20892,
                    "end": 21010
                  },
                  "confidence": 0.95
                }
              ]
            },
            {
              "concept": "empirical risk minimization",
              "definition_count": 1,
              "definitions": [
                {
                  "sentence": "A common learning algorithm is empirical risk minimization, denoted AERM, and defined AERM(S, f0, . . . , ft−1) = arg min ˆL(f, S).",
                  "definition": "A common learning algorithm is empirical risk minimization, denoted AERM, and defined AERM(S, f0, . . . , ft−1) = arg min ˆL(f, S).",
                  "pattern": "定义为/称为（denoted）",
                  "source_position": {
                    "start": 21638,
                    "end": 21791
                  },
                  "confidence": 0.9
                }
              ]
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "concept": "learning algorithm",
              "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X ."
            },
            {
              "concept": "empirical risk minimization",
              "definition": "A common learning algorithm is empirical risk minimization, denoted AERM, and defined AERM(S, f0, . . . , ft−1) = arg min ˆL(f, S)."
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "concept_definition_mappings": [
            {
              "concept": "learning algorithm",
              "definition": "Accordingly, we define a learning algorithm to be a (possibly randomized) function A : 2X×{0,1} ×({0, 1}X )∗→{0, 1}X ."
            },
            {
              "concept": "empirical risk minimization",
              "definition": "A common learning algorithm is empirical risk minimization, denoted AERM, and defined AERM(S, f0, . . . , ft−1) = arg min ˆL(f, S)."
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "statistical_analysis_report": {
            "definition_sentence_count": 5,
            "concept_count": 5,
            "mapping_count": 5,
            "section_distribution": []
          },
          "document": {
            "title": "35.pdf"
          },
          "document_title": "35.pdf"
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_c810d06894ca49d3ae4fbebe92fb7bef",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 16036,
    "created_at": "2026-10-27T22:24:43.357840+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_f505b425c8364f0b9e809e94be888383",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 13. 中英文通用领域命名实体识别

**工具ID**：`general-ner`

识别中英文科技文本中的人名、地名、机构名和事件等通用实体，并返回实体位置与上下文。

**功能特点**：四类通用实体识别，标准词映射，位置溯源

**适用场景**：通用信息抽取与图谱构建

### 13.1 单文本

- **接口**：`POST /api/v1/ner/general/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `bilingual_scientific_document_text` | string | 必填 | 中英文科技文献文本 |
| `general_domain_annotated_corpus` | file (.json) | 选填 | 可选上传资源：通用领域标注语料（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/general/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "科技文献题目",
  "bilingual_scientific_document_text": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析。"
}
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "科技文献题目"
  - document: object
    - title: string，示例 "科技文献题目"
  - entities: array<object>（5 项）
    - []: object
      - text: string，示例 "美国太平洋地震工程研究中心"
      - type: string，示例 "ORGANIZATION"
      - start: number，示例 13
      - end: number，示例 26
      - context: string，示例 "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震…"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "机构名称"
      - confidence: number，示例 0.9
  - entity_results: array<object>（5 项）
    - []: object
      - text: string，示例 "美国太平洋地震工程研究中心"
      - type: string，示例 "ORGANIZATION"
      - start: number，示例 13
      - end: number，示例 26
      - context: string，示例 "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震…"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "机构名称"
      - confidence: number，示例 0.9
  - mappings: array<object>（5 项）
    - []: object
      - text: string，示例 "美国太平洋地震工程研究中心"
      - type: string，示例 "ORGANIZATION"
      - start: number，示例 13
      - end: number，示例 26
      - context: string，示例 "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震…"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "机构名称"
      - confidence: number，示例 0.9
  - entity_mappings: array<object>（5 项）
    - []: object
      - text: string，示例 "美国太平洋地震工程研究中心"
      - type: string，示例 "ORGANIZATION"
      - start: number，示例 13
      - end: number，示例 26
      - context: string，示例 "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震…"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "机构名称"
      - confidence: number，示例 0.9
  - summary: object
    - entity_count: number，示例 5
    - by_type: object
      - ORGANIZATION: number，示例 1
      - PERSON: number，示例 3
      - LOCATION: number，示例 1
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "科技文献题目",
    "document": {
      "title": "科技文献题目"
    },
    "entities": [
      {
        "text": "美国太平洋地震工程研究中心",
        "type": "ORGANIZATION",
        "start": 13,
        "end": 26,
        "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
        "entity_id": null,
        "entity_type_name": "机构名称",
        "confidence": 0.9
      },
      {
        "text": "刘亭亭",
        "type": "PERSON",
        "start": 0,
        "end": 3,
        "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
        "entity_id": null,
        "entity_type_name": "人名",
        "confidence": 0.9
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "entity_results": [
      {
        "text": "美国太平洋地震工程研究中心",
        "type": "ORGANIZATION",
        "start": 13,
        "end": 26,
        "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
        "entity_id": null,
        "entity_type_name": "机构名称",
        "confidence": 0.9
      },
      {
        "text": "刘亭亭",
        "type": "PERSON",
        "start": 0,
        "end": 3,
        "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
        "entity_id": null,
        "entity_type_name": "人名",
        "confidence": 0.9
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "mappings": [
      {
        "text": "美国太平洋地震工程研究中心",
        "type": "ORGANIZATION",
        "start": 13,
        "end": 26,
        "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
        "entity_id": null,
        "entity_type_name": "机构名称",
        "confidence": 0.9
      },
      {
        "text": "刘亭亭",
        "type": "PERSON",
        "start": 0,
        "end": 3,
        "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
        "entity_id": null,
        "entity_type_name": "人名",
        "confidence": 0.9
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "entity_mappings": [
      {
        "text": "美国太平洋地震工程研究中心",
        "type": "ORGANIZATION",
        "start": 13,
        "end": 26,
        "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
        "entity_id": null,
        "entity_type_name": "机构名称",
        "confidence": 0.9
      },
      {
        "text": "刘亭亭",
        "type": "PERSON",
        "start": 0,
        "end": 3,
        "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
        "entity_id": null,
        "entity_type_name": "人名",
        "confidence": 0.9
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "summary": {
      "entity_count": 5,
      "by_type": {
        "ORGANIZATION": 1,
        "PERSON": 3,
        "LOCATION": 1
      }
    }
  },
  "meta": {
    "request_id": "req_99b09cfe539645918d25bcbe0b9dd56a",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 10422,
    "created_at": "2026-10-27T22:05:38.636379+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_ce3a12a8b63c4dc0aa04aaec9338c8cf",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_cf3ba23f39274562abb32b94b84bc656",
    "file_name": null
  }
}
```

### 13.2 批量文本

- **接口**：`POST /api/v1/ner/general/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `bilingual_scientific_document_text` | object[] | 必填 | 中英文科技文献文本 |
| `bilingual_scientific_document_text[].id` | string | 选填 | 批量文本条目编号 |
| `bilingual_scientific_document_text[].text` | string | 必填 | 用户输入的文本内容 |
| `bilingual_scientific_document_text[].title` | string | 选填 | 文献题名 |
| `general_domain_annotated_corpus` | file (.json) | 选填 | 可选上传资源：通用领域标注语料（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/general/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "第 1 篇文献题目",
    "第 2 篇文献题目",
    "第 3 篇文献题目"
  ],
  "bilingual_scientific_document_text": [
    {
      "id": "DEMO_1",
      "text": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究。",
      "title": "第 1 篇文献题目"
    },
    {
      "id": "DEMO_2",
      "text": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析。",
      "title": "第 2 篇文献题目"
    },
    {
      "id": "DEMO_3",
      "text": "桂林医学院研究团队从GEO数据库获取糖尿病肾病转录组数据，并开展糖尿病肾病关键基因研究。",
      "title": "第 3 篇文献题目"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_3d2a413d25b0401790dce0505677d72b"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_da27709681b742cb82b97be4796cc4f2"
      - result: object
        - document_title: string，示例 "第 1 篇文献题目"
        - document: object
          - title: string，示例 "第 1 篇文献题目"
        - entities: array<object>（5 项）
          - []: object
        - entity_results: array<object>（5 项）
          - []: object
        - mappings: array<object>（5 项）
          - []: object
        - entity_mappings: array<object>（5 项）
          - []: object
        - summary: object
          - entity_count: number，示例 5
          - by_type: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_3d2a413d25b0401790dce0505677d72b",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_da27709681b742cb82b97be4796cc4f2",
        "result": {
          "document_title": "第 1 篇文献题目",
          "document": {
            "title": "第 1 篇文献题目"
          },
          "entities": [
            {
              "text": "石河子大学体育学院",
              "type": "ORGANIZATION",
              "start": 13,
              "end": 22,
              "context": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究。",
              "entity_id": null,
              "entity_type_name": "机构名称",
              "confidence": 0.9
            },
            {
              "text": "余洪涛",
              "type": "PERSON",
              "start": 0,
              "end": 3,
              "context": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究",
              "entity_id": null,
              "entity_type_name": "人名",
              "confidence": 0.9
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "石河子大学体育学院",
              "type": "ORGANIZATION",
              "start": 13,
              "end": 22,
              "context": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究。",
              "entity_id": null,
              "entity_type_name": "机构名称",
              "confidence": 0.9
            },
            {
              "text": "余洪涛",
              "type": "PERSON",
              "start": 0,
              "end": 3,
              "context": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究",
              "entity_id": null,
              "entity_type_name": "人名",
              "confidence": 0.9
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "石河子大学体育学院",
              "type": "ORGANIZATION",
              "start": 13,
              "end": 22,
              "context": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究。",
              "entity_id": null,
              "entity_type_name": "机构名称",
              "confidence": 0.9
            },
            {
              "text": "余洪涛",
              "type": "PERSON",
              "start": 0,
              "end": 3,
              "context": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究",
              "entity_id": null,
              "entity_type_name": "人名",
              "confidence": 0.9
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "entity_mappings": [
            {
              "text": "石河子大学体育学院",
              "type": "ORGANIZATION",
              "start": 13,
              "end": 22,
              "context": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究。",
              "entity_id": null,
              "entity_type_name": "机构名称",
              "confidence": 0.9
            },
            {
              "text": "余洪涛",
              "type": "PERSON",
              "start": 0,
              "end": 3,
              "context": "余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究",
              "entity_id": null,
              "entity_type_name": "人名",
              "confidence": 0.9
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 5,
            "by_type": {
              "ORGANIZATION": 1,
              "PERSON": 3,
              "LOCATION": 1
            }
          }
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_9dc16516d1c14707a0cb16071fd07ff5",
        "result": {
          "document_title": "第 2 篇文献题目",
          "document": {
            "title": "第 2 篇文献题目"
          },
          "entities": [
            {
              "text": "美国太平洋地震工程研究中心",
              "type": "ORGANIZATION",
              "start": 13,
              "end": 26,
              "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
              "entity_id": null,
              "entity_type_name": "机构名称",
              "confidence": 0.9
            },
            {
              "text": "刘亭亭",
              "type": "PERSON",
              "start": 0,
              "end": 3,
              "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的PEER数据库开展地震动记录研究，并在南京完成了实验分析",
              "entity_id": null,
              "entity_type_name": "人名",
              "confidence": 0.9
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "美国太平洋地震工程研究中心",
              "type": "ORGANIZATION",
              "start": 13,
              "end": 26,
              "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
              "entity_id": null,
              "entity_type_name": "机构名称",
              "confidence": 0.9
            },
            {
              "text": "刘亭亭",
              "type": "PERSON",
              "start": 0,
              "end": 3,
              "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的PEER数据库开展地震动记录研究，并在南京完成了实验分析",
              "entity_id": null,
              "entity_type_name": "人名",
              "confidence": 0.9
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "美国太平洋地震工程研究中心",
              "type": "ORGANIZATION",
              "start": 13,
              "end": 26,
              "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
              "entity_id": null,
              "entity_type_name": "机构名称",
              "confidence": 0.9
            },
            {
              "text": "刘亭亭",
              "type": "PERSON",
              "start": 0,
              "end": 3,
              "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的PEER数据库开展地震动记录研究，并在南京完成了实验分析",
              "entity_id": null,
              "entity_type_name": "人名",
              "confidence": 0.9
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "entity_mappings": [
            {
              "text": "美国太平洋地震工程研究中心",
              "type": "ORGANIZATION",
              "start": 13,
              "end": 26,
              "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析",
              "entity_id": null,
              "entity_type_name": "机构名称",
              "confidence": 0.9
            },
            {
              "text": "刘亭亭",
              "type": "PERSON",
              "start": 0,
              "end": 3,
              "context": "刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的PEER数据库开展地震动记录研究，并在南京完成了实验分析",
              "entity_id": null,
              "entity_type_name": "人名",
              "confidence": 0.9
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 5,
            "by_type": {
              "ORGANIZATION": 1,
              "PERSON": 3,
              "LOCATION": 1
            }
          }
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_0adc1e76e5854c449639790152ccc7a4",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 7864,
    "created_at": "2026-10-27T22:05:46.515081+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_3d2a413d25b0401790dce0505677d72b",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 13.3 单文件

- **接口**：`POST /api/v1/ner/general/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `bilingual_scientific_document_text` | file | 必填 | 中英文科技文献文件（上传 PDF/DOCX/TXT） |
| `general_domain_annotated_corpus` | file (.json) | 选填 | 可选上传资源：通用领域标注语料（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/general/file' \
  -F 'bilingual_scientific_document_text=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "7.pdf"
  - document: object
    - title: string，示例 "7.pdf"
  - entities: array<object>（29 项）
    - []: object
      - text: string，示例 "Sergei Vassilvitskii"
      - type: string，示例 "PERSON"
      - confidence: number，示例 0.95
      - start: number，示例 121
      - end: number，示例 141
      - context: string，示例 "Kareem Amin Alex Bie Weiwei Kong Umar Sy…"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "人名"
  - entity_results: array<object>（29 项）
    - []: object
      - text: string，示例 "Sergei Vassilvitskii"
      - type: string，示例 "PERSON"
      - confidence: number，示例 0.95
      - start: number，示例 121
      - end: number，示例 141
      - context: string，示例 "Kareem Amin Alex Bie Weiwei Kong Umar Sy…"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "人名"
  - mappings: array<object>（29 项）
    - []: object
      - text: string，示例 "Sergei Vassilvitskii"
      - type: string，示例 "PERSON"
      - confidence: number，示例 0.95
      - start: number，示例 121
      - end: number，示例 141
      - context: string，示例 "Kareem Amin Alex Bie Weiwei Kong Umar Sy…"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "人名"
  - entity_mappings: array<object>（29 项）
    - []: object
      - text: string，示例 "Sergei Vassilvitskii"
      - type: string，示例 "PERSON"
      - confidence: number，示例 0.95
      - start: number，示例 121
      - end: number，示例 141
      - context: string，示例 "Kareem Amin Alex Bie Weiwei Kong Umar Sy…"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "人名"
  - summary: object
    - entity_count: number，示例 29
    - by_type: object
      - PERSON: number，示例 28
      - ORGANIZATION: number，示例 1
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "7.pdf",
    "document": {
      "title": "7.pdf"
    },
    "entities": [
      {
        "text": "Sergei Vassilvitskii",
        "type": "PERSON",
        "confidence": 0.95,
        "start": 121,
        "end": 141,
        "context": "Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
        "entity_id": null,
        "entity_type_name": "人名"
      },
      {
        "text": "Google Research",
        "type": "ORGANIZATION",
        "confidence": 0.95,
        "start": 178,
        "end": 193,
        "context": "Google Research",
        "entity_id": null,
        "entity_type_name": "机构名称"
      },
      "…（共 29 项，示例保留前 2 项）"
    ],
    "entity_results": [
      {
        "text": "Sergei Vassilvitskii",
        "type": "PERSON",
        "confidence": 0.95,
        "start": 121,
        "end": 141,
        "context": "Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
        "entity_id": null,
        "entity_type_name": "人名"
      },
      {
        "text": "Google Research",
        "type": "ORGANIZATION",
        "confidence": 0.95,
        "start": 178,
        "end": 193,
        "context": "Google Research",
        "entity_id": null,
        "entity_type_name": "机构名称"
      },
      "…（共 29 项，示例保留前 2 项）"
    ],
    "mappings": [
      {
        "text": "Sergei Vassilvitskii",
        "type": "PERSON",
        "confidence": 0.95,
        "start": 121,
        "end": 141,
        "context": "Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
        "entity_id": null,
        "entity_type_name": "人名"
      },
      {
        "text": "Google Research",
        "type": "ORGANIZATION",
        "confidence": 0.95,
        "start": 178,
        "end": 193,
        "context": "Google Research",
        "entity_id": null,
        "entity_type_name": "机构名称"
      },
      "…（共 29 项，示例保留前 2 项）"
    ],
    "entity_mappings": [
      {
        "text": "Sergei Vassilvitskii",
        "type": "PERSON",
        "confidence": 0.95,
        "start": 121,
        "end": 141,
        "context": "Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
        "entity_id": null,
        "entity_type_name": "人名"
      },
      {
        "text": "Google Research",
        "type": "ORGANIZATION",
        "confidence": 0.95,
        "start": 178,
        "end": 193,
        "context": "Google Research",
        "entity_id": null,
        "entity_type_name": "机构名称"
      },
      "…（共 29 项，示例保留前 2 项）"
    ],
    "summary": {
      "entity_count": 29,
      "by_type": {
        "PERSON": 28,
        "ORGANIZATION": 1
      }
    }
  },
  "meta": {
    "request_id": "req_60e52d08cfd04a149da1c41c03db1111",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 30494,
    "created_at": "2026-10-27T22:25:13.866039+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_58b1e506b75346698b215e9ddc9da97a",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_5cf35a3672a34f3298f5fce53f53007e",
    "file_name": "7.pdf"
  }
}
```

### 13.4 批量文件

- **接口**：`POST /api/v1/ner/general/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `bilingual_scientific_document_text` | file[] | 必填 | 中英文科技文献文件（上传 PDF/DOCX/TXT） |
| `general_domain_annotated_corpus` | file (.json) | 选填 | 可选上传资源：通用领域标注语料（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/general/files' \
  -F 'bilingual_scientific_document_text=@paper_01.pdf' \
  -F 'bilingual_scientific_document_text=@paper_02.docx' \
  -F 'bilingual_scientific_document_text=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_6edbf071dba94e19bc67f4608537d172"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_b6a8a8754de848219035895c57dc5bc7"
      - result: object
        - document_title: string，示例 "7.pdf"
        - document: object
          - title: string，示例 "7.pdf"
        - entities: array<object>（29 项）
          - []: object
        - entity_results: array<object>（29 项）
          - []: object
        - mappings: array<object>（29 项）
          - []: object
        - entity_mappings: array<object>（29 项）
          - []: object
        - summary: object
          - entity_count: number，示例 29
          - by_type: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_6edbf071dba94e19bc67f4608537d172",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_b6a8a8754de848219035895c57dc5bc7",
        "result": {
          "document_title": "7.pdf",
          "document": {
            "title": "7.pdf"
          },
          "entities": [
            {
              "text": "Sergei Vassilvitskii",
              "type": "PERSON",
              "confidence": 0.98,
              "start": 121,
              "end": 141,
              "context": "Sergei Vassilvitskii",
              "entity_id": null,
              "entity_type_name": "人名"
            },
            {
              "text": "Google Research",
              "type": "ORGANIZATION",
              "confidence": 0.98,
              "start": 178,
              "end": 193,
              "context": "Google Research",
              "entity_id": null,
              "entity_type_name": "机构名称"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "Sergei Vassilvitskii",
              "type": "PERSON",
              "confidence": 0.98,
              "start": 121,
              "end": 141,
              "context": "Sergei Vassilvitskii",
              "entity_id": null,
              "entity_type_name": "人名"
            },
            {
              "text": "Google Research",
              "type": "ORGANIZATION",
              "confidence": 0.98,
              "start": 178,
              "end": 193,
              "context": "Google Research",
              "entity_id": null,
              "entity_type_name": "机构名称"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "Sergei Vassilvitskii",
              "type": "PERSON",
              "confidence": 0.98,
              "start": 121,
              "end": 141,
              "context": "Sergei Vassilvitskii",
              "entity_id": null,
              "entity_type_name": "人名"
            },
            {
              "text": "Google Research",
              "type": "ORGANIZATION",
              "confidence": 0.98,
              "start": 178,
              "end": 193,
              "context": "Google Research",
              "entity_id": null,
              "entity_type_name": "机构名称"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "entity_mappings": [
            {
              "text": "Sergei Vassilvitskii",
              "type": "PERSON",
              "confidence": 0.98,
              "start": 121,
              "end": 141,
              "context": "Sergei Vassilvitskii",
              "entity_id": null,
              "entity_type_name": "人名"
            },
            {
              "text": "Google Research",
              "type": "ORGANIZATION",
              "confidence": 0.98,
              "start": 178,
              "end": 193,
              "context": "Google Research",
              "entity_id": null,
              "entity_type_name": "机构名称"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 29,
            "by_type": {
              "PERSON": 28,
              "ORGANIZATION": 1
            }
          }
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_660e3da171264877a2683099dd65d7a1",
        "result": {
          "document_title": "35.pdf",
          "document": {
            "title": "35.pdf"
          },
          "entities": [
            {
              "text": "Sergei Vassilvitskii",
              "type": "PERSON",
              "confidence": 0.95,
              "start": 121,
              "end": 141,
              "context": "Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
              "entity_id": null,
              "entity_type_name": "人名"
            },
            {
              "text": "Google Research",
              "type": "ORGANIZATION",
              "confidence": 0.9,
              "start": 178,
              "end": 193,
              "context": "Kareem Amin, Alex Bie, Weiwei Kong, Umar Syed, Sergei Vassilvitskii, Google Research",
              "entity_id": null,
              "entity_type_name": "机构名称"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "Sergei Vassilvitskii",
              "type": "PERSON",
              "confidence": 0.95,
              "start": 121,
              "end": 141,
              "context": "Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
              "entity_id": null,
              "entity_type_name": "人名"
            },
            {
              "text": "Google Research",
              "type": "ORGANIZATION",
              "confidence": 0.9,
              "start": 178,
              "end": 193,
              "context": "Kareem Amin, Alex Bie, Weiwei Kong, Umar Syed, Sergei Vassilvitskii, Google Research",
              "entity_id": null,
              "entity_type_name": "机构名称"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "Sergei Vassilvitskii",
              "type": "PERSON",
              "confidence": 0.95,
              "start": 121,
              "end": 141,
              "context": "Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
              "entity_id": null,
              "entity_type_name": "人名"
            },
            {
              "text": "Google Research",
              "type": "ORGANIZATION",
              "confidence": 0.9,
              "start": 178,
              "end": 193,
              "context": "Kareem Amin, Alex Bie, Weiwei Kong, Umar Syed, Sergei Vassilvitskii, Google Research",
              "entity_id": null,
              "entity_type_name": "机构名称"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "entity_mappings": [
            {
              "text": "Sergei Vassilvitskii",
              "type": "PERSON",
              "confidence": 0.95,
              "start": 121,
              "end": 141,
              "context": "Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
              "entity_id": null,
              "entity_type_name": "人名"
            },
            {
              "text": "Google Research",
              "type": "ORGANIZATION",
              "confidence": 0.9,
              "start": 178,
              "end": 193,
              "context": "Kareem Amin, Alex Bie, Weiwei Kong, Umar Syed, Sergei Vassilvitskii, Google Research",
              "entity_id": null,
              "entity_type_name": "机构名称"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 29,
            "by_type": {
              "PERSON": 28,
              "ORGANIZATION": 1
            }
          }
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_95a9d8b3ad69497c997c2bcd25530076",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 38184,
    "created_at": "2026-10-27T22:25:52.070430+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_6edbf071dba94e19bc67f4608537d172",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 14. 中英文通用科研实体识别

**工具ID**：`research-ner`

识别科研方法、数据资料、仪器设备、理论原理和研究问题等通用科研实体。

**功能特点**：五类科研实体识别，标准词映射，全文抽取

**适用场景**：科研信息抽取与图谱构建

### 14.1 单文本

- **接口**：`POST /api/v1/ner/research/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `academic_abstract_or_technical_report_text` | string | 必填 | 中英文学术论文摘要或技术报告文本 |
| `multi_domain_scientific_corpus` | file (.json) | 选填 | 可选上传资源：多领域科研语料（.json） |
| `manually_labeled_data` | file (.json) | 选填 | 可选上传资源：科研实体标准词表（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/research/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "科技文献题目",
  "academic_abstract_or_technical_report_text": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异。"
}
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "科技文献题目"
  - document: object
    - title: string，示例 "科技文献题目"
  - entities: array<object>（5 项）
    - []: object
      - text: string，示例 "地震动记录自适应选取"
      - type: string，示例 "TOPIC"
      - confidence: number，示例 0.85
      - standard_names: object
        - zh: string，示例 "地震动记录自适应选取"
        - en: string，示例 "adaptive selection of ground motion reco…"
      - start: number，示例 44
      - end: number，示例 54
      - context: string，示例 "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处…"
      - mapping_status: string，示例 "已映射"
      - mapping_confidence: number，示例 0.85
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "研究问题"
  - entity_results: array<object>（5 项）
    - []: object
      - text: string，示例 "地震动记录自适应选取"
      - type: string，示例 "TOPIC"
      - confidence: number，示例 0.85
      - standard_names: object
        - zh: string，示例 "地震动记录自适应选取"
        - en: string，示例 "adaptive selection of ground motion reco…"
      - start: number，示例 44
      - end: number，示例 54
      - context: string，示例 "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处…"
      - mapping_status: string，示例 "已映射"
      - mapping_confidence: number，示例 0.85
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "研究问题"
  - mappings: array<object>（5 项）
    - []: object
      - text: string，示例 "地震动记录自适应选取"
      - type: string，示例 "TOPIC"
      - confidence: number，示例 0.85
      - standard_names: object
        - zh: string，示例 "地震动记录自适应选取"
        - en: string，示例 "adaptive selection of ground motion reco…"
      - start: number，示例 44
      - end: number，示例 54
      - context: string，示例 "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处…"
      - mapping_status: string，示例 "已映射"
      - mapping_confidence: number，示例 0.85
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "研究问题"
  - standard_term_mappings: array<object>（5 项）
    - []: object
      - text: string，示例 "地震动记录自适应选取"
      - type: string，示例 "TOPIC"
      - confidence: number，示例 0.85
      - standard_names: object
        - zh: string，示例 "地震动记录自适应选取"
        - en: string，示例 "adaptive selection of ground motion reco…"
      - start: number，示例 44
      - end: number，示例 54
      - context: string，示例 "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处…"
      - mapping_status: string，示例 "已映射"
      - mapping_confidence: number，示例 0.85
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "研究问题"
  - summary: object
    - entity_count: number，示例 5
    - by_type: object
      - TOPIC: number，示例 2
      - DATASET: number，示例 1
      - METHOD: number，示例 2
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "科技文献题目",
    "document": {
      "title": "科技文献题目"
    },
    "entities": [
      {
        "text": "地震动记录自适应选取",
        "type": "TOPIC",
        "confidence": 0.85,
        "standard_names": {
          "zh": "地震动记录自适应选取",
          "en": "adaptive selection of ground motion records"
        },
        "start": 44,
        "end": 54,
        "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
        "mapping_status": "已映射",
        "mapping_confidence": 0.85,
        "entity_id": null,
        "entity_type_name": "研究问题"
      },
      {
        "text": "PEER数据库",
        "type": "DATASET",
        "confidence": 0.95,
        "standard_names": {
          "zh": "PEER强地震动数据库",
          "en": "PEER Ground Motion Database"
        },
        "start": 4,
        "end": 11,
        "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
        "mapping_status": "已映射",
        "mapping_confidence": 0.9,
        "entity_id": null,
        "entity_type_name": "数据资料"
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "entity_results": [
      {
        "text": "地震动记录自适应选取",
        "type": "TOPIC",
        "confidence": 0.85,
        "standard_names": {
          "zh": "地震动记录自适应选取",
          "en": "adaptive selection of ground motion records"
        },
        "start": 44,
        "end": 54,
        "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
        "mapping_status": "已映射",
        "mapping_confidence": 0.85,
        "entity_id": null,
        "entity_type_name": "研究问题"
      },
      {
        "text": "PEER数据库",
        "type": "DATASET",
        "confidence": 0.95,
        "standard_names": {
          "zh": "PEER强地震动数据库",
          "en": "PEER Ground Motion Database"
        },
        "start": 4,
        "end": 11,
        "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
        "mapping_status": "已映射",
        "mapping_confidence": 0.9,
        "entity_id": null,
        "entity_type_name": "数据资料"
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "mappings": [
      {
        "text": "地震动记录自适应选取",
        "type": "TOPIC",
        "confidence": 0.85,
        "standard_names": {
          "zh": "地震动记录自适应选取",
          "en": "adaptive selection of ground motion records"
        },
        "start": 44,
        "end": 54,
        "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
        "mapping_status": "已映射",
        "mapping_confidence": 0.85,
        "entity_id": null,
        "entity_type_name": "研究问题"
      },
      {
        "text": "PEER数据库",
        "type": "DATASET",
        "confidence": 0.95,
        "standard_names": {
          "zh": "PEER强地震动数据库",
          "en": "PEER Ground Motion Database"
        },
        "start": 4,
        "end": 11,
        "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
        "mapping_status": "已映射",
        "mapping_confidence": 0.9,
        "entity_id": null,
        "entity_type_name": "数据资料"
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "standard_term_mappings": [
      {
        "text": "地震动记录自适应选取",
        "type": "TOPIC",
        "confidence": 0.85,
        "standard_names": {
          "zh": "地震动记录自适应选取",
          "en": "adaptive selection of ground motion records"
        },
        "start": 44,
        "end": 54,
        "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
        "mapping_status": "已映射",
        "mapping_confidence": 0.85,
        "entity_id": null,
        "entity_type_name": "研究问题"
      },
      {
        "text": "PEER数据库",
        "type": "DATASET",
        "confidence": 0.95,
        "standard_names": {
          "zh": "PEER强地震动数据库",
          "en": "PEER Ground Motion Database"
        },
        "start": 4,
        "end": 11,
        "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
        "mapping_status": "已映射",
        "mapping_confidence": 0.9,
        "entity_id": null,
        "entity_type_name": "数据资料"
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "summary": {
      "entity_count": 5,
      "by_type": {
        "TOPIC": 2,
        "DATASET": 1,
        "METHOD": 2
      }
    }
  },
  "meta": {
    "request_id": "req_f3c17fbd15c44834a5ab2ec9e79ae978",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 26763,
    "created_at": "2026-10-27T22:06:13.300273+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_95daea4545bc4f2ba7f0405e01b8e0ec",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_b23929318a3641068c18c6b711629f14",
    "file_name": null
  }
}
```

### 14.2 批量文本

- **接口**：`POST /api/v1/ner/research/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `academic_abstract_or_technical_report_text` | object[] | 必填 | 中英文学术论文摘要或技术报告文本 |
| `academic_abstract_or_technical_report_text[].id` | string | 选填 | 批量文本条目编号 |
| `academic_abstract_or_technical_report_text[].title` | string | 选填 | 文献题名 |
| `academic_abstract_or_technical_report_text[].text` | string | 必填 | 用户输入的文本内容 |
| `multi_domain_scientific_corpus` | file (.json) | 选填 | 可选上传资源：多领域科研语料（.json） |
| `manually_labeled_data` | file (.json) | 选填 | 可选上传资源：科研实体标准词表（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/research/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "大数据赋能高校体育场馆智慧化建设的现实困境与路径研究",
    "地震动记录选取的新视角：大数据与机器学习",
    "基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因"
  ],
  "academic_abstract_or_technical_report_text": [
    {
      "id": "DEMO_1",
      "title": "大数据赋能高校体育场馆智慧化建设的现实困境与路径研究",
      "text": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题。"
    },
    {
      "id": "DEMO_2",
      "title": "地震动记录选取的新视角：大数据与机器学习",
      "text": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异。"
    },
    {
      "id": "DEMO_3",
      "title": "基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因",
      "text": "研究从GEO数据库获取转录组数据，采用WGCNA和113种机器学习算法开展糖尿病肾病关键基因识别，并分析VWF的潜在诊疗价值。"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_a84261d9f06847a9ab9ef7ade7a8e79c"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_71e2acf0ada94bf181b6674f8bc5404a"
      - result: object
        - document_title: string，示例 "大数据赋能高校体育场馆智慧化建设的现实困境与路径研究"
        - document: object
          - title: string，示例 "大数据赋能高校体育场馆智慧化建设的现实困境与路径研究"
        - entities: array<object>（6 项）
          - []: object
        - entity_results: array<object>（6 项）
          - []: object
        - mappings: array<object>（6 项）
          - []: object
        - standard_term_mappings: array<object>（6 项）
          - []: object
        - summary: object
          - entity_count: number，示例 6
          - by_type: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_a84261d9f06847a9ab9ef7ade7a8e79c",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_71e2acf0ada94bf181b6674f8bc5404a",
        "result": {
          "document_title": "大数据赋能高校体育场馆智慧化建设的现实困境与路径研究",
          "document": {
            "title": "大数据赋能高校体育场馆智慧化建设的现实困境与路径研究"
          },
          "entities": [
            {
              "text": "高校体育场馆可持续发展",
              "type": "TOPIC",
              "confidence": 0.9,
              "standard_names": {
                "zh": "高校体育场馆可持续发展",
                "en": "Sustainable Development of College Sports Venues"
              },
              "start": 52,
              "end": 63,
              "context": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题",
              "mapping_status": "已映射",
              "mapping_confidence": 0.85,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            {
              "text": "高校体育场馆智慧治理",
              "type": "TOPIC",
              "confidence": 0.95,
              "standard_names": {
                "zh": "高校体育场馆智慧治理",
                "en": "Smart Governance of University Sports Venues"
              },
              "start": 33,
              "end": 43,
              "context": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题。",
              "mapping_status": "已映射",
              "mapping_confidence": 0.85,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            "…（共 6 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "高校体育场馆可持续发展",
              "type": "TOPIC",
              "confidence": 0.9,
              "standard_names": {
                "zh": "高校体育场馆可持续发展",
                "en": "Sustainable Development of College Sports Venues"
              },
              "start": 52,
              "end": 63,
              "context": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题",
              "mapping_status": "已映射",
              "mapping_confidence": 0.85,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            {
              "text": "高校体育场馆智慧治理",
              "type": "TOPIC",
              "confidence": 0.95,
              "standard_names": {
                "zh": "高校体育场馆智慧治理",
                "en": "Smart Governance of University Sports Venues"
              },
              "start": 33,
              "end": 43,
              "context": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题。",
              "mapping_status": "已映射",
              "mapping_confidence": 0.85,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            "…（共 6 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "高校体育场馆可持续发展",
              "type": "TOPIC",
              "confidence": 0.9,
              "standard_names": {
                "zh": "高校体育场馆可持续发展",
                "en": "Sustainable Development of College Sports Venues"
              },
              "start": 52,
              "end": 63,
              "context": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题",
              "mapping_status": "已映射",
              "mapping_confidence": 0.85,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            {
              "text": "高校体育场馆智慧治理",
              "type": "TOPIC",
              "confidence": 0.95,
              "standard_names": {
                "zh": "高校体育场馆智慧治理",
                "en": "Smart Governance of University Sports Venues"
              },
              "start": 33,
              "end": 43,
              "context": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题。",
              "mapping_status": "已映射",
              "mapping_confidence": 0.85,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            "…（共 6 项，示例保留前 2 项）"
          ],
          "standard_term_mappings": [
            {
              "text": "高校体育场馆可持续发展",
              "type": "TOPIC",
              "confidence": 0.9,
              "standard_names": {
                "zh": "高校体育场馆可持续发展",
                "en": "Sustainable Development of College Sports Venues"
              },
              "start": 52,
              "end": 63,
              "context": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题",
              "mapping_status": "已映射",
              "mapping_confidence": 0.85,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            {
              "text": "高校体育场馆智慧治理",
              "type": "TOPIC",
              "confidence": 0.95,
              "standard_names": {
                "zh": "高校体育场馆智慧治理",
                "en": "Smart Governance of University Sports Venues"
              },
              "start": 33,
              "end": 43,
              "context": "研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题。",
              "mapping_status": "已映射",
              "mapping_confidence": 0.85,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            "…（共 6 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 6,
            "by_type": {
              "TOPIC": 3,
              "METHOD": 3
            }
          }
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_dc530e7e31f04a629db70135c7e1a446",
        "result": {
          "document_title": "地震动记录选取的新视角：大数据与机器学习",
          "document": {
            "title": "地震动记录选取的新视角：大数据与机器学习"
          },
          "entities": [
            {
              "text": "地震动记录自适应选取",
              "type": "TOPIC",
              "confidence": 0.9,
              "standard_names": {
                "zh": "地震动记录自适应选取",
                "en": "adaptive selection of ground motion records"
              },
              "start": 44,
              "end": 54,
              "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异。",
              "mapping_status": "已映射",
              "mapping_confidence": 0.9,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            {
              "text": "PEER数据库",
              "type": "DATASET",
              "confidence": 0.95,
              "standard_names": {
                "zh": "PEER强地震动数据库",
                "en": "PEER Ground Motion Database (Pacific Earthquake Engineering Research Center)"
              },
              "start": 4,
              "end": 11,
              "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
              "mapping_status": "已映射",
              "mapping_confidence": 0.9,
              "entity_id": null,
              "entity_type_name": "数据资料"
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "地震动记录自适应选取",
              "type": "TOPIC",
              "confidence": 0.9,
              "standard_names": {
                "zh": "地震动记录自适应选取",
                "en": "adaptive selection of ground motion records"
              },
              "start": 44,
              "end": 54,
              "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异。",
              "mapping_status": "已映射",
              "mapping_confidence": 0.9,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            {
              "text": "PEER数据库",
              "type": "DATASET",
              "confidence": 0.95,
              "standard_names": {
                "zh": "PEER强地震动数据库",
                "en": "PEER Ground Motion Database (Pacific Earthquake Engineering Research Center)"
              },
              "start": 4,
              "end": 11,
              "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
              "mapping_status": "已映射",
              "mapping_confidence": 0.9,
              "entity_id": null,
              "entity_type_name": "数据资料"
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "地震动记录自适应选取",
              "type": "TOPIC",
              "confidence": 0.9,
              "standard_names": {
                "zh": "地震动记录自适应选取",
                "en": "adaptive selection of ground motion records"
              },
              "start": 44,
              "end": 54,
              "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异。",
              "mapping_status": "已映射",
              "mapping_confidence": 0.9,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            {
              "text": "PEER数据库",
              "type": "DATASET",
              "confidence": 0.95,
              "standard_names": {
                "zh": "PEER强地震动数据库",
                "en": "PEER Ground Motion Database (Pacific Earthquake Engineering Research Center)"
              },
              "start": 4,
              "end": 11,
              "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
              "mapping_status": "已映射",
              "mapping_confidence": 0.9,
              "entity_id": null,
              "entity_type_name": "数据资料"
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "standard_term_mappings": [
            {
              "text": "地震动记录自适应选取",
              "type": "TOPIC",
              "confidence": 0.9,
              "standard_names": {
                "zh": "地震动记录自适应选取",
                "en": "adaptive selection of ground motion records"
              },
              "start": 44,
              "end": 54,
              "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异。",
              "mapping_status": "已映射",
              "mapping_confidence": 0.9,
              "entity_id": null,
              "entity_type_name": "研究问题"
            },
            {
              "text": "PEER数据库",
              "type": "DATASET",
              "confidence": 0.95,
              "standard_names": {
                "zh": "PEER强地震动数据库",
                "en": "PEER Ground Motion Database (Pacific Earthquake Engineering Research Center)"
              },
              "start": 4,
              "end": 11,
              "context": "研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异",
              "mapping_status": "已映射",
              "mapping_confidence": 0.9,
              "entity_id": null,
              "entity_type_name": "数据资料"
            },
            "…（共 5 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 5,
            "by_type": {
              "TOPIC": 2,
              "DATASET": 1,
              "METHOD": 2
            }
          }
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_bcc3c3e929d14bcc8f824e27f14933a1",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 30361,
    "created_at": "2026-10-27T22:06:43.673114+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_a84261d9f06847a9ab9ef7ade7a8e79c",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 14.3 单文件

- **接口**：`POST /api/v1/ner/research/file`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `academic_abstract_or_technical_report_text` | file | 必填 | 中英文学术论文或技术报告文本文件（上传 PDF/DOCX/TXT） |
| `multi_domain_scientific_corpus` | file (.json) | 选填 | 可选上传资源：多领域科研语料（.json） |
| `manually_labeled_data` | file (.json) | 选填 | 可选上传资源：科研实体标准词表（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/research/file' \
  -F 'academic_abstract_or_technical_report_text=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "7.pdf"
  - document: object
    - title: string，示例 "7.pdf"
  - entities: array<object>（30 项）
    - []: object
      - text: string，示例 "learning with positive and unlabeled exa…"
      - type: string，示例 "METHOD"
      - confidence: number，示例 0.9
      - start: number，示例 31417
      - end: number，示例 31462
      - standard_names: object
        - zh: string，示例 "正例与未标记样本学习"
        - en: string，示例 "Learning from Positive and Unlabeled Exa…"
      - context: string，示例 "The analysis proceeds via a reduction to…"
      - mapping_status: string，示例 "已映射"
      - mapping_confidence: number，示例 0.95
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "科研方法"
  - entity_results: array<object>（30 项）
    - []: object
      - text: string，示例 "learning with positive and unlabeled exa…"
      - type: string，示例 "METHOD"
      - confidence: number，示例 0.9
      - start: number，示例 31417
      - end: number，示例 31462
      - standard_names: object
        - zh: string，示例 "正例与未标记样本学习"
        - en: string，示例 "Learning from Positive and Unlabeled Exa…"
      - context: string，示例 "The analysis proceeds via a reduction to…"
      - mapping_status: string，示例 "已映射"
      - mapping_confidence: number，示例 0.95
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "科研方法"
  - mappings: array<object>（30 项）
    - []: object
      - text: string，示例 "learning with positive and unlabeled exa…"
      - type: string，示例 "METHOD"
      - confidence: number，示例 0.9
      - start: number，示例 31417
      - end: number，示例 31462
      - standard_names: object
        - zh: string，示例 "正例与未标记样本学习"
        - en: string，示例 "Learning from Positive and Unlabeled Exa…"
      - context: string，示例 "The analysis proceeds via a reduction to…"
      - mapping_status: string，示例 "已映射"
      - mapping_confidence: number，示例 0.95
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "科研方法"
  - standard_term_mappings: array<object>（30 项）
    - []: object
      - text: string，示例 "learning with positive and unlabeled exa…"
      - type: string，示例 "METHOD"
      - confidence: number，示例 0.9
      - start: number，示例 31417
      - end: number，示例 31462
      - standard_names: object
        - zh: string，示例 "正例与未标记样本学习"
        - en: string，示例 "Learning from Positive and Unlabeled Exa…"
      - context: string，示例 "The analysis proceeds via a reduction to…"
      - mapping_status: string，示例 "已映射"
      - mapping_confidence: number，示例 0.95
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "科研方法"
  - summary: object
    - entity_count: number，示例 30
    - by_type: object
      - METHOD: number，示例 13
      - THEORY: number，示例 9
      - TOPIC: number，示例 7
      - DATASET: number，示例 1
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "7.pdf",
    "document": {
      "title": "7.pdf"
    },
    "entities": [
      {
        "text": "learning with positive and unlabeled examples",
        "type": "METHOD",
        "confidence": 0.9,
        "start": 31417,
        "end": 31462,
        "standard_names": {
          "zh": "正例与未标记样本学习",
          "en": "Learning from Positive and Unlabeled Examples"
        },
        "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
        "mapping_status": "已映射",
        "mapping_confidence": 0.95,
        "entity_id": null,
        "entity_type_name": "科研方法"
      },
      {
        "text": "minimum variance unbiased estimator",
        "type": "THEORY",
        "confidence": 0.8,
        "start": 11088,
        "end": 11123,
        "standard_names": {
          "zh": "最小方差无偏估计量",
          "en": "Minimum Variance Unbiased Estimator"
        },
        "context": "Gaussian) it is also the minimum variance unbiased estimator (MVUE) of the",
        "mapping_status": "已映射",
        "mapping_confidence": 0.98,
        "entity_id": null,
        "entity_type_name": "理论原理"
      },
      "…（共 30 项，示例保留前 2 项）"
    ],
    "entity_results": [
      {
        "text": "learning with positive and unlabeled examples",
        "type": "METHOD",
        "confidence": 0.9,
        "start": 31417,
        "end": 31462,
        "standard_names": {
          "zh": "正例与未标记样本学习",
          "en": "Learning from Positive and Unlabeled Examples"
        },
        "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
        "mapping_status": "已映射",
        "mapping_confidence": 0.95,
        "entity_id": null,
        "entity_type_name": "科研方法"
      },
      {
        "text": "minimum variance unbiased estimator",
        "type": "THEORY",
        "confidence": 0.8,
        "start": 11088,
        "end": 11123,
        "standard_names": {
          "zh": "最小方差无偏估计量",
          "en": "Minimum Variance Unbiased Estimator"
        },
        "context": "Gaussian) it is also the minimum variance unbiased estimator (MVUE) of the",
        "mapping_status": "已映射",
        "mapping_confidence": 0.98,
        "entity_id": null,
        "entity_type_name": "理论原理"
      },
      "…（共 30 项，示例保留前 2 项）"
    ],
    "mappings": [
      {
        "text": "learning with positive and unlabeled examples",
        "type": "METHOD",
        "confidence": 0.9,
        "start": 31417,
        "end": 31462,
        "standard_names": {
          "zh": "正例与未标记样本学习",
          "en": "Learning from Positive and Unlabeled Examples"
        },
        "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
        "mapping_status": "已映射",
        "mapping_confidence": 0.95,
        "entity_id": null,
        "entity_type_name": "科研方法"
      },
      {
        "text": "minimum variance unbiased estimator",
        "type": "THEORY",
        "confidence": 0.8,
        "start": 11088,
        "end": 11123,
        "standard_names": {
          "zh": "最小方差无偏估计量",
          "en": "Minimum Variance Unbiased Estimator"
        },
        "context": "Gaussian) it is also the minimum variance unbiased estimator (MVUE) of the",
        "mapping_status": "已映射",
        "mapping_confidence": 0.98,
        "entity_id": null,
        "entity_type_name": "理论原理"
      },
      "…（共 30 项，示例保留前 2 项）"
    ],
    "standard_term_mappings": [
      {
        "text": "learning with positive and unlabeled examples",
        "type": "METHOD",
        "confidence": 0.9,
        "start": 31417,
        "end": 31462,
        "standard_names": {
          "zh": "正例与未标记样本学习",
          "en": "Learning from Positive and Unlabeled Examples"
        },
        "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
        "mapping_status": "已映射",
        "mapping_confidence": 0.95,
        "entity_id": null,
        "entity_type_name": "科研方法"
      },
      {
        "text": "minimum variance unbiased estimator",
        "type": "THEORY",
        "confidence": 0.8,
        "start": 11088,
        "end": 11123,
        "standard_names": {
          "zh": "最小方差无偏估计量",
          "en": "Minimum Variance Unbiased Estimator"
        },
        "context": "Gaussian) it is also the minimum variance unbiased estimator (MVUE) of the",
        "mapping_status": "已映射",
        "mapping_confidence": 0.98,
        "entity_id": null,
        "entity_type_name": "理论原理"
      },
      "…（共 30 项，示例保留前 2 项）"
    ],
    "summary": {
      "entity_count": 30,
      "by_type": {
        "METHOD": 13,
        "THEORY": 9,
        "TOPIC": 7,
        "DATASET": 1
      }
    }
  },
  "meta": {
    "request_id": "req_d6bf88350858413ab948fabfa693a7c2",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 73568,
    "created_at": "2026-10-27T22:27:05.659204+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_61921735255d4f3892bd51440d047144",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_d5b870f389ea4359b906cb7a34e156a1",
    "file_name": "7.pdf"
  }
}
```

### 14.4 批量文件

- **接口**：`POST /api/v1/ner/research/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `academic_abstract_or_technical_report_text` | file[] | 必填 | 中英文学术论文或技术报告文本文件（上传 PDF/DOCX/TXT） |
| `multi_domain_scientific_corpus` | file (.json) | 选填 | 可选上传资源：多领域科研语料（.json） |
| `manually_labeled_data` | file (.json) | 选填 | 可选上传资源：科研实体标准词表（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/research/files' \
  -F 'academic_abstract_or_technical_report_text=@paper_01.pdf' \
  -F 'academic_abstract_or_technical_report_text=@paper_02.docx' \
  -F 'academic_abstract_or_technical_report_text=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_04de9b66024244c8bb83bd0cba723f5e"
  - input_type: string，示例 "files"
  - total: number，示例 2
  - success_count: number，示例 2
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（2 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "7.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_381cc12fb065446cb15c200d5dd3158e"
      - result: object
        - document_title: string，示例 "7.pdf"
        - document: object
          - title: string，示例 "7.pdf"
        - entities: array<object>（29 项）
          - []: object
        - entity_results: array<object>（29 项）
          - []: object
        - mappings: array<object>（29 项）
          - []: object
        - standard_term_mappings: array<object>（29 项）
          - []: object
        - summary: object
          - entity_count: number，示例 29
          - by_type: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_04de9b66024244c8bb83bd0cba723f5e",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "7.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_381cc12fb065446cb15c200d5dd3158e",
        "result": {
          "document_title": "7.pdf",
          "document": {
            "title": "7.pdf"
          },
          "entities": [
            {
              "text": "learning with positive and unlabeled examples",
              "type": "METHOD",
              "confidence": 0.85,
              "start": 31417,
              "end": 31462,
              "standard_names": {
                "zh": "正例与未标注样本学习",
                "en": "Learning from Positive and Unlabeled Examples"
              },
              "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "科研方法"
            },
            {
              "text": "minimum-variance unbiased estimate",
              "type": "THEORY",
              "confidence": 0.8,
              "standard_names": {
                "zh": "最小方差无偏估计",
                "en": "minimum-variance unbiased estimate"
              },
              "start": 5922,
              "end": 5956,
              "context": "Uniform weighting is not the minimum-variance unbiased estimate (MVUE) of the mean.",
              "mapping_status": "已映射",
              "mapping_confidence": 0.98,
              "entity_id": null,
              "entity_type_name": "理论原理"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "learning with positive and unlabeled examples",
              "type": "METHOD",
              "confidence": 0.85,
              "start": 31417,
              "end": 31462,
              "standard_names": {
                "zh": "正例与未标注样本学习",
                "en": "Learning from Positive and Unlabeled Examples"
              },
              "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "科研方法"
            },
            {
              "text": "minimum-variance unbiased estimate",
              "type": "THEORY",
              "confidence": 0.8,
              "standard_names": {
                "zh": "最小方差无偏估计",
                "en": "minimum-variance unbiased estimate"
              },
              "start": 5922,
              "end": 5956,
              "context": "Uniform weighting is not the minimum-variance unbiased estimate (MVUE) of the mean.",
              "mapping_status": "已映射",
              "mapping_confidence": 0.98,
              "entity_id": null,
              "entity_type_name": "理论原理"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "learning with positive and unlabeled examples",
              "type": "METHOD",
              "confidence": 0.85,
              "start": 31417,
              "end": 31462,
              "standard_names": {
                "zh": "正例与未标注样本学习",
                "en": "Learning from Positive and Unlabeled Examples"
              },
              "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "科研方法"
            },
            {
              "text": "minimum-variance unbiased estimate",
              "type": "THEORY",
              "confidence": 0.8,
              "standard_names": {
                "zh": "最小方差无偏估计",
                "en": "minimum-variance unbiased estimate"
              },
              "start": 5922,
              "end": 5956,
              "context": "Uniform weighting is not the minimum-variance unbiased estimate (MVUE) of the mean.",
              "mapping_status": "已映射",
              "mapping_confidence": 0.98,
              "entity_id": null,
              "entity_type_name": "理论原理"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "standard_term_mappings": [
            {
              "text": "learning with positive and unlabeled examples",
              "type": "METHOD",
              "confidence": 0.85,
              "start": 31417,
              "end": 31462,
              "standard_names": {
                "zh": "正例与未标注样本学习",
                "en": "Learning from Positive and Unlabeled Examples"
              },
              "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "科研方法"
            },
            {
              "text": "minimum-variance unbiased estimate",
              "type": "THEORY",
              "confidence": 0.8,
              "standard_names": {
                "zh": "最小方差无偏估计",
                "en": "minimum-variance unbiased estimate"
              },
              "start": 5922,
              "end": 5956,
              "context": "Uniform weighting is not the minimum-variance unbiased estimate (MVUE) of the mean.",
              "mapping_status": "已映射",
              "mapping_confidence": 0.98,
              "entity_id": null,
              "entity_type_name": "理论原理"
            },
            "…（共 29 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 29,
            "by_type": {
              "METHOD": 11,
              "THEORY": 9,
              "TOPIC": 8,
              "DATASET": 1
            }
          }
        }
      },
      {
        "index": 1,
        "file_name": "35.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_e710c2d714bf4b84a3154dff3f1a9da2",
        "result": {
          "document_title": "35.pdf",
          "document": {
            "title": "35.pdf"
          },
          "entities": [
            {
              "text": "positive and unlabeled examples",
              "type": "METHOD",
              "confidence": 0.7,
              "start": 31431,
              "end": 31462,
              "standard_names": {
                "zh": "正例与未标注样本学习",
                "en": "Positive and Unlabeled Learning"
              },
              "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "科研方法"
            },
            {
              "text": "multiplicative Chernoff bound",
              "type": "THEORY",
              "confidence": 0.85,
              "start": 29623,
              "end": 29652,
              "standard_names": {
                "zh": "乘法切尔诺夫界",
                "en": "multiplicative Chernoff bound"
              },
              "context": "random variable, by the multiplicative Chernoff bound we have Pr[Ut < O(E[Ut])] ≤exp(−Ω(E[Ut]))",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "理论原理"
            },
            "…（共 30 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "positive and unlabeled examples",
              "type": "METHOD",
              "confidence": 0.7,
              "start": 31431,
              "end": 31462,
              "standard_names": {
                "zh": "正例与未标注样本学习",
                "en": "Positive and Unlabeled Learning"
              },
              "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "科研方法"
            },
            {
              "text": "multiplicative Chernoff bound",
              "type": "THEORY",
              "confidence": 0.85,
              "start": 29623,
              "end": 29652,
              "standard_names": {
                "zh": "乘法切尔诺夫界",
                "en": "multiplicative Chernoff bound"
              },
              "context": "random variable, by the multiplicative Chernoff bound we have Pr[Ut < O(E[Ut])] ≤exp(−Ω(E[Ut]))",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "理论原理"
            },
            "…（共 30 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "positive and unlabeled examples",
              "type": "METHOD",
              "confidence": 0.7,
              "start": 31431,
              "end": 31462,
              "standard_names": {
                "zh": "正例与未标注样本学习",
                "en": "Positive and Unlabeled Learning"
              },
              "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "科研方法"
            },
            {
              "text": "multiplicative Chernoff bound",
              "type": "THEORY",
              "confidence": 0.85,
              "start": 29623,
              "end": 29652,
              "standard_names": {
                "zh": "乘法切尔诺夫界",
                "en": "multiplicative Chernoff bound"
              },
              "context": "random variable, by the multiplicative Chernoff bound we have Pr[Ut < O(E[Ut])] ≤exp(−Ω(E[Ut]))",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "理论原理"
            },
            "…（共 30 项，示例保留前 2 项）"
          ],
          "standard_term_mappings": [
            {
              "text": "positive and unlabeled examples",
              "type": "METHOD",
              "confidence": 0.7,
              "start": 31431,
              "end": 31462,
              "standard_names": {
                "zh": "正例与未标注样本学习",
                "en": "Positive and Unlabeled Learning"
              },
              "context": "The analysis proceeds via a reduction to learning with positive and unlabeled examples (also referred",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "科研方法"
            },
            {
              "text": "multiplicative Chernoff bound",
              "type": "THEORY",
              "confidence": 0.85,
              "start": 29623,
              "end": 29652,
              "standard_names": {
                "zh": "乘法切尔诺夫界",
                "en": "multiplicative Chernoff bound"
              },
              "context": "random variable, by the multiplicative Chernoff bound we have Pr[Ut < O(E[Ut])] ≤exp(−Ω(E[Ut]))",
              "mapping_status": "已映射",
              "mapping_confidence": 0.95,
              "entity_id": null,
              "entity_type_name": "理论原理"
            },
            "…（共 30 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 30,
            "by_type": {
              "METHOD": 12,
              "THEORY": 7,
              "TOPIC": 10,
              "DATASET": 1
            }
          }
        }
      }
    ]
  },
  "meta": {
    "request_id": "req_f1fa91b690504dcbb5a53e3a9af6bf3b",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 66120,
    "created_at": "2026-10-27T22:28:11.814544+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_04de9b66024244c8bb83bd0cba723f5e",
    "input_type": "files",
    "total": 2,
    "success_count": 2,
    "failed_count": 0
  }
}
```

---

## 15. 专业领域科研实体识别

**工具ID**：`domain-ner`

面向医学、化工、物理等领域，识别疾病、药物、化合物、理论、现象与规律等专业实体。

**功能特点**：本体体系限定，领域实体识别，知识库映射

**适用场景**：专业领域抽取与图谱构建

### 15.1 单文本

- **接口**：`POST /api/v1/ner/domain/text`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `domain_scientific_document_text` | string | 必填 | 专业科研文献文本 |
| `ontology_classification_system` | file (.json) | 选填 | 可选上传资源：专业领域本体（.json） |
| `domain_labeled_training_data` | file (.json) | 选填 | 可选上传资源：领域标注训练数据（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/domain/text' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": "科技文献题目",
  "domain_scientific_document_text": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗。"
}
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "科技文献题目"
  - document: object
    - title: string，示例 "科技文献题目"
  - entities: array<object>（6 项）
    - []: object
      - text: string，示例 "经皮冠状动脉介入治疗"
      - type: string，示例 "TREATMENT"
      - domain: string，示例 "医学"
      - confidence: number，示例 0.97
      - standard_names: null（本示例中为空）
      - start: number，示例 70
      - end: number，示例 80
      - context: string，示例 "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变…"
      - mapping_status: string，示例 "未命中"
      - mapping_confidence: number，示例 0
      - mapping_source: string，示例 ""
      - standard_kb_id: string，示例 "未命中"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "治疗方法"
  - entity_results: array<object>（6 项）
    - []: object
      - text: string，示例 "经皮冠状动脉介入治疗"
      - type: string，示例 "TREATMENT"
      - domain: string，示例 "医学"
      - confidence: number，示例 0.97
      - standard_names: null（本示例中为空）
      - start: number，示例 70
      - end: number，示例 80
      - context: string，示例 "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变…"
      - mapping_status: string，示例 "未命中"
      - mapping_confidence: number，示例 0
      - mapping_source: string，示例 ""
      - standard_kb_id: string，示例 "未命中"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "治疗方法"
  - mappings: array<object>（6 项）
    - []: object
      - text: string，示例 "经皮冠状动脉介入治疗"
      - type: string，示例 "TREATMENT"
      - domain: string，示例 "医学"
      - confidence: number，示例 0.97
      - standard_names: null（本示例中为空）
      - start: number，示例 70
      - end: number，示例 80
      - context: string，示例 "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变…"
      - mapping_status: string，示例 "未命中"
      - mapping_confidence: number，示例 0
      - mapping_source: string，示例 ""
      - standard_kb_id: string，示例 "未命中"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "治疗方法"
  - ontology_mappings: array<object>（6 项）
    - []: object
      - text: string，示例 "经皮冠状动脉介入治疗"
      - type: string，示例 "TREATMENT"
      - domain: string，示例 "医学"
      - confidence: number，示例 0.97
      - standard_names: null（本示例中为空）
      - start: number，示例 70
      - end: number，示例 80
      - context: string，示例 "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变…"
      - mapping_status: string，示例 "未命中"
      - mapping_confidence: number，示例 0
      - mapping_source: string，示例 ""
      - standard_kb_id: string，示例 "未命中"
      - entity_id: null（本示例中为空）
      - entity_type_name: string，示例 "治疗方法"
  - summary: object
    - entity_count: number，示例 6
    - by_type: object
      - TREATMENT: number，示例 1
      - DISEASE: number，示例 3
      - DRUG: number，示例 2
  - selected_domain: object
    - code: string，示例 "医学"
    - name: string，示例 "医学"
    - entity_domain_distribution: object
      - 医学: number，示例 6
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "科技文献题目",
    "document": {
      "title": "科技文献题目"
    },
    "entities": [
      {
        "text": "经皮冠状动脉介入治疗",
        "type": "TREATMENT",
        "domain": "医学",
        "confidence": 0.97,
        "standard_names": null,
        "start": 70,
        "end": 80,
        "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗。",
        "mapping_status": "未命中",
        "mapping_confidence": 0,
        "mapping_source": "",
        "standard_kb_id": "未命中",
        "entity_id": null,
        "entity_type_name": "治疗方法"
      },
      {
        "text": "2型糖尿病",
        "type": "DISEASE",
        "domain": "医学",
        "confidence": 0.98,
        "standard_names": null,
        "start": 8,
        "end": 13,
        "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率。",
        "mapping_status": "未命中",
        "mapping_confidence": 0,
        "mapping_source": "",
        "standard_kb_id": "未命中",
        "entity_id": null,
        "entity_type_name": "疾病"
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "entity_results": [
      {
        "text": "经皮冠状动脉介入治疗",
        "type": "TREATMENT",
        "domain": "医学",
        "confidence": 0.97,
        "standard_names": null,
        "start": 70,
        "end": 80,
        "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗。",
        "mapping_status": "未命中",
        "mapping_confidence": 0,
        "mapping_source": "",
        "standard_kb_id": "未命中",
        "entity_id": null,
        "entity_type_name": "治疗方法"
      },
      {
        "text": "2型糖尿病",
        "type": "DISEASE",
        "domain": "医学",
        "confidence": 0.98,
        "standard_names": null,
        "start": 8,
        "end": 13,
        "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率。",
        "mapping_status": "未命中",
        "mapping_confidence": 0,
        "mapping_source": "",
        "standard_kb_id": "未命中",
        "entity_id": null,
        "entity_type_name": "疾病"
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "mappings": [
      {
        "text": "经皮冠状动脉介入治疗",
        "type": "TREATMENT",
        "domain": "医学",
        "confidence": 0.97,
        "standard_names": null,
        "start": 70,
        "end": 80,
        "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗。",
        "mapping_status": "未命中",
        "mapping_confidence": 0,
        "mapping_source": "",
        "standard_kb_id": "未命中",
        "entity_id": null,
        "entity_type_name": "治疗方法"
      },
      {
        "text": "2型糖尿病",
        "type": "DISEASE",
        "domain": "医学",
        "confidence": 0.98,
        "standard_names": null,
        "start": 8,
        "end": 13,
        "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率。",
        "mapping_status": "未命中",
        "mapping_confidence": 0,
        "mapping_source": "",
        "standard_kb_id": "未命中",
        "entity_id": null,
        "entity_type_name": "疾病"
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "ontology_mappings": [
      {
        "text": "经皮冠状动脉介入治疗",
        "type": "TREATMENT",
        "domain": "医学",
        "confidence": 0.97,
        "standard_names": null,
        "start": 70,
        "end": 80,
        "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗。",
        "mapping_status": "未命中",
        "mapping_confidence": 0,
        "mapping_source": "",
        "standard_kb_id": "未命中",
        "entity_id": null,
        "entity_type_name": "治疗方法"
      },
      {
        "text": "2型糖尿病",
        "type": "DISEASE",
        "domain": "医学",
        "confidence": 0.98,
        "standard_names": null,
        "start": 8,
        "end": 13,
        "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率。",
        "mapping_status": "未命中",
        "mapping_confidence": 0,
        "mapping_source": "",
        "standard_kb_id": "未命中",
        "entity_id": null,
        "entity_type_name": "疾病"
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "summary": {
      "entity_count": 6,
      "by_type": {
        "TREATMENT": 1,
        "DISEASE": 3,
        "DRUG": 2
      }
    },
    "selected_domain": {
      "code": "医学",
      "name": "医学",
      "entity_domain_distribution": {
        "医学": 6
      }
    }
  },
  "meta": {
    "request_id": "req_7c0a2307cb074f858560ec47b0520a89",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 30852,
    "created_at": "2026-10-27T22:07:14.561446+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_aa18e40471c145d3a49f05401fb3ad2d",
    "input_type": "text",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_3351c4b672694e038eea98e1f429e858",
    "file_name": null
  }
}
```

### 15.2 批量文本

- **接口**：`POST /api/v1/ner/domain/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_title` | string[] | 必填 | 文献题目,必填(文本输入时);用于响应结果标识与可视化弹窗的文献显示,文件输入时由文件名兜底 |
| `domain_scientific_document_text` | object[] | 必填 | 专业科研文献文本 |
| `domain_scientific_document_text[].id` | string | 选填 | 批量文本条目编号 |
| `domain_scientific_document_text[].title` | string | 选填 | 文献题名 |
| `domain_scientific_document_text[].text` | string | 必填 | 用户输入的文本内容 |
| `ontology_classification_system` | file (.json) | 选填 | 可选上传资源：专业领域本体（.json） |
| `domain_labeled_training_data` | file (.json) | 选填 | 可选上传资源：领域标注训练数据（.json） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/domain/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_title": [
    "二甲双胍联合胰岛素治疗2型糖尿病的疗效观察",
    "介孔二氧化硅负载石墨烯复合材料的制备与性能",
    "石墨烯中的量子霍尔效应与超导现象研究"
  ],
  "domain_scientific_document_text": [
    {
      "id": "DEMO_1",
      "title": "二甲双胍联合胰岛素治疗2型糖尿病的疗效观察",
      "text": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗。"
    },
    {
      "id": "DEMO_2",
      "title": "介孔二氧化硅负载石墨烯复合材料的制备与性能",
      "text": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物，制备介孔二氧化硅负载的石墨烯复合材料，并在N-甲基吡咯烷酮溶剂中考察自由基聚合反应速率与CO2吸附性能。"
    },
    {
      "id": "DEMO_3",
      "title": "石墨烯中的量子霍尔效应与超导现象研究",
      "text": "本文基于量子力学与密度泛函理论研究石墨烯中的量子霍尔效应与量子隧穿现象，实验观测到超导现象，验证了能量守恒定律与热力学第二定律，并讨论量子纠缠在波粒二象性实验中的表现。"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_ef2cdd1b8012446c89dfeb811e352bc4"
  - input_type: string，示例 "texts"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: null（本示例中为空）
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_41ed05b5df4f4f2192d0478db314417c"
      - result: object
        - document_title: string，示例 "二甲双胍联合胰岛素治疗2型糖尿病的疗效观察"
        - document: object
          - title: string，示例 "二甲双胍联合胰岛素治疗2型糖尿病的疗效观察"
        - entities: array<object>（6 项）
          - []: object
        - entity_results: array<object>（6 项）
          - []: object
        - mappings: array<object>（6 项）
          - []: object
        - ontology_mappings: array<object>（6 项）
          - []: object
        - summary: object
          - entity_count: number，示例 6
          - by_type: object
        - selected_domain: object
          - code: string，示例 "医学"
          - name: string，示例 "医学"
          - entity_domain_distribution: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_ef2cdd1b8012446c89dfeb811e352bc4",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_41ed05b5df4f4f2192d0478db314417c",
        "result": {
          "document_title": "二甲双胍联合胰岛素治疗2型糖尿病的疗效观察",
          "document": {
            "title": "二甲双胍联合胰岛素治疗2型糖尿病的疗效观察"
          },
          "entities": [
            {
              "text": "经皮冠状动脉介入治疗",
              "type": "TREATMENT",
              "domain": "医学",
              "confidence": 0.95,
              "standard_names": null,
              "start": 70,
              "end": 80,
              "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "治疗方法"
            },
            {
              "text": "2型糖尿病",
              "type": "DISEASE",
              "domain": "医学",
              "confidence": 0.98,
              "standard_names": null,
              "start": 8,
              "end": 13,
              "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率。",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "疾病"
            },
            "…（共 6 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "经皮冠状动脉介入治疗",
              "type": "TREATMENT",
              "domain": "医学",
              "confidence": 0.95,
              "standard_names": null,
              "start": 70,
              "end": 80,
              "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "治疗方法"
            },
            {
              "text": "2型糖尿病",
              "type": "DISEASE",
              "domain": "医学",
              "confidence": 0.98,
              "standard_names": null,
              "start": 8,
              "end": 13,
              "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率。",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "疾病"
            },
            "…（共 6 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "经皮冠状动脉介入治疗",
              "type": "TREATMENT",
              "domain": "医学",
              "confidence": 0.95,
              "standard_names": null,
              "start": 70,
              "end": 80,
              "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "治疗方法"
            },
            {
              "text": "2型糖尿病",
              "type": "DISEASE",
              "domain": "医学",
              "confidence": 0.98,
              "standard_names": null,
              "start": 8,
              "end": 13,
              "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率。",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "疾病"
            },
            "…（共 6 项，示例保留前 2 项）"
          ],
          "ontology_mappings": [
            {
              "text": "经皮冠状动脉介入治疗",
              "type": "TREATMENT",
              "domain": "医学",
              "confidence": 0.95,
              "standard_names": null,
              "start": 70,
              "end": 80,
              "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率，部分患者联合经皮冠状动脉介入治疗",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "治疗方法"
            },
            {
              "text": "2型糖尿病",
              "type": "DISEASE",
              "domain": "医学",
              "confidence": 0.98,
              "standard_names": null,
              "start": 8,
              "end": 13,
              "context": "研究纳入120例2型糖尿病患者，随机分为二甲双胍组和胰岛素组，观察糖化血红蛋白变化，并评估代谢综合征、糖尿病肾病等并发症发生率。",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "疾病"
            },
            "…（共 6 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 6,
            "by_type": {
              "TREATMENT": 1,
              "DISEASE": 3,
              "DRUG": 2
            }
          },
          "selected_domain": {
            "code": "医学",
            "name": "医学",
            "entity_domain_distribution": {
              "医学": 6
            }
          }
        }
      },
      {
        "index": 1,
        "file_name": null,
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_ece29bb88b33415d903b2987155ce4fc",
        "result": {
          "document_title": "介孔二氧化硅负载石墨烯复合材料的制备与性能",
          "document": {
            "title": "介孔二氧化硅负载石墨烯复合材料的制备与性能"
          },
          "entities": [
            {
              "text": "聚乳酸(PLA)",
              "type": "COMPOUND",
              "domain": "化工",
              "confidence": 0.95,
              "standard_names": null,
              "start": 21,
              "end": 29,
              "context": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物，制备介孔二氧化硅负载的石墨烯复合材料，并在N-甲基吡咯烷酮溶剂中考察自由基聚合反应速率与CO2吸附性能",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "化合物"
            },
            {
              "text": "聚乙二醇-400",
              "type": "COMPOUND",
              "domain": "化工",
              "confidence": 0.95,
              "standard_names": null,
              "start": 30,
              "end": 38,
              "context": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "化合物"
            },
            "…（共 7 项，示例保留前 2 项）"
          ],
          "entity_results": [
            {
              "text": "聚乳酸(PLA)",
              "type": "COMPOUND",
              "domain": "化工",
              "confidence": 0.95,
              "standard_names": null,
              "start": 21,
              "end": 29,
              "context": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物，制备介孔二氧化硅负载的石墨烯复合材料，并在N-甲基吡咯烷酮溶剂中考察自由基聚合反应速率与CO2吸附性能",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "化合物"
            },
            {
              "text": "聚乙二醇-400",
              "type": "COMPOUND",
              "domain": "化工",
              "confidence": 0.95,
              "standard_names": null,
              "start": 30,
              "end": 38,
              "context": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "化合物"
            },
            "…（共 7 项，示例保留前 2 项）"
          ],
          "mappings": [
            {
              "text": "聚乳酸(PLA)",
              "type": "COMPOUND",
              "domain": "化工",
              "confidence": 0.95,
              "standard_names": null,
              "start": 21,
              "end": 29,
              "context": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物，制备介孔二氧化硅负载的石墨烯复合材料，并在N-甲基吡咯烷酮溶剂中考察自由基聚合反应速率与CO2吸附性能",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "化合物"
            },
            {
              "text": "聚乙二醇-400",
              "type": "COMPOUND",
              "domain": "化工",
              "confidence": 0.95,
              "standard_names": null,
              "start": 30,
              "end": 38,
              "context": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "化合物"
            },
            "…（共 7 项，示例保留前 2 项）"
          ],
          "ontology_mappings": [
            {
              "text": "聚乳酸(PLA)",
              "type": "COMPOUND",
              "domain": "化工",
              "confidence": 0.95,
              "standard_names": null,
              "start": 21,
              "end": 29,
              "context": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物，制备介孔二氧化硅负载的石墨烯复合材料，并在N-甲基吡咯烷酮溶剂中考察自由基聚合反应速率与CO2吸附性能",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "化合物"
            },
            {
              "text": "聚乙二醇-400",
              "type": "COMPOUND",
              "domain": "化工",
              "confidence": 0.95,
              "standard_names": null,
              "start": 30,
              "end": 38,
              "context": "以TiO2为光催化剂，通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
              "mapping_status": "未命中",
              "mapping_confidence": 0,
              "mapping_source": "",
              "standard_kb_id": "未命中",
              "entity_id": null,
              "entity_type_name": "化合物"
            },
            "…（共 7 项，示例保留前 2 项）"
          ],
          "summary": {
            "entity_count": 7,
            "by_type": {
              "COMPOUND": 3,
              "REACTION": 2,
              "MATERIAL": 2
            }
          },
          "selected_domain": {
            "code": "化工",
            "name": "化工",
            "entity_domain_distribution": {
              "化工": 7
            }
          }
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_2c21f877f57d4336a0652798cf20903d",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 37057,
    "created_at": "2026-10-27T22:07:51.634163+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_ef2cdd1b8012446c89dfeb811e352bc4",
    "input_type": "texts",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

### 15.3 单文件

- **接口**：`POST /api/v1/ner/domain/file`
- **Content-Type**：multipart/form-data

> 上传与所选领域匹配的文献（示例领域为医学，上传医学文献可得非空实体）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `domain_scientific_document_text` | file | 必填 | 专业科研文献文件（上传 PDF/DOCX/TXT） |
| `ontology_classification_system` | file (.json) | 选填 | 可选上传资源：专业领域本体（.json） |
| `domain_labeled_training_data` | file (.json) | 选填 | 可选上传资源：领域标注训练数据（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/domain/file' \
  -F 'domain_scientific_document_text=@paper.pdf'
```

#### 响应字段（data）

```
- data: object
  - document_title: string，示例 "zh1.pdf"
  - document: object
    - title: string，示例 "zh1.pdf"
  - entities: array<undefined>
  - entity_results: array<undefined>
  - mappings: array<undefined>
  - ontology_mappings: array<undefined>
  - summary: object
    - entity_count: number，示例 0
    - by_type: object
  - selected_domain: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_title": "zh1.pdf",
    "document": {
      "title": "zh1.pdf"
    },
    "entities": [],
    "entity_results": [],
    "mappings": [],
    "ontology_mappings": [],
    "summary": {
      "entity_count": 0,
      "by_type": {}
    },
    "selected_domain": {}
  },
  "meta": {
    "request_id": "req_57385810f17b410d8ede11912722bb05",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 8707,
    "created_at": "2026-10-27T22:37:05.976278+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_df017d4f22254f3a812ab67ce5248989",
    "input_type": "file",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_30415860df6e4ab883a07f18d4069287",
    "file_name": "zh1.pdf"
  }
}
```

### 15.4 批量文件

- **接口**：`POST /api/v1/ner/domain/files`
- **Content-Type**：multipart/form-data

> 上传与所选领域匹配的文献（示例领域为医学，上传医学文献可得非空实体）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `domain_scientific_document_text` | file[] | 必填 | 专业科研文献文件（上传 PDF/DOCX/TXT） |
| `ontology_classification_system` | file (.json) | 选填 | 可选上传资源：专业领域本体（.json） |
| `domain_labeled_training_data` | file (.json) | 选填 | 可选上传资源：领域标注训练数据（.json） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/ner/domain/files' \
  -F 'domain_scientific_document_text=@paper_01.pdf' \
  -F 'domain_scientific_document_text=@paper_02.docx' \
  -F 'domain_scientific_document_text=@paper_03.pdf'
```

#### 响应字段（data）

```
- data: object
  - batch_id: string，示例 "tsk_90495aadea9747d8bc543842c3a6ecde"
  - input_type: string，示例 "files"
  - total: number，示例 3
  - success_count: number，示例 3
  - failed_count: number，示例 0
  - error_summary: null（本示例中为空）
  - results: array<object>（3 项）
    - []: object
      - index: number，示例 0
      - file_name: string，示例 "zh1.pdf"
      - status: string，示例 "succeeded"
      - code: number，示例 0
      - record_id: string，示例 "rec_5ff3c5df3bff415e808869c03a437676"
      - result: object
        - document_title: string，示例 "zh1.pdf"
        - document: object
          - title: string，示例 "zh1.pdf"
        - entities: array<undefined>
        - entity_results: array<undefined>
        - mappings: array<undefined>
        - ontology_mappings: array<undefined>
        - summary: object
          - entity_count: number，示例 0
          - by_type: object
        - selected_domain: object
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "tsk_90495aadea9747d8bc543842c3a6ecde",
    "input_type": "files",
    "total": 3,
    "success_count": 3,
    "failed_count": 0,
    "error_summary": null,
    "results": [
      {
        "index": 0,
        "file_name": "zh1.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_5ff3c5df3bff415e808869c03a437676",
        "result": {
          "document_title": "zh1.pdf",
          "document": {
            "title": "zh1.pdf"
          },
          "entities": [],
          "entity_results": [],
          "mappings": [],
          "ontology_mappings": [],
          "summary": {
            "entity_count": 0,
            "by_type": {}
          },
          "selected_domain": {}
        }
      },
      {
        "index": 1,
        "file_name": "zh2.pdf",
        "status": "succeeded",
        "code": 0,
        "record_id": "rec_596df6d796ab478687d99c330e419c27",
        "result": {
          "document_title": "zh2.pdf",
          "document": {
            "title": "zh2.pdf"
          },
          "entities": [],
          "entity_results": [],
          "mappings": [],
          "ontology_mappings": [],
          "summary": {
            "entity_count": 0,
            "by_type": {}
          },
          "selected_domain": {}
        }
      },
      "…（共 3 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_d0d830a6d8ac428bbad661900103cc96",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 25127,
    "created_at": "2026-10-27T22:37:31.141541+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_90495aadea9747d8bc543842c3a6ecde",
    "input_type": "files",
    "total": 3,
    "success_count": 3,
    "failed_count": 0
  }
}
```

---

## 16. 实体关系识别

**工具ID**：`relation-extract`

在实体识别结果基础上，抽取实体对之间的语义关系，并输出可用于知识图谱的关系三元组。

**功能特点**：实体关系三元组，依存路径，知识网络

**适用场景**：知识图谱边构建与关系发现

> upstream_ner_record_id 来源于通用/科研/领域 NER 工具的历史识别记录，可通过 `GET /api/v1/history/compatible?downstream_tool=relation-extract&upstream_type=entity` 查询当前可用记录。

### 16.1 历史识别记录

- **接口**：`POST /api/v1/relation/from-ner-record`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `upstream_ner_record_id` | string | 必填 | 上游实体记录编号。数据库中已完成的命名实体识别结果记录(rec_ 前缀),后端据此读取原始句子和实体列表,在其上抽取实体间关系三元组 |
| `dependency_parse` | object[] | 选填 | 依存句法分析结果。选择上游实体记录后系统自动生成并展示;包含句子编号、中心词、依存关系和依存词,用于支撑关系抽取的句法分析 |
| `dependency_paths` | object[] | 选填 | 实体关系三元组对应的依存句法路径,由系统自动生成 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/relation/from-ner-record' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "upstream_ner_record_id": "NER-20260816-001",
  "dependency_parse": [],
  "dependency_paths": []
}
```

#### 响应字段（data）

```
- data: object
  - relations: array<object>（6 项）
    - []: object
      - head: string，示例 "开环聚合反应"
      - relation: string，示例 "合成"
      - tail: string，示例 "聚乳酸(PLA)"
      - context: string，示例 "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物"
      - confidence: number，示例 0.95
      - triple_id: string，示例 "TRIPLE_001"
      - sentence_id: string，示例 "SENT-000"
      - trigger: string，示例 "合成"
      - dependency_path: string，示例 "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)"
      - source_position: object
        - start: number，示例 0
        - end: number，示例 22
      - subject: string，示例 "开环聚合反应"
      - object: string，示例 "聚乳酸(PLA)"
  - dependency_parse: array<object>（7 项）
    - []: object
      - sentence_id: string，示例 "SENT-000"
      - head: string，示例 "合成"
      - relation: string，示例 "状语"
      - dependent: string，示例 "开环聚合反应"
  - dependency_paths: array<object>（6 项）
    - []: object
      - triple_id: string，示例 "TRIPLE_001"
      - path: string，示例 "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)"
  - triples: array<object>（6 项）
    - []: object
      - head: string，示例 "开环聚合反应"
      - relation: string，示例 "合成"
      - tail: string，示例 "聚乳酸(PLA)"
      - context: string，示例 "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物"
      - confidence: number，示例 0.95
      - triple_id: string，示例 "TRIPLE_001"
      - sentence_id: string，示例 "SENT-000"
      - trigger: string，示例 "合成"
      - dependency_path: string，示例 "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)"
      - source_position: object
        - start: number，示例 0
        - end: number，示例 22
      - subject: string，示例 "开环聚合反应"
      - object: string，示例 "聚乳酸(PLA)"
  - relation_triples: array<object>（6 项）
    - []: object
      - head: string，示例 "开环聚合反应"
      - relation: string，示例 "合成"
      - tail: string，示例 "聚乳酸(PLA)"
      - context: string，示例 "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物"
      - confidence: number，示例 0.95
      - triple_id: string，示例 "TRIPLE_001"
      - sentence_id: string，示例 "SENT-000"
      - trigger: string，示例 "合成"
      - dependency_path: string，示例 "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)"
      - source_position: object
        - start: number，示例 0
        - end: number，示例 22
      - subject: string，示例 "开环聚合反应"
      - object: string，示例 "聚乳酸(PLA)"
  - relation_results: array<object>（6 项）
    - []: object
      - head: string，示例 "开环聚合反应"
      - relation: string，示例 "合成"
      - tail: string，示例 "聚乳酸(PLA)"
      - context: string，示例 "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物"
      - confidence: number，示例 0.95
      - triple_id: string，示例 "TRIPLE_001"
      - sentence_id: string，示例 "SENT-000"
      - trigger: string，示例 "合成"
      - dependency_path: string，示例 "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)"
      - source_position: object
        - start: number，示例 0
        - end: number，示例 22
      - subject: string，示例 "开环聚合反应"
      - object: string，示例 "聚乳酸(PLA)"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "relations": [
      {
        "head": "开环聚合反应",
        "relation": "合成",
        "tail": "聚乳酸(PLA)",
        "context": "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
        "confidence": 0.95,
        "triple_id": "TRIPLE_001",
        "sentence_id": "SENT-000",
        "trigger": "合成",
        "dependency_path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)",
        "source_position": {
          "start": 0,
          "end": 22
        },
        "subject": "开环聚合反应",
        "object": "聚乳酸(PLA)"
      },
      {
        "head": "开环聚合反应",
        "relation": "合成",
        "tail": "聚乙二醇-400",
        "context": "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
        "confidence": 0.95,
        "triple_id": "TRIPLE_002",
        "sentence_id": "SENT-000",
        "trigger": "合成",
        "dependency_path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乙二醇-400",
        "source_position": {
          "start": 0,
          "end": 22
        },
        "subject": "开环聚合反应",
        "object": "聚乙二醇-400"
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "dependency_parse": [
      {
        "sentence_id": "SENT-000",
        "head": "合成",
        "relation": "状语",
        "dependent": "开环聚合反应"
      },
      {
        "sentence_id": "SENT-000",
        "head": "合成",
        "relation": "宾语",
        "dependent": "聚乳酸(PLA)"
      },
      "…（共 7 项，示例保留前 2 项）"
    ],
    "dependency_paths": [
      {
        "triple_id": "TRIPLE_001",
        "path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)"
      },
      {
        "triple_id": "TRIPLE_002",
        "path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乙二醇-400"
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "triples": [
      {
        "head": "开环聚合反应",
        "relation": "合成",
        "tail": "聚乳酸(PLA)",
        "context": "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
        "confidence": 0.95,
        "triple_id": "TRIPLE_001",
        "sentence_id": "SENT-000",
        "trigger": "合成",
        "dependency_path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)",
        "source_position": {
          "start": 0,
          "end": 22
        },
        "subject": "开环聚合反应",
        "object": "聚乳酸(PLA)"
      },
      {
        "head": "开环聚合反应",
        "relation": "合成",
        "tail": "聚乙二醇-400",
        "context": "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
        "confidence": 0.95,
        "triple_id": "TRIPLE_002",
        "sentence_id": "SENT-000",
        "trigger": "合成",
        "dependency_path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乙二醇-400",
        "source_position": {
          "start": 0,
          "end": 22
        },
        "subject": "开环聚合反应",
        "object": "聚乙二醇-400"
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "relation_triples": [
      {
        "head": "开环聚合反应",
        "relation": "合成",
        "tail": "聚乳酸(PLA)",
        "context": "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
        "confidence": 0.95,
        "triple_id": "TRIPLE_001",
        "sentence_id": "SENT-000",
        "trigger": "合成",
        "dependency_path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)",
        "source_position": {
          "start": 0,
          "end": 22
        },
        "subject": "开环聚合反应",
        "object": "聚乳酸(PLA)"
      },
      {
        "head": "开环聚合反应",
        "relation": "合成",
        "tail": "聚乙二醇-400",
        "context": "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
        "confidence": 0.95,
        "triple_id": "TRIPLE_002",
        "sentence_id": "SENT-000",
        "trigger": "合成",
        "dependency_path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乙二醇-400",
        "source_position": {
          "start": 0,
          "end": 22
        },
        "subject": "开环聚合反应",
        "object": "聚乙二醇-400"
      },
      "…（共 6 项，示例保留前 2 项）"
    ],
    "relation_results": [
      {
        "head": "开环聚合反应",
        "relation": "合成",
        "tail": "聚乳酸(PLA)",
        "context": "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
        "confidence": 0.95,
        "triple_id": "TRIPLE_001",
        "sentence_id": "SENT-000",
        "trigger": "合成",
        "dependency_path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乳酸(PLA)",
        "source_position": {
          "start": 0,
          "end": 22
        },
        "subject": "开环聚合反应",
        "object": "聚乳酸(PLA)"
      },
      {
        "head": "开环聚合反应",
        "relation": "合成",
        "tail": "聚乙二醇-400",
        "context": "通过开环聚合反应合成聚乳酸(PLA)与聚乙二醇-400的嵌段共聚物",
        "confidence": 0.95,
        "triple_id": "TRIPLE_002",
        "sentence_id": "SENT-000",
        "trigger": "合成",
        "dependency_path": "开环聚合反应 ←[状语]— 合成 —[宾语]→ 聚乙二醇-400",
        "source_position": {
          "start": 0,
          "end": 22
        },
        "subject": "开环聚合反应",
        "object": "聚乙二醇-400"
      },
      "…（共 6 项，示例保留前 2 项）"
    ]
  },
  "meta": {
    "request_id": "req_d753b044ad0a411083b7e303a8d4c6a1",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 19227,
    "created_at": "2026-10-27T22:21:45.672990+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_f45003b69c0f4c74ab5b4d1431b8db88",
    "input_type": "upstream_records",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_93662ea7f2de41d49a1ce5d2fd5a834e",
    "file_name": null
  }
}
```

---

## 17. 深度聚类工具

**工具ID**：`deep-cluster`

对用户上传的多篇科技文献文本进行标准化处理、句子级语义编码和相似度聚类，输出聚类结果类簇、类簇特征统计和主题趋势分析结果。

**功能特点**：语义聚类，技术与应用双轴，质量与趋势

**适用场景**：文献群组组织与研究布局

### 17.1 批量文本

- **接口**：`POST /api/v1/cluster/deep/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scientific_document_texts` | object[] | 必填 | 多篇科技文献文本,至少 4 篇(批量文本模式专用参数) |
| `scientific_document_texts[].document_id` | string | 必填 | 文献编号，用于关联文本与元数据 |
| `scientific_document_texts[].text` | string | 必填 | 用户输入的文本内容 |
| `document_metadata` | object[] | 必填 | 文献元数据(文献编号+发表时间),用于趋势分析与文献集沉淀。批量文本模式必填;批量文件模式由文件解析自动补充 |
| `document_metadata[].document_id` | string | 必填 | 文献编号，用于关联文本与元数据 |
| `document_metadata[].title` | string | 必填 | 文献题名 |
| `document_metadata[].authors` | string[] | 选填 | 作者列表 |
| `document_metadata[].source` | string | 选填 | 资源来源或文献来源 |
| `document_metadata[].keywords` | string[] | 选填 | 文献关键词 |
| `document_metadata[].publication_date` | string | 选填 | 发表时间 |
| `cluster_dimension` | string | 必填 | 聚类维度。枚举:"technology"(技术路线,默认)、"application"(应用场景);决定句子特征抽取视角与聚类语义 |
| `clustering_algorithm_type` | string | 选填 | 聚类算法类型。枚举:"auto"(默认,语步对齐语义分组)、"kmeans"、"spectral"(谱聚类)、"agglomerative"(凝聚聚类)、"hierarchical"(层次聚类,与 agglomerative 同算法)、"hdbscan";非 auto 时按轴语步句向量执行所选向量聚类,聚类质量低于默认语义分组 |
| `cluster_count` | integer | 选填 | 类簇数量(>=1,且需小于输入文献数量)。不指定时算法自动确定;auto(语义分组)下为软约束(允许±1浮动),指定向量算法下为精确簇数(hdbscan 为就近搜索) |
| `output_format` | string | 选填 | 输出格式(默认 JSON) |
| `training_samples` | file (.json) | 选填 | 可选上传资源：训练样本锚点（.json：编号+文本+题名） |
| `manually_labeled_category_data` | file (.json) | 选填 | 可选上传资源：人工标注类目标签锚点（.json：编号+人工标注类目标签） |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/cluster/deep/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "scientific_document_texts": [
    {
      "document_id": "DOC-EN-018",
      "text": "The study compares reinforcement-learning vision-language models with their base models, identifies diversity collapse in GRPO, and proposes Multi-Group Policy Optimization to encourage divergent reasoning across multiple solutions."
    },
    {
      "document_id": "DOC-EN-024",
      "text": "The work learns timestep-specific block masks for diffusion models, reuses cached features, and applies timestep-aware loss scaling and mask rectification to reduce inference cost while retaining generation quality."
    },
    {
      "document_id": "DOC-EN-028",
      "text": "TRIAGE treats video reasoning as hierarchical resource allocation. It first selects keyframes and then allocates core and context tokens with relevance and diversity constraints to reduce memory and computation."
    },
    {
      "document_id": "DOC-EN-026",
      "text": "TimeReasoner reformulates time-series forecasting as an inference-time conditional reasoning process with hybrid instructions and rollout-based multi-step reasoning."
    },
    {
      "document_id": "DOC-EN-030",
      "text": "Foreground views guide adaptive visual pre-training so representations focus on semantically relevant object regions."
    }
  ],
  "document_metadata": [
    {
      "document_id": "DOC-EN-018",
      "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
      "authors": [],
      "source": "",
      "keywords": [],
      "publication_date": "2026-04-01"
    },
    {
      "document_id": "DOC-EN-024",
      "title": "Timestep-Aware Block Masking for Efficient Diffusion Model Inference",
      "authors": [],
      "source": "",
      "keywords": [],
      "publication_date": "2026-03-20"
    },
    {
      "document_id": "DOC-EN-028",
      "title": "TRIAGE: Hierarchical Visual Budgeting for Efficient Video Reasoning",
      "authors": [],
      "source": "",
      "keywords": [],
      "publication_date": "2026-01-30"
    },
    {
      "document_id": "DOC-EN-026",
      "title": "Can Slow-Thinking LLMs Reason Over Time?",
      "authors": [],
      "source": "",
      "keywords": []
    },
    {
      "document_id": "DOC-EN-030",
      "title": "FVG-PT: Adaptive Foreground View-Guided Pre-Training",
      "authors": [],
      "source": "",
      "keywords": []
    }
  ],
  "cluster_dimension": "technology",
  "clustering_algorithm_type": "auto",
  "cluster_count": null,
  "output_format": "JSON"
}
```

#### 响应字段（data）

```
- data: object
  - input_summary: object
    - document_count: number，示例 5
    - parsed_sentence_count: number，示例 12
  - cluster_dimension_name: string，示例 "技术路线聚类"
  - clustering_quality: object
    - cluster_count: number，示例 4
    - intra_cluster_similarity: number，示例 0.518
    - algorithm_requested: string，示例 "move_aligned"
    - algorithm_used: string，示例 "task_anchored_grouping_v1"
  - clusters: array<object>（4 项）
    - []: object
      - cluster_id: string，示例 "C01"
      - topic_id: string，示例 "C01"
      - topic_name: string，示例 "推理加速与令牌分配"
      - size: number，示例 2
      - doc_indices: array<number>（2 项）
      - representative_terms: array<string>（4 项）
      - members: array<object>（2 项）
        - []: object
          - document_id: string，示例 "DOC-EN-024"
          - title: string，示例 "Timestep-Aware Block Masking for Efficie…"
      - feature_statistics: object
        - intra_cluster_similarity: number，示例 0.518
        - inter_cluster_separation: number，示例 0.235
        - semantic_coherence: number，示例 0.85
      - ratio: number，示例 0.4
      - representative_documents: array<object>（2 项）
        - []: object
          - document_id: string，示例 "DOC-EN-024"
          - title: string，示例 "Timestep-Aware Block Masking for Efficie…"
  - document_assignments: array<object>（5 项）
    - []: object
      - document_id: string，示例 "DOC-EN-018"
      - title: string，示例 "All Roads Lead to Rome: Incentivizing Di…"
      - publication_date: string，示例 "2026-04-01"
      - publication_year: number，示例 2026
      - cluster_id: string，示例 "C02"
      - similarity_to_centroid: number，示例 1
      - key_evidence: string，示例 "The study compares reinforcement-learnin…"
  - semantic_projection: array<object>（5 项）
    - []: object
      - document_id: string，示例 "DOC-EN-018"
      - title: string，示例 "All Roads Lead to Rome: Incentivizing Di…"
      - cluster_id: string，示例 "C02"
      - x: number，示例 35.792
      - y: number，示例 95
  - theme_trend_analysis: object
    - years: array<number>
    - series: array<object>（2 项）
      - []: object
        - cluster_id: string，示例 "C01"
        - yearly_counts: array<number>
    - rising_cluster_id: null（本示例中为空）
    - emerging_cluster_id: null（本示例中为空）
    - stable_cluster_id: null（本示例中为空）
    - summary: string，示例 "2026 年间各主题分布均衡，无明显上升或新兴趋势。"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "input_summary": {
      "document_count": 5,
      "parsed_sentence_count": 12
    },
    "cluster_dimension_name": "技术路线聚类",
    "clustering_quality": {
      "cluster_count": 4,
      "intra_cluster_similarity": 0.518,
      "algorithm_requested": "move_aligned",
      "algorithm_used": "task_anchored_grouping_v1"
    },
    "clusters": [
      {
        "cluster_id": "C01",
        "topic_id": "C01",
        "topic_name": "推理加速与令牌分配",
        "size": 2,
        "doc_indices": [
          1,
          2
        ],
        "representative_terms": [
          "扩散模型推理加速",
          "视频推理令牌预算分配",
          "…（共 4 项，示例保留前 2 项）"
        ],
        "members": [
          {
            "document_id": "DOC-EN-024",
            "title": "Timestep-Aware Block Masking for Efficient Diffusion Model Inference"
          },
          {
            "document_id": "DOC-EN-028",
            "title": "TRIAGE: Hierarchical Visual Budgeting for Efficient Video Reasoning"
          }
        ],
        "feature_statistics": {
          "intra_cluster_similarity": 0.518,
          "inter_cluster_separation": 0.235,
          "semantic_coherence": 0.85
        },
        "ratio": 0.4,
        "representative_documents": [
          {
            "document_id": "DOC-EN-024",
            "title": "Timestep-Aware Block Masking for Efficient Diffusion Model Inference"
          },
          {
            "document_id": "DOC-EN-028",
            "title": "TRIAGE: Hierarchical Visual Budgeting for Efficient Video Reasoning"
          }
        ]
      },
      {
        "cluster_id": "C02",
        "topic_id": "C02",
        "topic_name": "多组策略优化",
        "size": 1,
        "doc_indices": [
          0
        ],
        "representative_terms": [
          "视觉推理多样性优化",
          "多组策略优化"
        ],
        "members": [
          {
            "document_id": "DOC-EN-018",
            "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models"
          }
        ],
        "feature_statistics": {
          "intra_cluster_similarity": null,
          "inter_cluster_separation": 0.476,
          "semantic_coherence": 0.7
        },
        "ratio": 0.2,
        "representative_documents": [
          {
            "document_id": "DOC-EN-018",
            "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models"
          }
        ]
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "document_assignments": [
      {
        "document_id": "DOC-EN-018",
        "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
        "publication_date": "2026-04-01",
        "publication_year": 2026,
        "cluster_id": "C02",
        "similarity_to_centroid": 1,
        "key_evidence": "The study compares reinforcement-learning vision-language models with their base models, identifies diversity collapse in GRPO, and proposes Multi-Group Policy …"
      },
      {
        "document_id": "DOC-EN-024",
        "title": "Timestep-Aware Block Masking for Efficient Diffusion Model Inference",
        "publication_date": "2026-03-20",
        "publication_year": 2026,
        "cluster_id": "C01",
        "similarity_to_centroid": 0.759,
        "key_evidence": "The work learns timestep-specific block masks for diffusion models, reuses cached features, and applies timestep-aware loss scaling and mask rectification to re…"
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "semantic_projection": [
      {
        "document_id": "DOC-EN-018",
        "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
        "cluster_id": "C02",
        "x": 35.792,
        "y": 95
      },
      {
        "document_id": "DOC-EN-024",
        "title": "Timestep-Aware Block Masking for Efficient Diffusion Model Inference",
        "cluster_id": "C01",
        "x": 95,
        "y": 60.447
      },
      "…（共 5 项，示例保留前 2 项）"
    ],
    "theme_trend_analysis": {
      "years": [
        2026
      ],
      "series": [
        {
          "cluster_id": "C01",
          "yearly_counts": [
            2
          ]
        },
        {
          "cluster_id": "C02",
          "yearly_counts": [
            1
          ]
        }
      ],
      "rising_cluster_id": null,
      "emerging_cluster_id": null,
      "stable_cluster_id": null,
      "summary": "2026 年间各主题分布均衡，无明显上升或新兴趋势。"
    }
  },
  "meta": {
    "request_id": "req_a2a32fa18b6d455baa91a758279bfc38",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 52556,
    "created_at": "2026-10-27T22:08:44.230005+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_9409bc2fc48248f9abc577811b68c9a0",
    "input_type": "texts",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_45eca2de0add4c24abdb7b39102d381f",
    "file_name": null
  }
}
```

### 17.2 批量文件

- **接口**：`POST /api/v1/cluster/deep/files`
- **Content-Type**：multipart/form-data

> 批量文件至少 4 篇（少于 4 篇返回 42201"至少需要 4 项输入数据"）

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scientific_document_texts` | file[] | 必填 | 多篇科技文献,至少 4 篇(批量文本模式专用参数)文件（上传 PDF/DOCX/TXT） |
| `document_metadata` | object[] | 必填 | 文献元数据(文献编号+发表时间),用于趋势分析与文献集沉淀。批量文本模式必填;批量文件模式由文件解析自动补充 |
| `document_metadata[].document_id` | string | 必填 | 文献编号，用于关联文本与元数据 |
| `document_metadata[].publication_date` | string | 选填 | 发表时间 |
| `document_metadata[].title` | string | 必填 | 文献题名 |
| `cluster_dimension` | string | 必填 | 聚类维度。枚举:"technology"(技术路线,默认)、"application"(应用场景);决定句子特征抽取视角与聚类语义 |
| `clustering_algorithm_type` | string | 选填 | 聚类算法类型。枚举:"auto"(默认,语步对齐语义分组)、"kmeans"、"spectral"(谱聚类)、"agglomerative"(凝聚聚类)、"hierarchical"(层次聚类,与 agglomerative 同算法)、"hdbscan";非 auto 时按轴语步句向量执行所选向量聚类,聚类质量低于默认语义分组 |
| `cluster_count` | integer | 选填 | 类簇数量(>=1,且需小于输入文献数量)。不指定时算法自动确定;auto(语义分组)下为软约束(允许±1浮动),指定向量算法下为精确簇数(hdbscan 为就近搜索) |
| `output_format` | string | 选填 | 输出格式(默认 JSON) |
| `training_samples` | file (.json) | 选填 | 可选上传资源：训练样本锚点（.json：编号+文本+题名） |
| `manually_labeled_category_data` | file (.json) | 选填 | 可选上传资源：人工标注类目标签锚点（.json：编号+人工标注类目标签） |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/cluster/deep/files' \
  -F 'scientific_document_texts=@paper_01.pdf' \
  -F 'scientific_document_texts=@paper_02.docx' \
  -F 'scientific_document_texts=@paper_03.pdf' \
  -F 'scientific_document_texts=@paper_04.pdf' \
  -F 'document_metadata=[{"document_id":"DOC001","publication_date":"2025-03-18","title":"工业表面缺陷检测研究"},{"document_id":"DOC002","title":"复杂场景视觉识别方法"},{"document_id":"DOC003","publication_date":"2024-11-02","title":"多尺度特征融合的表面缺陷检测"},{"document_id":"DOC004","title":"基于注意力机制的工业质检方法"}]' \
  -F 'cluster_dimension=technology' \
  -F 'clustering_algorithm_type=auto' \
  -F 'output_format=JSON'
```

#### 响应字段（data）

```
- data: object
  - input_summary: object
    - document_count: number，示例 4
    - parsed_sentence_count: number，示例 162
  - cluster_dimension_name: string，示例 "技术路线聚类"
  - clustering_quality: object
    - cluster_count: number，示例 4
    - intra_cluster_similarity: null（本示例中为空）
    - algorithm_requested: string，示例 "move_aligned"
    - algorithm_used: string，示例 "task_anchored_grouping_v1"
  - clusters: array<object>（4 项）
    - []: object
      - cluster_id: string，示例 "C01"
      - topic_id: string，示例 "C01"
      - topic_name: string，示例 "SVM-LSTM混合模型预测"
      - size: number，示例 1
      - doc_indices: array<number>
      - representative_terms: array<string>（2 项）
      - members: array<object>
        - []: object
          - document_id: string，示例 "DOC001"
          - title: string，示例 "工业表面缺陷检测研究"
      - feature_statistics: object
        - intra_cluster_similarity: null（本示例中为空）
        - inter_cluster_separation: number，示例 0.535
        - semantic_coherence: number，示例 1
      - ratio: number，示例 0.25
      - representative_documents: array<object>
        - []: object
          - document_id: string，示例 "DOC001"
          - title: string，示例 "工业表面缺陷检测研究"
  - document_assignments: array<object>（4 项）
    - []: object
      - document_id: string，示例 "DOC001"
      - title: string，示例 "工业表面缺陷检测研究"
      - publication_date: string，示例 "2025-03-18"
      - publication_year: number，示例 2025
      - cluster_id: string，示例 "C01"
      - similarity_to_centroid: number，示例 1
      - key_evidence: string，示例 "通过深入分析光伏电站运维数据的海量异构、多维关联和时变特征，构建了融合Hadoo…"
  - semantic_projection: array<object>（4 项）
    - []: object
      - document_id: string，示例 "DOC001"
      - title: string，示例 "工业表面缺陷检测研究"
      - cluster_id: string，示例 "C01"
      - x: number，示例 5.032
      - y: number，示例 77.599
  - theme_trend_analysis: object
    - years: array<number>（2 项）
    - series: array<object>（2 项）
      - []: object
        - cluster_id: string，示例 "C01"
        - yearly_counts: array<number>（2 项）
    - rising_cluster_id: null（本示例中为空）
    - emerging_cluster_id: string，示例 "C01"
    - stable_cluster_id: null（本示例中为空）
    - summary: string，示例 "2024–2025 年间趋势：新兴类簇 C01（新出现的主题方向，1 篇）。"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "input_summary": {
      "document_count": 4,
      "parsed_sentence_count": 162
    },
    "cluster_dimension_name": "技术路线聚类",
    "clustering_quality": {
      "cluster_count": 4,
      "intra_cluster_similarity": null,
      "algorithm_requested": "move_aligned",
      "algorithm_used": "task_anchored_grouping_v1"
    },
    "clusters": [
      {
        "cluster_id": "C01",
        "topic_id": "C01",
        "topic_name": "SVM-LSTM混合模型预测",
        "size": 1,
        "doc_indices": [
          0
        ],
        "representative_terms": [
          "光伏电站故障预测",
          "SVM-LSTM混合模型预测"
        ],
        "members": [
          {
            "document_id": "DOC001",
            "title": "工业表面缺陷检测研究"
          }
        ],
        "feature_statistics": {
          "intra_cluster_similarity": null,
          "inter_cluster_separation": 0.535,
          "semantic_coherence": 1
        },
        "ratio": 0.25,
        "representative_documents": [
          {
            "document_id": "DOC001",
            "title": "工业表面缺陷检测研究"
          }
        ]
      },
      {
        "cluster_id": "C02",
        "topic_id": "C02",
        "topic_name": "聚类与主成分分析结合",
        "size": 1,
        "doc_indices": [
          1
        ],
        "representative_terms": [
          "地震动记录选取",
          "聚类与主成分分析结合"
        ],
        "members": [
          {
            "document_id": "DOC002",
            "title": "复杂场景视觉识别方法"
          }
        ],
        "feature_statistics": {
          "intra_cluster_similarity": null,
          "inter_cluster_separation": 0.535,
          "semantic_coherence": 1
        },
        "ratio": 0.25,
        "representative_documents": [
          {
            "document_id": "DOC002",
            "title": "复杂场景视觉识别方法"
          }
        ]
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "document_assignments": [
      {
        "document_id": "DOC001",
        "title": "工业表面缺陷检测研究",
        "publication_date": "2025-03-18",
        "publication_year": 2025,
        "cluster_id": "C01",
        "similarity_to_centroid": 1,
        "key_evidence": "通过深入分析光伏电站运维数据的海量异构、多维关联和时变特征，构建了融合Hadoop生态、机器学习和实时计算技术的四层架构系统。 系统采用Kafka+ Storm 流处理架构实现实时数据采集与处理，结合支持向量机-长短期记忆网络(Support Vector Ma-chine-Long Short Term Memory…"
      },
      {
        "document_id": "DOC002",
        "title": "复杂场景视觉识别方法",
        "publication_date": null,
        "publication_year": null,
        "cluster_id": "C02",
        "similarity_to_centroid": 1,
        "key_evidence": "本文将地震动记录按照震级、距离进行聚类分析，然后基于主成分分析对不同场地类别和聚类分组的地震动记录进行排序，提出了一种聚类与主成分分析相结合的自适应地震动记录选取方法。 首先，将PEER强震数据库中的 2157组水平双向地震动记录进行聚类分析，将地震动记录分为四组：第一组为大震级M远距离 $R ;$ 第二组是小震级 M…"
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "semantic_projection": [
      {
        "document_id": "DOC001",
        "title": "工业表面缺陷检测研究",
        "cluster_id": "C01",
        "x": 5.032,
        "y": 77.599
      },
      {
        "document_id": "DOC002",
        "title": "复杂场景视觉识别方法",
        "cluster_id": "C02",
        "x": 95,
        "y": 95
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "theme_trend_analysis": {
      "years": [
        2024,
        2025
      ],
      "series": [
        {
          "cluster_id": "C01",
          "yearly_counts": [
            0,
            1
          ]
        },
        {
          "cluster_id": "C03",
          "yearly_counts": [
            1,
            0
          ]
        }
      ],
      "rising_cluster_id": null,
      "emerging_cluster_id": "C01",
      "stable_cluster_id": null,
      "summary": "2024–2025 年间趋势：新兴类簇 C01（新出现的主题方向，1 篇）。"
    }
  },
  "meta": {
    "request_id": "req_8e56fbc7796541729bcd9f1786964023",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 82760,
    "created_at": "2026-10-27T22:38:53.959472+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_1a306d16b34e49fdaf79854ec6d73320",
    "input_type": "files",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_c42b099e573f48659d6a57c757430110",
    "file_name": null
  }
}
```

---

## 18. 聚类标签生成工具

**工具ID**：`cluster-label`

接收深度聚类模型输出的类簇短语集合，为每个类簇生成具有概括性、代表性和区分度的简短标签。

**功能特点**：短语清洗，候选标签生成，差异化优化

**适用场景**：聚类结果命名与专题组织

### 18.1 批量文本

- **接口**：`POST /api/v1/cluster-labels/generate`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `cluster_task_id` | string | 条件必填 | 已完成的深度聚类任务编号(tsk_ 前缀)。后端读取该任务的类簇短语集合生成标签;与 cluster_phrase_sets 二选一 |
| `cluster_phrase_sets` | object[] | 条件必填 | 直接提供深度聚类输出的类簇短语集合(API 调用路径;与 cluster_task_id 二选一) |
| `cluster_phrase_sets[].cluster_id` | string | 条件必填 | cluster_id 子字段 |
| `cluster_phrase_sets[].phrases` | string[] | 条件必填 | phrases 子字段 |
| `label_length_limit` | integer | 选填 | 标签长度限制(默认 12) |
| `language_type` | string | 选填 | 标签语言。枚举:"auto"(默认)、"zh"、"en" |
| `distinctiveness_threshold` | number | 选填 | 差异度阈值,范围 0-1。默认"自动"(不传该参数):不做差异化优化,以模型生成的标签为准;显式设定时为强制闸门——低于该阈值的标签将被强制优化到达标(差异度=标签间语义差异度,BGE-M3 相似度定标) |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/cluster-labels/generate' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "cluster_task_id": null,
  "cluster_phrase_sets": [
    {
      "cluster_id": "TECH-01",
      "phrases": [
        "推理多样性",
        "多组策略优化",
        "慢思考",
        "多步推理"
      ]
    },
    {
      "cluster_id": "TECH-02",
      "phrases": [
        "时间步块掩码",
        "特征复用",
        "关键帧选择",
        "令牌预算"
      ]
    },
    {
      "cluster_id": "TECH-03",
      "phrases": [
        "前景引导",
        "自适应预训练",
        "视觉表征"
      ]
    }
  ],
  "label_length_limit": 12,
  "language_type": "zh",
  "distinctiveness_threshold": 0.75
}
```

#### 响应字段（data）

```
- data: object
  - labels: array<object>（3 项）
    - []: object
      - cluster_id: string，示例 "TECH-01"
      - label: string，示例 "推理多样性与多组策略优化"
      - candidate_labels: array<string>（5 项）
      - evidence_terms: array<string>（2 项）
      - language: string，示例 "zh"
      - confidence: number，示例 0.892648
      - distinctiveness: number，示例 0.889146
      - coverage: number，示例 0.943369
      - evidence_support: number，示例 0.86559
      - generation_method: string，示例 "semantic_phrase_pair"
      - phrase_count: number，示例 4
      - optimization: object
        - cluster_id: string，示例 "TECH-01"
        - before_label: string，示例 "推理多样性"
        - after_label: string，示例 "推理多样性与多组策略优化"
        - changed: boolean，示例 true
        - reason: string，示例 "低置信度门控触发；在近似同分候选中选择由两条输入证据共同支持的标签。"
        - before_distinctiveness: number，示例 0.893273
        - after_distinctiveness: number，示例 0.889146
        - threshold_passed: boolean，示例 true
      - soft_rule_fallback: object
        - triggered: boolean，示例 true
        - trigger_reasons: array<string>（2 项）
        - rule_ids: array<string>
        - before_label: string，示例 "推理多样性"
        - after_label: string，示例 "推理多样性与多组策略优化"
        - changed: boolean，示例 true
        - contribution: number，示例 0.075
        - max_contribution: number，示例 0.08
        - eligible_candidate_count: number，示例 6
        - hard_mapping_used: boolean，示例 false
        - decision_reason: string，示例 "低置信度门控触发；在近似同分候选中选择由两条输入证据共同支持的标签。"
      - linked_document_ids: array<undefined>
      - alternatives: array<string>（4 项）
      - recommended_label: string，示例 "推理多样性与多组策略优化"
      - status: string，示例 "generated"
      - representativeness: number，示例 0.943369
      - evidence: object
        - keywords: array<string>（2 项）
        - named_entities: array<undefined>
        - center_sentence: string，示例 ""
      - difference_explanation: string，示例 "推荐标签达到当前类簇间差异阈值。"
  - cluster_count: number，示例 3
  - generated_label_count: number，示例 3
  - parameters: object
    - label_length_limit: number，示例 12
    - language_type: string，示例 "zh"
    - distinctiveness_threshold: number，示例 0.75
    - candidate_count: number，示例 5
    - pair_similarity_lower_bound: number，示例 0.35
    - pair_similarity_upper_bound: number，示例 0.88
    - soft_score_gap_limit: number，示例 0.075
    - soft_relevance_drop_limit: number，示例 0.04
    - soft_coverage_drop_limit: number，示例 0.03
    - max_soft_fallback_contribution: number，示例 0.08
  - statistics: object
    - average_confidence: number，示例 0.894328
    - average_distinctiveness: number，示例 0.885633
    - average_coverage: number，示例 0.943494
    - distinctiveness_pass_count: number，示例 3
    - soft_fallback_triggered_count: number，示例 1
    - soft_fallback_changed_count: number，示例 1
  - label_generation_process_report: object
    - engine_version: string，示例 "cluster-label-semantic-soft-fallback-v11"
    - input_type: string，示例 "cluster_phrase_sets"
    - run_mode: string，示例 "batch"
    - cluster_count: number，示例 3
    - generated_label_count: number，示例 3
    - language_distribution: object
      - zh: number，示例 3
    - parameters: object
      - label_length_limit: number，示例 12
      - language_type: string，示例 "zh"
      - distinctiveness_threshold: number，示例 0.75
      - candidate_count: number，示例 5
      - pair_similarity_lower_bound: number，示例 0.35
      - pair_similarity_upper_bound: number，示例 0.88
      - soft_score_gap_limit: number，示例 0.075
      - soft_relevance_drop_limit: number，示例 0.04
      - soft_coverage_drop_limit: number，示例 0.03
      - max_soft_fallback_contribution: number，示例 0.08
    - stages: array<object>（7 项）
      - []: object
        - order: number，示例 1
        - name: string，示例 "证据归一化"
        - status: string，示例 "completed"
        - output: string，示例 "类簇短语证据清洗与归一化"
    - topic_library_used: boolean，示例 false
    - semantic_rule_library_used: boolean，示例 true
    - hard_rule_mapping_used: boolean，示例 false
    - soft_fallback_used: boolean，示例 true
    - gold_labels_used_in_inference: boolean，示例 false
    - llm_used: boolean，示例 true
    - llm_failures: array<undefined>
    - distinctiveness_changes_label: boolean，示例 false
    - soft_fallback_triggered_count: number，示例 1
    - soft_fallback_changed_count: number，示例 1
    - average_confidence: number，示例 0.894328
    - average_distinctiveness: number，示例 0.885633
    - average_coverage: number，示例 0.943494
    - requested_generation_mode: string，示例 "hybrid"
    - effective_generation_mode: string，示例 "hybrid"
    - llm_requested: boolean，示例 true
    - llm_configured: boolean，示例 true
    - llm_model: string，示例 "glm-5.2"
    - llm_candidate_generation_enabled: boolean，示例 true
    - llm_failure_count: number，示例 0
    - llm_fallback_used: boolean，示例 false
    - llm_fallback_reason: null（本示例中为空）
    - requested_label_engine_mode: string，示例 "bounded_soft_fallback"
    - effective_label_engine_mode: string，示例 "bounded_soft_fallback"
    - production_default_engine: string，示例 "bounded_soft_fallback"
    - semantic_reranking_model: string，示例 "bge-m3"
    - direct_input_contract: string，示例 "deep_clustering_cluster_phrase_sets"
  - label_distinctiveness_optimization_result: object
    - threshold: number，示例 0.75
    - optimized_count: number，示例 0
    - passed_count: number，示例 3
    - failed_count: number，示例 0
    - items: array<object>（3 项）
      - []: object
        - cluster_id: string，示例 "TECH-01"
        - before_label: string，示例 "推理多样性"
        - after_label: string，示例 "推理多样性与多组策略优化"
        - changed: boolean，示例 true
        - reason: string，示例 "低置信度门控触发；在近似同分候选中选择由两条输入证据共同支持的标签。"
        - before_distinctiveness: number，示例 0.893273
        - after_distinctiveness: number，示例 0.889146
        - threshold_passed: boolean，示例 true
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "labels": [
      {
        "cluster_id": "TECH-01",
        "label": "推理多样性与多组策略优化",
        "candidate_labels": [
          "推理多样性与多组策略优化",
          "推理多样性",
          "…（共 5 项，示例保留前 2 项）"
        ],
        "evidence_terms": [
          "推理多样性",
          "多组策略优化"
        ],
        "language": "zh",
        "confidence": 0.892648,
        "distinctiveness": 0.889146,
        "coverage": 0.943369,
        "evidence_support": 0.86559,
        "generation_method": "semantic_phrase_pair",
        "phrase_count": 4,
        "optimization": {
          "cluster_id": "TECH-01",
          "before_label": "推理多样性",
          "after_label": "推理多样性与多组策略优化",
          "changed": true,
          "reason": "低置信度门控触发；在近似同分候选中选择由两条输入证据共同支持的标签。",
          "before_distinctiveness": 0.893273,
          "after_distinctiveness": 0.889146,
          "threshold_passed": true
        },
        "soft_rule_fallback": {
          "triggered": true,
          "trigger_reasons": [
            "top1_single_evidence",
            "top1_near_tie"
          ],
          "rule_ids": [
            "SR_MULTI_EVIDENCE_NEAR_TIE"
          ],
          "before_label": "推理多样性",
          "after_label": "推理多样性与多组策略优化",
          "changed": true,
          "contribution": 0.075,
          "max_contribution": 0.08,
          "eligible_candidate_count": 6,
          "hard_mapping_used": false,
          "decision_reason": "低置信度门控触发；在近似同分候选中选择由两条输入证据共同支持的标签。"
        },
        "linked_document_ids": [],
        "alternatives": [
          "推理多样性",
          "推理策略多样性优化",
          "…（共 4 项，示例保留前 2 项）"
        ],
        "recommended_label": "推理多样性与多组策略优化",
        "status": "generated",
        "representativeness": 0.943369,
        "evidence": {
          "keywords": [
            "推理多样性",
            "多组策略优化"
          ],
          "named_entities": [],
          "center_sentence": ""
        },
        "difference_explanation": "推荐标签达到当前类簇间差异阈值。"
      },
      {
        "cluster_id": "TECH-02",
        "label": "时间步块掩码与特征复用",
        "candidate_labels": [
          "时间步块掩码与特征复用",
          "时间步块掩码",
          "…（共 5 项，示例保留前 2 项）"
        ],
        "evidence_terms": [
          "时间步块掩码",
          "特征复用"
        ],
        "language": "zh",
        "confidence": 0.891499,
        "distinctiveness": 0.875337,
        "coverage": 0.940684,
        "evidence_support": 0.841138,
        "generation_method": "semantic_phrase_pair",
        "phrase_count": 4,
        "optimization": {
          "cluster_id": "TECH-02",
          "before_label": "时间步块掩码与特征复用",
          "after_label": "时间步块掩码与特征复用",
          "changed": false,
          "reason": "语义最高分已由多条输入证据支持，软规则不覆盖主模型判断。",
          "before_distinctiveness": 0.875337,
          "after_distinctiveness": 0.875337,
          "threshold_passed": true
        },
        "soft_rule_fallback": {
          "triggered": false,
          "trigger_reasons": [],
          "rule_ids": [],
          "before_label": "时间步块掩码与特征复用",
          "after_label": "时间步块掩码与特征复用",
          "changed": false,
          "contribution": 0,
          "max_contribution": 0.08,
          "eligible_candidate_count": 0,
          "hard_mapping_used": false,
          "decision_reason": "语义最高分已由多条输入证据支持，软规则不覆盖主模型判断。"
        },
        "linked_document_ids": [],
        "alternatives": [
          "时间步块掩码",
          "时间步块掩码与关键帧选择",
          "…（共 4 项，示例保留前 2 项）"
        ],
        "recommended_label": "时间步块掩码与特征复用",
        "status": "generated",
        "representativeness": 0.940684,
        "evidence": {
          "keywords": [
            "时间步块掩码",
            "特征复用"
          ],
          "named_entities": [],
          "center_sentence": ""
        },
        "difference_explanation": "推荐标签达到当前类簇间差异阈值。"
      },
      "…（共 3 项，示例保留前 2 项）"
    ],
    "cluster_count": 3,
    "generated_label_count": 3,
    "parameters": {
      "label_length_limit": 12,
      "language_type": "zh",
      "distinctiveness_threshold": 0.75,
      "candidate_count": 5,
      "pair_similarity_lower_bound": 0.35,
      "pair_similarity_upper_bound": 0.88,
      "soft_score_gap_limit": 0.075,
      "soft_relevance_drop_limit": 0.04,
      "soft_coverage_drop_limit": 0.03,
      "max_soft_fallback_contribution": 0.08
    },
    "statistics": {
      "average_confidence": 0.894328,
      "average_distinctiveness": 0.885633,
      "average_coverage": 0.943494,
      "distinctiveness_pass_count": 3,
      "soft_fallback_triggered_count": 1,
      "soft_fallback_changed_count": 1
    },
    "label_generation_process_report": {
      "engine_version": "cluster-label-semantic-soft-fallback-v11",
      "input_type": "cluster_phrase_sets",
      "run_mode": "batch",
      "cluster_count": 3,
      "generated_label_count": 3,
      "language_distribution": {
        "zh": 3
      },
      "parameters": {
        "label_length_limit": 12,
        "language_type": "zh",
        "distinctiveness_threshold": 0.75,
        "candidate_count": 5,
        "pair_similarity_lower_bound": 0.35,
        "pair_similarity_upper_bound": 0.88,
        "soft_score_gap_limit": 0.075,
        "soft_relevance_drop_limit": 0.04,
        "soft_coverage_drop_limit": 0.03,
        "max_soft_fallback_contribution": 0.08
      },
      "stages": [
        {
          "order": 1,
          "name": "证据归一化",
          "status": "completed",
          "output": "类簇短语证据清洗与归一化"
        },
        {
          "order": 2,
          "name": "短语语义编码",
          "status": "completed",
          "output": "BGE-M3 短语向量编码完成"
        },
        "…（共 7 项，示例保留前 2 项）"
      ],
      "topic_library_used": false,
      "semantic_rule_library_used": true,
      "hard_rule_mapping_used": false,
      "soft_fallback_used": true,
      "gold_labels_used_in_inference": false,
      "llm_used": true,
      "llm_failures": [],
      "distinctiveness_changes_label": false,
      "soft_fallback_triggered_count": 1,
      "soft_fallback_changed_count": 1,
      "average_confidence": 0.894328,
      "average_distinctiveness": 0.885633,
      "average_coverage": 0.943494,
      "requested_generation_mode": "hybrid",
      "effective_generation_mode": "hybrid",
      "llm_requested": true,
      "llm_configured": true,
      "llm_model": "glm-5.2",
      "llm_candidate_generation_enabled": true,
      "llm_failure_count": 0,
      "llm_fallback_used": false,
      "llm_fallback_reason": null,
      "requested_label_engine_mode": "bounded_soft_fallback",
      "effective_label_engine_mode": "bounded_soft_fallback",
      "production_default_engine": "bounded_soft_fallback",
      "semantic_reranking_model": "bge-m3",
      "direct_input_contract": "deep_clustering_cluster_phrase_sets"
    },
    "label_distinctiveness_optimization_result": {
      "threshold": 0.75,
      "optimized_count": 0,
      "passed_count": 3,
      "failed_count": 0,
      "items": [
        {
          "cluster_id": "TECH-01",
          "before_label": "推理多样性",
          "after_label": "推理多样性与多组策略优化",
          "changed": true,
          "reason": "低置信度门控触发；在近似同分候选中选择由两条输入证据共同支持的标签。",
          "before_distinctiveness": 0.893273,
          "after_distinctiveness": 0.889146,
          "threshold_passed": true
        },
        {
          "cluster_id": "TECH-02",
          "before_label": "时间步块掩码与特征复用",
          "after_label": "时间步块掩码与特征复用",
          "changed": false,
          "reason": "语义最高分已由多条输入证据支持，软规则不覆盖主模型判断。",
          "before_distinctiveness": 0.875337,
          "after_distinctiveness": 0.875337,
          "threshold_passed": true
        },
        "…（共 3 项，示例保留前 2 项）"
      ]
    }
  },
  "meta": {
    "request_id": "req_b90a8daf80a6449d886e5d678fc01b8c",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 19161,
    "created_at": "2026-10-27T22:09:03.407911+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_653f398b996f42908fc6b84eb9839f99",
    "input_type": "texts",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_259df59a39bd4000b129079178a224ea",
    "file_name": null
  }
}
```

---

## 19. 结构化自动综述工具

**工具ID**：`structured-review`

对科技文献检索结果集或指定文献集进行自动化综合分析，以“研究问题—研究方法—研究进展”三层树形结构揭示研究脉络与知识骨架，并支持溯源询证。

**功能特点**：问题方法进展三层综述，趋势与证据溯源

**适用场景**：批量文献综述与进展梳理

> collection_id 来源于聚类标签生成任务沉淀的簇文献集，可通过 `GET /api/v1/collections/cluster-sets` 查询当前可用集合。

### 19.1 批量文本

- **接口**：`POST /api/v1/review/structured/texts`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_set` | object[] | 必填 | 文献集,至少 3 篇。批量文本模式传文本数组;批量文件模式传文件;指定文献集模式传集合引用对象 |
| `document_set[].document_id` | string | 必填 | 文献编号，用于关联文本与元数据 |
| `document_set[].text` | string | 必填 | 用户输入的文本内容 |
| `topic_or_keywords` | string | 必填 | 研究主题或关键词。限定综述的研究范围 |
| `document_metadata` | object[] | 必填 | 文献元数据。批量文本模式需逐篇提供;文件/文献集模式自动解析 |
| `document_metadata[].document_id` | string | 必填 | 文献编号，用于关联文本与元数据 |
| `document_metadata[].title` | string | 必填 | 文献题名 |
| `document_metadata[].publication_date` | string | 选填 | 发表时间 |
| `document_metadata[].source` | string | 选填 | 资源来源或文献来源 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/review/structured/texts' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_set": [
    {
      "document_id": "DOC-EN-018",
      "text": "The study compares reinforcement-learning vision-language models with their base models, identifies diversity collapse in GRPO, and proposes Multi-Group Policy Optimization to encourage divergent reasoning across multiple solutions."
    },
    {
      "document_id": "DOC-EN-024",
      "text": "The work learns timestep-specific block masks for diffusion models, reuses cached features, and applies timestep-aware loss scaling and mask rectification to reduce inference cost while retaining generation quality."
    },
    {
      "document_id": "DOC-EN-028",
      "text": "TRIAGE treats video reasoning as hierarchical resource allocation. It first selects keyframes and then allocates core and context tokens with relevance and diversity constraints to reduce memory and computation."
    },
    {
      "document_id": "DOC-EN-026",
      "text": "TimeReasoner studies whether slow-thinking language models can reason over temporal dynamics through inference-time multi-step reasoning."
    }
  ],
  "topic_or_keywords": "视觉与语言模型的推理多样性、高效推理与时间推理",
  "document_metadata": [
    {
      "document_id": "DOC-EN-018",
      "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
      "publication_date": "2026-04-01",
      "source": "arXiv"
    },
    {
      "document_id": "DOC-EN-024",
      "title": "Timestep-Aware Block Masking for Efficient Diffusion Model Inference",
      "publication_date": "2026-03-20",
      "source": "arXiv"
    },
    {
      "document_id": "DOC-EN-028",
      "title": "TRIAGE: Hierarchical Visual Budgeting for Efficient Video Reasoning",
      "publication_date": "2026-01-30",
      "source": "Conference preprint"
    },
    {
      "document_id": "DOC-EN-026",
      "title": "Can Slow-Thinking LLMs Reason Over Time?",
      "publication_date": "2026-02-15",
      "source": "Conference preprint"
    }
  ]
}
```

#### 响应字段（data）

```
- data: object
  - topic: string，示例 "视觉与语言模型的推理多样性、高效推理与时间推理"
  - document_count: number，示例 4
  - tree: array<object>（4 项）
    - []: object
      - question_id: string，示例 "RQ-01"
      - research_question: string，示例 "GRPO推理多样性坍缩与多组策略优化"
      - question_summary: string，示例 "针对强化学习视觉与语言模型GRPO中的推理多样性坍缩问题，提出Multi-Gro…"
      - document_count: number，示例 1
      - document_ids: array<string>
      - evidence_ids: array<string>
      - methods: array<object>
        - []: object
          - method_id: string，示例 "M-01"
          - method: string，示例 "Multi-Group Policy Optimization（多组策略优化），…"
          - source_ids: array<string>
          - evidence_ids: array<string>
          - progress: array<undefined>
  - cluster_induction_results: object
    - cluster_count: number，示例 4
    - clusters: array<object>（4 项）
      - []: object
        - cluster_id: string，示例 "PC-001"
        - label: string，示例 "GRPO推理多样性坍缩与多组策略优化"
        - summary: string，示例 "针对强化学习视觉与语言模型GRPO中的推理多样性坍缩问题，提出Multi-Gro…"
        - question_count: number，示例 1
        - document_count: number，示例 1
        - document_ids: array<string>
        - research_questions: array<string>
        - evidence_ids: array<string>
        - cohesion: number，示例 1
    - induction_basis: string，示例 "研究问题语义相似度、研究方法共现与来源证据一致性"
    - diagnostics: object
      - selection_mode: string，示例 "per_document_merge_0.70"
      - selected_k: number，示例 4
      - candidates: array<undefined>
      - representation: string，示例 "bge-m3"
      - candidate_count: number，示例 4
  - structured_report: object
    - title: string，示例 "视觉与语言模型的推理多样性、高效推理与时间推理结构化综述"
    - overview: string，示例 "本综述围绕视觉与语言模型的推理多样性、高效推理与时间推理四个研究主题展开。在推理…"
    - sections: array<object>（4 项）
      - []: object
        - section_id: string，示例 "SEC-01"
        - cluster_id: string，示例 "PC-001"
        - title: string，示例 "GRPO推理多样性坍缩与多组策略优化"
        - content: string，示例 "该类簇关注强化学习视觉与语言模型中的推理多样性问题。研究通过将强化学习视觉与语言…"
        - evidence_ids: array<string>
  - trend_hotspot_distribution: object
    - time_range: string，示例 "2026年"
    - hotspots: array<object>（4 项）
      - []: object
        - name: string，示例 "慢思考语言模型的推理时时间推理"
        - score: number，示例 0.655
        - status: string，示例 "持续关注"
        - cluster_id: string，示例 "PC-004"
        - document_count: number，示例 1
        - supporting_years: array<number>
        - year_coverage: number，示例 0.5
    - reliability_note: string，示例 "样本量小（4篇），强度与趋势仅供参考；文献年份集中，趋势方向参考价值有限"
  - evidence_index: array<object>（8 项）
    - []: object
      - evidence_id: string，示例 "EV-001-Q01"
      - document_id: string，示例 "DOC-EN-018"
      - title: string，示例 "All Roads Lead to Rome: Incentivizing Di…"
      - source_section: string，示例 "text"
      - evidence_excerpt: string，示例 "identifies diversity collapse in GRPO, a…"
      - quote: string，示例 "identifies diversity collapse in GRPO, a…"
      - start: number，示例 89
      - end: number，示例 231
      - supported_nodes: array<string>
  - statistics: object
    - document_count: number，示例 4
    - research_question_count: number，示例 4
    - method_count: number，示例 4
    - evidence_sentence_count: number，示例 8
    - trend_hotspot_status: string，示例 "computed"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "topic": "视觉与语言模型的推理多样性、高效推理与时间推理",
    "document_count": 4,
    "tree": [
      {
        "question_id": "RQ-01",
        "research_question": "GRPO推理多样性坍缩与多组策略优化",
        "question_summary": "针对强化学习视觉与语言模型GRPO中的推理多样性坍缩问题，提出Multi-Group Policy Optimization以促进跨多个解的发散性推理路径。",
        "document_count": 1,
        "document_ids": [
          "DOC-EN-018"
        ],
        "evidence_ids": [
          "EV-001-Q01"
        ],
        "methods": [
          {
            "method_id": "M-01",
            "method": "Multi-Group Policy Optimization（多组策略优化），并与基座模型进行对比实验",
            "source_ids": [
              "DOC-EN-018"
            ],
            "evidence_ids": [
              "EV-001-M01"
            ],
            "progress": []
          }
        ]
      },
      {
        "question_id": "RQ-02",
        "research_question": "扩散模型高效推理",
        "question_summary": "研究如何在保持生成质量的同时降低扩散模型的推理成本。",
        "document_count": 1,
        "document_ids": [
          "DOC-EN-024"
        ],
        "evidence_ids": [
          "EV-002-Q01"
        ],
        "methods": [
          {
            "method_id": "M-02",
            "method": "学习时间步特定的块掩码、复用缓存特征、时间步感知损失缩放与掩码修正",
            "source_ids": [
              "DOC-EN-024"
            ],
            "evidence_ids": [
              "EV-002-M01"
            ],
            "progress": []
          }
        ]
      },
      "…（共 4 项，示例保留前 2 项）"
    ],
    "cluster_induction_results": {
      "cluster_count": 4,
      "clusters": [
        {
          "cluster_id": "PC-001",
          "label": "GRPO推理多样性坍缩与多组策略优化",
          "summary": "针对强化学习视觉与语言模型GRPO中的推理多样性坍缩问题，提出Multi-Group Policy Optimization以促进跨多个解的发散性推理路径。",
          "question_count": 1,
          "document_count": 1,
          "document_ids": [
            "DOC-EN-018"
          ],
          "research_questions": [
            "如何解决强化学习视觉与语言模型（如GRPO）中的推理多样性坍缩问题，以鼓励多样化的推理路径？"
          ],
          "evidence_ids": [
            "EV-001-Q01"
          ],
          "cohesion": 1
        },
        {
          "cluster_id": "PC-002",
          "label": "扩散模型高效推理",
          "summary": "研究如何在保持生成质量的同时降低扩散模型的推理成本。",
          "question_count": 1,
          "document_count": 1,
          "document_ids": [
            "DOC-EN-024"
          ],
          "research_questions": [
            "如何降低扩散模型的推理成本同时保持生成质量？"
          ],
          "evidence_ids": [
            "EV-002-Q01"
          ],
          "cohesion": 1
        },
        "…（共 4 项，示例保留前 2 项）"
      ],
      "induction_basis": "研究问题语义相似度、研究方法共现与来源证据一致性",
      "diagnostics": {
        "selection_mode": "per_document_merge_0.70",
        "selected_k": 4,
        "candidates": [],
        "representation": "bge-m3",
        "candidate_count": 4
      }
    },
    "structured_report": {
      "title": "视觉与语言模型的推理多样性、高效推理与时间推理结构化综述",
      "overview": "本综述围绕视觉与语言模型的推理多样性、高效推理与时间推理四个研究主题展开。在推理多样性方面，研究识别出强化学习视觉与语言模型GRPO中的多样性坍缩问题，并提出Multi-Group Policy Optimization以鼓励跨多个解的发散性推理路径。在高效推理方面，一类工作通过学习时间步特定的块掩码、复用缓存特征并采…",
      "sections": [
        {
          "section_id": "SEC-01",
          "cluster_id": "PC-001",
          "title": "GRPO推理多样性坍缩与多组策略优化",
          "content": "该类簇关注强化学习视觉与语言模型中的推理多样性问题。研究通过将强化学习视觉与语言模型与其基础模型进行比较，识别出GRPO算法中存在的推理多样性坍缩现象，即模型在强化学习训练后推理路径趋于收敛、缺乏多样化的问题。针对这一问题，研究者提出Multi-Group Policy Optimization（多组策略优化）方法，其…",
          "evidence_ids": [
            "EV-001-Q01"
          ]
        },
        {
          "section_id": "SEC-02",
          "cluster_id": "PC-002",
          "title": "扩散模型高效推理",
          "content": "该类簇研究如何在保持生成质量的同时降低扩散模型的推理成本。研究问题直指扩散模型推理开销高的痛点。方法上，该工作为扩散模型学习时间步特定的块掩码，即在不同去噪时间步上选择性地计算网络模块；在此基础上复用缓存的特征，避免重复计算；并进一步采用时间步感知的损失缩放与掩码修正机制，以保证掩码学习与生成过程的一致性和稳定性。这些…",
          "evidence_ids": [
            "EV-002-Q01"
          ]
        },
        "…（共 4 项，示例保留前 2 项）"
      ]
    },
    "trend_hotspot_distribution": {
      "time_range": "2026年",
      "hotspots": [
        {
          "name": "慢思考语言模型的推理时时间推理",
          "score": 0.655,
          "status": "持续关注",
          "cluster_id": "PC-004",
          "document_count": 1,
          "supporting_years": [
            2026
          ],
          "year_coverage": 0.5
        },
        {
          "name": "GRPO推理多样性坍缩与多组策略优化",
          "score": 0.654,
          "status": "持续关注",
          "cluster_id": "PC-001",
          "document_count": 1,
          "supporting_years": [
            2026
          ],
          "year_coverage": 0.5
        },
        "…（共 4 项，示例保留前 2 项）"
      ],
      "reliability_note": "样本量小（4篇），强度与趋势仅供参考；文献年份集中，趋势方向参考价值有限"
    },
    "evidence_index": [
      {
        "evidence_id": "EV-001-Q01",
        "document_id": "DOC-EN-018",
        "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
        "source_section": "text",
        "evidence_excerpt": "identifies diversity collapse in GRPO, and proposes Multi-Group Policy Optimization to encourage divergent reasoning across multiple solutions",
        "quote": "identifies diversity collapse in GRPO, and proposes Multi-Group Policy Optimization to encourage divergent reasoning across multiple solutions",
        "start": 89,
        "end": 231,
        "supported_nodes": [
          "RQ-01"
        ]
      },
      {
        "evidence_id": "EV-001-M01",
        "document_id": "DOC-EN-018",
        "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
        "source_section": "text",
        "evidence_excerpt": "The study compares reinforcement-learning vision-language models with their base models",
        "quote": "The study compares reinforcement-learning vision-language models with their base models",
        "start": 0,
        "end": 87,
        "supported_nodes": [
          "M-01",
          "RQ-01"
        ]
      },
      "…（共 8 项，示例保留前 2 项）"
    ],
    "statistics": {
      "document_count": 4,
      "research_question_count": 4,
      "method_count": 4,
      "evidence_sentence_count": 8,
      "trend_hotspot_status": "computed"
    }
  },
  "meta": {
    "request_id": "req_c8a1297690a64389a1e3ea4fbc369e5e",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 46057,
    "created_at": "2026-10-27T22:09:49.479438+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_4b88eac9574c4c6e94b7bc8af50c0a4f",
    "input_type": "texts",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_cc1fdfbc3e3948448bb1c1d6feec69a9",
    "file_name": null
  }
}
```

### 19.2 批量文件

- **接口**：`POST /api/v1/review/structured/files`
- **Content-Type**：multipart/form-data

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_set` | file[] | 必填 | 文献集,至少 3 篇。批量模式传文本数组;批量文件模式传文件;指定文献集模式传集合引用对象文件（上传 PDF/DOCX/TXT） |
| `topic_or_keywords` | string | 必填 | 研究主题或关键词。限定综述的研究范围 |
| `document_metadata` | object[] | 条件必填 | 文献元数据。批量文本模式需逐篇提供;文件/文献集模式自动解析 |
| `document_metadata[].document_id` | string | 必填 | 文献编号，用于关联文本与元数据 |
| `document_metadata[].title` | string | 必填 | 文献题名 |
| `document_metadata[].publication_date` | string | 选填 | 发表时间 |
| `document_metadata[].source` | string | 选填 | 资源来源或文献来源 |

#### 请求示例

```bash
curl -X POST 'http://localhost:8000/api/v1/review/structured/files' \
  -F 'document_set=@paper_01.pdf' \
  -F 'document_set=@paper_02.docx' \
  -F 'topic_or_keywords=视觉与语言模型的推理多样性、高效推理与时间推理' \
  -F 'document_metadata=[{"document_id":"DOC-EN-018","title":"All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models","publication_date":"2026-04-01","source":"arXiv"},{"document_id":"DOC-EN-024","title":"Timestep-Aware Block Masking for Efficient Diffusion Model Inference","publication_date":"2026-03-20","source":"arXiv"},{"document_id":"DOC-EN-028","title":"TRIAGE: Hierarchical Visual Budgeting for Efficient Video Reasoning","publication_date":"2026-01-30","source":"Conference preprint"},{"document_id":"DOC-EN-026","title":"Can Slow-Thinking LLMs Reason Over Time?","publication_date":"2026-02-15","source":"Conference preprint"}]'
```

#### 响应字段（data）

```
- data: object
  - topic: string，示例 "视觉与语言模型的推理多样性、高效推理与时间推理"
  - document_count: number，示例 2
  - tree: array<object>
    - []: object
      - question_id: string，示例 "RQ-01"
      - research_question: string，示例 "合成数据混合下的经验风险最小化（ERM）局限性"
      - question_summary: string，示例 "研究在自然数据与LLM生成合成数据混合、且学习算法不知晓样本来源的序列学习任务设…"
      - document_count: number，示例 2
      - document_ids: array<string>（2 项）
      - evidence_ids: array<string>（4 项）
      - methods: array<object>
        - []: object
          - method_id: string，示例 "M-01"
          - method: string，示例 "We use the variable S to define sets tha…"
          - source_ids: array<string>（2 项）
          - evidence_ids: array<string>（2 项）
          - progress: array<object>
  - cluster_induction_results: object
    - cluster_count: number，示例 1
    - clusters: array<object>
      - []: object
        - cluster_id: string，示例 "PC-001"
        - label: string，示例 "合成数据混合下的经验风险最小化（ERM）局限性"
        - summary: string，示例 "研究在自然数据与LLM生成合成数据混合、且学习算法不知晓样本来源的序列学习任务设…"
        - question_count: number，示例 4
        - document_count: number，示例 2
        - document_ids: array<string>（2 项）
        - research_questions: array<string>（4 项）
        - evidence_ids: array<string>（4 项）
        - cohesion: number，示例 0.732215
    - induction_basis: string，示例 "研究问题语义相似度、研究方法共现与来源证据一致性"
    - diagnostics: object
      - selection_mode: string，示例 "per_document_merge_0.70"
      - selected_k: number，示例 1
      - candidates: array<undefined>
      - representation: string，示例 "bge-m3"
      - candidate_count: number，示例 4
  - structured_report: object
    - title: string，示例 "视觉与语言模型的推理多样性、高效推理与时间推理结构化综述"
    - overview: string，示例 "本综述围绕视觉与语言模型的推理多样性、高效推理与时间推理主题，对相关文献进行证据…"
    - sections: array<object>
      - []: object
        - section_id: string，示例 "SEC-01"
        - cluster_id: string，示例 "PC-001"
        - title: string，示例 "合成数据混合下的经验风险最小化（ERM）局限性"
        - content: string，示例 "随着大语言模型的普及与低成本生成能力的提升，合成内容大量涌入训练生态，这引出了一…"
        - evidence_ids: array<string>（4 项）
  - trend_hotspot_distribution: object
    - time_range: string，示例 "2026年"
    - hotspots: array<object>
      - []: object
        - name: string，示例 "合成数据混合下的经验风险最小化（ERM）局限性"
        - score: number，示例 0.632
        - status: string，示例 "持续关注"
        - cluster_id: string，示例 "PC-001"
        - document_count: number，示例 2
        - supporting_years: array<number>（2 项）
        - year_coverage: number，示例 0.5
    - reliability_note: string，示例 "样本量小（2篇），强度与趋势仅供参考；文献年份集中，趋势方向参考价值有限"
  - evidence_index: array<object>（10 项）
    - []: object
      - evidence_id: string，示例 "EV-001-Q01"
      - document_id: string，示例 "DOC-EN-018"
      - title: string，示例 "All Roads Lead to Rome: Incentivizing Di…"
      - source_section: string，示例 "text"
      - evidence_excerpt: string，示例 "Learning from Synthetic Data: Limitation…"
      - quote: string，示例 "Learning from Synthetic Data: Limitation…"
      - start: number，示例 0
      - end: number，示例 215
      - supported_nodes: array<string>
  - statistics: object
    - document_count: number，示例 2
    - research_question_count: number，示例 1
    - method_count: number，示例 1
    - evidence_sentence_count: number，示例 10
    - trend_hotspot_status: string，示例 "computed"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "topic": "视觉与语言模型的推理多样性、高效推理与时间推理",
    "document_count": 2,
    "tree": [
      {
        "question_id": "RQ-01",
        "research_question": "合成数据混合下的经验风险最小化（ERM）局限性",
        "question_summary": "研究在自然数据与LLM生成合成数据混合、且学习算法不知晓样本来源的序列学习任务设定下，经验风险最小化（ERM）的可能性与局限性。",
        "document_count": 2,
        "document_ids": [
          "DOC-EN-018",
          "DOC-EN-024"
        ],
        "evidence_ids": [
          "EV-001-Q01",
          "EV-001-Q02",
          "…（共 4 项，示例保留前 2 项）"
        ],
        "methods": [
          {
            "method_id": "M-01",
            "method": "We use the variable S to define sets that we actually want to think of as sequences, i",
            "source_ids": [
              "DOC-EN-018",
              "DOC-EN-024"
            ],
            "evidence_ids": [
              "EV-001-M01",
              "EV-002-M01"
            ],
            "progress": [
              {
                "progress_id": "M-01-P1",
                "summary": "在数据受合成数据污染的设定下，研究精确刻画了经验均值的方差，并证明一般情况下不存在使均匀加权成为MVUE的分布，尽管当α≤1/2时均匀加权有时能达到对t的最优依赖；同时给出下界表明自然算法（重复在上一轮数据上计算ERM假设）并不能持续改进分类器的泛化误差（定理5）；PAC设定下的主要结果通过归约利用了Angluin和L…",
                "conclusion": "合成数据污染下，朴素方法（均匀加权估计与迭代ERM算法）在统计与泛化性能上均无法保证持续或最优改进。",
                "source_ids": [
                  "DOC-EN-018"
                ],
                "source_evidence": [
                  {
                    "evidence_id": "M-01-EV01",
                    "document_id": "DOC-EN-018",
                    "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
                    "source_section": "text",
                    "evidence_excerpt": "We give a lower bound that demonstrates that the natural algorithm, repeatedly computing the ERM hypothesis on the previous round’s data, does not continually i…",
                    "start": 5545,
                    "end": 5767
                  },
                  {
                    "evidence_id": "M-01-EV02",
                    "document_id": "DOC-EN-018",
                    "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
                    "source_section": "text",
                    "evidence_excerpt": "Finally, our main results in the PAC setting make use of results of Angluin and Laird, Liu et al. and Mansouri and Ben-David via reductions",
                    "start": 9757,
                    "end": 9918
                  },
                  "…（共 4 项，示例保留前 2 项）"
                ],
                "evidence_sentences": [
                  {
                    "document_id": "DOC-EN-018",
                    "result": "We give a lower bound that demonstrates that the natural algorithm, repeatedly computing the ERM hypothesis on the previous round’s data, does not continually i…"
                  },
                  {
                    "document_id": "DOC-EN-018",
                    "result": "Finally, our main results in the PAC setting make use of results of Angluin and Laird, Liu et al. and Mansouri and Ben-David via reductions"
                  },
                  "…（共 4 项，示例保留前 2 项）"
                ]
              }
            ]
          }
        ]
      }
    ],
    "cluster_induction_results": {
      "cluster_count": 1,
      "clusters": [
        {
          "cluster_id": "PC-001",
          "label": "合成数据混合下的经验风险最小化（ERM）局限性",
          "summary": "研究在自然数据与LLM生成合成数据混合、且学习算法不知晓样本来源的序列学习任务设定下，经验风险最小化（ERM）的可能性与局限性。",
          "question_count": 4,
          "document_count": 2,
          "document_ids": [
            "DOC-EN-018",
            "DOC-EN-024"
          ],
          "research_questions": [
            "研究问题：Learning from Synthetic Data: Limitations of ERM* Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii",
            "研究问题：We model this scenario as a sequence of learning tasks where the input is aJan mix of natural and synthetic data, and",
            "…（共 4 项，示例保留前 2 项）"
          ],
          "evidence_ids": [
            "EV-001-Q01",
            "EV-001-Q02",
            "…（共 4 项，示例保留前 2 项）"
          ],
          "cohesion": 0.732215
        }
      ],
      "induction_basis": "研究问题语义相似度、研究方法共现与来源证据一致性",
      "diagnostics": {
        "selection_mode": "per_document_merge_0.70",
        "selected_k": 1,
        "candidates": [],
        "representation": "bge-m3",
        "candidate_count": 4
      }
    },
    "structured_report": {
      "title": "视觉与语言模型的推理多样性、高效推理与时间推理结构化综述",
      "overview": "本综述围绕视觉与语言模型的推理多样性、高效推理与时间推理主题，对相关文献进行证据约束的梳理。基于所提供的类簇与证据句，本报告聚焦于一个核心子方向：在大语言模型生成内容日益普遍、成本极低的背景下，当训练数据成为自然数据与合成数据的混合，且学习算法对单个样本的来源不可知时，经典经验风险最小化（ERM）范式所面临的可能性与局…",
      "sections": [
        {
          "section_id": "SEC-01",
          "cluster_id": "PC-001",
          "title": "合成数据混合下的经验风险最小化（ERM）局限性",
          "content": "随着大语言模型的普及与低成本生成能力的提升，合成内容大量涌入训练生态，这引出了一个基础性的学习理论问题：当自然数据与 LLM 生成的合成数据混合、且学习算法无法分辨任一样本来源时，经验风险最小化（ERM）还能否有效工作。Amin、Bie、Kong、Syed 与 Vassilvitskii（Google Research…",
          "evidence_ids": [
            "EV-001-Q01",
            "EV-001-Q02",
            "…（共 4 项，示例保留前 2 项）"
          ]
        }
      ]
    },
    "trend_hotspot_distribution": {
      "time_range": "2026年",
      "hotspots": [
        {
          "name": "合成数据混合下的经验风险最小化（ERM）局限性",
          "score": 0.632,
          "status": "持续关注",
          "cluster_id": "PC-001",
          "document_count": 2,
          "supporting_years": [
            2026,
            2026
          ],
          "year_coverage": 0.5
        }
      ],
      "reliability_note": "样本量小（2篇），强度与趋势仅供参考；文献年份集中，趋势方向参考价值有限"
    },
    "evidence_index": [
      {
        "evidence_id": "EV-001-Q01",
        "document_id": "DOC-EN-018",
        "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
        "source_section": "text",
        "evidence_excerpt": "Learning from Synthetic Data: Limitations of ERM* Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii Google Research Abstract The prevalence and lo…",
        "quote": "Learning from Synthetic Data: Limitations of ERM* Kareem Amin Alex Bie Weiwei Kong Umar Syed Sergei Vassilvitskii Google Research Abstract The prevalence and lo…",
        "start": 0,
        "end": 215,
        "supported_nodes": [
          "RQ-01"
        ]
      },
      {
        "evidence_id": "EV-001-Q02",
        "document_id": "DOC-EN-018",
        "title": "All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models",
        "source_section": "text",
        "evidence_excerpt": "We model this scenario as a sequence of learning tasks where the input is aJan mix of natural and synthetic data, and the learning algorithms are oblivious to t…",
        "quote": "We model this scenario as a sequence of learning tasks where the input is aJan mix of natural and synthetic data, and the learning algorithms are oblivious to t…",
        "start": 477,
        "end": 742,
        "supported_nodes": [
          "RQ-01"
        ]
      },
      "…（共 10 项，示例保留前 2 项）"
    ],
    "statistics": {
      "document_count": 2,
      "research_question_count": 1,
      "method_count": 1,
      "evidence_sentence_count": 10,
      "trend_hotspot_status": "computed"
    }
  },
  "meta": {
    "request_id": "req_08314d1f2a17486293f0e02fb6aaaa10",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 32924,
    "created_at": "2026-10-27T22:28:59.346397+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_ce738f3bd7c14b3e87994c1a543a73f6",
    "input_type": "files",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_c696fba1d081485db8cb2e256fe7e78e",
    "file_name": null
  }
}
```

### 19.3 已有文献集合

- **接口**：`POST /api/v1/review/structured/collections`
- **Content-Type**：application/json

#### 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `document_set` | object | 必填 | 文献集,至少 3 篇。批量文本模式传文本数组;批量文件模式传文件;指定文献集模式传集合引用对象 |
| `document_set.source` | string | 选填 | 资源来源或文献来源 |
| `document_set.collection_id` | string | 必填 | 数据库中的指定文献集编号 |
| `topic_or_keywords` | string | 必填 | 研究主题或关键词。限定综述的研究范围 |
| `document_metadata` | object[] | 条件必填 | 文献元数据。批量文本模式需逐篇提供;文件/文献集模式自动解析 |
| `document_metadata.source` | string | 选填 | 资源来源或文献来源 |
| `document_metadata.collection_id` | string | 条件必填 | 数据库中的指定文献集编号 |

#### 请求示例

将下方 JSON 保存为 `request.json`：

```bash
curl -X POST 'http://localhost:8000/api/v1/review/structured/collections' \
  -H 'Content-Type: application/json' \
  --data @request.json
```

```json
{
  "document_set": {
    "source": "database",
    "collection_id": "COLL-202608-VLM-01"
  },
  "topic_or_keywords": "视觉与语言模型的推理多样性、高效推理与时间推理",
  "document_metadata": {
    "source": "collection",
    "collection_id": "COLL-202608-VLM-01"
  }
}
```

#### 响应字段（data）

```
- data: object
  - topic: string，示例 "机器学习糖尿病肾病预测"
  - document_count: number，示例 3
  - tree: array<object>（3 项）
    - []: object
      - question_id: string，示例 "RQ-01"
      - research_question: string，示例 "基因生物标志物筛选"
      - question_summary: string，示例 "利用WGCNA共表达网络与113种机器学习算法筛选特征基因，发现VWF等关键基因…"
      - document_count: number，示例 1
      - document_ids: array<string>
      - evidence_ids: array<string>
      - methods: array<object>
        - []: object
          - method_id: string，示例 "M-01"
          - method: string，示例 "WGCNA共表达网络分析与113种机器学习算法筛选特征基因"
          - source_ids: array<string>
          - evidence_ids: array<string>
          - progress: array<undefined>
  - cluster_induction_results: object
    - cluster_count: number，示例 3
    - clusters: array<object>（3 项）
      - []: object
        - cluster_id: string，示例 "PC-001"
        - label: string，示例 "基因生物标志物筛选"
        - summary: string，示例 "利用WGCNA共表达网络与113种机器学习算法筛选特征基因，发现VWF等关键基因…"
        - question_count: number，示例 1
        - document_count: number，示例 1
        - document_ids: array<string>
        - research_questions: array<string>
        - evidence_ids: array<string>
        - cohesion: number，示例 1
    - induction_basis: string，示例 "研究问题语义相似度、研究方法共现与来源证据一致性"
    - diagnostics: object
      - selection_mode: string，示例 "per_document_merge_0.70"
      - selected_k: number，示例 3
      - candidates: array<undefined>
      - representation: string，示例 "bge-m3"
      - candidate_count: number，示例 3
  - structured_report: object
    - title: string，示例 "机器学习糖尿病肾病预测结构化综述"
    - overview: string，示例 "机器学习在糖尿病肾病预测中的应用主要围绕三个方向展开。其一是基因生物标志物筛选，…"
    - sections: array<object>（3 项）
      - []: object
        - section_id: string，示例 "SEC-01"
        - cluster_id: string，示例 "PC-001"
        - title: string，示例 "基因生物标志物筛选"
        - content: string，示例 "该类簇关注的核心研究问题是如何鉴定糖尿病肾病早期诊断的关键基因。研究采用WGCN…"
        - evidence_ids: array<string>
  - trend_hotspot_distribution: object
    - time_range: string，示例 "2024–2025"
    - hotspots: array<object>（3 项）
      - []: object
        - name: string，示例 "糖尿病肾病进展分层预测"
        - score: number，示例 0.875
        - status: string，示例 "上升趋势"
        - cluster_id: string，示例 "PC-003"
        - document_count: number，示例 1
        - supporting_years: array<number>
        - year_coverage: number，示例 0.5
    - reliability_note: string，示例 "样本量小（3篇），强度与趋势仅供参考"
  - evidence_index: array<object>（8 项）
    - []: object
      - evidence_id: string，示例 "EV-001-Q01"
      - document_id: string，示例 "DOC001"
      - title: string，示例 "糖尿病肾病关键基因鉴定"
      - source_section: string，示例 "text"
      - evidence_excerpt: string，示例 "利用WGCNA共表达网络与113种机器学习算法筛选特征基因，发现VWF等关键基因…"
      - quote: string，示例 "利用WGCNA共表达网络与113种机器学习算法筛选特征基因，发现VWF等关键基因…"
      - start: number，示例 14
      - end: number，示例 62
      - supported_nodes: array<string>
  - statistics: object
    - document_count: number，示例 3
    - research_question_count: number，示例 3
    - method_count: number，示例 3
    - evidence_sentence_count: number，示例 8
    - trend_hotspot_status: string，示例 "computed"
```

#### 响应示例（真实调用返回，数组/长文本已截断展示）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "topic": "机器学习糖尿病肾病预测",
    "document_count": 3,
    "tree": [
      {
        "question_id": "RQ-01",
        "research_question": "基因生物标志物筛选",
        "question_summary": "利用WGCNA共表达网络与113种机器学习算法筛选特征基因，发现VWF等关键基因对糖尿病肾病早期诊断具有价值。",
        "document_count": 1,
        "document_ids": [
          "DOC001"
        ],
        "evidence_ids": [
          "EV-001-Q01"
        ],
        "methods": [
          {
            "method_id": "M-01",
            "method": "WGCNA共表达网络分析与113种机器学习算法筛选特征基因",
            "source_ids": [
              "DOC001"
            ],
            "evidence_ids": [
              "EV-001-M01"
            ],
            "progress": []
          }
        ]
      },
      {
        "question_id": "RQ-02",
        "research_question": "转录组数据驱动的糖尿病肾病早期预测模型",
        "question_summary": "整合转录组数据并采用随机森林算法构建糖尿病肾病早期风险预测模型，AUC达0.89。",
        "document_count": 1,
        "document_ids": [
          "DOC002"
        ],
        "evidence_ids": [
          "EV-002-Q01"
        ],
        "methods": [
          {
            "method_id": "M-02",
            "method": "基于机器学习的糖尿病肾病早期预测模型研究：整合转录组数据与随机森林算法，构建风险预测模型，AUC达到0.89",
            "source_ids": [
              "DOC002"
            ],
            "evidence_ids": [
              "EV-RC03",
              "EV-002-M01"
            ],
            "progress": []
          }
        ]
      },
      "…（共 3 项，示例保留前 2 项）"
    ],
    "cluster_induction_results": {
      "cluster_count": 3,
      "clusters": [
        {
          "cluster_id": "PC-001",
          "label": "基因生物标志物筛选",
          "summary": "利用WGCNA共表达网络与113种机器学习算法筛选特征基因，发现VWF等关键基因对糖尿病肾病早期诊断具有价值。",
          "question_count": 1,
          "document_count": 1,
          "document_ids": [
            "DOC001"
          ],
          "research_questions": [
            "如何鉴定糖尿病肾病早期诊断的关键基因？"
          ],
          "evidence_ids": [
            "EV-001-Q01"
          ],
          "cohesion": 1
        },
        {
          "cluster_id": "PC-002",
          "label": "转录组数据驱动的糖尿病肾病早期预测模型",
          "summary": "整合转录组数据并采用随机森林算法构建糖尿病肾病早期风险预测模型，AUC达0.89。",
          "question_count": 1,
          "document_count": 1,
          "document_ids": [
            "DOC002"
          ],
          "research_questions": [
            "如何基于机器学习整合转录组数据构建糖尿病肾病早期风险预测模型？"
          ],
          "evidence_ids": [
            "EV-002-Q01"
          ],
          "cohesion": 1
        },
        "…（共 3 项，示例保留前 2 项）"
      ],
      "induction_basis": "研究问题语义相似度、研究方法共现与来源证据一致性",
      "diagnostics": {
        "selection_mode": "per_document_merge_0.70",
        "selected_k": 3,
        "candidates": [],
        "representation": "bge-m3",
        "candidate_count": 3
      }
    },
    "structured_report": {
      "title": "机器学习糖尿病肾病预测结构化综述",
      "overview": "机器学习在糖尿病肾病预测中的应用主要围绕三个方向展开。其一是基因生物标志物筛选，通过WGCNA共表达网络与113种机器学习算法相结合，鉴定出VWF等对早期诊断具有价值的关键基因；其二是基于转录组数据的早期风险预测建模，利用随机森林算法整合转录组数据构建预测模型，AUC达到0.89；其三是疾病进展的分层预测，采用XGBo…",
      "sections": [
        {
          "section_id": "SEC-01",
          "cluster_id": "PC-001",
          "title": "基因生物标志物筛选",
          "content": "该类簇关注的核心研究问题是如何鉴定糖尿病肾病早期诊断的关键基因。研究采用WGCNA共表达网络与113种机器学习算法相结合的策略进行特征基因筛选：WGCNA用于构建基因共表达网络、识别与疾病相关的基因模块，而机器学习算法组合则用于在候选基因中进一步筛选具有判别能力的特征基因。通过这一流程，研究发现了VWF等关键基因，并证…",
          "evidence_ids": [
            "EV-001-Q01"
          ]
        },
        {
          "section_id": "SEC-02",
          "cluster_id": "PC-002",
          "title": "转录组数据驱动的糖尿病肾病早期预测模型",
          "content": "该类簇的研究问题是如何基于机器学习整合转录组数据构建糖尿病肾病早期风险预测模型。与PC-001侧重基因筛选不同，本类簇直接面向预测建模任务：研究整合转录组数据，采用随机森林算法构建糖尿病肾病早期风险预测模型。随机森林作为集成学习方法，能够处理高维转录组特征并进行重要性评估，从而实现风险分层。模型评估结果显示其AUC达到…",
          "evidence_ids": [
            "EV-002-Q01"
          ]
        },
        "…（共 3 项，示例保留前 2 项）"
      ]
    },
    "trend_hotspot_distribution": {
      "time_range": "2024–2025",
      "hotspots": [
        {
          "name": "糖尿病肾病进展分层预测",
          "score": 0.875,
          "status": "上升趋势",
          "cluster_id": "PC-003",
          "document_count": 1,
          "supporting_years": [
            2025
          ],
          "year_coverage": 0.5
        },
        {
          "name": "转录组数据驱动的糖尿病肾病早期预测模型",
          "score": 0.479,
          "status": "上升趋势",
          "cluster_id": "PC-002",
          "document_count": 1,
          "supporting_years": [
            2024
          ],
          "year_coverage": 0.5
        },
        "…（共 3 项，示例保留前 2 项）"
      ],
      "reliability_note": "样本量小（3篇），强度与趋势仅供参考"
    },
    "evidence_index": [
      {
        "evidence_id": "EV-001-Q01",
        "document_id": "DOC001",
        "title": "糖尿病肾病关键基因鉴定",
        "source_section": "text",
        "evidence_excerpt": "利用WGCNA共表达网络与113种机器学习算法筛选特征基因，发现VWF等关键基因具有早期诊断价值",
        "quote": "利用WGCNA共表达网络与113种机器学习算法筛选特征基因，发现VWF等关键基因具有早期诊断价值",
        "start": 14,
        "end": 62,
        "supported_nodes": [
          "RQ-01"
        ]
      },
      {
        "evidence_id": "EV-001-M01",
        "document_id": "DOC001",
        "title": "糖尿病肾病关键基因鉴定",
        "source_section": "text",
        "evidence_excerpt": "利用WGCNA共表达网络与113种机器学习算法筛选特征基因",
        "quote": "利用WGCNA共表达网络与113种机器学习算法筛选特征基因",
        "start": 14,
        "end": 43,
        "supported_nodes": [
          "M-01",
          "RQ-01"
        ]
      },
      "…（共 8 项，示例保留前 2 项）"
    ],
    "statistics": {
      "document_count": 3,
      "research_question_count": 3,
      "method_count": 3,
      "evidence_sentence_count": 8,
      "trend_hotspot_status": "computed"
    }
  },
  "meta": {
    "request_id": "req_b3637f87943644d184713cdf23374a35",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "taxonomy_version": null,
    "ontology_version": null,
    "elapsed_ms": 30628,
    "created_at": "2026-10-28T00:22:51.804913+08:00",
    "database_dialect": "mysql",
    "task_id": "tsk_ddf1350bc17747a4ad7b84b22ef397c8",
    "input_type": "collection",
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "record_id": "rec_3fca03b751224d13805479a70ea90f9f",
    "file_name": null
  }
}
```

