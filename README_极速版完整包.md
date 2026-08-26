# 语义工具箱 Semantic Toolkit · 极速版完整包

> 打包时间：2026-08-25 ｜ 版本：极速版（PDF_EXTRACT_MODE=light）｜ 含模型权重 + 外部知识库 + 评估数据集

本压缩包为**极速版完整包**：包含全部前后端源码、数据库 schema、模型权重、外部知识库向量、规则资源与评估数据集。仅前端依赖（node_modules）与运行时缓存未打包，按下方步骤安装即可运行。

---

## 一、极速版核心特性

极速版相对原版的改动是 **PDF 取文链路从 mineru 全量解析切换为 PyMuPDF 极速取文**，单页解析速度提升约 9 倍，并内置双栏/扫描件自动回退 mineru 保质量。

| 机制 | 说明 |
|------|------|
| `PDF_EXTRACT_MODE=light` | 全局极速开关，见 `config/.env`。light=PyMuPDF 极速，full=mineru 原样 |
| `should_use_light(tool_id)` | 绝大多数工具走 PyMuPDF 极速；仅 `citation-intent`/`citation-sentiment` 为保版面结构走 mineru |
| `extract_bytes(content, name, light=)` | 极速取文入口（`infrastructure/document_parser/upload_reader.py:228`），light 分流到 `_pymupdf_text` |
| `_page_is_dual_column` | 自动检测双栏（双栏占比 >25%）或扫描件 → 自动回退 mineru 保结构 |
| `PageBudgetPool` | 回退 mineru 时的并发限流池，防 >60 页 PDF 多文件死锁 |
| `paper_abstract_extractor` | 摘要语步抽取走正则+LLM 兜底，动态扩页 3→5→7，学位论文不回退 |
| `_llm_judge_citations` | citation-intent 走「正则召回 → 批量 LLM judge」，去 60 行脆弱正则，63s→14s |
| concept-definition LLM 主导 | 概念定义走 `_glm_chat_batch` 并发 LLM 抽取（替代正则 markers 召回），全文清洗去期刊噪声 |

**回退链路**：light 取文 0（双栏漏段/PyMuPDF 漏抽）→ 用 `_source_pdf_path` 调 `mineru vlm-engine` 重抽全文 → 重跑。`MINERU_BACKEND=vlm-engine` 是回退里最快的 backend。

---

## 二、压缩包内容

### ✅ 已打包（项目资产）
- **后端源码**：`application/`（服务层，含 `semantic_service.py`/`tool_integration_service.py`/`deep_clustering_service.py`/`structured_review_service.py`/`result_normalizer.py` 等）、`infrastructure/`（数据库/聚类/文档解析/分类/CLC RAG 等）、`presentation/`（FastAPI 路由）、`domain/`、`config/`、`rules/`、`eval/`、`tests/`、`scripts/`、`training/`、`semantic_toolkit_sdk/`
- **前端源码**：`frontend/src/`（Vue3+Vite）、`frontend/dist/`（已构建产物）、配置文件（vite/tsconfig/package.json 等）
- **数据库**：`infrastructure/database/schema_mysql.sql`（54 张表完整建表语句）
- **配置**：`config/.env`（已填好数据库连接 + GLM + mineru，⚠️ 含 GLM_API_KEY 明文，注意保管）、`.env.docker.example`、`Dockerfile`、`docker-compose.yml`
- **模型权重**：`models/bge-m3`（4.3G）、`models/bge-large-zh-v1.5`（1.3G）、`models/bge-small-zh-v1.5`（92M）
- **外部知识库**：`rag_store/clc_rag`（585M，CLC 中图法分类向量库）
- **规则资源**：`rules/`（57M，含 `deep_clustering` 参考数据 + 各工具 yaml 规则）
- **评估数据集**：`data/datasets/`（123M，中英论文/关键词/分类标注集）、`data/ner/`、`data/zh_classify.pdf`

### ❌ 未打包（需自行准备）
| 项 | 原因 | 处理 |
|----|------|------|
| `frontend/node_modules/` | npm 依赖，跨平台二进制不通用 | `cd frontend && npm install` |
| `output/` | 运行时分析产出（2.3G） | 运行自动生成 |
| `.git/` | 版本历史 | 不影响运行 |
| `data/papers/` | 用户测试上传的 108 个样本 PDF | 你自己的测试 PDF |
| `runtime/cache/` `runtime/semantic_toolkit.db` | 运行时缓存/旧 sqlite | 运行自动生成 |
| `__pycache__/` | Python 字节码缓存 | 运行自动生成 |

---

## 三、环境依赖

| 组件 | 版本/要求 |
|------|-----------|
| Python | 3.10+（项目用 3.11） |
| PyTorch | 2.6（bge 模型推理） |
| MySQL | 8.0+（charset=utf8mb4） |
| Node.js | 18+（前端构建） |
| mineru | 可选，仅 citation 工具/双栏回退需要（`/root/autodl-tmp/conda/envs/mineru/bin/mineru`，或改 `.env` 的 `MINERU_BIN`） |
| Python 包 | `pip install -r requirements.txt -r requirements-ml.txt` |
| nltk 数据 | `nltk.download('punkt')` 等 |
| jieba | 中文分词（pip 装） |

---

## 四、快速启动

### 1. 准备数据库
```sql
CREATE DATABASE semantic_toolkit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'semantic_user'@'%' IDENTIFIED BY 'change_me';
GRANT ALL ON semantic_toolkit.* TO 'semantic_user'@'%';
FLUSH PRIVILEGES;
```
建表脚本启动时自动执行（`schema_mysql.sql`），并自动重建 default 工作区 + 13 个内置语义资源（RES-BUNDLED-*）。

### 2. 配置 `config/.env`
已预填，按需改：`DATABASE_URL`（数据库地址密码）、`GLM_API_KEY`、`GLM_MODEL`、`MINERU_BIN`/`MINERU_API_URL`（mineru 路径，若无 mineru 则 citation 工具/双栏回退不可用，其余 17 个工具正常）。极速模式保持 `PDF_EXTRACT_MODE=light`。

### 3. 启动后端
```bash
cd semantic_toolkit_final
pip install -r requirements.txt -r requirements-ml.txt   # 含 torch2.6/bge/jieba/nltk/fastapi 等
python -m uvicorn presentation.main:app --host 0.0.0.0 --port 8000 --reload
```
启动日志应见 `initialize() 完成` + 54 表 + 13 资源重建。

### 4. 启动前端
```bash
cd frontend
npm install          # 装 Vite7/Vue3 依赖
npm run dev          # 开发模式 http://localhost:5173
# 或 npm run build   # 生产构建到 dist/
```

### 5. 访问
浏览器开 `http://localhost:5173`（开发）或后端 `http://localhost:8000`。前端 `vite.config.ts` 已配代理转发 `/api` 到 8000。

---

## 五、19 个语义工具一览

| 工具 | code | 取文模式 |
|------|------|---------|
| 中图分类映射 | domain-classify | 极速 |
| 英文科研分类 | en-classify | 极速 |
| 中文关键词 | zh-keyword | 极速 |
| 英文关键词 | en-keyword | 极速 |
| 通用NER | general-ner | 极速 |
| 科研实体NER | ner-research | 极速 |
| 领域实体NER | ner-domain | 极速 |
| 关系抽取 | relation-extract | 极速(复用上游NER实体) |
| 研究问题识别 | rq-detect | 极速 |
| 概念定义识别 | concept-definition | 极速(LLM主导) |
| 基金语步 | fund-move | 极速 |
| 摘要语步 | abstract-move | 极速 |
| 深度聚类 | deep-cluster | 极速 |
| 聚类标签生成 | cluster-label | 极速 |
| 概念识别(definition-detect) | definition-detect | 极速 |
| **引用意图** | citation-intent | **mineru(保版面)** |
| **引用情感** | citation-sentiment | **mineru(保版面)** |
| 结构化综述 | structured-review | 极速 |
| 文献集合 | (collection) | 深度聚类沉淀自动建集 |

---

## 六、极速版验证要点

启动后可验证极速版是否生效：
1. `config/.env` 里 `PDF_EXTRACT_MODE=light`
2. 跑 zh-keyword/general-ner 等工具：日志应见 `extract_bytes light=True`，单篇秒级返回（非数十秒）
3. 双栏论文/扫描件：应见自动回退 mineru 日志（`_page_is_dual_column` 触发）
4. citation-intent：走 mineru full（`STRUCTURE_DEPENDENT_TOOLS` 包含它），这是保版面结构的正确行为
5. 概念定义：LLM 主导抽，concept 字段不空（非正则 markers 时代）

---

## 七、注意事项

- **GLM_API_KEY 明文**：`.env` 含明文 API Key，压缩包勿公开传播。
- **模型路径**：`models/bge-*` 三套权重已打包，代码按 `config/settings.py` 的 `MODEL_PATH` 读取，默认相对项目根，勿移动。
- **外部知识库**：`rag_store/clc_rag` 已打包，CLC 分类映射依赖它，勿删。
- **mineru 回退**：极速版下仅 citation 两个工具 + 双栏/扫描回退需要 mineru。无 mineru 环境时，17 个极速工具正常，citation 类不可用。
- **数据库已清空**：本包对应数据库已清空（54 表全空），启动后自动重建工作区与内置资源，需重新跑分析生成数据。
