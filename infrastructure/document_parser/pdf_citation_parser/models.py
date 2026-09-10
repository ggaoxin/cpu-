from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


BBox = tuple[float, float, float, float]
ValidationStatus = Literal["valid", "invalid", "unknown", "not_applicable"]


@dataclass(slots=True)
class ParseConfig:
    """Runtime policy. Defaults favor recall while exposing validation metadata."""

    strict_reference_validation: bool = False
    include_parenthetical_numeric: bool = True
    include_superscript: bool = True
    reference_heading_threshold: float = 5.5
    max_numeric_reference: int = 9999
    sentence_context_chars: int = 0


@dataclass(slots=True)
class AbstractConfig:
    """Conservative abstract-location policy for text-layer PDFs."""

    search_pages: int = 8
    min_chars: int = 60
    max_chars: int = 6500
    min_confidence: float = 0.55
    enable_unheaded: bool = True
    preferred_language: Literal["auto", "zh", "en"] = "auto"


@dataclass(slots=True)
class TextBlock:
    page: int
    block_no: int
    bbox: BBox
    text: str
    median_font_size: float
    bold_ratio: float = 0.0
    is_wide: bool = False
    column: int = 0
    text_start: int = 0
    text_end: int = 0


@dataclass(slots=True)
class PageLayout:
    page: int
    width: float
    height: float
    blocks: list[TextBlock] = field(default_factory=list)
    column_count: int = 1
    gutter_x: float | None = None
    text: str = ""


@dataclass(slots=True)
class LayoutDocument:
    text: str
    pages: list[PageLayout]
    text_char_count: int


@dataclass(slots=True)
class ReferenceSection:
    start: int
    page: int
    heading: str
    score: float
    number_set: set[int] = field(default_factory=set)
    evidence: dict[str, float | str | int | bool] = field(default_factory=dict)

    @property
    def number_range(self) -> tuple[int, int] | None:
        return (min(self.number_set), max(self.number_set)) if self.number_set else None


@dataclass(slots=True)
class ReferenceEntry:
    text: str
    start: int
    end: int
    number: int | None = None
    years: list[str] = field(default_factory=list)
    doi: str | None = None


@dataclass(slots=True)
class AbstractSection:
    text: str
    raw_text: str
    heading: str | None
    start: int
    end: int
    page: int
    method: Literal["headed", "unheaded"]
    confidence: float
    language: Literal["en", "zh", "mixed", "unknown"]
    structured_labels: list[str] = field(default_factory=list)
    evidence: dict[str, float | str | int | bool] = field(default_factory=dict)


@dataclass(slots=True)
class Citation:
    raw: str
    normalized: str
    kind: Literal["numeric", "author_year", "superscript"]
    pattern: str
    start: int
    end: int
    ids: list[int] = field(default_factory=list)
    years: list[str] = field(default_factory=list)
    validation: ValidationStatus = "unknown"
    confidence: float = 0.0


@dataclass(slots=True)
class CitationSentence:
    text: str
    start: int
    end: int
    citations: list[Citation]
    context: str | None = None


@dataclass(slots=True)
class ParseResult:
    source: str
    text: str
    body_text: str
    reference_text: str
    citations: list[Citation]
    citation_sentences: list[CitationSentence]
    reference_section: ReferenceSection | None
    reference_entries: list[ReferenceEntry]
    pages: int
    warnings: list[str] = field(default_factory=list)
    repair_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.reference_section:
            value["reference_section"]["number_set"] = sorted(self.reference_section.number_set)
            value["reference_section"]["number_range"] = self.reference_section.number_range
        return value

    def write_json(self, path: str | Path, *, indent: int = 2) -> None:
        import json

        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=indent),
            encoding="utf-8",
        )
