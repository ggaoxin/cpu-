"""Input representation for paper-like and generic scientific text.

The Vue contract is always ``id + publication_date + text``.  A paper-like
title/abstract/keyword structure is an optional, source-grounded optimization;
it is never fabricated for reports or other generic scientific material.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


CONFIG_VERSION = "deep-clustering-input-representation-v1"
DEFAULT_CONFIG: dict[str, Any] = {
    "version": CONFIG_VERSION,
    "manual_text_max_characters": 8000,
    "structured_confidence_threshold": 0.85,
    "minimum_title_characters": 2,
    "minimum_abstract_characters": 40,
    "minimum_keyword_count": 2,
    "plain_text_chunk_characters": 900,
    "plain_text_selected_chunks": 6,
    "technical_source_weights": {"title": 0.15, "abstract": 0.65, "keywords": 0.20},
    "application_source_weights": {"title": 0.20, "abstract": 0.70, "keywords": 0.10},
    "publication_date_used_for_clustering": False,
}

_SPACE = re.compile(r"[ \t\f\v]+")
_TITLE_LINE = re.compile(
    r"(?im)^\s*(?:【\s*)?(?:标题|题名|title)(?:\s*】)?\s*[:：]\s*(?P<value>[^\r\n]+)"
)
_ABSTRACT_BLOCK = re.compile(
    r"(?ims)^\s*(?:【\s*)?(?:摘要|abstract)(?:\s*】)?\s*[:：]\s*(?P<value>.+?)"
    r"(?=^\s*(?:【\s*)?(?:关键词|关键字|keywords?)(?:\s*】)?\s*[:：]|\Z)"
)
_KEYWORD_BLOCK = re.compile(
    r"(?ims)^\s*(?:【\s*)?(?:关键词|关键字|keywords?)(?:\s*】)?\s*[:：]\s*(?P<value>.+?)"
    r"(?=^\s*(?:【\s*)?(?:正文|引言|introduction|body)(?:\s*】)?\s*[:：]|\Z)"
)

TECHNICAL_CUES = (
    "方法", "模型", "算法", "框架", "机制", "网络", "训练", "实验", "仿真", "优化",
    "method", "model", "algorithm", "framework", "network", "training", "experiment",
    "simulation", "optimization", "finite element", "transformer", "研究设计", "技术路线",
)
APPLICATION_CUES = (
    "应用", "用于", "面向", "场景", "对象", "行业", "环境", "诊断", "检测", "监测", "预测",
    "application", "applied", "scenario", "domain", "industry", "diagnosis", "monitoring",
    "healthcare", "clinical", "agriculture", "industrial", "transport", "manufacturing",
)


def clean_text(value: Any) -> str:
    return _SPACE.sub(" ", str(value or "").replace("\r\n", "\n").replace("\r", "\n")).strip()


def load_input_representation_config(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parents[2] / "config" / "deep_clustering_input_representation_v1.json"
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return config
    if stored.get("version") != CONFIG_VERSION:
        return config
    config.update(stored)
    for key in ("technical_source_weights", "application_source_weights"):
        raw = config.get(key) or {}
        values = {name: max(0.0, float(raw.get(name, 0.0))) for name in ("title", "abstract", "keywords")}
        total = sum(values.values()) or 1.0
        config[key] = {name: value / total for name, value in values.items()}
    return config


def split_keywords(value: Any) -> list[str]:
    values: Sequence[Any]
    if isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = re.split(r"[;,；，、|/\n]+", clean_text(value))
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        term = clean_text(item).strip("-–—:：,，;；。.")
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            result.append(term)
    return result


def parse_labeled_structure(text: str, config: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """Parse explicit Title/Abstract/Keywords labels without inferring content."""
    cfg = dict(config or load_input_representation_config())
    source = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    title_match = _TITLE_LINE.search(source)
    abstract_match = _ABSTRACT_BLOCK.search(source)
    keyword_match = _KEYWORD_BLOCK.search(source)
    if not (title_match and abstract_match and keyword_match):
        return None
    title = clean_text(title_match.group("value"))
    abstract = clean_text(abstract_match.group("value"))
    keywords = split_keywords(keyword_match.group("value"))
    if (
        len(title) < int(cfg["minimum_title_characters"])
        or len(abstract) < int(cfg["minimum_abstract_characters"])
        or len(keywords) < int(cfg["minimum_keyword_count"])
    ):
        return None
    confidence = 0.98
    if confidence < float(cfg["structured_confidence_threshold"]):
        return None
    return {
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "parser": "explicit_label_regex",
        "structure_confidence": confidence,
    }


def resolve_input_representation(source: Mapping[str, Any], *, document_id: str) -> dict[str, Any]:
    """Choose structured weighting only when all three source fields are real."""
    cfg = load_input_representation_config()
    manual_text = clean_text(source.get("text") or source.get("content"))
    if source.get("text") is not None and len(manual_text) > int(cfg["manual_text_max_characters"]):
        raise ValueError(
            f"{document_id} 的 text 清洗后为 {len(manual_text)} 个字符，超过允许的 "
            f"{int(cfg['manual_text_max_characters'])} 个字符。"
        )
    explicit_title = clean_text(
        source.get("title") or source.get("ch_name") or source.get("en_name") or source.get("name")
    )
    explicit_abstract = clean_text(
        source.get("abstract") or source.get("ch_abstract") or source.get("en_abstract")
        or source.get("abstract_text")
    )
    explicit_keywords = split_keywords(source.get("keywords") or source.get("keyword"))
    complete_explicit = (
        len(explicit_title) >= int(cfg["minimum_title_characters"])
        and len(explicit_abstract) >= int(cfg["minimum_abstract_characters"])
        and len(explicit_keywords) >= int(cfg["minimum_keyword_count"])
    )
    parsed = None if complete_explicit else parse_labeled_structure(manual_text, cfg)
    if complete_explicit or parsed:
        fields = parsed or {
            "title": explicit_title,
            "abstract": explicit_abstract,
            "keywords": explicit_keywords,
            "parser": "provided_structured_fields",
            "structure_confidence": 1.0,
        }
        original_text = manual_text or clean_text(source.get("full_text")) or fields["abstract"]
        # Structured mode deliberately represents the three verified fields;
        # body/full text remains available only as source evidence, not as an
        # unweighted fourth semantic field.
        semantic_text = fields["abstract"]
        return {
            "mode": "structured",
            "title": fields["title"],
            "abstract": fields["abstract"],
            "keywords": fields["keywords"],
            "semantic_text": semantic_text,
            "audit": {
                "mode": "structured",
                "parser": fields["parser"],
                "structure_confidence": fields["structure_confidence"],
                "original_text_length": len(original_text),
                "fields_used": ["title", "abstract", "keywords"],
                "publication_date_used_for_clustering": False,
            },
        }
    # No pseudo-title and no fabricated keywords: generic reports use text only.
    semantic_text = (
        manual_text or clean_text(source.get("full_text")) or explicit_abstract
    )
    return {
        "mode": "plain_text",
        "title": explicit_title,
        "abstract": "",
        "keywords": [],
        "semantic_text": semantic_text,
        "audit": {
            "mode": "plain_text",
            "parser": "plain_text_fallback",
            "structure_confidence": 0.0,
            "original_text_length": len(semantic_text),
            "fields_used": ["text"],
            "publication_date_used_for_clustering": False,
        },
    }


def _paragraph_chunks(text: str, maximum: int) -> list[str]:
    paragraphs = [clean_text(item) for item in re.split(r"\n+", str(text or "")) if clean_text(item)]
    if len(paragraphs) <= 1:
        paragraphs = [
            clean_text(item) for item in re.split(r"(?<=[。！？!?；;\.])", clean_text(text))
            if clean_text(item)
        ]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        parts = [paragraph[index:index + maximum] for index in range(0, len(paragraph), maximum)]
        for part in parts:
            candidate = f"{current} {part}".strip()
            if current and len(candidate) > maximum:
                chunks.append(current)
                current = part
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks or [clean_text(text)[:maximum]]


def select_axis_chunks(text: str, axis: str, config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Review all text, then retain bounded source chunks for the selected axis."""
    cfg = dict(config or load_input_representation_config())
    chunks = _paragraph_chunks(text, int(cfg["plain_text_chunk_characters"]))
    cues = TECHNICAL_CUES if axis == "technical" else APPLICATION_CUES
    ranked: list[tuple[float, int, str]] = []
    for index, chunk in enumerate(chunks):
        lowered = chunk.casefold()
        hits = sum(1 for cue in cues if cue.casefold() in lowered)
        adoption = 1.0 if re.search(
            r"(?:采用|提出|构建|设计|用于|面向|应用于|use|employ|propose|apply|target)", lowered
        ) else 0.0
        ranked.append((1.0 + 2.0 * hits + adoption, index, chunk))
    selected = sorted(
        sorted(ranked, key=lambda row: (-row[0], row[1]))[:int(cfg["plain_text_selected_chunks"])],
        key=lambda row: row[1],
    )
    total = sum(row[0] for row in selected) or 1.0
    return [
        {"label": f"text_chunk_{rank + 1}", "source_text": chunk, "weight": score / total}
        for rank, (score, _, chunk) in enumerate(selected)
    ]


def source_groups(paper: Mapping[str, Any], axis: str) -> list[dict[str, Any]]:
    cfg = load_input_representation_config()
    representation = paper.get("input_representation") or {}
    if representation.get("mode") == "structured":
        weights = cfg[f"{axis}_source_weights"]
        values = {
            "title": clean_text(paper.get("title")),
            "abstract": clean_text(paper.get("abstract")),
            "keywords": "；".join(split_keywords(paper.get("keywords"))),
        }
        return [
            {"label": name, "source_text": value, "weight": float(weights[name])}
            for name, value in values.items() if value
        ]
    return select_axis_chunks(str(paper.get("semantic_text") or ""), axis, cfg)
