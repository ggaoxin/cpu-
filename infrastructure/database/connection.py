"""支持 MySQL 8 与 SQLite 开发回退的轻量数据库连接。"""
from __future__ import annotations

import contextlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Sequence
from urllib.parse import parse_qs, unquote, urlparse

from config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseSession:
    def __init__(self, connection: Any, dialect: str) -> None:
        self.connection = connection
        self.dialect = dialect

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.dialect == "mysql" else sql

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        if self.dialect == "mysql":
            cursor = self.connection.cursor()
            cursor.execute(self._sql(sql), tuple(params))
            return cursor
        return self.connection.execute(sql, tuple(params))

    def executemany(self, sql: str, params: Iterable[Sequence[Any]]) -> Any:
        if self.dialect == "mysql":
            cursor = self.connection.cursor()
            cursor.executemany(self._sql(sql), list(params))
            return cursor
        return self.connection.executemany(sql, list(params))

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
        row = self.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[Dict[str, Any]]:
        return [dict(row) for row in self.execute(sql, params).fetchall()]


class Database:
    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url or settings.DATABASE_URL
        self.dialect = "mysql" if self.url.startswith(("mysql://", "mysql+pymysql://")) else "sqlite"

    def _sqlite_path(self) -> Path:
        raw = self.url.removeprefix("sqlite:///")
        path = Path(unquote(raw))
        if not path.is_absolute():
            path = settings.PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _connect(self) -> Any:
        if self.dialect == "sqlite":
            connection = sqlite3.connect(self._sqlite_path(), timeout=30, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection

        try:
            import pymysql
        except ImportError as exc:  # pragma: no cover - exercised on MySQL deployment
            raise RuntimeError("MySQL 模式需要安装 PyMySQL：pip install PyMySQL") from exc

        parsed = urlparse(self.url.replace("mysql+pymysql://", "mysql://", 1))
        query = parse_qs(parsed.query)
        return pymysql.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 3306,
            user=unquote(parsed.username or "root"),
            password=unquote(parsed.password or ""),
            database=parsed.path.lstrip("/"),
            charset=query.get("charset", ["utf8mb4"])[0],
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )

    @contextlib.contextmanager
    def session(self) -> Iterator[DatabaseSession]:
        connection = self._connect()
        try:
            yield DatabaseSession(connection, self.dialect)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        schema_name = "schema_mysql.sql" if self.dialect == "mysql" else "schema_sqlite.sql"
        schema = (Path(__file__).parent / schema_name).read_text(encoding="utf-8")
        connection = self._connect()
        try:
            if self.dialect == "sqlite":
                connection.executescript(schema)
            else:
                cursor = connection.cursor()
                for statement in [part.strip() for part in schema.split(";") if part.strip()]:
                    cursor.execute(statement)
            connection.commit()
        finally:
            connection.close()
        self._seed_bundled_semantic_resources()

    def _seed_bundled_semantic_resources(self) -> None:
        from config.default_semantic_resources import BUNDLED_SEMANTIC_RESOURCES

        now = datetime.now(timezone.utc).isoformat()
        verb = "INSERT IGNORE" if self.dialect == "mysql" else "INSERT OR IGNORE"
        with self.session() as session:
            for resource_id, resource_key, name, storage_uri, language in BUNDLED_SEMANTIC_RESOURCES:
                session.execute(
                    f"""{verb} INTO semantic_resources
                    (id, workspace_id, resource_key, name, version, language, record_count, status,
                     source_type, storage_uri, content_hash, metadata_json, created_at, updated_at)
                    VALUES (?, 'default', ?, ?, 'bundled', ?, NULL, 'current', 'bundled', ?, NULL, ?, ?, ?)""",
                    (resource_id, resource_key, name, language, storage_uri, "{}", now, now),
                )
                # Bundled registrations are deployment configuration, not user
                # content. Keep their path/name synchronized after an upgrade;
                # uploaded/user-created versions are never touched here.
                session.execute(
                    """UPDATE semantic_resources SET name=?, language=?, storage_uri=?, updated_at=?
                    WHERE id=? AND source_type='bundled'""",
                    (name, language, storage_uri, now, resource_id),
                )

    def healthcheck(self) -> Dict[str, Any]:
        try:
            with self.session() as session:
                row = session.fetchone("SELECT 1 AS ok")
            return {"status": "ok", "dialect": self.dialect, "connected": bool(row and row["ok"] == 1)}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "dialect": self.dialect, "connected": False, "error": str(exc)}


database = Database()
