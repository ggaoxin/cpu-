# Release v1.0.0-cpu 资源附件说明

克隆代码后，按下表获取大资源。完整部署步骤见 `README.md`（快速开始）与 `docs/SETUP.md`。

## 1. clc-vectors.tar.gz（CLC 向量索引库，约 494M）

中图分类法外部知识库：40912 条 CLC 类目的 bge-large / bge-m3 向量索引，
供中英文 CLC 自动分类做向量检索。

下载后解压到 `rag_store/clc_rag/`：

```bash
mkdir -p rag_store/clc_rag
tar xzf clc-vectors.tar.gz -C rag_store/clc_rag/
# 得到 rag_store/clc_rag/clc_index_large/、clc_index_m3/、clc.faiss、clc_meta*.json 等
```

> 不下载可自行重建：`python -m scripts.encode_full_index` + `python -m scripts.encode_m3_index`
> （需先装好 bge 模型，纯 CPU 约 1-2 小时）。

## 2. bge 模型权重（不在此发布，约 5.7G）

bge-small / bge-large / bge-m3 三套权重。用脚本从 ModelScope 自动下载：

```bash
pip install modelscope
python -m scripts.setup_models
# 下载到 models/bge-small-zh-v1.5、models/bge-large-zh-v1.5、models/bge-m3
```

> ModelScope 不通时，可从 HuggingFace（`BAAI/bge-small-zh-v1.5` 等）下载，
> 手动放到 `models/` 下对应目录。

## 3. 测试数据集（已随仓库附带）

`data/datasets/`（12M）已包含在 git 仓库中，无需单独下载。
NER gold 标注（`data/ner/*.json`）同样随仓库附带。

## 4. MinerU pipeline 模型（可选，约 4.6G）

仅扫描版 PDF 解析需要。安装 mineru 后首次调用自动下载到 `~/.cache/modelscope/`。
纯 CPU 使用 `pipeline` 后端（不需要 vllm；`vlm-engine` 为 GPU 场景选项）。

## 接收方完整部署流程

```bash
git clone https://github.com/ggaoxin/cpu-.git semantic_toolkit
cd semantic_toolkit
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt -r requirements-ml.txt
cd frontend && npm install && cd ..
cp config/.env.example config/.env   # 填 GLM_API_KEY
python -m scripts.setup_models       # bge 权重
# + 下载 clc-vectors.tar.gz 解压到 rag_store/clc_rag/
# + MySQL 建库（见 README 第 4 步）
python -m uvicorn presentation.main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev           # http://127.0.0.1:6006
```
