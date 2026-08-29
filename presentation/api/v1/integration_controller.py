"""当前 Vue 使用的 19 个稳定接口，以及任务、历史和集合查询接口。"""
from __future__ import annotations

import asyncio
import json
import hashlib
import re
import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from application.service.tool_integration_service import ToolIntegrationService
from application.service.deep_cluster_evaluation_service import DeepClusterEvaluationService
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


async def _abstract_text(processor, tmp_path: str, content: bytes | None = None) -> tuple[str, str]:
    """摘要文本+标题提取。light 模式优先 paper_abstract_extractor（规则优先+评分+
    LLM 兜底，毫秒级正则，无 :8899）；扫描件/封面无摘要/低置信时回退 mineru
    process_pdf 保质量。full 模式直接走 mineru。返回 (abstract, title)。

    paper_abstract_extractor 只提 abstract 不提 title；light 命中时 title 留空，
    前端按文件名展示规则（record.file_name 优先）显示文件名。content 参数保留兼容
    但不再使用（paper_abstract_extractor 从 tmp_path 路径读 PDF）。"""
    abstract = ""
    title = ""
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
                abstract, title = await _abstract_text(processor, tmp_path, content)
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
            abstract, title = await _abstract_text(processor, tmp_path, content)
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
    if field in SEMANTIC_RESOURCE_FIELDS:
        meta = {"content_type": upload.content_type, "size_bytes": len(content)}
        record_count = None
        verdict = None
        # CLC 资源：算 verdict 写 metadata.clc_verdict + record_count（供 _resource_context 分治）
        try:
            entries = json.loads(content.decode("utf-8-sig"))
            if isinstance(entries, list):
                from infrastructure.rag.clc_user_index_service import compute_clc_verdict
                verdict = compute_clc_verdict(entries, len(content))
                meta["clc_verdict"] = verdict
                record_count = verdict["record_count"]
        except Exception:  # noqa: BLE001
            pass
        stored = service.resource_repository.register_semantic_resource(
            settings.DEFAULT_WORKSPACE_ID,
            {
                "resource_key": field,
                "name": original_name,
                "version": f"upload-{digest[:12]}",
                "language": None,
                "status": "current",
                "source_type": "upload",
                "storage_uri": stored_path.as_posix(),
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
                "result": record.get("result") or {},
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
        if not uploads:
            raise HTTPException(status_code=422, detail=f"缺少上传字段：{field}")
        if not multiple and len(uploads) != 1:
            raise HTTPException(status_code=422, detail="单文件接口只能上传一个文件")
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
        upload_limit_mb = 80 if tool_id == "structured-review" else settings.MAX_UPLOAD_SIZE_MB
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
        "只输出JSON:{\"data\":[{\"head\":\"\",\"relation\":\"\",\"dependent\":\"\",\"sentence_id\":\"SENT-001\"}]}"
    )
    try:
        out = glm_client.chat_json(system, f"分析以下文本的依存句法:\n{text}", timeout=30.0, max_tokens=2000)
        arcs = out.get("data", out) if isinstance(out, dict) else []
        if not isinstance(arcs, list):
            arcs = []
        return {"code": 0, "message": f"已生成 {len(arcs)} 条依存弧", "data": arcs}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"依存句法分析失败: {exc}") from exc


@router.post("/cluster/deep/evaluate")
async def evaluate_deep_cluster(
    request: Request,
    service: ToolIntegrationService = Depends(get_integration_service),
) -> Dict[str, Any]:
    """Run an independent, gold-backed clustering evaluation.

    This does not alter or block the user's ordinary document clustering task.
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
        value = DeepClusterEvaluationService(service).evaluate(payload)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"code": 0, "message": "success", "data": value}


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
            # NER 记录名加时间后缀(题目/文件名 · 年-月-日 时:分)
            _time = str(task.get("created_at") or "")[:16].replace("T", " ")
            if not _name:
                _name = _time
            elif _time:
                _name = f"{_name} · {_time}"
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
                phrase_sets = []
                for cluster in result.get("clusters") or []:
                    if not isinstance(cluster, dict):
                        continue
                    phrase_sets.append({
                        "cluster_id": cluster.get("cluster_id"),
                        "phrases": [t for t in (_clean_cluster_term(v) for v in (cluster.get("representative_terms") or cluster.get("keywords") or [])) if t],
                    })
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
    return {"code": 0, "data": task_repository.healthcheck(), "created_at": datetime.now(timezone.utc).isoformat()}


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


@router.get("/semantic-resources/{resource_id}")
def get_semantic_resource(resource_id: str) -> Dict[str, Any]:
    value = resource_service.get_semantic_resource(resource_id)
    if not value:
        raise HTTPException(status_code=404, detail="语义资源不存在")
    return {"code": 0, "data": value}


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
        "message": "资源已上传并保存到数据库",
        "data": {
            "resource_id": resource_id,
            "file_name": descriptor.get("file_name"),
            "content_hash": descriptor.get("content_hash"),
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
