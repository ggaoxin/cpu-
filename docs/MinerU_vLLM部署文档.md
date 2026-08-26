# MinerU vLLM 常驻服务部署文档（本项目专用）

> 版本：mineru 3.4.5 ｜ vllm 0.21.0 ｜ torch 2.11.0+cu130 ｜ 服务端口 8899 ｜ 文档日期 2026-08-25

本项目 PDF 结构化解析依赖 MinerU。MinerU 官方 CLI（`mineru` 子进程）每次启动都要冷加载模型，单文件 43s；本项目改用 **mineru-api 常驻 HTTP 服务 + vllm-engine 后端预加载模型**，单文件纯推理降至约 9.5s，批量并发吞吐再 ×8，且响应直接含 `md_content`/`content_list`，无需落盘读文件。

---

## 一、部署架构

```
                  ┌──────────────────────────────────────┐
   PDF 字节流      │  mineru-api 常驻服务 (127.0.0.1:8899) │
  ───────────────► │  ┌────────────────────────────────┐  │
  POST /file_parse │  │  vllm-engine 后端              │  │
  (mineru_api_     │  │  VLM 模型启动时预加载常驻显存   │  │
   client.py)      │  │  并发上限 8 (信号量钳制)        │  │
                   │  └────────────────────────────────┘  │
                   └──────────────────┬───────────────────┘
                                      │ md_content + content_list (JSON)
                                      ▼
                   项目后端 result_normalizer / 各工具消费
```

**组件分工**：

| 组件 | 角色 | 位置 |
|------|------|------|
| `mineru-api` | mineru 3.4.5 自带的 HTTP 服务进程，加载 vllm-engine 后端 | conda 环境 `mineru_vllm/bin/mineru-api` |
| vLLM 0.21.0 | 推理引擎，托管 MinerU 的 VLM 模型，常驻显存 | conda 环境 `mineru_vllm` |
| supervisor | 守护 mineru-api 进程，崩溃自拉起 | `config/supervisor/` |
| `mineru_api_guarded.sh` | 启动包装：清 GPU 残留进程 + 等显存释放 + exec 前台 | `scripts/mineru_api_guarded.sh` |
| `MineruApiClient` | 项目侧 HTTP 客户端（单例，httpx 线程安全） | `infrastructure/document_parser/mineru_api_client.py` |

**数据流**：项目代码 `MineruApiClient.parse_pdf()` → `POST http://127.0.0.1:8899/file_parse`（form: backend/return_md/return_content_list + files）→ mineru-api 调 vllm-engine 推理 → 返回 `{results: {<文件名>: {md_content, content_list}}}`。

---

## 二、环境准备

### 2.1 硬件 / 驱动

| 项 | 要求 |
|----|------|
| GPU | NVIDIA GPU，显存 ≥ 24GB（VLM 模型常驻约占 18–20GB；启动脚本以 `free > 20000MiB` 为就绪判据） |
| CUDA Toolkit | 13.0（cu130），`/usr/local/cuda`，须含 `nvcc`（flashinfer JIT 编译需要） |
| NVIDIA Driver | 与 CUDA 13.0 匹配（≥ 570 系列） |

### 2.2 conda 环境 `mineru_vllm`

实测版本矩阵（已在本环境验证）：

| 包 | 版本 |
|----|------|
| mineru | 3.4.5 |
| vllm | 0.21.0 |
| torch | 2.11.0（+cu130） |
| ninja | 必装（flashinfer JIT） |
| flashinfer | vllm 运行时 JIT 编译 |

**从零建环境（参考）**：

```bash
conda create -n mineru_vllm python=3.11 -y
conda activate mineru_vllm

# 1) torch 2.11 + cu130（按官方索引）
pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu130

# 2) vllm 0.21.0（自带 flashinfer 依赖）
pip install vllm==0.21.0

# 3) mineru 3.4.5（含 mineru-api CLI）
pip install -U "mineru[core]==3.4.5"

# 4) ninja（flashinfer AOT/JIT 编译器）
pip install ninja

# 5) pypdfium2（项目客户端 _count_pages 用，毫秒级数页不耗 GPU）
pip install pypdfium2
```

> 若 `flashinfer` 首次推理时报 JIT 编译错误，确认 `PATH` 同时含 conda `bin`（ninja）与 `/usr/local/cuda/bin`（nvcc），并设 `CUDA_HOME=/usr/local/cuda`——supervisor 配置已设好，手动调试时也要导出（见下文命令）。

### 2.3 关键环境变量（PATH 必须含两处）

```bash
ENV=/root/autodl-tmp/conda/envs/mineru_vllm
export PATH="$ENV/bin:/usr/local/cuda/bin:$PATH"
export CUDA_HOME=/usr/local/cuda
export MINERU_API_MAX_CONCURRENT_REQUESTS=8   # vllm 并发上限
```

> 缺 `ninja`（PATH 无 conda bin）或缺 `nvcc`（PATH 无 cuda bin）→ flashinfer JIT 失败 → 模型加载报错。这是最常见的部署坑。

### 2.4 VLM 模型

mineru 3.4.5 的 VLM 模型由 mineru 包管理，**首次启动 `--enable-vlm-preload true` 时自动下载**到 HuggingFace 默认缓存（`~/.cache/huggingface/`）。无网络环境需提前在有网机器下载后整体拷贝该缓存目录。

> 本项目 `.env` 不指定模型路径——用 mineru 默认 VLM。如需指定自定义模型，参考 mineru 3.4.5 文档的模型配置项。

---

## 三、部署 vLLM 常驻服务

### 3.1 启动命令（核心）

```bash
/root/autodl-tmp/conda/envs/mineru_vllm/bin/mineru-api \
  --host 127.0.0.1 \
  --port 8899 \
  --enable-vlm-preload true
```

- `--enable-vlm-preload true`：**启动时即把 VLM 模型加载进 vLLM 常驻显存**，后续请求免冷启动。这是性能关键，不可省。
- `--host 127.0.0.1`：仅本机访问（项目后端同机）。如需跨机改 `0.0.0.0` + 防火墙。
- `--port 8899`：与项目 `.env` 的 `MINERU_API_URL` 一致。

### 3.2 两条启动路径

| 场景 | 脚本 | 说明 |
|------|------|------|
| **生产（推荐）** | `config/supervisor/` 守护 | 崩溃自拉起、GPU 残留自清理、日志轮转 |
| 手动调试 | `scripts/start_mineru_api.sh` | 前台看日志或后台 nohup |

#### 手动启动（调试用）

```bash
cd /root/autodl-tmp/semantic_toolkit_final

# 前台（看实时日志）
bash scripts/start_mineru_api.sh --foreground

# 后台（nohup，日志 /tmp/mineru-api.log，脚本会轮询 /health 直到就绪）
bash scripts/start_mineru_api.sh
```

---

## 四、supervisor 守护部署（生产）

### 4.1 配置文件

- `config/supervisor/supervisord.conf`：独立 supervisord（专用 socket `/tmp/mineru-supervisor.sock`，与系统 supervisord 隔离，避免冲突）
- `config/supervisor/mineru-api.conf`：`[program:mineru-api]` 程序定义

`mineru-api.conf` 要点：

```ini
[program:mineru-api]
command=bash /root/autodl-tmp/semantic_toolkit_final/scripts/mineru_api_guarded.sh
directory=/root/autodl-tmp/semantic_toolkit_final
environment=PATH="/root/autodl-tmp/conda/envs/mineru_vllm/bin:/usr/local/cuda/bin:%(ENV_PATH)s",CUDA_HOME="/usr/local/cuda",HOME="/root",MINERU_API_MAX_CONCURRENT_REQUESTS="8"
autostart=true
autorestart=true
startsecs=120          # 模型预加载慢，给 120s 宽限才算"启动成功"
startretries=3
stopsignal=TERM
stopwaitsecs=30
stdout_logfile=/var/log/mineru-api.out.log
stderr_logfile=/var/log/mineru-api.err.log
```

### 4.2 启动包装脚本 `mineru_api_guarded.sh` 做了三件事

1. **清 GPU 残留进程**：`nvidia-smi --query-compute-apps=pid` 取残留 PID，先 `kill` 再 `kill -9`，解决异常崩溃（OOM/SIGKILL）后显存不释放。
2. **等显存释放**：轮询 `nvidia-smi --query-gpu=memory.free`，`free > 20000MiB` 才继续（最多等 30s）。
3. **exec 前台启动**：`exec mineru-api --host 127.0.0.1 --port 8899 --enable-vlm-preload true`，让 supervisor 直接管理该进程生命周期。

### 4.3 常用 supervisor 命令

```bash
CONF=/root/autodl-tmp/semantic_toolkit_final/config/supervisor/supervisord.conf

# 启动独立 supervisord（首次）
supervisord -c $CONF

# 查状态
supervisorctl -c $CONF status

# 重启 mineru-api（改配置后生效）
supervisorctl -c $CONF restart mineru-api

# 停止 / 启动
supervisorctl -c $CONF stop mineru-api
supervisorctl -c $CONF start mineru-api

# 看实时日志
supervisorctl -c $CONF tail -f mineru-api
# 或直接 tail 物理日志
tail -f /var/log/mineru-api.err.log
```

> 也可把 `mineru-api.conf` 放到系统 supervisor 的 include 目录（通常 `/etc/supervisor/conf.d/`）由系统 supervisord 统管；本项目默认用独立 supervisord 避免与 autodl 系统 supervisord 冲突。

---

## 五、项目对接

### 5.1 `.env` 配置（`config/.env`）

```ini
# ===== MinerU vLLM 常驻服务（主路径，替代 CLI）=====
MINERU_API_URL=http://127.0.0.1:8899      # mineru-api 常驻地址
MINERU_BACKEND=vlm-engine                 # 后端，vllm-engine 最快
MINERU_API_TIMEOUT=600                    # 单次解析超时(秒)，大PDF/排队时放宽
MINERU_PAGE_BUDGET=60                     # 单次并发页预算上限(PageBudgetPool 限流)
MINERU_MAX_CONCURRENCY=8                  # 项目侧并发上限(与 mineru-api max_concurrent 对齐)
```

> `.env` 里还有旧字段 `MINERU_BIN=/root/autodl-tmp/conda/envs/mineru/bin/mineru`（CLI 回退路径，仅当 8899 不可达且代码走 CLI 兜底时用，极速版主路径不再用）。常驻服务用的是 `mineru_vllm` 环境，不是 `mineru` 环境——两个环境分开，勿混。

### 5.2 客户端调用（`mineru_api_client.py`）

项目用单例 `MineruApiClient`（httpx.Client 线程安全，连接池复用，多 `asyncio.to_thread` 并发共享）：

```python
from infrastructure.document_parser.mineru_api_client import mineru_api_client

# 全文解析
result = mineru_api_client.parse_pdf("/path/to.pdf")
# result = {"md_content": "...", "content_list": [...], "pages": N}

# 只取前几页（摘要语步只需首页 abstract，降低 vllm 计算量）
result = mineru_api_client.parse_pdf("/path/to.pdf", end_page_id=2)  # 解析[0,2]页
```

- 请求：`POST /file_parse`，form=`{backend, return_md, return_content_list[, start_page_id, end_page_id]}` + `files={文件名: PDF字节}`
- 响应：`{results: {<文件名>: {md_content, content_list}}}`，客户端取第一个文件的 `md_content` + `content_list`
- 容错：超时/异常/空内容返回 `None`，由上层 `process_pdf` 触发 pdfplumber 兜底

### 5.3 何时走 mineru（极速版分流）

`PDF_EXTRACT_MODE=light` 极速版下：

| 场景 | 走向 |
|------|------|
| 17 个纯文本工具（keyword/ner/rq/concept…） | PyMuPDF 极速取文，**不走 mineru** |
| citation-intent / citation-sentiment | **走 mineru**（保版面结构，`STRUCTURE_DEPENDENT_TOOLS`） |
| 双栏论文 / 扫描件（`_page_is_dual_column` 检测） | 自动**回退 mineru**保质量 |
| light 取文为 0（漏抽） | 用 `_source_pdf_path` 回退 mineru 重抽 |

即：极速版下 mineru 只在「需要版面结构」或「PyMuPDF 抽不到」时才被触发，大部分请求走 PyMuPDF 秒级返回，mineru 负载大幅下降但仍不可缺。

---

## 六、验证

### 6.1 服务健康检查

```bash
curl http://127.0.0.1:8899/health
```

正常返回（mineru-api 3.4.5 协议 v2）：

```json
{
  "status": "healthy",
  "version": "3.4.5",
  "protocol_version": 2,
  "queued_tasks": 0,
  "processing_tasks": 0,
  "completed_tasks": 212,
  "failed_tasks": 0,
  "max_concurrent_requests": 8,
  "processing_window_size": 64,
  "task_retention_seconds": 86400,
  "task_cleanup_interval_seconds": 300
}
```

- `status=healthy` 即可用；`failed_tasks` 应为 0 或极小。
- `max_concurrent_requests=8` 与 `.env` `MINERU_API_MAX_CONCURRENCY` 一致。
- `processing_tasks` 持续高位且 `queued_tasks` 堆积 → 并发打满，调大并发或排查慢请求。

### 6.2 实测解析一篇

```bash
curl -s -X POST http://127.0.0.1:8899/file_parse \
  -F "backend=vlm-engine" \
  -F "return_md=true" \
  -F "return_content_list=true" \
  -F "files=@/path/to/test.pdf" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);r=list(d['results'].values())[0];print('md:',len(r['md_content']),'字符');print('content_list:',len(r['content_list']),'项')"
```

期望：`md` 数千字符、`content_list` 数十项，耗时约 9–15s（单文件纯推理）。

### 6.3 项目后端对接验证

启动项目后端：

```bash
cd /root/autodl-tmp/semantic_toolkit_final
python -m uvicorn presentation.main:app --host 0.0.0.0 --port 8000
```

启动日志应见：

```
presentation.main: 数据库结构初始化完成：mysql
httpx: HTTP Request: GET http://127.0.0.1:8899/health "HTTP/1.1 200 OK"
presentation.main: mineru-api 常驻服务就绪：http://127.0.0.1:8899 (backend=vlm-engine)
```

`mineru-api 常驻服务就绪` 这行出现 = 项目已成功探测并对接常驻服务。若见 `mineru-api 不可达` 警告，回查 8899 是否启动。

---

## 七、性能调优

### 7.1 并发

| 参数 | 位置 | 作用 |
|------|------|------|
| `MINERU_API_MAX_CONCURRENCY=8` | supervisor env / `.env` | mineru-api 侧 vllm 并发上限（信号量钳制，超出的请求排队） |
| `MINERU_MAX_CONCURRENCY=8` | `.env` | 项目侧提交并发上限，应 ≤ mineru-api 侧 |
| `processing_window_size=64` | mineru-api 内部 | 滑动窗口大小，一般不动 |

> 两者对齐为 8（实测 A100/3090 显存够用的安全值）。显存富余可调到 12–16，但注意 VLM 单请求显存占用，过高会 OOM 崩溃被 supervisor 拉起（`mineru_api_guarded.sh` 会清残留再起）。

### 7.2 页预算（PageBudgetPool）

`MINERU_PAGE_BUDGET=60`：项目侧多文件并发时，对回退 mineru 的请求按页数预算限流（防止 >60 页 PDF 多文件同时压垮显存）。`/files` 批量接口走此限流；单文件 `/file` 不经 pool。

> 历史坑：>60 页 PDF 多文件并发曾因 pool 无封顶死锁（`acquire` 永久阻塞）。已改 `budget=min(页数, 上限)` 封顶独占，3 个 280 页 PDF 从超时无响应→176s 全成功。页预算调大救不了死锁，必须 `min` 封顶。

### 7.3 限页降算力

摘要语步等只需首页内容的工具，传 `end_page_id` 限定解析范围：

```python
# 只解析前 3 页（0-indexed 闭区间 [0, end_page_id]）
mineru_api_client.parse_pdf(path, end_page_id=2)
```

vllm 只算指定页，省时省显存。全文场景不传（`None`=全文）。

### 7.4 性能基线（实测）

| 方式 | 单文件/页耗时 | 备注 |
|------|--------------|------|
| **mineru-api vllm-engine 常驻** | ~0.88s/页（单文件 ~9.5s） | **最快，本项目主路径** |
| mineru pipeline 后端 | ~1.55s/页 | 慢于 vlm |
| mineru hybrid 后端 | ~1.72s/页 | 慢 |
| mineru hybrid+txt | ~1.01s/页 | 仍慢于 vlm |
| mineru CLI 子进程 | 79s/文件 | 冷启动拖累，已弃用 |

结论：**vlm-engine 常驻无替代**，其余 backend/CLI 均更慢。

---

## 八、故障排查

### 8.1 flashinfer JIT 编译失败

```
RuntimeError: No available memory. / flashinfer JIT compilation failed / ninja: command not found
```

**根因**：PATH 缺 `ninja`（conda bin）或 `nvcc`（cuda bin）。
**解决**：确认 supervisor env 或手动启动前导出：

```bash
export PATH="/root/autodl-tmp/conda/envs/mineru_vllm/bin:/usr/local/cuda/bin:$PATH"
export CUDA_HOME=/usr/local/cuda
# 验证
which ninja && which nvcc
```

### 8.2 GPU 显存不释放（崩溃后起不来）

```
[guarded] GPU 显存未释放 free=XXXXMiB，等待...
```

**根因**：上次 OOM/SIGKILL 留下孤儿 vllm worker 占显存。
**解决**：`mineru_api_guarded.sh` 会自动 `nvidia-smi` 查残留 PID 并 kill。若手动排查：

```bash
nvidia-smi --query-compute-apps=pid,used_memory --format=csv
# kill 残留 PID，等 free > 20000MiB 再重启
supervisorctl -c <CONF> restart mineru-api
```

### 8.3 8899 端口被占

```bash
fuser 8899/tcp          # 看占用进程
# 若是旧 mineru-api 残留，kill 后 supervisor 会自拉新进程
```

### 8.4 单次解析超时（`MINERU_API_TIMEOUT`）

大 PDF（>100 页）或并发打满排队时，单请求可能超 `600s`。
- 临时：`.env` 调大 `MINERU_API_TIMEOUT=1200`
- 根本：用 `end_page_id` 限页；或调大 `MINERU_API_MAX_CONCURRENCY`（显存允许时）

### 8.5 项目报「mineru-api 不可达」但 curl /health 正常

检查 `.env` 的 `MINERU_API_URL` 末尾**不要带斜杠**（客户端会 `rstrip("/")`，但写错端口/地址最常见）。确认 `http://127.0.0.1:8899`。

### 8.6 completed 多但 failed 也涨

`/health` 的 `failed_tasks` 持续涨 = 有 PDF 解析失败。看 `/var/log/mineru-api.err.log`，常见是损坏 PDF/扫描件 OCR 失败。项目侧 `parse_pdf` 返回 None 会自动 pdfplumber 兜底，不影响主流程。

---

## 九、附录

### 9.1 版本矩阵

| 组件 | 实测版本 |
|------|---------|
| mineru | 3.4.5 |
| mineru-api 协议 | protocol_version 2 |
| vllm | 0.21.0 |
| torch | 2.11.0 +cu130 |
| CUDA Toolkit | 13.0（/usr/local/cuda，含 nvcc） |
| conda 环境 | `mineru_vllm`（常驻主路径）/ `mineru`（CLI 回退，旧） |
| 服务端口 | 8899 |
| supervisor socket | `/tmp/mineru-supervisor.sock` |

### 9.2 命令速查

```bash
# === 服务生命周期 ===
CONF=/root/autodl-tmp/semantic_toolkit_final/config/supervisor/supervisord.conf
supervisord -c $CONF                          # 首次起 supervisord
supervisorctl -c $CONF status                 # 看状态
supervisorctl -c $CONF restart mineru-api     # 重启
supervisorctl -c $CONF tail -f mineru-api      # 实时日志

# === 健康与解析 ===
curl http://127.0.0.1:8899/health
curl -X POST http://127.0.0.1:8899/file_parse -F backend=vlm-engine -F return_md=true -F return_content_list=true -F files=@test.pdf

# === GPU ===
nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits   # 空闲显存
nvidia-smi --query-compute-apps=pid,used_memory --format=csv      # 占用进程

# === 项目后端 ===
cd /root/autodl-tmp/semantic_toolkit_final && python -m uvicorn presentation.main:app --port 8000
curl http://127.0.0.1:8000/health
```

### 9.3 文件索引

| 文件 | 作用 |
|------|------|
| `config/supervisor/mineru-api.conf` | supervisor 程序守护配置 |
| `config/supervisor/supervisord.conf` | 独立 supervisord 主配置 |
| `scripts/mineru_api_guarded.sh` | 生产启动包装（清残留+等显存+exec） |
| `scripts/start_mineru_api.sh` | 手动启动脚本（前台/后台） |
| `infrastructure/document_parser/mineru_api_client.py` | 项目侧 HTTP 客户端（单例） |
| `infrastructure/document_parser/mineru_reader.py` | mineru 解析结果后处理 |
| `config/.env` | `MINERU_API_URL`/`MINERU_BACKEND` 等对接配置 |
| `config/settings.py` | 上述配置的读取与默认值 |
