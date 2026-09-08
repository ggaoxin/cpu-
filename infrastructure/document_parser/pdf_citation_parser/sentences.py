"""Conservative scientific and CJK sentence boundary recovery."""

from __future__ import annotations

from dataclasses import dataclass
import re


ABBREVIATIONS = {
    "al.", "approx.", "ca.", "cf.", "ch.", "dr.", "e.g.", "eq.", "eqs.",
    "et al.", "etc.", "fig.", "figs.", "i.e.", "mr.", "mrs.", "ms.",
    "no.", "pp.", "prof.", "ref.", "refs.", "sec.", "secs.", "vs.",
}


@dataclass(frozen=True, slots=True)
class SentenceSpan:
    text: str
    start: int
    end: int


def _last_token(text: str, end: int) -> str:
    fragment = text[max(0, end - 18) : end].lower()
    match = re.search(r"(?:[a-z]\.){2,}|[a-z]+(?:\s+al)?\.$", fragment)
    return match.group(0) if match else ""


def _is_decimal_or_initial(text: str, index: int) -> bool:
    before = text[index - 1] if index else ""
    after = text[index + 1] if index + 1 < len(text) else ""
    if before.isdigit() and after.isdigit():
        return True
    if before.isalpha() and index >= 1:
        # Initials such as "A. Smith".
        word_start = index - 1
        while word_start > 0 and text[word_start - 1].isalpha():
            word_start -= 1
        if index - word_start == 1 and after.isspace():
            return True
    return False


def split_sentences(text: str) -> list[SentenceSpan]:
    spans: list[SentenceSpan] = []
    start = 0
    i = 0
    round_depth = 0
    square_depth = 0
    while i < len(text):
        char = text[i]
        if char in "(\uff08":
            round_depth += 1
        elif char in ")\uff09":
            round_depth = max(0, round_depth - 1)
        elif char in "[\u3010":
            square_depth += 1
        elif char in "]\u3011":
            square_depth = max(0, square_depth - 1)
        boundary = False
        if char in "!?\u3002\uff01\uff1f":
            boundary = True
        elif char == ".":
            token = _last_token(text, i + 1)
            boundary = not _is_decimal_or_initial(text, i) and token not in ABBREVIATIONS
        elif char in ";\uff1b" and round_depth == 0 and square_depth == 0:
            # Treat a semicolon as a sentence boundary only in CJK prose. In
            # English it usually connects clauses; inside citations it is a
            # reference-list separator and must never split the sentence.
            nearby = text[max(start, i - 24) : min(len(text), i + 25)]
            boundary = bool(re.search(r"[\u3400-\u9fff]", nearby))
        elif char == "\n" and i + 1 < len(text) and text[i + 1] == "\n":
            boundary = True

        if boundary:
            end = i + 1
            # Absorb closing quotes/brackets and citation sentinels adjacent to
            # punctuation without consuming the next sentence.
            while end < len(text) and text[end] in "\"'\u2019\u201d)\uff09]":
                end += 1
            raw = text[start:end]
            left_trim = len(raw) - len(raw.lstrip())
            right = len(raw.rstrip())
            if right > left_trim:
                spans.append(SentenceSpan(raw.strip(), start + left_trim, start + right))
            start = end
            while start < len(text) and text[start].isspace():
                start += 1
            i = start
            continue
        i += 1

    if start < len(text):
        raw = text[start:]
        left_trim = len(raw) - len(raw.lstrip())
        if raw.strip():
            spans.append(SentenceSpan(raw.strip(), start + left_trim, len(text.rstrip())))
    return spans
