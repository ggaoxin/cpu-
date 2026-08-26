# 聚类标签自动生成 V11 正式接入说明

## 1. 正式方案

正式工程默认使用 `bounded_soft_fallback`，对应引擎版本
`cluster-label-semantic-soft-fallback-v11`。该方案以 BGE-M3 语义评分为主，
仅在语义第一候选证据不足时，对当前类簇中已经生成的近似同分候选执行一次
受限软兜底选择。

- 不使用主题库或预定义类别映射。
- 不读取 Gold 标签参与在线推理。
- 不新增输入中不存在的术语。
- 软兜底候选必须由至少两条输入短语支持。
- 软兜底贡献上限固定为 `0.08`，每次触发、候选数量、选择前后标签和贡献值均返回审计字段。
- 默认 `generation_mode=hybrid`：GLM-5.2 生成带证据候选，BGE-M3 负责语义校验、排序和差异度计算，V11 执行受限软门控。GLM 单个类簇调用失败时自动回退到本地候选并记录失败；显式传入 `local` 才完全关闭大模型。

## 2. 可用引擎模式

| `label_engine_mode` | 用途 | 是否建议正式默认 |
|---|---|---|
| `bounded_soft_fallback` | V11，BGE 主路径 + 受限软兜底 | 是 |
| `semantic_only` | V10，纯 BGE 语义基线 | 作为回退与对照 |
| `legacy_evidence_v2` | 原工程旧引擎 | 仅用于历史任务复现 |

别名 `v11`、`soft_fallback` 会归一为 `bounded_soft_fallback`；别名 `v10`
会归一为 `semantic_only`。未知模式直接返回参数错误，不会静默切换到未验证算法。

## 3. 直接算法输入

```json
{
  "params": {
    "cluster_phrase_sets": [
      {
        "cluster_id": "C01",
        "phrases": [
          {"text": "图神经网络", "weight": 1.0, "frequency": 8},
          {"text": "故障诊断", "weight": 0.9, "frequency": 6}
        ]
      }
    ],
    "label_length_limit": 12,
    "language_type": "auto",
    "distinctiveness_threshold": 0.75,
    "candidate_count": 5,
    "generation_mode": "hybrid",
    "label_engine_mode": "bounded_soft_fallback"
  }
}
```

`cluster_phrase_sets` 是深度聚类的类簇代表短语输出。V11 不负责重新分配文献，
也不改变类簇成员关系。

## 4. 输出与 Vue 对接

原有主结构保持不变：

- `labels`：每个类簇的推荐标签、候选标签、输入证据、置信度、覆盖度和区分度。
- `generation_report`：引擎版本、执行模式、阶段、平均指标和软兜底审计汇总。
- `label_differentiation_optimization`：阈值通过情况和逐类簇选择前后记录。

为了让 Vue 可视化弹窗直接消费真实结果，应用服务还补充以下派生字段：

- 顶层 `cluster_count`、`generated_label_count`、`parameters`、`statistics`。
- 标签中的 `recommended_label`、`alternatives`、`representativeness`、
  `difference_explanation`。
- `evidence.keywords` 直接来自引擎 `evidence_terms`。

命名实体、中心句和文献编号若上游没有提供，保持空值，不使用原型演示数据补齐。

## 5. 已验证结果

以下 V2 指标是“不调用 GLM”的本地安全基线，用来验证 BGE-M3 + V11 软门控在
大模型不可用时仍能工作；不能把它当成正式 GLM 混合链路的最终性能。正式默认
链路已经改为 GLM-5.2 候选生成 + BGE-M3 复核，混合链路需要在可访问 GLM 的
服务器上使用同一冻结 Gold 重新评测并单独出具指标。

V2 独立盲测包含 480 篇新文档、10 个有效类簇，和开发集文档无重叠。
V11 相对 V10 的结果为：概念 F1 从 `57.14%` 提升到 `66.67%`，召回率从
`40%` 提升到 `50%`，语义相似度从 `54.43%` 提升到 `56.98%`，差异度通过率
从 `70%` 提升到 `80%`；精确率、证据扎根率和长度合规率均保持 `100%`。

V12 自适应版本在后续盲测中没有形成准确率优势，因此没有接入正式默认路径。

## 6. 回归验证

```powershell
python -m unittest tests.test_cluster_labeling_engine -v
```

测试覆盖旧引擎兼容、V11 默认选择、V10 显式回退、未知模式拒绝、Vue 字段派生、
软兜底双证据门控、8% 贡献上限和无硬映射审计。
