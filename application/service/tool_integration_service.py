"""面向 Vue 的任务编排服务：输入适配、算法调用、结果归一化与持久化。"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
from threading import Event
from typing import Any, Dict, List, Optional, Tuple

from application.dto.common_dto import SemanticRequest
from application.service.result_normalizer import normalize_result, _clean_cluster_term
from application.service.semantic_service import SemanticApplicationService
from config.settings import settings
from config.tool_contracts import ToolContract, get_contract
from config.vue_contracts import get_vue_contract
from domain.entity.analysis_task import AnalysisTask, ResultRecord, TaskStatus
from infrastructure.database.task_repository import DatabaseTaskRepository, task_repository
from infrastructure.database.resource_repository import DatabaseResourceRepository


DOMAIN_CODE_MAP = {
    "biomedical_informatics": "10",
    "medical_imaging": "10",
    "materials_science": "14",
    "new_energy": "20",
    "agricultural_technology": "12",
    "intelligent_manufacturing": "18",
    "environmental_science": "32",
}

# ------------------------------------------------------------------ #
# 引用句识别文本模式自动派生：文献文本 + 参考文献条目 → 引用句上下文 + 被引元数据
# ------------------------------------------------------------------ #
_CITE_MARKER_RE = re.compile(r"\[(\d+(?:\s*[,，\-–~]\s*\d+)*)\]")


def _split_sentences_for_citation(text: str) -> list:
    """中英混排分句(句末标点或换行),供引用句定位与上下文截取。"""
    parts = re.split(r"(?<=[。！？!?])\s*|(?<=\.)\s+|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _extract_citation_contexts(document_text: str, limit: int = 30) -> list:
    """定位带引用标记([1]/[2,3]/[4-6])的句子,取前句/后句为上下文。

    返回 contexts 条目(含 citation_sentence/previous_context/next_context/
    citation_marker 与内部 _marker_nums),超出 limit 截断。
    """
    sentences = _split_sentences_for_citation(document_text)
    contexts = []
    for i, sent in enumerate(sentences):
        markers = _CITE_MARKER_RE.findall(sent)
        if not markers:
            continue
        nums = []
        for m in markers:
            for part in re.split(r"[,，]", m):
                part = part.strip()
                if re.fullmatch(r"\d+\s*[-–~]\s*\d+", part):
                    a, b = re.split(r"[-–~]", part)
                    nums.extend(range(int(a), int(b) + 1))
                elif part.isdigit():
                    nums.append(int(part))
        if not nums:
            continue
        contexts.append({
            "citation_sentence": sent,
            "previous_context": sentences[i - 1] if i > 0 else "（文档开头，无上文）",
            "next_context": sentences[i + 1] if i + 1 < len(sentences) else "（文档结尾，无下文）",
            "citation_marker": f"[{markers[0]}]",
            "_marker_nums": sorted(set(nums)),
        })
        if len(contexts) >= limit:
            break
    return contexts


def _parse_reference_entries(entries_raw: str) -> list:
    """GLM 解析参考文献条目原文 → 结构化元数据列表(按条目序号)。

    兼容逐行条目与单行长文本(按 [n]/n. 序号切分),单次 GLM 调用批量解析,
    上限 60 条。解析结果带 reference_index 供引用标记匹配。
    """
    from infrastructure.llm.glm_client import glm_client
    lines = [l.strip() for l in entries_raw.splitlines() if l.strip()]
    if len(lines) <= 1 and entries_raw.strip():
        lines = [s.strip() for s in re.split(r"(?=\[\d+\])|(?=\d+[.、]\s)", entries_raw) if s.strip()]
    if not lines:
        return []
    lines = lines[:60]
    system = ("你是参考文献解析器。把用户给出的每条参考文献条目解析为结构化字段，"
              "严格按条目原文，不得编造。返回 JSON {data:[{index, authors, title, year, venue, doi}]}："
              "index=条目序号(条目开头的[n]或n.的数字,无序号按顺序1起)；authors=作者数组(原文人名)；"
              "title=题名；year=发表年份整数(无则null)；venue=期刊/会议/出版社；doi=DOI(无则空串)。")
    user = "解析以下参考文献条目：\n" + "\n".join(lines)
    out = glm_client.chat_json(system, user, timeout=90.0, max_tokens=4000)
    data = out.get("data", out) if isinstance(out, dict) else []
    metadata = []
    for pos, item in enumerate(data if isinstance(data, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index") or pos)
        except (TypeError, ValueError):
            idx = pos
        metadata.append({
            "citation_id": f"cite-{idx}",
            "reference_index": idx,
            "authors": item.get("authors") if isinstance(item.get("authors"), list) else
                       ([str(item.get("authors"))] if item.get("authors") else []),
            "title": str(item.get("title") or ""),
            "year": item.get("year"),
            "venue": str(item.get("venue") or ""),
            "doi": str(item.get("doi") or ""),
        })
    return metadata

# Public V7.74 field used as the actual document/text input for each tool.
# These names are intentionally duplicated from config.vue_contracts only as a
# defensive adapter table: the public request is preserved in the task record,
# while the internal aliases below keep the existing algorithms unchanged.
PRIMARY_TEXT_FIELDS = {
    "zh-abstract-move": "chinese_scientific_abstract",
    "en-abstract-move": "english_scientific_abstract",
    "fund-move": "project_document_text",
    "zh-classify": "chinese_scientific_document_text",
    "en-classify": "english_scientific_document_text",
    "domain-classify": "domain_scientific_literature_data",
    "zh-keyword": "chinese_scientific_abstract",
    "en-keyword": "english_scientific_abstract",
    "rq-detect": "scientific_document_fragment",
    "citation-sentiment": "scientific_document_full_text",
    "citation-intent": "scientific_document_full_text",
    "definition-detect": "scientific_document_fragment_or_batch_text",
    "general-ner": "bilingual_scientific_document_text",
    "research-ner": "academic_abstract_or_technical_report_text",
    "domain-ner": "domain_scientific_document_text",
    "deep-cluster": "scientific_document_texts",
    "structured-review": "document_set",
}

REQUIRED_RESOURCE_FIELDS = {
    "zh-classify": ("clc_labeled_data",),
    "en-classify": ("clc_labeled_data",),  # zh/en 共用同一份 CLC 资源（DB 一行、下拉一致、建库一次）
    "domain-classify": ("domain_classification_rules", "manually_labeled_training_data"),
    "en-keyword": ("domain_terminology_library", "classification_standard_mapping_table"),
    "citation-intent": ("preprocessed_training_set",),
    "general-ner": ("general_domain_annotated_corpus",),
    "research-ner": ("multi_domain_scientific_corpus", "manually_labeled_data"),
    "domain-ner": ("ontology_classification_system", "domain_labeled_training_data"),
}

SEMANTIC_RESOURCE_FIELDS = frozenset(field for fields in REQUIRED_RESOURCE_FIELDS.values() for field in fields)

_TASK_EXECUTOR = ThreadPoolExecutor(max_workers=settings.ASYNC_WORKERS, thread_name_prefix="semantic-task")

# 进程级 GLM 并发闸口：解决 _TASK_EXECUTOR(4) × group线程池(6) 嵌套导致的线程爆炸。
# 多个批量任务同时跑时，全进程在途 GLM 调用总数不超过此值，钳制 GLM QPS 不超限。
# 阻塞在信号量上的线程不占 CPU（OS 级 wait），仅占线程栈内存。
_GLM_SEMAPHORE = threading.BoundedSemaphore(settings.GLM_MAX_CONCURRENCY)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InputItem:
    input_id: str
    text: str
    source: Dict[str, Any]


class ToolIntegrationService:
    def __init__(
        self,
        semantic_service: SemanticApplicationService,
        repository: Optional[DatabaseTaskRepository] = None,
        resource_repository: Optional[DatabaseResourceRepository] = None,
    ) -> None:
        self.semantic_service = semantic_service
        self.repository = repository or task_repository
        self.resource_repository = resource_repository or DatabaseResourceRepository(self.repository.db)

    def execute(
        self,
        tool_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        file_inputs: Optional[List[Dict[str, str]]] = None,
        workspace_id: Optional[str] = None,
        _task_id: Optional[str] = None,
        _created_event: Optional[Event] = None,
    ) -> Dict[str, Any]:
        try:
            return self._run_execute(
                tool_id,
                payload,
                file_inputs=file_inputs,
                workspace_id=workspace_id,
                _task_id=_task_id,
                _created_event=_created_event,
            )
        finally:
            self._cleanup_temp_files(file_inputs)

    @staticmethod
    def _cleanup_temp_files(file_inputs: Optional[List[Dict[str, str]]]) -> None:
        """清理 save_uploads_to_temp 落盘的临时上传文件（_temp 标记）。"""
        for item in file_inputs or []:
            path = item.get("path") if isinstance(item, dict) else None
            if path and item.get("_temp"):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _run_execute(
        self,
        tool_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        file_inputs: Optional[List[Dict[str, str]]] = None,
        workspace_id: Optional[str] = None,
        _task_id: Optional[str] = None,
        _created_event: Optional[Event] = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        request_id = _id("req")
        contract = get_contract(tool_id)
        payload = self._adapt_vue_payload(contract, dict(payload or {}))
        # 引用工具文本模式自动派生：文献文本+参考文献条目 → 引用句上下文+被引元数据
        # （用户只需提供两项输入；手动提供 citation_sentence_and_context 时不覆盖）
        if tool_id.startswith("citation-") and str(payload.get("input_type") or "text") == "text":
            try:
                self._derive_citation_inputs(payload)
            except ValueError as exc:
                fallback_type = str(payload.get("input_type") or "text")
                return self._validation_error(contract, request_id, fallback_type, started, str(exc))
            except Exception as exc:  # noqa: BLE001 - 派生失败回落手动输入校验
                logger.warning("引用句自动派生异常：%s", exc)
        workspace_id = workspace_id or settings.DEFAULT_WORKSPACE_ID
        input_type = str(payload.get("input_type") or ("files" if file_inputs else "text"))
        try:
            params = self._parameters(contract, payload)
        except ValueError as exc:
            return self._validation_error(contract, request_id, input_type, started, str(exc))
        payload_error = self._payload_error(contract, payload)
        if payload_error:
            return self._validation_error(contract, request_id, input_type, started, payload_error)
        try:
            inputs = self._inputs(contract, payload, file_inputs or [])
        except ValueError as exc:
            return self._validation_error(contract, request_id, input_type, started, str(exc))
        if not inputs:
            return self._validation_error(contract, request_id, input_type, started, "没有可处理的输入数据")
        minimum = 1 if input_type in {"cluster_task", "upstream_records"} else contract.min_items
        if len(inputs) < minimum:
            return self._validation_error(contract, request_id, input_type, started, f"至少需要 {minimum} 项输入数据")
        if len(inputs) > contract.max_items:
            return self._validation_error(contract, request_id, input_type, started, f"输入数据不能超过 {contract.max_items} 项")

        task_id = _task_id or _id("tsk")
        task = AnalysisTask(
            id=task_id,
            workspace_id=workspace_id,
            tool_id=tool_id,
            backend_code=contract.backend_code,
            input_type=input_type,
            total=1 if contract.collection_tool else len(inputs),
            parameters=params,
            request_payload=self._safe_payload(payload, file_inputs or []),
            model_version=settings.MODEL_VERSION,
        )
        self.repository.create_task(task)
        if _created_event:
            _created_event.set()
        self.repository.update_task_status(task_id, TaskStatus.RUNNING, progress=1)

        results: List[Dict[str, Any]] = []
        success_count = 0
        failed_count = 0
        execution_groups = [inputs] if contract.collection_tool else [[item] for item in inputs]
        total = len(execution_groups)

        # 并发启用条件：逐篇工具 + group 数 ≥ 2 + 并发配置 > 1。
        # collection_tool（整体一个 group）和单篇输入走串行，避免线程池开销。
        use_concurrent = (
            not contract.collection_tool
            and total >= 2
            and settings.GLM_MAX_CONCURRENCY > 1
        )

        if use_concurrent:
            success_count, failed_count = self._run_groups_concurrent(
                task_id=task_id, tool_id=tool_id, contract=contract,
                execution_groups=execution_groups, params=params, payload=payload,
                results_out=results,
            )
        else:
            cancelled_event = threading.Event()
            for index, group in enumerate(execution_groups):
                if self._task_cancelled(task_id):
                    break
                result = self._execute_group_once(
                    task_id=task_id, tool_id=tool_id, contract=contract, index=index,
                    group=group, params=params, payload=payload, cancelled=cancelled_event,
                )
                results.append(result)
                if result["status"] == "succeeded":
                    success_count += 1
                elif result["status"] == "failed":
                    failed_count += 1
                if self._task_cancelled(task_id):
                    cancelled_event.set()
                    break
                self.repository.update_task_status(
                    task_id,
                    TaskStatus.RUNNING,
                    progress=min(95, max(1, int((index + 1) / total * 95))),
                    success_count=success_count,
                    failed_count=failed_count,
                )

        current_task = self.repository.get_task(task_id)
        if current_task and current_task.get("status") == TaskStatus.CANCELLED.value:
            status = TaskStatus.CANCELLED
        elif success_count == total:
            status = TaskStatus.SUCCEEDED
        elif success_count:
            status = TaskStatus.PARTIAL_FAILED
        else:
            status = TaskStatus.FAILED
        error_summary = next((item.get("error") for item in results if item.get("error")), None)
        self.repository.update_task_status(
            task_id, status, progress=100,
            success_count=success_count, failed_count=failed_count,
            error_summary=error_summary,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "code": 0 if status != TaskStatus.FAILED else 50001,
            "message": status.value,
            "data": {
                "task_id": task_id,
                "tool_id": tool_id,
                "status": status.value,
                "input_type": input_type,
                "progress": 100,
                "total": total,
                "success_count": success_count,
                "failed_count": failed_count,
                "error_summary": error_summary,
                "results": results,
                "summary": self._summary(results),
                "available_exports": list(contract.export_formats),
            },
            "meta": {
                "request_id": request_id,
                "schema_version": "1.0",
                "model_version": settings.MODEL_VERSION,
                "taxonomy_version": payload.get("taxonomy_version_id"),
                "ontology_version": payload.get("ontology_version_id"),
                "elapsed_ms": elapsed_ms,
                "created_at": _now(),
                "database_dialect": self.repository.db.dialect,
            },
        }

    def _task_cancelled(self, task_id: str) -> bool:
        """查询任务是否已被取消（供串行/并发路径共用，避免重复 get_task 样板）。"""
        current = self.repository.get_task(task_id)
        return bool(current and current.get("status") == TaskStatus.CANCELLED.value)

    def _execute_group_once(
        self,
        *,
        task_id: str,
        tool_id: str,
        contract: ToolContract,
        index: int,
        group: List[InputItem],
        params: Dict[str, Any],
        payload: Dict[str, Any],
        cancelled: threading.Event,
    ) -> Dict[str, Any]:
        """执行单个 group 的全流程：create_item → execute(GLM) → save_result → update_item。

        永不向上抛异常：失败时返回 ``status='failed'`` 的结果 dict，保证并发 ``as_completed``
        不会因一个 group 崩溃而中断其余 future。``cancelled`` 由调用方在发现取消时 set，
        本方法在启动前与拿到 GLM 信号量后双重自检。
        """
        # 启动前取消自检：已取消则不建 item、不调 GLM
        if cancelled.is_set():
            return {
                "index": index, "item_id": None, "record_id": None, "status": "skipped",
                "input_id": group[0].input_id if len(group) == 1 else None,
                "file_name": None, "source": {}, "error": "任务已取消，未启动", "result": {},
            }

        source = dict(group[0].source) if len(group) == 1 else {"input_count": len(group)}
        # Entity-relation recognition is a real downstream workflow.  Keep
        # the exact NER input on its task item so a selected batch record
        # can always be replayed independently (including uploaded files).
        if len(group) == 1 and tool_id in {"general-ner", "research-ner", "domain-ner"}:
            source.setdefault("text", group[0].text)

        item_id = self.repository.create_item(task_id, index, source)
        self.repository.update_item(item_id, "running")
        input_id = group[0].input_id if len(group) == 1 else None
        try:
            request = self._semantic_request(contract, group, params, payload)
            # 信号量只包最耗时的 GLM 调用；DB 操作不限流（快且独立 session 线程安全）。
            # 全局 _GLM_SEMAPHORE 钳制全进程在途 GLM 请求数，防多任务嵌套线程爆炸。
            with _GLM_SEMAPHORE:
                if cancelled.is_set():  # 拿到信号量后二次自检，避免取消后仍打 GLM
                    self.repository.update_item(item_id, "failed", "任务已取消")
                    return {
                        "index": index, "item_id": item_id, "record_id": None,
                        "status": "skipped", "input_id": input_id,
                        "file_name": source.get("file_name"), "source": source,
                        "error": "任务已取消", "result": {},
                    }
                semantic_result = self.semantic_service.execute(contract.backend_code, request)
            if not semantic_result.success:
                raise RuntimeError(semantic_result.error or "算法执行失败")
            record_id = _id("rec")
            result_payload = self._result_payload(payload, group)
            normalized = normalize_result(tool_id, semantic_result.data, result_payload)
            self._attach_result_identity(tool_id, normalized, task_id, record_id, payload)
            self._complete_vue_result(tool_id, normalized)
            self.repository.save_result(ResultRecord(
                id=record_id,
                task_id=task_id,
                task_item_id=item_id,
                tool_id=tool_id,
                backend_code=contract.backend_code,
                result=normalized,
            ))
            upstream_ids = self._upstream_ids(payload)
            if upstream_ids:
                self.repository.add_dependencies(record_id, upstream_ids, self._dependency_type(tool_id))
            self.repository.update_item(item_id, "succeeded")
            return {
                "index": index, "item_id": item_id, "record_id": record_id,
                "status": "succeeded", "input_id": input_id,
                "file_name": source.get("file_name"), "source": source, "result": normalized,
            }
        except Exception as exc:  # noqa: BLE001  异常隔离：失败不上抛，不影响其他 group
            error = str(exc)
            self.repository.update_item(item_id, "failed", error)
            return {
                "index": index, "item_id": item_id, "record_id": None, "status": "failed",
                "input_id": input_id, "file_name": source.get("file_name"), "source": source,
                "error": error, "result": {},
            }

    def _run_groups_concurrent(
        self,
        *,
        task_id: str,
        tool_id: str,
        contract: ToolContract,
        execution_groups: List[List[InputItem]],
        params: Dict[str, Any],
        payload: Dict[str, Any],
        results_out: List[Dict[str, Any]],
    ) -> Tuple[int, int]:
        """逐篇 group 线程池并发执行。

        - ``ThreadPoolExecutor`` 限单任务线程数；``_GLM_SEMAPHORE`` 限全进程在途 GLM 调用数。
        - ``as_completed`` 流式收集：每完成一篇上报一次进度（前端轮询看到的 progress 单调递增）。
        - ``progress_lock`` 只护内存计数与快照，``update_task_status`` 在锁外写库（避免持锁做 IO
          串行化 worker）；写到 DB 的是聚合快照三元组，不会回退。
        - ``bucket`` 按 index 收集，``as_completed`` 完成顺序无序，最后 ``sorted`` 还原输入顺序。
        - 取消：发现 CANCELLED 则 set event + cancel 未启动 future；已 running 的跑完（HTTP 无法
          安全中断，强杀泄漏连接）。
        """
        total = len(execution_groups)
        cancelled = threading.Event()
        progress_lock = threading.Lock()
        bucket: Dict[int, Dict[str, Any]] = {}
        success_count = 0
        failed_count = 0
        completed = 0
        workers = min(settings.GLM_MAX_CONCURRENCY, total)

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="glm-group") as pool:
            future_to_index = {
                pool.submit(
                    self._execute_group_once,
                    task_id=task_id, tool_id=tool_id, contract=contract,
                    index=index, group=group, params=params, payload=payload,
                    cancelled=cancelled,
                ): index
                for index, group in enumerate(execution_groups)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()  # _execute_group_once 永不抛
                except Exception as exc:  # noqa: BLE001  防御性：worker 线程本身崩溃（如 OOM）
                    result = {
                        "index": index, "item_id": None, "record_id": None, "status": "failed",
                        "input_id": None, "file_name": None, "source": {},
                        "error": f"线程异常: {exc}", "result": {},
                    }

                with progress_lock:  # 锁只护内存计数 + 快照
                    bucket[index] = result
                    if result["status"] == "succeeded":
                        success_count += 1
                    elif result["status"] == "failed":
                        failed_count += 1
                    completed += 1
                    snap_success, snap_failed, snap_done = success_count, failed_count, completed

                # 取消传播：发现 CANCELLED 则通知未启动的 worker 跳过
                if self._task_cancelled(task_id):
                    cancelled.set()
                    for fut in future_to_index:
                        fut.cancel()  # 已 running 返回 False（让它跑完），未启动的取消

                # 渐进进度：锁外写库，写快照三元组自洽不回退
                self.repository.update_task_status(
                    task_id,
                    TaskStatus.RUNNING,
                    progress=min(95, max(1, int(snap_done / total * 95))),
                    success_count=snap_success,
                    failed_count=snap_failed,
                )

        # 按 index 排序还原输入顺序（as_completed 完成顺序无序）
        results_out.extend(bucket[i] for i in sorted(bucket))
        return success_count, failed_count

    @staticmethod
    def _attach_result_identity(
        tool_id: str,
        result: Dict[str, Any],
        task_id: str,
        record_id: str,
        payload: Dict[str, Any],
    ) -> None:
        if tool_id == "deep-cluster":
            result.setdefault("cluster_task_id", task_id)
        elif tool_id == "cluster-label":
            result.setdefault("source_cluster_task_id", payload.get("cluster_task_id"))
        elif tool_id == "structured-review":
            result.setdefault("review_id", record_id)

    @staticmethod
    def _result_payload(payload: Dict[str, Any], group: List[InputItem]) -> Dict[str, Any]:
        """Return the exact per-item context used to normalize a batch result.

        Without this step a title or project name from the batch-level request
        can leak into every row.  File names and structured batch metadata are
        intentionally copied only for the item currently being normalized.
        """
        value = dict(payload)
        if not group:
            return value
        source = group[0].source if len(group) == 1 else {}
        if source.get("title") is not None:
            value["title"] = source.get("title")
            value["document_title"] = source.get("title")
        if source.get("project_name") is not None:
            value["project_name"] = source.get("project_name")
        if source.get("file_name"):
            value["file_name"] = source.get("file_name")
            value.setdefault("title", source.get("file_name"))
            value.setdefault("document_title", source.get("file_name"))
        if value.get("input_type") == "upstream_records":
            value["text"] = group[0].text
        elif group[0].text:
            # 文件输入时把本篇解析出的摘要回填到 result_payload.text，供 normalizer
            # 给 document.abstract 补值——前端弹窗按字符范围定位每个语步（move.text
            # 在 abstract 内 indexOf 算起止）。单篇 text 输入时与 payload.text 一致，
            # setdefault 不覆盖；批量文件 payload 无 text，这里补上本篇 abstract。
            value.setdefault("text", group[0].text)
        return value

    @staticmethod
    def _complete_vue_result(tool_id: str, result: Dict[str, Any]) -> None:
        """固定 Vue 结果字段；未知业务值仅返回空值，绝不使用演示数据补齐。"""
        list_fields = {
            "moves", "classifications", "candidates", "domain_labels", "levels",
            "cross_language_mapping", "keywords", "research_question_sentences",
            "research_question_phrases", "structured_research_questions", "citations",
            "citation_sentiment_results", "citation_intent_results", "definitions",
            "entities", "triples", "clusters", "labels", "tree", "sections",
            "evidence", "trend_analysis", "hotspots", "candidate_classifications",
            "multilevel_classification_results", "keywords_or_topic_phrases",
            "concept_definition_mappings", "standard_term_mappings", "ontology_mappings",
            "dependency_parse", "dependency_paths", "relation_triples", "context_fragments",
            "document_assignments", "semantic_projection", "evidence_index",
        }
        dict_fields = {
            "move_statistics", "project_metadata", "writeback", "primary_classification",
            "selected_domain", "distribution_report", "dictionary_usage", "statistics",
            "source_records", "quality_metrics", "generation_report",
            "cluster_induction_results", "structured_report", "trend_hotspot_distribution",
            "document", "summary", "classification_confidence", "data_distribution_report",
            "literature_distribution_analysis_report", "research_question_statistics",
            "citation_sentiment_statistics", "citation_intent_statistics",
            "statistical_analysis_report", "clustering_quality", "training_evaluation",
            "input_summary", "theme_trend_analysis", "parameters",
            "label_generation_process_report", "label_distinctiveness_optimization_result",
        }
        for field in get_vue_contract(tool_id).result_fields:
            if field in result:
                continue
            if field in list_fields:
                result[field] = []
            elif field in dict_fields:
                result[field] = {}
            else:
                result[field] = None

    def submit(
        self,
        tool_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        file_inputs: Optional[List[Dict[str, str]]] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建后台任务并立即返回任务编号；用于批量、文件和集合计算。"""
        task_id = _id("tsk")
        created = Event()
        future = _TASK_EXECUTOR.submit(
            self.execute,
            tool_id,
            payload,
            file_inputs=file_inputs,
            workspace_id=workspace_id,
            _task_id=task_id,
            _created_event=created,
        )
        if not created.wait(timeout=3):
            if future.done():
                return future.result()
            raise RuntimeError("后台任务创建超时")
        task = self.repository.get_task(task_id) or {}
        contract = get_contract(tool_id)
        return {
            "code": 0,
            "message": "accepted",
            "data": {
                "task_id": task_id,
                "tool_id": tool_id,
                "status": task.get("status", TaskStatus.QUEUED.value),
                "input_type": task.get("input_type"),
                "progress": task.get("progress", 0),
                "total": task.get("total", 0),
                "success_count": task.get("success_count", 0),
                "failed_count": task.get("failed_count", 0),
                "results": [],
                "summary": {},
                "available_exports": list(contract.export_formats),
            },
            "meta": {
                "request_id": _id("req"),
                "schema_version": "1.0",
                "model_version": settings.MODEL_VERSION,
                "created_at": _now(),
                "database_dialect": self.repository.db.dialect,
            },
        }

    @staticmethod
    def _adapt_vue_payload(contract: ToolContract, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add internal aliases without removing any public Vue field.

        ``request_payload`` therefore remains auditable against the UI, while
        the existing algorithm services can continue consuming ``text``,
        ``texts``, ``domain`` and the other established internal names.
        """
        adapted = dict(payload)
        tool_id = contract.tool_id
        public_field = PRIMARY_TEXT_FIELDS.get(tool_id)
        public_value = adapted.get(public_field) if public_field else None

        if not adapted.get("input_type"):
            if tool_id == "relation-extract":
                adapted["input_type"] = "upstream_records"
            elif tool_id == "structured-review" and isinstance(public_value, dict):
                adapted["input_type"] = "collection"
            elif isinstance(public_value, list):
                adapted["input_type"] = "texts"
            else:
                adapted["input_type"] = "text"

        input_type = str(adapted.get("input_type") or "text")
        is_many = input_type in {"texts", "files", "batch", "batch-text"}

        if public_field and public_value is not None and not isinstance(public_value, (bytes, bytearray)):
            if is_many and isinstance(public_value, list):
                adapted.setdefault("texts", public_value)
                adapted.setdefault("documents", public_value)
            elif isinstance(public_value, str):
                adapted.setdefault("text", public_value)

        if adapted.get("document_title") is not None:
            adapted.setdefault("title", adapted.get("document_title"))
        if adapted.get("professional_domain") is not None:
            adapted.setdefault("domain", adapted.get("professional_domain"))
        if adapted.get("domain_label") is not None:
            adapted.setdefault("domain", adapted.get("domain_label"))

        if tool_id == "fund-move" and adapted.get("project_name"):
            adapted.setdefault("title", adapted.get("project_name"))

        if tool_id.startswith("citation-"):
            contexts = adapted.get("citation_sentence_and_context")
            citation_metadata = adapted.get("citation_metadata")
            full_text = adapted.get("scientific_document_full_text")
            if isinstance(contexts, list) and contexts:
                citation_documents = []
                full_texts = full_text if isinstance(full_text, list) else []
                for index, context in enumerate(contexts):
                    row = context if isinstance(context, dict) else {"citation_sentence": str(context or "")}
                    paired_full_text = ""
                    if index < len(full_texts):
                        value = full_texts[index]
                        paired_full_text = ToolIntegrationService._document_text(value) if isinstance(value, dict) else str(value or "")
                    elif isinstance(full_text, str):
                        paired_full_text = full_text
                    context_text = "\n".join(str(row.get(key) or "") for key in (
                        "previous_context", "citation_sentence", "next_context",
                    ) if row.get(key))
                    citation_documents.append({
                        "id": row.get("id") or f"CIT{index + 1:03d}",
                        "text": paired_full_text or context_text,
                        "citation_context": row,
                        "citation_metadata": (
                            citation_metadata[index]
                            if isinstance(citation_metadata, list) and index < len(citation_metadata)
                            else citation_metadata
                        ),
                    })
                if input_type == "texts":
                    adapted["texts"] = citation_documents
                    adapted["documents"] = citation_documents
                elif citation_documents:
                    adapted["text"] = citation_documents[0]["text"]
            adapted.setdefault("citation_contexts", contexts or [])

        if tool_id == "relation-extract" and adapted.get("upstream_ner_record_id"):
            adapted["input_type"] = "upstream_records"
            adapted.setdefault("upstream_entity_record_id", adapted["upstream_ner_record_id"])

        if tool_id == "deep-cluster":
            documents = adapted.get("scientific_document_texts")
            metadata = adapted.get("document_metadata")
            if isinstance(documents, list):
                metadata_by_id = {
                    str(item.get("document_id") or item.get("id")): item
                    for item in metadata or [] if isinstance(item, dict)
                } if isinstance(metadata, list) else {}
                merged = []
                for index, value in enumerate(documents):
                    row = dict(value) if isinstance(value, dict) else {"text": str(value or "")}
                    document_id = str(row.get("document_id") or row.get("id") or f"DOC{index + 1:03d}")
                    merged.append({**metadata_by_id.get(document_id, {}), **row, "document_id": document_id})
                adapted["documents"] = merged
                adapted["texts"] = merged

        if tool_id == "cluster-label":
            phrase_sets = adapted.get("cluster_phrase_sets")
            if isinstance(phrase_sets, list):
                adapted["documents"] = [
                    {
                        "id": str(item.get("cluster_id") or f"CLUSTER_{index + 1:03d}"),
                        "text": json.dumps(item, ensure_ascii=False),
                    }
                    for index, item in enumerate(phrase_sets) if isinstance(item, dict)
                ]
                adapted["texts"] = adapted["documents"]
            adapted.setdefault("label_length_max", adapted.get("label_length_limit"))
            adapted.setdefault("output_language", adapted.get("language_type"))

        if tool_id == "structured-review" and isinstance(adapted.get("document_set"), dict):
            document_set = adapted["document_set"]
            collection_id = document_set.get("collection_id") or document_set.get("resource_id")
            if collection_id:
                adapted["collection_id"] = collection_id
                adapted["input_type"] = "collection"

        dictionary = adapted.get("domain_terminology_dictionary")
        if tool_id == "zh-keyword" and isinstance(dictionary, dict):
            if dictionary.get("resource_id"):
                adapted.setdefault("dictionary_id", dictionary["resource_id"])
            if dictionary.get("terms") or dictionary.get("file"):
                adapted.setdefault("custom_dictionary", dictionary)
        return adapted

    def _inputs(self, contract: ToolContract, payload: Dict[str, Any], files: List[Dict[str, str]]) -> List[InputItem]:
        if files:
            items: List[InputItem] = []
            metadata = payload.get("document_metadata")
            for index, value in enumerate(files):
                path = value.get("path")
                text = path or value.get("text", "")
                if not text:
                    continue
                item_metadata = metadata[index] if isinstance(metadata, list) and index < len(metadata) and isinstance(metadata[index], dict) else {}
                items.append(InputItem(f"file{index + 1}", text, {
                    "file_name": value.get("file_name"), "media_type": value.get("media_type"),
                    "is_path": bool(path),
                    # 文件解析层回传的真实标题，供 _result_payload 取作题名（无标题时
                    # 为 None，由其后的 file_name 兜底）。放在 item_metadata 前，
                    # 让用户显式提供的 document_metadata.title 优先于文件提取值。
                    "title": value.get("title"),
                    **item_metadata,
                }))
            return items

        if payload.get("input_type") == "upstream_records":
            text = self._text_from_upstream(payload)
            return [InputItem("upstream", text, {"source_mode": "structured"})] if text else []

        if payload.get("input_type") == "collection" or payload.get("collection_id"):
            documents = self._collection_documents(str(payload.get("collection_id") or ""))
            return [InputItem(str(item.get("id", index)), self._document_text(item), item) for index, item in enumerate(documents)]

        if contract.tool_id == "cluster-label" and payload.get("cluster_task_id"):
            upstream_inputs = self._inputs_from_task(str(payload["cluster_task_id"]))
            if upstream_inputs:
                return upstream_inputs
            upstream_result = self._result_from_task(str(payload["cluster_task_id"]))
            return [InputItem("cluster-result", json.dumps(upstream_result, ensure_ascii=False), {"source_task_id": payload["cluster_task_id"]})] if upstream_result else []

        texts = payload.get("document_set") or payload.get("documents") or payload.get("texts")
        if isinstance(texts, list):
            items = []
            for index, value in enumerate(texts):
                if isinstance(value, dict):
                    text = self._document_text(value)
                    input_id = str(value.get("document_id") or value.get("id") or value.get("input_id") or f"text{index + 1}")
                    source = {**value, "input_id": input_id, "title": value.get("title")}
                else:
                    text = str(value or "").strip()
                    input_id = f"text{index + 1}"
                    source = {"input_id": input_id}
                if text:
                    items.append(InputItem(input_id, text, source))
            return items

        text = self._single_text(contract, payload)
        # 单文本：把用户填写的题目（document_title/title）带进 source，供
        # _result_payload 回填 document.title，弹窗题名列显示论文题目。
        source: Dict[str, Any] = {"input_id": "text1"}
        title = payload.get("document_title") or payload.get("title")
        if title:
            source["title"] = title
        return [InputItem("text1", text, source)] if text else []

    def _semantic_request(
        self,
        contract: ToolContract,
        group: List[InputItem],
        params: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> SemanticRequest:
        if contract.collection_tool:
            if contract.tool_id == "structured-review":
                texts = []
                for item in group:
                    value = item.text
                    if value.lstrip().startswith("{"):
                        try:
                            decoded = json.loads(value)
                        except (TypeError, ValueError):
                            decoded = None
                        if isinstance(decoded, dict):
                            decoded.setdefault("document_id", decoded.get("id") or item.input_id)
                            decoded.setdefault("text", decoded.get("content") or decoded.get("full_text") or "")
                            if not decoded.get("title"):
                                decoded["title"] = item.source.get("title") or item.source.get("file_name") or ""
                            texts.append(json.dumps(decoded, ensure_ascii=False))
                            continue
                    texts.append(json.dumps({
                        "document_id": item.source.get("document_id") or item.source.get("id") or item.input_id,
                        "title": item.source.get("title") or item.source.get("file_name") or "",
                        "authors": item.source.get("authors") or [],
                        "institutions": item.source.get("institutions") or [],
                        "publication_date": item.source.get("publication_date") or item.source.get("published_at"),
                        "source": item.source.get("source") or "",
                        "keywords": item.source.get("keywords") or [],
                        "text": value,
                    }, ensure_ascii=False))
            elif contract.tool_id == "deep-cluster":
                texts = []
                for item in group:
                    if item.source.get("is_path"):
                        texts.append(json.dumps({
                            "document_id": item.source.get("document_id") or item.input_id,
                            "file_path": item.text,
                            "title": item.source.get("title") or item.source.get("file_name") or "",
                            "publication_date": item.source.get("publication_date"),
                            "authors": item.source.get("authors") or [],
                            "source": item.source.get("source") or "",
                            "keywords": item.source.get("keywords") or [],
                        }, ensure_ascii=False))
                    else:
                        texts.append(self._backend_text(contract, item.text, payload))
            else:
                texts = [self._backend_text(contract, item.text, payload) for item in group]
            effective_params = dict(params)
            if contract.tool_id == "cluster-label":
                phrase_sets = payload.get("cluster_phrase_sets")
                if not phrase_sets and payload.get("cluster_task_id"):
                    upstream = self._result_from_task(str(payload["cluster_task_id"]))
                    phrase_sets = self._cluster_phrase_sets(upstream)
                if phrase_sets:
                    # The production label generator consumes phrase sets from
                    # params; request.texts exists only for the shared task and
                    # persistence pipeline.  Do not drop the public primary
                    # field merely because it is excluded from generic params.
                    effective_params["cluster_phrase_sets"] = phrase_sets
            return SemanticRequest(texts=texts, params=effective_params, meta={"source": payload.get("input_type", "texts")})

        _item = group[0]
        _text = _item.text
        source_pdf_path = None  # 原始PDF路径：light取文0结果时回退mineru重抽用（双栏sort拆句/layout漏段）
        if _item.source.get("is_path"):
            # 路径透传(PATH_PASSTHROUGH_TOOLS)：延迟到此处解析该篇 PDF，让
            # mineru(GPU, PageBudgetPool 控制) 与它篇 LLM 处理(GLM) 并行流水线。
            from pathlib import Path
            from infrastructure.document_parser.upload_reader import extract_bytes
            from infrastructure.document_parser.mineru_api_client import _count_pages
            from infrastructure.document_parser.concurrency_pool import get_page_budget_pool
            _p = Path(_text)
            _content = _p.read_bytes()
            _name = _item.source.get("file_name") or _p.name
            if settings.should_use_light(contract.tool_id):
                # PyMuPDF 毫秒级直抽，不耗 GPU，无需页数预算约束
                source_pdf_path = str(_p) if _name.lower().endswith(".pdf") else None
                _text = extract_bytes(_content, _name, light=True) or ""
            else:
                _pages = _count_pages(_content) if _name.lower().endswith(".pdf") else 1
                _pool = get_page_budget_pool()
                _pool.acquire(_pages)
                try:
                    _text = extract_bytes(_content, _name, light=False) or ""
                finally:
                    _pool.release(_pages)
        text = self._backend_text(contract, _text, payload)
        effective_params = dict(params)
        if source_pdf_path:
            effective_params["_source_pdf_path"] = source_pdf_path
        if contract.tool_id.startswith("citation-"):
            context = group[0].source.get("citation_context")
            metadata = group[0].source.get("citation_metadata")
            if context:
                effective_params["citation_sentence_and_context"] = [context]
            if metadata:
                effective_params["citation_metadata"] = [metadata] if isinstance(metadata, dict) else metadata
        return SemanticRequest(text=text, params=effective_params, meta=self._meta(payload))

    @staticmethod
    def _backend_text(contract: ToolContract, text: str, payload: Dict[str, Any]) -> str:
        if contract.tool_id in {"zh-classify", "en-classify", "domain-classify"}:
            if text.lstrip().startswith("{"):
                return text
            if not (payload.get("title") or payload.get("abstract") or payload.get("keywords")):
                return text
            return json.dumps({
                "title": payload.get("title", ""),
                "abstract": payload.get("abstract") or text,
                "keywords": payload.get("keywords") or [],
            }, ensure_ascii=False)
        if not contract.collection_tool and text.lstrip().startswith("{"):
            try:
                document = json.loads(text)
            except (TypeError, ValueError):
                document = None
            if isinstance(document, dict):
                return str(
                    document.get("text") or document.get("content") or document.get("abstract")
                    or document.get("abstract_text") or text
                ).strip()
        return text

    @staticmethod
    def _single_text(contract: ToolContract, payload: Dict[str, Any]) -> str:
        if contract.tool_id in {"zh-classify", "en-classify", "domain-classify"}:
            plain_text = str(payload.get("text") or "").strip()
            if plain_text:
                return plain_text
            if not (payload.get("title") or payload.get("abstract")):
                return ""
            return json.dumps({
                "title": payload.get("title", ""),
                "abstract": payload.get("abstract", ""),
                "keywords": payload.get("keywords") or [],
            }, ensure_ascii=False)
        return str(payload.get("text") or payload.get("abstract") or payload.get("content") or "").strip()

    @staticmethod
    def _document_text(document: Dict[str, Any]) -> str:
        raw_metadata = document.get("metadata_json") or {}
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except (TypeError, ValueError):
                metadata = {}
        elif isinstance(raw_metadata, dict):
            metadata = raw_metadata
        else:
            metadata = {}

        content = (
            document.get("content")
            or document.get("text")
            or document.get("content_text")
            or document.get("abstract")
            or document.get("abstract_text")
            or ""
        )
        publication_date = (
            document.get("publication_date")
            or document.get("published_at")
            or metadata.get("publication_date")
            or metadata.get("published_at")
            or metadata.get("publication_year")
            or metadata.get("year")
        )
        if any(document.get(field) is not None for field in (
            "document_id", "id", "input_id", "title", "keywords", "publication_date", "published_at", "metadata_json",
        )):
            return json.dumps({
                "document_id": document.get("document_id") or document.get("id") or document.get("input_id"),
                "title": document.get("title") or metadata.get("title") or "",
                "abstract": document.get("abstract") or document.get("abstract_text") or metadata.get("abstract") or "",
                "text": document.get("text") or document.get("content") or document.get("content_text") or "",
                "keywords": document.get("keywords") or metadata.get("keywords") or [],
                "authors": document.get("authors") or metadata.get("authors") or [],
                "institutions": document.get("institutions") or metadata.get("institutions") or [],
                "source": document.get("source") or metadata.get("source") or metadata.get("venue") or "",
                "doi": document.get("doi") or metadata.get("doi") or "",
                "published_at": document.get("published_at") or metadata.get("published_at"),
                "publication_date": publication_date,
                "full_text": document.get("full_text") or document.get("content_text") or metadata.get("full_text") or "",
            }, ensure_ascii=False)
        return str(content).strip()

    def _parameters(self, contract: ToolContract, payload: Dict[str, Any]) -> Dict[str, Any]:
        excluded = {
            "input_type", "text", "texts", "title", "abstract", "keywords", "documents", "file", "files",
            "async", "rerun_from_task_id", "upstream_entity_record_id", "upstream_dependency_record_id",
            "cluster_task_id", "collection_id", "source_mode", "document_set",
        }
        excluded.update(PRIMARY_TEXT_FIELDS.values())
        excluded.update({"document_title", "scientific_document_full_text"})
        params = {key: value for key, value in payload.items() if key not in excluded and value is not None}
        resolved_resources: Dict[str, Any] = {}
        # deep-cluster 的训练样本/人工标注类目是可选资源（小样本聚类锚点辅助），
        # 不在必填的 SEMANTIC_RESOURCE_FIELDS 里，这里一并解析给引擎。
        resource_fields = set(SEMANTIC_RESOURCE_FIELDS)
        if contract.tool_id == "deep-cluster":
            resource_fields.update({"training_samples", "manually_labeled_category_data"})
        for field in resource_fields:
            descriptor = payload.get(field)
            if not isinstance(descriptor, dict) or not descriptor.get("resource_id"):
                continue
            resource = self.resource_repository.get_semantic_resource(str(descriptor["resource_id"]))
            if resource:
                resolved_resources[field] = resource
        if resolved_resources:
            params["resolved_resources"] = resolved_resources
        if contract.tool_id in {"zh-keyword", "en-keyword"} and payload.get("dictionary_id"):
            selected = self.resource_repository.get_dictionary(
                str(payload["dictionary_id"]),
                int(payload["dictionary_version"]) if payload.get("dictionary_version") else None,
            )
            if not selected:
                raise ValueError("用户词典或指定版本不存在")
            expected_language = "en" if contract.tool_id == "en-keyword" else "zh"
            if str(selected.get("language") or "").lower() != expected_language:
                raise ValueError(f"当前关键词工具只能使用 {expected_language} 词典")
            params["custom_dictionary"] = {
                "id": selected["id"],
                "version_id": selected["version_id"],
                "version": selected["version"],
                "name": selected["name"],
                "weight_boost": selected["weight_boost"],
                "terms": selected["terms"],
            }
        elif contract.tool_id == "zh-keyword" and isinstance(payload.get("custom_dictionary"), dict):
            custom = dict(payload["custom_dictionary"])
            terms = custom.get("terms") or []
            if not terms and custom.get("text_content"):
                raw_text = str(custom["text_content"])
                try:
                    decoded = json.loads(raw_text)
                    if isinstance(decoded, list):
                        terms = decoded
                    elif isinstance(decoded, dict):
                        terms = decoded.get("terms") or []
                except json.JSONDecodeError:
                    terms = [item.strip() for item in re.split(r"[\r\n,，;；]+", raw_text) if item.strip()]
            if terms:
                created = self.resource_repository.create_dictionary(
                    settings.DEFAULT_WORKSPACE_ID,
                    {
                        "name": custom.get("dictionary_name") or custom.get("name") or f"用户自定义领域词典_{datetime.now().strftime('%Y%m%d_%H%M')}",
                        "language": "zh",
                        "weight_boost": custom.get("weight_boost", 0.08),
                        "terms": terms,
                    },
                )
                selected = self.resource_repository.get_dictionary(created["id"], created["version"])
                params["custom_dictionary"] = {
                    "id": selected["id"], "version_id": selected["version_id"],
                    "version": selected["version"], "name": selected["name"],
                    "weight_boost": selected["weight_boost"], "terms": selected["terms"],
                }
        if contract.tool_id == "domain-classify":
            domain = str(payload.get("domain") or "")
            params["domain_code"] = DOMAIN_CODE_MAP.get(domain, domain)
        if contract.tool_id in {"en-abstract-move", "en-keyword", "en-classify"}:
            params.setdefault("lang", "en")
        if contract.tool_id == "deep-cluster":
            params["cluster_axis"] = "technical" if payload.get("cluster_dimension", "technology") == "technology" else "application"
        if contract.tool_id == "cluster-label":
            params["cluster_axis"] = "technical" if payload.get("cluster_dimension", "technology") == "technology" else "application"
        return params

    @staticmethod
    def _meta(payload: Dict[str, Any]) -> Dict[str, str]:
        return {"domain": str(payload.get("domain") or payload.get("discipline") or "auto")}

    def _derive_citation_inputs(self, payload: Dict[str, Any]) -> None:
        """引用工具文本模式自动派生：文献文本 + 参考文献条目 → 其余全部参数。

        用户只需提供 scientific_document_full_text（文献文本）与 reference_entries
        （参考文献条目原文，粘贴或上传）。派生：
        ① 引用句及上下文（正则定位 [n] 标记句 + 前后句）
        ② 被引文献元数据（GLM 解析条目 → 作者/题名/年份/来源/DOI）
        ③ 标记号 ↔ 条目序号匹配（citation_id = cite-<n>）
        已手动提供 citation_sentence_and_context 时不覆盖（高级路径保留）。
        """
        if payload.get("citation_sentence_and_context"):
            return
        document_text = str(
            payload.get("scientific_document_full_text") or payload.get("text") or ""
        ).strip()
        entries_raw = payload.get("reference_entries")
        if isinstance(entries_raw, dict):  # 文件上传场景 {file_name, text_content}
            entries_raw = entries_raw.get("text_content") or entries_raw.get("content") or ""
        entries_raw = str(entries_raw or "").strip()
        if not document_text:
            return  # 无文献文本：回落手动输入校验
        contexts = _extract_citation_contexts(document_text)
        if not contexts:
            raise ValueError(
                "未能从文献文本中定位引用句（未发现 [n] 形式的引用标记）；"
                "请确认文本包含引用标记，或手动提供引用句及上下文"
            )
        if not entries_raw:
            raise ValueError(
                "请提供参考文献条目（粘贴条目文本或上传条目文件），"
                "系统将自动解析被引文献元数据"
            )
        metadata = _parse_reference_entries(entries_raw)
        if not metadata:
            raise ValueError("参考文献条目解析失败，请检查条目格式")
        # 引用句按标记号匹配元数据；未匹配到条目的引用句仍保留（元数据留空由引擎降级）
        for ctx in contexts:
            nums = ctx.pop("_marker_nums", None) or []
            ctx["citation_id"] = f"cite-{nums[0]}" if nums else "cite-0"
            ctx["matched_reference"] = nums[0] in {m.get("reference_index") for m in metadata}
        payload["citation_sentence_and_context"] = contexts
        payload["citation_metadata"] = metadata

    def _payload_error(self, contract: ToolContract, payload: Dict[str, Any]) -> Optional[str]:
        # 在线测试中的手工文本统一限制为 8000 个清洗后字符。
        # 文件和数据库集合不走这里，仍可保留全文并由各算法分段处理。
        candidates: List[tuple[str, Any]] = []
        for field in ("text", "abstract", "content"):
            if payload.get(field) is not None:
                candidates.append((field, payload.get(field)))
        for collection_name in ("document_set", "documents", "texts"):
            documents = payload.get(collection_name)
            if not isinstance(documents, list):
                continue
            for index, document in enumerate(documents):
                if isinstance(document, dict):
                    identifier = str(document.get("id") or document.get("input_id") or f"第{index + 1}条文本")
                    for field in ("text", "abstract", "content"):
                        if document.get(field) is not None:
                            candidates.append((f"{identifier} 的 {field}", document.get(field)))
                elif document is not None:
                    candidates.append((f"第{index + 1}条文本", document))
        for label, value in candidates:
            cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
            if len(cleaned) > 8000:
                return f"{label} 清洗后不能超过8000个字符"
        for field in ("minimum_confidence", "difference_threshold", "distinctiveness_threshold"):
            if payload.get(field) is not None:
                try:
                    value = float(payload[field])
                except (TypeError, ValueError):
                    return f"{field} 必须是数值"
                if not 0 <= value <= 1:
                    return f"{field} 必须在 0—1 之间"
        custom_dictionary = payload.get("custom_dictionary")
        if isinstance(custom_dictionary, dict):
            try:
                weight_boost = float(custom_dictionary.get("weight_boost", 0))
            except (TypeError, ValueError):
                return "用户词典 weight_boost 必须是数值"
            if not 0 <= weight_boost <= 0.5:
                return "用户词典 weight_boost 必须在 0—0.5 之间"
        try:
            minimum_keywords = int(payload.get("min_keywords", 5) or 5)
            maximum_keywords = int(payload.get("max_keywords", 8) or 8)
        except (TypeError, ValueError):
            return "min_keywords 和 max_keywords 必须是整数"
        if minimum_keywords < 1 or maximum_keywords < minimum_keywords or maximum_keywords > 50:
            return "关键词数量必须满足 1 ≤ min_keywords ≤ max_keywords ≤ 50"
        if contract.tool_id == "cluster-label":
            if not payload.get("cluster_phrase_sets") and not payload.get("cluster_task_id"):
                return "聚类标签生成必须提供深度聚类输出的类簇短语集合"
            try:
                minimum_length = int(payload.get("label_length_min", 1) or 1)
                maximum_length = int(payload.get("label_length_max", 12) or 12)
            except (TypeError, ValueError):
                return "label_length_min 和 label_length_max 必须是整数"
            if minimum_length < 1 or maximum_length < minimum_length or maximum_length > 100:
                return "标签长度必须满足 1 ≤ label_length_min ≤ label_length_max ≤ 100"
        if contract.tool_id == "domain-classify" and not str(payload.get("domain") or "").strip():
            return "domain 为必填项"
        for field in REQUIRED_RESOURCE_FIELDS.get(contract.tool_id, ()):
            descriptor = payload.get(field)
            if not isinstance(descriptor, dict):
                return f"{field} 为必填资源，请选择数据库当前资源或上传资源文件"
            source = str(descriptor.get("source") or "database")
            if source == "database":
                resource_id = str(descriptor.get("resource_id") or "")
                if not resource_id:
                    return f"{field} 未选择数据库资源"
                resource = self.resource_repository.get_semantic_resource(resource_id)
                if not resource or resource.get("resource_key") != field or resource.get("status") != "current":
                    return f"{field} 所选资源不存在、类型不匹配或不是当前资源"
            elif source == "upload":
                if not (descriptor.get("file_name") or descriptor.get("file") or descriptor.get("storage_uri")):
                    return f"{field} 已选择上传方式，但没有上传资源文件"
            else:
                return f"{field} 的资源来源必须是 database 或 upload"
        if contract.tool_id.startswith("citation-"):
            contexts = payload.get("citation_sentence_and_context")
            metadata = payload.get("citation_metadata")
            if payload.get("input_type") in {"text", "texts"}:
                if not isinstance(contexts, list) or not contexts:
                    return "citation_sentence_and_context 为必填项；文本输入必须提供引用句及其上下文"
                for index, item in enumerate(contexts):
                    if not isinstance(item, dict) or not str(item.get("citation_sentence") or "").strip():
                        return f"第 {index + 1} 条引用数据缺少引用句文本"
                    if not str(item.get("previous_context") or "").strip() or not str(item.get("next_context") or "").strip():
                        return f"第 {index + 1} 条引用数据必须同时提供引用句上文和下文"
                if not metadata:
                    return "citation_metadata 为必填项；文本输入必须提供被引文献元数据"
        if contract.tool_id == "deep-cluster":
            documents = payload.get("documents") or []
            metadata = payload.get("document_metadata")
            if payload.get("input_type") == "texts":
                if not isinstance(metadata, list) or len(metadata) != len(documents):
                    return "document_metadata 必须与科技文献文本逐篇对应"
                for index, item in enumerate(metadata):
                    if not isinstance(item, dict) or not str(item.get("document_id") or "").strip() or not str(item.get("publication_date") or "").strip():
                        return f"第 {index + 1} 篇文献的文献编号和发表时间为必填项"
        if contract.tool_id == "structured-review":
            if not str(payload.get("topic_or_keywords") or "").strip():
                return "topic_or_keywords 为必填项"
            if payload.get("input_type") == "texts":
                documents = payload.get("document_set") or []
                metadata = payload.get("document_metadata")
                if not isinstance(metadata, list) or len(metadata) != len(documents):
                    return "document_metadata 必须与文献集逐篇对应"
        if payload.get("input_type") == "upstream_records" and not payload.get("upstream_entity_record_id"):
            return "实体关系识别必须选择一条已完成的命名实体识别记录"
        return None

    def _text_from_upstream(self, payload: Dict[str, Any]) -> str:
        for key in ("upstream_entity_record_id", "upstream_dependency_record_id"):
            record_id = str(payload.get(key) or "")
            if not record_id:
                continue
            record = self.repository.get_result(record_id)
            if not record:
                continue
            # 上游为 NER 记录时，复用已识别实体组装关系抽取输入：NER 的原始全文
            # 多为 PDF 临时路径，到 relation 阶段常已失效，且 NER 未持久化全文，
            # 故用实体列表 + 各实体语境句子送 LLM 抽关系（best-effort，跨句关系
            # 可能漏，宁缺毋滥）。
            _res = record.get("result") or {}
            _ents = _res.get("entities") or _res.get("entity_results") or []
            if isinstance(_ents, list) and _ents:
                _composed = self._compose_entity_context(_ents)
                if _composed:
                    return _composed
            item = self.repository.get_task_item(str(record.get("task_item_id") or ""))
            item_text = self._text_from_task_item(item)
            if item_text:
                return item_text
            task = self.repository.get_task(record["task_id"])
            if task:
                source = task.get("request_payload") or {}
                item_index = item.get("input_index") if item else None
                indexed_text = self._text_from_task_payload(source, item_index, str(task.get("tool_id") or ""))
                if indexed_text:
                    return indexed_text
                text = source.get("text") or source.get("abstract")
                if not text:
                    public_field = PRIMARY_TEXT_FIELDS.get(str(task.get("tool_id") or ""))
                    text = source.get(public_field) if public_field else None
                if text:
                    return str(text)
                texts = source.get("texts")
                if isinstance(texts, list) and texts:
                    first = texts[0]
                    return self._document_text(first) if isinstance(first, dict) else str(first)
        raise ValueError("上游历史记录不存在，或未保存可复用的原始文本")

    @staticmethod
    def _compose_entity_context(ents: List[Dict[str, Any]]) -> str:
        """把上游 NER 已识别实体组装成关系抽取输入文本。

        上游 NER 的原始全文多为 PDF 临时路径，relation 阶段常已失效且 NER 未
        持久化全文，故复用已识别实体 + 各实体语境句子送 LLM 抽关系；跨句关系
        可能漏，宁缺毋滥（符合抽取召回阈值原则）。
        """
        ent_lines: List[str] = []
        seen_ctx: List[str] = []
        _seen = set()
        for _i, _e in enumerate(ents, 1):
            if not isinstance(_e, dict):
                continue
            _txt = str(_e.get("text") or "").strip()
            if not _txt:
                continue
            _typ = str(_e.get("type") or "").strip()
            _line = f"[{_i}] {_txt}"
            if _typ:
                _line += f"（{_typ}）"
            ent_lines.append(_line)
            _ctx = str(_e.get("context") or "").strip()
            if _ctx and _ctx not in _seen:
                _seen.add(_ctx)
                seen_ctx.append(_ctx)
        if not ent_lines:
            return ""
        _parts = [f"上游命名实体识别已完成，共识别 {len(ent_lines)} 个实体：",
                  "\n".join(ent_lines)]
        if seen_ctx:
            _parts.append("\n实体出现的语境句子（去重）：")
            _parts.append("\n".join(f"S{_j}: {_c}" for _j, _c in enumerate(seen_ctx, 1)))
        _parts.append(
            "\n\n请基于以上已识别实体及其语境句子，抽取实体之间的语义关系三元组 "
            "(头实体, 关系, 尾实体)。关系如治疗/抑制/使用/属于/任职于/应用于等；"
            "同一语境句中共现且存在语义关系的实体优先抽取；关系须语境可支撑，不得臆造。"
        )
        return "\n".join(_parts)

    @classmethod
    def _text_from_task_item(cls, item: Optional[Dict[str, Any]]) -> str:
        if not item:
            return ""
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        for key in ("text", "content", "content_text", "abstract", "abstract_text"):
            if str(source.get(key) or "").strip():
                return str(source[key]).strip()
        return ""

    @classmethod
    def _text_from_task_payload(cls, payload: Dict[str, Any], input_index: Any, tool_id: str = "") -> str:
        """Recover the matching batch member instead of silently using member zero."""
        if not isinstance(input_index, int):
            return ""
        for key in ("texts", "documents"):
            values = payload.get(key)
            if isinstance(values, list) and 0 <= input_index < len(values):
                value = values[input_index]
                if isinstance(value, dict):
                    for field in ("text", "content", "content_text", "abstract", "abstract_text"):
                        if str(value.get(field) or "").strip():
                            return str(value[field]).strip()
                    return cls._document_text(value)
                return str(value or "").strip()
        public_field = PRIMARY_TEXT_FIELDS.get(tool_id)
        values = payload.get(public_field) if public_field else None
        if isinstance(values, list) and 0 <= input_index < len(values):
            value = values[input_index]
            return cls._document_text(value) if isinstance(value, dict) else str(value or "").strip()
        return ""

    def _inputs_from_task(self, task_id: str) -> List[InputItem]:
        task = self.repository.get_task(task_id)
        if not task:
            raise ValueError(f"历史任务不存在：{task_id}")
        payload = task.get("request_payload") or {}
        documents = payload.get("documents") or payload.get("texts") or []
        return [InputItem(str(item.get("id", index)), self._document_text(item), item) if isinstance(item, dict)
                else InputItem(f"text{index + 1}", str(item), {"input_id": f"text{index + 1}"})
                for index, item in enumerate(documents)]

    def _result_from_task(self, task_id: str) -> Dict[str, Any]:
        records = self.repository.list_results(task_id)
        return records[0]["result"] if records else {}

    @staticmethod
    def _cluster_phrase_sets(result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recover the exact label-generator input from a persisted cluster result."""
        phrase_sets: List[Dict[str, Any]] = []
        for index, cluster in enumerate(result.get("clusters") or []):
            if not isinstance(cluster, dict):
                continue
            phrases = (
                cluster.get("representative_terms") or cluster.get("keywords")
                or cluster.get("top_terms") or cluster.get("phrases") or []
            )
            phrases = [t for t in (_clean_cluster_term(value) for value in phrases) if t]
            if not phrases:
                continue
            phrase_sets.append({
                "cluster_id": str(cluster.get("cluster_id") or cluster.get("topic_id") or f"C{index + 1}"),
                "phrases": phrases,
            })
        return phrase_sets

    def _collection_documents(self, collection_id: str) -> List[Dict[str, Any]]:
        if not collection_id:
            return []
        with self.repository.db.session() as session:
            return session.fetchall(
                """SELECT d.id, d.title, d.abstract_text, d.content_text, d.metadata_json
                FROM collection_documents cd JOIN documents d ON d.id=cd.document_id
                WHERE cd.collection_id=? ORDER BY cd.order_no, d.created_at""",
                (collection_id,),
            )

    def _upstream_ids(self, payload: Dict[str, Any]) -> List[str]:
        result_ids = [str(payload[key]) for key in (
            "upstream_entity_record_id", "upstream_dependency_record_id",
        ) if payload.get(key)]
        cluster_task_id = str(payload.get("cluster_task_id") or "")
        if cluster_task_id:
            result_ids.extend(record["id"] for record in self.repository.list_results(cluster_task_id))
        return list(dict.fromkeys(result_ids))

    @staticmethod
    def _dependency_type(tool_id: str) -> str:
        return {"relation-extract": "entity_and_dependency", "cluster-label": "cluster_task", "structured-review": "collection_or_cluster"}.get(tool_id, "upstream")

    @staticmethod
    def _safe_payload(payload: Dict[str, Any], files: List[Dict[str, str]]) -> Dict[str, Any]:
        value = dict(payload)
        if files:
            value["files"] = [{"file_name": item.get("file_name"), "media_type": item.get("media_type")} for item in files]
            value["documents"] = [{
                "id": f"FILE{index + 1:03d}",
                "title": item.get("file_name"),
                "content": item.get("text", ""),
                "media_type": item.get("media_type"),
            } for index, item in enumerate(files)]
        return value

    @staticmethod
    def _summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "succeeded": sum(item["status"] == "succeeded" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
        }

    def _validation_error(self, contract: ToolContract, request_id: str, input_type: str, started: float, message: str) -> Dict[str, Any]:
        return {
            "code": 42201,
            "message": message,
            "data": {
                "task_id": "", "tool_id": contract.tool_id, "status": "failed", "input_type": input_type,
                "progress": 0, "total": 0, "success_count": 0, "failed_count": 0,
                "results": [], "summary": {}, "available_exports": list(contract.export_formats),
            },
            "meta": {
                "request_id": request_id, "schema_version": "1.0", "model_version": settings.MODEL_VERSION,
                "elapsed_ms": int((time.perf_counter() - started) * 1000), "created_at": _now(),
                "database_dialect": self.repository.db.dialect,
            },
        }
