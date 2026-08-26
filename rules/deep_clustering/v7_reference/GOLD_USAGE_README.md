# TopicFusion v7 Gold 使用说明

## 文件等级

- `gold_zh_model_reviewed_round3_1000.csv`：1000篇完整三轮模型复核标签，包含每个维度的置信度与可信等级。
- `gold_zh_technical_high.csv`：287篇技术路线高可信Gold，适合技术路线校准与分层评测。
- `gold_zh_application_high.csv`：482篇应用场景高可信Gold，适合应用场景校准与分层评测。
- `gold_zh_combined_high.csv`：141篇两个维度均高可信的样本。
- `*_medium.csv`：可在人工抽查后加入训练。
- `*_needs_review.csv`：不应直接作为最终准确率真值。

## 防止数据泄漏

1. 调参和规则开发只使用 `*_calibration_gold.csv` 与 `*_development_gold.csv`。
2. 在预测文件固定前，不读取 `*_locked_test_gold.csv` 的标签。
3. 锁定测试只用于最终一次指标计算。
4. 新增规则必须先在开发集证明有效，再检查多随机种子稳定性。

## Gold性质

本交付中的Gold是基于标题、摘要和关键词进行三轮模型复核得到的高质量弱监督/模型复核Gold，不是由各学科领域专家逐篇签字确认的最终人工金标准。用于正式论文或验收时，建议继续人工复核技术路线高分歧样本。
