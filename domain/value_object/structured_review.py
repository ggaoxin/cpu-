"""结构化自动综述领域值对象。

这些对象只表达业务事实，不依赖 FastAPI、数据库或具体模型实现。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ReviewDocument:
    """参与综述的一篇科技文献或科技报告。"""

    document_id: str
    text: str
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.document_id.strip():
            raise ValueError("文献编号 document_id 不能为空")
        if not self.text.strip():
            raise ValueError(f"{self.document_id} 的 text 不能为空")


@dataclass(frozen=True)
class ReviewEvidence:
    """能够在原文中精确定位的证据片段。"""

    evidence_id: str
    document_id: str
    quote: str
    start: int
    end: int
    source_section: str = "text"


@dataclass
class ResearchQuestionCandidate:
    """从单篇文献中抽取出的研究问题及对应方法。"""

    candidate_id: str
    document_id: str
    question: str
    question_evidence: ReviewEvidence
    method: str = ""
    method_evidence: Optional[ReviewEvidence] = None
    extraction_mode: str = "llm"


@dataclass
class ResearchQuestionCluster:
    """语义相似研究问题形成的类簇。"""

    cluster_id: str
    label: str
    summary: str
    candidates: List[ResearchQuestionCandidate]
    cohesion: Optional[float] = None

