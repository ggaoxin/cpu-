"""领域事件基类。

预留：用于跨功能点解耦（如“聚类完成”触发“标签生成”、“综述生成”
等）。脚手架阶段仅提供基类与简单事件总线接口。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class DomainEvent:
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """极简内存事件总线。"""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[DomainEvent], None]]] = {}

    def subscribe(self, event_name: str, handler: Callable[[DomainEvent], None]) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(event.name, []):
            handler(event)


event_bus = EventBus()
