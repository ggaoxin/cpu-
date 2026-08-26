"""分析任务领域实体。数据库细节由 infrastructure 层实现。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class TaskStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AnalysisTask:
    id: str
    workspace_id: str
    tool_id: str
    backend_code: str
    input_type: str
    status: TaskStatus = TaskStatus.QUEUED
    progress: int = 0
    total: int = 0
    success_count: int = 0
    failed_count: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    request_payload: Dict[str, Any] = field(default_factory=dict)
    model_version: Optional[str] = None
    error_summary: Optional[str] = None


@dataclass
class ResultRecord:
    id: str
    task_id: str
    tool_id: str
    backend_code: str
    result: Dict[str, Any]
    task_item_id: Optional[str] = None
    schema_version: str = "1.0"
