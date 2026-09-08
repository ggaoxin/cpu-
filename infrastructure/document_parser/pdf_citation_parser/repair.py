"""Citation-aware repair for common PDF text-layer damage."""

from __future__ import annotations

from collections import Counter
import re
import unicodedata


SUP_TRANSLATION = str.maketrans(
    {
        "\u00b9": "1",
        "\u00b2": "2",
        "\u00b3": "3",
        "\u2070": "0",
        "\u2074": "4",
        "\u2075": "5",
        "\u2076": "6",
        "\u2077": "7",
        "\u2078": "8",
        "\u2079": "9",
        "\u207b": "-",
        "\u208b": "-",
    }
)
SUP_SEQUENCE = re.compile(r"[\u00b9\u00b2\u00b3\u2070\u2074-\u2079]+(?:[\u207b\u208b,;\u2013\u2014-][\u00b9\u00b2\u00b3\u2070\u2074-\u2079]+)*")
YEAR_RE = re.compile(r"(?:18|19|20|21)\d{2}[a-z]?", re.IGNORECASE)
NAME_RE = re.compile(r"(?:[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u024f'\u2019-]{1,}|[\u3400-\u9fff]{1,4})")


def _protect_unicode_superscripts(text: str, counts: Counter[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        counts["unicode_superscript_protected"] += 1
        return f"\u27e6SUP:{match.group(0).translate(SUP_TRANSLATION)}\u27e7"

    return SUP_SEQUENCE.sub(replace, text)


def _repair_numeric_brackets(text: str, counts: Counter[str]) -> str:
    # Bounded matching is deliberate: it repairs citation tokens, not arbitrary
    # bracketed prose or equations.
    bracket = re.compile(r"\[(?P<body>[^\[\]]{0,100})\]", re.DOTALL)
    permitted = re.compile(
        r"\s*\d[\d\s,;:.\-\u2010-\u2014\u2212A-Za-z()]*\s*",
        re.DOTALL,
    )
    locator = re.compile(
        r"\b(?:p{1,2}\.|fig\.|eq\.|sec\.|ch\.|lemma|theorem|algorithm|appendix|th\.)",
        re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        if not permitted.fullmatch(body):
            return match.group(0)
        if not re.search(r"\d", body):
            return match.group(0)
        original = body
        body = re.sub(r"(?<=\d)\s*[\r\n]+\s*(?=\d)", "", body)
        body = re.sub(r"(?<=\d)[ \t]+(?=\d)", "", body)
        body = re.sub(r"\s*[\r\n]+\s*", " ", body)
        body = re.sub(r"\s*([,;\-\u2010-\u2014\u2212])\s*", r"\1", body)
        body = re.sub(r"\s+", " ", body).strip()
        if body != original:
            counts["numeric_bracket_repaired"] += 1
        # Locator forms retain the meaningful space: [3, Fig. 1].
        if locator.search(body):
            body = re.sub(r",(?=[A-Za-z])", ", ", body)
        return f"[{body}]"

    return bracket.sub(replace, text)


def _repair_author_year_parentheses(text: str, counts: Counter[str]) -> str:
    paren = re.compile(r"([\(])([^()]{1,260})([\)])", re.DOTALL)

    def replace(match: re.Match[str]) -> str:
        body = match.group(2)
        if "\n" not in body or not YEAR_RE.search(body) or not NAME_RE.search(body):
            return match.group(0)
        fixed = re.sub(r"(?<=[A-Za-z\u00c0-\u024f])-\s*\n\s*(?=[A-Za-z\u00c0-\u024f])", "", body)
        fixed = re.sub(r"\s*\n\s*", " ", fixed)
        fixed = re.sub(r"\bet\s+al\s*\.", "et al.", fixed, flags=re.IGNORECASE)
        fixed = re.sub(r"\s+", " ", fixed).strip()
        counts["author_year_parenthesis_repaired"] += 1
        return f"({fixed})"

    return paren.sub(replace, text)


def repair_citation_text(text: str) -> tuple[str, dict[str, int]]:
    """Normalize Unicode and repair only bounded citation-like regions.

    Returns the repaired text and counters suitable for diagnostics.
    """

    counts: Counter[str] = Counter()
    text = _protect_unicode_superscripts(text, counts)
    normalized = unicodedata.normalize("NFKC", text)
    if normalized != text:
        counts["unicode_normalized"] += 1
    text = normalized.translate(
        {
            ord("\u3010"): "[",
            ord("\u3011"): "]",
            ord("\u3014"): "[",
            ord("\u3015"): "]",
            ord("\u3016"): "[",
            ord("\u3017"): "]",
            ord("\u200b"): None,
            ord("\u200c"): None,
            ord("\u200d"): None,
            ord("\ufeff"): None,
            ord("\u00ad"): None,
        }
    )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _repair_numeric_brackets(text, counts)
    text = _repair_author_year_parentheses(text, counts)

    # Narrative author-year citations split immediately before the year group.
    text, n = re.subn(
        r"(?<=[A-Za-z\u00c0-\u024f.\u3400-\u9fff])\s*\n\s*(?=\((?:18|19|20|21)\d{2}[a-z]?)",
        " ",
        text,
    )
    counts["narrative_author_year_repaired"] += n
    return text, dict(counts)


def recover_prose_lines(text: str) -> str:
    """Recover paragraphs without flattening section boundaries.

    Citation repair must run first. Blank lines remain paragraph separators;
    ordinary PDF line wraps become spaces; lexical hyphenation is removed.
    """

    text = re.sub(
        r"(?<=[A-Za-z\u00c0-\u024f])-\n(?=[a-z\u00df-\u024f])",
        "",
        text,
    )
    paragraphs = re.split(r"\n\s*\n+", text)
    recovered: list[str] = []
    for paragraph in paragraphs:
        paragraph = re.sub(r"[ \t]*\n[ \t]*", " ", paragraph)
        paragraph = re.sub(r"[ \t]{2,}", " ", paragraph).strip()
        if paragraph:
            recovered.append(paragraph)
    return "\n\n".join(recovered)
