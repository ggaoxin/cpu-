"""表现层：控制器基类与共享依赖。

提供两种端点：
1. POST /api/v1/<item>/<code> — 文本输入（原有，接收 JSON body）
2. POST /api/v1/<item>/<code>/file — 文件上传（新增，接收 PDF → MinerU → 解析器 → 功能点）
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from application.dto.common_dto import SemanticRequest, SemanticResponse
from application.service.semantic_service import SemanticApplicationService
from config.functional_points import FunctionalPoint, get_functional_point, list_functional_points
from infrastructure.llm.glm_client import glm_client
from infrastructure.rule_engine.rule_loader import rule_loader

logger = logging.getLogger(__name__)

# 应用层服务单例
_semantic_service = SemanticApplicationService(glm=glm_client, rule_loader=rule_loader)


def get_semantic_service() -> SemanticApplicationService:
    return _semantic_service


def build_item_router(
    item_code: str,
    item_name: str,
    points: List[FunctionalPoint],
    service: SemanticApplicationService = Depends(get_semantic_service),
) -> APIRouter:
    """构建路由器：文本端点 + 文件上传端点。"""
    router = APIRouter(prefix=f"/{item_code}", tags=[item_name])

    for fp in points:
        # --- 文本端点（原有）---
        def _endpoint(
            request: SemanticRequest,
            _code: str = fp.code,
            _service: SemanticApplicationService = Depends(get_semantic_service),
        ) -> SemanticResponse:
            result = _service.execute(_code, request)
            return _to_response(result)

        _endpoint.__name__ = f"{fp.code}_endpoint"
        router.add_api_route(
            path=f"/{fp.code}", endpoint=_endpoint, methods=["POST"],
            name=fp.name, summary=f"{fp.name}（文本输入）",
            description=fp.description, response_model=SemanticResponse,
        )

        # --- 文件上传端点（新增）---
        def _file_endpoint(
            file: UploadFile = File(..., description="PDF 文件"),
            _code: str = fp.code,
            _input_type: str = fp.input_type,
            _service: SemanticApplicationService = Depends(get_semantic_service),
        ) -> SemanticResponse:
            return _process_file_upload(file, _code, _input_type, _service)

        _file_endpoint.__name__ = f"{fp.code}_file_endpoint"
        router.add_api_route(
            path=f"/{fp.code}/file", endpoint=_file_endpoint, methods=["POST"],
            name=f"{fp.name}（文件上传）",
            summary=f"{fp.name}（PDF上传→MinerU→解析→处理）",
            description=f"上传 PDF 文件，自动提取标题/摘要/关键词后执行{fp.name}。",
            response_model=SemanticResponse,
        )

    return router


def _process_file_upload(
    file: UploadFile,
    code: str,
    input_type: str,
    service: SemanticApplicationService,
) -> SemanticResponse:
    """文件上传处理：PDF → MinerU → 解析器 → 组装输入 → 调用功能点。"""
    from infrastructure.document_parser.document_processor import get_document_processor

    # 保存上传文件到临时路径
    suffix = os.path.splitext(file.filename or "upload.pdf")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = file.file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        processor = get_document_processor()
        doc = None

        if input_type == "multi_text":
            # 多篇功能点：暂不支持多文件上传
            # 单文件也走 multi_text（texts=[单篇]）
            doc = processor.process_pdf(tmp_path)
            text_input = processor.to_multi_text_input([doc])
            request = SemanticRequest(texts=text_input)
        elif code == 'cd_identify':
            # 概念定义识别需全文（正文定义句），走极速版 PyMuPDF（扫描/双栏内置回退
            # mineru），与 /files 批量路径一致；不走 process_pdf(mineru)+to_text_input
            # （仅标题/摘要/关键词 JSON，无正文 → 正文定义句全丢召回 0）。
            # 传 _source_pdf_path 供 light 漏抽时回退 mineru 重抽（参考 rq-detect）。
            from infrastructure.document_parser.upload_reader import extract_bytes
            with open(tmp_path, 'rb') as f:
                _content = f.read()
            text_input = extract_bytes(_content, file.filename or 'upload.pdf', light=True) or ""
            request = SemanticRequest(text=text_input, params={"_source_pdf_path": tmp_path})
        elif code.startswith('ner_'):
            # NER 需全文识别实体（实体在正文，不只摘要），走极速版 PyMuPDF
            # （扫描/双栏内置回退 mineru），不走 to_text_input（标题+摘要+关键词
            # JSON 无正文 → 召回 0）。relation 三元组也在正文，一并走极速版。
            from infrastructure.document_parser.upload_reader import extract_bytes
            with open(tmp_path, 'rb') as f:
                _content = f.read()
            text_input = extract_bytes(_content, file.filename or 'upload.pdf', light=True) or ""
            request = SemanticRequest(text=text_input)
        else:
            # 单篇功能点：提取标题+摘要+关键词 → JSON → text
            doc = processor.process_pdf(tmp_path)
            if code in ('mr_zh_fund', 'cr_intent', 'cr_sentiment'):
                # 需要整篇全文（含 ## 章节标题）的功能点：基金语步、引用句识别。
                # 引用句需全文扫描 [n]/(作者,年份) 标记，to_text_input 只给标题/摘要/
                # 关键词 JSON 会导致召回 0。
                text_input = processor.to_full_text(doc)
            else:
                text_input = processor.to_text_input(doc)
            request = SemanticRequest(text=text_input)

        result = service.execute(code, request)
        # 附加文档元数据到 evidence（concept_definition 走极速版无 doc，跳过）
        if result.success and doc is not None:
            result.evidence = (result.evidence or []) + [{
                "doc_title": doc.get("title", ""),
                "doc_type": doc.get("doc_type", ""),
                "doc_keywords": doc.get("keywords", []),
                "doc_section_count": len(doc.get("sections", [])),
            }]
        return _to_response(result)

    except Exception as e:
        logger.exception("文件上传处理失败 [%s]", code)
        from domain.entity.base import SemanticResult
        result = SemanticResult(code=code, name=code)
        result.success = False
        result.error = f"文件处理失败：{e}"
        return _to_response(result)
    finally:
        os.unlink(tmp_path)


def _to_response(result) -> SemanticResponse:
    return SemanticResponse(
        code=result.code, name=result.name, success=result.success,
        data=result.data, evidence=result.evidence,
        confidence=result.confidence, error=result.error,
    )

