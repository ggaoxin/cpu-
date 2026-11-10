"""MinerU全文读取器（轻量，不做章节解析）。

替代 DocumentParser 的角色：
- PDF → MinerU → MD文件 → 读取全文（不做章节拆分/摘要提取/关键词提取）
- 所有结构化提取（标题/摘要/关键词）交给各功能点的LLM处理
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Any, Dict, Optional

import logging
logger = logging.getLogger(__name__)

MINERU_BIN = os.environ.get("MINERU_BIN", "/root/autodl-tmp/conda/envs/mineru/bin/mineru")  # mineru conda 环境的可执行文件（shebang 指向其 python，base 环境可直接调）


def _gpu_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def run_mineru(pdf_path: str | Path) -> str:
    """调 mineru-api 常驻服务，返回 MD 全文文本（pipeline 后端）。

    内容哈希磁盘缓存优先（重复上传/重跑秒回）；大文件走页切片并行解析。
    失败抛 RuntimeError，由 process_pdf_to_text 捕获后降级 pdfplumber。
    """
    from infrastructure.document_parser.mineru_api_client import mineru_api_client
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF不存在：{pdf_path}")
    from config.settings import settings
    if getattr(settings, "MINERU_PARALLEL_SLICES", False):
        result = mineru_api_client.parse_pdf_parallel(pdf_path)
    else:
        result = mineru_api_client.parse_pdf(pdf_path)
    if not result:
        raise RuntimeError("mineru-api 解析失败")
    md_content = result.get("md_content") or ""
    if not md_content:
        # 退化样本（如单文本框PDF）MD 为空但 content_list 有内容 → 拼接文本兜底
        parts = [str(item.get("text") or "").strip()
                 for item in result.get("content_list") or []
                 if isinstance(item, dict)]
        md_content = "\n\n".join(p for p in parts if p)
    if not md_content:
        raise RuntimeError("mineru-api 返回空 MD")
    logger.info("mineru-api 输出MD(len=%d)：%s", len(md_content), pdf_path.name)
    return md_content


def _clean_md_text(text: str) -> str:
    """清理 MinerU MD 文本的 HTML 标签（保留文本内容），不做章节解析。"""
    text = re.sub(r'<sup>\s*(\[?\d+\]?)\s*</sup>', r'\1', text)
    text = re.sub(r'<sub>\s*(\[?\d+\]?)\s*</sub>', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def read_full_text(md_path: str | Path) -> str:
    """读取MinerU MD文件的全文（清理HTML标签，不做章节解析）。"""
    text = Path(md_path).read_text(encoding="utf-8")
    return _clean_md_text(text)


def _pdfplumber_extract(pdf_path: str | Path) -> Dict[str, Any]:
    """pdfplumber 兜底解析：抽全文 + 首行作标题。几乎不失败。

    MinerU 间歇性解析失败（返回空/nan）或未安装时降级用此，
    保证至少有全文供 LLM 抽技术路线。
    """
    import pdfplumber
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    full_text = repair_glued_english("\n".join(pages).strip(), pdf_path)
    title = ""
    for line in full_text.split("\n"):
        line = line.strip()
        if len(line) >= 5 and not line.lower().startswith(("arxiv", "http", "doi", "preprint")):
            title = line[:120]
            break
    return {"full_text": full_text, "md_path": "", "title": title,
            "doc_type": "unknown", "parser": "pdfplumber_fallback"}


_GLUE_RUN_RE = re.compile(r"[A-Za-z]{12,}")


def repair_glued_english(text: str, pdf_path: str | Path) -> str:
    """英文断词粘连对位修复（MinerU md 与 pdfplumber 兜底共用出口）。

    2026-10-19 首发：mineru 合并 PDF 断行丢词间空格（"are often able to"→
    "areoftenableto"）。2026-11-05 扩展到 pdfplumber 兜底：MinerU 不可用时
    综述等强结构工具降级 pdfplumber，实测 ICLR 2026 论文集（20 篇）丢英文
    词间空格（"We demonstrate"→"Wedemonstrate"），综述 LLM 从粘连文本抄写
    导致节点标题粘连（用户实测 Self-Harmony 一篇）。PyMuPDF 对同批 PDF 实测
    无粘连 → 以其为对位源：粘连串按去空白索引在 PyMuPDF 原文中定位，取带
    空格版本替换；找不到则保持原样（不猜测）。合法长词（如
    "responsibilities"）在原文同为连续串、替换后不变，天然防误伤。
    阈值 12 且含大写（2026-11-05 实测：pdfplumber 粘连保留词首大写，
    "AchievingGold" 被 [a-z] 正则切成 <12 碎片全部漏检）；无粘连 fast-path
    直接返回不开 PDF。合法长词（"internationalization" 20 字符）在 PyMuPDF
    原文同为连续串、对位后内容不变不替换。
    """
    glue_runs = _GLUE_RUN_RE.findall(text)
    if not glue_runs:
        return text
    try:
        import pymupdf
        with pymupdf.open(str(pdf_path)) as doc:
            raw = "".join(page.get_text() for page in doc)
    except Exception:  # noqa: BLE001 - PyMuPDF 读取失败则不修
        return text
    if not raw.strip():
        return text
    stripped = re.sub(r"\s+", "", raw)
    # 去空白索引 → 原文索引映射
    index_map = [i for i, ch in enumerate(raw) if not ch.isspace()]
    def _spaced(needle: str):
        flat = re.sub(r"\s+", "", needle)
        pos = stripped.find(flat)
        if pos < 0 or pos + len(flat) > len(stripped):
            return None
        # 扩边界验证（防子串误配）：取原文区间折叠空白后须与 needle 一致
        candidate = raw[index_map[pos]:index_map[pos + len(flat) - 1] + 1]
        if re.sub(r"\s+", "", candidate) != flat:
            return None
        return candidate
    for run in set(glue_runs):
        fixed = _spaced(run)
        if fixed and fixed != run and " " in fixed:
            text = text.replace(run, fixed)
    return text


def _is_mineru_broken(full_text: str, title: str) -> bool:
    """判断 MinerU 结果是否不可用（空/nan/过短）。"""
    ft = (full_text or "").strip()
    t = (title or "").strip()
    if not ft or len(ft) < 200:
        return True
    if ft.lower() == "nan" or t.lower() == "nan":
        return True
    return False


def process_pdf_to_text(pdf_path: str | Path) -> Dict[str, Any]:
    """PDF → MinerU → MD → 全文。MinerU 失败/空结果时降级 pdfplumber。返回 {full_text, md_path, title, parser}。"""
    try:
        md_content = run_mineru(pdf_path)
        full_text = _clean_md_text(md_content)
        title = ""
        for line in full_text.split('\n'):
            line = line.strip()
            if line.startswith('# ') and not line.startswith('## '):
                title = line.lstrip('# ').strip()
                break
        if _is_mineru_broken(full_text, title):
            logger.warning("MinerU 结果疑似失败(len=%d title=%r)，降级 pdfplumber：%s",
                           len(full_text), title, pdf_path)
            return _pdfplumber_extract(pdf_path)
        return {"full_text": full_text, "md_path": "", "title": title,
                "doc_type": "unknown", "parser": "mineru_pipeline"}
    except Exception as e:  # noqa: BLE001
        logger.warning("MinerU 异常(%s)，降级 pdfplumber：%s", e, pdf_path)
        return _pdfplumber_extract(pdf_path)


def process_md_to_text(md_path: str | Path) -> Dict[str, Any]:
    """MD文件 → 全文。返回 {full_text, md_path, title}。"""
    full_text = read_full_text(md_path)
    title = ""
    for line in full_text.split('\n'):
        line = line.strip()
        if line.startswith('# ') and not line.startswith('## '):
            title = line.lstrip('# ').strip()
            break
    return {
        "full_text": full_text,
        "md_path": str(md_path),
        "title": title,
        "doc_type": "unknown",
    }


def process_to_text(path: str | Path) -> Dict[str, Any]:
    """统一入口：PDF走MinerU，MD直接读取。"""
    path = str(path)
    if path.lower().endswith('.pdf'):
        return process_pdf_to_text(path)
    elif path.lower().endswith('.md'):
        return process_md_to_text(path)
    else:
        # 纯文本
        return {"full_text": open(path, encoding='utf-8').read().strip(), "md_path": path, "title": "", "doc_type": "unknown"}
