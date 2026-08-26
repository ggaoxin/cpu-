# V7.74 服务器部署与运行指南

## 1. 服务器需要保留的目录

上传整个项目，但模型权重可继续使用服务器现有目录。至少保留：`application`、`config`、`domain`、`infrastructure`、`presentation`、`rules`、`frontend`、`requirements*.txt`、`Dockerfile`、`docker-compose.yml`。深度聚类和本地复核需要服务器已有的 `models`、`rag_store`、`data`；MinerU 由服务器环境提供。

## 2. 配置

复制 `config/.env.example` 为 `config/.env`，至少修改：

```env
GLM_API_KEY=服务器真实密钥
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
GLM_MODEL=glm-5.2
GLM_REQUIRED_AT_STARTUP=true
DATABASE_URL=mysql+pymysql://semantic_app:数据库密码@127.0.0.1:3306/semantic_toolkit?charset=utf8mb4
DATABASE_AUTO_CREATE=true
DATABASE_REQUIRED=true
CORS_ORIGINS=http://服务器前端地址
```

`GLM_REQUIRED_AT_STARTUP=false` 只适合无密钥的前后端联调；模型功能仍会返回明确错误，不会伪造结果。

## 3. Docker Compose（推荐）

先复制并编辑 Docker 环境配置，再启动：

```bash
cp .env.docker.example .env
# 编辑 .env：填写 GLM_API_KEY、MYSQL_PASSWORD、MYSQL_ROOT_PASSWORD
docker compose up -d --build
```

浏览器访问 `http://服务器地址:8080`。后端健康检查为 `http://服务器地址:8080/health`（由 Nginx 代理）或容器内 `http://backend:8000/health`。

## 4. 非 Docker 启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-ml.txt
uvicorn presentation.main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run build
```

开发查看可运行 `npm run dev -- --host 0.0.0.0`。生产环境使用 `dist` 和 `frontend/nginx.conf`。

## 5. MySQL

应用启动时会根据 `infrastructure/database/schema_mysql.sql` 创建 52 张表并登记内置语义资源。生产数据库账号需要对 `semantic_toolkit` 库拥有建表、查询、插入和更新权限。已有数据库不会删除用户数据；`CREATE TABLE IF NOT EXISTS` 只补建缺失表。

## 6. GLM 与本地模型

- 语步、分类、研究问题、引用、NER 等模型型功能使用 `GLM_MODEL` 指定的大模型。
- 深度聚类使用 BGE-M3/本地聚类路线，应用场景轴可使用 GLM 做可审计语义强化；失败时按实现的本地降级路线运行。
- 聚类标签正式默认使用 GLM 候选 + BGE-M3/V11 复核，单类簇失败会记录并回退。
- 结构化综述正式环境会调用 GLM，但证据必须能回指输入文献；无来源支撑的候选会被丢弃。
- `MINERU_BIN` 应指向服务器可执行的 MinerU 命令；PDF 解析失败时才使用轻量 PDF 解析回退。

## 7. 上线前验收命令

```bash
python -m unittest tests.test_fullstack_contracts tests.test_v774_http_contracts tests.test_five_tool_http_integration tests.test_sdk_client tests.test_glm_required -v
python -m compileall -q application config domain infrastructure presentation semantic_toolkit_sdk
cd frontend
npm run audit:interfaces
npm run audit:parity
npm run build
```

随后检查 `/health`：数据库应为 `connected: true`，正式部署的 `llm_configured` 应为 `true`。

## 8. Python SDK

在项目根目录执行 `pip install .`，然后使用：

```python
from semantic_toolkit_sdk import SemanticToolkitClient

client = SemanticToolkitClient("http://127.0.0.1:8000")
result = client.invoke_text(
    "/api/v1/research-question/text",
    payload={
        "scientific_document_fragment": "现有方法在小样本场景下泛化能力不足，如何提高稳定性？",
        "document_title": "小样本学习方法研究",
        "text_format_requirement": "自动识别",
    },
)
```

SDK 的 JSON、单文件、批量文件字段均使用 Vue 公共字段名，不要求调用方了解内部算法 DTO。
