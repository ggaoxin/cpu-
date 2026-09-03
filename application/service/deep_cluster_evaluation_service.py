"""Independent deep-clustering evaluation against a user-selected gold set."""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

from application.dto.common_dto import SemanticRequest
from config.settings import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("data", "documents", "records", "items", "results"):
            if isinstance(value.get(key), list):
                return [item for item in value[key] if isinstance(item, dict)]
    return []


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"评测资源文件不存在：{path}")
    # 用户 JSON 资源优先取公共归一化结果（别名 category→technical_cluster_id 等
    # 已处理）；jsonl/未预检路径维持原解析。
    from infrastructure.resources.normalize import normalized_rows_for
    _normalized = normalized_rows_for(path)
    if _normalized is not None:
        return _normalized
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return _rows(json.loads(path.read_text(encoding="utf-8-sig")))


def _project_path(uri: str) -> Path:
    if uri.startswith("project://"):
        return settings.PROJECT_ROOT / uri.removeprefix("project://")
    return Path(uri)


def _descriptor_path(descriptor: Any, resource_repository: Any, expected_key: str) -> Path:
    if not isinstance(descriptor, dict):
        raise ValueError(f"{expected_key} 必须选择数据库资源或上传资源文件")
    if descriptor.get("source") == "upload" and descriptor.get("storage_uri"):
        return _project_path(str(descriptor["storage_uri"]))
    resource_id = str(descriptor.get("resource_id") or "")
    resource = resource_repository.get_semantic_resource(resource_id) if resource_id else None
    if not resource or resource.get("resource_key") != expected_key:
        raise ValueError(f"{expected_key} 资源不存在或类型不匹配")
    uri = str(resource.get("storage_uri") or "")
    if not uri:
        raise ValueError(f"{expected_key} 没有可读取的存储地址")
    return _project_path(uri)


def _document_id(row: dict[str, Any], index: int) -> str:
    return str(row.get("document_id") or row.get("id") or row.get("record_id") or f"EVAL{index + 1:04d}")


def _document_text(row: dict[str, Any]) -> str:
    title = str(row.get("title") or row.get("ch_name") or row.get("en_name") or "").strip()
    body = str(
        row.get("text") or row.get("content") or row.get("abstract")
        or row.get("ch_abstract") or row.get("en_abstract") or ""
    ).strip()
    keywords = row.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]
    return "\n".join(part for part in (
        f"题名：{title}" if title else "",
        f"文本：{body}" if body else "",
        f"关键词：{'；'.join(map(str, keywords))}" if keywords else "",
    ) if part)


def _gold_label(row: dict[str, Any], dimension: str) -> str:
    keys = (
        ("application_cluster_id", "application_label", "application_gold", "gold_label", "label")
        if dimension == "application"
        else ("technical_cluster_id", "technical_label", "technical_gold", "gold_label", "label")
    )
    return str(next((row.get(key) for key in keys if row.get(key) not in (None, "")), ""))


def _stratified_limit(rows: Iterable[tuple[dict[str, Any], str]], limit: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row, label in rows:
        groups[label].append(row)
    chosen: list[dict[str, Any]] = []
    while len(chosen) < limit and any(groups.values()):
        for label in sorted(groups):
            if groups[label] and len(chosen) < limit:
                chosen.append(groups[label].pop(0))
    return chosen


class DeepClusterEvaluationService:
    def __init__(self, integration_service: Any) -> None:
        self.integration = integration_service

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        dimension = "application" if str(payload.get("cluster_dimension") or "technology") in {"application", "application_scenario"} else "technical"
        training_path = _descriptor_path(payload.get("training_samples"), self.integration.resource_repository, "training_samples")
        gold_path = _descriptor_path(payload.get("manually_labeled_category_data"), self.integration.resource_repository, "manually_labeled_category_data")
        training_rows = _load_json(training_path)
        gold_rows = _load_json(gold_path)
        gold_by_id = {_document_id(row, index): _gold_label(row, dimension) for index, row in enumerate(gold_rows)}
        aligned = []
        for index, row in enumerate(training_rows):
            document_id = _document_id(row, index)
            label = gold_by_id.get(document_id) or _gold_label(row, dimension)
            text = _document_text(row)
            if label and text:
                aligned.append(({**row, "document_id": document_id, "_evaluation_text": text}, label))
        limit = max(4, min(int(payload.get("evaluation_limit") or 200), 1000))
        selected = _stratified_limit(aligned, limit)
        if len(selected) < 4:
            raise ValueError("训练样本与人工标注答案按 document_id 对齐后不足4条")
        selected_ids = {_document_id(row, index) for index, row in enumerate(selected)}
        expected = {doc_id: label for row, label in aligned for doc_id in [_document_id(row, 0)] if doc_id in selected_ids}
        texts = [json.dumps({
            "document_id": _document_id(row, index),
            "title": row.get("title") or row.get("ch_name") or row.get("en_name") or "",
            "text": row["_evaluation_text"],
            "keywords": row.get("keywords") or [],
        }, ensure_ascii=False) for index, row in enumerate(selected)]
        semantic = self.integration.semantic_service.execute("dc_cluster", SemanticRequest(
            texts=texts,
            params={
                "cluster_dimension": "application" if dimension == "application" else "technology",
                "cluster_axis": dimension,
                "algorithm": payload.get("clustering_algorithm_type") or "auto",
                "cluster_count": payload.get("cluster_count"),
            },
            meta={"source": "independent_evaluation"},
        ))
        if not semantic.success:
            raise RuntimeError(semantic.error or "深度聚类评测运行失败")
        output = semantic.data if isinstance(semantic.data, dict) else {}
        predicted: dict[str, str] = {}
        for document in output.get("documents") or []:
            if not isinstance(document, dict):
                continue
            axis = document.get(dimension) or {}
            predicted[str(document.get("document_id"))] = str(axis.get("topic_id") or "")
        common = [document_id for document_id in expected if predicted.get(document_id)]
        if len(common) < 4:
            raise RuntimeError("聚类结果与人工标注答案无法按 document_id 对齐")
        y_true = [expected[document_id] for document_id in common]
        y_pred = [predicted[document_id] for document_id in common]
        from sklearn.metrics import (
            adjusted_rand_score, completeness_score, homogeneity_score,
            normalized_mutual_info_score, v_measure_score,
        )
        metrics = {
            "adjusted_rand_index": round(float(adjusted_rand_score(y_true, y_pred)), 6),
            "normalized_mutual_information": round(float(normalized_mutual_info_score(y_true, y_pred)), 6),
            "homogeneity": round(float(homogeneity_score(y_true, y_pred)), 6),
            "completeness": round(float(completeness_score(y_true, y_pred)), 6),
            "v_measure": round(float(v_measure_score(y_true, y_pred)), 6),
            "silhouette_score": (output.get("clustering_quality") or {}).get("silhouette_score"),
        }
        run_id = f"eval_{uuid.uuid4().hex}"
        result = {
            "evaluation_id": run_id,
            "status": "succeeded",
            "cluster_dimension": dimension,
            "sample_count": len(common),
            "gold_class_count": len(set(y_true)),
            "predicted_cluster_count": len(set(y_pred)),
            "metrics": metrics,
            "training_resource_id": payload["training_samples"].get("resource_id"),
            "gold_resource_id": payload["manually_labeled_category_data"].get("resource_id"),
            "completed_at": _now(),
        }
        with self.integration.repository.db.session() as session:
            session.execute(
                """INSERT INTO model_evaluation_runs
                (id, workspace_id, model_name, evaluation_type, status, request_json, metrics_json, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, settings.DEFAULT_WORKSPACE_ID, settings.MODEL_VERSION, f"deep_cluster_{dimension}",
                 "succeeded", json.dumps(payload, ensure_ascii=False, default=str),
                 json.dumps(result, ensure_ascii=False), result["completed_at"], result["completed_at"]),
            )
        return result

