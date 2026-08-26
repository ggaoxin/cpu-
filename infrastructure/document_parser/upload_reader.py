"""浏览器上传文件的轻量文本提取；PDF 优先用 pypdf，DOCX 使用标准库解析。"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List
import logging
from xml.etree import ElementTree

from fastapi import UploadFile

from config.settings import settings

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".json", ".csv", ".xlsx"}
logger = logging.getLogger(__name__)


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _docx_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 200 * 1024 * 1024:
            raise ValueError("DOCX 解压后内容过大")
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs = []
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _pdf_text(content: bytes) -> str:
    # 优先用 MinerU：产出带 ## 标题的 markdown，供基金语步等功能的章节溯源；
    # 失败/不可用则回退 pypdf 纯文本（无 ## 标题，来源会标"全文"）。
    try:
        import os as _os
        import tempfile as _tempfile
        from infrastructure.document_parser.mineru_reader import process_pdf_to_text
        with _tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            doc = process_pdf_to_text(tmp_path)
            text = (doc.get("full_text") or "").strip()
            if text:
                return text
        finally:
            try:
                _os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:  # noqa: BLE001
        pass
    # 回退：pypdf 纯文本
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("解析 PDF 需要安装 pypdf 或 MinerU") from exc
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def _page_is_dual_column(page) -> bool:
    """右栏正文块(x0>页宽*0.45 且 <页宽*0.95)文本量占比>25% → 该页双栏。

    PyMuPDF 对双栏 PDF 跨栏错拼会拆断句子（如"机器学习"被换行拆成"机器学"+"习"），
    破坏 rq-detect/definition-detect 等句式识别工具，故双栏页需回退 mineru。
    """
    blocks = page.get_text("blocks")
    if not blocks:
        return False
    pw = page.rect.width
    right_chars = 0
    total_chars = 0
    for b in blocks:
        txt = b[4].strip() if len(b) > 4 else ""
        if not txt:
            continue
        total_chars += len(txt)
        if b[0] > pw * 0.45 and b[0] < pw * 0.95:
            right_chars += len(txt)
    return total_chars > 0 and right_chars / total_chars > 0.25


def _layout_text_from_bytes(content: bytes, max_pages: int | None = None) -> str:
    """版面感知分栏读取（paper_abstract_extractor）：左栏读完再读右栏，不跨栏错拼。

    双栏 PDF 用 sort=True 会把同 y 的左右栏行交错（如左栏竖排标题单字插进右栏正文），
    破坏 rq-detect 等句式识别。extract_layout_text 收 pdf_path，故写临时文件再调。
    比 mineru 快 ~100x（0.3-1.3s vs ~99s/篇）。返空串由调用方按扫描件回退 mineru。
    """
    try:
        from paper_abstract_extractor.layout import extract_layout_text
    except ImportError:
        logger.warning("paper_abstract_extractor 未装，双栏无法走分栏读取")
        return ""
    import os as _os, tempfile as _tf
    fd, path = _tf.mkstemp(suffix=".pdf")
    try:
        with _os.fdopen(fd, "wb") as f:
            f.write(content)
        return extract_layout_text(path, max_pages=max_pages) or ""
    except Exception as e:
        logger.warning("版面感知分栏读取失败: %s", e)
        return ""
    finally:
        try:
            _os.remove(path)
        except OSError:
            pass


def _pymupdf_text(content: bytes) -> str:
    """PyMuPDF 直抽 PDF 内嵌文本（不经神经网络，无 ## 标题结构）。

    统一三路分流（light 模式，所有文件读取统一这套）：
    (1) 单栏 → sort=True 直抽（毫秒级）；
    (2) 双栏 → paper_abstract_extractor 版面感知分栏读取（左栏读完再读右栏，
        避免 sort=True 跨栏错拼拆句，0.3-1.3s/篇）；
    (3) 扫描件/图片页（内嵌文字过少）或上述返空 → 回退 mineru OCR。
    pymupdf 未装也返空由调用方回退。
    """
    try:
        import pymupdf
    except ImportError:
        return ""  # 未装 pymupdf，由调用方回退 _pdf_text（mineru/pypdf）
    parts: List[str] = []
    npages = 0
    dual_pages = 0
    with pymupdf.open(stream=content, filetype="pdf") as doc:
        npages = doc.page_count
        for page in doc:
            if _page_is_dual_column(page):
                dual_pages += 1
            parts.append(page.get_text(sort=True))  # sort 按 y 坐标，单栏改善阅读顺序
    full = "\n".join(p for p in parts if p and p.strip())
    # 扫描件兜底：平均每页 < 20 字符 → 疑似扫描件/图片页，回退 mineru OCR
    if npages and len(full) < npages * 20:
        logger.info("pymupdf 回退 mineru：扫描件/文字过少（%d字/%d页）", len(full), npages)
        return ""
    # 双栏：走版面感知分栏读取（不再回退 mineru，快 ~100x 且句子完整）
    if npages and dual_pages >= max(2, npages * 0.5):
        layout = _layout_text_from_bytes(content)
        if layout:
            logger.info("pymupdf 双栏走版面感知分栏读取（%d/%d 页双栏）", dual_pages, npages)
            return layout
        logger.info("pymupdf 双栏分栏读取失败，回退 mineru（%d/%d 页双栏）", dual_pages, npages)
        return ""
    return full


def _pymupdf_abstract(content: bytes, limit: int = 8000) -> str:
    """PyMuPDF 抽前 limit 字（摘要通常在前 2-3 页），供 abstract-move 极速用。

    与 _pymupdf_text 同款双栏/扫描回退（返空由调用方回退 mineru process_pdf），
    但只逐页累积到 limit 字即停，更省。摘要语步只需摘要，不必抽全文。
    """
    try:
        import pymupdf
    except ImportError:
        return ""
    parts: List[str] = []
    npages = 0
    dual_pages = 0
    total = 0
    with pymupdf.open(stream=content, filetype="pdf") as doc:
        for page in doc:
            npages += 1
            if _page_is_dual_column(page):
                dual_pages += 1
            txt = page.get_text(sort=True)
            if txt and txt.strip():
                parts.append(txt)
                total += len(txt)
            if total >= limit:
                break
    full = "\n".join(parts)
    # 扫描件兜底：平均每页 < 20 字符 → 回退 mineru OCR
    if npages and len(full) < npages * 20:
        logger.info("pymupdf 回退 mineru（摘要）：扫描件/文字过少（%d字/%d页）", len(full), npages)
        return ""
    # 双栏：走版面感知分栏读取（不再回退 mineru），与 _pymupdf_text 统一三路分流
    if npages and dual_pages >= max(2, npages * 0.5):
        layout = _layout_text_from_bytes(content)
        if layout:
            logger.info("pymupdf 双栏走版面感知分栏读取（摘要，%d/%d 页双栏）", dual_pages, npages)
            return layout[:limit] if len(layout) > limit else layout
        logger.info("pymupdf 双栏分栏读取失败，回退 mineru（摘要，%d/%d 页双栏）", dual_pages, npages)
        return ""
    return full[:limit] if len(full) > limit else full


def _xlsx_text(content: bytes) -> str:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("解析 XLSX 需要安装 openpyxl") from exc
    workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    rows = []
    for sheet in workbook.worksheets:
        rows.append(f"## {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values = [str(value).strip() for value in row if value not in (None, "")]
            if values:
                rows.append("\t".join(values))
    return "\n".join(rows)


def extract_bytes(content: bytes, filename: str, *, light: bool | None = None) -> str:
    suffix = Path(filename or "upload.txt").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式：{suffix or '无扩展名'}")
    if suffix == ".pdf":
        # light=None 跟全局 PDF_EXTRACT_MODE；light=True 走 PyMuPDF 直抽（纯文本工具轻量），
        # 扫描件/抽空时回退 _pdf_text（mineru OCR）；light=False 强制 mineru（强结构工具）
        use_light = light if light is not None else (settings.PDF_EXTRACT_MODE == "light")
        if use_light:
            text = _pymupdf_text(content)
            if text:
                return text
            # PyMuPDF 抽空（双栏/扫描件）回退 mineru OCR，经 PageBudgetPool 限流，
            # 避免多任务并发大双栏/扫描 PDF 回退时绕过在途页数预算压 GPU。
            # light=False 路径的 pool 由调用方(is_path)负责，此处只管 light 回退路径。
            from infrastructure.document_parser.mineru_api_client import _count_pages
            from infrastructure.document_parser.concurrency_pool import get_page_budget_pool
            _pages = _count_pages(content)
            _pool = get_page_budget_pool()
            _pool.acquire(_pages)
            try:
                return _pdf_text(content)
            finally:
                _pool.release(_pages)
        return _pdf_text(content)  # light=False 强制 mineru（调用方 is_path 已包 pool）
    if suffix == ".docx":
        return _docx_text(content)
    if suffix == ".xlsx":
        return _xlsx_text(content)
    text = _decode(content)
    if suffix == ".json":
        try:
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return text
    if suffix == ".csv":
        rows = csv.reader(io.StringIO(text))
        return "\n".join("\t".join(cell.strip() for cell in row) for row in rows)
    return text


async def extract_upload(upload: UploadFile, max_size_mb: int | None = None, *, light: bool | None = None) -> Dict[str, str]:
    limit_mb = max_size_mb or settings.MAX_UPLOAD_SIZE_MB
    maximum = limit_mb * 1024 * 1024
    content = await upload.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError(f"文件 {upload.filename} 超过 {limit_mb}MB 限制")
    # extract_bytes 含 PyMuPDF 直抽 / mineru HTTP（回退路径经 PageBudgetPool），
    # 均为同步阻塞调用，放 to_thread 避免阻塞 event loop —— 否则多个 /file 单文件
    # 请求会串行（同步 extract_bytes 独占 event loop），并发请求互相拖累。
    text = (await asyncio.to_thread(extract_bytes, content, upload.filename or "upload.txt", light=light)).strip()
    if not text:
        raise ValueError(f"未能从文件 {upload.filename} 提取文本")
    return {
        "file_name": upload.filename or "upload.txt",
        "media_type": upload.content_type or "application/octet-stream",
        "text": text,
    }


async def extract_uploads(uploads: Iterable[UploadFile], max_size_mb: int | None = None, *, light: bool | None = None) -> List[Dict[str, str]]:
    """并发提取多个上传文件的文本（页数预算自适应调度）。

    小文件自动高并发、大文件自动串行（PageBudgetPool 控制）。
    PDF 走 mineru-api（耗GPU，受页数预算约束）；非 PDF 走本地解析（pages=1）。
    light 透传给 extract_bytes（None 跟全局、True PyMuPDF、False 强制 mineru）。
    """
    import asyncio
    from infrastructure.document_parser.concurrency_pool import get_page_budget_pool
    from infrastructure.document_parser.mineru_api_client import _count_pages

    uploads = list(uploads)
    if len(uploads) <= 1:
        return [await extract_upload(u, max_size_mb=max_size_mb, light=light) for u in uploads]

    limit_mb = max_size_mb or settings.MAX_UPLOAD_SIZE_MB
    maximum = limit_mb * 1024 * 1024

    # 1. 并发读所有文件 bytes + 页数（pypdfium2 读页数毫秒级，不耗GPU）
    async def read_one(upload: UploadFile):
        content = await upload.read(maximum + 1)
        if len(content) > maximum:
            raise ValueError(f"文件 {upload.filename} 超过 {limit_mb}MB 限制")
        name = upload.filename or "upload.txt"
        pages = _count_pages(content) if name.lower().endswith(".pdf") else 1
        return upload, content, pages

    items = await asyncio.gather(*[read_one(u) for u in uploads])

    # 2. 页数预算并发提取（extract_bytes 同步阻塞，放 to_thread）
    pool = get_page_budget_pool()

    async def extract_one(upload: UploadFile, content: bytes, pages: int) -> Dict[str, str]:
        await asyncio.to_thread(pool.acquire, pages)
        try:
            name = upload.filename or "upload.txt"
            text = await asyncio.to_thread(extract_bytes, content, name, light=light)
            text = (text or "").strip()
            if not text:
                raise ValueError(f"未能从文件 {name} 提取文本")
            return {
                "file_name": name,
                "media_type": upload.content_type or "application/octet-stream",
                "text": text,
            }
        finally:
            await asyncio.to_thread(pool.release, pages)

    return await asyncio.gather(*[extract_one(*i) for i in items])


async def save_uploads_to_temp(uploads: Iterable[UploadFile], max_size_mb: int | None = None) -> List[Dict[str, str]]:
    """把上传文件原样落盘为临时文件，返回路径（不预解析文本）。

    供 deep-cluster / structured-review 的 _parse_papers_concurrent 并发处理：
    MinerU 解析 + dual_view LLM 双轴抽取在并发线程池中执行，避免在请求入口
    串行预解析。调用方（tool_integration_service.execute）负责在任务结束后
    清理带 ``_temp`` 标记的临时文件。
    """
    import tempfile

    results: List[Dict[str, str]] = []
    for upload in uploads:
        limit_mb = max_size_mb or settings.MAX_UPLOAD_SIZE_MB
        maximum = limit_mb * 1024 * 1024
        content = await upload.read(maximum + 1)
        if len(content) > maximum:
            raise ValueError(f"文件 {upload.filename} 超过 {limit_mb}MB 限制")
        suffix = Path(upload.filename or "upload.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        results.append({
            "file_name": upload.filename or "upload",
            "media_type": upload.content_type or "application/octet-stream",
            "path": tmp_path,
            "_temp": True,
        })
    return results
