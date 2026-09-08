"""High-level citation parser."""

from __future__ import annotations

from pathlib import Path
import re

from .layout import extract_layout
from .models import (
    Citation,
    CitationSentence,
    LayoutDocument,
    PageLayout,
    ParseConfig,
    ParseResult,
    TextBlock,
)
from .patterns import AUTHOR_YEAR_PATTERNS, NUMERIC_PATTERNS, SUPERSCRIPT_PATTERNS
from .references import detect_reference_section, extract_reference_entries, extract_reference_numbers
from .repair import repair_citation_text, recover_prose_lines
from .sentences import split_sentences


SUP_TO_ASCII = str.maketrans(
    "\u00b9\u00b2\u00b3\u2070\u2074\u2075\u2076\u2077\u2078\u2079\u207b\u208b",
    "1230456789--",
)
RANGE_RE = re.compile(r"(\d{1,5})\s*[-\u2010-\u2014\u2212]\s*(\d{1,5})")
SUP_SENTINEL_RE = re.compile(r"\u27e6SUP:([^\u27e7]+)\u27e7")
YEAR_RE = re.compile(r"(?:18|19|20|21)\d{2}[a-z]?", re.IGNORECASE)


def _numeric_ids(raw: str, max_reference: int) -> list[int]:
    content = SUP_SENTINEL_RE.sub(lambda m: m.group(1), raw).translate(SUP_TO_ASCII)
    content = content.strip("[]\u3010\u3011()\uff08\uff09 ")
    # Adjacent-bracket ranges such as [3]-[5] become 3-5; comma-separated
    # IEEE groups such as [1], [2] become 1, 2.
    content = content.translate({ord(char): " " for char in "[]\u3010\u3011()\uff08\uff09"})
    # IEEE locator syntax such as [3, Fig. 1] contains a non-reference number.
    locator = re.search(
        r",\s*(?:p{1,2}\.|fig\.|eq\.|sec\.|ch\.|lemma|theorem|algorithm|appendix|th\.)",
        content,
        re.IGNORECASE,
    )
    if locator:
        content = content[: locator.start()]
    ids: list[int] = []
    # Parse comma/semicolon-separated items in textual order.
    for item in re.split(r"[,;]", content):
        range_match = RANGE_RE.search(item)
        if range_match:
            first, last = int(range_match.group(1)), int(range_match.group(2))
            if 0 < first <= last <= max_reference and last - first <= 1000:
                ids.extend(range(first, last + 1))
            else:
                ids.extend([first, last])
        else:
            ids.extend(int(value) for value in re.findall(r"\d{1,5}", item))
    return list(dict.fromkeys(ids))


def _normalized_citation(raw: str) -> str:
    return SUP_SENTINEL_RE.sub(lambda match: match.group(1), raw).strip()


def _validation(ids: list[int], reference_numbers: set[int]) -> str:
    if not ids or not reference_numbers:
        return "unknown"
    return "valid" if all(value in reference_numbers for value in ids) else "invalid"


def _overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and span[1] > start for start, end in occupied)


def _extract_candidates(
    text: str,
    config: ParseConfig,
    reference_numbers: set[int],
) -> list[Citation]:
    citations: list[Citation] = []
    occupied: list[tuple[int, int]] = []
    groups = [NUMERIC_PATTERNS, AUTHOR_YEAR_PATTERNS]
    if config.include_superscript:
        groups.append(SUPERSCRIPT_PATTERNS)

    matches: list[tuple[int, int, object, re.Match[str]]] = []
    for group in groups:
        for named in group:
            if named.name == "parenthetical_numeric" and not config.include_parenthetical_numeric:
                continue
            for match in named.regex.finditer(text):
                # Longest match wins when author-year patterns overlap.
                matches.append((match.start(), -(match.end() - match.start()), named, match))

    for _, _, named_obj, match in sorted(matches, key=lambda item: (item[0], item[1])):
        named = named_obj  # NamedPattern without a runtime dependency/cast.
        span = match.span()
        if _overlaps(span, occupied):
            continue
        kind = named.kind
        ids = _numeric_ids(match.group(0), config.max_numeric_reference) if kind in {"numeric", "superscript"} else []
        years = YEAR_RE.findall(match.group(0)) if kind == "author_year" else []
        validation = _validation(ids, reference_numbers) if ids else "not_applicable"
        confidence = named.confidence

        # Plain (1) is equation-like and only becomes a citation when the
        # reference list independently confirms it.
        if named.name == "parenthetical_numeric":
            if not reference_numbers or validation != "valid":
                continue
        if validation == "invalid":
            confidence = max(0.15, confidence - 0.40)
            if config.strict_reference_validation:
                continue
        elif validation == "valid":
            confidence = min(0.99, confidence + 0.03)

        citations.append(
            Citation(
                raw=match.group(0),
                normalized=_normalized_citation(match.group(0)),
                kind=kind,
                pattern=named.name,
                start=match.start(),
                end=match.end(),
                ids=ids,
                years=years,
                validation=validation,  # type: ignore[arg-type]
                confidence=round(confidence, 3),
            )
        )
        occupied.append(span)
    return sorted(citations, key=lambda item: (item.start, item.end))


def _display_sentence(text: str) -> str:
    return SUP_SENTINEL_RE.sub(lambda match: f"^{{{match.group(1)}}}", text)


def _citation_sentences(
    body_text: str,
    citations: list[Citation],
    context_chars: int,
) -> list[CitationSentence]:
    result: list[CitationSentence] = []
    for sentence in split_sentences(body_text):
        contained = [c for c in citations if sentence.start <= c.start and c.end <= sentence.end]
        if not contained:
            continue
        context = None
        if context_chars:
            context = _display_sentence(
                body_text[max(0, sentence.start - context_chars) : min(len(body_text), sentence.end + context_chars)]
            )
        result.append(
            CitationSentence(
                text=_display_sentence(sentence.text),
                start=sentence.start,
                end=sentence.end,
                citations=contained,
                context=context,
            )
        )
    return result


def _text_layout(text: str) -> LayoutDocument:
    block = TextBlock(0, 0, (0.0, 0.0, 600.0, 800.0), text, 10.0, text_start=0, text_end=len(text))
    page = PageLayout(0, 600.0, 800.0, [block], 1, None, text)
    return LayoutDocument(text, [page], len(re.sub(r"\s+", "", text)))


class CitationParser:
    """Parse citations and their sentences from a PDF text layer."""

    def __init__(
        self,
        config: ParseConfig | None = None,
    ) -> None:
        self.config = config or ParseConfig()

    def parse(self, pdf: str | Path) -> ParseResult:
        layout = extract_layout(pdf, self.config)
        return self._parse_layout(layout, source=str(pdf))

    def parse_text(self, text: str, *, source: str = "<text>") -> ParseResult:
        """Parse already extracted text; useful for testing and custom pipelines."""

        return self._parse_layout(_text_layout(text), source=source)

    def _parse_layout(
        self,
        layout: LayoutDocument,
        *,
        source: str,
    ) -> ParseResult:
        reference = detect_reference_section(layout, self.config)
        raw_body = layout.text[: reference.start] if reference else layout.text
        raw_references = layout.text[reference.start :] if reference else ""

        repaired_body, body_counts = repair_citation_text(raw_body)
        repaired_refs, ref_counts = repair_citation_text(raw_references)
        body_text = recover_prose_lines(repaired_body)
        reference_text = recover_prose_lines(repaired_refs)
        reference_numbers = extract_reference_numbers(repaired_refs)
        reference_entries = extract_reference_entries(reference_text)
        if reference:
            reference.number_set = reference_numbers

        citations = _extract_candidates(body_text, self.config, reference_numbers)
        sentences = _citation_sentences(body_text, citations, self.config.sentence_context_chars)
        repair_counts = dict(body_counts)
        for key, value in ref_counts.items():
            repair_counts[key] = repair_counts.get(key, 0) + value
        return ParseResult(
            source=source,
            text=body_text + (("\n\n" + reference_text) if reference_text else ""),
            body_text=body_text,
            reference_text=reference_text,
            citations=citations,
            citation_sentences=sentences,
            reference_section=reference,
            reference_entries=reference_entries,
            pages=len(layout.pages),
            repair_counts=repair_counts,
        )
