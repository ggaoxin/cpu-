"""当前 Vue 使用的 19 个稳定接口，以及任务、历史和集合查询接口。"""
from __future__ import annotations

import asyncio
import json
import hashlib
import re
import csv
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

import logging

logger = logging.getLogger(__name__)


# NER 工具集合（头部行补丁适用范围）：头部元数据行是三类 NER 的实体富集区
NER_TOOLS = {"general-ner", "research-ner", "domain-ner"}

# 头部元数据块标记：基金项目/作者简介/收稿日期等（NER 实体富集区）；
# 编号单位条目（"2. 南京工业大学，江苏 南京 211816"）无前缀标记，单列一套
_NER_HEADER_MARK = re.compile(
    r"(?m)^(?:\*{0,2})(基金项目|基金资助|资助项目|课题来源|作者简介|通信作者|通讯作者|"
    r"收稿日期|网络首发日期?|作者单位|单位地址|依托单位|项目批准号)\s*[:：]")
_NER_AFFILIATION_MARK = re.compile(
    r"(?m)^\s*\(?\d{1,2}[.、）)]\s*[一-鿿A-Za-z][^，。\n]{2,28}"
    r"(大学|学院|医院|研究所|研究院|实验室|中心|公司|集团)")


def _patch_ner_header_lines(md: str, content: bytes, name: str) -> str:
    """NER 头部行补丁：把 MinerU 丢失的头部元数据块从 PyMuPDF 补进文本。

    MinerU 对个别 PDF 会静默丢基金项目/作者简介等头部行（AI画像案例：md 里
    "基金项目""西南交通大学" 整体消失，PyMuPDF 完整）。取 PyMuPDF 探针文本中
    以头部标记开头的块（至下一标记或段标），md 归一化后不含其前 20 字的块
    追加到 md 末尾。探针失败/无缺失原样返回。
    """
    if not md:
        return md
    try:
        from infrastructure.document_parser.upload_reader import extract_bytes as _eb
        py = _eb(content, name, light=True) or ""
    except Exception:  # noqa: BLE001
        return md
    if not py:
        return md
    md_norm = re.sub(r"\s+", "", md)
    missing = []
    marks = list(_NER_HEADER_MARK.finditer(py)) + list(_NER_AFFILIATION_MARK.finditer(py))
    for m in marks:
        start = m.start()
        end = min(start + 400, len(py))
        m2 = _NER_HEADER_MARK.search(py, m.end())
        if m2 and m2.start() < end:
            end = m2.start()
        stop = re.search(r"\n\s{0,6}(摘\s*要|关键词|Abstract|ABSTRACT|中图分类号)", py[start:end])
        if stop:
            end = start + stop.start()
        block = py[start:end].strip()
        if len(block) < 8:
            continue
        key = re.sub(r"\s+", "", block)[:20]
        if key in md_norm:
            continue
        if any(re.sub(r"\s+", "", b)[:20] == key for b in missing):
            continue
        missing.append(block)
    if not missing:
        return md
    logger.warning("NER 头部行补丁（%s）：MinerU 丢失 %d 个元数据块，已从 PyMuPDF 补入",
                   name, len(missing))
    # 前置到文首：追加在文末时模型当尾部噪声跳过（AI画像实测），头部元数据
    # 自然位置在开头，模型按首页头语境正常抽取
    return "\n".join(missing) + "\n\n" + md


def _count_body_citation_markers(text: str) -> int:
    """正文区引用标记计数（引用工具解析门禁探针口径）。

    先截参考文献章节（对齐引擎 ref_re），再数 [n]/［n］方括号组，排除数学噪声：
    - 含 0 的组（区间 [0,1]）不算
    - 乱序多值组（数组下标 [2,8,1]）不算——引用编号惯例递增
    - 单值年份（[2024]）计入——年份引用风格（35.pdf "Shumailov et al. [2024]"）
    - 多值组内含 >399 的编号不算（非引用编号）
    """
    m = re.search(r"(?:^|\n)\s*#{0,3}\s*(参考文献|References|REFERENCES)\s*[：:．.\s]*(?:\n|$)", text)
    if m:
        text = text[:m.start()]
    n = 0
    for g in re.finditer(r"[［\[]\s*(\d+(?:\s*[-–,，]\s*\d+)*)\s*[\]］]", text):
        try:
            nums = [int(x) for x in re.split(r"[-–,，]", g.group(1))]
        except ValueError:
            continue
        if any(v == 0 for v in nums):
            continue
        if len(nums) > 1 and nums != sorted(nums):
            continue
        if len(nums) == 1 and 1900 <= nums[0] <= 2099:
            n += 1
            continue
        if any(v > 399 for v in nums):
            continue
        n += 1
    return n

from application.service.tool_integration_service import ToolIntegrationService
from application.service.result_normalizer import public_viz_result
from application.service.export_service import export_service
from application.service.resource_service import resource_service
from application.service.result_governance_service import result_governance_service
from application.service.result_normalizer import _clean_cluster_term
from application.service.upstream_record_service import upstream_record_service
from config.settings import settings
from config.tool_contracts import CONTRACTS
from config.vue_contracts import get_vue_contract
from infrastructure.database.task_repository import task_repository
from infrastructure.document_parser.upload_reader import extract_uploads, save_uploads_to_temp
from presentation.api.base_controller import get_semantic_service

router = APIRouter(tags=["Vue 集成接口"])
_integration_service = ToolIntegrationService(get_semantic_service(), task_repository)

# 这类多文件工具的瓶颈是 _parse_papers_concurrent（并发 MinerU + dual_view LLM 抽取）。
# 上传时跳过 extract_uploads 的串行预解析，改为落盘路径透传，让并发优化真正生效。
# 路径透传工具：上传 PDF 落盘 path 不预解析，延迟到 _semantic_request 逐篇解析，
# 让 mineru(GPU,PageBudgetPool 控制) 与 LLM 处理(GLM) 流水线并行（不同资源）。
# 排除 collection_tool（走 _semantic_request collection 分支自有 path 处理）和
# ABSTRACT_MOVE（走 _extract_abstract_only 已 pool 并发）。
PATH_PASSTHROUGH_TOOLS = {
    "deep-cluster",  # collection_tool：端点落盘后走 collection 分支
    "en-keyword", "zh-keyword",
    "fund-move",
    "zh-classify", "en-classify", "domain-classify",
    "rq-detect",
    "citation-sentiment", "citation-intent",
    "definition-detect",
    "general-ner", "research-ner", "domain-ner",
    "relation-extract",
}

# 摘要语步识别工具：上传 PDF 后只送纯摘要文本给引擎，过滤掉标题/关键词/全文。
# 用四层融合解析（MinerU→pdfplumber→正则→LLM 校验）提取摘要，而非 extract_uploads 的全文。
ABSTRACT_MOVE_TOOLS = {"zh-abstract-move", "en-abstract-move"}
# PyMuPDF 专用工具（2026-09-09 用户指定）：基金语步/定义句/深度聚类/结构化综述
# 走 PyMuPDF light（毫秒级全文，含双栏分栏+断词重连），其余工具全走 MinerU
# 基金语步改回 MinerU（2026-09-09 用户确认：需要 ## 章节标题锚定研究目标/
# 技术方案/预期成果，MinerU md 的结构化标题远优于 PyMuPDF 的正则猜测）
PYMUPDF_TOOLS = {"definition-detect", "deep-cluster", "structured-review"}
# 摘要语步只需摘要文本（期刊首页、学位论文摘要最迟到第7页），限定 mineru 只解析
# 前 8 页（0-indexed 闭区间 end_page_id=7），vllm 计算量随页数大降而 abstract 仍完整
# （含无标题摘要——靠末端 LLM 从前若干页 md 语义提取，实测 38.pdf 限8页=全文1301字）。
ABSTRACT_MOVE_END_PAGE = 7

# 双栏预印本/会议论文首页噪声清洗：adaptive_regions_main 候选常把页面顶部 arXiv 元数据行
# 或底部 ACM/版权声明块并进摘要（blocks_yx 跨栏错拼评分虚高反而被选为 primary）。
_ARXIV_LINE = re.compile(
    r'arXiv:\d{4}\.\d{4,5}(?:v\d+)?\s*\[[\w\.\-/ ]*\]\s*\d{1,2}\s+[A-Z][a-z]{2}\s*\d{4}\s*'
)
_COPYRIGHT_BLOCK = re.compile(
    r'(?:∗Corresponding author|Permission to make digital or hard copies)'
    r'.*?https?://doi\.org/\S+\s*',
    re.DOTALL,
)
# 作者列表混入：作者序号上标紧跟姓名（如 "Max Kaufmann1, David Lindner1"），
# adaptive/blocks 候选把首页作者块并到摘要前，连续 >=2 个即为作者列表而非摘要
_AUTHOR_LIST = re.compile(r'[A-Z][a-z]+ [A-Z][a-z]+\d')


def _clean_abstract_noise(text: str) -> str:
    """清洗候选摘要里的非摘要噪声：开头 arXiv 元数据行、中间 ACM/版权声明块。
    正常摘要不含这些，清洗后不变；双栏预印本/ACM 会议论文 adaptive_regions_main
    候选清洗后即为纯摘要。"""
    text = _ARXIV_LINE.sub('', text, count=1)
    text = _COPYRIGHT_BLOCK.sub('', text)
    return text.strip()


def _is_pure_abstract(text: str) -> bool:
    """摘要纯净度检测：不含 arXiv 元数据、ACM/版权声明、开头引用 bracket、
    作者列表。primary 高置信但混入这些噪声时（双栏预印本 blocks_yx 跨栏错拼
    评分虚高）判定不纯，转而遍历候选找清洗后纯净的（adaptive_regions_main 常是正确的）。"""
    if _ARXIV_LINE.search(text):
        return False
    if re.search(r'Permission to make digital|ACM ISBN|©\s*\d{4}|https?://doi\.org/', text):
        return False
    if re.search(r'\[\d+[,\d\s]*\]', text[:80]):  # 开头 [13,47] 正文引用混入
        return False
    if len(_AUTHOR_LIST.findall(text[:120])) >= 2:  # 作者列表（姓名+序号上标）混入
        return False
    return True


def _glm_abstract_callable():
    """把 GLMClient 包成 paper_abstract_extractor 要求的 Callable[[str], str]：
    输入 build_llm_prompt 生成的完整提示词，输出 JSON 字符串。仅在低置信/候选歧义时触发，
    高置信正则结果（>=regex_accept_confidence）不调 GLM。"""
    from infrastructure.llm.glm_client import glm_client

    def _call(prompt: str) -> str:
        return glm_client.chat(
            system_prompt="严格按用户指令输出单个 JSON 对象，不要 Markdown 包装。",
            user_prompt=prompt,
            response_json=True,
            timeout=40.0,
        )

    return _call


async def _abstract_text_from_plain(tmp_path: str, filename: str) -> tuple[str, str]:
    """".txt/.docx/.md 等纯文本格式的摘要提取:整文即候选文本。

    短文（≤2000 字）通常就是用户准备的摘要文本，整文直接作摘要；
    长文（全文）用 DocumentParser.parse_text 按中文论文结构（标题/摘要：/关键词：）
    提取标题与摘要，未命中时截前 2000 字兜底。
    """
    from infrastructure.document_parser.upload_reader import extract_bytes
    try:
        text = extract_bytes(Path(tmp_path).read_bytes(), filename).strip()
    except ValueError:
        raise
    if not text:
        return "", ""
    if len(text) <= 2000:
        return text, ""
    try:
        from infrastructure.document_parser.document_parser import DocumentParser
        parsed = DocumentParser().parse_text(text)
        abstract = (parsed.get("abstract") or "").strip()
        title = (parsed.get("title") or "").strip()
        return (abstract or text[:2000]), title
    except Exception:  # noqa: BLE001
        return text[:2000], ""


def _extract_abstract_via_pymupdf(tmp_path: str) -> tuple[str, str]:
    """PyMuPDF 文本层 + DocumentParser 正则提取摘要（毫秒级）。

    paper_abstract_extractor 缺失时的轻量回退：单栏文本层 PDF 直接抽前 8000 字
    跑摘要/标题正则，避免全部掉进 mineru（~0.6s/页）。返回 (abstract, title)；
    文本层缺失（扫描件）/双栏（需版面感知，包未装）/正则未命中 → 返 ("", "")，
    由上层回退 mineru 结构化解析保质量。
    """
    from infrastructure.document_parser.document_parser import DocumentParser
    from infrastructure.document_parser.upload_reader import _pymupdf_abstract
    try:
        with open(tmp_path, "rb") as f:
            content = f.read()
        text = _pymupdf_abstract(content)
        if not text:
            return "", ""
        doc = DocumentParser().parse_text(text)
        abstract = _clean_abstract_noise(doc.get("abstract") or "")
        title = re.sub(r"<[^>]+>", "", doc.get("title") or "").strip()
        if not abstract or len(abstract) < 50 or not _is_pure_abstract(abstract):
            return "", ""
        return abstract, title
    except Exception:  # noqa: BLE001
        return "", ""


def _extract_abstract_via_rules(tmp_path: str) -> str:
    """paper_abstract_extractor 规则优先摘要提取（毫秒级正则，低置信/歧义才触发 LLM）。

    v2.0.0 多种阅读顺序（pymupdf_sort/blocks_yx/adaptive_regions_main 自适应递归 XY-cut）
    跑同一套起点/终止规则 + 评分，保留最高分候选；结构式摘要内部标签保护
    （Background/Methods/Results 不误截断）；中英双摘要分别保留；preferred_language=None
    按最高置信选 primary（中文论文 primary 中文摘要、英文论文 primary 英文摘要，
    与 zh/en-abstract-move 输入语种自然匹配）。

    逐级扩大页数 3→5→7：期刊论文摘要在前 1-2 页（3 页即命中，极速）；学位论文摘要在第
    6-7 页（封面/版权/目录在前），前 3 页没覆盖到就自动扩到 5、7 页继续跑规则，不回退
    mineru。扫描件 needs_ocr=True 立即返空回退 mineru（扩页无用，需 OCR）。基金/项目报告
    无摘要结构，各级均 success=False → 返空回退。success + 非 needs_ocr + confidence>=0.74
    才采用（0.74=llm_trigger，原 0.78 偏保守挡掉 conf 0.74-0.77 的正确摘要）。

    纯净度后处理 + LLM/layout 兜底：conf<0.78（llm_trigger）触发包内 LLM 兜底选候选
    ——GLM 能区分机构列表/作者/片段 vs 真摘要（4/41 避开「1Meta,2Harvard」机构、
    HYDRA 避开全大写作者、47 避开 (Author,year) 引用片段），选后 conf 0.82-0.88、
    method 含 llm 时直接用 LLM 选的（is_pure 兜底防误选）。method=layout_unlabeled
    是 v2 无标题摘要 fallback（4/41/47 无 Abstract 标记命中 conf0.85+，v1 需 LLM 兜底
    v2 原生命中），同样直接用。正则结果（method=regex，conf>=0.78 不触发 LLM）遍历
    debug_candidates 清洗后优先 adaptive_regions_main（防 blocks_yx 跨栏乱序无标记，
    21 标题尾排到摘要开头看似纯净实为乱序；adaptive 仅 conf>=0.85 优先，避免误伤单栏
    pymupdf_sort 高置信如 20），无则置信最高。采用门槛 0.74（LLM 兜底 0.82+ 与正则
    0.74-0.78 如 45 均采用；<0.74 或 success=False 如 38 无 Abstract 标记 → 回退
    mineru）。正常高置信论文不过 LLM，保持极速。
    """
    try:
        from paper_abstract_extractor import extract_abstract_from_pdf, ExtractorConfig
    except ImportError:
        # 私有包未随源码分发（仅原部署机安装）。按设计降级：返空 → 上层回退 mineru。
        return ""

    llm = _glm_abstract_callable()
    for pages in (3, 5, 7):
        cfg = ExtractorConfig(
            max_pages=pages,
            regex_accept_confidence=0.78,
            llm_trigger_confidence=0.78,  # conf<0.78 触发 LLM 兜底选候选（GLM 区分机构/作者/片段 vs 真摘要）
            enable_layout_variants=True,
            enable_unlabeled_fallback=True,
            return_debug_candidates=True,
        )
        try:
            result = extract_abstract_from_pdf(tmp_path, cfg, llm_callable=llm)
        except Exception:  # 包异常不应破坏 abstract-move 主链路，回退 mineru
            return ""
        if result.source_quality.get("needs_ocr"):
            return ""  # 扫描件，扩页无用，回退 mineru OCR
        if not (result.success and result.abstract and result.confidence >= 0.74):
            continue  # 未命中，扩页继续
        # LLM/layout 兜底选的候选（method 含 llm 或 layout）更可信：GLM 已区分
        # 机构列表/作者/片段 vs 真摘要（conf<0.78 触发，选后 conf 0.82-0.88）；
        # layout_unlabeled 是 v2 无标题摘要 fallback（4/41/47 无 Abstract 标记命中
        # conf0.85+，v1 需 LLM 兜底 v2 原生命中）。两者直接用 + is_pure 兜底防误选
        method = getattr(result, "method", "") or ""
        primary_text = _clean_abstract_noise(result.abstract or "")
        if ("llm" in method or "layout" in method) and primary_text and _is_pure_abstract(primary_text):
            return primary_text
        # 正则结果（method=regex，conf>=0.78 不触发 LLM）或 LLM/layout 选的不纯：
        # 遍历候选清洗后优先 adaptive_regions_main（防 blocks_yx 跨栏乱序无标记，如 21
        # 标题尾排到摘要开头看似纯净实为乱序），无则置信最高
        # 收集所有候选，清洗+纯净度检测（去重，同文本只留一个）
        candidates = getattr(result, "debug_candidates", None) or []
        pure = []  # [(variant, cleaned, conf)]
        seen = set()
        for cand in candidates:
            text = getattr(cand, "text", "") or ""
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned = _clean_abstract_noise(text)
            if cleaned and len(cleaned) >= 50 and _is_pure_abstract(cleaned):
                pure.append((getattr(cand, "variant", ""), cleaned, getattr(cand, "confidence", 0.0) or 0.0))
        if not pure:
            continue  # 无纯净候选，扩页继续
        # 优先 adaptive_regions_main（v2 自适应递归 XY-cut，双栏分栏重排最可靠）：
        # 单栏退化为正确全文序、分栏摘要正确重排；blocks_yx 对双栏易跨栏乱序且无噪声
        # 标记（21 标题尾排到摘要开头，看似纯净实为乱序，conf 虚高压过正确的
        # adaptive），故 adaptive 优先于按 conf 选；24/28 等 pymupdf_sort 抽到正文片段
        # 也因优先 adaptive 跳过。仅 adaptive conf>=0.85 才优先，避免低置信 adaptive
        # 误伤单栏 pymupdf_sort 高置信正确（如 20 conf0.99）
        for v, t, _conf in pure:
            if v == "adaptive_regions_main" and _conf >= 0.85:
                return t
        # 无高置信 adaptive 候选（单栏论文常只生成 pymupdf_sort）→ 置信最高
        pure.sort(key=lambda x: -x[2])
        return pure[0][1]
    return ""


async def _abstract_text(processor, tmp_path: str, content: bytes | None = None, filename: str = "") -> tuple[str, str]:
    """摘要文本+标题提取。light 模式优先 paper_abstract_extractor（规则优先+评分+
    LLM 兜底，毫秒级正则，无 :8899）；扫描件/封面无摘要/低置信时回退 mineru
    process_pdf 保质量。full 模式直接走 mineru。返回 (abstract, title)。

    非 PDF 格式（.txt/.docx/.md 等）不走 PDF 管线（实测 pdfplumber 直接崩溃）：
    先 extract_bytes 抽纯文本，短文（≤2000 字，通常就是摘要本身）整文作摘要，
    长文（全文粘贴）用 DocumentParser.parse_text 做摘要/标题结构化提取。
    paper_abstract_extractor 只提 abstract 不提 title；light 命中时 title 留空，
    前端按文件名展示规则（record.file_name 优先）显示文件名。content 参数保留兼容
    但不再使用（paper_abstract_extractor 从 tmp_path 路径读 PDF）。"""
    abstract = ""
    title = ""
    suffix = Path(filename or "").suffix.lower()
    if suffix and suffix != ".pdf":
        return await _abstract_text_from_plain(tmp_path, filename)
    if settings.PDF_EXTRACT_MODE == "light":
        abstract = await asyncio.to_thread(_extract_abstract_via_rules, tmp_path)
        if not abstract:
            # paper_abstract_extractor 缺失/未命中 → PyMuPDF 文本层 + 正则（毫秒级）
            abstract, title = await asyncio.to_thread(_extract_abstract_via_pymupdf, tmp_path)
    if not abstract:  # full / light 抽空（扫描/封面无摘要/低置信）→ mineru 兜底
        doc = await asyncio.to_thread(processor.process_pdf, tmp_path, end_page_id=ABSTRACT_MOVE_END_PAGE)
        abstract = (doc.get("abstract") or "").strip() or (doc.get("full_text") or "").strip()
        title = (doc.get("title") or "").strip()
    return abstract, title


async def _extract_abstract_only(
    uploads: List[StarletteUploadFile],
    max_size_mb: int,
) -> List[Dict[str, str]]:
    """摘要语步识别专用提取：PDF → 四层融合解析 → 只取纯摘要（页数预算并发）。

    与 ``extract_uploads`` 抽全文不同，这里用 ``DocumentProcessor.process_pdf``
    做结构化解析（MinerU content_list + pdfplumber 兜底 + 正则 + LLM 校验），
    只把摘要文本塞进 ``text``，标题/关键词/正文全部过滤——符合摘要语步
    只需标注摘要内句子的语义。摘要缺失时回退全文，避免空输入。

    多文件并发受 PageBudgetPool 调度（小文件高并发、大文件串行）。
    """
    import os
    import tempfile
    from infrastructure.document_parser.document_processor import get_document_processor
    from infrastructure.document_parser.concurrency_pool import get_page_budget_pool
    from infrastructure.document_parser.mineru_api_client import _count_pages

    limit = (max_size_mb or settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024
    processor = get_document_processor()
    uploads = list(uploads)

    if len(uploads) <= 1:
        # 单文件直接处理，无需并发调度开销
        results: List[Dict[str, str]] = []
        for upload in uploads:
            content = await upload.read(limit + 1)
            if len(content) > limit:
                raise ValueError(f"文件 {upload.filename} 超过 {max_size_mb or settings.MAX_UPLOAD_SIZE_MB}MB 限制")
            suffix = Path(upload.filename or "upload.pdf").suffix or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                abstract, title = await _abstract_text(processor, tmp_path, content, upload.filename or "")
                results.append({
                    "file_name": upload.filename or "upload.pdf",
                    "media_type": upload.content_type or "application/pdf",
                    "text": abstract,
                    # 回传解析出的真实标题，供前端弹窗题名列显示（无标题时为空串，
                    # 由 _result_payload 兜底成文件名、再由渲染层兜底成摘要前缀）。
                    "title": title,
                })
            finally:
                try: os.unlink(tmp_path)
                except OSError: pass
        return results

    # 1. 并发读所有文件 bytes + 页数 + 写临时文件
    async def prepare_one(upload: StarletteUploadFile):
        content = await upload.read(limit + 1)
        if len(content) > limit:
            raise ValueError(f"文件 {upload.filename} 超过 {max_size_mb or settings.MAX_UPLOAD_SIZE_MB}MB 限制")
        suffix = Path(upload.filename or "upload.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        return upload, tmp_path, content, _count_pages(content)

    items = await asyncio.gather(*[prepare_one(u) for u in uploads])

    # 2. 页数预算并发 process_pdf
    pool = get_page_budget_pool()

    async def process_one(upload: StarletteUploadFile, tmp_path: str, content: bytes, pages: int) -> Dict[str, str]:
        await asyncio.to_thread(pool.acquire, pages)
        try:
            abstract, title = await _abstract_text(processor, tmp_path, content, upload.filename or "")
            return {
                "file_name": upload.filename or "upload.pdf",
                "media_type": upload.content_type or "application/pdf",
                "text": abstract,
                # 回传解析出的真实标题（与单文件分支一致），供弹窗题名列显示。
                "title": title,
            }
        finally:
            try: os.unlink(tmp_path)
            except OSError: pass
            await asyncio.to_thread(pool.release, pages)

    return await asyncio.gather(*[process_one(*i) for i in items])


async def _parse_metadata_upload(upload: StarletteUploadFile) -> Any:
    """Parse user-supplied document/citation metadata into real rows."""
    content = await upload.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=422, detail=f"元数据文件不能超过 {settings.MAX_UPLOAD_SIZE_MB} MB")
    name = upload.filename or "metadata.json"
    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".xlsx":
            import openpyxl
            workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.active
            values = list(sheet.iter_rows(values_only=True))
            if not values:
                raise ValueError("元数据工作表为空")
            headers = [str(value or "").strip() for value in values[0]]
            rows = [
                {headers[index]: value for index, value in enumerate(row) if index < len(headers) and headers[index]}
                for row in values[1:] if any(value not in (None, "") for value in row)
            ]
            return rows
        text = next((content.decode(encoding) for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk")
                     if _can_decode(content, encoding)), "")
        if suffix == ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        if suffix == ".csv":
            return list(csv.DictReader(io.StringIO(text)))
        if suffix == ".json":
            value = json.loads(text)
            if isinstance(value, dict):
                for key in ("documents", "records", "data", "items"):
                    if isinstance(value.get(key), list):
                        return value[key]
            return value
        return {"source": "upload", "file_name": name, "text_content": text}
    except (ValueError, json.JSONDecodeError, ImportError) as exc:
        raise HTTPException(status_code=422, detail=f"无法解析元数据文件 {name}：{exc}") from exc


def _can_decode(content: bytes, encoding: str) -> bool:
    try:
        content.decode(encoding)
        return True
    except UnicodeDecodeError:
        return False


async def _store_uploaded_resource(
    field: str,
    upload: StarletteUploadFile,
    service: ToolIntegrationService,
) -> Dict[str, Any]:
    content = await upload.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=422, detail=f"资源文件不能超过 {settings.MAX_UPLOAD_SIZE_MB} MB")
    original_name = Path(upload.filename or "resource.bin").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name) or "resource.bin"
    digest = hashlib.sha256(content).hexdigest()
    directory = settings.PROJECT_ROOT / "runtime" / "semantic_resources"
    directory.mkdir(parents=True, exist_ok=True)
    stored_path = directory / f"{digest[:16]}_{safe_name}"
    if not stored_path.exists():
        stored_path.write_bytes(content)
    descriptor: Dict[str, Any] = {
        "source": "upload",
        "file_name": original_name,
        "content_type": upload.content_type,
        "storage_uri": stored_path.as_posix(),
        "content_hash": digest,
    }
    try:
        descriptor["text_content"] = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    from application.service.tool_integration_service import SEMANTIC_RESOURCE_FIELDS
    # deep-cluster 的可选锚点资源(训练样本/人工标注类目)同样支持独立上传入库
    registerable = SEMANTIC_RESOURCE_FIELDS | {"training_samples", "manually_labeled_category_data"}
    if field in registerable:
        meta = {"content_type": upload.content_type, "size_bytes": len(content)}
        record_count = None
        verdict = None
        # ---- 入库前统一结构校验/归一化（公共层，全部工具共用）----
        # 行型资源：确定性归一化 0 条 → LLM 一次性整理（写 _normalized.json 替换
        # storage_uri，原件留档 original_storage_uri）→ 仍失败 422，不入库；
        # 配置型资源：仅 JSON 解码校验。非 .json 后缀直接 422（accept 只过滤选择器）。
        from infrastructure.resources.normalize import (
            CONFIG_FIELD_LABELS, ROW_FIELD_CONFIG, ResourceParseError,
            inspect_user_resource, register_normalized,
        )
        entries: Any = None
        if field in ROW_FIELD_CONFIG:
            if stored_path.suffix.lower() != ".json":
                raise HTTPException(
                    status_code=422,
                    detail="仅支持标准 JSON 文件（CSV、JSONL、TXT 暂不支持）。",
                )
            try:
                entries = inspect_user_resource(stored_path, field=field)
            except ResourceParseError as exc:
                parse_error = str(exc)
                # 必要字段准入探测（2026-09-15 用户定调）：语法可解析但缺必要字段
                # （含中文别名）→ 无重构价值，不调大模型，直接指明缺什么；
                # 语法损坏 / 字段齐备 → 照旧走大模型重构兜底
                from infrastructure.resources.normalize import probe_required_fields
                _probe = probe_required_fields(descriptor.get("text_content") or "", field=field)
                if _probe["parse_ok"] and _probe["must_missing"]:
                    _found = "、".join(_probe["found_keys"][:10]) or "（无任何字段名——纯值结构）"
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"资源缺少必要字段，无法自动整理：{ROW_FIELD_CONFIG.get(field, {}).get('label') or field} "
                            f"需要每行包含 {'；'.join(_probe['must_missing'])}。"
                            f"文件中检测到的字段：{_found}。"
                            f"请补充必要字段（标准格式：{ROW_FIELD_CONFIG.get(field, {}).get('expect')}）后重新上传。"
                        ),
                    ) from exc
                if settings.RESOURCE_LLM_NORMALIZE_ENABLED and isinstance(descriptor.get("text_content"), str):
                    from infrastructure.resources.glm_salvage import maybe_llm_normalize
                    conv_path = directory / f"{digest[:16]}_{Path(safe_name).stem}_normalized.json"
                    salvaged = None
                    # 预检（/semantic-resources/validate）阶段已生成的大模型整理结果
                    # 直接复用——同内容指纹不重复调 LLM（选文件时整理过，提交秒级）
                    if conv_path.is_file():
                        try:
                            _reused = json.loads(conv_path.read_text(encoding="utf-8"))
                            if isinstance(_reused, list) and _reused:
                                salvaged = _reused
                        except (json.JSONDecodeError, OSError):
                            pass
                    note = ""
                    if salvaged is None:
                        salvaged, note = maybe_llm_normalize(
                            descriptor["text_content"], field=field,
                            max_bytes=settings.RESOURCE_LLM_NORMALIZE_MAX_BYTES,
                            max_rows=settings.RESOURCE_LLM_NORMALIZE_MAX_ROWS,
                        )
                    if salvaged is not None:
                        if not conv_path.is_file():
                            conv_path.write_text(
                                json.dumps(salvaged, ensure_ascii=False, indent=2), encoding="utf-8",
                            )
                        descriptor["storage_uri"] = conv_path.as_posix()
                        descriptor["normalized_by"] = "glm"
                        descriptor["normalized_rows"] = len(salvaged)
                        register_normalized(conv_path, salvaged)
                        meta["normalized_by"] = "glm"
                        meta["original_storage_uri"] = stored_path.as_posix()
                        entries = salvaged
                        parse_error = ""
                    elif note in {"oversize", "overrows"}:
                        parse_error = (
                            f"{exc}（文件超出大模型自动整理上限"
                            f"（{settings.RESOURCE_LLM_NORMALIZE_MAX_ROWS} 行 / "
                            f"{settings.RESOURCE_LLM_NORMALIZE_MAX_BYTES // 1024}KB），"
                            f"请按标准格式整理后重新上传）"
                        )
                    else:
                        parse_error = f"{exc}（已尝试大模型自动整理，未能生成有效结构）"
                if parse_error:
                    raise HTTPException(status_code=422, detail=parse_error)
        elif field in CONFIG_FIELD_LABELS and stored_path.suffix.lower() == ".json":
            try:
                json.loads(descriptor.get("text_content") or "")
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=422,
                    detail=f"资源文件 JSON 解析失败（{field}）：{exc}。请上传标准 JSON 文件。",
                ) from exc
        if entries is None:
            try:
                entries = json.loads(content.decode("utf-8-sig"))
            except Exception:  # noqa: BLE001
                entries = None
        # CLC 资源：算 verdict 写 metadata.clc_verdict + record_count（供 _resource_context 分治）
        try:
            if isinstance(entries, list):
                from infrastructure.rag.clc_user_index_service import compute_clc_verdict
                verdict = compute_clc_verdict(entries, len(content))
                meta["clc_verdict"] = verdict
                record_count = verdict["record_count"] if verdict else len(entries)
            elif isinstance(entries, dict) and field in {"training_samples", "manually_labeled_category_data"}:
                record_count = len(entries)
        except Exception:  # noqa: BLE001
            pass
        stored = service.resource_repository.register_semantic_resource(
            settings.DEFAULT_WORKSPACE_ID,
            {
                "resource_key": field,
                "name": original_name,
                # 版本号=内容摘要前 12 位（不带 upload- 标记：source_type 字段已表达
                # 上传来源，前缀会造成资源下拉里出现"名称 · upload-xxxx"冗余标识）
                "version": digest[:12],
                "language": None,
                "status": "current",
                "source_type": "upload",
                # LLM 整理成功时 descriptor["storage_uri"] 已指向 *_normalized.json
                "storage_uri": descriptor["storage_uri"],
                "content_hash": digest,
                "metadata": meta,
                "record_count": record_count,
            },
        )
        descriptor["resource_id"] = stored["id"]
        # 完整分类树 + 超阈值 → 异步建索引（供 for_path 加载替换内置检索）
        if verdict and verdict.get("kind") == "taxonomy_complete" \
                and verdict.get("record_count", 0) > settings.CLC_BUILD_MIN_RECORDS:
            from infrastructure.rag.clc_user_index_service import submit_build
            submit_build(stored)
    return descriptor


def get_integration_service() -> ToolIntegrationService:
    return _integration_service


JSON_ROUTES = {
    "/move/abstract/zh/text": ("zh-abstract-move", "text"),
    "/move/abstract/zh/texts": ("zh-abstract-move", "texts"),
    "/move/abstract/en/text": ("en-abstract-move", "text"),
    "/move/abstract/en/texts": ("en-abstract-move", "texts"),
    "/move/fund/zh/text": ("fund-move", "text"),
    "/move/fund/zh/texts": ("fund-move", "texts"),
    "/classify/clc/zh/text": ("zh-classify", "text"),
    "/classify/clc/zh/texts": ("zh-classify", "texts"),
    "/classify/clc/en/text": ("en-classify", "text"),
    "/classify/clc/en/texts": ("en-classify", "texts"),
    "/classify/domain/text": ("domain-classify", "text"),
    "/classify/domain/texts": ("domain-classify", "texts"),
    "/keywords/zh/text": ("zh-keyword", "text"),
    "/keywords/zh/texts": ("zh-keyword", "texts"),
    "/keywords/en/text": ("en-keyword", "text"),
    "/keywords/en/texts": ("en-keyword", "texts"),
    "/research-question/text": ("rq-detect", "text"),
    "/research-question/texts": ("rq-detect", "texts"),
    "/citation-sentiment/text": ("citation-sentiment", "text"),
    "/citation-sentiment/texts": ("citation-sentiment", "texts"),
    "/citation-intent/text": ("citation-intent", "text"),
    "/citation-intent/texts": ("citation-intent", "texts"),
    "/concept-definition/text": ("definition-detect", "text"),
    "/concept-definition/texts": ("definition-detect", "texts"),
    "/ner/general/text": ("general-ner", "text"),
    "/ner/general/texts": ("general-ner", "texts"),
    "/ner/research/text": ("research-ner", "text"),
    "/ner/research/texts": ("research-ner", "texts"),
    "/ner/domain/text": ("domain-ner", "text"),
    "/ner/domain/texts": ("domain-ner", "texts"),
    "/relation/from-ner-record": ("relation-extract", "upstream_records"),
    "/relation/from-records": ("relation-extract", "upstream_records"),
    "/cluster/deep/texts": ("deep-cluster", "texts"),
    "/cluster/deep/collection": ("deep-cluster", "collection"),
    "/cluster-labels/generate": ("cluster-label", "texts"),
    "/cluster-labels/texts": ("cluster-label", "texts"),
    "/cluster-labels/from-cluster-task": ("cluster-label", "cluster_task"),
    "/review/structured/texts": ("structured-review", "texts"),
}

FILE_ROUTES = {
    "/move/abstract/zh/file": ("zh-abstract-move", False),
    "/move/abstract/zh/files": ("zh-abstract-move", True),
    "/move/abstract/en/file": ("en-abstract-move", False),
    "/move/abstract/en/files": ("en-abstract-move", True),
    "/move/fund/zh/file": ("fund-move", False),
    "/move/fund/zh/files": ("fund-move", True),
    "/classify/clc/zh/file": ("zh-classify", False),
    "/classify/clc/zh/files": ("zh-classify", True),
    "/classify/clc/en/file": ("en-classify", False),
    "/classify/clc/en/files": ("en-classify", True),
    "/classify/domain/file": ("domain-classify", False),
    "/classify/domain/files": ("domain-classify", True),
    "/keywords/zh/file": ("zh-keyword", False),
    "/keywords/zh/files": ("zh-keyword", True),
    "/keywords/en/file": ("en-keyword", False),
    "/keywords/en/files": ("en-keyword", True),
    "/research-question/file": ("rq-detect", False),
    "/research-question/files": ("rq-detect", True),
    "/citation-sentiment/file": ("citation-sentiment", False),
    "/citation-sentiment/files": ("citation-sentiment", True),
    "/citation-intent/file": ("citation-intent", False),
    "/citation-intent/files": ("citation-intent", True),
    # Historical aliases retained for deployed SDK clients.
    "/citation/sentiment/file": ("citation-sentiment", False),
    "/citation/sentiment/files": ("citation-sentiment", True),
    "/citation/intent/file": ("citation-intent", False),
    "/citation/intent/files": ("citation-intent", True),
    "/concept-definition/file": ("definition-detect", False),
    "/concept-definition/files": ("definition-detect", True),
    "/ner/general/file": ("general-ner", False),
    "/ner/general/files": ("general-ner", True),
    "/ner/research/file": ("research-ner", False),
    "/ner/research/files": ("research-ner", True),
    "/ner/domain/file": ("domain-ner", False),
    "/ner/domain/files": ("domain-ner", True),
    "/relation/file": ("relation-extract", False),
    "/relation/files": ("relation-extract", True),
    "/cluster/deep/files": ("deep-cluster", True),
    "/cluster-labels/files": ("cluster-label", True),
    "/review/structured/files": ("structured-review", True),
}


def _parse_form_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped.lower() in {"true", "false"}:
        return stripped.lower() == "true"
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
    try:
        if "." in stripped:
            return float(stripped)
        # 前导零数字串（如专业领域码 "09"）保持字符串，避免 int() 丢失前导零
        if stripped != "0" and stripped.startswith("0"):
            return stripped
        return int(stripped)
    except ValueError:
        return stripped


def _wants_async(request: Request, payload: Dict[str, Any]) -> bool:
    prefer = request.headers.get("prefer", "").lower()
    return "respond-async" in prefer or payload.get("async") is True


def _vue_public_response(tool_id: str, internal: Dict[str, Any], input_type: str) -> Dict[str, Any]:
    """Expose persisted task results in the exact response envelope used by Vue."""
    if internal.get("code") != 0:
        return internal
    task_data = internal.get("data") if isinstance(internal.get("data"), dict) else {}
    records = task_data.get("results") if isinstance(task_data.get("results"), list) else []
    contract = get_vue_contract(tool_id)
    is_batch = input_type in {"texts", "files"} and tool_id not in {"deep-cluster", "cluster-label", "structured-review"}
    meta = dict(internal.get("meta") or {})
    meta.update({
        "task_id": task_data.get("task_id"),
        "input_type": input_type,
        "total": task_data.get("total", len(records)),
        "success_count": task_data.get("success_count", 0),
        "failed_count": task_data.get("failed_count", 0),
    })
    if is_batch:
        public_results = []
        for record in records:
            public_results.append({
                "index": record.get("index"),
                "file_name": record.get("file_name"),
                "status": record.get("status"),
                "code": 0 if record.get("status") == "succeeded" else 50001,
                "record_id": record.get("record_id"),
                # 公开响应按弹窗渲染器白名单收敛；落库结果保持完整
                "result": public_viz_result(tool_id, record.get("result") or {}),
                **({"error": record.get("error")} if record.get("error") else {}),
            })
        return {
            "code": 0,
            "message": "success" if not task_data.get("failed_count") else "partial_success",
            "data": {
                "batch_id": task_data.get("task_id"),
                "input_type": input_type,
                "total": task_data.get("total", len(public_results)),
                "success_count": task_data.get("success_count", 0),
                "failed_count": task_data.get("failed_count", 0),
                "error_summary": task_data.get("error_summary"),
                "results": public_results,
            },
            "meta": meta,
        }
    record = next((item for item in records if item.get("status") == "succeeded"), records[0] if records else None)
    if not record:
        return {"code": 50001, "message": task_data.get("status") or "failed", "data": {}, "meta": meta}
    meta["record_id"] = record.get("record_id")
    # 暴露 file_name 供前端单文件弹窗题名列显示文件名（单文件 data 只含 record.result，
    # 不含 file_name；多文件 is_batch 分支已把 file_name 放进 results[i] 顶层）。
    meta["file_name"] = record.get("file_name")
    result = dict(record.get("result") or {})
    # A missing field is a contract defect, not an invitation to inject demo data.
    for field in contract.result_fields:
        result.setdefault(field, [] if field.endswith("s") and field not in {"statistics"} else None)
    # 公开响应按弹窗渲染器白名单收敛（在契约补全之后执行）：弹窗不读的中间/别名字段
    # 不对外输出，保证响应 JSON 与可视化弹窗严格一致；落库结果保持完整供后端消费。
    result = public_viz_result(tool_id, result)
    return {"code": 0, "message": "success", "data": result, "meta": meta}


def _json_endpoint(tool_id: str, input_type: str):
    async def endpoint(
        request: Request,
        service: ToolIntegrationService = Depends(get_integration_service),
    ) -> JSONResponse:
        if "multipart/form-data" in request.headers.get("content-type", ""):
            form = await request.form()
            payload: Dict[str, Any] = {}
            uploaded_resources: Dict[str, Dict[str, Any]] = {}
            for key, value in form.multi_items():
                if isinstance(value, StarletteUploadFile):
                    base_key = key.split("__", 1)[0]
                    uploaded_resources[base_key] = await _store_uploaded_resource(base_key, value, service)
                    await value.close()
                    continue
                payload[key] = _parse_form_value(value)
            for key, descriptor in uploaded_resources.items():
                current = payload.get(key)
                payload[key] = {**(current if isinstance(current, dict) else {}), **descriptor}
        else:
            try:
                payload = await request.json()
            except (json.JSONDecodeError, ValueError):
                payload = {}
            if not isinstance(payload, dict):
                raise HTTPException(status_code=422, detail="JSON 请求体必须是对象")
        payload = {**payload, "input_type": input_type}
        async_mode = _wants_async(request, payload)
        result = service.submit(tool_id, payload) if async_mode else service.execute(tool_id, payload)
        if not async_mode:
            result = _vue_public_response(tool_id, result, input_type)
        status_code = 202 if async_mode and result.get("code") == 0 else 200 if result.get("code") == 0 else (422 if 42200 <= int(result.get("code", 0)) < 42300 else 500)
        return JSONResponse(status_code=status_code, content=result)

    endpoint.__name__ = f"vue_{tool_id.replace('-', '_')}_{uuid_suffix()}"
    return endpoint


async def _extract_citation_pdf(uploads: List[StarletteUploadFile], *, max_size_mb: int | None = None) -> List[Dict[str, str]]:
    """引用工具专用解析：pymupdf citation parser（版面感知）→ mineru 兜底。

    citation parser 处理双栏阅读顺序 + 引用标记断裂修复（[1 跨行 → [1]），
    输出 body_text（参考文献章节之前的正文）。失败或正文 <100 字时回退
    extract_uploads(light=False)（强制 mineru），保证引用句召回不降级。
    """
    import asyncio
    limit_mb = max_size_mb or settings.MAX_UPLOAD_SIZE_MB
    maximum = limit_mb * 1024 * 1024
    out: List[Dict[str, str]] = []
    for upload in uploads:
        content = await upload.read(maximum + 1)
        if len(content) > maximum:
            raise ValueError(f"文件 {upload.filename} 超过 {limit_mb}MB 限制")
        text = ""
        try:
            from infrastructure.document_parser.pdf_citation_parser import CitationParser, ParseConfig
            import tempfile, os as _os
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                parser = CitationParser(ParseConfig(strict_reference_validation=False))
                result = await asyncio.to_thread(parser.parse, tmp_path)
                text = result.body_text or ""
            finally:
                _os.unlink(tmp_path)
        except Exception:  # noqa: BLE001
            text = ""
        if len(text.strip()) < 100:
            # parser 失败或太短 → 回退 mineru（走通用解析）
            try:
                fallback = extract_bytes(content, upload.filename or "upload.pdf", light=False)
                text = str(fallback or "")
            except Exception:  # noqa: BLE001
                pass
        if not text.strip():
            raise ValueError(f"未能从文件 {upload.filename} 提取文本")
        out.append({
            "file_name": upload.filename or "upload.pdf",
            "media_type": upload.content_type or "application/pdf",
            "text": text,
        })
    return out


def _llm_extract_abstract(pdf_path: str, feedback: str = "") -> str:
    """LLM 摘要提取（2026-09-09 混合架构）：PyMuPDF 抽前 5000 字 → GLM 逐字摘录。

    规则版面对疑难版式（标题拆字/无标题正文式/图例表格混排/引用导出页）覆盖不稳，
    LLM 语义定位天然稳健。输入截前 5000 字（实测 74 篇语料：摘要最晚结束于第 3077 字、P90 1975；
    密集页一页 4000+ 字，按字符截比按页数截更省 token）。
    输出强制逐字校验：去空白后在源文本中 find 不到且相似度 <0.93 即判失败
    （防改写/编造），由调用方回退规则结果/四层融合。
    feedback 非空 = 质检不合格重试：带上不合格原因让模型修正。
    """
    import pymupdf
    import re as _re
    from difflib import SequenceMatcher
    pages_text = []
    with pymupdf.open(pdf_path) as doc:
        for page in list(doc)[:5]:
            pages_text.append(page.get_text(sort=True))
            if sum(len(p) for p in pages_text) >= 5000:
                break
    full = "\n".join(p for p in pages_text if p and p.strip()).strip()[:5000]
    if len(full) < 60:
        return ""
    src = full
    from infrastructure.llm.glm_client import glm_client
    system = (
        "你是科技文献摘要提取器。从给定的文献前几页文本中找到摘要（摘要/Abstract/Summary 段），"
        "逐字摘录摘要全文，不得改写、增删、翻译或纠正错字。规则："
        "1) 中文论文常同时有中文摘要和英文 Abstract——此时必须提取【中文摘要】；"
        "2) 无标题的正文式摘要（arXiv 风格：作者单位行之后直接是摘要段落）也要完整提取；"
        "3) 只输出摘要正文，不含'摘要'标题词、关键词、作者、单位、收稿信息、版权声明、图表说明；"
        "4) 找不到摘要时输出空。只输出 JSON：{\"has_abstract\": true, \"abstract\": \"...\"}"
    )
    user = f"文献文本：\n{src}"
    if feedback:
        user += f"\n\n【重要】上一次提取未通过质检，原因：{feedback}。请严格修正后重新输出。"
    try:
        data = glm_client.chat_json(system, user, timeout=60.0,
                                    max_tokens=3000, temperature=0.0)
    except Exception:  # noqa: BLE001  GLM 不可用/超时 → 调用方回退
        return ""
    d = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
    if not isinstance(d, dict) or not d.get("has_abstract", True):
        return ""
    abstract = str(d.get("abstract") or "").strip()
    if len(abstract) < 60:
        return ""
    norm = lambda s: _re.sub(r"\s+", "", s)
    n_abs, n_full = norm(abstract), norm(full)
    if n_abs in n_full or n_abs[:400] in n_full:
        return abstract
    # 逐字校验失败 → 相似度兜底（拆字版式会把个别字符打散进句中，如"摘"插进句内）
    if SequenceMatcher(None, n_abs[:1500], n_full).find_longest_match(0, len(n_abs[:1500]), 0, len(n_full)).size \
            / max(1, min(len(n_abs), 1500)) >= 0.93:
        return abstract
    return ""


def _validate_extracted_abstract(pdf_path: str, abstract: str) -> List[str]:
    """提取结果硬校验（2026-09-09 工程化需求：正确性不依赖版式规则拟合）。

    版式无关的不变量，程序可判定——未见版式的正确性靠"提取+校验+自愈"闭环
    保证而非规则覆盖。返回不合格原因列表（空 = 通过）。
    """
    import re as _re
    import pymupdf
    reasons: List[str] = []
    if not (100 <= len(abstract) <= 3500):
        reasons.append(f"摘要长度异常（{len(abstract)} 字，正常 100~3500）")
    # 句子完整性：前 500 字内必须出现句末标点（从句中截断则整段无断句）
    if not _re.search(r"(?<!\d)[.。!?](?=\s|$)", abstract[:500]):
        reasons.append("开头疑似从句中截断（前 500 字无句末标点）")
    # 干净性：非摘要内容标记
    noise = [k for k in ("©", "Permission to make", "ACM ISBN", "ISBN",
                         "Corresponding author", "Correspondence", "⟦SUP",
                         "arXiv:", "doi.org", "@", "关键词", "Keywords") if k in abstract]
    if noise:
        reasons.append(f"含非摘要内容（{ '、'.join(noise[:3]) }）")
    # 语言正确性：页面存在中文摘要标记时，结果必须中文主导（双语=中文文献规则）
    cjk = sum(1 for ch in abstract if "一" <= ch <= "鿿")
    latin = sum(1 for ch in abstract if ch.isascii() and ch.isalpha())
    if cjk < latin * 0.5 and cjk + latin > 100:
        try:
            with pymupdf.open(pdf_path) as doc:
                head = "".join(doc[i].get_text() for i in range(min(3, doc.page_count)))
            if _re.search(r"摘\s*要|[关键词]", head):
                reasons.append("文献含中文摘要，但提取结果为英文")
        except Exception:  # noqa: BLE001
            pass
    return reasons


def _llm_extract_abstract_validated(pdf_path: str) -> str:
    """LLM 主路径闭环（2026-09-09）：提取 → 硬校验 → 带反馈重试一次 → 清洗。

    重试仍不合格时返回该结果（软性问题如末句无句号不阻断）——硬失败
    （逐字校验不过/空）返回空串由调用方走规则兜底。
    """
    from infrastructure.document_parser.pdf_citation_parser.abstract_repair import repair_abstract_text
    abstract = _llm_extract_abstract(pdf_path)
    if not abstract:
        return ""
    reasons = _validate_extracted_abstract(pdf_path, abstract)
    if reasons:
        retried = _llm_extract_abstract(pdf_path, feedback="；".join(reasons))
        if retried:
            abstract = retried
    # 清洗残余噪声/标记（⟦SUP⟧/尾部碎片等，与规则路径同口径）
    abstract = repair_abstract_text(abstract)
    return abstract if len(abstract.strip()) >= 50 else ""


async def _extract_abstract_fast(
    uploads: List[StarletteUploadFile], *, max_size_mb: int | None = None,
    preferred_language: str | None = None,
) -> List[Dict[str, str]]:
    """摘要语步快速解析（2026-09-09 LLM 主路径架构，用户拍板）。

    对未见版式的正确性不依赖规则拟合，靠"提取+校验+自愈"闭环：
    ① LLM 语义提取（主路径，2~4s/篇）：读前 5000 字逐字摘录，硬校验
    （逐字性/句完整性/干净性/语言正确）不合格带反馈重试一次；
    ② LLM 硬失败 → 规则版面提取兜底（v0.4.0 + 全部噪声修复，0.3s）；
    ③ 两者皆无结果 → 四层融合（MinerU→pdfplumber→正则→LLM）。
    preferred_language 恒 "zh"（双语摘要=中文文献，2026-09-08 用户规则，已写入
    LLM prompt 与硬校验双重保证）。
    """
    import asyncio
    import tempfile
    import os as _os
    limit_mb = max_size_mb or settings.MAX_UPLOAD_SIZE_MB
    maximum = limit_mb * 1024 * 1024
    from infrastructure.document_parser.pdf_citation_parser.abstracts import AbstractExtractor, AbstractConfig
    extractor = AbstractExtractor(AbstractConfig(search_pages=8, preferred_language=preferred_language))

    texts: Dict[str, str] = {}
    failed: List[StarletteUploadFile] = []
    raw_by_name: Dict[str, bytes] = {}
    for upload in uploads:
        content = await upload.read(maximum + 1)
        if len(content) > maximum:
            raise ValueError(f"文件 {upload.filename} 超过 {limit_mb}MB 限制")
        raw_by_name[upload.filename or "upload.pdf"] = content
        text = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                # ① LLM 主路径（线程池跑阻塞调用，4 路上传天然并发）
                text = await asyncio.to_thread(_llm_extract_abstract_validated, tmp_path)
                if not text:
                    # ② 规则兜底（GLM 不可用/逐字校验失败/无摘要结构）
                    result = await asyncio.to_thread(extractor.extract, tmp_path)
                    if result and result.text and len(result.text.strip()) >= 50:
                        text = result.text.strip()
            finally:
                _os.unlink(tmp_path)
        except Exception:  # noqa: BLE001
            text = ""
        if text:
            texts[upload.filename or "upload.pdf"] = text
        else:
            failed.append(upload)

    out: List[Dict[str, str]] = [
        {"file_name": name, "media_type": "application/pdf", "text": text}
        for name, text in texts.items()
    ]
    # 兜底：快速路径失败的走原四层融合（MinerU→pdfplumber→正则→LLM）
    if failed:
        async def _rebuild(fb: StarletteUploadFile):
            from starlette.datastructures import UploadFile as _UF
            import io as _io
            data = raw_by_name.get(fb.filename or "upload.pdf", b"")
            return _UF(file=_io.BytesIO(data), filename=fb.filename, headers=fb.headers)
        rebuilt = [await _rebuild(fb) for fb in failed]
        slow = await _extract_abstract_only(rebuilt, max_size_mb=limit_mb)
        out.extend(slow)
    return out


def _mineru_parse_one(content: bytes, filename: str, end_page: Optional[int]) -> Optional[Dict[str, str]]:
    """MinerU 单文件解析（2026-09-09 主路径，用户拍板：解析已与响应解离，用结构化
    markdown 换取全链路文本质量；CPU 后端实测英文 13~28s/20页、限 8 页约减半）。

    断词/双栏交错/噪声块/标题误抓等 PyMuPDF 固有问题在 md 输出中不存在。
    失败/超时/服务不可用返回 None，由调用方走 PyMuPDF 栈兜底（不删代码）。
    """
    import tempfile
    import os as _os
    from infrastructure.document_parser.mineru_api_client import MineruApiClient
    from infrastructure.document_parser.mineru_reader import _clean_md_text
    suffix = Path(filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = MineruApiClient().parse_pdf(tmp_path, end_page_id=end_page)
        if not result:
            return None
        md = _clean_md_text(str(result.get("md_content") or ""))
        if len(md.strip()) < 200 or md.strip().lower() == "nan":
            return None
        title = ""
        for line in md.splitlines():
            s = line.strip()
            if s.startswith("# ") and len(s) > 4:
                title = s[2:].strip()[:200]
                break
        return {"file_name": filename, "media_type": "application/pdf",
                "text": md, "title": title}
    except Exception:  # noqa: BLE001  mineru 任何异常 → 兜底路径
        return None
    finally:
        try:
            _os.unlink(tmp_path)
        except OSError:
            pass


_ABSTRACT_MD_HEADING = re.compile(r"^#{1,3}\s*(?:Abstract|ABSTRACT|摘\s*要)\s*[:：]?\s*$")


_FIG_REF = re.compile(r"^!\[.*?\]\(.*?\)$|^Figure\s+\d+|^Fig\.\s*\d+|^Table\s+\d+|^图\s*\d+|^表\s*\d+", re.IGNORECASE)


def _abstract_from_md(md: str) -> tuple:
    """从 MinerU markdown 提取 (摘要, 标题)：摘要标题段直到下一个 # 标题。

    图表注解过滤（2026-09-09，6.pdf 案例）：MinerU md 的摘要段后面紧跟
    Figure 1: / Table 1: / ![](images/...) 等图表内容，一并捞入会污染摘要
    文本和语步分类。逐行遇到首个图表标记即截断（图表前通常是摘要末句）。
    """
    title = ""
    lines = md.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if not title and s.startswith("# ") and len(s) > 4:
            title = s[2:].strip()[:200]
        if _ABSTRACT_MD_HEADING.match(s):
            buf = []
            for j in range(i + 1, min(i + 100, len(lines))):
                lj = lines[j].strip()
                if lj.startswith("#") or _FIG_REF.match(lj):
                    break
                buf.append(lines[j])
            abstract = "\n".join(buf).strip()
            # 附加清洗：去除可能残余的图片引用/图表标题
            abstract = re.sub(r"\n!\[.*?\]\(.*?\)", "", abstract)
            abstract = re.sub(r"\n(Figure|Fig\.?|Table|图|表)\s+\d+[^\n]*(?:\n|$)", "", abstract, flags=re.IGNORECASE)
            if len(abstract) >= 50:
                return abstract.strip(), title
    return "", title


# 主文献文件格式白名单（2026-09-20 用户定调：除声明格式外一律弹窗报错拒绝，
# 不允许上传——选择器切"所有文件"或改扩展名绕过 accept 的文件此前会被当
# 纯文本解析"成功"出结果，属于静默错误）
_ALLOWED_DOC_SUFFIXES = {".pdf", ".docx", ".txt"}


def _reject_disallowed_doc_files(uploads) -> None:
    bad = [u.filename or "?" for u in uploads
           if Path(u.filename or "").suffix.lower() not in _ALLOWED_DOC_SUFFIXES]
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的文件格式：{'、'.join(bad[:5])}{' 等' if len(bad) > 5 else ''}。"
                   "仅支持 PDF、DOCX、TXT",
        )


@router.post("/files/parse")
async def parse_files(
    request: Request,
    tool_id: str = Form(""),
) -> JSONResponse:
    """上传即解析（2026-09-07 架构调整）：文件→文本的解析前移到上传动作。

    与各工具 /file 路由的解析链完全同源（摘要语步=四层摘要提取、引用类=
    mineru 结构化、其余=light/full extract），保证功能结果不变；解析文本
    落 parse_store 并返回 parse_id，提交时 file/batch 路由带 preparsed=
    [parse_id,...] 直接取文本——点「在线测试」后的响应时间只剩功能执行。
    """
    form = await request.form()
    uploads = [value for value in form.getlist("files") if isinstance(value, StarletteUploadFile)]
    _reject_disallowed_doc_files(uploads)
    if not uploads:
        return JSONResponse(status_code=422, content={"code": 42201, "message": "未收到待解析文件"})
    if len(uploads) > settings.MAX_BATCH_FILES:
        return JSONResponse(status_code=422, content={
            "code": 42201, "message": f"批量文件数量不能超过 {settings.MAX_BATCH_FILES} 个（错误码 42201），本次共 {len(uploads)} 个"})
    effective_tool = str(tool_id or "").strip()
    CITATION_TOOLS = {"citation-intent", "citation-sentiment"}
    is_abstract_tool = effective_tool in ABSTRACT_MOVE_TOOLS
    # 摘要依赖型工具统一限前 8 页（2026-09-09）：摘要语步/分类×3/RQ/关键词×2 的
    # 核心信号源都是标题+摘要（最迟在第 7 页），限页减半耗时且不损质量——
    # 全文仅做关键词字面校验（前 8 页覆盖）和分类 LLM 参考（有摘要已足够）
    _ABSTRACT_DEPENDENT = ABSTRACT_MOVE_TOOLS | {
        "zh-classify", "en-classify", "domain-classify", "rq-detect",
        "zh-keyword", "en-keyword",
    }
    _end_page = ABSTRACT_MOVE_END_PAGE if effective_tool in _ABSTRACT_DEPENDENT else None
    _limit_mb = settings.MAX_UPLOAD_SIZE_MB
    _maximum = _limit_mb * 1024 * 1024
    try:
        # ── MinerU 主路径（2026-09-09 用户拍板）：全部工具走结构化 markdown；
        # PyMuPDF 栈（v0.4.0 规则库+修复管线+LLM 校验闭环）降级为逐文件兜底。
        # 摘要工具限前 8 页（ABSTRACT_MOVE_END_PAGE）控耗时；引用工具截参考
        # 文献章节（引用句召回面向正文）；非 PDF（txt/docx）不走 mineru。
        parsed_pairs: List[Dict[str, str]] = []
        failed: List[tuple] = []  # (name, content, content_type, headers)
        for upload in uploads:
            content = await upload.read(_maximum + 1)
            if len(content) > _maximum:
                raise ValueError(f"文件 {upload.filename} 超过 {_limit_mb}MB 限制")
            name = upload.filename or "upload.pdf"
            if not name.lower().endswith(".pdf") or effective_tool in PYMUPDF_TOOLS:
                # 非 PDF 或 PyMuPDF 专用工具（基金/定义/聚类/综述）：直接走
                # PyMuPDF light（含双栏分栏+断词重连+扫描件 MinerU 兜底）
                failed.append((name, content, upload.content_type, upload.headers))
                continue
            pair = await asyncio.to_thread(_mineru_parse_one, content, name, _end_page)
            if pair is None:
                failed.append((name, content, upload.content_type, upload.headers))
                continue
            if is_abstract_tool:
                # 摘要提取：md 正则（## Abstract/摘要 段）→ LLM（干净结构文本上
                # 校验通过率高）→ 仍无 → 兜底路径。双语=中文文献规则由 LLM 兜底
                # 承担（prompt 已含）；md 正则命中的天然是文档主摘要。
                abstract, title = await asyncio.to_thread(_abstract_from_md, pair["text"])
                if len(abstract) < 50:
                    try:
                        _svc = get_semantic_service()
                        _t2, _a2 = await asyncio.to_thread(
                            _svc._llm_title_abstract, pair["text"][:5000])
                        if _a2 and len(_a2) >= 50:
                            abstract, title = _a2, (_t2 or title)
                    except Exception:  # noqa: BLE001
                        pass
                if len(abstract) >= 50:
                    parsed_pairs.append({"file_name": name, "media_type": pair["media_type"],
                                         "text": abstract, "title": title})
                else:
                    failed.append((name, content, upload.content_type, upload.headers))
            elif effective_tool in CITATION_TOOLS:
                # 截参考文献章节：引用句抽取面向正文（LLM 全文兜底不受影响）
                body = re.split(r"(?m)^#{1,3}\s*(?:References|REFERENCES|参考文献)\s*$",
                                pair["text"])[0]
                # 质量门禁（2026-09-10，BOPPS/35.pdf 两代案例）：MinerU 对个别
                # PDF 会静默丢引用标记（嵌入字体丢字形 BOPPS 全丢；35.pdf 正文
                # 26 个年份引用只剩 4 个），不报错只是残缺 → 正则召回锐减/全空。
                # 每篇都跑 PyMuPDF 探针（~0.3s）按同口径数正文区引用标记，
                # MinerU 丢过半即整篇换 PyMuPDF light 文本。计数口径（防数学
                # 噪声误报，11.pdf [2,8,1] 数组/RL.pdf [0,1] 区间教训）：
                # 截参考文献区后数 [n]/［n］，排除含 0 区间与乱序数组（引用
                # 编号惯例递增），单值年份 [2024] 计入（年份引用风格），
                # 编号>399 排除。扫描件探针 0 标记不触发，MinerU 结果照用。
                _md_n = _count_body_citation_markers(pair["text"])
                from infrastructure.document_parser.upload_reader import extract_bytes as _eb
                try:
                    _probe = await asyncio.to_thread(_eb, content, name, light=True)
                except Exception:  # noqa: BLE001
                    _probe = ""
                _py_n = _count_body_citation_markers(_probe or "")
                if _py_n >= 3 and _md_n < _py_n * 0.5:
                    logger.warning(
                        "MinerU 丢引用标记（%s：MinerU %d 个 vs PyMuPDF %d 个），换用 PyMuPDF 文本",
                        name, _md_n, _py_n)
                    body = _probe
                parsed_pairs.append({"file_name": name, "media_type": pair["media_type"],
                                     "text": body, "title": pair.get("title", "")})
            else:
                if effective_tool in NER_TOOLS:
                    # NER 头部行补丁（2026-09-10 用户方案2）：MinerU 对个别 PDF
                    # 会丢基金项目/作者简介/收稿日期等头部元数据行（AI画像案例：
                    # md 无"基金项目"整行，PyMuPDF 有），而这类行是机构/人名/
                    # 地名富集区，丢了伤 NER 召回最大。PyMuPDF 探针（~0.3s）取
                    # 头部块中 md 缺失的行块，追加到 md 末尾再送 LLM——不动
                    # MinerU 主文本，只补丢的块。
                    pair["text"] = await asyncio.to_thread(
                        _patch_ner_header_lines, pair["text"], content, name)
                parsed_pairs.append(pair)
        if failed:
            async def _rebuild(fb_name, fb_data, fb_headers):
                from starlette.datastructures import UploadFile as _UF
                import io as _io
                return _UF(file=_io.BytesIO(fb_data), filename=fb_name, headers=fb_headers)
            _pdf_failed = [f for f in failed if f[0].lower().endswith(".pdf")]
            _other = [f for f in failed if not f[0].lower().endswith(".pdf")]
            if _pdf_failed:
                rebuilt = [await _rebuild(f[0], f[1], f[3]) for f in _pdf_failed]
                if is_abstract_tool:
                    parsed_pairs.extend(await _extract_abstract_fast(
                        rebuilt, max_size_mb=_limit_mb, preferred_language="zh"))
                elif effective_tool in CITATION_TOOLS:
                    parsed_pairs.extend(await _extract_citation_pdf(rebuilt, max_size_mb=_limit_mb))
                else:
                    parsed_pairs.extend(await extract_uploads(
                        rebuilt, max_size_mb=_limit_mb, light=settings.should_use_light(effective_tool)))
            if _other:
                rebuilt2 = [await _rebuild(f[0], f[1], f[3]) for f in _other]
                parsed_pairs.extend(await extract_uploads(
                    rebuilt2, max_size_mb=_limit_mb, light=settings.should_use_light(effective_tool)))
    except (ValueError, RuntimeError, OSError) as exc:
        return JSONResponse(status_code=422, content={"code": 42201, "message": str(exc)})
    finally:
        for upload in uploads:
            await upload.close()
    from infrastructure.document_parser import parse_store
    results = []
    for item in parsed_pairs:
        text = str(item.get("text") or "")
        parse_id = parse_store.put(str(item.get("file_name") or "file"), str(item.get("media_type") or ""), text)
        results.append({"parse_id": parse_id, "file_name": item.get("file_name"), "char_count": len(text)})
    return {"code": 0, "message": "解析完成", "data": {"tool_id": effective_tool, "results": results}}


def _file_endpoint(tool_id: str, multiple: bool):
    async def endpoint(
        request: Request,
        service: ToolIntegrationService = Depends(get_integration_service),
    ) -> JSONResponse:
        form = await request.form()
        contract = get_vue_contract(tool_id)
        field = contract.primary_input_field
        uploads = [value for value in form.getlist(field) if isinstance(value, StarletteUploadFile)]
        if not uploads:
            fallback_fields = ("files", "file", "document_set", "scientific_document_texts")
            uploads = [
                value for fallback in fallback_fields for value in form.getlist(fallback)
                if isinstance(value, StarletteUploadFile)
            ]
        # 预解析模式（2026-09-07）：preparsed=[parse_id,...]（JSON 数组）——上传阶段
        # 已通过 /files/parse 完成文件→文本，这里直接取文本构造 extracted，
        # 跳过文件接收与解析；文件本体不再传输。
        preparsed_raw = str(form.get("preparsed") or "").strip()
        if uploads:
            _reject_disallowed_doc_files(uploads)
        if not uploads and not preparsed_raw:
            raise HTTPException(status_code=422, detail=f"缺少上传字段：{field}")
        if not multiple and not preparsed_raw and len(uploads) != 1:
            raise HTTPException(status_code=422, detail="单文件接口只能上传一个文件")
        # 批量文件数量上限（边界异常用例预期：提交后返回明确错误提示 code=42201）
        if len(uploads) > settings.MAX_BATCH_FILES:
            raise HTTPException(
                status_code=422,
                detail=f"批量文件数量不能超过 {settings.MAX_BATCH_FILES} 个（错误码 42201），本次共 {len(uploads)} 个",
            )
        payload: Dict[str, Any] = {}
        uploaded_resources: Dict[str, Any] = {}
        primary_ids = {id(upload) for upload in uploads}
        for key, value in form.multi_items():
            if isinstance(value, StarletteUploadFile):
                if id(value) not in primary_ids:
                    base_key = key.split("__", 1)[0]
                    if base_key in {"document_metadata", "citation_metadata"}:
                        uploaded_resources[base_key] = await _parse_metadata_upload(value)
                    else:
                        uploaded_resources[base_key] = await _store_uploaded_resource(base_key, value, service)
                    await value.close()
                continue
            parsed = _parse_form_value(value)
            if key in payload:
                payload[key] = payload[key] if isinstance(payload[key], list) else [payload[key]]
                payload[key].append(parsed)
            else:
                payload[key] = parsed
        for key, descriptor in uploaded_resources.items():
            current = payload.get(key)
            payload[key] = (
                {**(current if isinstance(current, dict) else {}), **descriptor}
                if isinstance(descriptor, dict) else descriptor
            )
        payload.setdefault("input_type", "files" if multiple else "file")
        # 单文件上限统一 50MB（结构化综述不再放宽；需求 2026-09-05：所有功能点单文件 ≤50M、批量 ≤20 篇）
        upload_limit_mb = settings.MAX_UPLOAD_SIZE_MB
        if preparsed_raw:
            # 预解析提交：parse_store 取文本（含校验单文件/批量数量），不再解析
            import json as _json
            from infrastructure.document_parser import parse_store as _ps
            try:
                parse_ids = _json.loads(preparsed_raw)
                if not isinstance(parse_ids, list) or not all(isinstance(x, str) for x in parse_ids):
                    raise ValueError("preparsed 必须是 parse_id 字符串数组")
            except (ValueError, TypeError) as exc:
                raise HTTPException(status_code=422, detail=f"preparsed 格式不正确：{exc}") from exc
            if not multiple and len(parse_ids) != 1:
                raise HTTPException(status_code=422, detail="单文件接口只能提交一个预解析结果")
            if len(parse_ids) > settings.MAX_BATCH_FILES:
                raise HTTPException(
                    status_code=422,
                    detail=f"批量文件数量不能超过 {settings.MAX_BATCH_FILES} 个（错误码 42201），本次共 {len(parse_ids)} 个",
                )
            try:
                extracted = [{
                    "file_name": item["file_name"],
                    "media_type": item["media_type"],
                    "text": item["text"],
                } for item in _ps.take_many(parse_ids)]
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            # 批量预解析提交支持异步（2026-09-09 实时进度需求）：Prefer: respond-async
            # → submit 立即返回 task_id，前端轮询 /tasks/{id}/progress，终态取
            # /tasks/{id}/vue-result（与同步响应同构）。此前 preparsed 分支提前
            # 同步返回，异步分支永远不可达——而前端文件批量恰全走 preparsed。
            async_mode = _wants_async(request, payload)
            if async_mode:
                result = service.submit(tool_id, payload, file_inputs=extracted)
                status_code = 202 if result.get("code") == 0 else (422 if 42200 <= int(result.get("code", 0)) < 42300 else 500)
                return JSONResponse(status_code=status_code, content=result)
            try:
                result = service.execute(tool_id, payload, file_inputs=extracted)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            result = _vue_public_response(tool_id, result, payload["input_type"])
            status_code = 200 if result.get("code") == 0 else (422 if 42200 <= int(result.get("code", 0)) < 42300 else 500)
            return JSONResponse(status_code=status_code, content=result)
        try:
            if tool_id in ABSTRACT_MOVE_TOOLS:
                # 摘要语步识别：只送纯摘要（四层融合解析），过滤标题/关键词/全文
                extracted = await _extract_abstract_only(uploads, max_size_mb=upload_limit_mb)
            elif tool_id in PATH_PASSTHROUGH_TOOLS:
                # 单/多文件均落盘路径延迟解析（_semantic_request 走 is_path 分支）：
                # ① rq-detect light 取文 0 时用 _source_pdf_path 回退 mineru 重抽重判
                # ② extract_bytes 内双栏/扫描回退走 PageBudgetPool，前端并发调多个 /file 也安全
                extracted = await save_uploads_to_temp(uploads, max_size_mb=upload_limit_mb)
            else:
                extracted = await extract_uploads(uploads, max_size_mb=upload_limit_mb, light=settings.should_use_light(tool_id))
        except (ValueError, RuntimeError, OSError) as exc:
            if tool_id.startswith("citation-"):
                # 引用工具文件解析失败（扫描版/无文本层/损坏文件等）不暴露底层
                # 报错，返回业务可读提示（在线测试页直接展示 message）
                return JSONResponse(status_code=422, content={
                    "code": 42201,
                    "message": f"文件解析失败，无法执行引用识别：{exc}。请上传含文本层的 PDF/DOCX/TXT 文件（扫描版请先转为文字版）。",
                    "data": {"task_id": "", "tool_id": tool_id, "status": "failed",
                             "input_type": str(payload.get("input_type") or "file"), "progress": 0,
                             "total": 0, "success_count": 0, "failed_count": 0,
                             "results": [], "summary": {}, "available_exports": ["json", "csv"]},
                    "meta": {},
                })
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            for upload in uploads:
                await upload.close()
        async_mode = _wants_async(request, payload)
        result = service.submit(tool_id, payload, file_inputs=extracted) if async_mode else service.execute(tool_id, payload, file_inputs=extracted)
        if not async_mode:
            result = _vue_public_response(tool_id, result, payload["input_type"])
        status_code = 202 if async_mode and result.get("code") == 0 else 200 if result.get("code") == 0 else (422 if 42200 <= int(result.get("code", 0)) < 42300 else 500)
        return JSONResponse(status_code=status_code, content=result)

    endpoint.__name__ = f"vue_{tool_id.replace('-', '_')}_{'files' if multiple else 'file'}_{uuid_suffix()}"
    return endpoint


def uuid_suffix() -> str:
    # 注册动态路由时仅需短且稳定于本进程的唯一函数名。
    import uuid
    return uuid.uuid4().hex[:8]


for route_path, (route_tool_id, route_input_type) in JSON_ROUTES.items():
    router.add_api_route(route_path, _json_endpoint(route_tool_id, route_input_type), methods=["POST"], summary=route_tool_id)

for route_path, (route_tool_id, route_multiple) in FILE_ROUTES.items():
    router.add_api_route(route_path, _file_endpoint(route_tool_id, route_multiple), methods=["POST"], summary=route_tool_id)


@router.post("/cluster/deep/evaluate")
async def evaluate_deep_cluster(
    request: Request,
    service: ToolIntegrationService = Depends(get_integration_service),
) -> Dict[str, Any]:
    """独立金标聚类评估（不改动、不阻塞用户的常规聚类任务）。

    2026-09-08 恢复：v3 语步对齐重构（956c214）时路由被误删，服务层
    DeepClusterEvaluationService 一直存活（仍写 model_evaluation_runs）。
    """
    if "multipart/form-data" in request.headers.get("content-type", ""):
        form = await request.form()
        payload: Dict[str, Any] = {}
        uploaded_resources: Dict[str, Dict[str, Any]] = {}
        for key, value in form.multi_items():
            if isinstance(value, StarletteUploadFile):
                base_key = key.split("__", 1)[0]
                uploaded_resources[base_key] = await _store_uploaded_resource(base_key, value, service)
                await value.close()
            else:
                payload[key] = _parse_form_value(value)
        for key, descriptor in uploaded_resources.items():
            current = payload.get(key)
            payload[key] = {**(current if isinstance(current, dict) else {}), **descriptor}
    else:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="JSON 请求体必须是对象")
    try:
        from application.service.deep_cluster_evaluation_service import DeepClusterEvaluationService
        value = DeepClusterEvaluationService(service).evaluate(payload)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "success", "data": value}


@router.post("/citation-metadata/parse")
def parse_citation_metadata(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """参考文献条目批量解析（GLM）：粘贴整段参考文献列表 → 结构化元数据数组。

    供引用句识别前端「被引文献元数据」面板使用：支持多条中英文条目混排。
    """
    entries_text = str(payload.get("entries_text") or "").strip()
    if not entries_text:
        raise HTTPException(status_code=422, detail="请提供参考文献条目文本")
    from application.service.tool_integration_service import _parse_reference_entries
    try:
        metadata = _parse_reference_entries(entries_text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"条目解析失败：{exc}") from exc
    if not metadata:
        raise HTTPException(status_code=422, detail="未能解析出任何条目，请检查条目格式")
    return {"code": 0, "message": f"已解析 {len(metadata)} 条参考文献", "data": metadata}


@router.post("/relation/dependency-preview")
def relation_dependency_preview(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """依存句法分析预览:基于上游 NER 记录的实体与语境,用 GLM 快速生成依存弧。

    供实体关系识别输入区展示:用户选择上游记录后即可看到
    依存句法分析结果(中心词/依存关系/依存词),无需提交。
    """
    record_id = str(payload.get("upstream_entity_record_id") or "").strip()
    if not record_id:
        raise HTTPException(status_code=422, detail="请选择上游实体记录")
    service = get_integration_service()
    record = service.repository.get_result(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="上游记录不存在")
    result = record.get("result") or {}
    entities = result.get("entities") or result.get("entity_results") or []
    if not isinstance(entities, list) or not entities:
        raise HTTPException(status_code=422, detail="上游记录无已识别实体")
    # 取实体语境句子作为分析文本
    contexts = []
    for ent in entities:
        if isinstance(ent, dict) and ent.get("context"):
            ctx = str(ent["context"]).strip()
            if ctx and ctx not in contexts and not ctx.startswith("/tmp/"):
                contexts.append(ctx)
    text = " ".join(contexts[:5])[:2000]  # 最多5句,2000字
    if not text:
        # 无语境时用实体列表组合
        text = " ".join(str(e.get("text") or "") for e in entities[:20] if isinstance(e, dict))
    if not text:
        raise HTTPException(status_code=422, detail="无可用文本进行依存句法分析")
    # GLM 快速依存句法分析
    from infrastructure.llm.glm_client import glm_client
    system = (
        "你是中文依存句法分析专家。对给定文本做依存句法分析,输出依存弧列表。\n"
        "每条弧:head(中心词/支配词)、relation(依存关系类型,如:主谓关系/动宾关系/定语/状语/并列关系/介宾关系)、"
        "dependent(依存词/从属词)、sentence_id(句子编号,SENT-001格式)。\n"
        "硬约束(违反的弧会被丢弃):head与dependent必须是实词或实体——禁止标点符号((),。:;等)、"
        "括号、纯数字(邮编/年份)作为节点;禁止head与dependent相同(自环);"
        "单位地址邮编等附属信息不产弧;每个词至多一个中心词。\n"
        "只输出JSON:{\"data\":[{\"head\":\"\",\"relation\":\"\",\"dependent\":\"\",\"sentence_id\":\"SENT-001\"}]}"
    )
    try:
        out = glm_client.chat_json(system, f"分析以下文本的依存句法:\n{text}", timeout=30.0, max_tokens=2000)
        arcs = out.get("data", out) if isinstance(out, dict) else []
        if not isinstance(arcs, list):
            arcs = []
        # 依存弧清洗（2026-09-20 用户定调）：符号节点/自环/重复弧过滤——
        # 中心词与依存词必须是实词或实体，标点括号邮编不是句法节点
        from application.service.semantic_service import sanitize_dependency_arcs
        arcs = sanitize_dependency_arcs(arcs)
        return {"code": 0, "message": f"已生成 {len(arcs)} 条依存弧", "data": arcs}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"依存句法分析失败: {exc}") from exc


@router.post("/review/structured/collections/{collection_id}")
def review_from_collection(
    collection_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
    service: ToolIntegrationService = Depends(get_integration_service),
) -> Dict[str, Any]:
    internal = service.execute("structured-review", {**payload, "input_type": "collection", "collection_id": collection_id})
    return _vue_public_response("structured-review", internal, "collection")


@router.post("/review/structured/collections")
def review_from_selected_collection(
    payload: Dict[str, Any] = Body(default_factory=dict),
    service: ToolIntegrationService = Depends(get_integration_service),
) -> Dict[str, Any]:
    """与 Vue 的“指定文献集”模式保持一致，集合编号由请求体提交。"""
    document_set = payload.get("document_set")
    collection_id = str(
        payload.get("collection_id")
        or (document_set.get("collection_id") if isinstance(document_set, dict) else document_set)
        or ""
    ).strip()
    if not collection_id:
        raise HTTPException(status_code=422, detail="缺少指定文献集编号 collection_id")
    internal = service.execute(
        "structured-review",
        {**payload, "input_type": "collection", "collection_id": collection_id},
    )
    return _vue_public_response("structured-review", internal, "collection")


@router.get("/capabilities")
def capabilities() -> Dict[str, Any]:
    return {
        "code": 0,
        "data": [{
            "tool_id": item.tool_id,
            "backend_code": item.backend_code,
            "name": item.name,
            "collection_tool": item.collection_tool,
            "supported_modes": list(get_vue_contract(item.tool_id).input_modes),
            "request_fields": list(get_vue_contract(item.tool_id).request_fields),
            "result_fields": list(get_vue_contract(item.tool_id).result_fields),
            "schema_version": "1.0",
            "model_version": settings.MODEL_VERSION,
            "available_exports": list(item.export_formats),
        } for item in CONTRACTS],
    }


@router.get("/tasks")
def list_tasks(
    tool_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    workspace_id: str = Query(settings.DEFAULT_WORKSPACE_ID),
) -> Dict[str, Any]:
    return {"code": 0, "data": task_repository.list_tasks(workspace_id, tool_id, limit)}


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> Dict[str, Any]:
    task = task_repository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"code": 0, "data": task}


@router.get("/tasks/{task_id}/progress")
def get_task_progress(task_id: str) -> Dict[str, Any]:
    """批量任务逐篇进度（2026-09-09 需求：等待响应期间显示哪些文件已出结果+耗时）。

    前端批量提交带 Prefer: respond-async 后轮询本端点：items 按输入序返回
    {index, file_name, status, elapsed_ms}——耗时取条目时间戳（运行中=now-created，
    完成=updated-created）。"""
    from datetime import datetime
    task = task_repository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    items_out = []
    for item in task_repository.list_items(task_id):
        source = item.get("source") or {}
        try:
            created = datetime.fromisoformat(str(item.get("created_at")))
            updated = datetime.fromisoformat(str(item.get("updated_at")))
        except (TypeError, ValueError):
            created = updated = now
        finished = str(item.get("status")) in {"succeeded", "failed", "skipped"}
        end_at = updated if finished else now
        items_out.append({
            "index": item.get("input_index"),
            "file_name": source.get("file_name") or f"第{(item.get('input_index') or 0) + 1}篇",
            "status": item.get("status"),
            "elapsed_ms": max(0, int((end_at - created).total_seconds() * 1000)),
        })
    return {"code": 0, "data": {
        "task_id": task_id,
        "status": task.get("status"),
        "progress": task.get("progress"),
        "total": task.get("total") or len(items_out),
        "success_count": task.get("success_count", 0),
        "failed_count": task.get("failed_count", 0),
        "items": items_out,
    }}


@router.get("/tasks/{task_id}/vue-result")
def get_task_vue_result(task_id: str, tool_id: str = Query(...), input_type: str = Query("files")) -> Dict[str, Any]:
    """异步任务终态 → 与同步响应完全同构的 Vue 信封（复用 _vue_public_response）。

    前端轮询到终态后取本端点渲染，弹窗/导出/复制与同步路径零差异。
    全部失败且错误同类（2026-09-10 用户需求）：批量上传整批同类错误（如英文论文
    全部进中文工具的语言不匹配）不逐条重复 N 次，返回一条干净的错误提示。"""
    task = task_repository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    items = task_repository.list_items(task_id)
    records_by_item = {}
    for record in task_repository.list_results(task_id):
        records_by_item[record.get("task_item_id")] = record
    results = []
    for item in items:
        record = records_by_item.get(item.get("id")) or {}
        results.append({
            "index": item.get("input_index"),
            "file_name": (item.get("source") or {}).get("file_name"),
            "status": item.get("status"),
            "record_id": record.get("id"),
            "error": item.get("error_message"),
            "result": record.get("result") or {},
        })
    internal = {"code": 0, "message": task.get("status"), "data": {
        "task_id": task_id,
        "tool_id": tool_id,
        "input_type": input_type,
        "status": task.get("status"),
        "total": len(items),
        "success_count": task.get("success_count", 0),
        "failed_count": task.get("failed_count", 0),
        "results": results,
    }}
    # 全部失败且错误同类：返回一条干净错误（不逐条重复 N 次）
    _failed_errors = [str(r.get("error") or "") for r in results if r.get("status") == "failed" and r.get("error")]
    _common_prefixes = ("语言不匹配", "文件解析失败", "预解析结果已过期")
    if results and _failed_errors and len(_failed_errors) == len(results):
        for _prefix in _common_prefixes:
            if all(e.startswith(_prefix) for e in _failed_errors):
                raise HTTPException(status_code=422, detail=_failed_errors[0])
    return _vue_public_response(tool_id, internal, input_type)


@router.get("/tasks/{task_id}/results")
def get_task_results(task_id: str) -> Dict[str, Any]:
    if not task_repository.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"code": 0, "data": task_repository.list_results(task_id)}


@router.get("/results/{record_id}")
def get_result(record_id: str) -> Dict[str, Any]:
    record = task_repository.get_result(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="结果记录不存在")
    return {"code": 0, "data": record}


@router.get("/results/{record_id}/lineage")
def get_result_lineage(record_id: str) -> Dict[str, Any]:
    try:
        value = result_governance_service.lineage(record_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"code": 0, "data": value}


@router.post("/tasks/{task_id}/rerun")
def rerun_task(
    task_id: str,
    service: ToolIntegrationService = Depends(get_integration_service),
) -> Dict[str, Any]:
    task = task_repository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    payload = dict(task.get("request_payload") or {})
    payload["rerun_from_task_id"] = task_id
    return service.execute(task["tool_id"], payload, workspace_id=task["workspace_id"])


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str) -> Dict[str, Any]:
    if not task_repository.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task_repository.cancel_task(task_id):
        raise HTTPException(status_code=409, detail="任务已结束，不能取消")
    return {"code": 0, "message": "任务已取消", "data": {"task_id": task_id, "status": "cancelled"}}


@router.post("/tasks/{task_id}/archive")
def archive_task(task_id: str) -> Dict[str, Any]:
    if not task_repository.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    task_repository.archive_task(task_id)
    return {"code": 0, "message": "任务已归档", "data": {"task_id": task_id}}


@router.post("/classification-results/{record_id}/confirm")
def confirm_classification(record_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        value = result_governance_service.confirm_classification(record_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "分类结果已确认", "data": value}


@router.post("/cluster-labels/{record_id}/confirm")
def confirm_cluster_label(record_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        value = result_governance_service.confirm_cluster_label(record_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "类簇标签已确认", "data": value}


@router.post("/results/{record_id}/feedback")
def create_feedback(record_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        value = result_governance_service.feedback(record_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "反馈已保存", "data": value}


@router.get("/history/compatible")
def compatible_history(
    downstream_tool: str,
    upstream_type: str,
    workspace_id: str = Query(settings.DEFAULT_WORKSPACE_ID),
    limit: int = Query(50, ge=1, le=200),
    service: ToolIntegrationService = Depends(get_integration_service),
) -> Dict[str, Any]:
    repository = service.repository
    allowed = {
        "entity": {"general-ner", "research-ner", "domain-ner", "upstream-entity"},
        "dependency": {"upstream-dependency"},
        "cluster": {"deep-cluster"},
        "review_source": {"deep-cluster", "cluster-label"},
    }.get(upstream_type, set())
    tasks = [task for task in repository.list_tasks(workspace_id, limit=200)
             if task.get("tool_id") in allowed and task.get("status") == "succeeded"][:limit]
    options = []
    for task_summary in tasks:
        # list_tasks intentionally omits request_payload; load the complete
        # task only for the selected compatible history rows.
        task = repository.get_task(task_summary["id"]) or task_summary
        for record in repository.list_results(task["id"]):
            result = record.get("result") if isinstance(record.get("result"), dict) else {}
            request_payload = task.get("request_payload") if isinstance(task.get("request_payload"), dict) else {}
            # 记录命名:文本输入用题目,文件输入用文件名,方便用户选择
            _rp = request_payload
            _name = ""
            if isinstance(_rp, dict):
                # 文件输入:file_inputs 或 files 里的 file_name
                _files = _rp.get("files") or []
                if isinstance(_files, list) and _files:
                    _first = _files[0]
                    if isinstance(_first, dict):
                        _name = str(_first.get("file_name") or "")[:60]
                if not _name:
                    _titles = _rp.get("document_title") or _rp.get("title")
                    if isinstance(_titles, list) and _titles:
                        _name = str(_titles[0] or "")[:60]
                    elif isinstance(_titles, str):
                        _name = _titles[:60]
                if not _name:
                    # 从结果回填的 document.title
                    _name = str((result.get("document") or {}).get("title") or "")[:60]
            # NER 记录名格式（2026-09-11 用户定稿）：文件名 · 命名实体识别类型 · 北京时间
            # created_at 已是 Asia/Shanghai（北京标准时间），截到分钟
            _NER_TYPE_ZH = {
                "general-ner": "通用命名实体识别",
                "research-ner": "科研命名实体识别",
                "domain-ner": "专业领域命名实体识别",
                "upstream-entity": "实体识别",
                "upstream-dependency": "依存句法",
                "deep-cluster": "深度聚类",
                "cluster-label": "标签生成",
            }
            _type_zh = _NER_TYPE_ZH.get(task["tool_id"], task["tool_id"])
            _time = str(task.get("created_at") or "")[:16].replace("T", " ")
            if not _name:
                _name = f"{_type_zh} · {_time}" if _time else _type_zh
            else:
                _parts = [_name, _type_zh]
                if _time:
                    _parts.append(_time)
                _name = " · ".join(_parts)
            option = {
                "task_id": task["id"], "record_id": record["id"], "tool_id": task["tool_id"],
                "status": task["status"], "created_at": task["created_at"],
                "label": _name,
            }
            if upstream_type == "entity":
                task_item = repository.get_task_item(str(record.get("task_item_id") or ""))
                source_text = service._text_from_task_item(task_item)
                if not source_text:
                    source_text = service._text_from_task_payload(
                        request_payload,
                        task_item.get("input_index") if task_item else None,
                        str(task.get("tool_id") or ""),
                    )
                if not source_text:
                    public_field = get_vue_contract(task["tool_id"]).primary_input_field
                    source_text = request_payload.get(public_field) or request_payload.get("text") or ""
                    if isinstance(source_text, list):
                        source_text = source_text[0].get("text", "") if source_text and isinstance(source_text[0], dict) else (source_text[0] if source_text else "")
                option.update({
                    "sentence": str(source_text),
                    "entities": result.get("entities") or [],
                    "document_title": (result.get("document") or {}).get("title"),
                })
            elif upstream_type == "cluster":
                # 与标签生成实际输入同源：候选类目分布（锚定+双候选票数）构建短语集，
                # 未锚定簇由方法内部回退代表短语——前端预览即标签生成真正吃到的内容
                from application.service.tool_integration_service import ToolIntegrationService as _TIS
                phrase_sets = _TIS._cluster_phrase_sets(result)
                _dim = str(result.get("cluster_dimension") or result.get("dimension") or "")
                _dim_label = "技术路线聚类" if _dim.startswith("tech") else ("应用场景聚类" if _dim.startswith("app") else "深度聚类")
                _doc_count = (result.get("input_summary") or {}).get("document_count") or len(phrase_sets)
                _time = str(task.get("created_at") or "")[:16].replace("T", " ")
                option.update({
                    "dimension": result.get("cluster_dimension") or result.get("dimension"),
                    "document_count": _doc_count,
                    "cluster_count": len(phrase_sets),
                    "phrase_sets": phrase_sets,
                    "label": f"{_dim_label}({_doc_count}篇) · {_time}",
                })
            options.append(option)
    return {"code": 0, "data": options, "meta": {"downstream_tool": downstream_tool, "upstream_type": upstream_type}}


@router.get("/database/health")
def database_health() -> Dict[str, Any]:
    return {"code": 0, "data": task_repository.healthcheck(), "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()}


@router.post("/upstream-records/{kind}")
def create_upstream_record(kind: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        value = upstream_record_service.create(kind, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "上游结构化记录已保存", "data": value}


@router.post("/collections")
def create_collection(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        value = resource_service.create_collection(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "文献集合已创建", "data": value}


@router.get("/collections/cluster-sets")
def cluster_collection_options(
    workspace_id: str = Query(settings.DEFAULT_WORKSPACE_ID),
    limit: int = Query(50, ge=1, le=200),
    service: ToolIntegrationService = Depends(get_integration_service),
) -> Dict[str, Any]:
    """聚类标签生成任务的簇文献集列表（结构化综述"指定文献集"数据源）。

    每个已完成的标签生成任务按簇展开：簇名（推荐标签）、任务时间、簇内篇数。
    按任务时间倒序返回，不做主题相似度过滤（2026-09-06 用户定调：直接下拉选择）。
    """
    return {"code": 0, "data": service.cluster_set_options(workspace_id, limit)}


@router.get("/collections")
def list_collections(
    limit: int = Query(100, ge=1, le=200),
    workspace_id: str = Query(settings.DEFAULT_WORKSPACE_ID),
    topic: Optional[str] = Query(None, description="研究主题，传入后按主题↔场景标签语义相似度过滤"),
    threshold: float = Query(0.3, ge=0.0, le=1.0, description="相似度阈值"),
) -> Dict[str, Any]:
    return {"code": 0, "data": resource_service.list_collections(workspace_id, limit, topic, threshold)}


@router.get("/collections/{collection_id}")
def get_collection(collection_id: str) -> Dict[str, Any]:
    value = resource_service.get_collection(collection_id)
    if not value:
        raise HTTPException(status_code=404, detail="文献集合不存在")
    return {"code": 0, "data": value}


@router.post("/dictionaries")
def create_dictionary(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        value = resource_service.create_dictionary(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "用户词典已保存", "data": value}


@router.get("/dictionaries")
def list_dictionaries(
    limit: int = Query(100, ge=1, le=200),
    workspace_id: str = Query(settings.DEFAULT_WORKSPACE_ID),
) -> Dict[str, Any]:
    return {"code": 0, "data": resource_service.list_dictionaries(workspace_id, limit)}


@router.get("/dictionaries/{dictionary_id}")
def get_dictionary(dictionary_id: str, version: Optional[int] = Query(None, ge=1)) -> Dict[str, Any]:
    value = resource_service.get_dictionary(dictionary_id, version)
    if not value:
        raise HTTPException(status_code=404, detail="用户词典或指定版本不存在")
    return {"code": 0, "data": value}


@router.delete("/dictionaries/{dictionary_id}")
def delete_dictionary(dictionary_id: str) -> Dict[str, Any]:
    deleted = resource_service.delete_dictionary(dictionary_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="用户词典不存在或已删除")
    return {"code": 0, "message": "词典已删除"}


@router.post("/semantic-resources")
def register_semantic_resource(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        value = resource_service.register_semantic_resource(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "语义资源已登记", "data": value}


@router.get("/semantic-resources")
def list_semantic_resources(
    resource_key: Optional[str] = Query(None),
    status: Optional[str] = Query("current"),
    limit: int = Query(200, ge=1, le=500),
) -> Dict[str, Any]:
    return {"code": 0, "data": resource_service.list_semantic_resources(resource_key, status, limit=limit)}


@router.get("/semantic-resources/index-status")
def get_index_status(storage_uri: str = Query(...)) -> Dict[str, Any]:
    """CLC 用户索引构建进度（2026-09-19 用户定调：编码过程要有进度，
    与文件解析进度同款交互——资源槽选文件后前端轮询此端点渲染进度条）。"""
    from infrastructure.rag.clc_user_index_service import index_status_for
    status = index_status_for(storage_uri)
    if status is None:
        raise HTTPException(status_code=404, detail="该资源无需构建索引或路径不存在")
    return {"code": 0, "data": status}


@router.get("/semantic-resources/{resource_id}")
def get_semantic_resource(resource_id: str) -> Dict[str, Any]:
    value = resource_service.get_semantic_resource(resource_id)
    if not value:
        raise HTTPException(status_code=404, detail="语义资源不存在")
    return {"code": 0, "data": value}


@router.post("/semantic-resources/validate")
async def validate_semantic_resource(
    resource_key: str = Form(...),
    upload: UploadFile = File(...),
) -> Dict[str, Any]:
    """选文件即预检（2026-09-15 用户定调：加载/解析/重构在参数录入阶段完成，
    点击在线测试只跑功能）。落盘（同指纹复用）+ 确定性归一 + 必要字段探测 +
    大模型重构（磁盘结果复用，同内容不重复调 LLM），立即返回可读条数或格式
    错误。不登记数据库——提交在线测试时随请求内联上传才入库（一次性语义不变）。
    """
    import hashlib
    from infrastructure.resources.normalize import (
        ROW_FIELD_CONFIG as _ROWCFG, ResourceParseError as _RPE,
        inspect_user_resource as _inspect, register_normalized as _reg,
    )

    def _index_build_status(stored_path, field, rows):
        """CLC 大表（分类树+超阈值）预检即建索引，返回进度描述供前端轮询展示。"""
        try:
            if field not in ("clc_labeled_data", "classification_standard_mapping_table",
                             "domain_classification_rules") or not isinstance(rows, list):
                return None
            from infrastructure.rag.clc_user_index_service import compute_clc_verdict
            verdict = compute_clc_verdict(rows, stored_path.stat().st_size)
            if not (verdict and verdict.get("kind") == "taxonomy_complete"
                    and verdict.get("record_count", 0) > settings.CLC_BUILD_MIN_RECORDS):
                return None
            from infrastructure.rag.clc_user_index_service import submit_build, index_status_for
            resource_row = {
                "id": f"probe_{digest[:12]}", "workspace_id": settings.DEFAULT_WORKSPACE_ID,
                "storage_uri": stored_path.as_posix(),
                "record_count": verdict.get("record_count"),
            }
            submit_build(resource_row)
            _st = index_status_for(stored_path.as_posix()) or {}
            _st["storage_uri"] = stored_path.as_posix()
            return _st
        except Exception:  # noqa: BLE001 - 进度信息失败不影响预检
            return None


    content = await upload.read()
    original_name = Path(upload.filename or "resource.bin").name
    if not original_name.lower().endswith(".json"):
        return {"valid": False, "error": "仅支持标准 JSON 文件（CSV、JSONL、TXT 暂不支持）"}
    digest = hashlib.sha256(content).hexdigest()
    directory = settings.PROJECT_ROOT / "runtime" / "semantic_resources"
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name) or "resource.bin"
    stored_path = directory / f"{digest[:16]}_{safe_name}"
    if not stored_path.exists():
        stored_path.write_bytes(content)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"valid": False, "error": "文件不是有效的 UTF-8 文本 JSON"}
    field = resource_key
    if field not in _ROWCFG:
        return {"valid": True, "rows": None, "normalized_by": None,
                "note": "配置型资源，仅校验 JSON 可解码", "file_name": original_name}
    try:
        rows = _inspect(stored_path, field=field)
        return {"valid": True, "rows": len(rows), "normalized_by": None, "file_name": original_name,
                "index_build": _index_build_status(stored_path, field, rows)}
    except _RPE as exc:
        from infrastructure.resources.normalize import probe_required_fields
        probe = probe_required_fields(text, field=field)
        if probe["parse_ok"] and probe["must_missing"]:
            _found = "、".join(probe["found_keys"][:10]) or "（无任何字段名——纯值结构）"
            return {"valid": False, "error": (
                f"缺少必要字段：{'；'.join(probe['must_missing'])}。"
                f"文件中检测到的字段：{_found}。"
                f"标准格式：{_ROWCFG.get(field, {}).get('expect')}")}
        # 字段齐备/语法损坏 → 大模型重构（先复用磁盘上已有整理结果）
        conv_path = directory / f"{digest[:16]}_{Path(safe_name).stem}_normalized.json"
        salvaged = None
        if conv_path.is_file():
            try:
                _reused = json.loads(conv_path.read_text(encoding="utf-8"))
                if isinstance(_reused, list) and _reused:
                    salvaged = _reused
            except (json.JSONDecodeError, OSError):
                pass
        if salvaged is None:
            if not settings.RESOURCE_LLM_NORMALIZE_ENABLED:
                return {"valid": False, "error": str(exc)}
            from infrastructure.resources.glm_salvage import maybe_llm_normalize
            salvaged, note = maybe_llm_normalize(
                text, field=field,
                max_bytes=settings.RESOURCE_LLM_NORMALIZE_MAX_BYTES,
                max_rows=settings.RESOURCE_LLM_NORMALIZE_MAX_ROWS,
            )
            if salvaged is None:
                if note in {"oversize", "overrows"}:
                    return {"valid": False, "error": f"{exc}（文件超出大模型自动整理上限）"}
                return {"valid": False, "error": f"{exc}（已尝试大模型自动整理，未能生成有效结构）"}
            conv_path.write_text(json.dumps(salvaged, ensure_ascii=False, indent=2), encoding="utf-8")
        _reg(conv_path, salvaged)
        return {"valid": True, "rows": len(salvaged), "normalized_by": "glm",
                "file_name": original_name, "note": "结构非标准，已由大模型整理为标准格式（提交时直接复用）",
                "index_build": _index_build_status(stored_path, field, salvaged)}


@router.post("/semantic-resources/upload")
async def upload_semantic_resource(
    resource_key: str = Form(...),
    upload: UploadFile = File(...),
) -> Dict[str, Any]:
    """独立上传资源文件并登记入库，返回 resource_id 供复用（不依赖在线测试）。"""
    service = get_integration_service()
    descriptor = await _store_uploaded_resource(resource_key, upload, service)
    resource_id = descriptor.get("resource_id")
    if not resource_id:
        raise HTTPException(status_code=422, detail="该资源字段不支持独立保存到数据库")
    return {
        "code": 0,
        "message": (
            f"资源已上传并保存到数据库（结构非标准，已自动整理为标准格式 {descriptor.get('normalized_rows')} 条）"
            if descriptor.get("normalized_by") == "glm"
            else "资源已上传并保存到数据库"
        ),
        "data": {
            "resource_id": resource_id,
            "file_name": descriptor.get("file_name"),
            "content_hash": descriptor.get("content_hash"),
            "normalized_by": descriptor.get("normalized_by"),
            "normalized_rows": descriptor.get("normalized_rows"),
        },
    }


@router.post("/exports")
def create_export(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        value = export_service.create(str(payload.get("result_record_id") or ""), str(payload.get("format") or "json"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "导出文件已生成", "data": value}


@router.get("/exports/{export_id}/download")
def download_export(export_id: str) -> FileResponse:
    value = export_service.get(export_id)
    if not value:
        raise HTTPException(status_code=404, detail="导出文件不存在或已失效")
    return FileResponse(
        value["path"],
        media_type=value["content_type"],
        filename=value["path"].name,
    )


@router.get("/exports/{export_id}")
def get_export(export_id: str) -> Dict[str, Any]:
    value = export_service.get(export_id)
    if not value:
        raise HTTPException(status_code=404, detail="导出记录不存在或文件已失效")
    public_value = {key: item for key, item in value.items() if key not in {"path", "object_key"}}
    public_value["download_url"] = f"/api/v1/exports/{export_id}/download"
    return {"code": 0, "data": public_value}
