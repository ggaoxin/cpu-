"""Evidence-grounded, topic-library-free cluster label generation.

The engine consumes the phrase sets produced by deep clustering.  It never
assigns documents to clusters and it never maps a cluster to a predefined
topic catalogue.  A language model may propose extra candidates, but every
candidate is reranked against the supplied cluster evidence and the engine has
a deterministic extractive fallback.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import json
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping, Protocol, Sequence


ENGINE_VERSION = "cluster-label-evidence-v2"
SUPPORTED_LANGUAGES = {"auto", "zh", "en"}

_SPACE = re.compile(r"\s+")
_SPLIT = re.compile(r"[;,；，、|/\n]+")
_EN_TOKEN = re.compile(r"[a-z][a-z0-9+#.-]*", re.I)
_ZH_CHAR = re.compile(r"[\u3400-\u9fff]")
_TRIM_PUNCT = " \t\r\n-–—_:：,，;；。.!?！？()（）[]【】{}<>《》'\""

_GENERIC_ZH = {
    "研究", "分析", "方法", "模型", "算法", "技术", "系统", "应用", "问题",
    "结果", "数据", "实验", "相关研究", "方法研究", "技术研究", "综合研究",
    "科技文献", "文献", "主题", "类簇", "聚类",
}
_GENERIC_EN = {
    "study", "research", "analysis", "method", "methods", "model", "models",
    "approach", "approaches", "system", "systems", "application", "applications",
    "result", "results", "data", "experiment", "experiments", "paper", "papers",
    "topic", "cluster", "clustering",
}
_EN_STOP = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "with",
    "by", "from", "using", "based", "via", "toward", "towards", "under",
}
_ZH_JOINERS = ("及", "与", "和", "的", "基于", "面向", "用于")
_EN_JOINERS = {"and", "or", "for", "of", "based", "using", "via", "with"}

# These are language-level research actions, not domain topics.  They let the
# deterministic fallback preserve a method/task word that appears in one
# evidence phrase while combining it with a more representative phrase.
_ZH_TASK_TERMS = (
    "分析", "预测", "识别", "检测", "诊断", "定位", "评价", "评估", "优化",
    "调度", "模拟", "仿真", "建模", "生成", "分类", "聚类", "控制", "表征",
    "合成", "监测", "管理", "治疗", "开发", "发展", "保护", "存储", "转化",
)
_EN_TASK_TERMS = (
    "analysis", "prediction", "classification", "detection", "diagnosis",
    "segmentation", "simulation", "modeling", "optimisation", "optimization",
    "control", "synthesis", "characterization", "management", "treatment",
    "storage", "conservation", "development", "review", "assessment", "evaluation",
    "monitoring", "forecasting", "model",
)


class Encoder(Protocol):
    def encode(self, texts: list[str]) -> Any:
        """Return a row-normalized matrix-like value."""


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
    language: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Candidate:
    label: str
    origin: str
    evidence: list[str]
    base_score: float = 0.0
    relevance: float = 0.0
    evidence_support: float = 0.0
    distinctiveness: float = 0.0
    conciseness: float = 0.0
    total_score: float = 0.0
    rejected_reasons: list[str] = field(default_factory=list)


def _clean(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return _SPACE.sub(" ", text).strip(_TRIM_PUNCT)


def _language(text: str) -> str:
    zh_count = len(_ZH_CHAR.findall(text))
    en_count = len(_EN_TOKEN.findall(text))
    return "zh" if zh_count >= max(2, en_count) else "en"


def _singular(token: str) -> str:
    token = token.casefold()
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("ses"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str, language: str) -> tuple[str, ...]:
    normalized = _clean(text).casefold()
    if language == "en":
        return tuple(
            _singular(token) for token in _EN_TOKEN.findall(normalized)
            if token.casefold() not in _EN_STOP
        )
    # Character bigrams make Chinese comparison useful without requiring a
    # tokenizer or a domain dictionary.
    chars = "".join(_ZH_CHAR.findall(normalized))
    if len(chars) <= 2:
        return (chars,) if chars else ()
    return tuple(chars[index:index + 2] for index in range(len(chars) - 1))


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _cosine_counts(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    lnorm = math.sqrt(sum(value * value for value in left.values()))
    rnorm = math.sqrt(sum(value * value for value in right.values()))
    return float(dot / max(lnorm * rnorm, 1e-12))


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _label_length(label: str, language: str) -> int:
    if language == "en":
        return len(_EN_TOKEN.findall(label))
    # Latin abbreviations embedded in a Chinese label count as one unit each.
    return len(_ZH_CHAR.findall(label)) + len(_EN_TOKEN.findall(label))


def _is_generic(label: str, language: str) -> bool:
    value = _clean(label).casefold()
    return value in (_GENERIC_EN if language == "en" else _GENERIC_ZH)


def _normalize_key(label: str, language: str) -> str:
    if language == "en":
        return " ".join(_tokens(label, language))
    zh = "".join(_ZH_CHAR.findall(label))
    latin = " ".join(_singular(token) for token in _EN_TOKEN.findall(label.casefold()))
    return f"{zh}|{latin}"


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
    return PhraseEvidence(text=text, weight=max(0.01, weight), frequency=frequency, source=source)


def _parse_cluster(value: Mapping[str, Any], index: int, language: str) -> ClusterInput:
    cluster_id = _clean(value.get("cluster_id") or value.get("topic_id") or value.get("id") or f"cluster_{index + 1}")
    raw_phrases = (
        value.get("phrases") or value.get("representative_phrases")
        or value.get("representative_terms") or value.get("terms") or []
    )
    if isinstance(raw_phrases, str):
        raw_phrases = _SPLIT.split(raw_phrases)
    phrases = [parsed for item in raw_phrases if (parsed := _parse_phrase(item))]
    if not phrases:
        raise ValueError(f"{cluster_id} 缺少有效的 phrases。")
    explicit_language = str(value.get("language") or language or "auto").strip().lower()
    if explicit_language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"{cluster_id} 的 language 必须为 auto、zh 或 en。")
    resolved = _language(" ".join(item.text for item in phrases)) if explicit_language == "auto" else explicit_language
    metadata = {key: item for key, item in value.items() if key not in {
        "cluster_id", "topic_id", "id", "phrases", "representative_phrases", "representative_terms", "terms"
    }}
    return ClusterInput(cluster_id=cluster_id, phrases=phrases, language=resolved, metadata=metadata)


class ClusterLabelGenerator:
    """Generate concise labels from deep-clustering phrase sets."""

    def __init__(self, *, encoder: Encoder | None = None, llm_client: LLMClient | None = None) -> None:
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
        try:
            threshold = float(distinctiveness_threshold)
        except (TypeError, ValueError) as exc:
            raise ValueError("distinctiveness_threshold 必须是0到1之间的数值。") from exc
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("distinctiveness_threshold 必须在0到1之间。")
        candidate_count = max(3, min(int(candidate_count), 10))

        clusters = [
            _parse_cluster(value, index, language_type)
            for index, value in enumerate(cluster_phrase_sets)
        ]
        phrase_df = self._phrase_document_frequency(clusters)
        token_df = self._token_document_frequency(clusters)
        generated: dict[str, list[Candidate]] = {}
        rejected_count = 0
        llm_failures: list[dict[str, str]] = []

        for cluster in clusters:
            candidates = self._extractive_candidates(
                cluster, phrase_df, token_df, len(clusters), label_length_limit
            )
            if self.llm_client is not None:
                try:
                    candidates.extend(self._llm_candidates(cluster, label_length_limit))
                except Exception as exc:  # noqa: BLE001 - deterministic fallback is intentional
                    llm_failures.append({"cluster_id": cluster.cluster_id, "error": str(exc)[:240]})
            candidates = self._deduplicate(candidates, cluster.language)
            rejected_count += sum(bool(item.rejected_reasons) for item in candidates)
            generated[cluster.cluster_id] = candidates

        self._score_candidates(clusters, generated, token_df, label_length_limit)
        selected, optimization = self._global_select(
            clusters, generated, threshold=threshold, candidate_count=candidate_count
        )

        labels: list[dict[str, Any]] = []
        for cluster in clusters:
            winner = selected[cluster.cluster_id]
            ranked = sorted(
                (item for item in generated[cluster.cluster_id] if not item.rejected_reasons),
                key=lambda item: (-item.total_score, -item.distinctiveness, item.label.casefold()),
            )
            alternatives = [item.label for item in ranked if item.label != winner.label][:candidate_count - 1]
            opt = optimization[cluster.cluster_id]
            labels.append({
                "cluster_id": cluster.cluster_id,
                "label": winner.label,
                "candidate_labels": [winner.label, *alternatives],
                "evidence_terms": winner.evidence[:8],
                "language": cluster.language,
                "confidence": round(winner.total_score, 6),
                "distinctiveness": round(winner.distinctiveness, 6),
                "coverage": round(winner.relevance, 6),
                "evidence_support": round(winner.evidence_support, 6),
                "generation_method": winner.origin,
                "phrase_count": len(cluster.phrases),
                "optimization": opt,
            })

        average = lambda key: round(sum(float(item[key]) for item in labels) / len(labels), 6)
        language_counts = Counter(item.language for item in clusters)
        optimized_count = sum(bool(item["optimization"]["changed"]) for item in labels)
        pass_count = sum(float(item["distinctiveness"]) >= threshold for item in labels)
        return {
            "labels": labels,
            "generation_report": {
                "engine_version": ENGINE_VERSION,
                "input_type": "cluster_phrase_sets",
                "run_mode": "single_cluster" if len(clusters) == 1 else "batch",
                "cluster_count": len(clusters),
                "generated_label_count": len(labels),
                "language_distribution": dict(sorted(language_counts.items())),
                "parameters": {
                    "label_length_limit": label_length_limit,
                    "language_type": language_type,
                    "distinctiveness_threshold": threshold,
                    "candidate_count": candidate_count,
                },
                "stages": [
                    "phrase_cleaning_and_normalization",
                    "frequency_ngram_and_cooccurrence_candidates",
                    "evidence_grounded_candidate_scoring",
                    "cross_cluster_differentiation",
                    "global_label_selection",
                ],
                "topic_library_used": False,
                "llm_used": self.llm_client is not None,
                "llm_assigns_cluster_membership": False,
                "llm_failures": llm_failures,
                "rejected_candidate_count": rejected_count,
                "optimized_label_count": optimized_count,
                "distinctiveness_pass_count": pass_count,
                "average_confidence": average("confidence"),
                "average_distinctiveness": average("distinctiveness"),
                "average_coverage": average("coverage"),
            },
            "label_differentiation_optimization": {
                "threshold": threshold,
                "optimized_count": optimized_count,
                "passed_count": pass_count,
                "failed_count": len(labels) - pass_count,
                "items": [item["optimization"] for item in labels],
            },
        }

    @staticmethod
    def _phrase_document_frequency(clusters: Sequence[ClusterInput]) -> Counter[str]:
        result: Counter[str] = Counter()
        for cluster in clusters:
            result.update({_clean(item.text).casefold() for item in cluster.phrases})
        return result

    @staticmethod
    def _token_document_frequency(clusters: Sequence[ClusterInput]) -> Counter[str]:
        result: Counter[str] = Counter()
        for cluster in clusters:
            present: set[str] = set()
            for phrase in cluster.phrases:
                present.update(_tokens(phrase.text, cluster.language))
            result.update(present)
        return result

    def _extractive_candidates(
        self,
        cluster: ClusterInput,
        phrase_df: Counter[str],
        token_df: Counter[str],
        cluster_count: int,
        limit: int,
    ) -> list[Candidate]:
        scored: list[tuple[float, PhraseEvidence]] = []
        for rank, phrase in enumerate(cluster.phrases):
            exact_df = phrase_df[_clean(phrase.text).casefold()]
            idf = math.log((cluster_count + 1.0) / (exact_df + 0.5)) + 1.0
            rank_weight = 1.0 / math.log2(rank + 2.0)
            informativeness = self._informativeness(phrase.text, cluster.language, token_df, cluster_count)
            score = phrase.weight * math.log1p(phrase.frequency) * idf * rank_weight * (0.7 + 0.3 * informativeness)
            scored.append((score, phrase))
        scored.sort(key=lambda row: (-row[0], row[1].text.casefold()))

        candidates: list[Candidate] = []
        top = scored[:12]
        score_by_phrase = {_clean(phrase.text).casefold(): score for score, phrase in scored}
        for score, phrase in top:
            candidates.append(Candidate(
                label=phrase.text,
                origin="extractive_phrase",
                evidence=[phrase.text],
                base_score=score,
            ))
            for part in self._split_phrase(phrase.text, cluster.language):
                if part != phrase.text:
                    candidates.append(Candidate(
                        label=part,
                        origin="extractive_subphrase",
                        evidence=[phrase.text],
                        base_score=score * 0.88,
                    ))

        # Association candidates combine two high-value, non-redundant phrases.
        # Both compact and readable conjunction variants are retained.  The
        # reranker, rather than a hard-coded topic rule, decides which wording
        # best represents the complete cluster profile.
        for left_index, (left_score, left) in enumerate(top[:7]):
            for right_score, right in top[left_index + 1:8]:
                if _jaccard(_tokens(left.text, cluster.language), _tokens(right.text, cluster.language)) >= 0.58:
                    continue
                for combined in self._compose_variants(left.text, right.text, cluster.language, limit):
                    candidates.append(Candidate(
                        label=combined,
                        origin="evidence_phrase_fusion",
                        evidence=[left.text, right.text],
                        base_score=(left_score + right_score) / 2.0,
                    ))

        # Preserve a task/action word from a separate evidence phrase.  This
        # is useful when deep clustering emits e.g. a method phrase and a
        # prediction/analysis phrase independently.  Only terms literally
        # present in the input are eligible, so this remains evidence-grounded.
        task_evidence = self._task_evidence(cluster)
        for score, phrase in top[:8]:
            for task, evidence_phrase in task_evidence[:6]:
                if task.casefold() in phrase.text.casefold():
                    continue
                value = self._append_task(phrase.text, task, cluster.language, limit)
                if value:
                    task_score = score_by_phrase.get(evidence_phrase.casefold(), 0.0)
                    candidates.append(Candidate(
                        label=value,
                        origin="evidence_task_fusion",
                        evidence=[phrase.text, evidence_phrase],
                        base_score=(score + task_score) / 2.0,
                    ))
        return candidates

    @staticmethod
    def _task_evidence(cluster: ClusterInput) -> list[tuple[str, str]]:
        terms = _EN_TASK_TERMS if cluster.language == "en" else _ZH_TASK_TERMS
        found: list[tuple[str, str]] = []
        for phrase in cluster.phrases[:8]:
            lowered = phrase.text.casefold()
            for term in terms:
                if cluster.language == "zh" and term == "调度" and "协调度" in phrase.text:
                    continue
                if term.casefold() in lowered:
                    row = (term, phrase.text)
                    if row not in found:
                        found.append(row)
        return found

    @staticmethod
    def _append_task(base: str, task: str, language: str, limit: int) -> str:
        base, task = _clean(base), _clean(task)
        if not base or not task:
            return ""
        if language == "en":
            value = f"{base} {task}"
        else:
            value = f"{base}{task}"
        return value if _label_length(value, language) <= limit else ""

    @staticmethod
    def _informativeness(
        phrase: str,
        language: str,
        token_df: Counter[str],
        cluster_count: int,
    ) -> float:
        values = [math.log((cluster_count + 1.0) / (token_df[token] + 0.5)) + 1.0 for token in _tokens(phrase, language)]
        if not values:
            return 0.0
        maximum = math.log((cluster_count + 1.0) / 0.5) + 1.0
        return _clip(sum(values) / len(values) / maximum)

    @staticmethod
    def _split_phrase(text: str, language: str) -> list[str]:
        values = [_clean(value) for value in _SPLIT.split(text) if _clean(value)]
        if language == "en":
            more: list[str] = []
            for value in values:
                parts = re.split(r"\s+(?:and|or|with|via)\s+", value, flags=re.I)
                more.extend(_clean(item) for item in parts if _clean(item))
            values.extend(more)
        return list(dict.fromkeys(values))

    @staticmethod
    def _combine(left: str, right: str, language: str, limit: int) -> str:
        left, right = _clean(left), _clean(right)
        if not left or not right:
            return ""
        if left.casefold() in right.casefold():
            value = right
        elif right.casefold() in left.casefold():
            value = left
        elif language == "en":
            left_words = left.split()
            right_words = right.split()
            overlap = 0
            for size in range(min(len(left_words), len(right_words)), 0, -1):
                if [v.casefold() for v in left_words[-size:]] == [v.casefold() for v in right_words[:size]]:
                    overlap = size
                    break
            value = " ".join(left_words + right_words[overlap:])
        else:
            overlap = 0
            for size in range(min(len(left), len(right)), 0, -1):
                if left[-size:] == right[:size]:
                    overlap = size
                    break
            value = left + right[overlap:]
        return value if _label_length(value, language) <= limit else ""

    @classmethod
    def _compose_variants(
        cls,
        left: str,
        right: str,
        language: str,
        limit: int,
    ) -> list[str]:
        """Create readable evidence fusions without consulting a topic catalogue."""
        left, right = _clean(left), _clean(right)
        if not left or not right:
            return []
        values: list[str] = []

        def add(value: str) -> None:
            value = _clean(value)
            if value and _label_length(value, language) <= limit and value not in values:
                values.append(value)

        if language == "en":
            left_tokens = set(_tokens(left, "en"))
            right_tokens = set(_tokens(right, "en"))
            if left_tokens <= right_tokens or right_tokens <= left_tokens:
                return []
            if len(left_tokens) == len(right_tokens) == 1:
                left_word, right_word = next(iter(left_tokens)), next(iter(right_tokens))
                shared_prefix = 0
                for size in range(min(len(left_word), len(right_word)), 3, -1):
                    if left_word[:size] == right_word[:size]:
                        shared_prefix = size
                        break
                shared_suffix = 0
                for size in range(min(len(left_word), len(right_word)), 3, -1):
                    if left_word[-size:] == right_word[-size:]:
                        shared_suffix = size
                        break
                if max(shared_prefix, shared_suffix) / max(min(len(left_word), len(right_word)), 1) >= 0.6:
                    return []
            add(cls._combine(left, right, language, limit))
            add(f"{left} and {right}")
            add(f"{right} and {left}")
            return values

        add(cls._combine(left, right, language, limit))
        add(f"{left}与{right}")
        add(f"{right}与{left}")

        # Factor shared Chinese wording.  Examples of the generic operation:
        # “故障定位 + 故障诊断” -> “故障诊断与定位”;
        # “优化调度 + 鲁棒优化” -> “鲁棒优化与调度”.
        prefix_size = 0
        for size in range(min(len(left), len(right)), 1, -1):
            if left[:size] == right[:size]:
                prefix_size = size
                break
        if prefix_size:
            prefix = left[:prefix_size]
            left_tail, right_tail = left[prefix_size:], right[prefix_size:]
            if left_tail and right_tail:
                add(f"{prefix}{left_tail}与{right_tail}")
                add(f"{prefix}{right_tail}与{left_tail}")

        suffix_size = 0
        for size in range(min(len(left), len(right)), 1, -1):
            if left[-size:] == right[-size:]:
                suffix_size = size
                break
        if suffix_size:
            suffix = left[-suffix_size:]
            left_head, right_head = left[:-suffix_size], right[:-suffix_size]
            if left_head and right_head:
                add(f"{left_head}与{right_head}{suffix}")
                add(f"{right_head}与{left_head}{suffix}")

        shared = ""
        for size in range(min(len(left), len(right)), 1, -1):
            match = next(
                (left[start:start + size] for start in range(len(left) - size + 1)
                 if left[start:start + size] in right),
                "",
            )
            if match:
                shared = match
                break
        if shared:
            if left.startswith(shared) and right.endswith(shared):
                add(f"{right}{left[len(shared):]}")
                add(f"{right}与{left[len(shared):]}")
            if right.startswith(shared) and left.endswith(shared):
                add(f"{left}{right[len(shared):]}")
                add(f"{left}与{right[len(shared):]}")
        return values

    def _llm_candidates(self, cluster: ClusterInput, limit: int) -> list[Candidate]:
        evidence = [item.text for item in cluster.phrases[:20]]
        prompt = {
            "cluster_id": cluster.cluster_id,
            "language": cluster.language,
            "label_length_limit": limit,
            "phrases": evidence,
        }
        system = (
            "你是类簇标签生成器。输入仅包含深度聚类输出的类簇短语。"
            "不得使用预设主题库，不得为类簇重新分类。优先概括类簇中两个或以上的主导概念，"
            "不要机械拼接同义词、词形变体、单篇文献专名或过窄对象。"
            "允许使用由多条输入短语共同支持的保守上位概念，但不得引入无法由输入证据解释的主题。"
            "生成3到5个语法完整、简洁且彼此不同的候选标签；每个候选必须列出2到5条直接依据的输入短语。"
            "中文长度按汉字、英文长度按单词计算。只返回JSON："
            '{"candidates":[{"label":"...","evidence_phrases":["..."]}]}。'
        )
        response = self.llm_client.chat_json(
            system,
            json.dumps(prompt, ensure_ascii=False),
            temperature=0.0,
            timeout=60.0,
            max_tokens=800,
        )
        raw = response.get("data", response) if isinstance(response, Mapping) else {}
        values = raw.get("candidates", []) if isinstance(raw, Mapping) else []
        result: list[Candidate] = []
        evidence_keys = {_clean(item).casefold() for item in evidence}
        for value in values if isinstance(values, list) else []:
            if not isinstance(value, Mapping):
                continue
            label = _clean(value.get("label"))
            cited = [_clean(item) for item in value.get("evidence_phrases", []) if _clean(item)]
            verified = [item for item in cited if item.casefold() in evidence_keys]
            candidate = Candidate(label=label, origin="llm_evidence_candidate", evidence=verified)
            if not verified:
                candidate.rejected_reasons.append("llm_candidate_has_no_verifiable_evidence")
            result.append(candidate)
        return result

    @staticmethod
    def _deduplicate(candidates: Sequence[Candidate], language: str) -> list[Candidate]:
        result: dict[str, Candidate] = {}
        for candidate in candidates:
            candidate.label = _clean(candidate.label)
            key = _normalize_key(candidate.label, language)
            if not key:
                continue
            existing = result.get(key)
            if existing is None or candidate.base_score > existing.base_score:
                result[key] = candidate
            elif candidate.evidence:
                existing.evidence = list(dict.fromkeys([*existing.evidence, *candidate.evidence]))
        return list(result.values())

    def _score_candidates(
        self,
        clusters: Sequence[ClusterInput],
        generated: Mapping[str, list[Candidate]],
        token_df: Counter[str],
        label_length_limit: int,
    ) -> None:
        cluster_profiles: dict[str, Counter[str]] = {}
        for cluster in clusters:
            profile: Counter[str] = Counter()
            for phrase in cluster.phrases:
                for token in _tokens(phrase.text, cluster.language):
                    profile[token] += phrase.weight * math.log1p(phrase.frequency)
            cluster_profiles[cluster.cluster_id] = profile

        semantic_scores = self._semantic_scores(clusters, generated)
        for cluster in clusters:
            own = cluster_profiles[cluster.cluster_id]
            other_profiles = [value for key, value in cluster_profiles.items() if key != cluster.cluster_id]
            max_base = max((item.base_score for item in generated[cluster.cluster_id]), default=1.0) or 1.0
            phrase_salience = {
                phrase.text: (
                    phrase.weight * math.log1p(phrase.frequency)
                    / math.log2(rank + 2.0)
                )
                for rank, phrase in enumerate(cluster.phrases)
            }
            max_phrase_salience = max(phrase_salience.values(), default=1.0) or 1.0
            for candidate in generated[cluster.cluster_id]:
                length = _label_length(candidate.label, cluster.language)
                if length < 2:
                    candidate.rejected_reasons.append("label_too_short")
                if length > label_length_limit:
                    candidate.rejected_reasons.append("label_exceeds_requested_length_limit")
                if _is_generic(candidate.label, cluster.language):
                    candidate.rejected_reasons.append("overly_generic_label")

                ctokens = _tokens(candidate.label, cluster.language)
                cprofile = Counter(ctokens)
                lexical_relevance = _cosine_counts(cprofile, own)
                cross = max((_cosine_counts(cprofile, other) for other in other_profiles), default=0.0)
                lexical_distinctiveness = _clip(1.0 - 0.78 * cross + 0.22 * lexical_relevance)
                phrase_support = max(
                    (_jaccard(ctokens, _tokens(item.text, cluster.language)) for item in cluster.phrases),
                    default=0.0,
                )
                evidence_breadth = min(len(set(candidate.evidence)), 3) / 3.0
                evidence_support = _clip(0.55 * phrase_support + 0.45 * evidence_breadth)
                semantic = semantic_scores.get((cluster.cluster_id, candidate.label))
                if semantic is not None:
                    relevance, distinctiveness, semantic_breadth = semantic
                    candidate.relevance = _clip(0.70 * relevance + 0.30 * lexical_relevance)
                    candidate.distinctiveness = _clip(0.75 * distinctiveness + 0.25 * lexical_distinctiveness)
                    candidate.evidence_support = _clip(0.65 * evidence_support + 0.35 * relevance)
                    evidence_breadth = _clip(0.60 * evidence_breadth + 0.40 * semantic_breadth)
                else:
                    candidate.relevance = _clip(0.60 * lexical_relevance + 0.40 * phrase_support)
                    candidate.distinctiveness = lexical_distinctiveness
                    candidate.evidence_support = evidence_support
                candidate.conciseness = self._conciseness(length, cluster.language)
                if candidate.origin == "llm_evidence_candidate":
                    cited_salience = [
                        phrase_salience[value] for value in candidate.evidence
                        if value in phrase_salience
                    ]
                    base = _clip(
                        (sum(cited_salience) / len(cited_salience)) / max_phrase_salience
                    ) if cited_salience else 0.0
                else:
                    base = _clip(candidate.base_score / max_base)
                readability = self._readability(candidate)
                # A usable cluster label normally summarizes more than one
                # representative phrase.  Source salience remains important so
                # a rare named entity cannot displace the cluster's central
                # phrases merely because it is distinctive.
                candidate.total_score = _clip(
                    0.27 * candidate.relevance
                    + 0.10 * candidate.distinctiveness
                    + 0.14 * candidate.evidence_support
                    + 0.18 * evidence_breadth
                    + 0.19 * base
                    + 0.05 * candidate.conciseness
                    + 0.07 * readability
                )

    def _semantic_scores(
        self,
        clusters: Sequence[ClusterInput],
        generated: Mapping[str, list[Candidate]],
    ) -> dict[tuple[str, str], tuple[float, float, float]]:
        if self.encoder is None:
            return {}
        profile_texts = ["；".join(item.text for item in cluster.phrases[:20]) for cluster in clusters]
        candidate_rows = [
            (cluster.cluster_id, candidate.label)
            for cluster in clusters for candidate in generated[cluster.cluster_id]
        ]
        if not candidate_rows:
            return {}
        try:
            evidence_rows = list(dict.fromkeys(
                (cluster.cluster_id, phrase.text)
                for cluster in clusters for phrase in cluster.phrases[:20]
            ))
            vectors = self.encoder.encode(
                profile_texts
                + [row[1] for row in candidate_rows]
                + [row[1] for row in evidence_rows]
            )
            import numpy as np  # Optional dependency only when an encoder is supplied.

            values = np.asarray(vectors, dtype=float)
            norms = np.linalg.norm(values, axis=1, keepdims=True)
            values = values / np.maximum(norms, 1e-12)
            profiles = values[:len(clusters)]
            candidate_start = len(clusters)
            evidence_start = candidate_start + len(candidate_rows)
            candidates = values[candidate_start:evidence_start]
            evidence_vectors = {
                row: vector for row, vector in zip(evidence_rows, values[evidence_start:])
            }
            cluster_index = {cluster.cluster_id: index for index, cluster in enumerate(clusters)}
            candidate_lookup = {
                (cluster.cluster_id, candidate.label): candidate
                for cluster in clusters for candidate in generated[cluster.cluster_id]
            }
            result: dict[tuple[str, str], tuple[float, float, float]] = {}
            for row, vector in zip(candidate_rows, candidates):
                own_index = cluster_index[row[0]]
                scores = profiles @ vector
                own = _clip((float(scores[own_index]) + 1.0) / 2.0)
                cross = max((float(value) for index, value in enumerate(scores) if index != own_index), default=-1.0)
                margin = float(scores[own_index]) - cross
                # Calibrate cosine margin to a 0..1 engineering confidence.
                # A raw margin around 0.18 is already meaningful for BGE-M3
                # cluster profiles; the sigmoid keeps 0.75 as a useful default
                # instead of making it practically unreachable.
                distinctiveness = _clip(1.0 / (1.0 + math.exp(-6.0 * margin)))
                candidate = candidate_lookup[row]
                cited_vectors = [
                    evidence_vectors[(row[0], evidence)]
                    for evidence in dict.fromkeys(candidate.evidence)
                    if (row[0], evidence) in evidence_vectors
                ]
                if len(cited_vectors) < 2:
                    semantic_breadth = 0.25
                else:
                    minimum_similarity = min(
                        float(cited_vectors[left] @ cited_vectors[right])
                        for left in range(len(cited_vectors))
                        for right in range(left + 1, len(cited_vectors))
                    )
                    semantic_breadth = _clip((1.0 - minimum_similarity) / 0.55)
                result[row] = (own, distinctiveness, semantic_breadth)
            return result
        except Exception:
            return {}

    @staticmethod
    def _conciseness(length: int, language: str) -> float:
        ideal_low, ideal_high = ((4, 12) if language == "zh" else (2, 8))
        if ideal_low <= length <= ideal_high:
            return 1.0
        if length < ideal_low:
            return _clip(length / ideal_low)
        return _clip(ideal_high / max(length, 1))

    @staticmethod
    def _readability(candidate: Candidate) -> float:
        lowered = candidate.label.casefold()
        if _ZH_CHAR.search(candidate.label) and _EN_TOKEN.search(candidate.label):
            return 0.55 if "与" in candidate.label else 0.72
        if "与" in candidate.label or "及" in candidate.label or " and " in lowered:
            return 1.0
        if candidate.origin == "extractive_phrase":
            return 0.92
        if candidate.origin in {"evidence_task_fusion", "llm_evidence_candidate"}:
            return 0.90
        return 0.72

    def _global_select(
        self,
        clusters: Sequence[ClusterInput],
        generated: Mapping[str, list[Candidate]],
        *,
        threshold: float,
        candidate_count: int,
    ) -> tuple[dict[str, Candidate], dict[str, dict[str, Any]]]:
        ranked: dict[str, list[Candidate]] = {}
        for cluster in clusters:
            valid = [item for item in generated[cluster.cluster_id] if not item.rejected_reasons]
            if not valid:
                fallback = Candidate(
                    label=cluster.phrases[0].text,
                    origin="forced_evidence_fallback",
                    evidence=[cluster.phrases[0].text],
                    relevance=0.5,
                    evidence_support=1.0,
                    distinctiveness=0.5,
                    conciseness=0.5,
                    total_score=0.5,
                )
                valid = [fallback]
            ranked[cluster.cluster_id] = sorted(
                valid,
                key=lambda item: (-item.total_score, -item.distinctiveness, item.label.casefold()),
            )[:max(candidate_count * 3, 10)]

        order = sorted(
            clusters,
            key=lambda cluster: (-ranked[cluster.cluster_id][0].total_score, cluster.cluster_id),
        )
        selected: dict[str, Candidate] = {}
        optimization: dict[str, dict[str, Any]] = {}
        for cluster in order:
            options = ranked[cluster.cluster_id]
            initial = options[0]
            chosen = initial
            reason = "最高综合评分候选"
            quality_floor = initial.total_score * 0.98
            for option in options:
                similarity = max(
                    (
                        _jaccard(
                            _tokens(option.label, cluster.language),
                            _tokens(existing.label, cluster.language),
                        )
                        for existing in selected.values()
                    ),
                    default=0.0,
                )
                # A higher user threshold demands a higher per-label
                # distinctiveness score and a lower collision with labels that
                # have already been selected.
                collision_limit = max(0.12, 1.0 - threshold + 0.18)
                if (
                    option.total_score >= quality_floor
                    and option.relevance >= initial.relevance - 0.01
                    and option.evidence_support >= initial.evidence_support - 0.03
                    and option.base_score >= initial.base_score * 0.65
                    and option.distinctiveness >= threshold
                    and similarity <= collision_limit
                ):
                    chosen = option
                    reason = "满足类簇间差异阈值且综合评分最高"
                    break
            selected[cluster.cluster_id] = chosen
            optimization[cluster.cluster_id] = {
                "cluster_id": cluster.cluster_id,
                "before_label": initial.label,
                "after_label": chosen.label,
                "changed": initial.label != chosen.label,
                "reason": reason,
                "before_distinctiveness": round(initial.distinctiveness, 6),
                "after_distinctiveness": round(chosen.distinctiveness, 6),
                "threshold_passed": chosen.distinctiveness >= threshold,
            }
        return selected, optimization


def generate_cluster_labels(
    cluster_phrase_sets: Sequence[Mapping[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience entry point using the deterministic local engine."""
    return ClusterLabelGenerator().generate(cluster_phrase_sets, **kwargs)
