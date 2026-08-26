"""领域实体基类。

详细功能开发阶段，每个功能项会派生出专属结果实体（如 MoveResult、
ClassificationResult、NerResult 等），承载该功能点的结构化输出。
脚手架阶段提供统一基类与通用结果实体。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Entity:
    """所有领域实体的基类，提供唯一标识。"""
    id: Optional[str] = None


@dataclass
class SemanticResult(Entity):
    """通用语义计算结果实体。

    各功能点输出的结构化数据统一以 ``data`` 承载；详细开发时可被
    更具体的子类替代，但保持 ``code`` / ``success`` / ``data`` 契约。
    """
    code: str = ""                          # 功能点 code
    name: str = ""                          # 功能点中文名
    success: bool = True
    data: Any = None                        # 结构化结果
    evidence: List[Dict[str, Any]] = field(default_factory=list)  # 证据句/来源（可解释性）
    confidence: Optional[float] = None      # 整体置信度
    raw: Optional[str] = None               # 大模型原始返回（调试用）
    error: Optional[str] = None             # 失败原因
