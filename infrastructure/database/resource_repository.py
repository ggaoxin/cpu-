"""文献集合、用户词典和导出记录的数据库实现。"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.settings import settings
from domain.repository.resource_repository import IResourceRepository
from infrastructure.database.connection import Database, database


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_DICT_STAMP_RE = re.compile(r"_\d{8}_\d{4}$")


def _strip_dict_stamp(name: str) -> str:
    """剥离词典名末尾的时间戳（_YYYYMMDD_HHMM），得到基础名用于按基础名归并。"""
    return _DICT_STAMP_RE.sub("", str(name or "")).strip()


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


class DatabaseResourceRepository(IResourceRepository):
    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or database

    def create_collection(self, workspace_id: str, name: str, description: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        collection_id = _id("col")
        now = _now()
        with self.db.session() as session:
            session.execute(
                """INSERT INTO document_collections
                (id, workspace_id, name, description, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)""",
                (collection_id, workspace_id, name, description, now, now),
            )
            for order_no, document in enumerate(documents):
                content = str(document.get("content") or document.get("text") or "")
                abstract = str(document.get("abstract") or document.get("abstract_text") or "")
                content_hash = hashlib.sha256(f"{document.get('title', '')}\n{abstract}\n{content}".encode("utf-8")).hexdigest()
                metadata = {
                    "source_document_id": document.get("id"),
                    "keywords": document.get("keywords") or [],
                    "published_at": document.get("published_at"),
                    **(document.get("metadata") or {}),
                }
                # 改动3: 按 (workspace_id, content_hash) 复用已存文献，避免聚类重跑或
                # 同篇跨簇重复写 documents（利用现成 idx_documents_hash 索引）。仅当文献
                # 不存在时才 INSERT；collection_documents 关联去重，防联合主键冲突。
                existing_doc = session.fetchone(
                    "SELECT id FROM documents WHERE workspace_id=? AND content_hash=? LIMIT 1",
                    (workspace_id, content_hash),
                )
                if existing_doc:
                    document_id = existing_doc["id"]
                else:
                    document_id = _id("doc")
                    session.execute(
                        """INSERT INTO documents
                        (id, workspace_id, language, title, abstract_text, content_text, content_hash,
                         metadata_json, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            document_id, workspace_id, document.get("language"), document.get("title"),
                            abstract, content, content_hash, _dump(metadata), now, now,
                        ),
                    )
                link_exists = session.fetchone(
                    "SELECT 1 FROM collection_documents WHERE collection_id=? AND document_id=? LIMIT 1",
                    (collection_id, document_id),
                )
                if not link_exists:
                    session.execute(
                        "INSERT INTO collection_documents (collection_id, document_id, order_no) VALUES (?, ?, ?)",
                        (collection_id, document_id, order_no),
                    )
        return self.get_collection(collection_id) or {"id": collection_id}

    def list_collections(self, workspace_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            rows = session.fetchall(
                """SELECT c.*, COUNT(cd.document_id) AS document_count
                FROM document_collections c
                LEFT JOIN collection_documents cd ON cd.collection_id=c.id
                WHERE c.workspace_id=? AND c.archived_at IS NULL
                GROUP BY c.id ORDER BY c.created_at DESC LIMIT ?""",
                (workspace_id, max(1, min(int(limit), 200))),
            )
        return rows

    def update_collection_name(self, collection_id: str, name: str) -> None:
        """更新文献集名称(聚类标签生成后用最终标签重命名)。"""
        with self.db.session() as session:
            session.execute(
                "UPDATE document_collections SET name = %s WHERE id = %s",
                (name, collection_id),
            )

    def get_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            collection = session.fetchone(
                """SELECT c.*, COUNT(cd.document_id) AS document_count
                FROM document_collections c LEFT JOIN collection_documents cd ON cd.collection_id=c.id
                WHERE c.id=? GROUP BY c.id""",
                (collection_id,),
            )
            if not collection:
                return None
            documents = session.fetchall(
                """SELECT d.*, cd.order_no FROM collection_documents cd
                JOIN documents d ON d.id=cd.document_id
                WHERE cd.collection_id=? ORDER BY cd.order_no""",
                (collection_id,),
            )
        for document in documents:
            document["metadata"] = _load(document.pop("metadata_json", None), {})
        return {**collection, "documents": documents}

    def create_dictionary(self, workspace_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        dictionary_id = _id("dic")
        version_id = _id("div")
        now = _now()
        full_name = str(payload["name"]).strip()
        base_name = _strip_dict_stamp(full_name)
        language = payload.get("language", "zh")
        terms = payload.get("terms") or []
        if isinstance(terms, str):
            terms = [item.strip() for item in re.split(r"[\r\n,，;；]+", terms) if item.strip()]
        normalized_terms: Dict[str, Dict[str, Any]] = {}
        for item in terms:
            term = str(item.get("term") if isinstance(item, dict) else item).strip()
            if term:
                normalized_terms.setdefault(term.casefold(), {
                    "term": term,
                    "weight": float(item.get("weight", 1)) if isinstance(item, dict) else 1.0,
                })
        unique_terms = list(normalized_terms.values())
        content_hash = hashlib.sha256("\n".join(item["term"] for item in unique_terms).encode("utf-8")).hexdigest()
        with self.db.session() as session:
            # 按基础名归并：同名（基础名）词典视为同一个，新增版本；名字更新为最新时间戳，便于溯源。
            candidates = session.fetchall(
                "SELECT id, current_version, name FROM dictionaries WHERE workspace_id=? AND language=? AND status='active'",
                (workspace_id, language),
            )
            existing = next((c for c in candidates if _strip_dict_stamp(c["name"]) == base_name), None)
            if existing:
                dictionary_id = existing["id"]
                version = int(existing["current_version"]) + 1
                session.execute(
                    "UPDATE dictionaries SET name=?, current_version=?, status='active', updated_at=? WHERE id=?",
                    (full_name, version, now, dictionary_id),
                )
            else:
                version = 1
                session.execute(
                    """INSERT INTO dictionaries
                    (id, workspace_id, name, language, status, current_version, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'active', 1, ?, ?)""",
                    (dictionary_id, workspace_id, full_name, language, now, now),
                )
            session.execute(
                """INSERT INTO dictionary_versions
                (id, dictionary_id, version, weight_boost, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (version_id, dictionary_id, version, float(payload.get("weight_boost", 0)), content_hash, now),
            )
            rows = [
                (_id("dit"), version_id, item["term"], item["term"].casefold(), item["weight"])
                for item in unique_terms
            ]
            if rows:
                session.executemany(
                    """INSERT INTO dictionary_terms
                    (id, dictionary_version_id, term, normalized_term, weight)
                    VALUES (?, ?, ?, ?, ?)""",
                    rows,
                )
            # 版本上限：保留最近 5 个版本，超出则硬删除最早版本的术语与版本记录。
            all_versions = session.fetchall(
                "SELECT id, version FROM dictionary_versions WHERE dictionary_id=? ORDER BY version ASC",
                (dictionary_id,),
            )
            if len(all_versions) > 5:
                for ov in all_versions[: len(all_versions) - 5]:
                    session.execute("DELETE FROM dictionary_terms WHERE dictionary_version_id=?", (ov["id"],))
                    session.execute("DELETE FROM dictionary_versions WHERE id=?", (ov["id"],))
        return {"id": dictionary_id, "version_id": version_id, "version": version, "name": full_name, "language": language, "term_count": len(unique_terms), "weight_boost": float(payload.get("weight_boost", 0))}

    def list_dictionaries(self, workspace_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            return session.fetchall(
                """SELECT d.*, COUNT(t.id) AS term_count, v.weight_boost
                FROM dictionaries d JOIN dictionary_versions v
                  ON v.dictionary_id=d.id AND v.version=d.current_version
                LEFT JOIN dictionary_terms t ON t.dictionary_version_id=v.id
                WHERE d.workspace_id=? AND d.status='active'
                GROUP BY d.id, v.id ORDER BY d.updated_at DESC LIMIT ?""",
                (workspace_id, max(1, min(int(limit), 200))),
            )

    def delete_dictionary(self, dictionary_id: str) -> bool:
        """软删除词典：置 status='deleted'，使其从列表中隐藏（历史数据保留，可恢复）。"""
        with self.db.session() as session:
            cur = session.execute(
                "UPDATE dictionaries SET status='deleted', updated_at=? WHERE id=? AND status='active'",
                (_now(), dictionary_id),
            )
            return cur.rowcount > 0

    def get_dictionary(self, dictionary_id: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            dictionary = session.fetchone("SELECT * FROM dictionaries WHERE id=? AND status='active'", (dictionary_id,))
            if not dictionary:
                return None
            selected_version = int(version or dictionary["current_version"])
            version_row = session.fetchone(
                "SELECT * FROM dictionary_versions WHERE dictionary_id=? AND version=?",
                (dictionary_id, selected_version),
            )
            if not version_row:
                return None
            terms = session.fetchall(
                "SELECT id, term, normalized_term, weight FROM dictionary_terms WHERE dictionary_version_id=? ORDER BY term",
                (version_row["id"],),
            )
            versions = session.fetchall(
                """SELECT id AS version_id, version, weight_boost, created_at
                FROM dictionary_versions WHERE dictionary_id=? ORDER BY version DESC""",
                (dictionary_id,),
            )
        return {
            **dictionary,
            "version_id": version_row["id"],
            "version": selected_version,
            "weight_boost": float(version_row.get("weight_boost") or 0),
            "terms": terms,
            "term_count": len(terms),
            "versions": versions,
        }

    def register_semantic_resource(self, workspace_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a versioned resource used by a Vue request field."""
        resource_id = str(payload.get("id") or _id("res"))
        resource_key = str(payload.get("resource_key") or "").strip()
        name = str(payload.get("name") or "").strip()
        version = str(payload.get("version") or "1").strip()
        if not resource_key or not name:
            raise ValueError("resource_key 和 name 为必填项")
        now = _now()
        with self.db.session() as session:
            existing = session.fetchone(
                "SELECT id FROM semantic_resources WHERE workspace_id=? AND resource_key=? AND version=?",
                (workspace_id, resource_key, version),
            )
            values = (
                name, payload.get("language"), payload.get("record_count"),
                payload.get("status", "current"), payload.get("source_type", "bundled"),
                payload.get("storage_uri"), payload.get("content_hash"),
                _dump(payload.get("metadata") or {}), now,
            )
            if existing:
                resource_id = existing["id"]
                session.execute(
                    """UPDATE semantic_resources SET name=?, language=?, record_count=?, status=?,
                    source_type=?, storage_uri=?, content_hash=?, metadata_json=?, updated_at=? WHERE id=?""",
                    (*values, resource_id),
                )
            else:
                session.execute(
                    """INSERT INTO semantic_resources
                    (id, workspace_id, resource_key, name, version, language, record_count, status,
                     source_type, storage_uri, content_hash, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (resource_id, workspace_id, resource_key, name, version, *values[1:-1], now, now),
                )
        return self.get_semantic_resource(resource_id) or {"id": resource_id}

    def list_semantic_resources(
        self,
        workspace_id: str,
        resource_key: Optional[str] = None,
        status: Optional[str] = "current",
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        clauses = ["workspace_id=?"]
        params: List[Any] = [workspace_id]
        if resource_key:
            clauses.append("resource_key=?")
            params.append(resource_key)
        if status:
            clauses.append("status=?")
            params.append(status)
        params.append(max(1, min(int(limit), 500)))
        with self.db.session() as session:
            rows = session.fetchall(
                f"SELECT * FROM semantic_resources WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?",
                tuple(params),
            )
        for row in rows:
            row["metadata"] = _load(row.pop("metadata_json", None), {})
        return rows

    def delete_semantic_resource(self, resource_id: str) -> bool:
        """硬删除用户上传型资源行（一次性语义：测试结束即删，不保留复用）。"""
        with self.db.session() as session:
            cur = session.execute(
                "DELETE FROM semantic_resources WHERE id=? AND source_type='upload'",
                (resource_id,),
            )
            return cur.rowcount > 0

    def get_semantic_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            row = session.fetchone("SELECT * FROM semantic_resources WHERE id=?", (resource_id,))
        if row:
            row["metadata"] = _load(row.pop("metadata_json", None), {})
        return row

    def create_export(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        export_id = str(payload.get("id") or _id("exp"))
        with self.db.session() as session:
            session.execute(
                """INSERT INTO exports
                (id, workspace_id, task_id, result_record_id, format, status, object_key,
                 error_message, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    export_id, payload.get("workspace_id", settings.DEFAULT_WORKSPACE_ID),
                    payload.get("task_id"), payload.get("result_record_id"), payload["format"],
                    payload.get("status", "succeeded"), payload.get("object_key"),
                    payload.get("error_message"), _now(), payload.get("expires_at"),
                ),
            )
        return self.get_export(export_id) or {"id": export_id}

    def get_export(self, export_id: str) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            return session.fetchone("SELECT * FROM exports WHERE id=?", (export_id,))


resource_repository = DatabaseResourceRepository()
