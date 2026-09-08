"""Layout-aware abstract and citation extraction for academic PDFs."""

from .abstracts import AbstractExtractor
from .models import (
    AbstractConfig,
    AbstractSection,
    Citation,
    CitationSentence,
    ParseConfig,
    ParseResult,
    ReferenceEntry,
    ReferenceSection,
)
from .parser import CitationParser

__all__ = [
    "AbstractConfig",
    "AbstractExtractor",
    "AbstractSection",
    "Citation",
    "CitationParser",
    "CitationSentence",
    "ParseConfig",
    "ParseResult",
    "ReferenceEntry",
    "ReferenceSection",
]

__version__ = "0.2.0"
