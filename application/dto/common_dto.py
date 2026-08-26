"""应用层 DTO：统一的请求 / 响应模型。

所有 19 个功能点共用同一套 DTO 契约，差异由功能点 code 与规则库决定。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SemanticRequest(BaseModel):
    """语义计算请求。

    - text:  单篇文本（input_type=text 的功能点使用）
    - texts: 多篇文本集合（input_type=multi_text 的功能点使用）
    - meta:  可选元数据
    - params:可选运行参数（如聚类簇数、标签长度等）
    """
    text: Optional[str] = Field(None, description="单篇文献文本片段")
    texts: Optional[List[str]] = Field(None, description="多篇文献文本集合")
    meta: Optional[Dict[str, str]] = Field(None, description="文献元数据")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="运行参数")


class SemanticResponse(BaseModel):
    """语义计算响应。"""
    code: str
    name: str
    success: bool
    data: Any = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float] = None
    error: Optional[str] = None
