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
    ABSTRACT_NOISE_LINE_PATTERNS,
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


def _looks_like_numeric_table(block: TextBlock) -> bool:
    """Detect table bodies whose caption was emitted in another PDF block.

    The rule requires several row-like lines and repeated numeric cells. It is
    intentionally stricter than a digit-ratio test so quantitative abstract
    prose (percentages, p-values, model scores) remains valid content.
    """

    lines = [line.strip() for line in block.text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    numeric = re.compile(r"(?<!\w)[+\-−]?(?:\d+(?:[.,]\d+)?|\.\d+)(?:%|\u00b1\d+(?:\.\d+)?)?(?!\w)")
    row_counts = [len(numeric.findall(line)) for line in lines]
    data_rows = sum(count >= 2 for count in row_counts)
    total_numbers = sum(row_counts)
    if data_rows < 3 or total_numbers < 8:
        return False
    compact = re.sub(r"\s+", "", block.text)
    numeric_chars = len(re.findall(r"[\d.,%+\-−\u00b1]", compact))
    letters = len(re.findall(r"[A-Za-z\u3400-\u9fff]", compact))
    return numeric_chars / max(1, len(compact)) >= 0.24 and letters / max(1, len(compact)) <= 0.48


def _find_layout_end_boundary(
    layout: LayoutDocument,
    start: int,
    limit: int,
    min_gap: int,
) -> tuple[int, str | None]:
    for page in layout.pages:
        for block in page.blocks:
            if not (start + min_gap <= block.text_start < limit):
                continue
            if _looks_like_numeric_table(block):
                return block.text_start, "numeric_table_block"
    return limit, None


def _removed_noise_names(text: str) -> list[str]:
    normalized = _width_normalized(text)
    return [
        pattern.name
        for pattern in ABSTRACT_NOISE_LINE_PATTERNS
        if pattern.regex.search(normalized)
    ]


def _layout_noise_reasons(block: TextBlock) -> list[str]:
    """Classify an entire PyMuPDF block as removable front-matter noise."""

    names = _removed_noise_names(block.text)
    normalized = _width_normalized(block.text)
    acm_markers = (
        r"permission\s+to\s+make\s+digital\s+or\s+hard\s+copies",
        r"request\s+permissions\s+from\s+permissions@acm\.org",
        r"copyright\s+held\s+by\s+the\s+(?:owner|author)",
        r"publication\s+rights\s+licensed\s+to\s+acm",
        r"\bacm\s+isbn\b",
    )
    if sum(bool(re.search(marker, normalized, re.IGNORECASE)) for marker in acm_markers) >= 2:
        names.append("acm_permission_block")
    elif re.search(acm_markers[0], normalized, re.IGNORECASE):
        names.append("acm_permission_block")
    return list(dict.fromkeys(names))


def _is_removable_noise_block(block: TextBlock) -> bool:
    names = _layout_noise_reasons(block)
    if not names:
        return False
    if "acm_permission_block" in names:
        return True
    cleaned = repair_abstract_text(block.text)
    useful_before = len(re.findall(r"[A-Za-z\u3400-\u9fff]", block.text))
    useful_after = len(re.findall(r"[A-Za-z\u3400-\u9fff]", cleaned))
    return useful_after <= max(5, useful_before * 0.20)


def _without_layout_noise(
    layout: LayoutDocument,
    start: int,
    end: int,
) -> tuple[str, list[str]]:
    """Remove complete noise blocks while retaining source-order prose."""

    source = layout.text
    cursor = start
    parts: list[str] = []
    removed: list[str] = []
    blocks = sorted(
        (
            block
            for page in layout.pages
            for block in page.blocks
            if block.text_end > start and block.text_start < end
        ),
        key=lambda block: block.text_start,
    )
    for block in blocks:
        reasons = _layout_noise_reasons(block)
        if not reasons or not _is_removable_noise_block(block):
            continue
        left = max(start, block.text_start)
        right = min(end, block.text_end)
        if left > cursor:
            parts.append(source[cursor:left])
        parts.append("\n")
        cursor = max(cursor, right)
        removed.extend(reasons)
    if cursor < end:
        parts.append(source[cursor:end])
    return "".join(parts), list(dict.fromkeys(removed))


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

    # Real IJCAI/CV papers sometimes contain the literal word "Abstract" in
    # a page-one workflow diagram after section 1 has started. If a genuine
    # heading was already seen before the first main-section boundary, later
    # heading-shaped diagram labels cannot be the article abstract.
    main_section_names = {"introduction", "first_main_section", "generic_numbered_first_section"}
    main_section_starts = [
        match.start()
        for end_pattern in ABSTRACT_END_PATTERNS
        if end_pattern.name in main_section_names
        for match in end_pattern.regex.finditer(match_text[:limit])
    ]
    if hits and main_section_starts:
        first_main_section = min(main_section_starts)
        if any(hit[0] < first_main_section for hit in hits):
            hits = [hit for hit in hits if hit[0] < first_main_section]
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
            layout_boundary, layout_boundary_name = _find_layout_end_boundary(
                layout,
                start,
                min(limit, next_heading, start + config.max_chars),
                max(25, config.min_chars // 2),
            )
            if layout_boundary < boundary:
                boundary, boundary_name = layout_boundary, layout_boundary_name
            start, end, raw = _trim_raw_span(text, start, boundary)
            filtered_raw, layout_noise = _without_layout_noise(layout, start, end)
            removed_noise = list(dict.fromkeys(layout_noise + _removed_noise_names(filtered_raw)))
            clean = repair_abstract_text(filtered_raw)
            if len(clean) < config.min_chars:
                continue
            if len(clean) > config.max_chars:
                clean = clean[: config.max_chars].rstrip()
                end = min(end, start + config.max_chars)
            sentences, prose_ratio = _prose_metrics(clean)
            labels = _structured_labels(filtered_raw + "\n" + clean)
            page = _page_for_offset(layout, match.start())
            heading = " ".join(match.group("heading").split())
            # 弱标题词（summary/synopsis 等同义词）只在前两页有效（本地补丁 2026-09-09）：
            # 正文行首的普通词汇 "Summary"（如 4.pdf 第 3 页贡献列表段）会被误当标题，
            # 吞掉 search_limit 整段正文（实测 4561 字）。真 Summary 摘要必在首页区；
            # 强标题（abstract/摘要 0.9+）不受限（CNKI 封面页论文摘要在第 1~2 页）。
            if pattern.confidence < 0.9 and page > 1:
                continue
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
                        "removed_noise_count": len(removed_noise),
                        "removed_noise_patterns": ",".join(removed_noise),
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
        and not _is_removable_noise_block(block)
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
            raw = text[first.text_start : window[-1].text_end]
            filtered_raw, layout_noise = _without_layout_noise(
                layout, first.text_start, window[-1].text_end
            )
            removed_noise = list(dict.fromkeys(layout_noise + _removed_noise_names(filtered_raw)))
            clean = repair_abstract_text(filtered_raw)
            if len(clean) < config.min_chars:
                continue
            if len(clean) > config.max_chars:
                break
            score, evidence, labels = _score_unheaded(clean, filtered_raw, window, stop, body_font, title)
            evidence["end_pattern"] = stop_name or "none"
            evidence["removed_noise_count"] = len(removed_noise)
            evidence["removed_noise_patterns"] = ",".join(removed_noise)
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
        headed = [candidate for candidate in candidates if candidate.method == "headed"]
        rescue_winner = None
        if headed:
            best_headed_score = max(candidate.score for candidate in headed)
            competitive = [candidate for candidate in headed if candidate.score >= best_headed_score - 0.06]
            preferred = self.config.preferred_language
            if preferred != "auto":
                # zh 偏好须接受 mixed（2026-09-09 本地补丁）：中文摘要常含英文术语
                # （ResNet18/LSTM…），_language 会判 mixed；精确 == "zh" 会让英文候选
                # 抢走双语论文的中文摘要。
                acceptable = (preferred, "mixed") if preferred == "zh" else (preferred,)
                language_matches = [candidate for candidate in competitive if _language(candidate.text) in acceptable]
                if not language_matches:
                    # 救援（本地补丁）：CNKI 网络首发等版式会把"摘\n要："标题拆行打散进
                    # 阅读顺序（"摘"字孤立在句中），中文摘要无 headed 候选而英文
                    # Abstract 反而成形——从 unheaded 候选补位语言匹配者，保住
                    # "双语=抽中文"规则。按分数选（按 start 选会抓到作者/单位块）。
                    rescue = [
                        candidate for candidate in candidates
                        if candidate.method == "unheaded" and _language(candidate.text) in acceptable
                    ]
                    if rescue:
                        rescue_winner = max(rescue, key=lambda candidate: (candidate.score, -candidate.start))
                elif language_matches:
                    competitive = language_matches
            if rescue_winner is not None:
                winner = rescue_winner
            else:
                # In a bilingual article the first complete abstract is normally
                # the publication's primary-language abstract.
                winner = min(competitive, key=lambda candidate: (candidate.start, -candidate.score))
        else:
            winner = max(candidates, key=lambda candidate: (candidate.score, -candidate.start))
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
