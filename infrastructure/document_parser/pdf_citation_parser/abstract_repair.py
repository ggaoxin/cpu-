"""Targeted cleanup for abstract text extracted from PDF spans and lines."""

from __future__ import annotations

import re
import unicodedata

from .abstract_patterns import ABSTRACT_NOISE_LINE_PATTERNS


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
    # Remove only high-precision, line-shaped front-matter noise. In
    # particular, do not remove generic URLs or strings containing '@'.
    for pattern in ABSTRACT_NOISE_LINE_PATTERNS:
        text = pattern.regex.sub("", text)
    # PyMuPDF sometimes makes the label and the contact address two physical
    # lines inside one block.
    text = re.sub(
        r"(?im)^[ \t]*(?:\*|\u2020|\u2021)?[ \t]*corresponding[ \t]+authors?"
        r"[ \t]*[.:：]?[ \t]*\n[ \t]*(?:contact|e-?mail|email)[ \t]*[:：]?[ \t]*"
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}[ \t]*$",
        "",
        text,
    )
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
    # 上标序号标记（⟦SUP:1⟧ 作者/单位上标，版面重建混入摘要文本）
    text = re.sub(r"⟦SUP:[^⟧]*⟧", " ", text)
    # 行中版权句（本地补丁 2026-09-09，5.pdf 案例）：行锚定模式抓不到跟在正文
    # 句后的 "© 2013 Author(s). … licensed under a Creative Commons … License."
    # 锚定穿过 Creative Commons…License.，避免非贪婪停在 "licensed" 词内。
    text = re.sub(
        r"(?i)\s*©\s*\d{4}[\s\S]{0,320}?creative\s+commons[\s\S]{0,80}?license\.?",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\s*©\s*\d{4}[\s\S]{0,240}?(?:all\s+rights\s+reserved|licensed\s+to\s+\w+)\.?",
        " ",
        text,
    )
    # 尾部方括号 DOI/URL 残块：…License. [http://dx.doi.org/10.1063/…]
    text = re.sub(r"\s*\[\s*https?://\S+\s*\]", " ", text)
    # 尾部碎片修剪（本地补丁 2026-09-09）：最后一个真实句末标点（数字小数点
    # 不算——2.5/4.1 会干扰 rfind）之后的尾巴若
    # ① <40 字符且无标点（10.pdf 残头 "The COT"），或
    # ② ≥6 个 token 且 ≥90% 为大写开头/数字形态（6/11.pdf 图例模型名串与表体
    #   "Gemini 2.5 Pro … 80.7 80.5"——正常英文句含 the/of 等小写词不会命中），
    # 则修剪掉。合法的"末句无句号"整句（长且含小写词）不受影响。
    import re as _tail_re
    _terms = [m.end() for m in _tail_re.finditer(r"(?<!\d)[.。!?](?=\s|$)", text)]
    _term = _terms[-1] if _terms else None
    if _term is not None and _term < len(text):
        tail = text[_term:].strip()
        if tail:
            tokens = tail.split()
            cap_ratio = (
                sum(1 for tk in tokens
                    if _tail_re.match(r"^[A-Z0-9]", tk.strip("()[]{}+±–—-"))) / len(tokens)
                if tokens else 0
            )
            if len(tail) < 40 or (len(tokens) >= 6 and cap_ratio >= 0.9):
                text = text[:_term].rstrip()
    # 末句超短碎片（10.pdf "The COT."）：带句号但 ≤3 个英文词的尾巴整句剪掉
    # （要求按空格分词且含拉丁字母——中文无空格整句不受影响）
    if len(_terms) >= 1:
        _start = _terms[-2] if len(_terms) >= 2 else 0
        _last_sent = text[_start:].strip()
        if (_last_sent and " " in _last_sent and _tail_re.search(r"[A-Za-z]", _last_sent)
                and len(_last_sent.split()) <= 3):
            text = text[:_start].rstrip()
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # 前导机构名残留（4.pdf：单位块与摘要同块合并，块级噪声过滤失效）：
    # 前缀若全为 Title-Case/全大写/连接词（of/for/and/the…）且含机构关键词
    # （center/university/labs…），在首个非连接词小写 token 处截断。正常英文
    # 摘要开头的小写词（prevalence/discovery…）会在第 1~2 词触发且前缀无机构词/
    # 词数不足，不受影响；中文无空格分词天然不命中。
    _org_re = re.compile(
        r"(?i)\b(?:center|centre|institute|university|laboratory|labs?|academy|"
        r"college|school|inc|ltd|gmbh|corp|company|technolog(?:y|ies))\b")
    _connectors = {"of", "for", "and", "the", "de", "at", "in", "on", "to", "with", "a", "an"}
    _toks = text.split(" ")
    if len(_toks) > 4:
        _cut = None
        for _i, _tk in enumerate(_toks[:20]):
            _core = _tk.strip(",.;:()[]&")
            if not _core:
                continue
            # 断点 = 首个非连接词的小写单词，或 CJK 字符（中文摘要天然不命中）
            if (_core[:1].islower() and _core not in _connectors) or re.match(r"[㐀-鿿]", _core):
                _cut = _i
                break
        # 句首回退：切点前一 token 若为 Title 且本身非机构词（如 "Large language
        # model…" 的 Large），它更像句子首词而非机构名一部分 → 切点前移一位
        if _cut is not None and _cut >= 2:
            _prev = _toks[_cut - 1].strip(",.;:()[]&")
            if (_prev[:1].isupper() and not _org_re.search(_prev)
                    and _toks[_cut][:1].islower()):
                _cut -= 1
        if _cut is not None and 2 <= _cut <= 18:
            _prefix = " ".join(_toks[:_cut])
            if (len(_prefix) <= 90 and _org_re.search(_prefix)
                    and not _org_re.search(" ".join(_toks[_cut:_cut + 3]))):
                text = " ".join(_toks[_cut:]).lstrip(" ,;–-")
    text = text.strip()
    return re.sub(r"^[:：?.\u00b7\ufffd\-\u2013\u2014]+\s*", "", text)
