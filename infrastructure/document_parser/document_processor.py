"""文档处理器：PDF → MinerU → 解析器 → 结构化文档 → 功能点输入。

打通文件上传到已实现功能点的管线：
1. 调用 MinerU 从 PDF 提取 Markdown 全文
2. 调用 DocumentParser 解析出标题/摘要/关键词/章节
3. 组装成各功能点所需的输入格式
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from infrastructure.document_parser.document_parser import DocumentParser
from infrastructure.document_parser.mineru_api_client import mineru_api_client

logger = logging.getLogger(__name__)

MINERU_BIN = os.environ.get("MINERU_BIN", "/root/autodl-tmp/conda/envs/mineru/bin/mineru")  # 降级备用：mineru-api 常驻服务不可用时回退 CLI


class DocumentProcessor:
    """PDF → MinerU → 解析器 → 结构化文档。"""

    def __init__(self, glm_client=None):
        self.parser = DocumentParser()
        if glm_client:
            self.parser.set_glm(glm_client)

    def process_pdf(self, pdf_path: str | Path, *, end_page_id: int | None = None) -> Dict[str, Any]:
        """四层融合解析：MinerU 结构化 → pdfplumber 兜底 → 正则补全 → LLM 校验清洗。

        层级：
        ① MinerU 首选：成功则优先用 content_list.json 结构化提取（版面准）
        ② pdfplumber 兜底：MinerU 失败/未装时抽全文
        ③ 正则补全：content_list 缺字段时用 MD 正则补；pdfplumber 路径全程正则
        ④ LLM 校验清洗：末端总是调用，校验候选是否真为标题/摘要/关键词并清洗噪声
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 不存在：{pdf_path}")

        # ① 首选 MinerU（HTTP 调 mineru-api 常驻服务，返回 md_content + content_list）
        result = self._run_mineru(pdf_path, end_page_id=end_page_id)
        if result:
            md_content = result.get("md_content") or ""
            blocks = result.get("content_list") or []
            if blocks:
                # ① 结构化提取（MinerU 版面识别，能区分页眉页码）
                doc = self.parser.parse_content_list_blocks(blocks)
                doc = self._regex_fallback(doc, md_text=md_content)  # ③ 正则补全空缺字段
            else:
                doc = self.parser.parse_text(md_content)             # ③ 纯正则
            doc["md_content"] = md_content  # 存 md 文本，替代 _md_path（不落盘）
            doc.setdefault("parser", "mineru_vllm")
        else:
            # ② MinerU 失败 → pdfplumber 抽全文 → 正则提取
            logger.warning("mineru-api 提取失败，降级 pdfplumber 兜底：%s", pdf_path)
            doc = self._pdfplumber_fallback(pdf_path)

        # ④ 末端 LLM 校验+清洗（总是调用，容错不阻塞主流程）
        doc = self.parser.llm_verify_and_clean(doc)
        return doc

    @staticmethod
    def _find_content_list(md_path: str | Path) -> Optional[str]:
        """从 MinerU 的 md 产出路径推导 content_list.json 路径（同目录同 stem）。

        仅 CLI 降级模式使用；HTTP 模式直接从响应取 content_list 数组，无需此方法。
        """
        p = Path(md_path)
        stem = p.stem
        for cand in (p.parent / f"{stem}_content_list.json",
                     p.parent / f"{stem}_content_list_v2.json"):
            if cand.exists():
                return str(cand)
        return None

    def _run_mineru(self, pdf_path: Path, *, end_page_id: int | None = None) -> Optional[Dict[str, Any]]:
        """调用 mineru-api 常驻服务，返回 {md_content, content_list, pages} 或 None。

        主路径走 HTTP（vllm-engine 后端，单文件~9.5s）。失败返回 None，
        由 process_pdf 触发 pdfplumber 兜底。
        """
        return mineru_api_client.parse_pdf(pdf_path, end_page_id=end_page_id)

    def _regex_fallback(self, doc: Dict[str, Any], md_text: str) -> Dict[str, Any]:
        """对 content_list 提取结果中空缺的字段，用 MD 正则结果补全（不覆盖已提取的非空值）。"""
        if doc.get("title") and doc.get("abstract") and doc.get("keywords"):
            return doc  # 字段齐全，无需正则补全
        try:
            regex_doc = self.parser.parse_text(md_text)
        except Exception:  # noqa: BLE001
            return doc
        if not doc.get("title"):
            doc["title"] = regex_doc.get("title", "")
        if not doc.get("abstract"):
            doc["abstract"] = regex_doc.get("abstract", "")
        if not doc.get("keywords"):
            doc["keywords"] = regex_doc.get("keywords", [])
        # content_list 的 sections 为空，优先用正则结果补
        if not doc.get("sections") and regex_doc.get("sections"):
            doc["sections"] = regex_doc["sections"]
        if not doc.get("full_text"):
            doc["full_text"] = regex_doc.get("full_text", "")
        return doc


    def _pdfplumber_fallback(self, pdf_path: Path) -> Dict[str, Any]:
        """pdfplumber 兜底解析：抽全文 → DocumentParser.parse_text 提取结构化字段。

        MinerU 依赖外部 conda 环境且间歇性失败；pdfplumber 纯 Python 几乎不失败，
        抽全文后由 DocumentParser 用正则从「摘要：」/「Abstract」等标志提取摘要、
        关键词、章节，产出与 MinerU 路径同构的 doc，下游无感切换。
        """
        import pdfplumber
        pages = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        full_text = "\n".join(pages).strip()
        if not full_text:
            # 扫描件/损坏件：两路都提取不到文字，返回空 doc 而非抛异常，
            # 让批量 gather 优雅降级（下游取空 text），避免单文件拖垮整批。
            logger.warning("两路解析均无文本（扫描件/损坏件），返回空 doc：%s", pdf_path)
            return {"title": "", "abstract": "", "keywords": [],
                    "sections": [], "full_text": "", "md_content": "",
                    "parser": "empty_fallback"}
        doc = self.parser.parse_text(full_text)
        doc["md_content"] = ""
        doc["parser"] = "pdfplumber_fallback"
        logger.info("pdfplumber 兜底成功(len=%d, abstract=%d字)：%s",
                    len(full_text), len(doc.get("abstract") or ""), pdf_path)
        return doc

    def process_pdfs(self, pdf_paths: List[str | Path]) -> List[Dict[str, Any]]:
        """批量处理多个 PDF。"""
        return [self.process_pdf(p) for p in pdf_paths]

    def to_text_input(self, doc: Dict[str, Any]) -> str:
        """将结构化文档转为单文本功能点的输入格式（JSON）。

        适用于：ac_zh, ac_en, kw_zh, kw_en, rq_identify 等单篇功能点。
        """
        import json
        title = doc.get("title", "")
        abstract = doc.get("abstract", "")
        keywords = doc.get("keywords", [])
        return json.dumps({
            "ch_name": title,
            "ch_abstract": abstract,
            "keywords": [{"ch_name": k, "en_name": k} for k in keywords],
        }, ensure_ascii=False)

    def to_multi_text_input(self, docs: List[Dict[str, Any]]) -> List[str]:
        """将多个结构化文档转为多篇功能点的输入格式。

        适用于：多篇功能点。
        """
        return [f"{d.get('title', '')}\n{d.get('abstract', '')}" for d in docs]

    def to_full_text(self, doc: Dict[str, Any]) -> str:
        """返回文档全文（MinerU 提取的 Markdown 原文，含 ``##`` 章节标题）。

        适用于需要整篇全文的功能点（如基金项目语步识别 mr_zh_fund），区别于
        ``to_text_input`` 只取标题/摘要/关键词。优先读 MinerU 产出的 .md 原文，
        以保留 ``##`` 标题层级供下游章节感知切块使用；读不到则回退拼接章节正文。
        """
        md_content = doc.get("md_content")
        if md_content:
            text = md_content.strip()
            if text:
                return text
        # 兜底：按章节拼接正文
        parts = []
        for sec in doc.get("sections", []):
            heading = sec.get("heading", "").strip()
            body = sec.get("text", "").strip()
            if heading:
                parts.append(f"## {heading}")
            if body:
                parts.append(body)
        return "\n".join(parts).strip()


# 单例
_document_processor: Optional[DocumentProcessor] = None


def get_document_processor() -> DocumentProcessor:
    """获取文档处理器单例（延迟初始化，注入 GLM）。"""
    global _document_processor
    if _document_processor is None:
        try:
            from infrastructure.llm.glm_client import glm_client
            _document_processor = DocumentProcessor(glm_client)
        except Exception:
            _document_processor = DocumentProcessor()
    return _document_processor
