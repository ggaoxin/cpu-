"""结果血缘、人工确认、反馈和任务生命周期应用服务。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from infrastructure.database.task_repository import DatabaseTaskRepository, task_repository


class ResultGovernanceService:
    def __init__(self, repository: Optional[DatabaseTaskRepository] = None) -> None:
        self.repository = repository or task_repository

    def lineage(self, record_id: str) -> Dict[str, Any]:
        if not self.repository.get_result(record_id):
            raise ValueError("结果记录不存在")
        return self.repository.get_lineage(record_id)

    def confirm_classification(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = self.repository.get_result(record_id)
        if not record or record.get("tool_id") not in {"zh-classify", "en-classify", "domain-classify"}:
            raise ValueError("指定记录不是可确认的分类结果")
        primary_code = str(payload.get("primary_code") or "").strip()
        if not primary_code:
            raise ValueError("primary_code 不能为空")
        candidate_id = str(payload.get("candidate_id") or "").strip()
        result = record.get("result") if isinstance(record.get("result"), dict) else {}
        candidates = result.get("candidate_classifications") or result.get("candidates") or []
        if candidates and not candidate_id:
            raise ValueError("candidate_id 不能为空，必须确认当前结果中的候选分类")
        if candidate_id:
            candidate = next((
                item for item in candidates
                if isinstance(item, dict) and str(item.get("candidate_id") or "") == candidate_id
            ), None)
            if not candidate:
                raise ValueError("candidate_id 不属于当前分类结果")
            candidate_code = str(
                candidate.get("main_code")
                or candidate.get("classification_code")
                or candidate.get("clc_code")
                or candidate.get("code")
                or ""
            ).split("+", 1)[0].strip()
            if candidate_code and candidate_code != primary_code:
                raise ValueError("primary_code 与所选候选分类不一致")
            candidate_secondary = []
            aux_code = str(candidate.get("aux_code") or "").strip()
            if aux_code:
                candidate_secondary.append(aux_code)
            combined = str(candidate.get("classification_code") or "").split("+")[1:]
            candidate_secondary.extend(str(item).strip() for item in combined if str(item).strip())
            submitted_secondary = [
                str(item).strip() for item in (payload.get("secondary_codes") or []) if str(item).strip()
            ]
            if sorted(set(submitted_secondary)) != sorted(set(candidate_secondary)):
                raise ValueError("secondary_codes 与所选候选分类不一致")
        normalized = {
            **payload,
            "primary_code": primary_code,
            "secondary_codes": [
                str(item).strip() for item in (payload.get("secondary_codes") or []) if str(item).strip()
            ],
        }
        return self.repository.save_classification_confirmation(record_id, normalized)

    def confirm_cluster_label(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = self.repository.get_result(record_id)
        if not record or record.get("tool_id") != "cluster-label":
            raise ValueError("指定记录不是类簇标签结果")
        if payload.get("cluster_id") is None or not str(payload.get("label_text") or "").strip():
            raise ValueError("cluster_id 和 label_text 不能为空")
        return self.repository.save_cluster_label_confirmation(record_id, payload)

    def feedback(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.repository.get_result(record_id):
            raise ValueError("结果记录不存在")
        rating = payload.get("rating")
        if rating is not None and not 1 <= int(rating) <= 5:
            raise ValueError("rating 必须在 1—5 之间")
        if not any(payload.get(key) not in (None, "", {}) for key in ("rating", "comment", "correction")):
            raise ValueError("反馈内容不能为空")
        return self.repository.save_feedback(record_id, payload)


result_governance_service = ResultGovernanceService()
