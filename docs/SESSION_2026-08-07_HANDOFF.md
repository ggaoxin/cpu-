# 会话交接文档（2026-08-07）

> 本文件用于跨窗口/跨会话交接。新窗口打开后先读本文件 + `docs/HANDOFF.md` 即可接续。

## 项目基础

- **项目根**：`/root/autodl-tmp/semantic_toolkit_final/`（注意带 `_final`，旧记忆里的 `/semantic-toolkit/` 已废弃）
- **架构**：DDD 四层 + FastAPI 后端（端口 8000）+ Vue 3/vite 前端（端口 6006）+ MySQL + GLM-5.2
- **大模型**：GLM-5.2，OpenAI 兼容协议；结构化任务必须关 thinking（`extra_body`），否则空响应（见 [[glm-reasoning-model-empty-response]]）
- **MinerU**：`/root/autodl-tmp/conda/envs/mineru/bin/mineru`，GPU 模式（RTX 3090 24GB）
- **cwd 注意**：工具调用间 cwd 会回退到 `/root`，所有命令需 `cd /root/autodl-tmp/semantic_toolkit_final &&` 前缀，或用 `git -C <path>`、绝对路径
- **pkill 陷阱**：`pkill -f "uvicorn presentation"` 会连带杀掉当前 shell（exit 144）；pkill 和重启必须分两次 Bash 调用

## 服务启停

```bash
# 后端（YAML 规则改动需全重启，--reload 不够）
cd /root/autodl-tmp/semantic_toolkit_final
nohup python -m uvicorn presentation.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
# 前端
cd frontend && nohup npm run dev > /tmp/frontend.log 2>&1 &
# MySQL
service mysql start
# 健康检查
curl -s http://127.0.0.1:8000/health
```
前端 vite.config.js 已加 `watch: { usePolling: true }` 绕过 inotify 限制（vscode-server 占满 65535）。

## 终端菜单

```bash
cd /root/autodl-tmp/semantic_toolkit_final && python test_menu.py
```
- 共 **15 项**，覆盖全部 19 个规则。用 FastAPI TestClient 进程内起应用，不用单独开后端。
- 13 命名实体识别 / 14 引用句识别：选父项后弹子类型菜单（ner_general/domain/research/relation；cr_intent/sentiment）。
- 10/11/12（dc_cluster/cl_label/sr_review）多篇功能：输入后提示**并发解析数**（默认 5，上限 6）。
- 所有编号输入经 `unicodedata.normalize("NFKC")` 全角→半角，兼容中文输入法全角数字。

## 本会话改动（8 个提交，均在 main 分支，未 push）

### 1. 研究问题识别 rq_identify（rules/research_question/rq_identify.yaml + semantic_service.py）
- **置信度**：schema 加 `confidence`(0-1, required)，中英 prompt 加打分标尺（0.9-1.0 显式主旨句/0.7-0.8 隐式目标句/0.5-0.6 偏方法动机）。后端 `_execute_rq_identify` 对 confidence 做 float 强转+clamp[0,1]+round(2)。归一化器 `_confidence` 本就支持。
- **来源章节**：改为"标题优先 + LLM 语义兜底"。`_rq_detect_section` 仅返回真实标题层级路径（如`（一）立项依据： / 1．研究背景与动机`），不再对前置内容一律补"摘要"；无标题时回退到 LLM 的 `source_section` 字段（LLM 按段落内容判 摘要/引言/方法…）。schema 加 `source_section`(required)，prompt 指导"陈述缺口/动机的段落是引言不是摘要"。
- **expression_type**：显式(explicit，点缺口)/隐式(implicit，目标陈述)，按主干措辞判，不确定判 implicit。
- **验证**：MOGONET（无标题）"Therefore, there is a need for..."→Introduction，摘要句→Abstract；projectrecommend.pdf（有标题）→层级路径。

### 2. test_menu.py 补全 + 并发（test_menu.py）
- 补 3 类 7 规则：NER(ner_general/domain/research/relation)、引用句(cr_intent/sentiment)、概念定义(cd_identify)。FPS 12→15 项。
- get_text 对 ner_*/cr_*/cd_identify 取 full_text（非摘要）；show 加专用展示分支。
- 全角数字归一化 `_norm()`。
- 多篇功能加 `select_concurrency()`（默认 5 上限 6），传 `params.concurrency`。

### 3. 深度聚类/综述并发解析（semantic_service.py）
- 抽 `_parse_papers_concurrent` 助手（ThreadPoolExecutor），dc_cluster(dual_view=True 含 LLM 双轴抽取) 与 sr_review(dual_view=False) 共用，替换原串行循环。
- **实测并发上限**：RTX 3090 24GB，后端 uvicorn 常驻 2500MiB，单 MinerU 峰值 ~3344MiB，**6 路并发峰值 22564MiB(91%) 无 OOM，第 7 路 OOM**。默认 5、硬上限 6。
- 10 篇估算：原串行 ~10 分钟 → 并发 5 路 ~2-3 分钟。
- 用户明确：现实场景是全新 PDF 一次性批处理，**不加路径缓存**（无重复 PDF）。

## 关键文件速查

| 文件 | 作用 |
|---|---|
| `rules/research_question/rq_identify.yaml` | rq-detect 规则（schema: sentence/phrase/implication/expression_type/confidence/source_section） |
| `application/service/semantic_service.py` | 所有 `_execute_*` 引擎；`_execute_rq_identify`(~897)、`_rq_detect_section`(~1020)、`_parse_papers_concurrent`(~1574)、`_execute_clustering`(~1640)、`_execute_structured_review`(~1917) |
| `application/service/result_normalizer.py` | 各工具结果归一化；`_confidence`(16行) clamp[0,1] |
| `frontend/src/utils/visualizationRenderers.js` | 可视化渲染（字符串模板 v-html）；`sourceSectionHierarchy`、`confidence()` |
| `frontend/src/assets/prototype.css` | rq 句子表 fixed 布局 + 层级章节 CSS |
| `frontend/vite.config.js` | `watch: { usePolling: true }` |
| `test_menu.py` | 终端 15 项菜单 |
| `infrastructure/document_parser/mineru_reader.py` | MinerU 解析（无缓存，每次 subprocess，独立 tempfile 目录线程安全） |
| `docs/HANDOFF.md` | 项目自包含交接（含全部 19 功能点设计） |

## 设计方案汇总（汇报用）

见本会话生成的"功能点设计方案汇总"（已口头输出）。一句话：以 GLM-5.2 为核心，四范式——**LLM 直驱+字面校验**（研究问题/关键词/NER）、**LLM+规则引擎分层调分**（摘要语步/引用/概念）、**LLM 优先+RAG 兜底**（分类）、**向量匹配+多步流水线**（聚类/综述）；统一靠 resolve_code/字面校验/冲突仲裁防幻觉。19 规则/10 功能项。

## 待办 / 未决

- **未 push**：本会话 8 个提交均在本地 main，用户每次问"要 push 吗"未确认。push 前必须问用户（见 [[ask-before-git-push]]）。
- 深度聚类大数据待办：诱导器改"先聚类错例再按簇归纳"（见旧记忆大数据待办节）。
- 规则库重设计方法论见 [[rule-redesign-methodology]]。

## 用户工作方式偏好

- 改完代码即 commit（用户要能随时回退，见 [[always-commit-push-after-changes]]）；push 前必须问。
- 主动汇报长任务进度；诚实说明限制。
- 现实场景导向（如拒绝缓存方案，因现实无重复 PDF）。
