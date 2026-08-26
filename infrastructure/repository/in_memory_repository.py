"""仓储实现：内存实现（脚手架占位）。

后续可替换为 ORM / 数据库实现，不影响领域层与应用层。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from domain.entity.base import SemanticResult
from domain.repository.base_repository import ISemanticResultRepository


class InMemorySemanticResultRepository(ISemanticResultRepository):
    def __init__(self) -> None:
        self._store: Dict[str, SemanticResult] = {}

    def save(self, result: SemanticResult) -> None:
        if result.id is None:
            import uuid
            result.id = str(uuid.uuid4())
        self._store[result.id] = result

    def get(self, result_id: str) -> Optional[SemanticResult]:
        return self._store.get(result_id)

    def list_by_code(self, code: str) -> List[SemanticResult]:
        return [r for r in self._store.values() if r.code == code]
