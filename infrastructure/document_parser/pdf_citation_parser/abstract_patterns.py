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
            r"^[ \t]*(?:[\[\u3010\u3014]\s*)?(?:key[ \t-]*words?|index\s+terms?|author\s+keywords?|"
            r"关键词|关\s*键\s*词|关键字|索引词)[ \t]*"
            r"(?:[\]\u3011\u3015][ \t]*[:：]?[ \t]*|[:：?.\u00b7\ufffd\-\u2013\u2014]|$)"
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
            r"^[ \t]*(?:[\[\u3010\u3014]\s*)?(?:jel\s+classification|msc(?:\s+classification)?|pacs(?:\s+numbers?)?|"
            r"中图分类号|文献标志码|文献标识码|文章编号)[ \t]*"
            r"(?:[\]\u3011\u3015][ \t]*[:：]?[ \t]*|[:：]|$)"
        ),
        0.94,
    ),
    AbstractPattern(
        "introduction",
        _c(
            r"^[ \t]*(?:(?:section\s+)?(?:[ivxlcdm]+|\d+(?:\.\d+)*)[.)]?[ \t]+)?"
            r"(?:introduction(?:[ \t]+(?:and|&)[ \t]+(?:motivation(?:s)?|background))?|"
            r"introductory\s+remarks|引\s*言|绪\s*论|緒\s*論)\s*[:：.]?[ \t]*$"
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
        "figure_table_caption",
        _c(r"^[ \t]*(?:figure|fig\.?|table|图|表)\s*\d{1,2}\s*[:.][ \t]*"),
        0.85,
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
    AbstractPattern(
        "figure_table_caption",
        _c(
            r"^[ \t]*(?:(?:figure|fig(?:ure)?\.?|table)\s*"
            r"(?:s?\d+[A-Za-z]?|[IVXLC]+)(?:\s*[.:：]|\s+[A-Z])|"
            r"(?:图|表)\s*(?:[一二三四五六七八九十百]+|\d+)[A-Za-z]?\s*[.:：、]?)"
        ),
        0.96,
    ),
    AbstractPattern(
        "references",
        _c(
            r"^[ \t]*(?:(?:section\s+)?(?:[ivxlcdm]+|\d+(?:\.\d+)*)[.)]?[ \t]+)?"
            r"(?:references?|bibliography|literature[ \t]+cited|参考文献|參考文獻)\s*[:：.]?[ \t]*$"
        ),
        0.96,
    ),
    AbstractPattern(
        "citation_instruction",
        _c(
            r"^[ \t]*(?:please[ \t]+use[ \t]+the[ \t]+following[ \t]+format[ \t]+when[ \t]+citing|"
            r"how[ \t]+to[ \t]+cite|to[ \t]+cite[ \t]+this[ \t]+(?:article|chapter))\b[^\n]{0,220}$"
        ),
        0.97,
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


# Strong, line-anchored patterns that are safe to remove from a candidate.
# A bare URL is deliberately absent: an abstract may legitimately say
# "Code and pre-trained models at https://...".
ABSTRACT_NOISE_LINE_PATTERNS: tuple[AbstractPattern, ...] = (
    AbstractPattern(
        "arxiv_watermark",
        _c(
            r"^[ \t]*(?:\*|\u2217|\u2020|\u2021|\u00a7|\u00b6)?[ \t]*"
            r"a[ \t]*r[ \t]*x[ \t]*i[ \t]*v[ \t]*:[ \t]*"
            r"\d{4}\.\d{4,5}(?:v\d+)?(?:[ \t]*\[[^\]\n]{2,30}\])?"
            r"(?:[ \t]+\d{1,2}[ \t]+[A-Za-z]{3,9}[ \t]+\d{4})?[ \t]*$"
        ),
        1.0,
    ),
    AbstractPattern(
        "corresponding_contact",
        _c(
            r"^[ \t]*(?:\*|\u2217|\u2020|\u2021|\u00a7|\u00b6|\d+)?[ \t]*"
            r"corresponding[ \t]+authors?[ \t]*[.:：]?[ \t]*"
            r"(?:contact|e-?mail|email)?[ \t]*[:：]?[ \t]*[^\n]{0,220}$"
        ),
        1.0,
    ),
    AbstractPattern(
        "correspondence_to",
        _c(
            r"^[ \t]*(?:\*|\u2217|\u2020|\u2021|\u00a7|\u00b6|\d+)?[ \t]*"
            r"correspondence[ \t]+(?:to|should[ \t]+be[ \t]+addressed[ \t]+to)"
            r"[ \t]*[:：]?[ \t]*[^\n]{0,220}$"
        ),
        1.0,
    ),
    AbstractPattern(
        "correspondence_at",
        _c(
            r"^[ \t]*(?:\*|\u2217|\u2020|\u2021|\u00a7|\u00b6|\d+)?[ \t]*"
            r"correspondence[ \t]*[:：][^\n]{0,160}\b(?:at|via)[ \t]+[^\n]{1,100}$"
        ),
        0.99,
    ),
    AbstractPattern(
        "cjk_corresponding_author",
        _c(
            r"^[ \t]*(?:\*|\u2217|\u2020|\u2021|\u00a7|\u00b6|\d+)?[ \t]*"
            r"(?:通讯作者|通信作者|通訊作者|聯絡作者|联系人|聯絡人)\s*[:：]?[^\n]{0,180}$"
        ),
        1.0,
    ),
    AbstractPattern(
        "contributor_footnote",
        _c(
            r"^[ \t]*(?:\*|\u2217|\u2020|\u2021|\u00a7|\u00b6|\d+)?[ \t]*"
            r"(?:core[ \t]+contributors?|equal(?:ly)?[ \t]+contribut(?:ions?|ors?|ed)|"
            r"(?:these[ \t]+)?authors?[ \t]+contributed[ \t]+equally|"
            r"共同(?:第一)?作者|同等贡献|共同貢獻)\b[^\n]{0,180}$"
        ),
        0.99,
    ),
    AbstractPattern(
        "page_resource_label",
        _c(
            r"^[ \t]*(?:project|model|code|data|home|paper|demo|dataset|repository|web)"
            r"[ \t]*(?:page|site)?[ \t]*[:：][ \t]*(?:https?://|www\.)\S+[ \t]*$"
        ),
        1.0,
    ),
    AbstractPattern(
        "cjk_page_resource_label",
        _c(
            r"^[ \t]*(?:项目|模型|代码|数据|主页|演示|資料|專案)(?:页面|頁面|地址|链接|連結)?"
            r"[ \t]*[:：][ \t]*(?:https?://|www\.)\S+[ \t]*$"
        ),
        1.0,
    ),
    AbstractPattern(
        "date_label",
        _c(
            r"^[ \t]*(?:date|日期)[ \t]*[:：][ \t]*(?:"
            r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[ \t]+[A-Za-z]{3,9}[ \t]+\d{4}|"
            r"[A-Za-z]{3,9}[ \t]+\d{1,2},?[ \t]+\d{4}|\d{4}年\d{1,2}月\d{1,2}日)"
            r"[^\n]{0,50}$"
        ),
        0.99,
    ),
    AbstractPattern(
        "standalone_email",
        _c(
            r"^[ \t]*(?:e-?mail[ \t]*[:：][ \t]*)?"
            r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?:[ \t]*[,;/][ \t]*)?)+[ \t]*$"
        ),
        0.99,
    ),
    AbstractPattern(
        "contact_email_label",
        _c(
            r"^[ \t]*(?:contact|contacts|e-?mail|email)[ \t]*[:：][ \t]*"
            r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?:[ \t]*[,;/][ \t]*)?)+[ \t]*$"
        ),
        1.0,
    ),
    AbstractPattern(
        "copyright_license",
        _c(
            r"^[ \t]*(?:\u00a9|copyright\b|all[ \t]+rights[ \t]+reserved\b|"
            r"this[ \t]+work[ \t]+is[ \t]+licensed\b|open[ \t]+access\b|"
            r"版[ \t]*权[ \t]*所[ \t]*有|版[ \t]*權[ \t]*所[ \t]*有)[^\n]{0,260}$"
        ),
        0.98,
    ),
    AbstractPattern(
        "submission_history",
        _c(
            r"^[ \t]*(?:(?:received|revised|accepted|published(?:[ \t]+online)?)"
            r"[ \t]*[:：]|(?:收稿|修回|录用|接受|发表|出版)日期[ \t]*[:：])[^\n]{1,160}$"
        ),
        0.98,
    ),
)


# Broader signals used for candidate scoring and title exclusion. These are
# not blindly removed because words such as "university" or "received" can
# occur in valid prose.
FRONT_MATTER_NOISE_PATTERNS: tuple[AbstractPattern, ...] = (
    AbstractPattern("email", _c(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), 1.0),
    AbstractPattern(
        "affiliation",
        _c(r"\b(?:university|institute|laboratory|department|school\s+of|college|academy|hospital)\b|大学|学院|研究院|实验室|医院"),
        0.9,
    ),
    AbstractPattern(
        "publication_metadata",
        _c(r"\b(?:doi\s*:|arxiv\s*:|received|accepted|published|copyright|issn|isbn|corresponding\s+author)\b|收稿日期|基金项目|作者简介|通讯作者"),
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
    "noise_line": ABSTRACT_NOISE_LINE_PATTERNS,
    "front_matter_noise": FRONT_MATTER_NOISE_PATTERNS,
    "unheaded_signal": UNHEADED_ABSTRACT_SIGNAL_PATTERNS,
}


def iter_patterns(group: str, text: str) -> Iterator[tuple[AbstractPattern, re.Match[str]]]:
    for pattern in ABSTRACT_PATTERN_GROUPS[group]:
        for match in pattern.regex.finditer(text):
            yield pattern, match
