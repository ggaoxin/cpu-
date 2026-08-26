"""任务与结果仓储接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional

from domain.entity.analysis_task import AnalysisTask, ResultRecord, TaskStatus


class ITaskRepository(ABC):
    @abstractmethod
    def create_task(self, task: AnalysisTask) -> None: ...

    @abstractmethod
    def create_item(self, task_id: str, input_index: int, source: Dict[str, Any]) -> str: ...

    @abstractmethod
    def update_item(self, item_id: str, status: str, error: Optional[str] = None) -> None: ...

    @abstractmethod
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        progress: Optional[int] = None,
        success_count: Optional[int] = None,
        failed_count: Optional[int] = None,
        error_summary: Optional[str] = None,
    ) -> None: ...

    @abstractmethod
    def save_result(self, record: ResultRecord) -> None: ...

    @abstractmethod
    def add_dependencies(self, record_id: str, upstream_ids: Iterable[str], dependency_type: str) -> None: ...

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def list_tasks(self, workspace_id: str, tool_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def get_result(self, record_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def get_task_item(self, item_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def list_results(self, task_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def archive_task(self, task_id: str) -> bool: ...

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool: ...

    @abstractmethod
    def get_lineage(self, record_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    def save_classification_confirmation(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def save_cluster_label_confirmation(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def save_feedback(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    @abstractmethod
    def healthcheck(self) -> Dict[str, Any]: ...
