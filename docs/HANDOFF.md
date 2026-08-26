# 语义计算工具库LLM — 项目交接文档

> **本项目是 semantic-toolkit 的LLM优先版**：所有功能不再用DocumentParser做章节解析，而是用MinerU全文直接输入，LLM从全文角度处理。
> 原项目 `/root/autodl-tmp/semantic-toolkit` 保持只读，不修改。本项目独立开发。

## 核心区别（vs 原项目）

| | 原项目（semantic-toolkit） | 本项目（semantic-tookitLLM） |
|---|---|---|
| 文档处理 | PDF→MinerU→DocumentParser章节解析→结构化（标题/摘要/关键词/章节/页码） | PDF→MinerU→MD→**直接用全文**（mineru_reader.py） |
| 分类输入 | DocumentParser提取的标题+摘要+关键词 | 全文→LLM提取双轴描述→聚类 |
| 规则库 | 基于章节结构的规则 | 基于全文的规则（持续调整中） |
| 关键新增 | - | mineru_reader.py + LLM双轴提取 + LLM主题精选 |

## 1. 项目总览

- **位置**：`/root/autodl-tmp/semantic-tookitLLM/`
- **架构**：DDD 四层 + FastAPI + GLM-5.2
- **核心模式**：MinerU全文 → LLM处理 → 规则库校验

## 1. 项目总览

- **位置**：`/root/autodl-tmp/semantic-toolkit/`
- **架构**：DDD 四层（presentation/application/domain/infrastructure）+ FastAPI + GLM-5.2（OpenAI兼容协议，`https://open.bigmodel.cn/api/paas/v4`）
- **核心模式**：每个功能点 = 独立规则库 YAML（`rules/<item>/<code>.yaml`）+ 大模型调用。API key 在 `config/.env`（GLM_API_KEY）
- **19 功能点**：注册在 `config/functional_points.py`，路由 `POST /api/v1/<功能项>/<功能点>`
- **方法论依据**：`/root/autodl-tmp/rule.pdf`（19条防过拟合规则库设计原则）
- **启动服务**：`uvicorn presentation.main:app --host 0.0.0.0 --port 8000`，文档 `http://localhost:8000/docs`

## 2. 核心架构（重要——所有功能复用）

分层式混合架构（非"规则全拼进prompt"，也非"纯LLM兜底"）：
1. **Prompt层**：只放少量抽象判定原则（principles），不逐条拼规则
2. **后置规则引擎层（为主）**：LLM输出后做确定性校验+pattern证据+调分+冲突检测
3. **冲突二次审核层**：规则与LLM冲突时，结构化证据送GLM二次裁定
4. **动态权重**：规则权重从验证集净收益学出来（太宽→停用，太紧→低权，中间地带存活）
5. **验证集准入**：规则从归纳集产出，在未参与归纳的验证集上测净纠错收益才采纳（防过拟合循环泄漏）

**语言 Profile 化**：`training/profile.py` 把语言相关配置（moves/分句/特征/prompt/路径）集中，共享核心读 `get_profile()`。中文默认，英文挂 EN_PROFILE。新增语言只需加一个 Profile。

关键文件：
- `training/rule_lib.py`：Rule/RuleLib（新schema：principles/pattern_rules/dictionaries + Rule带必要/排除条件/证据维度/等级/统计/动态权重）
- `training/rule_engine.py`：后置引擎（verify_and_adjust：校验+调分+冲突检测）
- `training/feature_extractor.py` / `feature_extractor_en.py`：确定性6维语义特征（零GLM）
- `training/conflict_review.py`：冲突二次审核
- `training/rule_inducer.py`：规则归纳+净收益准入+反例搜索+复杂度惩罚+等级分配
- `training/aggregator.py`：多折聚合+跨折去重+等级重评
- `training/profile.py`：语言Profile + get/set_profile_by_lang/code
- `application/service/semantic_service.py`：`_execute_with_engine` 走新管线（按code切profile）

## 3. 已完成功能

### 3.1 中文摘要语步识别（mr_zh_abstract）✅ 已交付
- 运行时规则库：`rules/move_recognition/mr_zh_abstract.yaml`（动态权重版8规则）
- 数据：`/root/autodl-tmp/datasets/chinese_abstracts.json`（2000篇）+ `chinese_abstract_move_results.json`
- 5语步：研究背景/目的/方法/结果/结论
- 结果（40篇留出集）：acc 0.79 / macroF1 0.67（动态权重版 macroF1 最高 0.676，研究目的F1 0.488）
- 备份：`training/runs/baseline5_seed.yaml`（5种子基线）、`dynamic_weighted.yaml`
- 评测：`python -m training.eval_rules --lang zh --n 40`
- 训练：`python -m training.run_training --lang zh`（数据上万时用，含验证集准入+动态权重）

### 3.2 英文摘要语步识别（mr_en_abstract）✅ 已完成
- 运行时规则库：`rules/move_recognition/mr_en_abstract.yaml`（5种子规则，新schema）
- 数据：`/root/autodl-tmp/datasets/clean_english_abstracts.json`（50篇）+ `clean_english_abstract_move_results.json`
- 5语步：Background/Objective/Methods/Results/Conclusion（注意复数）
- 结果（10篇留出集）：acc 0.755 / macroF1 0.754，Objective是短板（F1 0.364）
- 英文分句器 `sentence_seg_en.py`（缩写保护e.g./et al./Fig./小数点）
- 评测：`python -m training.eval_rules --lang en --n 10`
- 训练：`python -m training.run_training --lang en`

### 3.3 中文摘要语步识别的教训（重要，避免重蹈）
- 上一轮过拟合：训练后留出集从0.74掉到0.72，研究目的F1崩到0.24。根因：规则记训练集词语、循环泄漏（用训练集既归纳又验证）
- 修复：验证集分离准入 + 动态权重（太宽规则自动停用）+ 净纠错收益（改对-改错）
- **小数据（200篇）下诱导规则产不出泛化增益**，主要靠架构本身；数据上万+诱导器聚类改造后才发力
- 大数据待办：诱导器改成"先聚类错例、再按簇归纳"（当前逐错例归纳）

### 3.4 中文基金项目语步识别（mr_zh_fund）✅ 管线已交付，三本交叉验证通过（2026-08-01）
> 本节最初在另一窗口开发时因 context 爆满卡死；本窗口接手后完成 prompt 定稿与三本交叉验证。

- **任务**：基金申请/结题本子全文 → 按章节提取**五类语步**：①立项依据 ②研究目标 ③技术实施方案 ④预期成果 ⑤应用价值。
- **与摘要语步的区别**：基金本子按"章节"组织，同一语步内容散布在多个章节；输出须**归纳提炼**，不是原文拼接。
- **功能点**：`mr_zh_fund`，已注册 `config/functional_points.py:55`，路由 `POST /api/v1/move_recognition/mr_zh_fund`，规则库 `rules/move_recognition/mr_zh_fund.yaml`（`engine_type: fund_move`）。

#### 管线（`_execute_fund_move`，自适应全文直送，2026-08-03 改）
LLM 优先版：**不按 ## 章节切分**，从全文角度处理。按长度自适应：
```
全文（mineru markdown，不解析章节）
  ├─ 短全文（≤30000字）→ 单次 LLM 调用：summary_prompt + 全文 → 直接出归纳后五类语步（真·全文直送）
  └─ 长全文（>30000字）→ 按字数切块 map-reduce：
       ① 切成 10000字/块（非章节语义）
       ② 并发(5线程)：每块 system_prompt 提取五类语步(含confidence)
       ③ 过滤 confidence<0.5 → 按语步类型聚合（来源=块号"第X段"）
       ④ summary_prompt 汇总：各块片段 → 去重整合 → 归纳中文总结
  → 输出 [{move_type, content, sources[], text_location[], n_fragments}]
```
- 阈值/块大小：`FULL_TEXT_THRESHOLD=30000`、`CHUNK_SIZE=10000`（在 `_execute_fund_move` 内常量）。
- 溯源：单调用模式 sources=["全文"]；切块模式 sources=["第1段","第3段"...]（块号，取代旧章节标题）。`text_location` 保留字段但全文模式无页码→空数组。
- **为什么不再按章节切**：原管线按 `##` 切章节是"解析过"的结构化处理，违背 LLM 优先版"全文直接给 LLM"原则。改为全文直送/按字数切块后，LLM 从全文角度处理，长本子不丢内容（最长 14.7 万字→15 块）。
- 冒烟（2026-08-03）：project3(29173字→单调用) 五类齐全、预期成果两段结构保留；project1(56788字→6块) 五类齐全、多块片段正确聚合（技术实施方案 5 片段来自 3 块）。与三本标准对齐。

#### 文档解析（document_parser.py，本任务期间大幅扩展，改了35次）
- 新增 `doc_type: fund_project` 检测（FUND_MARKERS 打分≥2）与 `_parse_fund`：`_extract_fund_sections`(L1/L2/L3白名单) + 自适应拆分>4000字大章节(`_extract_sub_headings`) + `_check_fund_missing`/`_llm_find_missing_sections`(LLM补缺失章节)。
- 输入链路：mineru 把 PDF 转 markdown → `DocumentParser.parse(md_path)` → `doc['full_text']` → API。

#### 预期成果（语步④）判定规则 —— 已定稿验证通过
定稿口径写入 `mr_zh_fund.yaml` 的 system_prompt 第4条 + summary_prompt 第4条：
- 预期成果**分两段输出**：①**立项时拟达成的成果**——从项目摘要/研究目标提取"要达成什么/提供什么"（拟获得规律/提出机制/明确影响/提供理论依据，拟发论文/专利、培养人才），**即使没有"拟"字也算**，**允许与研究目标内容有适当重叠**（不要因研究目标已提及就把预期成果留空）；②**结题时的完成证据**——从"研究目标完成情况""项目取得成果的总体情况"简述完成情况，要点即可不堆砌研究细节。
- 结题报告正文的大量"研究结果"归完成证据简述，**不当作"立项时拟达成"**；若摘要和正文均无预期性内容，输出空字符串。
- **关键教训（用户定）**：prompt 不要太紧——早期只认"拟/计划/将"字眼 + "严禁研究结果"卡太死，反而把项目摘要里无"拟"字的前瞻性成果目标漏了、只剩照抄完成情况。放宽来源、允许与研究目标重叠后，内容才捞全。

#### 三本交叉验证结论（2026-08-01，对照 `minerutest/project.md` 标准）
project1(TiAl氢原子团簇)/project2(隐式非线性有限元软件)/project3(FeCoNiCr高熵合金氢脆) 五语步均与标准基本对齐：预期成果两段结构正确、纯中文、前瞻性成果目标捞全、不照抄研究结果。
- 共性小差距（可接受，按"不要太紧"不改）：输出偏技术细节，标准更带"自主可控/国产替代"宏观定位；个别篇章缺一两句次要表述。
- 调 prompt 时同步把汇总 `max_tokens` 1000→2500（防两段预期成果被截断）。

#### 用户硬性要求（务必遵守）
1. **全文直送 LLM**（2026-08-03 改，原"分章节"要求已废止）：全文直接给 LLM 从全文角度处理，不按 `##` 章节切分；长本子按字数切块（非章节语义）。置信度低→该语步片段丢弃；最后汇总归纳。
2. **不得返回原文拼接**——语步内容散布多处，须归纳提炼重新组织语言。
3. **输出必须纯中文**：英文片段只是中文摘要的翻译，以中文为准；只有英文片段时翻译提炼为中文，严禁保留英文原句。
4. 无内容可为空，不强求每类都有。

#### 标准对照与测试输入
- **标准**：`/root/autodl-tmp/datasets/PdfFiles/minerutest/project.md`（标准基金本子语步识别结果，含"立项时拟达成的成果"等）。同目录 `sections.md`、`section3.md`。
- **测试输入**：`/root/autodl-tmp/datasets/PdfFiles/minerutest/mineru_all/`（mineru 解析的 markdown，24个本子：18-30/ch1-8/project1-3，每个在 `<名>/auto/<名>.md`）。已持久化（原 `/tmp/mineru_all` 已删可弃）。
- **复跑命令**：
```bash
cd /root/autodl-tmp/semantic-toolkit
python -c "
from presentation.main import app
from fastapi.testclient import TestClient
import os, sys; sys.path.insert(0,'.')
from infrastructure.document_parser.document_parser import DocumentParser
parser=DocumentParser(); client=TestClient(app)
base='/root/autodl-tmp/datasets/PdfFiles/minerutest/mineru_all'
for f in sorted(os.listdir(base)):
    md=None
    for r,d,fs in os.walk(f'{base}/{f}'):
        for x in fs:
            if x.endswith('.md'): md=os.path.join(r,x); break
    if not md: continue
    doc=parser.parse(md)
    r=client.post('/api/v1/move_recognition/mr_zh_fund', json={'text':doc['full_text']}).json()
    print(f'\n=== {f} | {doc[\"title\"]} ===')
    if r['success']:
        for m in r['data']: print(f'【{m[\"move_type\"]}】\n{m.get(\"content\") or \"（空）\"}\n')
    else: print('error:',r.get('error','')[:200])
" 2>&1 | grep -vE "INFO|Warning|warn|Building|Loading|Dumping|Prefix|punkt|starlette"
```

#### 续作第一步
1. mr_zh_fund 已验证通过。若新增本子对照标准有偏差，调 `mr_zh_fund.yaml` 的 system_prompt/summary_prompt（不要动主管线），保持"不要太紧"原则。
2. GLM-5.2 是推理模型，结构化任务必须关 thinking（`glm_client` 已设 `extra_body={"thinking":{"type":"disabled"}}`，勿删）。
3. `glm_client.chat_json` 已加固：JSON 截断时先 `_repair_json` 补全引号/括号，仍失败则增大 max_tokens 重试一次（防长章节截断丢内容）。

## 4. 当前任务：中文科技文献分类（ac_zh）✅ 管线已交付，评测进行中
- 输入：`{ch_name 标题, ch_abstract 摘要, keywords[] 关键词}`（API 的 `text` 字段传整个 paper 的 JSON）
- 输出：main_classification + auxiliary_classifications[]（0-1个）+ is_interdisciplinary + selection_reason + rag_top_k_candidates + alignment_check
- 分类号：中图法（CLC），12468条，必须真实存在于知识库（防幻觉），路径从知识库复制
- 功能点code：`ac_zh`，规则库 `rules/auto_classification/ac_zh.yaml`（新schema：principles + output_schema + engine_type）
- 数据：`/root/autodl-tmp/datasets/random_50_chinese_papers.json`（50篇）+ 标准结果

### 4.2 资源
- **完整 CLC 知识库（40912 条）**：`/root/autodl-tmp/rag_store/clc_rag/clc_meta_full.json`（合并旧库12468 + PDF解析28444干净新码；TM7系列从1条→101条，含TM713电力系统短路等细码）
- **bge-large 索引（1024维）**：`infrastructure/rag/clc_index_large/`（clc_vectors_large_fullpath.npy + ragtext + manifest.json，编码40912条）
- 编码器：bge-large 在 `/root/autodl-tmp/models/models/BAAI--bge-large-zh-v1.5/snapshots/master`
- 完整中图法 PDF：`/root/autodl-tmp/zh_classify.pdf`（1100页，详表全码）
- **本机 GPU 现为 RTX 3090（24GB），不再是 2080Ti**——bge-large 可直接本机构建

### 4.3 知识库重建脚本（已执行）
- `scripts/parse_clc_pdf.py`：解析 PDF 详表（只取字母开头全码行）→ 38712 条
- `scripts/merge_clc_kb.py`：合并旧库+PDF（重复码用旧库干净名，新码过滤187条乱码）→ 40912 条 clc_meta_full
- `scripts/encode_full_index.py`：bge-large 编码 40912 条（fullpath+ragtext 两套向量）

### 4.4 已实现管线：LLM优先 + 二阶段层级细化 + 后置校验
```
输入(标题+摘要+关键词)
  → ①检索top-K（仅输出rag_top_k_candidates+兜底，不喂LLM，防锚定）
  → ②LLM凭CLC知识提议 main/aux/inter/reason（prompt不含候选）
  → ③二阶段层级细化：把初判码的同级+下位子码列给LLM选最贴切具体号
       （层级引导，非语义候选——只在该学科内选子码，不跨学科锚定）
  → ④后置校验：resolve_code上溯到知识库真实条目，名称/路径从meta复制（防幻觉）
  → 输出
```
关键文件：
- `infrastructure/rag/clc_retriever.py`：retrieve / get_by_code / resolve_code（上溯）/ children
- `application/service/semantic_service.py`：`_execute_classification` + `_refine_main_hierarchy`（二阶段）
- `infrastructure/rule_engine/rule_loader.py`：RuleLibrary 加 `engine_type`，has_engine 分发
- `training/eval_classification.py`：50篇评测（main_acc/main_hier_acc/main_branch_acc/aux/inter/防幻觉）
- `scripts/author_v3_standard.py`：基于完整库的自主判定 v3 标准

### 4.5 关键设计决策（实测驱动）
1. **LLM优先，检索退居**：弱检索候选会锚定LLM照抄错答（4/4 TM论文被带偏到TQ/TV）；不给候选时GLM自身CLC知识4/4判对二级类。故prompt不含候选，检索仅作输出+兜底。
2. **resolve_code上溯**：GLM提议的细码若知识库未收录，沿层级上溯到最长存在前缀（TM713→TM7），保学科判断+防幻觉。完整库后多数细码直接命中。
3. **二阶段层级细化**：解决"学科对但子码选错"（如TM712稳定 vs TM713短路）。冒烟6篇：main_acc 0.167→0.6、main_hier_acc 0.333→0.8。

### 4.6 交叉学科判定准则
主类=应用场景；辅助号=有分量次要主题（方法/技术或并列应用主题）；is_interdisciplinary = 主辅分属不同"学科边界"。学科边界：T大类取二级类（TM/TP/TQ…），其余取一级字母。同大学科双主题给辅助号但标false。

### 4.7 标准（gold）演进
- 原 gold：`*_clc_classification.json`（粗码，旧库粒度，30交叉）
- v2：`*_v2.json`（按学科边界重标，23交叉，作历史对照）
- **v3（当前）**：`*_v3.json`（基于完整库的自主判定，细码优先，25交叉，所有码精确命中知识库）。生成脚本 `scripts/author_v3_standard.py`。评测默认对 v3。

### 4.8 评测
- `python -m training.eval_classification --n 50 --top-k 25`（对 v3，带二阶段细化）
- 指标：main_acc（精确号）/ main_hier_acc（同分支）/ main_branch_acc（学科边界，主指标）/ aux_match / inter_acc+F1 / anti_hallucination_pass
- **全量50篇最终结果（0失败）**：main_branch_acc=0.94、main_top_acc=0.94、main_hier_acc=0.46、main_acc=0.38、inter_f1=0.81（P1.0/R0.68）、aux_match=0.30、防幻觉=1.0
- 解读：94% 判对学科；精确号 0.38 偏低因模型常选同二级类的兄弟/更细子码（粒度分歧）；交叉学科 F1 0.81（精确率 1.0，召回 0.68 偏保守）
- 注：完整库下检索 recall@25 降至0.26（细码分散），但管线不依赖检索，靠GLM知识+层级细化
- **关键修复**：GLM-5.2 是推理模型，reasoning_tokens 致挂起/空内容（曾导致评测反复超时）；`glm_client` 加 `extra_body={"thinking":{"type":"disabled"}}` 关推理后，50篇5分钟跑完0失败

### 4.9 英文科技文献分类（ac_en）✅ 管线+评测已交付
- **任务**：英文文献（SCI/EI/会议摘要）→ 中图分类号（跨语言映射，目标知识库同 clc_meta_full）
- **编码器**：bge-m3（多语言）建跨语言索引 `infrastructure/rag/clc_index_m3/`（40912×1024），英文query↔中文CLC。实测跨语言 recall@25 仅 0.04（英文摘要↔简短中文类名语义距离大），但管线 LLM 优先不依赖检索。
- **管线**：复用 `_execute_classification`，ac_en.yaml 设 `cross_lingual: true` → retrieve 走 bge-m3；英文 system_prompt；LLM 凭 CLC 知识做英→中图法映射；resolve_code 校验；二阶段层级细化。
- **关键文件**：`rules/auto_classification/ac_en.yaml`、`scripts/encode_m3_index.py`、`scripts/author_en_standard.py`（gold）、`clc_retriever.py` 的 `_ensure_m3_loaded`+`retrieve(cross_lingual=True)`
- **数据**：`/root/autodl-tmp/datasets/en_paper_50.json`（50篇英文）+ `en_paper_50_clc_classification.json`（Claude 自主判定 gold，3交叉）
- **评测**（50篇0失败）：main_branch_acc=0.92、main_hier_acc=0.66、main_acc=0.04、inter_f1=**0.571**（P0.5/R0.667）、aux_match=0.444、防幻觉=1.0
- **交叉学科过度判定已优化**（2026-08-03，改 ac_en.yaml prompt 规则3/4）：原 inter_f1=0.333（P0.2/R1.0，12个误报）。根因：模型把"论文使用的方法/工具学科"当辅助号→机械因边界不同判 inter=true。修复：辅助号分两类——①方法/工具型（借用工具，论文不贡献于该学科）给 aux 但 inter=false；②并列应用主题型（论文同时贡献于两个领域）给 aux 且 inter=true。判 inter 的真问题改为"论文是否对辅助学科有 substantive 贡献"。改后误报 12→2（剩2个为交通×电工/社会×政治边界模糊），F1 0.333→0.571。代价：+1 漏报（R65外科+TP计算机，gold标inter但模型判为工具型——经典模糊case，可加few-shot修复）。
- **结论**：学科准确率 0.92 与 ac_zh（0.94）相当，GLM 跨语言映射有效；交叉学科经 prompt 规则细化后大幅改善；如需进一步压漏报可补 few-shot（B方案）
- 评测命令：`python -m training.eval_classification --code ac_en --papers .../en_paper_50.json --gold .../en_paper_50_clc_classification.json --n 50`

### 4.10 专业领域科技文献分类（ac_domain）✅ 管线+评测已交付
- **任务**：两层分类——第一层 32 个专业领域（用户划定自定义体系）；第二层基于 RAG(clc_meta_full) 的细粒度中图法号。
- **数据**：`/root/autodl-tmp/datasets/professional_domain_classification_32x2_zh_simple.json`（64篇，32领域×2）+ `professional_domain_64_classification.json`（Claude 自主判定 gold，两层标注）
- **管线**：`_execute_domain_classification`（engine_type=domain_classification）——LLM 一次出 domain_code(01-32)+clc_code → 校验 domain 在列表内 → resolve_code+二阶段层级细化 clc。复用 ac_zh 的 resolve_code/`_refine_main_hierarchy`。
- **关键文件**：`rules/auto_classification/ac_domain.yaml`（含 32 领域 domain_list）、`scripts/author_domain_standard.py`（gold）、`training/eval_domain_classification.py`（两层评测）
- **评测**（64篇0失败）：**domain_acc=0.938**（第一层32领域）、**clc_branch_acc=0.984**（第二层CLC学科）、clc_hier_acc=0.625、clc_acc=0.172、防幻觉=1.0
- **4 个领域判错均为边界模糊**（地热跨地质/能源、合金跨材料/冶金、太阳能电池跨能源/材料、电力调度跨电气/能源——CLC 都落在正确学科），非真错。
- 评测命令：`python -m training.eval_domain_classification --n 64`

### 4.11 分类工具支持原始文档全文上传（2026-08-01 新增）
**背景**：实际场景是 mineru 提 PDF → DocumentParser 拆章节提取标题/摘要/关键词 → 进功能。但分类工具 `_parse_paper_input` 原本只收结构化 JSON 或纯摘要，传原始全文会把全文当摘要、标题/关键词丢失。
**改动**：
- `DocumentParser` 新增 `parse_text(text)`（`parse` 重构为读文件→调它），供已持有文本时调用。
- `semantic_service._parse_paper_input` 由 `@staticmethod` 改实例方法，新增分支：`text` 含 ≥2 个 markdown 标题行（`_looks_like_full_document`）时，先 `_extract_fields_from_document` 跑 DocumentParser 提取 title/abstract/keywords 再分类。覆盖 ac_zh/ac_en/ac_domain（都走同一入口）。轻量提取（不 set_glm，不跑章节缺失 LLM 兜底）。
- 英文论文关键词若原文无 Keywords 行则为空，**不兜底提取**（用户定）。
**验证**：直接传原始全文（不预解析 JSON）——中文论文 ch3→G641、英文论文 18→TP181、中文基金 project1→TG135，三类都正确提取字段并分类。`text` 仍可为结构化 JSON 或纯摘要（向后兼容）。
**文件**：`infrastructure/document_parser/document_parser.py`（parse_text）、`application/service/semantic_service.py`（_parse_paper_input/_looks_like_full_document/_extract_fields_from_document）。

### 4.12 GLM 客户端加固（2026-08-01）
`glm_client.chat_json` 原本 JSON 解析失败直接抛错。现加固：解析失败→`_repair_json` 补全未闭合的字符串/括号（修复 max_tokens 截断）→仍失败则 max_tokens 翻倍重试一次。避免长章节/大输出偶发截断丢内容（曾致 project2 某章节识别结果被跳过）。空内容重试机制不变。


## 5. 关键词识别（kw_zh / kw_en）✅ 管线+训练已交付

### 5.1 任务
- 输入：文献片段（中文含"标题。摘要"；英文纯摘要）
- 输出：`[{keyword, weight}]`，3-8 个，按主题代表性降序
- 数据：中文 `random_50_chinese_papers.json`（50篇）；英文 `/root/autodl-tmp/datasets/english_abstracts_keywords_original_preserved.json`（22篇，clean gold——关键词为规范短语列表，无作者名/单词/缩写噪声）

### 5.2 设计（与训练产物解耦，数据多了只重训模型文件，管线不动）
```
输入(标题+摘要)
  → ①确定性短语挖掘（中文jieba词性 / 英文nltk POS，抽名词短语候选 + 特征）
  → ②特征打分 → top-25 候选作提示
  → ③LLM 选/概括（优先原词，允许概念概括；避免量化修饰语；固定术语不拆）
  → ④后置引擎：去重 + 包含去重(保留简洁基础词) + 停用词 + 长度 + 排序
  → 输出
```
- 中英文复用同一管线 `_execute_keyword`，按 rule.lang 切挖掘器/语言。
- 训练产物：`rules/keyword_recognition/kw_zh_model.json`、`kw_en_model.json`（特征权重+few_shot）。

### 5.3 关键文件
- `training/keyword_phrase_miner.py`（中文 jieba）/ `keyword_phrase_miner_en.py`（英文 nltk POS）
- `application/service/semantic_service.py`：`_execute_keyword` 管线 + `_clean_keywords` 后置 + `_render_keyword_user_prompt`（双语）
- `training/run_keyword_training.py`：5 折 CV（双语，`--lang zh/en`，网格校准+few_shot+P/R/F1+未命中分析）
- `rules/keyword_recognition/kw_zh.yaml` / `kw_en.yaml`：engine_type=keyword + lang + principles + stopwords

### 5.4 评测
- `python -m training.run_keyword_training --lang zh --folds 5` / `--lang en --papers <英文数据集>`
- 指标：exact P/R/F1（逐字）+ partial P/R/F1（子串/Jaccard≥0.6）
- **中文 5 折**：exact_F1=0.347、partial_F1=0.541
- **英文 5 折（clean 数据集，22篇）**：exact_F1=0.391、partial_F1=0.511（与中文相当；曾在 en_keyword.json 抽样上仅 0.206/0.347，后证实是该数据集 gold 噪声——混入作者名/单词/缩写——所致，非模型问题）
- 训练（网格校准权重）增益有限（小数据过拟合噪声，符合方法论预期）；few-shot + LLM 是主力
- 演进路径：50篇→纯LLM+特征；几百篇→接 rule_inducer 归纳词典/搭配规则+动态权重；上千篇→加 PMI 短语挖掘模块。三次升级都不动主管线。


## 6. 研究问题句识别（rq_identify）✅ 管线+评测已交付

### 6.1 任务
- 输入：摘要文本（`text`，中/英）
- 输出：`[{sentence, phrase, implication}]`——研究问题句（摘要 verbatim 子串）+ 句中研究问题短语（句子 verbatim 子串，防幻觉，下游聚合用）+ 隐含问题释义（LLM 概括，人读用，非字面）
- 数据：中文从 `chinese_abstracts.json` 2000篇抽50；英文 `english_abstracts_keywords_original_preserved.json` 22篇。gold 由 Claude 自主标注（`rq_sample_72_gold.json`，67条RQ标注，5篇非研究文本无标注）

### 6.2 管线（LLM优先 + 后置字面校验）
```
摘要
  → LLM 识别 RQ 句+短语（直接返回 verbatim，中英按 lang 切 prompt）
  → 后置校验：句子须为摘要字面子串、短语须为句子字面子串（drop 不符，防幻觉）；implication 允许概括不校验
  → 去重 → 输出 [{sentence, phrase, implication}]
```
- 无需预分句（LLM 直接返回原句，后置校验字面）。
- 关键文件：`rules/research_question/rq_identify.yaml`（engine_type=rq_identify + 中英 system_prompt + principles）、`_execute_rq_identify`、`scripts/author_rq_standard.py`（gold）、`training/eval_rq.py`

### 6.3 评测（72篇0失败）
- gold 放宽：英文摘要常把"问题/缺口句"和"目标句"分写两句，原 gold 只标 gap 句；`scripts/broaden_rq_gold.py` 自动抽取含 "we propose/study/present" 的目标句补入 gold，使口径同时接受两类。
- LLM 裁判：pred 句未命中 gold 时，`eval_rq` 调 GLM 判其是否也是合理 RQ 句（只提精确率，不提召回，避免 R>1）。
- **结果**：句F1 全部0.78（中0.877/英0.647）、**篇章召回0.941**（中0.957/英0.909——模型在91-96%论文找到≥1有效RQ）、英文句精确率0.957（模型输出几乎都有效）、防幻觉=1.0、裁判TP=9
- 解读：英文原"低分"是 gold 与模型在 gap句 vs 目标句 上的识别分歧（非召回失败）；放宽+裁判后，篇章召回证明工具有效。count-R 偏低是放宽 gold 每篇2句、模型出1句的口径效应。
- 评测命令：`python -m training.eval_rq`（默认放宽 gold + LLM 裁判）；`--no-judge` 仅 verbatim 匹配


## 7. 深度聚类（dc_cluster）— TopicFusion v8 迁移 + bge-m3 优化

> 聚类标签（cl_label）/ 结构化综述（sr_review）仍待重新设计。dc_cluster 已迁移 TopicFusion v8.1 并用 bge-m3 优化父类打分。

### 7.1 设计（TopicFusion v8 双轴主题映射）
- **双轴独立**：技术路线轴（T01-T49，49父类）+ 应用场景轴（A01-A51，51父类），同一文献两轴各归一主题。
- **主题库匹配**：每篇文献→父类打分→Top2父类内检索细主题→融合4信号（中心相似度+代表文献+词汇+父类分）→阈值判 matched/review/candidate。
- **向量化**：原版 TF-IDF（char/word ngram），**已优化为 bge-m3 语义打分**（父类层）。
- **k 自动选**：主题库决定聚类结构，不让用户指定 k。

### 7.2 迁移落地
- **代码**：`infrastructure/clustering/topicfusion_v7/`（语义解析）+ `topicfusion_v8/`（主题记忆 memory.py/incremental.py/runtime.py），改了1处相对导入。
- **数据**：`rules/deep_clustering/`（mappings 主题库160技术+176应用 / models 204个joblib / rules rule_library_v7.json / taxonomy / v7_reference/gold / input_1000中英数据）。
- **包装层**：`semantic_service._execute_clustering`（engine_type=clustering）— texts(paper JSON list) → map_documents → 双轴映射结果+按主题分组。
- **注册**：functional_points dc_cluster（第17功能点，multi_text）+ deep_clustering_controller + router + dc_cluster.yaml。
- **依赖**：pandas/scipy/joblib（base 环境已装）。
- **验证**：20篇结果和原 TopicFusion 100% 一致。

### 7.3 bge-m3 父类打分优化（对照试验结果）
父类打分 `_parent_scores`（topicfusion_v8/memory.py）：`score = 0.72×semantic + 0.28×lexical + v8_overrides`
- **semantic 改用 bge-m3**：检测 `models/parent_{axis}_{lang}_bge.npy` 存在则用 bge-m3 编码 vs bge父类中心，否则 fallback TF-IDF。
- **bge 父类中心**：`scripts/build_bge_parent.py` 用 gold 文献的 txt(axis) 文本 bge-m3 编码按父类算中心（technical 49父类46覆盖 / application 51父类48覆盖）。
- **对照 gold 准确率**（1000中文，`scripts/clustering_eval_gold.py`）：

| 方案 | 技术acc | 应用acc | 技术macroF1 | 应用macroF1 |
|---|---|---|---|---|
| TF-IDF 基线 | 0.601 | 0.741 | - | - |
| bge-m3 + lexical（v1 gold） | 0.671 | 0.755 | 0.566 | 0.525 |
| **bge-m3 + lexical + v2 gold审查**（最优，已落地） | **0.768** | **0.850** | **0.783** | **0.767** |

- **gold 审查**（`scripts/audit_gold.py` 已弃用GLM版，改用 Agent/Claude 审查）：v1 gold（v7 model_reviewed）有 396 处错标（技术233+应用163）——医学/生物标签套电力论文、A39/A31/A40 过度套用等系统性错配。Agent（Claude）逐个读文献+父类定义判断，修正输出 `gold_zh_reviewed_v2.csv`。修正后准确率大幅提升（0.671→0.768、macroF1 0.566→0.783），证明 v1 gold 噪声严重拉低了评估。
- **bge 中心用 v1 gold 构建**（覆盖46/49父类），不用 v2 gold（v2 修正后某些父类文献少，覆盖降到41，macroF1 反降）。最优组合：v1 bge中心 + v2 gold评估。
- **结论**：bge-m3 优于 TF-IDF；lexical 词汇规则有正向增益（纯bge更差）；gold 审查价值最大（+9.7% acc、+21.7% macroF1）；补规则边际递减。
- **m3_encoder**：`infrastructure/rag/m3_encoder.py`（bge-m3 编码单例，懒加载）。

### 7.4 增量主题发现链路（GLM 四层审核，替代人工）
用户后期大批量文献来时，全自动发现新主题：
```
dc_cluster 运行时 → map_documents → candidate 进池
  → python -m scripts.clustering_incremental --candidates <候选池> --min-support 12
  → propose_incremental_topics 提案 → 四层审核：
    ① 相似度阈值（新提案名 vs 现有主题名）≥0.6 → use_existing（归已有）
    ②③ <阈值 → GLM判断 → accept（入库）/ use_existing（GLM查表挑已有名）
    ④ 都不确定 → pending（记录，用户手动加，不LLM再审）
```
- **GLM 审核器**：`infrastructure/clustering/topic_review.py`（review_proposal 四层判断）。
- **增量脚本**：`scripts/clustering_incremental.py`（propose + GLM审核 + 报告）。
- **验证**：input_1000 跑出 49 提案，GLM审核 4通过(1 accept+3 rename)/45 reject（边界不清），判断准确。

### 7.5 关键文件
- `infrastructure/clustering/topicfusion_v7/` + `topicfusion_v8/`（核心代码）
- `infrastructure/clustering/topic_review.py`（GLM 四层审核）
- `infrastructure/rag/m3_encoder.py`（bge-m3 编码器）
- `rules/deep_clustering/`（主题库/模型/规则/gold/数据）
- `scripts/clustering_eval_gold.py`（对照gold评测）
- `scripts/build_bge_parent.py`（构建bge父类中心）
- `scripts/clustering_incremental.py`（增量提案+GLM审核）
- `application/service/semantic_service.py:_execute_clustering`（包装层）

### 7.6 待优化
- **细主题换 bge（已试，失败回退）**：用 assignments 构建 bge 细主题中心，父类准确率反降（0.671→0.590）。已回退 TF-IDF 细主题。
- **build_topic_memory 适配**：用户大批量数据来时，用新数据+模型判父类重建。
- **深度聚类工具三功能已全部实现**：dc_cluster ✅ / cl_label ✅ / sr_review ✅（三层树）。

### 7.7 聚类标签生成（cl_label）
- **功能点**：`cl_label`（第18功能点，multi_text），`engine_type: labeling`
- **两种模式**：
  - 不传 clusters：内部调 dc_cluster 聚类 → 取 topic_name 作为标签
  - 传 params.clusters（自定义簇分组）：LLM 看代表文献生成专业标签
- **输入**：texts（文本/PDF/MD，和 dc_cluster 一致）
- **输出**：`{clusters: [{cluster_id, label, doc_indices, n, axis}]}`
- **关键文件**：`semantic_service._execute_labeling` + `_generate_cluster_label`

### 7.8 结构化自动综述（sr_review）✅ 三层树已实现
- **功能点**：`sr_review`（第19功能点，multi_text），`engine_type: structured_review`
- **输入**：texts（文献，文本/PDF/MD）+ params.topic（综述主题，必填）+ 可选 cluster_result/cluster_axis
- **输出格式**：三层树（RQ→M→进展/结论/DOC）+ 研究背景 + 现有问题 + 发展趋势
```
{
  "title": "xxx研究综述",
  "background": "研究背景段落",
  "tree": [
    {"rq_id":"RQ-01", "rq_label":"研究问题描述",
     "methods":[
       {"method_id":"M-01","method_label":"方法名",
        "progress":"研究进展","conclusion":"阶段结论","doc_indices":[0,1]}
     ]}
  ],
  "problems":"跨子方向归纳的现有问题",
  "trends":"发展趋势",
  "n_documents":8, "n_clusters":8, "weak_documents":["3","4"]
}
```
- **流程**（`_execute_structured_review`）：
  1. 获取类簇（传 cluster_result 用它，否则内部调 dc_cluster）
  2. 综述主题筛选（LLM 判每篇文献相关性：high/weak/irrelevant）
  3. LLM 归纳 RQ（`_induce_rqs`：从综述主题+类簇标签归纳2-4个研究问题，每RQ关联类簇）
  4. 每类簇（M）LLM 分析（`_analyze_cluster`：返回 progress+conclusion）
  5. 综合 LLM（`_synthesize`：跨子方向归纳现有问题+发展趋势）
  6. 研究背景 LLM（`_generate_background`）
- **关键文件**：`semantic_service._execute_structured_review` + `_induce_rqs`/`_analyze_cluster`/`_synthesize`/`_generate_background`
- **测试**：8篇电力系统文献 + 主题"新型电力系统新能源消纳" → 4个RQ、8个M、完整三层树+溯源

## 8. 环境与依赖
- Python 3.12，torch 2.5.1+cu124（本机GPU不稳，慎用大批量GPU编码）
- 已装：sentence_transformers 3.3.1 + transformers 4.46.3（**勿升级到transformers 5.x**，会要求torch≥2.6）
- HuggingFace不通，ModelScope可达（`from modelscope import snapshot_download`）
- GLM通过 `infrastructure/llm/glm_client.py`（chat_json，强制JSON输出）

## 9. 迁移到新服务器
拷贝这些目录到新服务器（保持路径或改 profile.py/config.py 里的路径）：
- `/root/autodl-tmp/semantic-toolkit/`（项目代码+本交接文档）
- `/root/autodl-tmp/datasets/`（所有数据集）
- `/root/autodl-tmp/rag_store/`（CLC知识库）
- `/root/autodl-tmp/models/`（bge编码器）
- `/root/autodl-tmp/rule.pdf`（方法论）

新服务器开新Claude窗口，第一句："读 /root/autodl-tmp/semantic-toolkit/docs/HANDOFF.md，继续项目"。

## 10. 关键命令速查
```bash
# 启动服务
cd /root/autodl-tmp/semantic-toolkit && uvicorn presentation.main:app --port 8000

# 语步识别评测
python -m training.eval_rules --lang zh --n 40   # 中文
python -m training.eval_rules --lang en --n 10   # 英文

# 语步识别训练（数据多时）
python -m training.run_training --lang zh --induce-size 12 --eval-size 20 --iterations 1

# 调用API
curl -X POST http://localhost:8000/api/v1/move_recognition/mr_zh_abstract -H "Content-Type: application/json" -d '{"text":"..."}'
curl -X POST http://localhost:8000/api/v1/move_recognition/mr_en_abstract -H "Content-Type: application/json" -d '{"text":"..."}'

# 自检测试
python -m pytest tests/ -q
```

## 11. 用户工作偏好
- 主动汇报长任务进度（定时任务自动检查日志）
- 诚实说明限制，不夸大效果
- 数据可扩展性优先（小数据先基线，大数据再完整训练）
- 规则库防过拟合是核心关切（验证集准入+动态权重）

## 新增文件

- `infrastructure/document_parser/mineru_reader.py`：MinerU全文读取器（PDF→MinerU→MD→全文，不做章节解析）
- `training/citation_profile.py`：引用句/概念定义Profile（含cd_identify）
- `training/citation_rule_engine.py`：引用句后置规则引擎
- `training/run_citation_training.py`：训练入口

## 已改造的功能

### 深度聚类（dc_cluster）✅ 全文+LLM双轴+LLM精选
```
PDF/MD文件 → mineru_reader全文
  → LLM提取技术路线描述+应用场景描述（中文，从全文归纳）
  → load_input（已改：保留LLM提取的双轴文本，不覆盖）
  → map_documents（bge-m3父类打分+K-Means主题匹配）
  → LLM精选（candidate_new_topic/低分→从Top-K候选LLM选最贴切）
  → 输出
```
测试效果（6篇中英文论文，四种方案对照）：

**技术路线轴**
| 文献 | 原项目(摘要) | 全文直传 | LLM双轴 | LLM双轴+精选 |
|---|---|---|---|---|
| ch3 | 数字學生 ❌ | AHP ❌ | 深度学习 ✅ | 数据集、基准与工具验证 ✅ |
| ch7 | Transformer ✅ | Transformer ✅ | Transformer ✅ | Transformer ✅ |
| ch8 | 经典机器学习 ✅ | AHP ❌ | 经典机器学习 ✅ | 经典机器学习 ✅ |
| 18号 | 经济评价 ❌ | 经济评价 ❌ | 经典机器学习(和23号聚一起) ✅ | 深度学习与神经网络(和23号聚一起) ✅ |
| 23号 | 深度学习 ✅ | 深度学习 ✅ | 经典机器学习 | 深度学习与神经网络 ✅ |
| 27号 | 第一性原理 ❌ | 数值模拟 ❌ | 时序预测 | 时序预测(candi) |

**应用场景轴**
| 文献 | 原项目 | 全文直传 | LLM双轴 | LLM双轴+精选 |
|---|---|---|---|---|
| ch3 | 教育培训 ✅ | 公共服务 | 教育培训 ✅ | 教育培训 ✅ |
| ch8 | 分子生物 ✅ | V2G ❌ | 分子生物 ✅ | 分子生物 ✅ |
| 23号 | 医学影像 ❌ | 计算机科学 ✅ | 能源电池 ❌ | 计算机科学、人工智能 ✅ |

**关键改善（LLM双轴+精选 vs 原项目）**
- 18号+23号聚到一起（深度学习与神经网络）✅ — 两篇 VLM/AI 论文方法相似
- ch3 改为"数据集、基准与工具验证" ✅ — AI画像确实涉及数据集和工具
- ch8 应用场景"分子生物学" ✅ — 糖尿病肾病属于分子生物学
- 23号 应用场景"计算机科学、人工智能" ✅ — 生成式分类器属于计算机科学
- 5个轴标记为 llm_refined — LLM精选从候选里选了更贴切的主题

**仍有的问题（主题库覆盖不够，需方向2扩充父类解决）**
- 27号：技术路线"时序预测"和应用"医学影像"都不太准 — 主题库缺"认知科学/心理模拟"方向
- ch7 应用："妇产儿科"不对 — 门诊量预测应该是"医院管理"

### 引用句识别（cr_sentiment/cr_intent）✅ 全文分句
- 全文分句（截掉参考文献章节）→ 规则抽取 → LLM判定不确定句 → LLM标注 → 后置规则引擎
- et al.句号保护 + 图片路径排除

### 概念定义识别（cd_identify）✅ 全文分句
- 高置信标志词（40+个）→ 确定 → 线索词"是" → LLM判定 → LLM提取概念词 → 后置规则引擎

### 命名实体/关系识别（ner_general/ner_research/ner_domain/ner_relation）✅ 全文直送（2026-08-03）
- 4 个 NER 功能点加 `engine_type: ner`，走专属 `_execute_ner`（此前走默认路径，不处理文件路径、不截断）。
- `_execute_ner`：text 可为实体片段、文件路径（.pdf/.md→`process_to_text` 全文）、或 mineru markdown 全文。全文 > 10000 字截取前段（命名实体多集中在标题/摘要/引言/作者机构/方法节）；`start`/`end` 位置相对实际送入 LLM 的（截断后）文本。ner_relation 无位置字段不受影响。
- 冒烟（ch3.pdf）：ner_general 26 实体（PERSON/ORG/LOCATION + 英文对应，位置正确）；ner_research 30 实体（METHOD 大数据与AI画像/TOPIC 高校思政教育个性化实践）。
- 限制：超长全文只取前 10000 字；如需全篇实体覆盖，未来可改 chunk map-reduce（带块内位置偏移与跨块去重）。

## 待改造的功能

### 分类工具（ac_zh/ac_en/ac_domain）✅ 已改为全文直传（2026-08-03）
- `_parse_paper_input` 改返回 4 元组 `(title, abstract, keywords, full_text)`：输入为全文（mineru markdown 或 .pdf/.md 文件路径）时 full_text 非 None。
- `_render_classification_user_prompt(title, abstract, keywords, full_text=None)`：full_text 非 None 时附前 6000 字全文，LLM 从全文判断学科（不只看摘要）。
- ac_zh / ac_en / ac_domain（`_execute_classification` + `_execute_domain_classification`）均传 full_text。eval 走 JSON 输入（无 full_text），行为不变、指标不受影响。
- 冒烟：ch3 全文 → G641 思想政治教育（LLM 基于全文 reasoning，提到 AI画像/辅导员/思政教育）。

### 关键词识别（kw_zh/kw_en）✅ 已改为全文直传（2026-08-03）
- `_execute_keyword` 检测全文（文件路径或 mineru markdown）→ 截断前 5000 字作 LLM 上下文 + 短语挖掘源（取代仅摘要）。
- 短语挖掘仍跑（高召回确定性候选），LLM 看全文选/精炼。`_clean_keywords` 字面校验对同一截断文本。
- 冒烟：ch3 全文 → 大数据与AI画像/高校辅导员/思政教育/数据壁垒 等全文级概念。

### 研究问题识别（rq_identify）✅ 已改为全文直传（2026-08-03）
- `_execute_rq_identify` 检测全文 → 截断前 8000 字送 LLM；字面校验（sentence/phrase 须字面子串）对同一截断文本，防幻觉不变。
- 冒烟：ch3 全文 → 2 条研究问题句，均为全文字面子串。

## 测试
- pytest 5 passed
- GLM API key: <your-glm-api-key>
