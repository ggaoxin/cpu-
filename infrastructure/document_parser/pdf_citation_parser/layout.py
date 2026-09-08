"""PyMuPDF dict extraction and geometry-based reading-order recovery."""

from __future__ import annotations

from dataclasses import replace
import re
import statistics
from pathlib import Path
from typing import Any, Iterable

from .models import LayoutDocument, PageLayout, ParseConfig, TextBlock


SUP_TOKEN = "\u27e6SUP:{text}\u27e7"
NUMERIC_SPAN = re.compile(r"\s*\d{1,5}(?:\s*[,;\-\u2010-\u2014]\s*\d{1,5})*\s*")


def _join_spans(spans: list[dict[str, Any]]) -> tuple[str, float, float]:
    if not spans:
        return "", 0.0, 0.0
    sizes = [float(s.get("size", 0.0)) for s in spans if s.get("text", "").strip()]
    median_size = statistics.median(sizes) if sizes else 0.0
    baseline_bottoms = [float(s.get("bbox", (0, 0, 0, 0))[3]) for s in spans]
    median_bottom = statistics.median(baseline_bottoms) if baseline_bottoms else 0.0
    pieces: list[str] = []
    previous: dict[str, Any] | None = None
    bold_chars = 0
    total_chars = 0

    # Source span order is not guaranteed in malformed or incrementally edited
    # PDFs. Geometry is the authoritative order for horizontal academic text.
    ordered_spans = sorted(
        enumerate(spans),
        key=lambda item: (
            round(float(item[1].get("bbox", (0, 0, 0, 0))[0]), 2),
            round(float(item[1].get("bbox", (0, 0, 0, 0))[1]), 2),
            item[0],
        ),
    )
    for _, span in ordered_spans:
        raw = str(span.get("text", ""))
        if not raw:
            continue
        flags = int(span.get("flags", 0))
        bbox = tuple(float(v) for v in span.get("bbox", (0, 0, 0, 0)))
        size = float(span.get("size", median_size or 1.0))
        font = str(span.get("font", "")).lower()
        is_superscript = bool(flags & 1)
        # Some PDFs do not set PyMuPDF's superscript flag. A small, raised,
        # numeric-only span is a useful secondary signal.
        is_raised_small = (
            median_size > 0
            and size <= median_size * 0.86
            and bbox[3] < median_bottom - median_size * 0.10
        )
        if NUMERIC_SPAN.fullmatch(raw) and (is_superscript or is_raised_small):
            raw = SUP_TOKEN.format(text=re.sub(r"\s+", "", raw))

        if previous is not None and pieces:
            prev_box = tuple(float(v) for v in previous.get("bbox", (0, 0, 0, 0)))
            gap = bbox[0] - prev_box[2]
            threshold = max(0.8, min(size, float(previous.get("size", size))) * 0.14)
            if gap > threshold and not pieces[-1].endswith((" ", "\n")) and not raw.startswith(" "):
                pieces.append(" ")
        pieces.append(raw)
        chars = len(raw.strip())
        total_chars += chars
        if (flags & 16) or "bold" in font or "black" in font or "demi" in font:
            bold_chars += chars
        previous = span

    return "".join(pieces).strip(), median_size, (bold_chars / total_chars if total_chars else 0.0)


def _block_from_dict(page_no: int, block_no: int, raw: dict[str, Any]) -> TextBlock | None:
    if raw.get("type", 0) != 0:
        return None
    line_texts: list[str] = []
    sizes: list[float] = []
    weighted_bold = 0.0
    weight = 0
    ordered_lines = sorted(
        enumerate(raw.get("lines", [])),
        key=lambda item: (
            round(float(item[1].get("bbox", (0, 0, 0, 0))[1]), 2),
            round(float(item[1].get("bbox", (0, 0, 0, 0))[0]), 2),
            item[0],
        ),
    )
    for _, line in ordered_lines:
        text, size, bold = _join_spans(line.get("spans", []))
        if text:
            line_texts.append(text)
            sizes.append(size)
            weighted_bold += bold * len(text)
            weight += len(text)
    text = "\n".join(line_texts).strip()
    if not text:
        return None
    bbox = tuple(float(v) for v in raw.get("bbox", (0, 0, 0, 0)))
    return TextBlock(
        page=page_no,
        block_no=block_no,
        bbox=bbox,  # type: ignore[arg-type]
        text=text,
        median_font_size=statistics.median(sizes) if sizes else 0.0,
        bold_ratio=weighted_bold / weight if weight else 0.0,
    )


def _detect_columns(blocks: list[TextBlock], page_width: float) -> tuple[int, float | None]:
    """Find a central gutter using text mass on both sides.

    Wide title/figure/table blocks are excluded from the gutter vote. This is
    more reliable than sorting on x/y alone and works with asymmetric margins.
    """

    # A valid two-column page can be represented by only two paragraph blocks
    # (one per column), plus an optional title. Do not require four blocks.
    if len(blocks) < 2 or page_width <= 0:
        return 1, None
    candidates = [page_width * (0.40 + i * 0.01) for i in range(21)]
    best: tuple[float, float] | None = None
    total_chars = sum(len(b.text) for b in blocks)
    for split in candidates:
        tolerance = page_width * 0.018
        left = right = crossing = 0
        for block in blocks:
            x0, _, x1, _ = block.bbox
            width = x1 - x0
            mass = max(1, len(block.text))
            if width >= page_width * 0.62:
                continue
            if x1 <= split + tolerance:
                left += mass
            elif x0 >= split - tolerance:
                right += mass
            else:
                crossing += mass
        balance = min(left, right)
        score = balance - 1.8 * crossing
        if best is None or score > best[0]:
            best = (score, split)
    if not best:
        return 1, None
    score, split = best
    minimum_side = max(80, total_chars * 0.10)
    left_mass = sum(len(b.text) for b in blocks if b.bbox[2] <= split + page_width * 0.018)
    right_mass = sum(len(b.text) for b in blocks if b.bbox[0] >= split - page_width * 0.018)
    if score <= 0 or min(left_mass, right_mass) < minimum_side:
        return 1, None
    return 2, split


def _sort_single_column(blocks: Iterable[TextBlock]) -> list[TextBlock]:
    return sorted(blocks, key=lambda b: (round(b.bbox[1], 1), b.bbox[0], b.block_no))


def _sort_two_columns(blocks: list[TextBlock], split: float, page_width: float) -> list[TextBlock]:
    tolerance = page_width * 0.018
    prepared: list[TextBlock] = []
    anchors: list[TextBlock] = []
    for block in blocks:
        x0, _, x1, _ = block.bbox
        crosses = x0 < split - tolerance and x1 > split + tolerance
        wide = crosses and (x1 - x0) >= page_width * 0.48
        if wide:
            item = replace(block, is_wide=True, column=-1)
            anchors.append(item)
        elif x1 <= split + tolerance:
            prepared.append(replace(block, column=0))
        elif x0 >= split - tolerance:
            prepared.append(replace(block, column=1))
        else:
            # A narrow gutter-overlapping block goes to the nearest column.
            center = (x0 + x1) / 2
            prepared.append(replace(block, column=0 if center < split else 1))

    # Full-width blocks split the page into horizontal reading bands. Within a
    # band, read the complete left column and then the complete right column.
    ordered: list[TextBlock] = []
    remaining = list(prepared)
    for anchor in sorted(anchors, key=lambda b: (b.bbox[1], b.bbox[0])):
        before = [b for b in remaining if (b.bbox[1] + b.bbox[3]) / 2 < anchor.bbox[1]]
        if before:
            ordered.extend(sorted(before, key=lambda b: (b.column, b.bbox[1], b.bbox[0])))
            before_ids = {(b.page, b.block_no) for b in before}
            remaining = [b for b in remaining if (b.page, b.block_no) not in before_ids]
        ordered.append(anchor)
    ordered.extend(sorted(remaining, key=lambda b: (b.column, b.bbox[1], b.bbox[0])))
    return ordered


def reconstruct_pages(page_dicts: list[dict[str, Any]], config: ParseConfig | None = None) -> LayoutDocument:
    """Reconstruct a document from PyMuPDF-like page dictionaries.

    This public helper also makes layout behavior testable without fixture PDFs.
    Each input dictionary needs ``width``, ``height`` and a PyMuPDF ``blocks`` list.
    """

    config = config or ParseConfig()
    pages: list[PageLayout] = []
    document_parts: list[str] = []
    document_offset = 0
    text_chars = 0

    for page_no, page_dict in enumerate(page_dicts):
        width = float(page_dict.get("width", 0.0))
        height = float(page_dict.get("height", 0.0))
        blocks = [
            block
            for i, raw in enumerate(page_dict.get("blocks", []))
            if (block := _block_from_dict(page_no, i, raw)) is not None
        ]
        column_count, gutter = _detect_columns(blocks, width)
        if column_count == 2 and gutter is not None:
            ordered = _sort_two_columns(blocks, gutter, width)
        else:
            ordered = _sort_single_column(blocks)

        page_parts: list[str] = []
        local_offset = 0
        laid_out: list[TextBlock] = []
        for block in ordered:
            if page_parts:
                page_parts.append("\n\n")
                local_offset += 2
            start = document_offset + local_offset
            page_parts.append(block.text)
            local_offset += len(block.text)
            laid_out.append(replace(block, text_start=start, text_end=document_offset + local_offset))
        page_text = "".join(page_parts)
        pages.append(
            PageLayout(
                page=page_no,
                width=width,
                height=height,
                blocks=laid_out,
                column_count=column_count,
                gutter_x=gutter,
                text=page_text,
            )
        )
        document_parts.append(page_text)
        text_chars += len(re.sub(r"\s+", "", page_text))
        document_offset += len(page_text)
        if page_no < len(page_dicts) - 1:
            document_offset += 2

    text = "\n\n".join(document_parts)
    return LayoutDocument(text, pages, text_chars)


def extract_layout(
    pdf: str | Path,
    config: ParseConfig | None = None,
    *,
    max_pages: int | None = None,
) -> LayoutDocument:
    import fitz

    page_dicts: list[dict[str, Any]] = []
    with fitz.open(str(pdf)) as document:
        for page_no, page in enumerate(document):
            if max_pages is not None and page_no >= max(0, max_pages):
                break
            data = page.get_text("dict", sort=False)
            data["width"] = float(page.rect.width)
            data["height"] = float(page.rect.height)
            page_dicts.append(data)
    return reconstruct_pages(page_dicts, config)
