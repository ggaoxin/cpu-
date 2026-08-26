# 部署指南

本项目代码 + 规则库 + 前端 + 数据库脚本 + 文档全在仓库内。**大资源（bge 模型权重、CLC 向量索引、测试数据集）不含在 git 仓库**，clone 后按第 4 节获取。**MinerU**（PDF 解析）为外部工具，按第 3 节安装。

> 若通过完整压缩包（含 models/rag_store/data）交付，则开箱即用，跳过第 4 节。

## 1. 环境要求

- Python 3.12
- 依赖：`pip install -r requirements.txt`（FastAPI / sentence-transformers / numpy / pandas / scipy / joblib / jieba / nltk / python-dotenv 等）
- GPU 可选（有 GPU 则 bge 编码走 CUDA，无则走 CPU，较慢但可用）

## 2. 配置

`config/.env`：
```
GLM_API_KEY=<你的智谱 API Key>
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MINERU_BIN=mineru          # MinerU 可执行文件；默认假设 conda activate mineru 后在 PATH
```

后端模型已固定为 `glm-5.2`，不读取 `GLM_MODEL` 覆盖值。`GLM_API_KEY` 是必填项：
缺失时服务不启动。前五个功能项共 11 个接口在调用 GLM-5.2 失败时任务直接返回失败，
不使用本地规则或 RAG 结果生成替代的成功响应。

所有资源路径默认相对项目根（`data/datasets`、`rag_store/clc_rag`、`models/`），无需配置。
如需指向外部位置，可用环境变量覆盖（见 `config/settings.py` 的 `_path()`）：`DATA_DIR` / `CLC_RAG_DIR` / `MODELS_DIR` / `BGE_SMALL_PATH` / `BGE_LARGE_PATH` / `BGE_M3_PATH` / `MINERU_BIN`。

## 3. 安装 MinerU（唯一外部依赖，仅 PDF 输入需要）

若只调用文本类 API（直接传 text），**不需要 MinerU**。只有当输入是 PDF 文件路径时才用 MinerU 把 PDF 转成 markdown 全文。

```bash
# 1. 创建 conda 环境
conda create -n mineru python=3.10 -y
conda activate mineru

# 2. 安装 MinerU（magic-pdf）
pip install -U "magic-pdf[full]"

# 3. 下载 MinerU 模型权重（layout/OCR/formula 等，按 magic-pdf 官方文档）
#    通常首次运行 magic-pdf 时自动下载到 ~/.cache/huggingface 或指定目录
#    官方文档：https://github.com/opendatalab/MinerU

# 4. 验证
mineru --help

# 5. 让项目能找到 mineru
#    方式 A：运行项目前先 conda activate mineru（mineru 进入 PATH，.env 的 MINERU_BIN=mineru 即可）
#    方式 B：在 .env 写绝对路径：MINERU_BIN=/path/to/conda/envs/mineru/bin/mineru
```

## 4. 获取模型与重建向量索引（GitHub 交付不含大文件）

GitHub 仓库不含 `models/`（bge 权重 5.7G）和 `rag_store/clc_rag/clc_index_large|clc_index_m3/`（CLC 向量索引 480M）。clone 后按以下步骤获取。

### 4.1 下载 bge 模型权重

```bash
cd semantic_toolkit_final
pip install modelscope
python -m scripts.setup_models                 # 下载全部三个 bge 模型到 models/
# 或只下某个：python -m scripts.setup_models --only bge-m3
```

下载到：
- `models/bge-small-zh-v1.5`（92M）
- `models/bge-large-zh-v1.5`（1.3G）
- `models/bge-m3`（4.3G）

> ModelScope 不通时，可从 HuggingFace（`BAAI/bge-small-zh-v1.5` 等）下载，或手动放到对应目录。目录名必须与上述一致（`config/settings.py` 的 `BGE_*_PATH` 默认指向这些路径）。

### 4.2 重建 CLC 向量索引

模型下载后，重建分类检索用的向量索引（编码 40912 条 CLC 类目，需 GPU 约 10-20 分钟，CPU 较慢）：

```bash
# bge-large 编码完整 CLC 知识库 → rag_store/clc_rag/clc_index_large/
python -m scripts.encode_full_index

# bge-m3 编码跨语言索引 → rag_store/clc_rag/clc_index_m3/
python -m scripts.encode_m3_index
```

> CLC 元数据 `rag_store/clc_rag/clc_meta_full.json`（40912 条，42M）**已含在仓库**，无需重建。仅向量索引需重建。
> 已有索引文件时跳过此步（如通过 Release 附件或对象存储获取了 `clc_index_large/`、`clc_index_m3/`，直接放入 `rag_store/clc_rag/` 即可）。

### 4.3 路径覆盖（可选）

模型/索引不在默认位置时，用环境变量覆盖（见 `config/settings.py`）：
```
MODELS_DIR=/path/to/models
BGE_SMALL_PATH=/path/to/bge-small
BGE_LARGE_PATH=/path/to/bge-large
BGE_M3_PATH=/path/to/bge-m3
CLC_RAG_DIR=/path/to/clc_rag
```

### 4.4 测试数据集

`data/datasets/`（论文/摘要/分类 gold 等评测数据，约 222M）不含在 git 仓库。需要跑评测（`training/eval_*.py`）或复现时，从以下途径获取并放入 `data/datasets/`：

- GitHub Release 附件（随版本发布打包）
- 或由交付方单独提供

> NER gold 标注（`data/ner/*.json`）已含在仓库，无需单独获取。
> `data/zh_classify.pdf`（中图法详表，用于重建 CLC 元数据）已含在仓库。

## 5. 启动服务

```bash
cd semantic_toolkit_final
uvicorn presentation.main:app --host 0.0.0.0 --port 8000
```
交互文档：http://localhost:8000/docs

## 6. 自检

```bash
python -m pytest tests/ -q          # 脚手架测试
python -m training.eval_ner --type ner_research   # NER 评测（验证数据/模型路径）
```

## 项目结构

```
semantic_toolkit_final/
├── presentation/ application/ domain/ infrastructure/   # 代码（DDD 四层）
├── config/   settings.py + .env + functional_points.py
├── rules/    19 功能点规则库 YAML + ner/mappings/（实体映射表）
├── training/ 评测与训练脚本（含 eval_ner.py）
├── scripts/  gold 标注、索引构建脚本
├── data/     datasets/（数据集）+ ner/（gold）+ zh_classify.pdf
├── rag_store/clc_rag/  CLC 知识库元数据 + 向量索引（large/m3）
├── models/   bge-small-zh / bge-large-zh / bge-m3 权重
└── docs/     HANDOFF.md（项目交接）+ SETUP.md（本文）
```
