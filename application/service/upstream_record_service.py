"""接收其他后端模块产生的实体或依存句法记录，供实体关系识别复用。"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from config.settings import settings
from domain.entity.analysis_task import AnalysisTask, ResultRecord, TaskStatus
from infrastructure.database.task_repository import DatabaseTaskRepository, task_repository


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class UpstreamRecordService:
    KINDS = {
        "entity": ("upstream-entity", "upstream_entity_external", "entities"),
        "dependency": ("upstream-dependency", "upstream_dependency_external", "dependencies"),
    }

    def __init__(self, repository: Optional[DatabaseTaskRepository] = None) -> None:
        self.repository = repository or task_repository

    def create(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if kind not in self.KINDS:
            raise ValueError("上游记录类型只支持 entity 或 dependency")
        text = str(payload.get("text") or "").strip()
        if not text:
            raise ValueError("上游结构化记录必须包含关联原文 text")
        tool_id, backend_code, data_key = self.KINDS[kind]
        structured_data = payload.get(data_key)
        if not isinstance(structured_data, list) or not structured_data:
            raise ValueError(f"{data_key} 必须是非空数组")
        task_id, item_id, record_id = _id("tsk"), "", _id("rec")
        task = AnalysisTask(
            id=task_id,
            workspace_id=str(payload.get("workspace_id") or settings.DEFAULT_WORKSPACE_ID),
            tool_id=tool_id,
            backend_code=backend_code,
            input_type="external_structured",
            total=1,
            parameters={"source_system": payload.get("source_system")},
            request_payload={"text": text, data_key: structured_data, "source_system": payload.get("source_system")},
            model_version=str(payload.get("model_version") or "external"),
        )
        self.repository.create_task(task)
        self.repository.update_task_status(task_id, TaskStatus.RUNNING, progress=10)
        item_id = self.repository.create_item(task_id, 0, {"source_system": payload.get("source_system")})
        self.repository.update_item(item_id, "running")
        self.repository.save_result(ResultRecord(
            id=record_id,
            task_id=task_id,
            task_item_id=item_id,
            tool_id=tool_id,
            backend_code=backend_code,
            result={data_key: structured_data, "text": text},
        ))
        self.repository.update_item(item_id, "succeeded")
        self.repository.update_task_status(task_id, TaskStatus.SUCCEEDED, progress=100, success_count=1, failed_count=0)
        return {"task_id": task_id, "record_id": record_id, "tool_id": tool_id, "data_type": kind, "status": "succeeded"}


upstream_record_service = UpstreamRecordService()
