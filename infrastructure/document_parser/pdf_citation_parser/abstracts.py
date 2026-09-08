"""Layout-aware abstract location for PyMuPDF text-layer output."""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import re
import statistics
from pathlib import Path

from .abstract_patterns import (
    ABSTRACT_END_PATTERNS,
    ABSTRACT_HEADING_PATTERNS,
    BROKEN_ABSTRACT_HEADING_PATTERNS,
    FRONT_MATTER_NOISE_PATTERNS,
    STRUCTURED_ABSTRACT_LABEL_PATTERNS,
    UNHEADED_ABSTRACT_SIGNAL_PATTERNS,
)
from .abstract_repair import repair_abstract_text
from .layout import extract_layout
from .models import AbstractConfig, AbstractSection, LayoutDocument, PageLayout, TextBlock
from .sentences import split_sentences


@dataclass(slots=True)
class _Candidate:
    text: str
    raw_text: str
    heading: str | None
    start: int
    end: int
    page: int
    method: str
    score: float
    labels: list[str]
    evidence: dict[str, float | str | int | bool]


def _width_normalized(text: str) -> str:
    """Normalize fullwidth ASCII while preserving one-character offsets."""

    chars: list[str] = []
    for char in text:
        code = ord(char)
        if 0xFF01 <= code <= 0xFF5E:
            chars.append(chr(code - 0xFEE0))
        elif char == "\u3000":
            chars.append(" ")
        else:
            chars.append(char)
    return "".join(chars)


def _page_for_offset(layout: LayoutDocument, offset: int) -> int:
    for page in layout.pages:
        if any(block.text_start <= offset <= block.text_end for block in page.blocks):
            return page.page
    preceding = [
        block.page
        for page in layout.pages
        for block in page.blocks
        if block.text_start <= offset
    ]
    return max(preceding, default=0)


def _search_end(layout: LayoutDocument, search_pages: int) -> int:
    allowed = [page for page in layout.pages if page.page < search_pages]
    if not allowed:
        return len(layout.text)
    endings = [block.text_end for page in allowed for block in page.blocks]
    return max(endings, default=min(len(layout.text), 1))


def _find_end_boundary(text: str, start: int, limit: int, min_gap: int) -> tuple[int, str | None]:
    window = _width_normalized(text[start:limit])
    found: list[tuple[int, str]] = []
    for pattern in ABSTRACT_END_PATTERNS:
        for match in pattern.regex.finditer(window):
            absolute = start + match.start()
            if absolute - start >= min_gap:
                found.append((absolute, pattern.name))
    if not found:
        return limit, None
    return min(found, key=lambda item: item[0])


def _language(text: str) -> str:
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if cjk and latin and min(cjk, latin) >= max(cjk, latin) * 0.12:
        return "mixed"
    if cjk > latin * 0.25:
        return "zh"
    if latin:
        return "en"
    return "unknown"


def _structured_labels(text: str) -> list[str]:
    labels: list[str] = []
    for pattern in STRUCTURED_ABSTRACT_LABEL_PATTERNS:
        for match in pattern.regex.finditer(text):
            label = match.groupdict().get("label")
            if label:
                normalized = " ".join(label.split()).strip().rstrip(":：-—").title()
                if normalized not in labels:
                    labels.append(normalized)
    return labels


def _prose_metrics(text: str) -> tuple[int, float]:
    sentences = len(split_sentences(text))
    useful = len(re.findall(r"[A-Za-z\u3400-\u9fff]", text))
    ratio = useful / max(1, len(text))
    return sentences, ratio


def _trim_raw_span(text: str, start: int, end: int) -> tuple[int, int, str]:
    raw = text[start:end]
    left = len(raw) - len(raw.lstrip())
    right = len(raw.rstrip())
    return start + left, start + right, raw[left:right]


def _headed_candidates(
    layout: LayoutDocument,
    config: AbstractConfig,
    limit: int,
) -> list[_Candidate]:
    text = layout.text
    match_text = _width_normalized(text)
    candidates: list[_Candidate] = []
    patterns = ABSTRACT_HEADING_PATTERNS + BROKEN_ABSTRACT_HEADING_PATTERNS
    raw_hits = [
        (match.start(), match.end(), pattern, match)
        for pattern in patterns
        for match in pattern.regex.finditer(match_text[:limit])
    ]
    # The damage-tolerant spaced rule also matches a clean "ABSTRACT". Keep
    # the strongest rule for an identical span, and use later headings as a
    # boundary. This prevents titles such as "Abstract Interpretation ..."
    # from swallowing the actual abstract below.
    best_by_span: dict[tuple[int, int], tuple] = {}
    for hit in raw_hits:
        key = (hit[0], hit[1])
        if key not in best_by_span or hit[2].confidence > best_by_span[key][2].confidence:
            best_by_span[key] = hit
    hits = sorted(best_by_span.values(), key=lambda hit: (hit[0], hit[1]))
    for hit_index, (_, _, pattern, match) in enumerate(hits):
            before = text[max(0, match.start() - 30) : match.start()]
            if re.search(r"(?:graphical|visual)\s*$", before, re.IGNORECASE):
                continue
            start = match.end()
            next_heading = next(
                (other[0] for other in hits[hit_index + 1 :] if other[0] > match.start()),
                limit,
            )
            boundary, boundary_name = _find_end_boundary(
                text,
                start,
                min(limit, next_heading, start + config.max_chars),
                max(25, config.min_chars // 2),
            )
            start, end, raw = _trim_raw_span(text, start, boundary)
            clean = repair_abstract_text(raw)
            if len(clean) < config.min_chars:
                continue
            if len(clean) > config.max_chars:
                clean = clean[: config.max_chars].rstrip()
                end = min(end, start + config.max_chars)
            sentences, prose_ratio = _prose_metrics(clean)
            labels = _structured_labels(raw + "\n" + clean)
            page = _page_for_offset(layout, match.start())
            heading = " ".join(match.group("heading").split())
            score = pattern.confidence * 0.56
            score += 0.12 if page == 0 else 0.08 if page == 1 else 0.04 if page < 4 else 0.0
            score += 0.12 if 100 <= len(clean) <= 4500 else 0.05
            score += 0.08 if boundary_name else 0.0
            score += 0.05 if sentences >= 2 else 0.0
            score += 0.04 if prose_ratio >= 0.55 else 0.0
            score += 0.04 if labels else 0.0
            score = min(0.995, score)
            candidates.append(
                _Candidate(
                    text=clean,
                    raw_text=raw,
                    heading=heading,
                    start=start,
                    end=end,
                    page=page,
                    method="headed",
                    score=score,
                    labels=labels,
                    evidence={
                        "heading_pattern": pattern.name,
                        "end_pattern": boundary_name or "search_limit",
                        "content_chars": len(clean),
                        "sentence_count": sentences,
                        "prose_ratio": round(prose_ratio, 3),
                    },
                )
            )
    return candidates


def _matches_any(text: str, patterns: tuple) -> bool:
    normalized = _width_normalized(text)
    return any(pattern.regex.search(normalized) for pattern in patterns)


def _body_font(layout: LayoutDocument) -> float:
    sizes = [
        block.median_font_size
        for page in layout.pages
        for block in page.blocks
        if len(block.text) >= 100 and block.median_font_size > 0
    ]
    return statistics.median(sizes) if sizes else 0.0


def _title_block(layout: LayoutDocument, limit_page: int = 2) -> TextBlock | None:
    possible = [
        block
        for page in layout.pages[:limit_page]
        for block in page.blocks
        if 8 <= len(re.sub(r"\s+", " ", block.text).strip()) <= 350
        and block.median_font_size > 0
        and block.bbox[1] <= page.height * 0.72
        and not _matches_any(block.text, FRONT_MATTER_NOISE_PATTERNS)
        and not _matches_any(block.text, ABSTRACT_HEADING_PATTERNS)
    ]
    if not possible:
        return None
    return max(possible, key=lambda block: (block.median_font_size, len(block.text), -block.page))


def _score_unheaded(
    clean: str,
    raw: str,
    blocks: list[TextBlock],
    stop: int | None,
    body_font: float,
    title: TextBlock | None,
) -> tuple[float, dict[str, float | str | int | bool], list[str]]:
    sentences, prose_ratio = _prose_metrics(clean)
    labels = _structured_labels(raw + "\n" + clean)
    signals = sum(
        1 for pattern in UNHEADED_ABSTRACT_SIGNAL_PATTERNS if pattern.regex.search(clean)
    )
    noise = sum(1 for pattern in FRONT_MATTER_NOISE_PATTERNS if pattern.regex.search(clean))
    last = blocks[-1]
    distance_to_stop = stop - last.text_end if stop is not None else -1
    page = blocks[0].page
    median_font = statistics.median(
        [block.median_font_size for block in blocks if block.median_font_size > 0]
    ) if any(block.median_font_size > 0 for block in blocks) else 0.0

    score = 0.20
    score += 0.12 if len(clean) >= 120 else 0.0
    score += 0.06 if 250 <= len(clean) <= 4500 else 0.0
    score += 0.09 if sentences >= 2 else 0.03 if sentences == 1 and len(clean) >= 180 else 0.0
    score += 0.05 if prose_ratio >= 0.55 else 0.0
    score += min(0.18, signals * 0.10)
    score += 0.15 if labels else 0.0
    score += 0.17 if 0 <= distance_to_stop <= 350 else 0.07 if 0 <= distance_to_stop <= 900 else 0.0
    score += 0.06 if page == 0 else 0.03 if page == 1 else 0.0
    score += 0.03 if title and blocks[0].text_start > title.text_end else 0.0
    if body_font and median_font:
        ratio = median_font / body_font
        score += 0.03 if 0.78 <= ratio <= 1.18 else 0.0
    score -= min(0.40, noise * 0.22)
    if stop is None and signals == 0 and not labels:
        # Without a heading, boundary or abstract-like discourse signal, the
        # first body paragraph is indistinguishable from an introduction.
        score -= 0.18
    evidence: dict[str, float | str | int | bool] = {
        "content_chars": len(clean),
        "sentence_count": sentences,
        "prose_ratio": round(prose_ratio, 3),
        "language_signal_count": signals,
        "noise_signal_count": noise,
        "distance_to_end_marker": distance_to_stop,
        "title_detected": bool(title),
    }
    return max(0.0, min(0.92, score)), evidence, labels


def _unheaded_candidates(
    layout: LayoutDocument,
    config: AbstractConfig,
    limit: int,
) -> list[_Candidate]:
    if not config.enable_unheaded:
        return []
    text = layout.text
    match_text = _width_normalized(text)
    title = _title_block(layout)
    floor = title.text_end if title else 0
    end_matches: list[tuple[int, str]] = []
    for pattern in ABSTRACT_END_PATTERNS:
        for match in pattern.regex.finditer(match_text[floor:limit]):
            end_matches.append((floor + match.start(), pattern.name))
    stop, stop_name = min(end_matches, default=(None, None), key=lambda item: item[0])

    blocks = [
        block
        for page in layout.pages
        if page.page < config.search_pages
        for block in page.blocks
        if block.text_start >= floor and block.text_end <= limit
        and (stop is None or block.text_start < stop)
    ]
    candidates: list[_Candidate] = []
    body_font = _body_font(layout)
    for i, first in enumerate(blocks):
        if _matches_any(first.text, FRONT_MATTER_NOISE_PATTERNS):
            continue
        if _matches_any(first.text, ABSTRACT_HEADING_PATTERNS + BROKEN_ABSTRACT_HEADING_PATTERNS):
            continue
        for j in range(i, min(len(blocks), i + 4)):
            window = blocks[i : j + 1]
            if any(_matches_any(block.text, FRONT_MATTER_NOISE_PATTERNS) for block in window[1:]):
                break
            raw = text[first.text_start : window[-1].text_end]
            clean = repair_abstract_text(raw)
            if len(clean) < config.min_chars:
                continue
            if len(clean) > config.max_chars:
                break
            score, evidence, labels = _score_unheaded(clean, raw, window, stop, body_font, title)
            evidence["end_pattern"] = stop_name or "none"
            if title:
                evidence["title_font_size"] = round(title.median_font_size, 2)
            candidates.append(
                _Candidate(
                    text=clean,
                    raw_text=raw,
                    heading=None,
                    start=first.text_start,
                    end=window[-1].text_end,
                    page=first.page,
                    method="unheaded",
                    score=score,
                    labels=labels,
                    evidence=evidence,
                )
            )
    return candidates


def _text_layout(text: str) -> LayoutDocument:
    block = TextBlock(0, 0, (0.0, 0.0, 600.0, 800.0), text, 10.0, text_start=0, text_end=len(text))
    page = PageLayout(0, 600.0, 800.0, [block], 1, None, text)
    return LayoutDocument(text, [page], len(re.sub(r"\s+", "", text)))


class AbstractExtractor:
    def __init__(self, config: AbstractConfig | None = None) -> None:
        self.config = config or AbstractConfig()

    def extract(self, pdf: str | Path) -> AbstractSection | None:
        layout = extract_layout(pdf, max_pages=self.config.search_pages)
        return self.extract_layout(layout)

    def extract_many(
        self,
        pdfs: list[str | Path],
        *,
        workers: int = 1,
    ) -> list[tuple[str, AbstractSection | None]]:
        """Extract a batch while preserving input order.

        Each worker opens its own PDF, so no PyMuPDF document object is shared
        across threads. For small local files, 2-4 workers is usually enough.
        """

        paths = [str(path) for path in pdfs]
        if workers <= 1:
            return [(path, self.extract(path)) for path in paths]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(self.extract, paths))
        return list(zip(paths, results))

    def extract_text(self, text: str) -> AbstractSection | None:
        """Extract a headed abstract from already ordered text.

        Layout-free text cannot reliably support the unheaded font/position
        heuristic, but all heading and boundary rules remain available.
        """

        return self.extract_layout(_text_layout(text), allow_unheaded=False)

    def extract_layout(
        self,
        layout: LayoutDocument,
        *,
        allow_unheaded: bool | None = None,
    ) -> AbstractSection | None:
        limit = _search_end(layout, self.config.search_pages)
        candidates = _headed_candidates(layout, self.config, limit)
        if allow_unheaded is None:
            allow_unheaded = self.config.enable_unheaded
        if allow_unheaded:
            candidates.extend(_unheaded_candidates(layout, self.config, limit))
        if not candidates:
            return None
        winner = max(candidates, key=lambda candidate: (candidate.score, candidate.method == "headed", -candidate.start))
        if winner.score < self.config.min_confidence:
            return None
        return AbstractSection(
            text=winner.text,
            raw_text=winner.raw_text,
            heading=winner.heading,
            start=winner.start,
            end=winner.end,
            page=winner.page,
            method=winner.method,  # type: ignore[arg-type]
            confidence=round(winner.score, 3),
            language=_language(winner.text),  # type: ignore[arg-type]
            structured_labels=winner.labels,
            evidence=winner.evidence,
        )
