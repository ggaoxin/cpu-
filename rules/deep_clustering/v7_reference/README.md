# TopicFusion-multifield-v7-unified

中英文标题、摘要和关键词双通道聚类：技术路线与应用场景。

## 兼容原则

- 英文 v6 的 `T01–T33` 与 `A01–A30` 原样保留。
- 中文语料新增类别从 `T34` 与 `A31` 之后追加。
- 中文、英文和混合输入均输出同一套类别 ID。
- 英文 v6 已验证代码保留在 `legacy_english_v6/`。

## 运行

```bash
python run.py \
  --input data/input.json \
  --calibration gold/gold.csv \
  --output results_new
```

支持字段：

- 中文：`ch_name`、`ch_abstract`、`keywords`
- 英文：`en_name`、`en_abstract`、`keywords`
- 混合：每条记录可使用其中任一组字段，程序自动识别语言。

当前离线运行器采用语言专用 TF-IDF/SVD 表示、共享类别 ID、校准判别器和规则证据。部署真实中英文联合向量子聚类时，建议替换为 BGE-M3 或 multilingual-e5。
