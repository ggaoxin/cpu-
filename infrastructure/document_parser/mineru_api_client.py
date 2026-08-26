"""MinerU 常驻 API 服务的 HTTP 客户端（替代 CLI subprocess 调用）。

通过 mineru-api 常驻服务的 /file_parse 端点调用 vllm-engine 后端，
单文件纯推理约 9.5s（vs CLI pipeline 43s），批量并发吞吐 8 倍。
响应 JSON 直接含 md_content 与 content_list 数组，无需落盘读文件。

参考 infrastructure/llm/glm_client.py 的 httpx + 超时 + 单例模式。
httpx.Client 线程安全，可被多个 asyncio.to_thread 并发共享（连接池复用）。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class MineruApiClient:
    """MinerU 常驻 API 服务的 HTTP 客户端。"""

    def __init__(self) -> None:
        # 未配置或服务不可达时也允许构造（服务可启动）；真正依赖在 parse_pdf 中容错。
        self.base_url = settings.MINERU_API_URL.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(settings.MINERU_API_TIMEOUT, connect=10.0),
        )
        self._backend = settings.MINERU_BACKEND

    def healthy(self) -> bool:
        """mineru-api 是否可达（GET /health）。供启动期检查，不抛异常。"""
        try:
            r = self._client.get("/health", timeout=3.0)
            return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def parse_pdf(
        self, pdf_path: str | Path, *, end_page_id: int | None = None,
        start_page_id: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """调 /file_parse 解析单个 PDF。

        end_page_id：限定解析到的页（0-indexed 闭区间 [start_page_id, end_page_id]，含两端页）。
        摘要语步只需首页 abstract，传 end_page_id 限定前若干页即可降低计算量；None=解析全文。
        返回 {md_content, content_list, pages}；失败/超时返回 None
        （由上层 process_pdf 触发 pdfplumber 兜底）。
        """
        pdf_path = Path(pdf_path)
        try:
            with open(pdf_path, "rb") as f:
                data = f.read()
        except Exception as e:  # noqa: BLE001
            logger.error("读取 PDF 失败：%s (%s)", pdf_path, e)
            return None

        logger.info("mineru-api 解析：%s pages[%d-%s] (backend=%s, %.1fMB)",
                    pdf_path.name, start_page_id,
                    end_page_id if end_page_id is not None else "EOF",
                    self._backend, len(data) / 1048576)
        form_data = {
            "backend": self._backend,
            "return_md": "true",
            "return_content_list": "true",
        }
        if end_page_id is not None:
            # 0-indexed 闭区间 [start_page_id, end_page_id]，限定页范围降低计算量
            form_data["start_page_id"] = str(start_page_id)
            form_data["end_page_id"] = str(end_page_id)
        try:
            resp = self._client.post(
                "/file_parse",
                data=form_data,
                files={"files": (pdf_path.name, data, "application/pdf")},
            )
        except httpx.TimeoutException:
            logger.error("mineru-api 超时（%ss）：%s", settings.MINERU_API_TIMEOUT, pdf_path.name)
            return None
        except Exception as e:  # noqa: BLE001
            logger.error("mineru-api 请求异常：%s (%s)", pdf_path.name, e)
            return None

        if resp.status_code != 200:
            logger.error("mineru-api 返回 %s：%s", resp.status_code, resp.text[-300:])
            return None

        try:
            payload = resp.json()
        except Exception as e:  # noqa: BLE001
            logger.error("mineru-api 响应解析失败：%s", e)
            return None

        # MinerU 3.x 异步协议：POST /file_parse 返回任务信封 {task_id, status, result_url}，
        # 需轮询任务状态再取结果；旧协议直接返回 results。
        if "results" not in payload and payload.get("task_id"):
            task_id = str(payload["task_id"])
            deadline = time.monotonic() + settings.MINERU_API_TIMEOUT
            status = str(payload.get("status") or "")
            while status not in {"completed", "failed", "error"}:
                if time.monotonic() > deadline:
                    logger.error("mineru-api 任务轮询超时（%ss）：%s %s",
                                 settings.MINERU_API_TIMEOUT, task_id, pdf_path.name)
                    return None
                time.sleep(2.0)
                try:
                    poll = self._client.get(f"/tasks/{task_id}", timeout=30.0)
                    status = str(poll.json().get("status") or "") if poll.status_code == 200 else ""
                except Exception:  # noqa: BLE001
                    status = ""
            if status != "completed":
                logger.error("mineru-api 任务失败（status=%s）：%s %s", status, task_id, pdf_path.name)
                return None
            try:
                result_resp = self._client.get(f"/tasks/{task_id}/result", timeout=120.0)
                payload = result_resp.json()
            except Exception as e:  # noqa: BLE001
                logger.error("mineru-api 取结果失败：%s %s (%s)", task_id, pdf_path.name, e)
                return None

        # results: {<文件名>: {md_content, content_list, ...}}，取第一个文件
        results = payload.get("results") or {}
        if not results:
            logger.error("mineru-api 响应无 results：%s", pdf_path.name)
            return None
        first = next(iter(results.values()))
        if not isinstance(first, dict):
            return None

        md_content = first.get("md_content") or ""
        content_list = first.get("content_list") or []
        # content_list 可能是字符串（需再 json.loads）或已是 list
        if isinstance(content_list, str):
            import json
            try:
                content_list = json.loads(content_list)
            except Exception:  # noqa: BLE001
                content_list = []

        if not md_content and not content_list:
            logger.warning("mineru-api 返回空内容：%s", pdf_path.name)
            return None

        pages = _count_pages(data)
        return {
            "md_content": md_content,
            "content_list": content_list if isinstance(content_list, list) else [],
            "pages": pages,
        }

    # ---- 页切片并行解析：CPU pipeline 单请求顺序处理页面且吃不满所有核，
    # 大文件按页段并发提交（mineru-api 原生支持 start_page_id/end_page_id），
    # 多个页段请求在服务端并行推理，实测可将大 PDF 解析时间压缩到 1/2~1/3。
    PARALLEL_MIN_PAGES = 24   # 低于此页数不值得切片，直接单请求
    SLICE_PAGES = 64          # 每片页数（对齐 mineru-api 内部 64 页处理窗口）

    def parse_pdf_parallel(
        self, pdf_path: str | Path, *, max_concurrency: int | None = None,
        slice_pages: int | None = None,
    ) -> Optional[Dict[str, Any]]:
        """大 PDF 页切片并行解析；小 PDF 自动退化为单请求。

        返回结构与 parse_pdf 相同（md_content 按页序拼接、content_list 的
        page_idx 已重编为全文档页号）；任一片失败返回 None。
        """
        pdf_path = Path(pdf_path)
        try:
            with open(pdf_path, "rb") as f:
                data = f.read()
        except Exception as e:  # noqa: BLE001
            logger.error("读取 PDF 失败：%s (%s)", pdf_path.name, e)
            return None
        total = _count_pages(data)
        slice_n = slice_pages or self.SLICE_PAGES
        if total <= max(self.PARALLEL_MIN_PAGES, slice_n):
            return self.parse_pdf(pdf_path)

        ranges = [(s, min(s + slice_n - 1, total - 1))
                  for s in range(0, total, slice_n)]
        workers = max_concurrency or min(
            getattr(settings, "MINERU_MAX_CONCURRENCY", 3), len(ranges))
        logger.info("mineru-api 并行分片：%s %d页 → %d片(每片%d页) 并发%d",
                    pdf_path.name, total, len(ranges), slice_n, workers)

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self.parse_pdf, pdf_path,
                            start_page_id=s, end_page_id=e): (s, e)
                for s, e in ranges
            }
            slices: Dict[tuple, Optional[Dict[str, Any]]] = {}
            for future, key in futures.items():
                slices[key] = future.result()

        md_parts, content_all = [], []
        for s, e in ranges:
            piece = slices.get((s, e))
            if not piece:
                logger.error("mineru-api 分片失败：%s pages[%d-%d]", pdf_path.name, s, e)
                return None
            md_parts.append(str(piece.get("md_content") or "").strip())
            for item in piece.get("content_list") or []:
                if isinstance(item, dict):
                    # 分片内 page_idx 相对片首，重编为全文档页号
                    try:
                        item["page_idx"] = int(item.get("page_idx", 0)) + s
                    except (TypeError, ValueError):
                        item["page_idx"] = s
                content_all.append(item)

        md_content = "\n\n".join(p for p in md_parts if p)
        if not md_content and not content_all:
            return None
        return {
            "md_content": md_content,
            "content_list": content_all,
            "pages": total,
        }


def _count_pages(data: bytes) -> int:
    """从 PDF 字节流读页数（pypdfium2，毫秒级不耗 GPU）。供并发调度估算页数预算。"""
    try:
        import pypdfium2
        doc = pypdfium2.PdfDocument(data)
        n = len(doc)
        doc.close()
        return n
    except Exception:  # noqa: BLE001
        return 1


# 单例
mineru_api_client = MineruApiClient()
