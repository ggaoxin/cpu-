"""Rule-free semantic cluster-label generation.

The engine deliberately contains no topic catalogue, Gold-label mapping,
domain vocabulary, task-term list, morphology exception list, or examples
copied from evaluation failures.  Label selection depends on source evidence,
BGE embeddings, and fixed mathematical scoring only.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Protocol, Sequence


ENGINE_VERSION = "cluster-label-semantic-only-v10"
SUPPORTED_LANGUAGES = {"auto", "zh", "en"}
_ZH = re.compile(r"[\u3400-\u9fff]")
_EN = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]*")
_SPACE = re.compile(r"\s+")


class Encoder(Protocol):
    def encode(self, texts: Sequence[str]):
        """Return one dense vector per text."""


class LLMClient(Protocol):
    def chat_json(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> Mapping[str, Any]:
        """Return parsed JSON."""


@dataclass(frozen=True)
class PhraseEvidence:
    text: str
    weight: float = 1.0
    frequency: int = 1
    source: str = "deep_clustering"


@dataclass
class ClusterInput:
    cluster_id: str
    phrases: list[PhraseEvidence]
    language: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Candidate:
    label: str
    origin: str
    evidence: list[str]
    source_score: float
    relevance: float = 0.0
    coverage: float = 0.0
    distinctiveness: float = 0.0
    conciseness: float = 0.0
    evidence_diversity: float = 0.0
    total_score: float = 0.0
    rejected_reasons: list[str] = field(default_factory=list)


def _clean(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return _SPACE.sub(" ", text).strip(" \t\r\n,;:，；：。.!?、")


def _language(text: str) -> str:
    zh = len(_ZH.findall(text))
    en = len(_EN.findall(text))
    return "zh" if zh >= max(2, en) else "en"


def _label_length(text: str, language: str) -> int:
    if language == "en":
        return len(_EN.findall(text))
    return len(_ZH.findall(text)) + len(_EN.findall(text))


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_key(text: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]+", " ", _clean(text).casefold()).strip()


def _parse_phrase(value: Any) -> PhraseEvidence | None:
    if isinstance(value, Mapping):
        text = _clean(value.get("text") or value.get("phrase") or value.get("term") or value.get("value"))
        try:
            weight = float(value.get("weight", value.get("score", 1.0)) or 1.0)
        except (TypeError, ValueError):
            weight = 1.0
        try:
            frequency = max(1, int(value.get("frequency", value.get("count", 1)) or 1))
        except (TypeError, ValueError):
            frequency = 1
        source = _clean(value.get("source") or "deep_clustering")
    else:
        text, weight, frequency, source = _clean(value), 1.0, 1, "deep_clustering"
    if not text:
        return None
    return PhraseEvidence(text, max(0.01, weight), frequency, source)


def _parse_cluster(value: Mapping[str, Any], index: int, language_type: str) -> ClusterInput:
    cluster_id = _clean(value.get("cluster_id") or value.get("topic_id") or value.get("id") or f"cluster_{index + 1}")
    raw = (
        value.get("phrases")
        or value.get("representative_phrases")
        or value.get("representative_terms")
        or value.get("terms")
        or []
    )
    if isinstance(raw, str):
        raw = re.split(r"[\n,，;；]+", raw)
    phrases = [parsed for item in raw if (parsed := _parse_phrase(item))]
    if not phrases:
        raise ValueError(f"{cluster_id} 缺少有效的 phrases。")
    requested = str(value.get("language") or language_type or "auto").lower()
    if requested not in SUPPORTED_LANGUAGES:
        raise ValueError(f"{cluster_id} 的 language 必须为 auto、zh 或 en。")
    resolved = _language(" ".join(item.text for item in phrases)) if requested == "auto" else requested
    metadata = {key: item for key, item in value.items() if key not in {
        "cluster_id", "topic_id", "id", "phrases", "representative_phrases", "representative_terms", "terms"
    }}
    return ClusterInput(cluster_id, phrases, resolved, metadata)


class SemanticClusterLabelGenerator:
    """Generate labels with embeddings and evidence, without semantic rules."""

    def __init__(self, *, encoder: Encoder, llm_client: LLMClient | None = None) -> None:
        if encoder is None:
            raise ValueError("semantic-only 模式必须提供编码器。")
        self.encoder = encoder
        self.llm_client = llm_client

    def generate(
        self,
        cluster_phrase_sets: Sequence[Mapping[str, Any]],
        *,
        label_length_limit: int = 12,
        language_type: str = "auto",
        distinctiveness_threshold: float = 0.75,
        candidate_count: int = 5,
    ) -> dict[str, Any]:
        if not cluster_phrase_sets:
            raise ValueError("cluster_phrase_sets 至少包含一个类簇。")
        if language_type not in SUPPORTED_LANGUAGES:
            raise ValueError("language_type 必须为 auto、zh 或 en。")
        if not isinstance(label_length_limit, int) or not 2 <= label_length_limit <= 100:
            raise ValueError("label_length_limit 必须是2到100之间的整数。")
        threshold = float(distinctiveness_threshold)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("distinctiveness_threshold 必须在0到1之间。")
        candidate_count = max(3, min(int(candidate_count), 10))

        clusters = [
            _parse_cluster(value, index, language_type)
            for index, value in enumerate(cluster_phrase_sets)
        ]
        phrase_rows = [
            (cluster.cluster_id, phrase.text)
            for cluster in clusters for phrase in cluster.phrases
        ]
        phrase_vectors = self._encode([text for _, text in phrase_rows])
        vector_by_phrase = {
            row: vector for row, vector in zip(phrase_rows, phrase_vectors)
        }
        centroids = self._cluster_centroids(clusters, vector_by_phrase)

        generated: dict[str, list[Candidate]] = {}
        llm_failures: list[dict[str, str]] = []
        for cluster in clusters:
            candidates = self._local_candidates(
                cluster,
                vector_by_phrase,
                label_length_limit,
            )
            if self.llm_client is not None:
                try:
                    candidates.extend(self._llm_candidates(cluster, label_length_limit))
                except Exception as exc:  # deterministic local fallback
                    llm_failures.append({"cluster_id": cluster.cluster_id, "error": str(exc)[:240]})
            generated[cluster.cluster_id] = self._deduplicate(candidates)

        self._score(
            clusters,
            generated,
            vector_by_phrase,
            centroids,
            label_length_limit,
        )

        labels: list[dict[str, Any]] = []
        optimizations: list[dict[str, Any]] = []
        for cluster in clusters:
            valid = [item for item in generated[cluster.cluster_id] if not item.rejected_reasons]
            if not valid:
                first = cluster.phrases[0]
                valid = [Candidate(first.text, "evidence_fallback", [first.text], 1.0, total_score=0.5)]
            ranked = sorted(valid, key=lambda item: (-item.total_score, -item.relevance, item.label.casefold()))
            winner = ranked[0]
            passed = winner.distinctiveness >= threshold
            optimization = {
                "cluster_id": cluster.cluster_id,
                "before_label": winner.label,
                "after_label": winner.label,
                "changed": False,
                "reason": "纯语义最高分；差异度只报告，不为过阈值替换成窄标签",
                "before_distinctiveness": round(winner.distinctiveness, 6),
                "after_distinctiveness": round(winner.distinctiveness, 6),
                "threshold_passed": passed,
            }
            optimizations.append(optimization)
            alternatives = [item.label for item in ranked[1:candidate_count]]
            labels.append({
                "cluster_id": cluster.cluster_id,
                "label": winner.label,
                "candidate_labels": [winner.label, *alternatives],
                "evidence_terms": winner.evidence,
                "language": cluster.language,
                "confidence": round(winner.total_score, 6),
                "distinctiveness": round(winner.distinctiveness, 6),
                "coverage": round(winner.relevance, 6),
                "evidence_support": round(winner.coverage, 6),
                "generation_method": winner.origin,
                "phrase_count": len(cluster.phrases),
                "optimization": optimization,
                # 关联文献透传（来自 phrase_sets 的 metadata，供弹窗「关联文献」列）
                "linked_document_ids": cluster.metadata.get("linked_document_ids") or [],
            })

        average = lambda key: round(sum(float(item[key]) for item in labels) / len(labels), 6)
        passed_count = sum(bool(item["optimization"]["threshold_passed"]) for item in labels)
        return {
            "labels": labels,
            "generation_report": {
                "engine_version": ENGINE_VERSION,
                "input_type": "cluster_phrase_sets",
                "run_mode": "single_cluster" if len(clusters) == 1 else "batch",
                "cluster_count": len(clusters),
                "generated_label_count": len(labels),
                "language_distribution": dict(sorted(Counter(item.language for item in clusters).items())),
                "parameters": {
                    "label_length_limit": label_length_limit,
                    "language_type": language_type,
                    "distinctiveness_threshold": threshold,
                    "candidate_count": candidate_count,
                    "pair_similarity_lower_bound": 0.35,
                    "pair_similarity_upper_bound": 0.88,
                },
                "stages": [
                    "evidence_normalization",
                    "bge_phrase_encoding",
                    "semantic_centroid_construction",
                    "semantic_candidate_generation",
                    "evidence_coverage_scoring",
                    "cross_cluster_distance_reporting",
                ],
                "topic_library_used": False,
                "semantic_rule_library_used": False,
                "gold_labels_used_in_inference": False,
                "llm_used": self.llm_client is not None,
                "llm_failures": llm_failures,
                "distinctiveness_changes_label": False,
                "average_confidence": average("confidence"),
                "average_distinctiveness": average("distinctiveness"),
                "average_coverage": average("coverage"),
            },
            "label_differentiation_optimization": {
                "threshold": threshold,
                "optimized_count": 0,
                "passed_count": passed_count,
                "failed_count": len(labels) - passed_count,
                "items": optimizations,
            },
        }

    def _encode(self, texts: Sequence[str]):
        import numpy as np

        values = np.asarray(self.encoder.encode(list(texts)), dtype=float)
        if values.ndim != 2 or values.shape[0] != len(texts):
            raise ValueError("编码器返回的向量形状与输入文本数量不一致。")
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        return values / np.maximum(norms, 1e-12)

    def _cluster_centroids(self, clusters, vector_by_phrase):
        import numpy as np

        result = {}
        for cluster in clusters:
            vectors = np.asarray([
                vector_by_phrase[(cluster.cluster_id, phrase.text)]
                for phrase in cluster.phrases
            ])
            weights = np.asarray([
                phrase.weight * math.log1p(phrase.frequency) / math.log2(rank + 2.0)
                for rank, phrase in enumerate(cluster.phrases)
            ], dtype=float)
            centroid = (vectors * weights[:, None]).sum(axis=0) / max(weights.sum(), 1e-12)
            centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-12)
            result[cluster.cluster_id] = centroid
        return result

    def _local_candidates(self, cluster, vector_by_phrase, limit):
        scored = []
        for rank, phrase in enumerate(cluster.phrases):
            source_score = phrase.weight * math.log1p(phrase.frequency) / math.log2(rank + 2.0)
            scored.append((source_score, phrase))
        scored.sort(key=lambda row: (-row[0], row[1].text.casefold()))
        top = scored[:8]
        candidates = [
            Candidate(phrase.text, "extractive_phrase", [phrase.text], source_score)
            for source_score, phrase in top
        ]
        for left_index, (left_score, left) in enumerate(top[:6]):
            left_vector = vector_by_phrase[(cluster.cluster_id, left.text)]
            for right_score, right in top[left_index + 1:6]:
                right_vector = vector_by_phrase[(cluster.cluster_id, right.text)]
                similarity = float(left_vector @ right_vector)
                if not 0.35 <= similarity <= 0.88:
                    continue
                label = (
                    f"{left.text}与{right.text}"
                    if cluster.language == "zh"
                    else f"{left.text} and {right.text}"
                )
                if _label_length(label, cluster.language) <= limit:
                    candidates.append(Candidate(
                        label,
                        "semantic_phrase_pair",
                        [left.text, right.text],
                        (left_score + right_score) / 2.0,
                    ))
        return candidates

    def _llm_candidates(self, cluster, limit):
        evidence = [item.text for item in cluster.phrases[:20]]
        system = (
            "Generate short cluster-label candidates that are entailed by the supplied evidence phrases. "
            "Do not use an external taxonomy or assign documents to clusters. Each candidate must cite "
            "two or more exact input evidence phrases. Prefer a concise noun phrase that covers the shared "
            "meaning of the cluster. Return JSON only: "
            '{"candidates":[{"label":"...","evidence_phrases":["...","..."]}]}.'
        )
        payload = {
            "cluster_id": cluster.cluster_id,
            "language": cluster.language,
            "label_length_limit": limit,
            "evidence_phrases": evidence,
        }
        response = self.llm_client.chat_json(
            system,
            json.dumps(payload, ensure_ascii=False),
            temperature=0.0,
            timeout=60.0,
            max_tokens=800,
        )
        raw = response.get("data", response) if isinstance(response, Mapping) else {}
        values = raw.get("candidates", []) if isinstance(raw, Mapping) else []
        evidence_by_key = {_normalize_key(value): value for value in evidence}
        result = []
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, Mapping):
                continue
            label = _clean(value.get("label"))
            cited = [
                evidence_by_key[key]
                for item in value.get("evidence_phrases", [])
                if (key := _normalize_key(item)) in evidence_by_key
            ]
            candidate = Candidate(label, "llm_evidence_candidate", list(dict.fromkeys(cited)), 0.0)
            if len(candidate.evidence) < 2:
                candidate.rejected_reasons.append("llm_candidate_needs_two_exact_evidence_phrases")
            result.append(candidate)
        return result

    @staticmethod
    def _deduplicate(candidates):
        result = {}
        for candidate in candidates:
            candidate.label = _clean(candidate.label)
            key = _normalize_key(candidate.label)
            if not key:
                continue
            existing = result.get(key)
            if existing is None or candidate.source_score > existing.source_score:
                result[key] = candidate
        return list(result.values())

    def _score(self, clusters, generated, vector_by_phrase, centroids, limit):
        candidate_rows = [
            (cluster.cluster_id, candidate.label)
            for cluster in clusters for candidate in generated[cluster.cluster_id]
        ]
        vectors = self._encode([label for _, label in candidate_rows])
        candidate_vectors = {row: vector for row, vector in zip(candidate_rows, vectors)}
        cluster_by_id = {cluster.cluster_id: cluster for cluster in clusters}
        for cluster_id, label in candidate_rows:
            cluster = cluster_by_id[cluster_id]
            candidate = next(item for item in generated[cluster_id] if item.label == label)
            length = _label_length(label, cluster.language)
            if length < 2:
                candidate.rejected_reasons.append("label_too_short")
            if length > limit:
                candidate.rejected_reasons.append("label_exceeds_requested_length_limit")
            if not candidate.evidence:
                candidate.rejected_reasons.append("candidate_has_no_input_evidence")
            vector = candidate_vectors[(cluster_id, label)]
            own_similarity = float(vector @ centroids[cluster_id])
            cross_similarity = max(
                (float(vector @ centroid) for other_id, centroid in centroids.items() if other_id != cluster_id),
                default=-1.0,
            )
            candidate.relevance = _clip((own_similarity + 1.0) / 2.0)
            candidate.distinctiveness = _clip(1.0 / (1.0 + math.exp(-6.0 * (own_similarity - cross_similarity))))

            phrase_weights = [
                phrase.weight * math.log1p(phrase.frequency) / math.log2(rank + 2.0)
                for rank, phrase in enumerate(cluster.phrases)
            ]
            phrase_similarities = [
                _clip((float(vector @ vector_by_phrase[(cluster_id, phrase.text)]) + 1.0) / 2.0)
                for phrase in cluster.phrases
            ]
            candidate.coverage = sum(
                weight * similarity for weight, similarity in zip(phrase_weights, phrase_similarities)
            ) / max(sum(phrase_weights), 1e-12)

            max_source = max(
                (item.source_score for item in generated[cluster_id]),
                default=1.0,
            ) or 1.0
            source = _clip(candidate.source_score / max_source)
            if candidate.origin == "llm_evidence_candidate":
                evidence_scores = []
                for value in candidate.evidence:
                    index = next(
                        (rank for rank, phrase in enumerate(cluster.phrases) if phrase.text == value),
                        None,
                    )
                    if index is not None:
                        phrase = cluster.phrases[index]
                        evidence_scores.append(
                            phrase.weight * math.log1p(phrase.frequency) / math.log2(index + 2.0)
                        )
                source = _clip(sum(evidence_scores) / max(len(evidence_scores), 1) / max_source)

            if len(candidate.evidence) >= 2:
                evidence_vectors = [vector_by_phrase[(cluster_id, value)] for value in candidate.evidence]
                pair_similarity = min(
                    float(evidence_vectors[left] @ evidence_vectors[right])
                    for left in range(len(evidence_vectors))
                    for right in range(left + 1, len(evidence_vectors))
                )
                candidate.evidence_diversity = _clip((0.88 - pair_similarity) / 0.53)
            candidate.conciseness = self._conciseness(length, cluster.language)
            candidate.total_score = _clip(
                0.38 * candidate.relevance
                + 0.24 * candidate.coverage
                + 0.16 * source
                + 0.10 * candidate.distinctiveness
                + 0.08 * candidate.conciseness
                + 0.04 * candidate.evidence_diversity
            )

    @staticmethod
    def _conciseness(length: int, language: str) -> float:
        low, high = ((4, 12) if language == "zh" else (2, 8))
        if low <= length <= high:
            return 1.0
        if length < low:
            return _clip(length / low)
        return _clip(high / max(length, 1))


