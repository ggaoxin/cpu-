# 无 GPU 版完整部署指南

> 适用:无显卡服务器 ｜ CPU only ｜ 不依赖 vllm/cuda ｜ 文档日期 2026-08-25
>
> 本包是极速版的 **CPU 适配版**:所有 GPU 依赖改为 CPU 路径——bge 向量走 CPU、mineru 走 onnxruntime pipeline(不用 vllm)、PyMuPDF 取文本纯 CPU、GLM 走云 API(不占本地 GPU)。**甲方机器无需 GPU、无需 CUDA、无需 vllm**。
>
> 代码已 grep 确认**无任何 GPU 硬依赖**:`cuda` 仅用于 `torch.cuda.is_available()` 条件检测 + `BGE_DEVICE="cuda" if _gpu_available() else "cpu"` 自适应,无 `.to("cuda")` 硬编码。19 个工具全部能在 CPU 跑通。

---

## 一、能跑什么(功能清单)

| 工具类型 | 取文/依赖 | CPU 版表现 |
|---------|----------|-----------|
| 17 个纯文本工具(abstract-move / fund-move / zh+en-classify / zh+en-keyword / domain-classify / rq-detect / concept-definition / general-ner / research-ner / domain-ner / relation-extract / cluster-label / structured-review 等) | PyMuPDF(CPU)+ GLM 云 | **快**(秒级,与 GPU 版几乎同) |
| deep-cluster / 综述 / 文献集合 | bge-m3 CPU + GLM | **慢但能跑**(单篇 5–30s,m3 sparse 固有) |
| citation-intent / citation-sentiment | mineru pipeline(onnxruntime CPU) | **慢但能跑**(单文件 30–90s);不部署 mineru 则降级 pdfplumber(能跑,版面降) |
| 双栏/扫描件回退 | mineru pipeline CPU | 慢,但质量优于 pdfplumber |
| CLC 分类(zh/en-classify) | bge m3/large rerank CPU | 慢(10–30s/篇),准 |

**结论**:19 工具全部 CPU 可跑通,无隐藏 GPU 依赖。

---

## 二、环境要求(甲方机器)

| 项 | 要求 |
|----|------|
| OS | Linux x86_64 |
| Python | 3.11(用 conda 建两个独立环境) |
| MySQL | 8.0+(utf8mb4) |
| Node.js | 18+(前端) |
| CPU | 多核(8+ 为宜,pipeline/bge 并发受益) |
| 内存 | ≥ 16GB(bge-m3 CPU 推理 + onnxruntime 占内存) |
| 磁盘 | ≥ 15GB(包 3.8G + 解压 + conda 环境 + mineru 模型缓存) |
| 网络 | 必须能联外网(GLM 云 API + 模型首次下载) |
| GPU/CUDA | **不需要** |

**三个独立环境**:
1. `semantic`(项目后端):FastAPI + torch CPU + bge + faiss-cpu + jieba/nltk
2. `mineru_cpu`(可选但推荐):mineru pipeline,citation 保版面质量
3. Node.js(前端):Vue3 + Vite7

---

## 三、解压部署包

```bash
# 解压到 /opt(或甲方自定目录)
mkdir -p /opt/semantic_toolkit_final
tar -xzf semantic_toolkit_final_nogpu_20260825.tar.gz -C /opt/semantic_toolkit_final
cd /opt/semantic_toolkit_final
```

包内已含:全部源码 + `models/`(bge-m3 4.3G + bge-large-zh 1.3G + bge-small-zh 92M)+ `rag_store/`(CLC 检索库)+ `rules/`(规则/训练配置)+ `data/datasets/`(标注数据)。**前端 dist 与 node_modules 未打包**(需甲方 build,见第六节)。

---

## 四、后端 conda 环境(semantic)

```bash
conda create -n semantic python=3.11 -y
conda activate semantic
cd /opt/semantic_toolkit_final

# ① torch CPU 版(关键:用 CPU 索引,不要装 +cu 版)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# ② 项目依赖(requirements-ml.txt 的 torch>=2.2 已由上步装好,会跳过)
pip install -r requirements.txt -r requirements-ml.txt

# ③ nltk 数据(分句/词性用)
python -c "import nltk; [nltk.download(x) for x in ('punkt','punkt_tab','stopwords','averaged_perceptron_tagger')]"

# ④ 验证关键依赖
python -c "import torch,faiss,sentence_transformers,jieba,nltk,fastapi; print('backend deps ok', 'cuda' if torch.cuda.is_available() else 'cpu')"
# 期望:backend deps ok cpu
```

> `requirements-ml.txt` 里 `faiss-cpu>=1.8` 本就是 CPU 版;`torch>=2.2` 不锁 cuda,CPU 版可装。
>
> 若 `pip install torch --index-url .../cpu` 被 `requirements-ml.txt` 覆盖成 cu 版:先装 torch CPU,再 `pip install -r requirements-ml.txt --no-deps torch`(或手动 `pip install torch --index-url .../cpu` 再装其余)。一般不锁 cuda 不会覆盖。

---

## 五、mineru_cpu conda 环境(citation 保质量,可选但推荐)

**作用**:citation-intent / citation-sentiment 走 mineru 保版面质量;双栏/扫描件回退 mineru 保结构。**不部署此环境**:这些工具降级 pdfplumber(能跑不报错,但版面/表格/双栏信息丢失,citation 召回降低)。

```bash
# 独立 conda 环境,不带 vllm
conda create -n mineru_cpu python=3.11 -y
conda activate mineru_cpu

# 关键:只装 core + pipeline extra,不装 vllm extra
pip install "mineru[core,pipeline]"
# pipeline extra 自带 onnxruntime(>1.17.0,CPU),无需 CUDA

# 验证:不应 import vllm(纯 CPU pipeline)
python -c "import mineru; print('mineru ok', mineru.__version__)"
# 若报 ImportError: vllm → 说明该 mineru 版本 api 启动代码硬 import vllm(非预期),
#   兜底: pip install vllm (纯 wheel 装上但不调用,--enable-vlm-preload 已关)。
#   若 vllm wheel 因 cuda runtime 缺失装不上,反馈项目方适配。

# 记录环境路径(后面 .env / 启动脚本要用)
echo $CONDA_PREFIX
# 例:/root/autodl-tmp/conda/envs/mineru_cpu
```

### 5.1 mineru pipeline 模型(首次下载)

mineru 首次运行会自动下载 pipeline 模型(paddle/onnx 权重)到 `~/.cache/huggingface/` 与 `~/.cache/modelscope/`,**需联网**。

- **有网机器**:首次启动 mineru-api 时自动下载(见第十节),下载完即可。
- **无网/离线机器**:先在一台有网机器跑一次 mineru pipeline 触发下载,再整体拷贝 `~/.cache/huggingface/` 和 `~/.cache/modelscope/` 到甲方机器同路径。

### 5.2 配置 mineru-api 启动脚本路径

```bash
cd /opt/semantic_toolkit_final
# 改 scripts/mineru_api_cpu.sh 的 ENV 指向你的 mineru_cpu 环境(默认 /root/autodl-tmp/conda/envs/mineru_cpu)
# 方式一:直接改脚本里 ENV= 行
# 方式二:启动时用环境变量覆盖
export MINERU_CPU_ENV=/your/path/to/mineru_cpu
```

`scripts/mineru_api_cpu.sh` 与 GPU 版差异:不清 GPU 残留(无 GPU)、不等显存、不传 `--enable-vlm-preload`(无 vllm)、并发默认 3、已设 `OMP_NUM_THREADS=4`。

### 5.3 supervisor 守护(生产推荐)

```bash
# 无 GPU 版用 mineru-api-cpu.conf(与 GPU 版 mineru-api.conf 二选一,program 名都是 mineru-api,勿同启)
# 先按实际改 conf 里 PATH 的 conda 环境路径
CONF=config/supervisor/supervisord.conf
supervisord -c $CONF
supervisorctl -c $CONF restart mineru-api
```

`mineru-api-cpu.conf` 要点:`startsecs=180`(CPU pipeline + onnxruntime 模型加载慢,给 180s)、`stopwaitsecs=60`、`MINERU_API_MAX_CONCURRENT_REQUESTS=3`、`OMP_NUM_THREADS=4`。

---

## 六、前端 npm 环境(Vue3 + Vite7)

```bash
cd /opt/semantic_toolkit_final/frontend

# 安装前端依赖(node_modules 未打包,需联网)
npm install

# 方式一:开发模式(默认 5173,vite.config 已配 proxy /api → 后端 8000,无需配 nginx)
npm run dev
# 访问 http://<服务器IP>:5173

# 方式二:生产构建 + nginx
npm run build          # 产出 frontend/dist
# 用 nginx 部署 dist:root 指向 frontend/dist,proxy /api → http://127.0.0.1:8000/api/
# 参考包内 frontend/nginx.conf(Docker 部署版,proxy_pass backend:8000 按实际改 127.0.0.1:8000)
```

> 前端 dev 模式 `vite.config.ts:11` 已配 `proxy: {'/api':'http://127.0.0.1:8000'}`,5173 调后端无跨域问题。后端 `.env` 的 `CORS_ORIGINS` 也已含 5173/6006。

---

## 七、MySQL 数据库初始化

```bash
mysql -u root -p
```

```sql
-- 建库(utf8mb4)
CREATE DATABASE IF NOT EXISTS semantic_toolkit
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 建用户并授权(密码改成甲方自己的)
CREATE USER IF NOT EXISTS 'semantic_user'@'%' IDENTIFIED BY 'your_strong_password';
GRANT ALL PRIVILEGES ON semantic_toolkit.* TO 'semantic_user'@'%';
FLUSH PRIVILEGES;
```

> 后端启动时 `database.initialize()` 会自动执行 `infrastructure/database/schema_mysql.sql` 建全部表(含 `INSERT IGNORE` 默认工作区 'default'),**无需手动建表**。

---

## 八、配置 .env(无 GPU 版)

```bash
cd /opt/semantic_toolkit_final
cp config/.env.nogpu config/.env   # 用无 GPU 配置覆盖
```

按实际改 `.env` 三处:

```ini
# ① GLM 云 API Key(甲方自己的,必填;无 GPU 版 LLM 全靠云)
GLM_API_KEY=你的GLM_API_KEY
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
GLM_MODEL=glm-5.2

# ② MySQL 连接(密码改成第七步建的)
DATABASE_URL=mysql+pymysql://semantic_user:your_strong_password@127.0.0.1:3306/semantic_toolkit?charset=utf8mb4
DATABASE_AUTO_CREATE=true       # 启动自动建表+播种(保持 true)
DATABASE_REQUIRED=true

# ③ mineru_cpu 环境路径(降级备用 CLI 路径,按实际 conda 环境填)
MINERU_BIN=/your/path/to/mineru_cpu/bin/mineru

# 以下无 GPU 版已配好,无需改:
# MINERU_API_URL=http://127.0.0.1:8899
# MINERU_BACKEND=pipeline
# MINERU_API_TIMEOUT=900
# MINERU_MAX_CONCURRENCY=3
# PDF_EXTRACT_MODE=light        # 极速版:纯文本工具走 PyMuPDF,citation 走 mineru
# BGE_DEVICE=cpu                # bge 向量走 CPU
```

---

## 九、bge 模型(包内已有,确认即可)

包内 `models/` 已含:
- `models/bge-m3`(4.3G)——deep-cluster / CLC rerank / 综述用,**硬依赖 sparse_linear.pt,不可换 small**
- `models/bge-large-zh-v1.5`(1.3G)——CLC 分类备选
- `models/bge-small-zh-v1.5`(92M)——轻量备选

代码按 `settings.MODELS_DIR`(项目根 `models/`)读取,`.env` 的 `BGE_DEVICE=cpu` 强制 CPU(代码本身也 `_gpu_available()` 自适应,双保险)。**勿移动 `models/` 目录**。

---

## 十、启动服务(顺序)

按序启动,任一可独立验证:

### 10.1 启动 MySQL
确保 MySQL 服务在跑,第七步的库/用户已建。

### 10.2 启动 mineru-api(可选,推荐 citation 保质量)
```bash
conda activate mineru_cpu
cd /opt/semantic_toolkit_final
export MINERU_CPU_ENV=$CONDA_PREFIX
bash scripts/mineru_api_cpu.sh          # 后台启动,等就绪
# 或 supervisor 守护(见 5.3)
curl http://127.0.0.1:8899/health       # 期望 {"status":"healthy","max_concurrent_requests":3}
```
> 首次启动会下载 pipeline 模型(见 5.1),可能数分钟。`mineru-api` 不起也不阻塞后端(降级 pdfplumber)。

### 10.3 启动后端(自动建表 + 播种内置资源)
```bash
conda activate semantic
cd /opt/semantic_toolkit_final
export OMP_NUM_THREADS=4          # 限 bge/torch CPU 线程,留核给 mineru-api(8核设4/16核设6-8)
python -m uvicorn presentation.main:app --host 0.0.0.0 --port 8000
```

启动日志应见:
```
presentation.main: 数据库结构初始化完成：mysql          # 自动建表 + 默认工作区 + 13 内置资源
presentation.main: mineru-api 常驻服务就绪：http://127.0.0.1:8899 (backend=pipeline)  # mineru 已起
# 或:mineru-api 不可用(...),文件解析将降级 pdfplumber  # mineru 没起也不崩
INFO: Application startup complete.
```

`database.initialize()` 会自动:`schema_mysql.sql` 建全表 → `INSERT IGNORE` 默认工作区 'default' → `_seed_bundled_semantic_resources()` upsert 13 个 `RES-BUNDLED-*` 内置资源(指向 `project://rag_store`、`project://rules`、`project://data/datasets` 包内文件)。**启动即就绪,无需跑种子脚本**。

### 10.4 启动前端
```bash
cd /opt/semantic_toolkit_final/frontend
npm run dev          # 开发模式 5173(proxy /api → 8000)
```

---

## 十一、部署验证(冒烟测试)

```bash
# 1. 后端健康检查
curl http://127.0.0.1:8000/health
# 期望:{"status":"ok","database":{"connected":true},...,"llm_configured":true}

# 2. 前端打开 http://<服务器IP>:5173,测一个纯文本工具(应秒级返回):
#    如 zh-keyword /text、rq-detect /text、general-ner /text(带 RES-BUNDLED-NER-GENERAL 资源)

# 3. 测 deep-cluster /text(单篇,慢但应成功,bge-m3 CPU)

# 4. 测 citation-intent /file(需 mineru-api 起来,慢 30-90s;mineru 未起则降级 pdfplumber)
```

13 个内置资源校验(MySQL):
```sql
SELECT id, resource_key, name FROM semantic_resources WHERE source_type='bundled';
-- 期望 13 行 RES-BUNDLED-*(CLC/DOMAIN/EN-TERM/CITATION/NER/CLUSTER 系列)
```

---

## 十二、性能调优(无损提速)

CPU 版速度天花板 = bge-m3 CPU 推理 + onnxruntime pipeline(已核实 deep-cluster 硬依赖 `sparse_linear.pt`,m3 不可换 small;用户选保留 mineru pipeline + CLC rerank 质量优先)。以下无损调优榨干 CPU:

1. **OMP_NUM_THREADS**(onnxruntime/torch CPU 线程):留 2 核给后端(uvicorn)+ GLM(httpx IO)。8 核机设 4,16 核机设 6-8。过大抢核反慢。
   - mineru-api 侧:已在 `scripts/mineru_api_cpu.sh` + `mineru-api-cpu.conf` 设 `OMP_NUM_THREADS=4`
   - **项目后端启动前也要 export**(限 bge torch CPU 线程,留核给 mineru-api):`export OMP_NUM_THREADS=4`
2. **并发对齐**:`MINERU_API_MAX_CONCURRENT_REQUESTS=3` + `MINERU_MAX_CONCURRENCY=3`(onnxruntime 单请求占核,8 饱和排队)。16 核+可调 4,收益非线性。
3. **GLM 云 API**:不占本地 CPU/GPU,是 CPU 版的免费提速(已是)。
4. **PyMuPDF 取文**:17 工具已秒级(已是)。

**性能预期(CPU 版,保留全功能)**:

| 工具类型 | CPU 表现 |
|---------|---------|
| 17 纯文本工具 | 秒级,与 GPU 版差距小 |
| deep-cluster / 综述 / 文献集合(bge-m3 CPU) | 单篇 5–30s,批量累积 |
| citation-intent/sentiment(mineru pipeline CPU) | 单文件 30–90s(vllm 9.5s 的 3–9 倍) |
| CLC 分类(bge rerank CPU) | 一篇 10–30s |
| 双栏/扫描回退(mineru pipeline CPU) | 慢,但质量优于 pdfplumber |

> 若某项太慢影响使用,可选(有损质量,本包默认未启用):citation 清空 `STRUCTURE_DEPENDENT_TOOLS` 走 PyMuPDF(秒级,版面降)、CLC 降级规则不用 rerank(秒级,精度降)、双栏/扫描强制 pdfplumber 不回退 mineru(快,质量降)。

---

## 十三、故障排查

### 13.1 mineru-api 启动报 vllm import 错
`pip install "mineru[core,pipeline]"` 后启动报 `ImportError: vllm`:
- 该 mineru 版本 api 启动代码硬 import vllm(非预期)
- 兜底:`pip install vllm`(纯 wheel 装上但不调用,`--enable-vlm-preload` 已关);vllm wheel 因 cuda runtime 缺失装不上则反馈项目方

### 13.2 bge CPU 太慢(deep-cluster/综述卡在编码)
- 临时:减小批量篇数(分批跑)
- 根本:换 bge-small-zh-v1.5(改 `settings.BGE_M3_PATH` 指向 small + 重建 rag_store 索引),精度降但 CPU 快 10 倍——**注意 deep-cluster 的 bge_m3_sparse 硬依赖 `sparse_linear.pt`,换 small 会让 deep-cluster 崩,仅 CLC/检索可换**

### 13.3 onnxruntime CPU 占满核致系统卡顿
```bash
export OMP_NUM_THREADS=4    # 限 onnxruntime/numpy 线程,留核给系统/后端
```

### 13.4 mineru pipeline 模型下载失败(无网/慢)
无网环境:在有网机器跑一次 mineru pipeline 触发下载,再整体拷贝 `~/.cache/huggingface/` 和 `~/.cache/modelscope/` 到甲方机器。

### 13.5 GLM 云 API 超时
无 GPU 版 LLM 全靠云 API,网络到 `open.bigmodel.cn` 不通则所有工具失败。确认 `GLM_API_KEY` 有效 + 网络可达。

### 13.6 后端启动报数据库连接失败
- MySQL 服务未起/库未建/密码错:查 `DATABASE_URL`
- 表不存在:`DATABASE_AUTO_CREATE=true` 会自动建,保持 true

### 13.7 工具报 422 缺资源
7 个工具必填内置资源(zh/en-classify、domain-classify、en-keyword、citation-intent、general-ner、research-ner、domain-ner),资源 ID 形如 `RES-BUNDLED-CLC-ZH`。若缺,查 `semantic_resources` 表(见第十一节),重启后端会重新 upsert。

---

## 十四、文件索引

| 文件 | 作用 |
|------|------|
| `config/.env.nogpu` | 无 GPU 配置模板(`cp .env.nogpu .env`) |
| `scripts/mineru_api_cpu.sh` | mineru-api CPU 启动脚本(pipeline,不预加载 vllm) |
| `config/supervisor/mineru-api-cpu.conf` | CPU 版 supervisor 守护(与 GPU 版二选一) |
| `config/default_semantic_resources.py` | 13 个内置资源定义(启动自动播种) |
| `infrastructure/database/schema_mysql.sql` | 建表 SQL + 默认工作区(启动自动执行) |
| `frontend/vite.config.ts` | 前端 dev proxy `/api`→8000 |
| `frontend/nginx.conf` | 前端生产 nginx 配置(proxy /api→后端) |
| `docs/无GPU版部署文档.md` | 本文档 |
| `docs/MinerU_vLLM部署文档.md` | GPU 版部署文档(甲方有 GPU 时参考) |
| `README_极速版完整包.md` | 项目整体说明 |

> GPU 版的 `mineru-api.conf` / `mineru_api_guarded.sh` / `.env`(vlm-engine) 本包也保留,供有 GPU 机器切换。无 GPU 机器用上述 `.nogpu` / `_cpu` 系列即可。
