# TopicFusion Multi-field v6

v6 将标题、摘要和关键词拆分建模，并在技术路线与应用场景两个维度分别融合：

- 语义原型相似度；
- 高可信 Gold 校准的线性判别器；
- 边界规则库与负向证据；
- 低边界差值人工复核标志。

## 运行

```bash
pip install -r requirements.txt
python run.py \
  --input data.json \
  --taxonomy taxonomy_v6.json \
  --calibration calibration_gold.csv \
  --output results
```

校准文件至少需要：

```text
document_id,technical_cluster_id,application_cluster_id
```

不提供 `--calibration` 时，代码仍可运行，但只使用语义原型与规则，指标会低于半监督模式。

详细边界见 `BOUNDARY_RULES.md`，锁定测试指标见 `evaluation/locked_test_metrics_v6.csv`。
