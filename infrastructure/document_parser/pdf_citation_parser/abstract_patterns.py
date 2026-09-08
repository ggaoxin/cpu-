"""Maintainable regex families for English, Chinese and multilingual abstracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterator, Pattern


FLAGS = re.IGNORECASE | re.MULTILINE | re.UNICODE


@dataclass(frozen=True, slots=True)
class AbstractPattern:
    name: str
    regex: Pattern[str]
    confidence: float


def _c(pattern: str, flags: int = FLAGS) -> Pattern[str]:
    return re.compile(pattern, flags)


# Matches only the heading and its separator. The following content remains
# outside the match, whether it starts on the same line or the next block.
ABSTRACT_HEADING_PATTERNS: tuple[AbstractPattern, ...] = (
    AbstractPattern(
        "english_abstract",
        _c(r"^[ \t]*(?P<heading>abstract)\b[ \t]*(?:[:?.\u00b7\ufffd\-\u2012\u2013\u2014]\s*)?"),
        0.97,
    ),
    AbstractPattern(
        "english_summary",
        _c(r"^[ \t]*(?P<heading>summary|synopsis)\b[ \t]*(?:[:?.\u00b7\ufffd\-\u2012\u2013\u2014]\s*)?"),
        0.88,
    ),
    AbstractPattern(
        "extended_abstract",
        _c(r"^[ \t]*(?P<heading>extended\s+abstract)\b[ \t]*(?:[:?.\u00b7\ufffd\-\u2012\u2013\u2014]\s*)?"),
        0.84,
    ),
    AbstractPattern(
        "author_summary",
        _c(r"^[ \t]*(?P<heading>author\s+summary)\b[ \t]*(?:[:?.\u00b7\ufffd\-\u2012\u2013\u2014]\s*)?"),
        0.76,
    ),
    AbstractPattern(
        "cjk_abstract",
        _c(
            r"^[ \t]*(?P<heading>(?:中\s*文\s*)?摘\s*要|内\s*容\s*摘\s*要|"
            r"提\s*要|概\s*要)[ \t]*(?:[:：?.。\u00b7\ufffd\-\u2013\u2014]\s*)?"
        ),
        0.98,
    ),
    AbstractPattern(
        "bracketed_cjk_abstract",
        _c(
            r"^[ \t]*[\[\u3010\u3014]\s*(?P<heading>摘\s*要|提\s*要|概\s*要)\s*"
            r"[\]\u3011\u3015][ \t]*(?:[:：?.。\u00b7\ufffd\-\u2013\u2014]\s*)?"
        ),
        0.94,
    ),
    AbstractPattern(
        "romance_abstract",
        _c(
            r"^[ \t]*(?P<heading>r[e\u00e9]sum[e\u00e9]|resumen|resumo|riassunto)\b"
            r"[ \t]*(?:[:?.\u00b7\ufffd\-\u2013\u2014]\s*)?"
        ),
        0.82,
    ),
    AbstractPattern(
        "german_abstract",
        _c(r"^[ \t]*(?P<heading>zusammenfassung)\b[ \t]*(?:[:?.\u00b7\ufffd\-\u2013\u2014]\s*)?"),
        0.82,
    ),
)


# PyMuPDF may return each heading glyph as its own span/line, or preserve a
# line-end hyphen inside the word. These patterns are intentionally separate
# from clean headings so their behavior can be tested and tuned independently.
BROKEN_ABSTRACT_HEADING_PATTERNS: tuple[AbstractPattern, ...] = (
    AbstractPattern(
        "spaced_english_abstract",
        _c(
            r"^[ \t]*(?P<heading>A[ \t\n]*B[ \t\n]*S[ \t\n]*T[ \t\n]*R"
            r"[ \t\n]*A[ \t\n]*C[ \t\n]*T)[ \t]*(?:[:?.\u00b7\ufffd\-\u2013\u2014]\s*)?"
        ),
        0.91,
    ),
    AbstractPattern(
        "hyphen_split_english_abstract",
        _c(r"^[ \t]*(?P<heading>ab\s*-\s*\n\s*stract)\b[ \t]*(?:[:?.\u00b7\ufffd\-\u2013\u2014]\s*)?"),
        0.88,
    ),
    AbstractPattern(
        "line_split_cjk_abstract",
        _c(r"^[ \t]*(?P<heading>摘[ \t\n]+要)[ \t]*(?:[:：?.。\u00b7\ufffd\-\u2013\u2014]\s*)?"),
        0.93,
    ),
)


# Boundary patterns match the start of the first non-abstract section. They are
# deliberately anchored to physical/reconstructed lines to avoid stopping on
# words such as "introduction" inside abstract prose.
ABSTRACT_END_PATTERNS: tuple[AbstractPattern, ...] = (
    AbstractPattern(
        "keywords",
        _c(
            r"^[ \t]*(?:key[ \t-]*words?|index\s+terms?|author\s+keywords?|"
            r"关键词|关\s*键\s*词|关键字|索引词)[ \t]*(?:[:：?.\u00b7\ufffd\-\u2013\u2014]|$)"
        ),
        0.98,
    ),
    AbstractPattern(
        "acm_metadata",
        _c(
            r"^[ \t]*(?:ccs\s+concepts?|categories\s+and\s+subject\s+descriptors|"
            r"acm\s+reference\s+format|additional\s+key\s+words)\b"
        ),
        0.97,
    ),
    AbstractPattern(
        "classification_codes",
        _c(
            r"^[ \t]*(?:jel\s+classification|msc(?:\s+classification)?|pacs(?:\s+numbers?)?|"
            r"中图分类号|文献标志码|文章编号)[ \t]*(?:[:：]|$)"
        ),
        0.94,
    ),
    AbstractPattern(
        "introduction",
        _c(
            r"^[ \t]*(?:(?:section\s+)?(?:[ivxlcdm]+|\d+(?:\.\d+)*)[.)]?[ \t]+)?"
            r"(?:introduction|introductory\s+remarks|引\s*言|绪\s*论|緒\s*論)\s*[:：.]?[ \t]*$"
        ),
        0.98,
    ),
    AbstractPattern(
        "first_main_section",
        _c(
            r"^[ \t]*(?:1|I)[.)]?[ \t]+(?:background|overview|preliminaries|motivation|"
            r"related\s+work|研究背景|问题提出|研究设计)\s*[:：.]?[ \t]*$"
        ),
        0.86,
    ),
    AbstractPattern(
        "other_front_sections",
        _c(r"^[ \t]*(?:plain\s+language\s+summary|highlights?|nomenclature|graphical\s+abstract)\s*[:：.]?[ \t]*$"),
        0.88,
    ),
    AbstractPattern(
        "generic_numbered_first_section",
        _c(r"^[ \t]*(?:1|I)[.)]?[ \t]+[A-Z\u3400-\u9fff][^\n]{1,80}$"),
        0.78,
    ),
    AbstractPattern(
        "inline_keywords",
        _c(r"(?<=[.!?。！？])[ \t]+(?:key[ \t-]*words?|index\s+terms?|关键词|关键字)[ \t]*(?:[:：?\u00b7\ufffd\-\u2013\u2014])"),
        0.90,
    ),
    AbstractPattern(
        "spaced_keywords",
        _c(
            r"^[ \t]*(?:K[ \t]*E[ \t]*Y[ \t]*W[ \t]*O[ \t]*R[ \t]*D[ \t]*S?|"
            r"I[ \t]*N[ \t]*D[ \t]*E[ \t]*X[ \t]+T[ \t]*E[ \t]*R[ \t]*M[ \t]*S)"
            r"[ \t]*(?:[:：?.\u00b7\ufffd\-\u2013\u2014]|$)"
        ),
        0.88,
    ),
)


STRUCTURED_ABSTRACT_LABEL_PATTERNS: tuple[AbstractPattern, ...] = (
    AbstractPattern(
        "english_structured_labels",
        _c(
            r"(?:^|(?<=[.;]))\s*(?P<label>background|context|importance|objective(?:s)?|"
            r"aim(?:s)?|purpose|design|setting|participants|interventions?|materials\s+and\s+methods|"
            r"methods?|main\s+outcome\s+measures?|results?|findings?|conclusions?|interpretation|"
            r"relevance|trial\s+registration)\s*[:\u2014-]"
        ),
        0.92,
    ),
    AbstractPattern(
        "cjk_structured_labels",
        _c(
            r"(?:^|(?<=[。；;]))\s*(?P<label>背景|目的|目标|方法|材料与方法|结果|结论|意义|"
            r"创新点|研究设计|临床意义)\s*[:：]"
        ),
        0.94,
    ),
    AbstractPattern(
        "english_standalone_labels",
        _c(
            r"^[ \t]*(?P<label>background|context|importance|objective(?:s)?|aim(?:s)?|purpose|"
            r"design|setting|participants|interventions?|materials\s+and\s+methods|methods?|"
            r"results?|findings?|conclusions?|interpretation|relevance)\s*[:\u2014-]?[ \t]*$"
        ),
        0.84,
    ),
    AbstractPattern(
        "cjk_standalone_labels",
        _c(r"^[ \t]*(?P<label>背景|目的|目标|方法|材料与方法|结果|结论|意义|创新点|研究设计)\s*[:：]?[ \t]*$"),
        0.88,
    ),
)


FRONT_MATTER_NOISE_PATTERNS: tuple[AbstractPattern, ...] = (
    AbstractPattern("email", _c(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), 1.0),
    AbstractPattern(
        "affiliation",
        _c(r"\b(?:university|institute|laboratory|department|school\s+of|college|academy|hospital)\b|大学|学院|研究院|实验室|医院"),
        0.9,
    ),
    AbstractPattern(
        "publication_metadata",
        _c(r"\b(?:doi\s*:|https?://|arxiv\s*:|received|accepted|published|copyright|issn|isbn|corresponding\s+author)\b|收稿日期|基金项目|作者简介|通讯作者"),
        0.95,
    ),
    AbstractPattern("graphical_abstract", _c(r"\b(?:graphical|visual)\s+abstract\b|图文摘要"), 1.0),
    AbstractPattern("figure_table", _c(r"^[ \t]*(?:figure|fig\.|table|图|表)\s*\d+\b"), 0.9),
)


UNHEADED_ABSTRACT_SIGNAL_PATTERNS: tuple[AbstractPattern, ...] = (
    AbstractPattern(
        "english_research_voice",
        _c(r"\b(?:in\s+this\s+(?:paper|work|study)|this\s+(?:paper|work|study)|we\s+(?:propose|present|introduce|investigate|develop|show|demonstrate|report|evaluate)|here,?\s+we)\b"),
        0.8,
    ),
    AbstractPattern(
        "english_results_voice",
        _c(r"\b(?:our\s+(?:results|findings|experiments)|experimental\s+results|results\s+(?:show|demonstrate|indicate)|we\s+find\s+that)\b"),
        0.75,
    ),
    AbstractPattern(
        "cjk_research_voice",
        _c(r"(?:本文|本研究|本论文|该研究|本工作)(?:提出|研究|探讨|构建|设计|实现|分析|采用|旨在|针对)|研究结果(?:表明|显示)|结果表明"),
        0.83,
    ),
)


ABSTRACT_PATTERN_GROUPS: dict[str, tuple[AbstractPattern, ...]] = {
    "heading": ABSTRACT_HEADING_PATTERNS,
    "broken_heading": BROKEN_ABSTRACT_HEADING_PATTERNS,
    "end": ABSTRACT_END_PATTERNS,
    "structured_label": STRUCTURED_ABSTRACT_LABEL_PATTERNS,
    "front_matter_noise": FRONT_MATTER_NOISE_PATTERNS,
    "unheaded_signal": UNHEADED_ABSTRACT_SIGNAL_PATTERNS,
}


def iter_patterns(group: str, text: str) -> Iterator[tuple[AbstractPattern, re.Match[str]]]:
    for pattern in ABSTRACT_PATTERN_GROUPS[group]:
        for match in pattern.regex.finditer(text):
            yield pattern, match
