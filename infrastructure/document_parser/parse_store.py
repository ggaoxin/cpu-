"""预解析文本缓存：上传阶段把文件解析成文本，提交时只带 parse_id。

用途（2026-09-07 用户定调）：文件读取与解析前移到上传动作，点「在线测试」
只做功能计算——响应时间不再包含 PDF 解析（mineru 可达 45s+）。
上传时 POST /api/v1/files/parse 落文本进本缓存并返回 parse_id；提交时
file/batch 路由带 preparsed=[parse_id,...] 直接取文本，不再上传文件本体。

多 Worker 改造（2026-09-21 甲方机器事故整改）：原实现是进程内存字典，
Uvicorn 开 --workers 2 后「上传落在 Worker A、提交落在 Worker B」会查不到
parse_id 导致文件"消失"。现改为 MySQL/SQLite 持久化为主、进程内存为
同 Worker 快路径：任一 Worker 写入全 Worker 可见；同 Worker 命中内存
免一次 DB 查询。DB 不可用时自动回退纯内存（单 worker 行为不变）。
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TTL_SECONDS = 2 * 60 * 60          # 解析结果保留 2 小时（足够用户填元数据再提交）
_CAP = 200                          # 最多缓存 200 条（批量 20 文件 × 多任务余量）

_LOCK = threading.Lock()
_STORE: Dict[str, Dict[str, Any]] = {}   # 同 Worker 快路径（DB 写成功也留一份）

_db_checked = False
_db_usable = False


def _db():
    global _db_checked, _db_usable
    if not _db_checked:
        try:
            from infrastructure.database.connection import database as _d
            _d.initialize()  # 幂等：含 parse_store 建表
            _db_usable = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("parse_store DB 持久化不可用，回退进程内存（多 worker 下跨进程取不到）: %s", exc)
            _db_usable = False
        _db_checked = True
    if not _db_usable:
        return None
    from infrastructure.database.connection import database as _d
    return _d


def _sweep(now: float) -> None:
    expired = [key for key, value in _STORE.items() if now - value["created_at"] > _TTL_SECONDS]
    for key in expired:
        _STORE.pop(key, None)


def _db_sweep(db) -> None:
    """惰性清理过期行（每次 put 顺带执行；created_ts 用 float 存避免方言日期函数差异）。"""
    try:
        with db.session() as s:
            s.execute("DELETE FROM parse_store WHERE created_ts < ?", (time.time() - _TTL_SECONDS,))
    except Exception:  # noqa: BLE001
        pass


def put(file_name: str, media_type: str, text: str) -> str:
    parse_id = f"prs_{uuid.uuid4().hex[:20]}"
    now = time.time()
    row = {
        "file_name": file_name,
        "media_type": media_type or "application/octet-stream",
        "text": text,
        "created_at": now,
    }
    with _LOCK:
        _sweep(now)
        while len(_STORE) >= _CAP:
            _STORE.pop(next(iter(_STORE)))
        _STORE[parse_id] = row
    db = _db()
    if db is not None:
        try:
            from datetime import datetime as _dt
            with db.session() as s:
                s.execute(
                    """INSERT INTO parse_store (parse_id, file_name, media_type, text, created_at, created_ts)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (parse_id, str(file_name or "")[:500], row["media_type"], text,
                     _dt.now().isoformat(timespec="seconds"), now),
                )
            _db_sweep(db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("parse_store DB 写入失败（本 worker 内存仍可用）: %s", exc)
    return parse_id


def get(parse_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        _sweep(time.time())
        hit = _STORE.get(parse_id)
    if hit is not None:
        return dict(hit)
    db = _db()
    if db is None:
        return None
    try:
        with db.session() as s:
            rows = s.fetchall(
                "SELECT file_name, media_type, text, created_ts FROM parse_store WHERE parse_id = ?",
                (parse_id,),
            )
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    row = rows[0]
    created = float(row.get("created_ts") or 0)
    if time.time() - created > _TTL_SECONDS:
        return None
    item = {
        "file_name": row.get("file_name") or "",
        "media_type": row.get("media_type") or "application/octet-stream",
        "text": row.get("text") or "",
        "created_at": created,
    }
    with _LOCK:  # 回填内存快路径（容量守恒）
        _sweep(time.time())
        while len(_STORE) >= _CAP:
            _STORE.pop(next(iter(_STORE)))
        _STORE[parse_id] = item
    return dict(item)


def take_many(parse_ids: List[str]) -> List[Dict[str, Any]]:
    """按提交顺序取回；任一失效（过期/不存在）抛 ValueError 由路由返回 422。"""
    out: List[Dict[str, Any]] = []
    for parse_id in parse_ids:
        item = get(str(parse_id or ""))
        if not item:
            raise ValueError(f"预解析结果已过期或不存在：{parse_id}，请重新上传解析文件")
        out.append(item)
    return out
