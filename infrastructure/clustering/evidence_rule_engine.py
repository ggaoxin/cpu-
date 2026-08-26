"""Open-vocabulary evidence rules for dual-axis literature clustering.

Rules in this module extract auditable concepts from source text. They never
return cluster IDs, class labels, a requested K, or final membership. The
resulting concept features may be blended with BGE features with a bounded
weight, providing a conservative lower-bound fallback when LLM extraction is
missing or unclear.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.preprocessing import normalize


RULE_ENGINE_VERSION = "dual-axis-evidence-rules-v1"
FUSION_CONFIG_VERSION = "dual-axis-rule-fusion-v1"
AXES = ("technical", "application")
FACETS = {
    "technical": {"method", "model", "measurement", "analysis", "study_design"},
    "application": {"domain", "object", "problem", "task", "environment"},
}

DEFAULT_FUSION_CONFIG: dict[str, Any] = {
    "version": FUSION_CONFIG_VERSION,
    "rule_mode": "audit",
    "technical_rule_mode": "audit",
    "application_rule_mode": "audit",
    "technical_rule_weight": 0.12,
    "technical_rule_policy": "fallback_only",
    "application_rule_weight": 0.16,
    "application_rule_policy": "fallback_only",
    "technical_axis_extraction": "local",
    "application_axis_extraction": "llm_verified",
}
_SPACE = re.compile(r"\s+")
_LATIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.\-/ ]*$")
_NEGATION = re.compile(
    r"(?:未采用|没有采用|不采用|并未使用|未使用|不是使用|无需|排除|"
    r"not\s+(?:use|using|employ|adopt)|without\s+(?:using|employing)|"
    r"was\s+not\s+used)",
    re.IGNORECASE,
)
_RELATED_WORK = re.compile(
    r"(?:相关工作|已有研究|既往研究|文献\s*\[|他人提出|"
    r"related\s+work|previous\s+(?:studies|work)|prior\s+work|"
    r"has\s+been\s+(?:widely\s+)?used)",
    re.IGNORECASE,
)
_TECHNICAL_ADOPTION = re.compile(
    r"(?:本文|本研究|我们|提出|采用|使用|利用|构建|建立|设计|训练|开发|实施|"
    r"we\s+(?:propose|use|employ|adopt|develop|design|train|construct)|"
    r"this\s+(?:study|paper|work)\s+(?:proposes|uses|employs|adopts|develops)|"
    r"was\s+(?:used|employed|adopted|developed))",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    return _SPACE.sub(" ", str(value or "")).strip()


def _unique(values: Sequence[str], maximum: int = 12) -> list[str]:
    output, seen = [], set()
    for value in values:
        cleaned = _text(value).strip(" ,;，；。:：-—\"'")
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
        if len(output) >= maximum:
            break
    return output


def _pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    if _LATIN.fullmatch(term):
        return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _contains_any(text: str, values: Sequence[str]) -> bool:
    return any(_pattern(str(value)).search(text) for value in values if str(value).strip())


def _context(text: str, start: int, end: int, radius: int) -> str:
    return _text(text[max(0, start - radius):min(len(text), end + radius)])


def _clause_context(text: str, start: int, end: int, radius: int) -> str:
    """Keep adoption/negation checks in the clause containing the match."""
    separators = "。！？!?;；\n"
    left_candidates = [text.rfind(mark, max(0, start - radius), start) for mark in separators]
    left = max(left_candidates, default=-1) + 1
    right_candidates = [
        position for mark in separators
        if (position := text.find(mark, end, min(len(text), end + radius))) >= 0
    ]
    right = min(right_candidates, default=min(len(text), end + radius))
    return _text(text[left:right])


@dataclass(frozen=True)
class RuleHit:
    document_id: str
    rule_id: str
    axis: str
    facet: str
    canonical_zh: str
    canonical_en: str
    matched_alias: str
    evidence: str
    field: str
    confidence: float
    weight: float
    derivation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "axis": self.axis,
            "facet": self.facet,
            "canonical_zh": self.canonical_zh,
            "canonical_en": self.canonical_en,
            "matched_alias": self.matched_alias,
            "evidence": self.evidence,
            "source_field": self.field,
            "confidence": round(self.confidence, 6),
            "feature_weight": round(self.weight, 6),
            "derivation": self.derivation,
        }


@dataclass
class RuleEvidenceBatch:
    document_ids: list[str]
    hits_by_document: list[list[RuleHit]]
    rule_version: str
    rule_sha256: str

    def evidence(self, index: int, axis: str, maximum: int = 3) -> list[str]:
        return _unique([
            hit.evidence for hit in self.hits_by_document[index] if hit.axis == axis
        ], maximum)

    def application_facets(self, index: int, language: str) -> dict[str, list[str]]:
        result = {name: [] for name in FACETS["application"]}
        for hit in self.hits_by_document[index]:
            if hit.axis != "application":
                continue
            value = hit.canonical_zh if language == "zh" else hit.canonical_en
            result[hit.facet].append(value)
        normalized = {name: _unique(values, 8) for name, values in result.items()}
        # A single broad domain/object word is lexical recognition, not enough
        # evidence to infer an implicit application scenario. Requiring two
        # distinct facets prevents rules from behaving like a hard classifier.
        if sum(bool(values) for values in normalized.values()) < 2:
            return {name: [] for name in normalized}
        return normalized

    def application_context_strength(self, index: int) -> dict[str, Any]:
        hit_facets = {
            hit.facet for hit in self.hits_by_document[index]
            if hit.axis == "application"
        }
        return {
            "distinct_facet_count": len(hit_facets),
            "facets": sorted(hit_facets),
            "eligible_for_semantic_expansion": len(hit_facets) >= 2,
        }

    def technical_terms(self, index: int, language: str) -> list[str]:
        return _unique([
            hit.canonical_zh if language == "zh" else hit.canonical_en
            for hit in self.hits_by_document[index] if hit.axis == "technical"
        ], 10)

    def document_audit(self, index: int) -> dict[str, Any]:
        hits = self.hits_by_document[index]
        return {
            "document_id": self.document_ids[index],
            "technical_hit_count": sum(hit.axis == "technical" for hit in hits),
            "application_hit_count": sum(hit.axis == "application" for hit in hits),
            "application_context_strength": self.application_context_strength(index),
            "hits": [hit.as_dict() for hit in hits],
        }

    def summary(self) -> dict[str, Any]:
        technical = [sum(hit.axis == "technical" for hit in hits) for hits in self.hits_by_document]
        application = [sum(hit.axis == "application" for hit in hits) for hits in self.hits_by_document]
        n = max(len(self.document_ids), 1)
        return {
            "engine_version": RULE_ENGINE_VERSION,
            "rule_version": self.rule_version,
            "rule_sha256": self.rule_sha256,
            "topic_library_used": False,
            "rules_assign_cluster_membership": False,
            "rule_id_affinity_used": False,
            "semantic_space_effect": "evidence_phrase_expansion_then_bge_reencoding",
            "document_count": len(self.document_ids),
            "technical_covered_documents": sum(value > 0 for value in technical),
            "application_covered_documents": sum(value > 0 for value in application),
            "technical_coverage": round(sum(value > 0 for value in technical) / n, 6),
            "application_coverage": round(sum(value > 0 for value in application) / n, 6),
            "technical_hit_count": sum(technical),
            "application_hit_count": sum(application),
        }


class EvidenceRuleEngine:
    """Load, validate and apply evidence-only dual-axis rules."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw.decode("utf-8"))
        self.version = str(payload.get("version") or "")
        if self.version != RULE_ENGINE_VERSION:
            raise ValueError(f"Unsupported evidence-rule version: {self.version}")
        if payload.get("can_assign_cluster_membership") is not False:
            raise ValueError("Evidence rules must explicitly forbid cluster assignment.")
        self.context_radius = max(40, min(int(payload.get("context_radius", 180)), 500))
        self.field_weights = {
            str(key): float(value)
            for key, value in (payload.get("field_weights") or {}).items()
        }
        self.rules = self._validate_rules(payload.get("rules") or [])

    @staticmethod
    def _validate_rules(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        result, seen = [], set()
        for raw in rows:
            rule = dict(raw)
            rule_id = str(rule.get("id") or "").strip()
            axis = str(rule.get("axis") or "").strip()
            facet = str(rule.get("facet") or "").strip()
            if not rule_id or rule_id in seen:
                raise ValueError(f"Missing or duplicate rule id: {rule_id}")
            if axis not in AXES or facet not in FACETS[axis]:
                raise ValueError(f"Invalid axis/facet for {rule_id}: {axis}/{facet}")
            if any(key in rule for key in ("cluster_id", "class_id", "gold_label", "target_k")):
                raise ValueError(f"Rule {rule_id} contains forbidden membership fields.")
            aliases = _unique([str(value) for value in rule.get("aliases") or []], 50)
            conditional = rule.get("conditional_aliases") or []
            if not aliases and not conditional:
                raise ValueError(f"Rule {rule_id} has no aliases.")
            rule["aliases"] = aliases
            rule["conditional_aliases"] = conditional
            rule["weight"] = float(np.clip(float(rule.get("weight", 1.0)), 0.05, 2.0))
            seen.add(rule_id)
            result.append(rule)
        return result

    def _segments(self, paper: Mapping[str, Any]) -> list[tuple[str, str]]:
        return [
            ("title", _text(paper.get("title"))),
            ("keywords", "；".join(_unique([str(v) for v in paper.get("keywords") or []], 30))),
            ("abstract", _text(paper.get("abstract"))),
            ("full_text", _text(paper.get("full_text"))[:50000]),
        ]

    def _candidate_hit(
        self,
        paper: Mapping[str, Any],
        rule: Mapping[str, Any],
        *,
        alias: str,
        requires_any: Sequence[str],
        excludes_any: Sequence[str],
        derivation: str,
    ) -> RuleHit | None:
        for field, source in self._segments(paper):
            if not source:
                continue
            for match in _pattern(alias).finditer(source):
                context = _clause_context(source, match.start(), match.end(), self.context_radius)
                if requires_any and not _contains_any(context, requires_any):
                    continue
                if excludes_any and _contains_any(context, excludes_any):
                    continue
                if _NEGATION.search(context):
                    continue
                if rule["axis"] == "technical" and field not in {"title", "keywords"}:
                    if _RELATED_WORK.search(context):
                        continue
                    if bool(rule.get("require_adoption_cue", True)) and not _TECHNICAL_ADOPTION.search(context):
                        continue
                field_weight = float(self.field_weights.get(field, 0.60))
                confidence = field_weight
                if requires_any:
                    confidence += 0.06
                if field in {"title", "keywords"}:
                    confidence += 0.08
                confidence = float(np.clip(confidence, 0.0, 0.99))
                evidence = context if len(context) <= 360 else context[:360]
                return RuleHit(
                    document_id=str(paper.get("document_id") or ""),
                    rule_id=str(rule["id"]),
                    axis=str(rule["axis"]),
                    facet=str(rule["facet"]),
                    canonical_zh=str(rule.get("canonical_zh") or rule["id"]),
                    canonical_en=str(rule.get("canonical_en") or rule["id"]),
                    matched_alias=match.group(0),
                    evidence=evidence,
                    field=field,
                    confidence=confidence,
                    weight=float(rule["weight"]),
                    derivation=derivation,
                )
        return None

    def match(self, paper: Mapping[str, Any]) -> list[RuleHit]:
        hits: list[RuleHit] = []
        for rule in self.rules:
            hit = None
            excludes = [str(value) for value in rule.get("exclude_any") or []]
            for alias in rule["aliases"]:
                hit = self._candidate_hit(
                    paper, rule, alias=alias, requires_any=(), excludes_any=excludes,
                    derivation="explicit_alias",
                )
                if hit:
                    break
            if hit is None:
                for conditional in rule["conditional_aliases"]:
                    alias = str(conditional.get("term") or "").strip()
                    if not alias:
                        continue
                    hit = self._candidate_hit(
                        paper,
                        rule,
                        alias=alias,
                        requires_any=[str(v) for v in conditional.get("requires_any") or []],
                        excludes_any=excludes + [str(v) for v in conditional.get("exclude_any") or []],
                        derivation="contextual_alias",
                    )
                    if hit:
                        break
            if hit:
                hits.append(hit)
        return hits

    def apply(self, papers: Sequence[Mapping[str, Any]]) -> RuleEvidenceBatch:
        hits_by_document = [self.match(paper) for paper in papers]
        return RuleEvidenceBatch(
            document_ids=[str(paper.get("document_id") or "") for paper in papers],
            hits_by_document=hits_by_document,
            rule_version=self.version,
            rule_sha256=self.sha256,
        )


def load_rule_fusion_config(path: Path | None = None) -> dict[str, Any]:
    """Load bounded production defaults without exposing arbitrary weights."""
    if path is None:
        path = Path(__file__).resolve().parents[2] / "config" / "dual_axis_rule_fusion_v1.json"
    config = dict(DEFAULT_FUSION_CONFIG)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return config
    if stored.get("version") != FUSION_CONFIG_VERSION:
        return config
    if stored.get("rule_mode") in {"off", "audit", "enhance"}:
        config["rule_mode"] = stored["rule_mode"]
    for axis in AXES:
        mode_key = f"{axis}_rule_mode"
        extraction_key = f"{axis}_axis_extraction"
        if stored.get(mode_key) in {"off", "audit", "enhance"}:
            config[mode_key] = stored[mode_key]
        if stored.get(extraction_key) in {"local", "llm_verified"}:
            config[extraction_key] = stored[extraction_key]
    if stored.get("application_rule_policy") in {"fallback_only", "all"}:
        config["application_rule_policy"] = stored["application_rule_policy"]
    if stored.get("technical_rule_policy") in {"fallback_only", "all"}:
        config["technical_rule_policy"] = stored["technical_rule_policy"]
    config["technical_rule_weight"] = float(np.clip(
        float(stored.get("technical_rule_weight", config["technical_rule_weight"])), 0.0, 0.40
    ))
    config["application_rule_weight"] = float(np.clip(
        float(stored.get("application_rule_weight", config["application_rule_weight"])), 0.0, 0.35
    ))
    return config


def input_evidence_profile(paper: Mapping[str, Any]) -> dict[str, Any]:
    """Describe input completeness without looking at labels or clusters.

    Short title/abstract records benefit most from conservative semantic
    expansion.  Full-text records already carry considerably more evidence, so
    an expansion must have less influence.  The multiplier is deliberately
    axis-independent and is fixed before an experiment is run.
    """
    abstract_length = len(_text(paper.get("abstract")))
    full_text_length = len(_text(paper.get("full_text")))
    keyword_count = len(paper.get("keywords") or [])
    if full_text_length >= 1500:
        level, multiplier = "full_text", 0.45
    elif abstract_length >= 500 and keyword_count >= 3:
        level, multiplier = "rich_text_record", 0.72
    elif abstract_length >= 220 or keyword_count >= 2:
        level, multiplier = "standard_text_record", 0.88
    else:
        level, multiplier = "brief_text_record", 1.0
    return {
        "level": level,
        "abstract_characters": abstract_length,
        "full_text_characters": full_text_length,
        "keyword_count": keyword_count,
        "enhancement_multiplier": multiplier,
    }


def adaptive_semantic_weights(
    papers: Sequence[Mapping[str, Any]],
    base_weight: float,
    *,
    maximum: float,
    active_mask: Sequence[bool] | None = None,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Return bounded per-document weights derived only from input richness."""
    profiles = [input_evidence_profile(paper) for paper in papers]
    active = (
        np.ones(len(papers), dtype=np.float32)
        if active_mask is None
        else np.asarray(active_mask, dtype=np.float32)
    )
    if active.shape != (len(papers),):
        raise ValueError("active_mask must contain one value per document")
    bounded = float(np.clip(base_weight, 0.0, maximum))
    weights = np.asarray([
        bounded * float(profile["enhancement_multiplier"])
        for profile in profiles
    ], dtype=np.float32) * active
    return weights, profiles


def augment_axis_views(
    views: Sequence[str],
    papers: Sequence[Mapping[str, Any]],
    batch: RuleEvidenceBatch,
    *,
    axis: str,
    active_mask: Sequence[bool] | None = None,
) -> list[str]:
    """Append human-readable inferred phrases before BGE encoding.

    The appended phrases describe source-grounded meaning. Rule IDs and rule
    feature columns are deliberately absent from the returned text.
    """
    output = []
    for index, (view, paper) in enumerate(zip(views, papers)):
        active = active_mask is None or bool(active_mask[index])
        language = str(paper.get("language") or "en")
        if axis == "technical":
            terms = batch.technical_terms(index, language) if active else []
            header = "规则补充的技术表述" if language == "zh" else "rule-supported technical expression"
        else:
            facets = batch.application_facets(index, language) if active else {}
            facet_names = {
                "zh": {"domain": "应用领域", "object": "服务对象", "problem": "现实问题", "task": "应用任务", "environment": "使用环境"},
                "en": {"domain": "domain", "object": "target object", "problem": "real-world problem", "task": "application task", "environment": "environment"},
            }["zh" if language == "zh" else "en"]
            terms = [
                f"{facet_names[name]}：{'、'.join(values)}"
                for name, values in facets.items() if values
            ]
            header = "规则补充的隐含应用场景表述" if language == "zh" else "rule-supported implicit application expression"
        supplement = "；".join(terms)
        output.append(_text(f"{view} {header}：{supplement}")[:3000] if supplement else str(view))
    return output


def blend_sparse_semantic_features(
    base: csr_matrix,
    augmented: csr_matrix,
    *,
    rule_weight: float | Sequence[float],
    active_mask: Sequence[bool] | None = None,
) -> csr_matrix:
    """Blend original and rule-expanded BGE sparse semantic vectors."""
    base = normalize(base, norm="l2", copy=True).tocsr()
    augmented = normalize(augmented, norm="l2", copy=True).tocsr()
    if augmented.shape != base.shape:
        raise ValueError("Original and rule-expanded BGE matrices must have equal shape.")
    active = np.ones(base.shape[0], dtype=np.float32) if active_mask is None else np.asarray(active_mask, dtype=np.float32)
    if active.shape != (base.shape[0],):
        raise ValueError("active_mask must contain one value per document")
    if np.isscalar(rule_weight):
        weights = np.full(base.shape[0], float(rule_weight), dtype=np.float32)
    else:
        weights = np.asarray(rule_weight, dtype=np.float32)
        if weights.shape != (base.shape[0],):
            raise ValueError("rule_weight sequence must contain one value per document")
    weights = np.clip(weights, 0.0, 0.40) * active
    if not np.any(weights > 0):
        return base
    base_scale = np.sqrt(1.0 - weights)
    augmented_scale = np.sqrt(weights)
    fused = hstack([
        base.multiply(base_scale[:, None]),
        augmented.multiply(augmented_scale[:, None]),
    ], format="csr", dtype=np.float32)
    return normalize(fused, norm="l2", copy=False).tocsr()


# Compatibility alias for older experimental imports. The second matrix must
# now be a BGE encoding of rule-expanded text, never a rule-ID one-hot matrix.
fuse_sparse_rule_features = blend_sparse_semantic_features


def blend_dense_semantic_representations(
    base_matrix: np.ndarray,
    augmented_matrix: np.ndarray,
    base_affinity: np.ndarray,
    augmented_affinity: np.ndarray,
    *,
    rule_weight: float | Sequence[float],
    active_mask: Sequence[bool],
) -> tuple[np.ndarray, np.ndarray]:
    """Blend two BGE spaces without injecting rule IDs into similarity."""
    base = np.asarray(base_matrix, dtype=np.float32)
    augmented = np.asarray(augmented_matrix, dtype=np.float32)
    if base.shape[0] != augmented.shape[0] or base.shape[0] != len(active_mask):
        raise ValueError("Semantic representations and active mask must align.")
    active = np.asarray(active_mask, dtype=np.float32)
    if np.isscalar(rule_weight):
        weights = np.full(base.shape[0], float(rule_weight), dtype=np.float32)
    else:
        weights = np.asarray(rule_weight, dtype=np.float32)
    if weights.shape != (base.shape[0],):
        raise ValueError("rule_weight must contain one value per document")
    weights = np.clip(weights, 0.0, 0.35) * active
    base_scale = np.sqrt(1.0 - weights)
    augmented_scale = np.sqrt(weights)
    fused = np.concatenate([
        base * base_scale[:, None],
        augmented * augmented_scale[:, None],
    ], axis=1)
    fused = fused / np.maximum(np.linalg.norm(fused, axis=1, keepdims=True), 1e-12)
    pair_weight = np.sqrt(np.outer(weights, weights))
    affinity = (
        (1.0 - pair_weight) * np.asarray(base_affinity, dtype=np.float32)
        + pair_weight * np.asarray(augmented_affinity, dtype=np.float32)
    )
    np.fill_diagonal(affinity, 1.0)
    return fused.astype(np.float32), np.clip(affinity, 0.0, 1.0).astype(np.float32)


def merge_application_rule_facets(
    facets: Sequence[Mapping[str, Sequence[str]]],
    papers: Sequence[Mapping[str, Any]],
    batch: RuleEvidenceBatch,
    *,
    fill_only: bool = True,
    active_mask: Sequence[bool] | None = None,
) -> list[dict[str, list[str]]]:
    """Fill missing application facets while preserving LLM-verified values."""
    output = []
    for index, (source, paper) in enumerate(zip(facets, papers)):
        row = {name: _unique([str(v) for v in source.get(name, [])], 8) for name in (
            "domain", "object", "problem", "task", "environment", "general"
        )}
        additions = (
            batch.application_facets(index, str(paper.get("language") or "en"))
            if active_mask is None or bool(active_mask[index])
            else {name: [] for name in FACETS["application"]}
        )
        for name, values in additions.items():
            if not fill_only or not row[name]:
                row[name] = _unique(row[name] + values, 8)
        output.append(row)
    return output
