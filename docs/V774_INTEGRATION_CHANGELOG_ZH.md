# V7.74 前后端适配修改记录

## 核心原则

- 以当前 Vue/需规字段为公共合同，旧后端字段只在应用层适配。
- 后端缺少但弹窗需要的字段由真实算法结果归一化生成；无法由当前结果计算的字段保持空值，不使用原型数字。
- 预览弹窗仍可用于 UI 审查；真实在线测试不会调用演示响应。

## 主要修改

| 文件/目录 | 修改目的 |
|---|---|
| `config/vue_contracts.py` | 固定 19 个功能的公共请求、响应字段与 67 种输入方式 |
| `application/service/tool_integration_service.py` | Vue 字段适配、必填校验、批量隔离、文件元数据、历史任务/文献集读取、资源解析和结果持久化 |
| `application/service/result_normalizer.py` | 将 19 个算法的内部结果转换为可视化弹窗真实字段 |
| `presentation/api/v1/integration_controller.py` | 提供 Vue 稳定路由、文件上传、历史、资源、评测和公共响应封装 |
| `infrastructure/database/schema_*.sql` | MySQL/SQLite 统一 52 张表，增加语义资源和模型评测记录 |
| `infrastructure/database/result_projection.py` | 将统一结果写入各功能业务表 |
| `frontend/src/services/api.ts` | 在线测试改为真实 FastAPI 请求，支持 JSON 与 multipart |
| `frontend/src/components/OnlineTester.vue` | 真实输入校验、数据库选项、批量逐条字段和真实响应展示 |
| `frontend/src/components/RequirementSupplement.vue` | 当前资源选择、引文元数据解析、独立聚类评测 |
| `semantic_toolkit_sdk` | 提供与 Vue 公共字段一致的 Python SDK |
| `tests/test_v774_http_contracts.py` | 覆盖所有公共模式、批量对应、特殊文件元数据、历史链路和评测持久化 |

## 已补足的重要字段/逻辑

1. 分类、关键词和研究问题的批量题目逐篇绑定，不再复用第一篇题目。
2. 基金项目名称逐项目绑定；文件名只在文件模式作为来源标识。
3. 引用文本模式严格传入当前引用句、前后文和被引文献元数据；批量任务逐条隔离。
4. 实体关系仅接收 NER 历史记录编号，原句、实体列表和依存句法均由后端读取/生成；批量 NER 的每条结果通过 `task_item_id` 精确绑定原文，切换历史记录不会误用第一篇文本。
5. 深度聚类文件模式保留文献编号、发表时间、题名、作者、来源、关键词。
6. 深度聚类独立评测计算真实 ARI/NMI/轮廓系数并写入数据库。
7. 聚类标签的 `cluster_phrase_sets` 已实际进入正式生成器；历史任务接口可从持久化聚类结果恢复短语集合。
8. 结构化综述文件和数据库文献集保留文献元数据，且不依赖历史深度聚类任务。
9. GLM 模型名称和启动期密钥检查可通过环境变量配置。

## 上服务器后仅需替换/确认的外部配置

- `GLM_API_KEY`、`GLM_BASE_URL`、`GLM_MODEL`。
- MySQL 地址、账号和密码。
- 服务器现有 BGE 模型、RAG 索引和数据目录路径。
- MinerU 可执行命令路径。

这些属于部署环境，不需要再次修改 Vue 公共字段或 19 个功能的路由代码。
