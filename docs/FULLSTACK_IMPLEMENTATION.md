# 语义计算工具全栈实现与部署说明

版本：2026-08-04  
技术栈：Vue 3 + Vite、FastAPI、Python、MySQL 8（本地开发可使用 SQLite）

## 1. Vue 在 DDD 项目中的位置

Vue 是独立客户端，不属于后端 DDD 的领域层、应用层或基础设施层，因此放在项目根目录 `frontend/`，与四层后端并列：

```text
semantic_toolkit_final/
├── frontend/          Vue 页面、真实接口客户端、历史/集合选择器、可视化
├── presentation/      FastAPI 路由、HTTP 校验、统一响应
├── application/       19 功能编排、结果归一化、资源、导出、确认与反馈
├── domain/            任务/结果实体以及仓储契约
├── infrastructure/    MySQL/SQLite、文档解析、GLM、规则库和仓储实现
├── config/            19 功能注册、Vue—后端映射、运行配置
├── rules/             19 个功能独立规则库
├── models/            本地模型资源
├── rag_store/         分类检索资源
├── tests/             算法脚手架与全栈契约测试
└── docker-compose.yml Vue + FastAPI + MySQL 8 编排
```

依赖方向保持为：`frontend → presentation → application → domain ← infrastructure`。Vue 不直接访问数据库，也不引用 Python 领域对象。

## 2. 已实现的数据流

1. Vue 根据页面输入发送 JSON 或 multipart 请求。
2. FastAPI 把 19 个 Vue 工具 ID 映射到原后端 19 个功能码。
3. 单文本默认同步处理；文件、批量文本、批量文件、集合和历史任务带 `Prefer: respond-async`，后端返回 HTTP 202 与真实 `task_id`。
4. Vue 自动查询任务状态，完成后读取结果记录；页面只显示原有“处理中/完成”状态，不增加步骤进度条。
5. 应用服务调用原有语义算法，并把各算法的内部数据转换为可视化组件使用的稳定字段。
6. MySQL 保存任务、逐项状态、结果、上游依赖、参数、模型版本和时间。
7. 实体关系可复用实体与依存句法记录；标签可复用聚类任务；综述可复用文献集合和聚类任务。
8. 后端导出 JSON、CSV、XML、RDF 或 Markdown 报告，并保存导出记录。

## 3. 核心代码职责

| 位置 | 职责 |
|---|---|
| `config/tool_contracts.py` | 19 个 Vue 工具 ID 与原算法功能码的唯一映射 |
| `application/service/tool_integration_service.py` | 输入适配、同步/后台任务、算法调用、结果持久化、上游血缘 |
| `application/service/result_normalizer.py` | 把 19 种原算法输出转换成 Vue 的稳定结果字段 |
| `application/service/resource_service.py` | 文献集合和用户词典用例 |
| `application/service/export_service.py` | JSON/CSV/XML/RDF/报告文件生成 |
| `application/service/upstream_record_service.py` | 接收其他后端提供的实体/依存句法结构化记录 |
| `application/service/result_governance_service.py` | 分类确认、标签确认、反馈、结果血缘 |
| `infrastructure/database/connection.py` | MySQL 8 与 SQLite 的连接、事务和 DDL 初始化 |
| `infrastructure/database/schema_mysql.sql` | MySQL 完整建表脚本 |
| `presentation/api/v1/integration_controller.py` | Vue 精确路由、任务、历史、集合、词典、导出和确认接口 |
| `frontend/src/services/api.js` | JSON/multipart、错误解析、异步任务轮询 |
| `frontend/src/components/HistorySelector.vue` | 从数据库加载真实兼容历史记录 |
| `frontend/src/components/CollectionSelector.vue` | 从数据库加载真实文献集合 |
| `frontend/src/components/ToolRequestExtras.vue` | 用户词典保存、历史版本选择以及各工具专属输入 |

## 4. 统一响应

```json
{
  "code": 0,
  "message": "succeeded",
  "data": {
    "task_id": "tsk_...",
    "tool_id": "general-ner",
    "status": "succeeded",
    "input_type": "text",
    "progress": 100,
    "total": 1,
    "success_count": 1,
    "failed_count": 0,
    "results": [
      {
        "item_id": "itm_...",
        "record_id": "rec_...",
        "status": "succeeded",
        "source": {},
        "result": { "entities": [] }
      }
    ],
    "summary": {},
    "available_exports": ["json", "csv"]
  },
  "meta": {
    "request_id": "req_...",
    "schema_version": "1.0",
    "model_version": "semantic-toolkit-2026.08",
    "elapsed_ms": 100,
    "created_at": "2026-08-04T00:00:00+00:00",
    "database_dialect": "mysql"
  }
}
```

演示可视化只存在于前端工具目录；不进入在线请求、任务或数据库。真实响应存在时，可视化自动使用 `data.results[].result`。

## 5. 数据库设计与原因

| 数据域 | 表 | 为什么需要 |
|---|---|---|
| 工作空间与版本 | `workspaces`, `model_versions` | 隔离数据并解释历史结果由哪个模型产生 |
| 文件与文献 | `files`, `documents`, `document_collections`, `collection_documents` | 多功能复用同一文献，聚类和综述不必反复上传 |
| 任务 | `analysis_tasks`, `task_items` | 保存同步/后台任务状态，批量逐项失败时可定位 |
| 结果与血缘 | `result_records`, `record_dependencies` | 统一查询 19 种结果，并追踪实体→关系、聚类→标签/综述 |
| 用户词典 | `dictionaries`, `dictionary_versions`, `dictionary_terms` | 词典可复用、可版本化，历史关键词结果可复现 |
| 结果投影 | `move_*`, `classification_*`, `keyword_*`, `entity_*`, `relation_*`, `cluster_*`, `review_*` | 完整 JSON 继续留在统一结果表，同时把查询、统计、确认和下游复用字段结构化保存 |
| 分类与本体 | `taxonomy_versions`, `taxonomy_nodes`, `ontology_versions`, `ontology_nodes` | 正式装载 CLC/专业体系和本体版本，不能把分类清单硬编码在 Vue |
| 人工闭环 | `classification_confirmations`, `cluster_revisions`, `cluster_corrections`, `cluster_label_confirmations`, `user_feedback` | 人工最终值不覆盖模型原结果，支持纠错和模型迭代 |
| 输出与外部系统 | `exports`, `external_writebacks` | 导出文件生命周期和外部写回可追踪、可重试 |
| 审计 | `audit_events` | 为后续接入用户身份、权限和变更审计保留统一结构 |

正式环境使用 `infrastructure/database/schema_mysql.sql`；SQLite 脚本仅用于本地验证，不替代正式 MySQL。

## 6. 运行方式

### 6.1 本地 SQLite 验证

```powershell
cd semantic_toolkit_final
python -m pip install -r requirements.txt
python -m pip install -r requirements-ml.txt
cd frontend
npm install
cd ..
.\scripts\start_fullstack.ps1 -UseSqlite
```

- Vue：`http://127.0.0.1:6006`（autodl 自定义服务端口；本地可用 `VITE_DEV_PORT` 改）
- FastAPI 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

### 6.2 MySQL 8 + Docker Compose

```powershell
Copy-Item .env.docker.example .env
# 修改 .env 中的 MYSQL_PASSWORD、MYSQL_ROOT_PASSWORD、GLM_API_KEY
docker compose up --build
```

- 统一入口：`http://127.0.0.1:8080`
- MySQL 数据使用命名卷 `mysql_data`
- 本地 `models/`、`rag_store/`、`data/` 以只读卷提供给算法容器
- 本地 `runtime/` 保存导出文件

若服务器已有 Python/GPU 环境，也可不用 Docker 启动算法容器，只把 `DATABASE_URL` 指向 MySQL：

```text
mysql+pymysql://semantic_app:密码@127.0.0.1:3306/semantic_toolkit?charset=utf8mb4
```

## 7. 配置项

| 变量 | 说明 |
|---|---|
| `GLM_API_KEY` | 调用 GLM 的必填密钥 |
| `GLM_BASE_URL` | GLM 兼容接口；模型固定为 `glm-5.2` |
| `DATABASE_URL` | MySQL 或本地 SQLite URL |
| `DATABASE_AUTO_CREATE` | 启动时幂等创建表 |
| `DATABASE_REQUIRED` | 数据库连接失败时是否阻止服务启动 |
| `ASYNC_WORKERS` | 进程内后台任务并发数，默认 4 |
| `CORS_ORIGINS` | 允许调用 API 的 Vue 地址 |
| `MAX_UPLOAD_SIZE_MB` | 后端上传大小上限 |
| `MODELS_DIR`, `RAG_STORE_DIR`, `DATA_DIR` | 本地算法资源目录 |

真实密钥只放 `config/.env` 或部署环境变量，不写入源代码。

## 8. 通用资源与治理接口

| 接口 | 作用 |
|---|---|
| `GET /api/v1/tasks` | 真实任务历史 |
| `GET /api/v1/tasks/{id}` | 任务状态与计数 |
| `POST /api/v1/tasks/{id}/rerun` | 复制历史输入生成新任务 |
| `POST /api/v1/tasks/{id}/cancel` | 取消排队/运行任务；已进入单次模型调用时在调用返回后生效 |
| `POST /api/v1/tasks/{id}/archive` | 逻辑归档 |
| `GET /api/v1/results/{id}/lineage` | 上下游依赖图数据 |
| `GET /api/v1/history/compatible` | 为下游页面返回兼容成功记录 |
| `POST/GET /api/v1/collections` | 创建/查询文献集合 |
| `POST/GET /api/v1/dictionaries` | 保存/查询用户词典；同名同语言再次保存时生成新版本 |
| `GET /api/v1/dictionaries/{id}?version=N` | 读取当前或指定历史版本的词典与术语 |
| `POST /api/v1/upstream-records/{entity\|dependency}` | 导入其他后端的实体或依存句法结果 |
| `POST /api/v1/exports` | 生成结果导出文件 |
| `POST /api/v1/classification-results/{id}/confirm` | 保存分类人工确认 |
| `POST /api/v1/cluster-labels/{id}/confirm` | 保存标签人工确认 |
| `POST /api/v1/results/{id}/feedback` | 保存评分、意见或结构化纠错 |

## 9. 已验证项目

- Python 全层编译通过。
- 19 个 Vue 工具与 19 个原算法功能码逐一执行契约测试通过。
- 前端登记的 67 个业务请求地址与 FastAPI 路由逐一核对，缺失 0 个。
- 任务、结果、文献集合、词典、上游依赖、血缘、确认、反馈和导出数据库测试通过。
- 后台任务提交与查询测试通过。
- 非法阈值、缺少领域、聚类数量不足、缺少上游记录均返回参数错误且不创建任务。
- Vue 生产构建通过。
- 本地 Vue→FastAPI 代理、数据库健康检查、真实历史下拉、独立滚动和演示可视化完成浏览器实测。
- 用户词典的新增版本、指定历史版本载入、任务参数传递、结果命中信息与数据库投影契约测试通过；中文关键词页面新增区域完成 1280×720 浏览器排版检查，无横向溢出和控制台错误。

本次工作机未检测到 MySQL/MariaDB 服务、3306/3307 监听、客户端命令或可读取的 Workbench 连接配置，且当前 Python 环境缺少 `PyMySQL`，因此本机只完成了 SQLite 的真实启动验收。MySQL DDL、连接适配、Docker Compose 和正式 `DATABASE_URL` 已在代码中提供；拿到实际 MySQL 地址、端口、用户和密码后仍需执行一次正式库建表与读写验收，不能把 SQLite 通过写成 MySQL 已通过。

运行测试：

```powershell
python -m unittest discover -s tests -p "test_fullstack_contracts.py" -v
npm.cmd --prefix frontend run build
```

## 10. 仍需业务方提供的数据或外部接口

完整代码已经提供相应表和接口，但以下内容不能由项目自行伪造：

1. 正式授权的中图法/专业分类体系版本与节点数据；
2. 正式 ScienceWISE 或其他领域本体数据及授权；
3. 基金项目目标数据库、字段映射、认证与绩效评估接口；
4. 引用分析所需的外部文献数据库查询接口；
5. 正式多用户认证、角色和 workspace 权限规则；
6. 生产数据保留期限、对象存储地址和备份制度。

这些外部依赖缺失时，19 个现有算法、页面、MySQL 任务/结果历史、集合、词典、导出和血缘仍可正常工作；外部写回与正式资源覆盖证明需拿到真实资料后再配置，不能用假数据冒充完成。
