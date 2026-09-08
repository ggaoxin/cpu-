"""Reference-section localization using heading, position and local density."""

from __future__ import annotations

import re
import statistics

from .models import LayoutDocument, ParseConfig, ReferenceEntry, ReferenceSection, TextBlock
from .patterns import is_reference_heading


NUMERIC_ENTRY = re.compile(
    r"(?m)^\s*(?:[\[\u3010]\s*(?P<bracket>\d{1,5})\s*[\]\u3011]|"
    r"[\(\uff08]?\s*(?P<plain>\d{1,5})\s*(?:[.)\u3001\uff09]))\s+"
)
AUTHOR_YEAR_ENTRY = re.compile(
    r"(?m)^\s*(?:[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u024f'\u2019-]+|[\u3400-\u9fff]{1,4})"
    r"[^\n]{0,140}(?:18|19|20|21)\d{2}[a-z]?"
)
DOI_OR_VENUE = re.compile(r"(?i)\b(?:doi\s*:|https?://doi\.org/|vol\.|pp?\.|arxiv\s*:)")
DOI_VALUE = re.compile(r"(?i)(?:https?://doi\.org/|doi\s*:\s*)(10\.\d{4,9}/[-._;()/:A-Z0-9]+)")
YEAR_VALUE = re.compile(r"(?:18|19|20|21)\d{2}[a-z]?", re.IGNORECASE)
MERGED_HEADING = re.compile(
    r"^\s*(?P<heading>(?:references|bibliography|works\s+cited|literature\s+cited|"
    r"参\s*考\s*文\s*献|引\s*用\s*文\s*献|參\s*考\s*文\s*獻))\s*[:.]?"
    r"(?=\s*(?:[\[\u3010]\s*1\s*[\]\u3011]|[\(\uff08]?\s*1\s*[.)\u3001\uff09]))",
    re.IGNORECASE,
)


def _body_font_size(layout: LayoutDocument) -> float:
    sizes = [
        block.median_font_size
        for page in layout.pages
        for block in page.blocks
        if len(block.text) >= 40 and block.median_font_size > 0
    ]
    return statistics.median(sizes) if sizes else 0.0


def _density(text: str) -> tuple[float, int, int, int]:
    sample = text[:7000]
    numeric = len(list(NUMERIC_ENTRY.finditer(sample)))
    author_year = len(list(AUTHOR_YEAR_ENTRY.finditer(sample)))
    scholarly = len(list(DOI_OR_VENUE.finditer(sample)))
    units = max(1.0, len(sample) / 1000)
    return (numeric * 1.5 + author_year + scholarly * 0.35) / units, numeric, author_year, scholarly


def _candidate_score(
    block: TextBlock,
    layout: LayoutDocument,
    body_size: float,
) -> tuple[float, dict[str, float | str | int | bool]]:
    total = max(1, len(layout.text))
    position = block.text_start / total
    after = layout.text[block.text_end :]
    density, numeric, author_year, scholarly = _density(after)
    page = layout.pages[block.page]
    x0, _, x1, _ = block.bbox
    centered = abs(((x0 + x1) / 2) - page.width / 2) < page.width * 0.12
    font_ratio = block.median_font_size / body_size if body_size else 1.0

    score = 3.0
    score += max(-2.0, min(2.2, (position - 0.45) * 5.0))
    score += min(3.0, density * 0.55)
    score += 0.8 if font_ratio >= 1.08 else 0.0
    score += 0.7 if block.bold_ratio >= 0.45 else 0.0
    score += 0.35 if centered else 0.0
    score += 0.35 if len(block.text.strip()) <= 40 else -0.5
    if position < 0.25 and numeric + author_year < 3:
        # Penalize table-of-contents headings and prose mentions, but let a
        # dense run of real reference entries override position. This matters
        # for short papers and extended abstracts with little body.
        score -= 2.0
    evidence: dict[str, float | str | int | bool] = {
        "position_ratio": round(position, 4),
        "reference_density": round(density, 3),
        "numeric_entries_after": numeric,
        "author_year_entries_after": author_year,
        "scholarly_tokens_after": scholarly,
        "font_ratio": round(font_ratio, 3),
        "bold": block.bold_ratio >= 0.45,
        "centered": centered,
    }
    return score, evidence


def extract_reference_numbers(text: str) -> set[int]:
    numbers: set[int] = set()
    for match in NUMERIC_ENTRY.finditer(text):
        value = match.group("bracket") or match.group("plain")
        if value:
            numbers.add(int(value))
    return numbers


def extract_reference_entries(text: str) -> list[ReferenceEntry]:
    """Split a detected reference section into useful structured entries.

    Numeric markers are strongest. For unnumbered author-year bibliographies,
    paragraph boundaries are used conservatively.
    """

    markers = list(NUMERIC_ENTRY.finditer(text))
    entries: list[ReferenceEntry] = []
    if markers:
        for index, marker in enumerate(markers):
            start = marker.start()
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            value = marker.group("bracket") or marker.group("plain")
            entry_text = text[start:end].strip()
            doi_match = DOI_VALUE.search(entry_text)
            entries.append(
                ReferenceEntry(
                    text=entry_text,
                    start=start,
                    end=end,
                    number=int(value) if value else None,
                    years=YEAR_VALUE.findall(entry_text),
                    doi=doi_match.group(1).rstrip(".") if doi_match else None,
                )
            )
        return entries

    cursor = 0
    for chunk in re.split(r"(\n\s*\n+)", text):
        if not chunk or re.fullmatch(r"\n\s*\n+", chunk):
            cursor += len(chunk)
            continue
        stripped = chunk.strip()
        local_start = cursor + (len(chunk) - len(chunk.lstrip()))
        if stripped and not is_reference_heading(stripped) and AUTHOR_YEAR_ENTRY.search(stripped):
            doi_match = DOI_VALUE.search(stripped)
            entries.append(
                ReferenceEntry(
                    text=stripped,
                    start=local_start,
                    end=local_start + len(stripped),
                    years=YEAR_VALUE.findall(stripped),
                    doi=doi_match.group(1).rstrip(".") if doi_match else None,
                )
            )
        cursor += len(chunk)
    return entries


def detect_reference_section(
    layout: LayoutDocument,
    config: ParseConfig | None = None,
) -> ReferenceSection | None:
    config = config or ParseConfig()
    body_size = _body_font_size(layout)
    candidates: list[tuple[float, TextBlock, dict[str, float | str | int | bool]]] = []
    for page in layout.pages:
        for block in page.blocks:
            # A heading may share a PDF block with preceding/following text
            # (especially in parse_text input), so inspect every physical
            # line and retain its exact document offset.
            cursor = 0
            for raw_line in block.text.splitlines(keepends=True):
                line = raw_line.strip()
                merged = MERGED_HEADING.match(line) if line else None
                heading_text = merged.group("heading") if merged else line
                if not line or (not merged and not is_reference_heading(line)):
                    cursor += len(raw_line)
                    continue
                leading = len(raw_line) - len(raw_line.lstrip())
                heading_offset = cursor + leading
                heading_block = TextBlock(
                    page=block.page,
                    block_no=block.block_no,
                    bbox=block.bbox,
                    text=heading_text,
                    median_font_size=block.median_font_size,
                    bold_ratio=block.bold_ratio,
                    is_wide=block.is_wide,
                    column=block.column,
                    text_start=block.text_start + max(0, heading_offset),
                    text_end=block.text_start + max(0, heading_offset) + len(heading_text),
                )
                score, evidence = _candidate_score(heading_block, layout, body_size)
                candidates.append((score, heading_block, evidence))
                cursor += len(raw_line)

    if candidates:
        score, winner, evidence = max(candidates, key=lambda item: item[0])
        if score >= config.reference_heading_threshold:
            reference_text = layout.text[winner.text_start :]
            return ReferenceSection(
                start=winner.text_start,
                page=winner.page,
                heading=winner.text.strip(),
                score=round(score, 3),
                number_set=extract_reference_numbers(reference_text),
                evidence=evidence,
            )

    # Heading-less fallback: accept only a strong numeric run in the final 45%.
    floor = int(len(layout.text) * 0.55)
    tail = layout.text[floor:]
    entries = list(NUMERIC_ENTRY.finditer(tail))
    if len(entries) >= 5:
        first_five = [int(m.group("bracket") or m.group("plain")) for m in entries[:5]]
        if first_five[0] in (1, 2) and all(b > a for a, b in zip(first_five, first_five[1:])):
            start = floor + entries[0].start()
            numbers = extract_reference_numbers(layout.text[start:])
            page_no = max(
                (block.page for page in layout.pages for block in page.blocks if block.text_start <= start),
                default=max(0, len(layout.pages) - 1),
            )
            return ReferenceSection(
                start=start,
                page=page_no,
                heading="",
                score=config.reference_heading_threshold,
                number_set=numbers,
                evidence={"headingless_numeric_run": True, "numeric_entries_after": len(entries)},
            )
    return None
