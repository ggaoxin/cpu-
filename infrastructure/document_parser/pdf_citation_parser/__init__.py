"""Layout-aware citation sentence extraction for academic PDFs."""

from .models import Citation, CitationSentence, ParseConfig, ParseResult, ReferenceEntry, ReferenceSection
from .parser import CitationParser

__all__ = [
    "Citation",
    "CitationParser",
    "CitationSentence",
    "ParseConfig",
    "ParseResult",
    "ReferenceEntry",
    "ReferenceSection",
]

__version__ = "0.1.0"
