"""Data-driven dual-axis clustering for scientific literature.

The grouping decision is deliberately independent of a predefined topic library
and of any large-language-model service.  A configured LLM may rename clusters
afterwards, but it never changes membership or quality metrics.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

from infrastructure.clustering.input_representation import (
    resolve_input_representation,
    split_keywords,
)


TECHNICAL_CUES = (
    "方法", "模型", "算法", "框架", "机制", "网络", "架构", "训练", "优化", "估计",
    "回归", "仿真", "实验", "编码", "特征", "注意力", "聚类", "分类", "检测", "预测",
    "method", "model", "algorithm", "framework", "architecture", "network", "training",
    "optimization", "regression", "simulation", "embedding", "encoder", "attention",
    "clustering", "classification", "detection", "prediction", "transformer", "bert",
    "systematic review", "meta-analysis", "meta analysis", "cohort", "retrospective",
    "prospective", "cross-sectional", "case-control", "randomized", "randomised",
    "controlled trial", "finite element", "molecular dynamics", "first-principles",
    "density functional", "研究设计", "系统综述", "元分析", "队列研究", "回顾性研究",
    "前瞻性研究", "横断面研究", "病例对照", "随机对照", "空间计量", "空间杜宾",
    "鲁棒优化", "有限元", "第一性原理", "密度泛函",
)
STUDY_DESIGN_CUES = (
    "systematic review", "meta-analysis", "meta analysis", "cohort",
    "retrospective", "prospective", "cross-sectional", "case-control",
    "randomized", "randomised", "controlled trial", "case series",
    "系统综述", "元分析", "队列研究", "回顾性研究", "前瞻性研究",
    "横断面研究", "病例对照", "随机对照", "病例系列",
)
APPLICATION_CUES = (
    "应用", "用于", "面向", "场景", "领域", "任务", "对象", "行业", "环境", "系统",
    "医疗", "农业", "工业", "电力", "交通", "城市", "教育", "金融", "制造", "临床",
    "application", "applied", "scenario", "domain", "task", "industry", "healthcare",
    "clinical", "agriculture", "industrial", "power", "transport", "urban", "education",
    "finance", "manufacturing",
)
GENERIC_TERMS = {
    "研究", "分析", "方法", "模型", "结果", "技术", "系统", "应用", "问题", "数据",
    "实验", "本文", "提出", "基于", "采用", "通过", "实现", "文献", "领域", "场景",
    "research", "analysis", "method", "model", "result", "results", "system", "data",
    "based", "using", "study", "paper", "approach", "application", "applications",
}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _keywords(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = re.split(r"[;,；，|/\n]+", _clean_text(value))
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        term = _clean_text(item).strip("-–—:：,，;；。.")
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            result.append(term)
    return result


def _year(value: Any) -> int | None:
    if isinstance(value, (int, np.integer)) and 1900 <= int(value) <= 2100:
        return int(value)
    match = re.search(r"(?:19|20)\d{2}", _clean_text(value))
    if match:
        parsed = int(match.group(0))
        return parsed if 1900 <= parsed <= 2100 else None
    return None


def normalize_papers(items: Sequence[dict[str, Any] | str]) -> list[dict[str, Any]]:
    """Normalize Vue ``id + publication_date + text`` and optional paper fields."""
    papers: list[dict[str, Any]] = []
    skipped: list[str] = []
    for index, item in enumerate(items):
        source = item if isinstance(item, dict) else {"text": str(item or "")}
        published_at = (
            source.get("published_at") or source.get("publication_date")
            or source.get("publication_year") or source.get("year") or source.get("date")
        )
        document_id = _clean_text(
            source.get("document_id") or source.get("id") or source.get("input_id")
        ) or f"D{index + 1:02d}"
        representation = resolve_input_representation(source, document_id=document_id)
        semantic_text = _clean_text(representation["semantic_text"])
        if not semantic_text:
            logging.getLogger(__name__).warning(
                "文档 %s 文本为空（mineru 未提取到文本或输入为空），跳过该文档", document_id)
            skipped.append(document_id)
            continue
        extracted_title = _clean_text(representation["title"])
        display_title = extracted_title or document_id
        semantic_title = extracted_title if representation["mode"] == "structured" else ""
        abstract = _clean_text(representation["abstract"])
        terms = split_keywords(representation["keywords"])
        full_text = _clean_text(source.get("full_text"))
        papers.append({
            "document_id": document_id,
            "title": display_title,
            "semantic_title": semantic_title,
            "abstract": abstract,
            "full_text": full_text,
            "semantic_text": semantic_text,
            "keywords": terms,
            "published_at": published_at,
            "publication_year": _year(published_at),
            "language": source.get("language") or source.get("lang") or _language(semantic_title + semantic_text),
            "input_representation": representation["audit"],
        })
    if skipped:
        logging.getLogger(__name__).warning(
            "normalize_papers 跳过 %d 篇空文本文档：%s", len(skipped), skipped)
    if not papers:
        raise ValueError("所有文档文本均为空（mineru 未提取到任何文本，请检查文件是否为扫描件或图片型 PDF），无法聚类。")
    return papers


def _language(text: str) -> str:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if chinese > latin * 0.2:
        return "zh"
    return "en" if latin else "unknown"


def _sentences(text: str) -> list[str]:
    return [
        _clean_text(part)
        for part in re.split(r"(?<=[。！？!?;；])\s*|(?<=[.!?])\s*(?=[A-Z])", text)
        if _clean_text(part)
    ]


def _cue_snippet(sentence: str, cues: Sequence[str], *, radius: int = 150) -> str:
    """Return compact evidence around the first axis cue in a sentence."""
    low = sentence.casefold()
    positions = [low.find(cue) for cue in cues if cue in low]
    if not positions:
        return sentence[: radius * 2]
    position = min(value for value in positions if value >= 0)
    return sentence[max(0, position - radius): position + radius]


def _view_text(paper: dict[str, Any], axis: str) -> tuple[str, list[str]]:
    """Build an auditable local technical-route or application-scenario view."""
    title = paper.get("semantic_title") or ""
    keywords = paper["keywords"]
    sentences = _sentences(paper.get("semantic_text") or paper.get("abstract") or "")
    cues = TECHNICAL_CUES if axis == "technical" else APPLICATION_CUES
    cue_keywords = [
        keyword for keyword in keywords
        if any(cue in keyword.casefold() for cue in cues)
    ]
    title_and_keywords = f"{title} {' '.join(keywords)}".casefold()
    explicit_cues = [cue for cue in cues if cue in title_and_keywords]
    study_design_cues = [cue for cue in STUDY_DESIGN_CUES if cue in title_and_keywords]
    ranked: list[tuple[float, int, str]] = []
    for position, sentence in enumerate(sentences):
        low = sentence.casefold()
        cue_hits = sum(1 for cue in cues if cue in low)
        method_bonus = 0.0
        if axis == "technical" and re.search(r"(?:采用|提出|构建|设计|训练|利用|develop|propose|use|employ)", low):
            method_bonus = 1.0
        if axis == "application" and re.search(r"(?:用于|面向|服务|解决|应用于|apply|target|for the)", low):
            method_bonus = 1.0
        ranked.append((cue_hits * 2.0 + method_bonus + min(len(sentence), 220) / 500.0, position, sentence))
    selected = sorted(sorted(ranked, reverse=True)[:4], key=lambda row: row[1])
    evidence_threshold = 1.5 if axis == "technical" else 0.25
    evidence = [row[2] for row in selected if row[0] > evidence_threshold]
    if not evidence:
        evidence = sentences[:3]
    keyword_text = "；".join(keywords)
    focus_terms = list(dict.fromkeys(
        study_design_cues if axis == "technical" and study_design_cues
        else cue_keywords + explicit_cues
    ))
    focus_text = "；".join(focus_terms)
    if axis == "technical":
        header = "科学文献的技术方法、算法模型与研究设计 / technical methodology and study design"
    else:
        header = "科学文献的应用领域、研究对象与应用场景 / application domain and studied object"
    # Focus terms are deliberately repeated once to make the selected semantic
    # axis dominate a general-purpose embedding.  Every term comes from the
    # document itself and is never mapped to a predefined topic or cluster ID.
    if axis == "technical" and study_design_cues:
        # Explicit study-design phrases are already a complete technical-axis
        # description.  Keeping disease/object text here would reintroduce the
        # application axis and reduce separability.
        parts = (header, focus_text, focus_text, focus_text)
    elif axis == "technical" and focus_text:
        # Do not let disease/domain words dominate a method-oriented request.
        # The fallback below still supports unseen methods when no explicit
        # technical cue can be extracted locally.
        compact_evidence = " ".join(_cue_snippet(item, cues) for item in evidence[:3])
        parts = (header, focus_text, focus_text, focus_text, compact_evidence)
    else:
        parts = (header, focus_text, focus_text, focus_text, title, keyword_text, " ".join(evidence))
    view = " ".join(part for part in parts if part)
    return view[:2400], evidence


def build_dual_views(papers: Sequence[dict[str, Any]]) -> tuple[list[str], list[str], list[list[str]], list[list[str]]]:
    technical: list[str] = []
    application: list[str] = []
    technical_evidence: list[list[str]] = []
    application_evidence: list[list[str]] = []
    for paper in papers:
        tech, tech_evidence = _view_text(paper, "technical")
        app, app_evidence = _view_text(paper, "application")
        technical.append(tech)
        application.append(app)
        technical_evidence.append(tech_evidence)
        application_evidence.append(app_evidence)
    return technical, application, technical_evidence, application_evidence


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def _agglomerative(matrix: np.ndarray, k: int) -> np.ndarray:
    kwargs = {"n_clusters": k, "linkage": "average"}
    try:
        return AgglomerativeClustering(metric="cosine", **kwargs).fit_predict(matrix)
    except TypeError:  # scikit-learn < 1.2
        return AgglomerativeClustering(affinity="cosine", **kwargs).fit_predict(matrix)


def _agglomerative_threshold(matrix: np.ndarray, similarity_threshold: float) -> np.ndarray:
    kwargs = {
        "n_clusters": None,
        "linkage": "average",
        "distance_threshold": 1.0 - float(np.clip(similarity_threshold, 0.0, 1.0)),
    }
    try:
        return AgglomerativeClustering(metric="cosine", **kwargs).fit_predict(matrix)
    except TypeError:  # scikit-learn < 1.2
        return AgglomerativeClustering(affinity="cosine", **kwargs).fit_predict(matrix)


def _run_hdbscan(matrix: np.ndarray, min_cluster_size: int) -> tuple[np.ndarray, str, list[str]]:
    warnings: list[str] = []
    try:
        from sklearn.cluster import HDBSCAN  # type: ignore[attr-defined]

        labels = HDBSCAN(
            min_cluster_size=max(2, min(min_cluster_size, len(matrix))),
            min_samples=1,
            metric="euclidean",
        ).fit_predict(matrix)
        return labels, "hdbscan", warnings
    except (ImportError, AttributeError):
        try:
            import hdbscan  # type: ignore[import-not-found]

            labels = hdbscan.HDBSCAN(
                min_cluster_size=max(2, min(min_cluster_size, len(matrix))),
                min_samples=1,
                metric="euclidean",
            ).fit_predict(matrix)
            return labels, "hdbscan", warnings
        except ImportError:
            k = max(2, min(len(matrix) - 1, round(math.sqrt(len(matrix)))))
            warnings.append("HDBSCAN dependency is unavailable; agglomerative clustering was used.")
            return _agglomerative(matrix, k), "agglomerative_fallback", warnings


def _safe_silhouette(matrix: np.ndarray, labels: np.ndarray) -> float | None:
    mask = labels >= 0
    clean = labels[mask]
    if mask.sum() < 3 or len(set(clean.tolist())) < 2 or len(set(clean.tolist())) >= mask.sum():
        return None
    return float(silhouette_score(matrix[mask], clean, metric="cosine"))


def _stability(matrix: np.ndarray, labels: np.ndarray, runner: Callable[[np.ndarray], np.ndarray], seed: int) -> float | None:
    if len(set(labels[labels >= 0].tolist())) < 2:
        return None
    scores: list[float] = []
    rng = np.random.default_rng(seed)
    for _ in range(3):
        perturbed = _normalize_rows(matrix + rng.normal(0.0, 0.004, size=matrix.shape))
        try:
            scores.append(float(adjusted_rand_score(labels, runner(perturbed))))
        except Exception:
            continue
    return float(np.mean(scores)) if scores else None


def _balance_score(labels: np.ndarray) -> float:
    counts = [count for label, count in Counter(labels.tolist()).items() if label >= 0]
    if not counts:
        return 0.0
    return float(min(counts) / max(counts))


@dataclass
class Candidate:
    labels: np.ndarray
    requested: str
    used: str
    k: int
    silhouette: float | None
    stability: float | None
    balance: float
    undersized_document_ratio: float
    selection_score: float
    warnings: list[str]


def _candidate(matrix: np.ndarray, method: str, k: int, min_cluster_size: int, seed: int) -> Candidate:
    warnings: list[str] = []
    if method == "kmeans":
        runner = lambda values: KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(values)
        labels = runner(matrix)
        used = "kmeans"
    elif method in {"agglomerative", "hierarchical"}:
        runner = lambda values: _agglomerative(values, k)
        labels = runner(matrix)
        used = "agglomerative"
    elif method == "hdbscan":
        labels, used, warnings = _run_hdbscan(matrix, min_cluster_size)
        runner = lambda values: _run_hdbscan(values, min_cluster_size)[0]
        actual = len(set(labels[labels >= 0].tolist()))
        # 全噪声时 actual=0，回落到 1（类簇数量最低为 1，不能为 0/负）。
        k = max(1, actual)
    else:
        raise ValueError(f"Unsupported clustering algorithm: {method}")
    silhouette = _safe_silhouette(matrix, labels)
    stability = _stability(matrix, labels, runner, seed)
    balance = _balance_score(labels)
    silhouette_part = -1.0 if silhouette is None else silhouette
    stability_part = 0.0 if stability is None else stability
    noise_ratio = float(np.mean(labels < 0))
    counts = Counter(labels.tolist())
    undersized_documents = sum(
        count for label, count in counts.items()
        if label >= 0 and count < min_cluster_size
    )
    undersized_ratio = float(undersized_documents / max(len(labels), 1))
    if undersized_ratio > 0:
        warnings.append(
            f"{undersized_documents} documents belong to clusters smaller than "
            f"minimum_cluster_size={min_cluster_size}."
        )
    selection_score = (
        0.60 * silhouette_part
        + 0.25 * stability_part
        + 0.15 * balance
        - 0.30 * noise_ratio
        - 0.60 * undersized_ratio
    )
    return Candidate(
        labels, method, used, k, silhouette, stability, balance,
        undersized_ratio, selection_score, warnings,
    )


def _threshold_candidate(matrix: np.ndarray, similarity_threshold: float, seed: int) -> Candidate:
    runner = lambda values: _agglomerative_threshold(values, similarity_threshold)
    labels = runner(matrix)
    k = len(set(labels.tolist()))
    silhouette = _safe_silhouette(matrix, labels)
    stability = _stability(matrix, labels, runner, seed)
    balance = _balance_score(labels)
    silhouette_part = -1.0 if silhouette is None else silhouette
    stability_part = 0.0 if stability is None else stability
    selection_score = 0.60 * silhouette_part + 0.25 * stability_part + 0.15 * balance
    return Candidate(
        labels, "agglomerative", "agglomerative_threshold", k,
        silhouette, stability, balance, 0.0, selection_score, [],
    )


def _choose_candidate(
    matrix: np.ndarray,
    algorithm: str,
    requested_k: int | None,
    min_cluster_size: int,
    similarity_threshold: float | None,
    seed: int,
) -> Candidate:
    n = len(matrix)
    if n == 1:
        return Candidate(np.array([0]), algorithm, "single_cluster", 1, None, 1.0, 1.0, 0.0, 1.0, [])
    if requested_k is not None:
        # 用户指定簇数：最低 1（支持全部文献归为一类），最高 n-1。
        requested_k = max(1, min(int(requested_k), n - 1))
    if algorithm not in {"auto", "kmeans", "agglomerative", "hierarchical", "hdbscan"}:
        raise ValueError("algorithm must be auto, kmeans, agglomerative, hierarchical, or hdbscan")
    if algorithm == "hdbscan":
        return _candidate(matrix, algorithm, requested_k or 2, min_cluster_size, seed)
    if requested_k is not None:
        method = "kmeans" if algorithm == "auto" else algorithm
        return _candidate(matrix, method, requested_k, min_cluster_size, seed)

    if algorithm in {"agglomerative", "hierarchical"} and similarity_threshold is not None:
        threshold_result = _threshold_candidate(matrix, similarity_threshold, seed)
        if 2 <= threshold_result.k < n:
            return threshold_result

    upper = min(n - 1, max(2, min(12, round(math.sqrt(n) * 2))))
    candidates: list[Candidate] = []
    methods = ("kmeans", "agglomerative") if algorithm == "auto" else (algorithm,)
    for method in methods:
        for k in range(2, upper + 1):
            candidates.append(_candidate(matrix, method, k, min_cluster_size, seed))
    if algorithm == "auto" and n >= max(8, min_cluster_size * 2):
        density = _candidate(matrix, "hdbscan", 2, min_cluster_size, seed)
        if density.k >= 2:
            candidates.append(density)
    if algorithm == "auto" and similarity_threshold is not None:
        threshold_result = _threshold_candidate(matrix, similarity_threshold, seed)
        if 2 <= threshold_result.k < n:
            candidates.append(threshold_result)
    return max(candidates, key=lambda item: (item.selection_score, item.stability or -1.0, -(item.k or 0)))


def _terms_from_text(text: str) -> set[str]:
    result = {token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z0-9+_.-]{2,30}", text)}
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,18}", text):
        if 2 <= len(chunk) <= 8:
            result.add(chunk)
        for size in (2, 3, 4, 5, 6):
            if len(chunk) < size:
                continue
            result.update(chunk[pos:pos + size] for pos in range(0, len(chunk) - size + 1))
    return {term for term in result if term not in GENERIC_TERMS and not term.isdigit()}


def _representative_terms(
    papers: Sequence[dict[str, Any]],
    views: Sequence[str],
    members: Sequence[int],
    limit: int = 6,
) -> list[str]:
    doc_terms: list[set[str]] = []
    keyword_terms: list[set[str]] = []
    for paper, view in zip(papers, views):
        kw = {term.casefold(): term for term in paper["keywords"] if term}.values()
        keyword_set = set(kw)
        keyword_terms.append(keyword_set)
        doc_terms.append(_terms_from_text(view) | keyword_set)
    document_frequency = Counter(term for terms in doc_terms for term in terms)
    cluster_frequency = Counter()
    keyword_frequency = Counter()
    for index in members:
        cluster_frequency.update(doc_terms[index])
        keyword_frequency.update(keyword_terms[index])
    n = len(doc_terms)
    scored = []
    for term, frequency in cluster_frequency.items():
        if len(term) < 2 or len(term) > 24:
            continue
        idf = math.log((1 + n) / (1 + document_frequency[term])) + 1.0
        score = frequency * idf + keyword_frequency[term] * 2.5
        scored.append((score, keyword_frequency[term], len(term), term))
    selected: list[str] = []
    for _, _, _, term in sorted(scored, reverse=True):
        if any(term in chosen or chosen in term for chosen in selected):
            continue
        selected.append(term)
        if len(selected) >= limit:
            break
    return selected


def _projection(matrix: np.ndarray, labels: Sequence[str], papers: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    n = len(matrix)
    if n == 1:
        coords = np.array([[50.0, 50.0]])
    else:
        components = min(2, n, matrix.shape[1])
        coords = PCA(n_components=components, random_state=42).fit_transform(matrix)
        if components == 1:
            coords = np.column_stack([coords[:, 0], np.zeros(n)])
        scaled = []
        for column in range(2):
            values = coords[:, column]
            span = float(values.max() - values.min())
            scaled.append(np.full(n, 50.0) if span < 1e-12 else 5.0 + (values - values.min()) / span * 90.0)
        coords = np.column_stack(scaled)
    return [{
        "document_id": papers[index]["document_id"],
        "title": papers[index]["title"],
        "cluster_id": labels[index],
        "x": round(float(coords[index, 0]), 3),
        "y": round(float(coords[index, 1]), 3),
    } for index in range(n)]


def _quality_metrics(matrix: np.ndarray, labels: np.ndarray, candidate: Candidate) -> dict[str, Any]:
    mask = labels >= 0
    clean_labels = labels[mask]
    # 全噪声时 clean_labels 为空，len(set())=0；回落到 1 保证 cluster_count 最低为 1。
    cluster_count = max(1, len(set(clean_labels.tolist())))
    ch = db = None
    if mask.sum() > cluster_count >= 2:
        dimensions = min(10, matrix.shape[1], int(mask.sum()) - 1)
        reduced = PCA(n_components=dimensions, random_state=42).fit_transform(matrix[mask])
        ch = float(calinski_harabasz_score(reduced, clean_labels))
        db = float(davies_bouldin_score(reduced, clean_labels))
    counts = Counter(labels.tolist())
    normal_sizes = [count for label, count in counts.items() if label >= 0]
    return {
        "cluster_count": cluster_count,
        "silhouette_score": None if candidate.silhouette is None else round(candidate.silhouette, 6),
        "calinski_harabasz_score": None if ch is None else round(ch, 6),
        "davies_bouldin_score": None if db is None else round(db, 6),
        "stability_ari": None if candidate.stability is None else round(candidate.stability, 6),
        "balance_score": round(candidate.balance, 6),
        "undersized_document_ratio": round(candidate.undersized_document_ratio, 6),
        "noise_ratio": round(float(np.mean(labels < 0)), 6),
        "singleton_ratio": round(sum(1 for size in normal_sizes if size == 1) / max(cluster_count, 1), 6),
        "algorithm_requested": candidate.requested,
        "algorithm_used": candidate.used,
        "selection_score": round(candidate.selection_score, 6),
        "warnings": candidate.warnings,
        "evaluation_note": "ARI against a gold standard is only reported when reviewed gold labels are supplied.",
    }


def cluster_axis(
    matrix: np.ndarray,
    papers: Sequence[dict[str, Any]],
    views: Sequence[str],
    evidence: Sequence[Sequence[str]],
    *,
    axis: str,
    algorithm: str = "auto",
    cluster_count: int | None = None,
    min_cluster_size: int = 2,
    similarity_threshold: float | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    matrix = _normalize_rows(matrix)
    candidate = _choose_candidate(
        matrix, algorithm, cluster_count, min_cluster_size, similarity_threshold, random_state
    )
    return format_axis_result(matrix, papers, views, evidence, axis=axis, candidate=candidate)


def format_axis_result(
    matrix: np.ndarray,
    papers: Sequence[dict[str, Any]],
    views: Sequence[str],
    evidence: Sequence[Sequence[str]],
    *,
    axis: str,
    candidate: Candidate,
) -> dict[str, Any]:
    """Build the stable Vue/API result contract from externally chosen labels.

    Axis-specific engines (for example the BGE-M3 sparse-head graph engine)
    can choose membership using their native representation and pass a compact
    normalized matrix here for scores, projection, and internal metrics.
    """
    matrix = _normalize_rows(matrix)
    raw_labels = candidate.labels.astype(int)
    normal_labels = sorted(set(raw_labels[raw_labels >= 0].tolist()), key=lambda label: int(np.flatnonzero(raw_labels == label)[0]))
    id_map = {label: f"C{index + 1:02d}" for index, label in enumerate(normal_labels)}
    display_labels = ["OUTLIER" if label < 0 else id_map[label] for label in raw_labels]

    centroids: dict[int, np.ndarray] = {}
    for label in normal_labels:
        centroid = matrix[raw_labels == label].mean(axis=0)
        centroids[label] = centroid / max(float(np.linalg.norm(centroid)), 1e-12)

    axis_info: list[dict[str, Any]] = [{} for _ in papers]
    clusters: list[dict[str, Any]] = []
    total = len(papers)
    for label in normal_labels:
        members = np.flatnonzero(raw_labels == label).tolist()
        centroid = centroids[label]
        similarities = matrix[members] @ centroid
        terms = _representative_terms(papers, views, members)
        cluster_id = id_map[label]
        other_centroids = [centroids[other] for other in normal_labels if other != label]
        max_inter = max((float(centroid @ other) for other in other_centroids), default=0.0)
        representative_order = [members[pos] for pos in np.argsort(-similarities)[:3]]
        topic_name = " / ".join(terms[:2]) if terms else cluster_id
        clusters.append({
            "cluster_id": cluster_id,
            "topic_id": cluster_id,
            "topic_name": topic_name,
            "doc_indices": members,
            "size": len(members),
            "ratio": round(len(members) / max(total, 1), 6),
            "representative_terms": terms,
            "representative_documents": [{
                "document_id": papers[index]["document_id"],
                "title": papers[index]["title"],
            } for index in representative_order],
            "members": [{
                "document_id": papers[index]["document_id"],
                "title": papers[index]["title"],
            } for index in members],
            "feature_statistics": {
                "intra_cluster_similarity": round(float(np.mean(np.clip(similarities, 0.0, 1.0))), 6),
                "inter_cluster_separation": round(float(np.clip(1.0 - max_inter, 0.0, 1.0)), 6),
                "semantic_density": round(float(np.clip(1.0 - np.std(similarities), 0.0, 1.0)), 6),
            },
        })
        for local_pos, document_index in enumerate(members):
            axis_info[document_index] = {
                "topic_id": cluster_id,
                "topic_name": topic_name,
                "score": round(float(np.clip(similarities[local_pos], 0.0, 1.0)), 6),
                "status": "matched",
                "key_evidence": " ".join(evidence[document_index][:2])[:260],
            }

    outlier_indices = np.flatnonzero(raw_labels < 0).tolist()
    if outlier_indices:
        clusters.append({
            "cluster_id": "OUTLIER", "topic_id": "OUTLIER", "topic_name": "待人工复核",
            "doc_indices": outlier_indices, "size": len(outlier_indices),
            "ratio": round(len(outlier_indices) / max(total, 1), 6),
            "representative_terms": [], "representative_documents": [],
            "members": [{"document_id": papers[index]["document_id"], "title": papers[index]["title"]} for index in outlier_indices],
            "feature_statistics": {"intra_cluster_similarity": 0.0, "inter_cluster_separation": 0.0, "semantic_density": 0.0},
        })
        for index in outlier_indices:
            axis_info[index] = {
                "topic_id": "OUTLIER", "topic_name": "待人工复核", "score": 0.0,
                "status": "outlier", "key_evidence": " ".join(evidence[index][:2])[:260],
            }

    quality = _quality_metrics(matrix, raw_labels, candidate)
    return {
        "axis": axis,
        "clusters": clusters,
        "doc_axis_info": axis_info,
        "projection": _projection(matrix, display_labels, papers),
        "quality": quality,
        "labels": display_labels,
    }


def run_dual_axis_clustering(
    items: Sequence[dict[str, Any] | str],
    encoder: Any,
    *,
    axis_extractor: Any | None = None,
    algorithm: str = "auto",
    cluster_count: int | None = None,
    min_cluster_size: int = 2,
    similarity_threshold: float | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """Execute both semantic axes with one BGE encoder batch."""
    papers = normalize_papers(items)
    if not papers:
        raise ValueError("At least one scientific document is required.")
    technical, application, technical_evidence, application_evidence = build_dual_views(papers)
    extraction_metadata = {
        "mode": "local",
        "document_count": len(papers),
        "verified_document_count": 0,
        "fallback_document_count": 0,
        "llm_assigns_cluster_membership": False,
        "topic_library_used": False,
    }
    if axis_extractor is not None:
        extracted = axis_extractor.extract(
            papers,
            local_technical_views=technical,
            local_application_views=application,
            local_technical_evidence=technical_evidence,
            local_application_evidence=application_evidence,
        )
        technical = extracted.technical_views
        application = extracted.application_views
        technical_evidence = extracted.technical_evidence
        application_evidence = extracted.application_evidence
        extraction_metadata = extracted.metadata
    vectors = np.asarray(encoder.encode(technical + application), dtype=np.float32)
    if len(vectors) != len(papers) * 2:
        raise ValueError("The encoding model returned an unexpected number of vectors.")
    technical_result = cluster_axis(
        vectors[:len(papers)], papers, technical, technical_evidence,
        axis="technical", algorithm=algorithm, cluster_count=cluster_count,
        min_cluster_size=min_cluster_size, similarity_threshold=similarity_threshold,
        random_state=random_state,
    )
    application_result = cluster_axis(
        vectors[len(papers):], papers, application, application_evidence,
        axis="application", algorithm=algorithm, cluster_count=cluster_count,
        min_cluster_size=min_cluster_size, similarity_threshold=similarity_threshold,
        random_state=random_state,
    )
    return {
        "papers": papers,
        "technical": technical_result,
        "application": application_result,
        "axis_extraction": extraction_metadata,
        "parsed_sentence_count": sum(len(_sentences(paper["abstract"])) for paper in papers),
    }
