"""值对象：文本输入。

语义计算工具库的输入无外乎“单篇文本片段”或“多篇文本集合”，
将其抽象为不可变值对象，便于在各层间传递与校验。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TextInput:
    """单篇文本输入。"""
    text: str
    meta: Optional[Dict[str, str]] = None  # 作者/时间/期刊等元数据

    def validate(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("文本内容不能为空")


@dataclass(frozen=True)
class MultiTextInput:
    """多篇文本输入（用于深度聚类、综述等）。"""
    texts: List[str]
    metas: Optional[List[Dict[str, str]]] = None

    def validate(self) -> None:
        if not self.texts:
            raise ValueError("文本集合不能为空")
        if any(not t.strip() for t in self.texts):
            raise ValueError("文本集合中存在空文本")
