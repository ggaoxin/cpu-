"""文献集合与用户词典应用服务。"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from config.settings import settings
from domain.repository.resource_repository import IResourceRepository
from infrastructure.database.resource_repository import resource_repository

logger = logging.getLogger(__name__)


class ResourceService:
    def __init__(self, repository: Optional[IResourceRepository] = None) -> None:
        self.repository = repository or resource_repository

    def create_collection(self, payload: Dict[str, Any], workspace_id: Optional[str] = None) -> Dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        documents = payload.get("documents") or []
        if not name:
            raise ValueError("文献集合名称不能为空")
        if not isinstance(documents, list) or not documents:
            raise ValueError("文献集合至少需要一篇文献")
        for index, document in enumerate(documents):
            if not isinstance(document, dict):
                raise ValueError(f"第 {index + 1} 篇文献格式不正确")
            if not any(str(document.get(key) or "").strip() for key in ("title", "abstract", "text", "content")):
                raise ValueError(f"第 {index + 1} 篇文献没有可保存内容")
        return self.repository.create_collection(
            workspace_id or settings.DEFAULT_WORKSPACE_ID,
            name,
            str(payload.get("description") or ""),
            documents,
        )

    def list_collections(
        self,
        workspace_id: Optional[str] = None,
        limit: int = 100,
        topic: Optional[str] = None,
        threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        collections = self.repository.list_collections(
            workspace_id or settings.DEFAULT_WORKSPACE_ID, limit
        )
        # 按研究主题↔场景标签（collection.name）bge-m3 语义相似度过滤：
        # 综述选定主题后，下拉只显示≥阈值的场景文献集（用户设计闭环）。
        topic_text = str(topic or "").strip()
        if not topic_text or not collections:
            return collections
        try:
            from infrastructure.rag.m3_encoder import m3_encoder
            names = [str(item.get("name") or "") for item in collections]
            vectors = m3_encoder.encode([topic_text, *names])
            query_vec = vectors[0]
            scores = vectors[1:] @ query_vec  # (N,) cosine（m3_encoder 已 L2 归一化）
            filtered = [
                {**item, "topic_similarity": round(float(scores[index]), 4)}
                for index, item in enumerate(collections)
                if float(scores[index]) >= float(threshold)
            ]
            return sorted(filtered, key=lambda item: item["topic_similarity"], reverse=True)
        except Exception as exc:  # noqa: BLE001 - 相似度失败回退全量，不阻断列表
            logger.warning("collection 主题相似度过滤失败，回退全量：%s", exc)
            return collections

    def get_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        return self.repository.get_collection(collection_id)

    def create_dictionary(self, payload: Dict[str, Any], workspace_id: Optional[str] = None) -> Dict[str, Any]:
        if not str(payload.get("name") or "").strip():
            raise ValueError("词典名称不能为空")
        if not payload.get("terms"):
            raise ValueError("词典至少需要一个术语")
        language = str(payload.get("language") or "zh").strip().lower()
        if language not in {"zh", "en"}:
            raise ValueError("词典 language 仅支持 zh 或 en")
        try:
            weight_boost = float(payload.get("weight_boost", 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("词典 weight_boost 必须是数值") from exc
        if not 0 <= weight_boost <= 0.5:
            raise ValueError("词典 weight_boost 必须在 0—0.5 之间")
        return self.repository.create_dictionary(
            workspace_id or settings.DEFAULT_WORKSPACE_ID,
            {**payload, "language": language, "weight_boost": weight_boost},
        )

    def list_dictionaries(self, workspace_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self.repository.list_dictionaries(workspace_id or settings.DEFAULT_WORKSPACE_ID, limit)

    def get_dictionary(self, dictionary_id: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return self.repository.get_dictionary(dictionary_id, version)

    def delete_dictionary(self, dictionary_id: str) -> bool:
        return self.repository.delete_dictionary(dictionary_id)

    def register_semantic_resource(self, payload: Dict[str, Any], workspace_id: Optional[str] = None) -> Dict[str, Any]:
        # CLC 资源：读 storage_uri 算 verdict 写 metadata.clc_verdict（供 _resource_context 分治）
        verdict = self._maybe_enrich_clc_verdict(payload)
        resource_row = self.repository.register_semantic_resource(
            workspace_id or settings.DEFAULT_WORKSPACE_ID,
            payload,
        )
        # 完整分类树 + 超阈值 → 异步建索引（供 for_path 加载替换内置检索）
        if verdict and verdict.get("kind") == "taxonomy_complete" \
                and verdict.get("record_count", 0) > settings.CLC_BUILD_MIN_RECORDS:
            from infrastructure.rag.clc_user_index_service import submit_build
            submit_build(resource_row)
        return resource_row

    @staticmethod
    def _maybe_enrich_clc_verdict(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """CLC 资源读 storage_uri entries 算 verdict，写回 payload.metadata.clc_verdict + record_count。"""
        resource_key = str(payload.get("resource_key") or "")
        storage_uri = str(payload.get("storage_uri") or "")
        if not resource_key or not storage_uri:
            return None
        try:
            from application.service.tool_integration_service import SEMANTIC_RESOURCE_FIELDS
        except ImportError:
            SEMANTIC_RESOURCE_FIELDS = set()
        if resource_key not in SEMANTIC_RESOURCE_FIELDS:
            return None
        try:
            with open(storage_uri, encoding="utf-8-sig") as f:
                entries = json.load(f)
            if not isinstance(entries, list):
                return None
            from infrastructure.rag.clc_user_index_service import compute_clc_verdict
            verdict = compute_clc_verdict(entries, os.path.getsize(storage_uri))
            meta = dict(payload.get("metadata") or {})
            meta["clc_verdict"] = verdict
            payload["metadata"] = meta
            payload["record_count"] = verdict["record_count"]
            logger.info("CLC 资源 %s verdict: %s", resource_key, verdict)
            return verdict
        except Exception as e:  # noqa: BLE001
            logger.warning("CLC 资源 %s verdict 计算失败: %s", resource_key, e)
            return None

    def list_semantic_resources(
        self,
        resource_key: Optional[str] = None,
        status: Optional[str] = "current",
        workspace_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        return self.repository.list_semantic_resources(
            workspace_id or settings.DEFAULT_WORKSPACE_ID,
            resource_key,
            status,
            limit,
        )

    def get_semantic_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        return self.repository.get_semantic_resource(resource_id)


resource_service = ResourceService()
