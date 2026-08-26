"""任务与结果的 MySQL/SQLite 仓储实现。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from domain.entity.analysis_task import AnalysisTask, ResultRecord, TaskStatus
from domain.repository.task_repository import ITaskRepository
from infrastructure.database.connection import Database, database
from infrastructure.database.result_projection import save_result_projection


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


class DatabaseTaskRepository(ITaskRepository):
    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or database

    def create_task(self, task: AnalysisTask) -> None:
        now = _now()
        with self.db.session() as session:
            session.execute(
                """INSERT INTO analysis_tasks
                (id, workspace_id, tool_id, backend_code, status, progress, input_type,
                 request_payload, parameters_json, model_version, total, success_count,
                 failed_count, error_summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id, task.workspace_id, task.tool_id, task.backend_code, task.status.value,
                    task.progress, task.input_type, _dump(task.request_payload), _dump(task.parameters),
                    task.model_version, task.total, task.success_count, task.failed_count,
                    task.error_summary, now, now,
                ),
            )

    def create_item(self, task_id: str, input_index: int, source: Dict[str, Any]) -> str:
        item_id = _id("itm")
        now = _now()
        with self.db.session() as session:
            session.execute(
                """INSERT INTO task_items
                (id, task_id, input_index, status, source_json, created_at, updated_at)
                VALUES (?, ?, ?, 'queued', ?, ?, ?)""",
                (item_id, task_id, input_index, _dump(source), now, now),
            )
        return item_id

    def update_item(self, item_id: str, status: str, error: Optional[str] = None) -> None:
        with self.db.session() as session:
            session.execute(
                "UPDATE task_items SET status=?, error_message=?, updated_at=? WHERE id=?",
                (status, error, _now(), item_id),
            )

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        progress: Optional[int] = None,
        success_count: Optional[int] = None,
        failed_count: Optional[int] = None,
        error_summary: Optional[str] = None,
    ) -> None:
        updates = ["status=?", "updated_at=?"]
        values: list[Any] = [status.value, _now()]
        for column, value in (
            ("progress", progress), ("success_count", success_count),
            ("failed_count", failed_count), ("error_summary", error_summary),
        ):
            if value is not None:
                updates.append(f"{column}=?")
                values.append(value)
        if status in {TaskStatus.SUCCEEDED, TaskStatus.PARTIAL_FAILED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            updates.append("completed_at=?")
            values.append(_now())
        values.append(task_id)
        with self.db.session() as session:
            session.execute(f"UPDATE analysis_tasks SET {', '.join(updates)} WHERE id=?", values)

    def save_result(self, record: ResultRecord) -> None:
        with self.db.session() as session:
            session.execute(
                """INSERT INTO result_records
                (id, task_id, task_item_id, tool_id, backend_code, result_json, schema_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id, record.task_id, record.task_item_id, record.tool_id,
                    record.backend_code, _dump(record.result), record.schema_version, _now(),
                ),
            )
            save_result_projection(session, record)

    def add_dependencies(self, record_id: str, upstream_ids: Iterable[str], dependency_type: str) -> None:
        rows = [(_id("dep"), record_id, upstream_id, dependency_type, _now()) for upstream_id in upstream_ids if upstream_id]
        if not rows:
            return
        with self.db.session() as session:
            session.executemany(
                """INSERT INTO record_dependencies
                (id, record_id, upstream_record_id, dependency_type, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                rows,
            )

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            row = session.fetchone("SELECT * FROM analysis_tasks WHERE id=?", (task_id,))
        return self._task_row(row) if row else None

    def list_tasks(self, workspace_id: str, tool_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM analysis_tasks WHERE workspace_id=? AND archived_at IS NULL"
        values: list[Any] = [workspace_id]
        if tool_id:
            sql += " AND tool_id=?"
            values.append(tool_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        values.append(max(1, min(int(limit), 200)))
        with self.db.session() as session:
            rows = session.fetchall(sql, values)
        summaries = [self._task_row(row) for row in rows]
        for item in summaries:
            item.pop("request_payload", None)
        return summaries

    def get_result(self, record_id: str) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            row = session.fetchone("SELECT * FROM result_records WHERE id=?", (record_id,))
        return self._result_row(row) if row else None

    def get_task_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Return the exact persisted input item linked to one result record."""
        with self.db.session() as session:
            row = session.fetchone("SELECT * FROM task_items WHERE id=?", (item_id,))
        if not row:
            return None
        value = dict(row)
        value["source"] = _load(value.pop("source_json", None), {})
        return value

    def list_results(self, task_id: str) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            rows = session.fetchall(
                # 降序：最新结果在前。compatible_history 遍历时让最新 record 的 option
                # 排在同任务多项之前，_result_from_task 取 records[0] 也命中最新，
                # 避免重跑/重算产生的多 record 把旧结果当成"当前"提交给下游。
                "SELECT * FROM result_records WHERE task_id=? ORDER BY created_at DESC, id DESC",
                (task_id,),
            )
        return [self._result_row(row) for row in rows]

    def archive_task(self, task_id: str) -> bool:
        with self.db.session() as session:
            cursor = session.execute(
                "UPDATE analysis_tasks SET archived_at=?, updated_at=? WHERE id=? AND archived_at IS NULL",
                (_now(), _now(), task_id),
            )
            return bool(cursor.rowcount)

    def cancel_task(self, task_id: str) -> bool:
        with self.db.session() as session:
            cursor = session.execute(
                """UPDATE analysis_tasks SET status='cancelled', completed_at=?, updated_at=?
                WHERE id=? AND status IN ('draft','queued','running')""",
                (_now(), _now(), task_id),
            )
            return bool(cursor.rowcount)

    def get_lineage(self, record_id: str) -> Dict[str, Any]:
        with self.db.session() as session:
            upstream = session.fetchall(
                """SELECT d.dependency_type, r.* FROM record_dependencies d
                JOIN result_records r ON r.id=d.upstream_record_id WHERE d.record_id=?""",
                (record_id,),
            )
            downstream = session.fetchall(
                """SELECT d.dependency_type, r.* FROM record_dependencies d
                JOIN result_records r ON r.id=d.record_id WHERE d.upstream_record_id=?""",
                (record_id,),
            )
        return {
            "record_id": record_id,
            "upstream": [self._result_row(row) for row in upstream],
            "downstream": [self._result_row(row) for row in downstream],
        }

    def save_classification_confirmation(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        confirmation_id = _id("ccf")
        now = _now()
        secondary_codes = payload.get("secondary_codes") or []
        confirmation = {
            "id": confirmation_id,
            "result_record_id": record_id,
            "status": "confirmed",
            "primary_code": payload["primary_code"],
            "secondary_codes": secondary_codes,
            "confirmed_candidate_id": payload.get("candidate_id"),
            "confirmed_path": payload.get("confirmed_path"),
            "confirmed_by": payload.get("actor_id"),
            "confirmed_at": now,
            "reason": payload.get("reason"),
        }
        main_code = payload["primary_code"]
        candidate_id = payload.get("candidate_id")
        with self.db.session() as session:
            session.execute(
                """INSERT INTO classification_confirmations
                (id, result_record_id, primary_code, secondary_codes, actor_id, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (confirmation_id, record_id, payload["primary_code"], _dump(secondary_codes), payload.get("actor_id"), payload.get("reason"), now),
            )
            row = session.fetchone("SELECT result_json FROM result_records WHERE id=?", (record_id,))
            result = _load(row.get("result_json") if row else None, {})
            # 优先用 payload 携带的候选完整结构；否则按 candidate_id 从结果候选列表回查
            cand = payload.get("candidate_classification") if isinstance(payload.get("candidate_classification"), dict) else {}
            if not cand and candidate_id:
                for _c in (result.get("candidate_classifications") or result.get("candidates") or []):
                    if isinstance(_c, dict) and str(_c.get("candidate_id") or "") == str(candidate_id):
                        cand = _c
                        break
            main_name = cand.get("main_name") or cand.get("label") or ""
            main_path = cand.get("main_path") or cand.get("classification_path") or payload.get("confirmed_path") or []
            aux_code = cand.get("aux_code")
            aux_name = cand.get("aux_name") or ""
            aux_path = cand.get("aux_path") or []
            _raw_conf = cand.get("confidence")
            try:
                _conf_num = float(_raw_conf) if _raw_conf is not None else None
            except (TypeError, ValueError):
                _conf_num = None
            new_primary = {
                "role": "main",
                "clc_code": main_code,
                "code": main_code,
                "label": main_name,
                "category_name": main_name,
                "classification_path": main_path,
                "path": main_path,
                "confidence": _raw_conf,
            }
            new_secondary = None
            if aux_code:
                new_secondary = {
                    "role": "secondary",
                    "clc_code": aux_code,
                    "code": aux_code,
                    "label": aux_name,
                    "category_name": aux_name,
                    "classification_path": aux_path,
                    "path": aux_path,
                    "confidence": _raw_conf,
                }
            new_classifications = [new_primary] + ([new_secondary] if new_secondary else [])
            result["manual_confirmation"] = confirmation
            result["confirmation_status"] = "confirmed"
            # 同步替换：主/次分类改为用户确认的候选，重新拉取即见确认后结果
            result["classifications"] = new_classifications
            result["multilevel_classification_results"] = new_classifications
            result["primary_classification"] = new_primary
            if new_secondary:
                result["secondary_classification"] = new_secondary
            else:
                result.pop("secondary_classification", None)
            session.execute("UPDATE result_records SET result_json=? WHERE id=?", (_dump(result), record_id))
            session.execute(
                """UPDATE classification_results
                SET primary_code=?, primary_name=?, primary_path=?, primary_confidence=?, confirmation_status='confirmed'
                WHERE result_record_id=?""",
                (main_code, main_name, _dump(main_path), _conf_num, record_id),
            )
            # 投影同步：删旧主/次/候选行，按确认后的主/次重新插入，保持一致
            session.execute("DELETE FROM classification_candidates WHERE result_record_id=?", (record_id,))
            cand_rows = [(_id("clc"), record_id, "primary", main_code, main_name, _dump(main_path), _conf_num, 1)]
            if new_secondary:
                cand_rows.append((_id("clc"), record_id, "secondary", aux_code, aux_name, _dump(aux_path), _conf_num, 2))
            for _cid, _rid, _role, _code, _name, _path, _conf, _rank in cand_rows:
                session.execute(
                    """INSERT INTO classification_candidates
                    (id, result_record_id, role_name, class_code, class_name, path_json, confidence, rank_no)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (_cid, _rid, _role, _code, _name, _path, _conf, _rank),
                )
        return confirmation

    def save_cluster_label_confirmation(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        confirmation_id = _id("lcf")
        now = _now()
        with self.db.session() as session:
            session.execute(
                """INSERT INTO cluster_label_confirmations
                (id, result_record_id, cluster_id, label_text, actor_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (confirmation_id, record_id, str(payload["cluster_id"]), payload["label_text"], payload.get("actor_id"), now),
            )
        return {"id": confirmation_id, "result_record_id": record_id, "cluster_id": str(payload["cluster_id"]), "label_text": payload["label_text"], "created_at": now}

    def save_feedback(self, record_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        feedback_id = _id("fbk")
        now = _now()
        with self.db.session() as session:
            session.execute(
                """INSERT INTO user_feedback
                (id, result_record_id, feedback_type, rating, comment, correction_json, actor_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (feedback_id, record_id, payload.get("feedback_type", "comment"), payload.get("rating"), payload.get("comment"), _dump(payload.get("correction") or {}), payload.get("actor_id"), now),
            )
        return {"id": feedback_id, "result_record_id": record_id, "feedback_type": payload.get("feedback_type", "comment"), "created_at": now}

    def healthcheck(self) -> Dict[str, Any]:
        return self.db.healthcheck()

    @staticmethod
    def _task_row(row: Dict[str, Any]) -> Dict[str, Any]:
        value = dict(row)
        value["request_payload"] = _load(value.get("request_payload"), {})
        value["parameters"] = _load(value.pop("parameters_json", None), {})
        return value

    @staticmethod
    def _result_row(row: Dict[str, Any]) -> Dict[str, Any]:
        value = dict(row)
        value["result"] = _load(value.pop("result_json", None), {})
        return value


task_repository = DatabaseTaskRepository()
