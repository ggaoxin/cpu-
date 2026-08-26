"""面向 Vue 的统一响应 DTO。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskResultItem(BaseModel):
    index: int
    item_id: str
    record_id: Optional[str] = None
    status: str
    input_id: Optional[str] = None
    file_name: Optional[str] = None
    error: Optional[str] = None
    result: Dict[str, Any] = Field(default_factory=dict)


class TaskData(BaseModel):
    task_id: str
    tool_id: str
    status: str
    input_type: str
    progress: int
    total: int
    success_count: int
    failed_count: int
    results: List[TaskResultItem] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    available_exports: List[str] = Field(default_factory=list)


class ResponseMeta(BaseModel):
    request_id: str
    schema_version: str = "1.0"
    model_version: str
    elapsed_ms: int
    created_at: str
    database_dialect: Optional[str] = None


class ToolResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: TaskData
    meta: ResponseMeta
