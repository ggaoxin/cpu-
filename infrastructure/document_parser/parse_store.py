"""预解析文本缓存：上传阶段把文件解析成文本，提交时只带 parse_id。

用途（2026-09-07 用户定调）：文件读取与解析前移到上传动作，点「在线测试」
只做功能计算——响应时间不再包含 PDF 解析（mineru 可达 45s+）。
上传时 POST /api/v1/files/parse 落文本进本缓存并返回 parse_id；提交时
file/batch 路由带 preparsed=[parse_id,...] 直接取文本，不再上传文件本体。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_TTL_SECONDS = 2 * 60 * 60          # 解析结果保留 2 小时（足够用户填元数据再提交）
_CAP = 200                          # 最多缓存 200 条（批量 20 文件 × 多任务余量）

_LOCK = threading.Lock()
_STORE: Dict[str, Dict[str, Any]] = {}


def _sweep(now: float) -> None:
    expired = [key for key, value in _STORE.items() if now - value["created_at"] > _TTL_SECONDS]
    for key in expired:
        _STORE.pop(key, None)


def put(file_name: str, media_type: str, text: str) -> str:
    parse_id = f"prs_{uuid.uuid4().hex[:20]}"
    now = time.time()
    with _LOCK:
        _sweep(now)
        while len(_STORE) >= _CAP:
            _STORE.pop(next(iter(_STORE)))
        _STORE[parse_id] = {
            "file_name": file_name,
            "media_type": media_type or "application/octet-stream",
            "text": text,
            "created_at": now,
        }
    return parse_id


def get(parse_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        _sweep(time.time())
        return _STORE.get(parse_id)


def take_many(parse_ids: List[str]) -> List[Dict[str, Any]]:
    """按提交顺序取回；任一失效（过期/不存在）抛 ValueError 由路由返回 422。"""
    out: List[Dict[str, Any]] = []
    for parse_id in parse_ids:
        item = get(str(parse_id or ""))
        if not item:
            raise ValueError(f"预解析结果已过期或不存在：{parse_id}，请重新上传解析文件")
        out.append(item)
    return out
