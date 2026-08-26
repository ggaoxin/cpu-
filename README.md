# 语义计算工具库（Semantic Toolkit）— 纯 CPU 版

面向科技文献全生命周期的语义计算底座，采用 **DDD（领域驱动设计）分层架构**。
共 **10 个功能项、19 个功能点**，统一由 **GLM 大模型 + 独立规则库** 驱动实现。

**本仓库特点：完整可复现的纯 CPU 部署**——不需要 GPU，只需要一台能联网调 GLM API
的机器（1.2GHz×15核级别的服务器即可），所有功能点均可正常运行。

> 运行约束：正式后端模型调用由 `GLM_MODEL` 配置，默认 `glm-5.2`。模型型功能不会用演示数据
> 伪装真实响应；缺少密钥或调用失败时返回明确错误。开发联调可设置
> `GLM_REQUIRED_AT_STARTUP=false` 让服务先启动，正式服务器建议设为 `true`。

---

## 一、功能总览

| 功能项 | 功能点 | 说明 |
|---|---|---|
| 语步识别 | 中文摘要语步 / 英文摘要语步 / 基金申请书语步 | 摘要五类语步（背景/目的/方法/结果/结论）切分与置信度 |
| 自动分类 | 中文 CLC 分类 / 英文 CLC 分类 / 专业领域分类 | 中图法分类（bge 向量检索 4 万类目 + LLM 精排）/ 32 领域三级分类 |
| 关键词识别 | 中文 / 英文 | 术语归一、词典加权 |
| 研究问题识别 | 研究问题检测 | 句式与章节溯源 |
| 引用句识别 | 引用情感 / 引用意图 | 强结构 PDF 解析（MinerU） |
| 概念定义识别 | 概念定义检测 | 定义句抽取与标准化映射 |
| 命名实体识别 | 通用 / 科研 / 领域（+ 关系抽取） | 实体链接、本体映射、上下游 NER→关系链 |
| 深度聚类 | 文献深度聚类 | bge-m3 句子级语义特征 + 层次聚类 |
| 聚类标签生成 | 类簇标签 | 区分度优化、多候选标签 |
| 结构化自动综述 | 多文献综述 | 研究问题树 + 证据溯源 + 趋势热点 |

技术栈：**Vue 3 + Vite**（前端）/ **FastAPI**（后端）/ **MySQL 8**（持久化，也支持 SQLite）/
**GLM-5.2**（智谱 API，OpenAI 兼容协议）/ **bge 向量模型**（本地 CPU 推理）/
**MinerU**（可选，扫描件 PDF 解析）。

---

## 二、资源下载（克隆后必读）

本仓库 **不含** 两类大资源，克隆后按下表获取：

| 资源 | 大小 | 获取方式 | 放置位置 |
|---|---|---|---|
| bge 模型权重（3 套） | ~5.7G | `python -m scripts.setup_models`（ModelScope 自动下载）；或从 [HuggingFace](https://huggingface.co/BAAI) 手动下载 `BAAI/bge-small-zh-v1.5`、`BAAI/bge-large-zh-v1.5`、`BAAI/bge-m3` | `models/<对应目录名>/` |
| CLC 向量索引库 | ~585M | 本仓库 [Release 附件](https://github.com/ggaoxin/cpu-/releases) `clc-vectors.tar.gz` | 解压：`tar xzf clc-vectors.tar.gz -C rag_store/clc_rag/` |
| MinerU pipeline 模型 | ~4.6G | 首次调用时自动下载（可选，仅扫描件 PDF 需要） | `~/.cache/modelscope/` |

> CLC 向量索引库（中图分类法外部知识库）编码了 40912 条 CLC 类目的 bge-large/bge-m3
> 向量。若不下载，可用 `python -m scripts.encode_full_index` + `python -m scripts.encode_m3_index`
> 自行重建（需先装好 bge 模型，纯 CPU 约需 1-2 小时）。
>
> 测试数据集已随仓库附带（`data/datasets/`，12M）。

---

## 三、快速开始（完整复现）

以下步骤在一台全新的 Ubuntu 22.04（无 GPU）上验证通过。

### 1. 克隆并安装依赖

```bash
git clone https://github.com/ggaoxin/cpu-.git semantic_toolkit
cd semantic_toolkit

# Python 依赖（Python ≥ 3.10）
# 纯 CPU 机器务必用 CPU 版 torch（本仓库要求 torch>=2.6，transformers 5.x 加载权重的硬性要求）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt -r requirements-ml.txt

# 前端依赖
cd frontend && npm install --registry=https://registry.npmmirror.com && cd ..
```

### 2. 配置

```bash
cp config/.env.example config/.env
# 编辑 config/.env：
#   GLM_API_KEY=<你的智谱密钥，必填>
#   DATABASE_URL 默认指向本机 MySQL（见第 4 步）
#   BGE_DEVICE=cpu 强制纯 CPU
```

GLM 密钥在 [open.bigmodel.cn](https://open.bigmodel.cn) 注册获取。

### 3. 下载大资源

```bash
pip install modelscope
python -m scripts.setup_models        # bge 三套权重 → models/

# CLC 向量索引（Release 附件）
mkdir -p rag_store/clc_rag
wget -O clc-vectors.tar.gz https://github.com/ggaoxin/cpu-/releases/download/v1.0.0-cpu/clc-vectors.tar.gz
tar xzf clc-vectors.tar.gz -C rag_store/clc_rag/
```

### 4. MySQL 8（推荐；也可用 SQLite 零配置）

```bash
sudo apt-get install -y mysql-server          # Ubuntu 22.04 = MySQL 8.0
sudo mysqld --user=mysql --daemonize          # 无 systemd 的容器环境
mysql -e "
CREATE DATABASE semantic_toolkit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'semantic_user'@'127.0.0.1' IDENTIFIED BY 'change_me';
CREATE USER 'semantic_user'@'localhost' IDENTIFIED BY 'change_me';
GRANT ALL PRIVILEGES ON semantic_toolkit.* TO 'semantic_user'@'127.0.0.1';
GRANT ALL PRIVILEGES ON semantic_toolkit.* TO 'semantic_user'@'localhost';
FLUSH PRIVILEGES;"
# 首次启动后端时自动建表（52 张）+ 写入内置语义资源
```

> 不想装 MySQL：把 `.env` 里 `DATABASE_URL` 注释掉即回落到 SQLite（`runtime/semantic_toolkit.db`），
> `DATABASE_REQUIRED` 设为 `false`。

### 5. 启动

```bash
# 后端（8000）
python -m uvicorn presentation.main:app --host 0.0.0.0 --port 8000

# 前端（6006，另开终端；vite 已配置 /api 代理到 8000）
cd frontend && npm run dev
```

- 前端：http://127.0.0.1:6006 （无登录，打开即用）
- FastAPI 接口文档：http://127.0.0.1:8000/docs
- 健康检查：`curl http://127.0.0.1:8000/health`

**AutoDL 等容器环境**：开启平台的「自定义服务」（默认映射 6006），vite 配置已放行公网域名
（`allowedHosts`），直接用平台给的 URL 访问。

### 6.（可选）MinerU——扫描件 PDF 解析

不装也能跑：文本层 PDF 走 PyMuPDF（毫秒级），MinerU 不可用时自动降级 pdfplumber。
只有**扫描版 PDF**（图片页）和引用情感/意图两个强结构工具需要它：

```bash
conda create -n mineru python=3.10 -y
conda run -n mineru pip install -U "mineru[core,api]" -i https://pypi.tuna.tsinghua.edu.cn/simple
# 启动常驻 API 服务（pipeline 后端，纯 CPU 可用，首次调用自动下载模型 ~4.6G）
conda run -n mineru mineru-api --host 127.0.0.1 --port 8899
# 然后确认 .env: MINERU_API_URL=http://127.0.0.1:8899  MINERU_BACKEND=pipeline
```

> CPU 性能参考：文本层 2 页 PDF ≈ 2 秒；扫描版 ≈ 0.6 秒/页。
> 不需要 vllm——`vlm-engine` 后端才需要（GPU 场景），纯 CPU 用 `pipeline`。

### 7. 验证

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/move/abstract/zh/text \
  -H "Content-Type: application/json" \
  -d '{"text": "针对X问题,本文提出Y方法。实验表明Z。研究表明该方法有效。"}'
# 返回 code=0 且 moves 含五个语步即成功
```

**Docker 方式**（MySQL + 后端 + 前端一键）：设置 `GLM_API_KEY`、`MYSQL_PASSWORD` 后
`docker compose up -d --build`，访问 http://127.0.0.1:8080 。

---

## 四、目录结构（DDD 分层）

```
semantic_toolkit/
├── frontend/                  # Vue 3 + Vite 单页应用（工具面板配置驱动）
├── presentation/              # 表现层：FastAPI 入口 + 19 功能点路由 + Vue 集成接口
├── application/               # 应用层：semantic_service（19 条算法链路）、
│                              #   tool_integration_service（任务编排/批量/异步）
├── domain/                    # 领域层：实体/值对象/仓储接口（纯逻辑）
├── infrastructure/            # 基础设施层：GLM 客户端、规则引擎、数据库、
│                              #   RAG 检索、聚类、文档解析（PyMuPDF/MinerU）
├── rules/                     # 19 个功能点独立规则库（YAML：原则+模式+词典）
├── training/                  # 引擎实现（语步分类器/规则引擎/冲突审核等）
├── config/                    # settings + 功能点/合同定义 + .env
├── models/                    # bge 权重（脚本下载，不进 git）
├── rag_store/clc_rag/         # CLC 向量索引（Release 附件，不进 git）
├── data/datasets/             # 测试数据集（随仓库）
├── scripts/                   # 模型下载/索引重建等工具
├── docs/                      # 使用/部署/字段矩阵文档
└── tests/                     # 测试
```

**模型×规则融合方式**：prompt 只注入规则库中的抽象判定原则（防过拟合），LLM 输出后由
后置规则引擎校验、调分、检测冲突，冲突句再触发一次 LLM 二次审核裁决；置信度 = LLM 自评
基础分 + 规则命中微调。

---

## 五、纯 CPU 运行说明

- `BGE_DEVICE=cpu`：bge 编码器全部走 CPU（`clc_retriever`/`m3_encoder`/`clc_index_builder`
  三处统一读取该变量）
- 依赖安装 CPU 版 torch（`--index-url https://download.pytorch.org/whl/cpu`），不装 CUDA
- PDF 解析三级降级链：`paper_abstract_extractor 规则包（可选）→ PyMuPDF 文本层 + 正则
  （毫秒级）→ MinerU 结构化解析（扫描件兜底）→ pdfplumber 保底`
- 性能参考（15 核 CPU）：文本类功能 2-10 秒（大头是 GLM 调用）；CLC 分类含向量编码约 12 秒；
  扫描版 PDF OCR 约 0.6 秒/页

---

## 六、相对原始交付包的修复清单

本仓库在原始交付包基础上修复了以下问题（均已验证）：

1. **MySQL schema 不同步**：`move_results` 缺 5 列、`move_segments` 缺 `label` 列，
   导致语步结果落库必然失败（`schema_mysql.sql`/`schema_sqlite.sql` 已补）
2. **NER 引擎 `_idx` 未定义**：实体位置有效时触发 `UnboundLocalError`（`semantic_service.py`）
3. **MinerU 3.x 异步协议适配**：`/file_parse` 返回任务信封，客户端自动轮询取结果
   （兼容新旧两种协议）
4. **摘要正则括号前缀兼容**：CNKI 网络首发格式的 `[摘要]`/`[关键词]` 此前匹配不到，
   导致中文论文误用英文摘要
5. **PyMuPDF 摘要快速路径接线**：`_pymupdf_abstract` 此前无调用方，私有包
   `paper_abstract_extractor` 缺失时全部掉进 MinerU（22 秒 → 135 毫秒）
6. **私有包优雅降级**：`paper_abstract_extractor` 未安装时不再 500，按设计回退
7. **语步字符范围补全**：非连续语步（英文常见）填充句序号，连续语步给出精确偏移
8. **结构化综述趋势热点实现**：原"二期未实现"的 `trend_hotspot_distribution` 已按
   类簇支持文献数 + 发表年份确定性计算
9. **弹窗文献名优先级**：可视化弹窗改为文件名优先（此前显示 PDF 抽取的期刊名噪声）
10. **前端 vite 配置**：`0.0.0.0:6006` + `allowedHosts`，适配 AutoDL 自定义服务

---

## 七、更多文档

- [系统使用与数据库需求说明书](docs/SYSTEM_USER_OPERATION_AND_REQUIREMENTS_GUIDE_ZH.md)
- [19 功能点输入输出与数据库字段矩阵](docs/V774_FULLSTACK_FIELD_MATRIX_ZH.md)
- [服务器部署指南](docs/V774_DEPLOYMENT_GUIDE_ZH.md)
- [完整部署（含模型/向量/数据库/MinerU）](docs/SETUP.md)
- [资源附件说明](RELEASE_NOTES.md)
