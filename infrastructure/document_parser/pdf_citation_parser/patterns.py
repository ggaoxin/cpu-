"""Modular citation regex library.

The expressions intentionally model syntax families. PDF damage repair belongs in
``repair.py``; semantic checks (especially numeric range validation) belong in
``parser.py``. Keeping those concerns separate prevents a single opaque regex.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterator, Pattern


FLAGS = re.IGNORECASE | re.UNICODE | re.VERBOSE
YEAR = r"(?:18|19|20|21)\d{2}[a-z]?"
NUMBER = r"\d{1,5}"
RANGE_SEP = r"[-\u2010\u2011\u2012\u2013\u2014\u2212]"
LIST_SEP = r"[,;]"
NUM_ITEM = rf"{NUMBER}(?:\s*{RANGE_SEP}\s*{NUMBER})?"
NUM_LIST = rf"{NUM_ITEM}(?:\s*{LIST_SEP}\s*{NUM_ITEM})*"

# Names cover Latin names with diacritics, common particles, and CJK surnames.
LATIN_NAME = r"(?:[A-Z\u00c0-\u00d6\u00d8-\u00de][A-Za-z\u00c0-\u024f'\u2019-]+)"
CJK_COMPOUND_SURNAME = r"(?:欧阳|司马|上官|诸葛|东方|皇甫|尉迟|公孙|慕容|司徒|司空|夏侯|令狐)"
CJK_SINGLE_SURNAME = r"[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛伍余米贝姚孟顾尹江钟蔡田樊胡凌霍虞万支柯管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包左石崔吉龚程嵇邢滑裴陆荣翁荀羊甄曲封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东殴殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公]"
CJK_PERSON = rf"(?:(?:{CJK_COMPOUND_SURNAME}|{CJK_SINGLE_SURNAME})[\u3400-\u9fff]{{1,2}})"
CJK_NAME = rf"(?:{CJK_PERSON}|[\u3400-\u9fff]{{1,4}})"
PARTICLE = r"(?:(?:de|del|der|di|du|la|le|van|von)\s+)?"
SURNAME = rf"(?:{PARTICLE}{LATIN_NAME}|{CJK_NAME})"
ET_AL = r"(?:et\s+al\.?|等)"
JOINER = r"(?:,?\s*(?:&|and|和|与|、)\s*)"
AUTHOR_GROUP = rf"(?:{SURNAME}(?:\s+{ET_AL}|{JOINER}{SURNAME})?)"


@dataclass(frozen=True, slots=True)
class NamedPattern:
    name: str
    regex: Pattern[str]
    kind: str
    confidence: float


def _c(pattern: str, *, flags: int = FLAGS) -> Pattern[str]:
    return re.compile(pattern, flags)


# IEEE, ACM numeric, Springer numeric, Elsevier numeric, AAAI/IJCAI and
# CVPR/ICCV/ECCV commonly resolve to these bracket forms. Variants are kept
# separate so callers can tune or disable ambiguous syntax.
NUMERIC_PATTERNS: tuple[NamedPattern, ...] = (
    NamedPattern(
        "adjacent_square_groups",
        _c(
            rf"(?<![\d\[]) [\[\u3010]\s*{NUM_LIST}\s*[\]\u3011]"
            rf"(?:\s*(?:[,;]|{RANGE_SEP})\s*[\[\u3010]\s*{NUM_LIST}\s*[\]\u3011])+"
        ),
        "numeric",
        0.97,
    ),
    NamedPattern(
        "square_list_or_range",
        # Citations are often attached directly to the preceding word in
        # Chinese typesetting and some Elsevier templates: 文献[1], brackets[2].
        _c(rf"(?<![\d\[]) [\[\u3010]\s*{NUM_LIST}\s*[\]\u3011]"),
        "numeric",
        0.96,
    ),
    NamedPattern(
        "square_with_locator",
        _c(
            rf"(?<![\d\[]) [\[\u3010]\s*{NUMBER}\s*,\s*"
            r"(?:p{1,2}\.|fig\.|eq\.|sec\.|ch\.|lemma|theorem|algorithm|appendix)"
            r"\s*[A-Za-z0-9.\u2013-]+\s*[\]\u3011]"
        ),
        "numeric",
        0.94,
    ),
    NamedPattern(
        "parenthetical_numeric",
        _c(rf"(?<![\w\d])\(\s*{NUM_LIST}\s*\)(?!\s*[=+*/^])"),
        "numeric",
        0.66,
    ),
    NamedPattern(
        "explicit_ref_prefix",
        _c(
            rf"\b(?:refs?|references?)\.?\s+(?:nos?\.?\s*)?"
            rf"{NUM_ITEM}(?:\s*{LIST_SEP}\s*{NUM_ITEM})*"
        ),
        "numeric",
        0.76,
    ),
)


# ACL/AAAI/NeurIPS/ICML papers commonly use natbib-like forms; ACM and
# Springer also explicitly support author-year styles.
AUTHOR_YEAR_PATTERNS: tuple[NamedPattern, ...] = (
    NamedPattern(
        "parenthetical_author_year",
        _c(
            rf"[\(\uff08]\s*{AUTHOR_GROUP}\s*,?\s*{YEAR}"
            rf"(?:\s*[,;]\s*(?:{AUTHOR_GROUP}\s*,?\s*)?{YEAR})*\s*[\)\uff09]"
        ),
        "author_year",
        0.95,
    ),
    NamedPattern(
        "square_author_year",
        _c(
            rf"[\[]\s*{AUTHOR_GROUP}\s*,?\s*{YEAR}"
            rf"(?:\s*[,;]\s*(?:{AUTHOR_GROUP}\s*,?\s*)?{YEAR})*\s*[\]]"
        ),
        "author_year",
        0.88,
    ),
    NamedPattern(
        "cjk_narrative_author_year",
        _c(
            rf"{CJK_PERSON}(?:\s*(?:等|、|和|与)\s*{CJK_PERSON})?\s*"
            rf"[\(\uff08]\s*{YEAR}(?:\s*[,;]\s*{YEAR})*\s*[\)\uff09]"
        ),
        "author_year",
        0.95,
    ),
    NamedPattern(
        "narrative_author_year",
        _c(rf"(?<![\w]){AUTHOR_GROUP}\s*[\(\uff08]\s*{YEAR}(?:\s*[,;]\s*{YEAR})*\s*[\)\uff09]"),
        "author_year",
        0.93,
    ),
    NamedPattern(
        "possessive_narrative_author_year",
        _c(rf"(?<![\w]){SURNAME}(?:['\u2019]s)?\s*[\(\uff08]\s*{YEAR}\s*[\)\uff09]"),
        "author_year",
        0.90,
    ),
    NamedPattern(
        "bare_et_al_year",
        _c(rf"(?<![\w])(?:{SURNAME}\s+{ET_AL})\s*,\s*{YEAR}"),
        "author_year",
        0.78,
    ),
)


SUP_DIGITS = "\u00b9\u00b2\u00b3\u2070\u2074\u2075\u2076\u2077\u2078\u2079"
SUP_SEPARATORS = "\u207b\u208b,;\u2013\u2014-"
SUPERSCRIPT_PATTERNS: tuple[NamedPattern, ...] = (
    NamedPattern(
        "layout_superscript",
        _c(r"\u27e6SUP:\s*\d{1,5}(?:\s*[,;\u2013\u2014-]\s*\d{1,5})*\s*\u27e7"),
        "superscript",
        0.91,
    ),
    NamedPattern(
        "unicode_superscript",
        _c(rf"(?<![\d{SUP_DIGITS}])[{SUP_DIGITS}]+(?:[{SUP_SEPARATORS}][{SUP_DIGITS}]+)*(?![{SUP_DIGITS}])"),
        "superscript",
        0.80,
    ),
)


# These patterns document/detect damage before repair and are useful for QA.
# Extraction normally runs against the repaired representation.
BROKEN_PDF_PATTERNS: tuple[NamedPattern, ...] = (
    NamedPattern(
        "numeric_bracket_newline",
        _c(r"\[\s*\n[\s\d,;\u2013\u2014-]{1,80}\]|\[[\s\d,;\u2013\u2014-]{1,80}\n\s*\]", flags=FLAGS),
        "broken_pdf",
        0.75,
    ),
    NamedPattern(
        "numeric_internal_whitespace",
        _c(r"\[(?:\s*\d\s+\d[\s\d,;\u2013\u2014-]*)\]"),
        "broken_pdf",
        0.70,
    ),
    NamedPattern(
        "author_year_newline",
        _c(rf"[\(\uff08][^()\n]{{0,100}}{SURNAME}[^()]{{0,80}}\n[^()]{{0,80}}{YEAR}[^()]{{0,30}}[\)\uff09]"),
        "broken_pdf",
        0.75,
    ),
    NamedPattern(
        "split_et_al",
        _c(rf"{SURNAME}\s*\n\s*et\s*\n?\s*al\.?\s*,?\s*\n?\s*{YEAR}"),
        "broken_pdf",
        0.78,
    ),
    NamedPattern(
        "split_every_numeric_component",
        _c(
            r"\[\s*(?:\n\s*)?\d(?:\s*\n\s*\d)*"
            r"(?:\s*(?:,|;|-|\u2013|\u2014)\s*\n?\s*\d(?:\s*\n\s*\d)*)+\s*\n?\s*\]"
        ),
        "broken_pdf",
        0.82,
    ),
    NamedPattern(
        "detached_bracket_spans",
        _c(r"\[\s*\n(?:\s*\n)*\s*\d[\d\s\n,;\u2013\u2014-]{0,80}(?:\n\s*)+\]"),
        "broken_pdf",
        0.80,
    ),
)


REFERENCE_HEADING_PATTERNS: tuple[NamedPattern, ...] = (
    NamedPattern(
        "references",
        _c(
            r"^\s*(?:(?:section\s+)?(?:[ivxlcdm]+|\d+(?:\.\d+)*)[.)]?\s+)?"
            r"(?:references|bibliography|works\s+cited|literature\s+cited|references\s+and\s+notes)\s*[:.]?\s*$",
            flags=FLAGS | re.MULTILINE,
        ),
        "reference_heading",
        1.0,
    ),
    NamedPattern(
        "cjk_references",
        _c(
            r"^\s*(?:(?:第?[一二三四五六七八九十\d]+[章节.]?)\s*)?"
            r"(?:参\s*考\s*文\s*献|引\s*用\s*文\s*献|參\s*考\s*文\s*獻)\s*$",
            flags=FLAGS | re.MULTILINE,
        ),
        "reference_heading",
        1.0,
    ),
    NamedPattern(
        "spaced_references",
        _c(
            r"^\s*(?:(?:section\s+)?(?:[ivxlcdm]+|\d+(?:\.\d+)*)[.)]?\s+)?"
            r"r\s*e\s*f\s*e\s*r\s*e\s*n\s*c\s*e\s*s\s*$",
            flags=FLAGS | re.MULTILINE,
        ),
        "reference_heading",
        0.98,
    ),
    NamedPattern(
        "european_bibliography",
        _c(r"^\s*(?:literaturverzeichnis|quellenverzeichnis|r[e\u00e9]f[e\u00e9]rences|bibliograf[i\u00ed]a)\s*$", flags=FLAGS | re.MULTILINE),
        "reference_heading",
        1.0,
    ),
    NamedPattern(
        "references_cited",
        _c(
            r"^\s*(?:references\s+cited|cited\s+literature|bibliographical\s+references)\s*$",
            flags=FLAGS | re.MULTILINE,
        ),
        "reference_heading",
        1.0,
    ),
    NamedPattern(
        "expanded_cjk_references",
        _c(
            r"^\s*(?:主\s*要\s*)?(?:参\s*考\s*书\s*目|参\s*考\s*资\s*料|參\s*考\s*書\s*目)\s*$",
            flags=FLAGS | re.MULTILINE,
        ),
        "reference_heading",
        0.96,
    ),
)


PATTERN_GROUPS: dict[str, tuple[NamedPattern, ...]] = {
    "numeric": NUMERIC_PATTERNS,
    "author_year": AUTHOR_YEAR_PATTERNS,
    "superscript": SUPERSCRIPT_PATTERNS,
    "broken_pdf": BROKEN_PDF_PATTERNS,
    "reference_heading": REFERENCE_HEADING_PATTERNS,
}


def iter_group(group: str, text: str) -> Iterator[tuple[NamedPattern, re.Match[str]]]:
    for named in PATTERN_GROUPS[group]:
        for match in named.regex.finditer(text):
            yield named, match


def is_reference_heading(text: str) -> bool:
    compact = " ".join(text.strip().split())
    return any(item.regex.fullmatch(compact) for item in REFERENCE_HEADING_PATTERNS)
