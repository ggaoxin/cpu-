"""领域服务接口。

每个功能点的核心“大模型 + 规则库”计算逻辑由应用层编排，领域层在此
定义契约。详细开发时可为各功能项扩展专属领域服务（如聚类、综述等
含跨文献聚合逻辑的服务）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain.entity.base import SemanticResult


class ISemanticService(ABC):
    """语义计算领域服务契约。"""

    @abstractmethod
    def execute(self, code: str, payload: Any) -> SemanticResult:
        """依据功能点 code 与输入负载执行语义计算，返回结果实体。"""
