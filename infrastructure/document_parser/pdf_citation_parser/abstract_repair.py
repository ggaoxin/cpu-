"""Targeted cleanup for abstract text extracted from PDF spans and lines."""

from __future__ import annotations

import re
import unicodedata


def repair_abstract_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(
        {
            ord("\u00ad"): None,
            ord("\u200b"): None,
            ord("\u200c"): None,
            ord("\u200d"): None,
            ord("\ufeff"): None,
        }
    )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Lexical line-end hyphenation, including an intervening blank block caused
    # by separately extracted spans. Real compound dashes are preserved.
    text = re.sub(
        r"(?<=[A-Za-z\u00c0-\u024f])-\s*\n(?:\s*\n)?\s*(?=[a-z\u00df-\u024f])",
        "",
        text,
    )
    # Rejoin English heading glyphs when PyMuPDF emits one span per glyph.
    text = re.sub(
        r"(?im)^\s*A\s*B\s*S\s*T\s*R\s*A\s*C\s*T\s*(?=[:.\-\u2013\u2014]|$)",
        "Abstract",
        text,
    )
    text = re.sub(r"(?m)^\s*摘\s+要\s*(?=[:：.。\-\u2013\u2014]|$)", "摘要", text)
    # Page numbers and running headers that land between abstract blocks.
    text = re.sub(r"(?m)^\s*(?:page\s+)?\d{1,4}\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()
    return re.sub(r"^[:：?.\u00b7\ufffd\-\u2013\u2014]+\s*", "", text)
