"""仓储接口（抽象）。

脚手架阶段以接口形式存在；后续若需持久化（结果归档、知识库、
聚类结果存储等），在 infrastructure/repository 中提供具体实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from domain.entity.base import SemanticResult


class ISemanticResultRepository(ABC):
    """语义计算结果仓储接口。"""

    @abstractmethod
    def save(self, result: SemanticResult) -> None: ...

    @abstractmethod
    def get(self, result_id: str) -> Optional[SemanticResult]: ...

    @abstractmethod
    def list_by_code(self, code: str) -> List[SemanticResult]: ...
