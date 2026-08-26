"""CLC 用户上传资源异步建索引服务。

register 时判定 verdict 后，对完整分类树（taxonomy_complete + records>BUILD_MIN）
异步建 large+m3 向量索引，供 ``clc_retriever.for_path`` 加载替换内置检索。

设计要点：
- 独立 ThreadPoolExecutor(max 1)：建库 GPU 密集且串行，不与分类任务抢
  ``_TASK_EXECUTOR`` 线程，避免拖慢在线分类；
- 建库失败**不写 manifest** → 分类 probe ``index_dir/clc_index_large/manifest.json``
  落空 → ``_resolve_clc_retriever`` 自动回退内置单例（filesystem 为 ground truth，
  不信 DB 状态防 stale）；
- 非完整分类树（scattered/labeled_papers）→ FAILED + 不建库（resolve_code 上溯
  在散点库失效，few-shot 注入更优）。
"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings
from domain.entity.analysis_task import AnalysisTask, TaskStatus
from infrastructure.rag.clc_meta_builder import detect_taxonomy_kind, normalize_meta

logger = logging.getLogger(__name__)

# 建库串行（GPU 密集，max 1）
_BUILD_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clc-index-build")


def compute_clc_verdict(entries: list, size_bytes: Optional[int] = None) -> Dict[str, Any]:
    """计算 CLC 资源 verdict（kind/record_count/size_bytes）供分治与 _resource_context 读取。"""
    kind = detect_taxonomy_kind(entries)
    return {
        "kind": kind,
        "record_count": len(entries),
        "size_bytes": size_bytes if size_bytes is not None else len(json.dumps(entries, ensure_ascii=False)),
    }


def submit_build(resource_row: Dict[str, Any], repository=None) -> Optional[str]:
    """对完整分类树用户资源异步建索引；返回 task_id（不满足建库条件返回 None）。

    Args:
        resource_row: ``get_semantic_resource`` 返回的 DB 记录
            （含 storage_uri/record_count/workspace_id/id）。
        repository: task_repository（create_task/update_task_status）。
    """
    storage_uri = str(resource_row.get("storage_uri") or "")
    if not storage_uri:
        return None
    if repository is None:
        from infrastructure.database.task_repository import task_repository
        repository = task_repository
    record_count = int(resource_row.get("record_count") or 0)
    if record_count <= settings.CLC_BUILD_MIN_RECORDS:
        logger.info("CLC 资源 %s 条数 %d ≤ %d，不建库（走 few-shot/范围块）",
                    resource_row.get("id"), record_count, settings.CLC_BUILD_MIN_RECORDS)
        return None
    task_id = f"tsk_clcidx_{uuid.uuid4().hex[:12]}"
    task = AnalysisTask(
        id=task_id,
        workspace_id=str(resource_row.get("workspace_id") or settings.DEFAULT_WORKSPACE_ID),
        tool_id="clc-index-build",
        backend_code="clc",
        input_type="index_build",
        status=TaskStatus.QUEUED,
        total=100,
        parameters={"resource_id": resource_row.get("id"), "storage_uri": storage_uri},
    )
    try:
        repository.create_task(task)
    except Exception as e:  # noqa: BLE001
        logger.warning("CLC 建索引任务创建失败 %s: %s", task_id, e)
        return None
    _BUILD_EXECUTOR.submit(_build, task_id, storage_uri, resource_row.get("id"), repository)
    logger.info("CLC 建索引任务已提交：%s 资源=%s storage_uri=%s",
                task_id, resource_row.get("id"), storage_uri)
    return task_id


def _build(task_id: str, storage_uri: str, resource_id: str, repository) -> None:
    """异步建索引：读 entries → normalize → detect（非 complete 失败）→ 写 meta → build_index。"""
    from infrastructure.rag.clc_index_builder import build_index
    from infrastructure.rag.clc_retriever import CLCRetriever
    index_dir = CLCRetriever._index_dir_for(storage_uri)
    try:
        repository.update_task_status(task_id, TaskStatus.RUNNING, progress=5)
        # 1. 读 entries
        with open(storage_uri, encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list) or not entries:
            raise ValueError("资源非 JSON 数组或为空")
        # 2. normalize + detect（非完整树拒绝）
        normalize_meta(entries)
        kind = detect_taxonomy_kind(entries)
        if kind != "taxonomy_complete":
            raise ValueError(f"非完整分类树（{kind}），拒绝建库——resolve_code 上溯在散点库失效")
        # 3. 写 clc_meta_full.json
        index_dir.mkdir(parents=True, exist_ok=True)
        meta_path = index_dir / "clc_meta_full.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        logger.info("CLC 建索引 %s：meta 写入 %s（%d 条）", task_id, meta_path, len(entries))

        # 4. 建向量索引（progress_cb 更新进度）
        def _cb(progress: float, stage: str) -> None:
            repository.update_task_status(task_id, TaskStatus.RUNNING,
                                          progress=max(5, int(progress)))
            logger.info("CLC 建索引 %s: %d%% %s", task_id, int(progress), stage)

        build_index(str(index_dir), build_large=True, build_m3=True, progress_cb=_cb)
        repository.update_task_status(task_id, TaskStatus.SUCCEEDED,
                                      progress=100, success_count=1)
        logger.info("CLC 建索引完成：%s → %s", task_id, index_dir)
    except Exception as e:  # noqa: BLE001
        logger.error("CLC 建索引失败 %s: %s", task_id, e)
        repository.update_task_status(task_id, TaskStatus.FAILED,
                                      error_summary=str(e)[:500])
        # 删半成品（不写/删 manifest → 分类 probe 落空自动回退内置单例）
        try:
            for sub in ("clc_index_large", "clc_index_m3"):
                shutil.rmtree(index_dir / sub, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass
