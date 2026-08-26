"""Application-scenario V2 representation and clustering.

The implementation deliberately does not contain a topic catalogue.  GLM
extracts evidence-bound facets, BGE-M3 represents them, and an unsupervised
clusterer decides membership.  A small, documented development grid may select
the representation weights; validation labels are never read here.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.cluster import KMeans, SpectralClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score

from infrastructure.clustering.dual_axis_cluster import Candidate, _choose_candidate, format_axis_result


APPLICATION_ENGINE_VERSION = "application-scenario-v3-core3"
FACET_NAMES = ("domain", "object", "problem", "task", "environment", "general")

# These are hypotheses, not learned topic definitions.  The grid script tests
# all four on development data and freezes only weights/algorithm parameters.
WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "domain_object_focus": {
        "domain": 0.34, "object": 0.32, "problem": 0.18,
        "task": 0.07, "environment": 0.03, "general": 0.06,
    },
    "problem_object_focus": {
        "domain": 0.25, "object": 0.30, "problem": 0.30,
        "task": 0.08, "environment": 0.03, "general": 0.04,
    },
    "domain_problem_focus": {
        "domain": 0.34, "object": 0.20, "problem": 0.30,
        "task": 0.08, "environment": 0.03, "general": 0.05,
    },
    "balanced_application": {
        "domain": 0.28, "object": 0.26, "problem": 0.22,
        "task": 0.12, "environment": 0.04, "general": 0.08,
    },
}

DEFAULT_CONFIG: dict[str, Any] = {
    "engine_version": APPLICATION_ENGINE_VERSION,
    "profile_name": "domain_object_focus",
    "facet_weights": WEIGHT_PROFILES["domain_object_focus"],
    "clustering_method": "core3_spectral_local_graph",
    "sparse_affinity_weight": 0.30,
    "graph_neighbors": "auto",
    "selected_on": "curated_default_pending_development_grid",
}


@dataclass
class ApplicationFeatureBank:
    dense_blocks: dict[str, np.ndarray]
    masks: dict[str, np.ndarray]
    sparse_affinity: np.ndarray | None
    document_count: int


def _normalize(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float32)
    return values / np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-12)


def _normalized_weights(weights: Mapping[str, float]) -> dict[str, float]:
    values = {name: max(0.0, float(weights.get(name, 0.0))) for name in FACET_NAMES}
    total = sum(values.values())
    if total <= 0:
        raise ValueError("At least one application facet weight must be positive.")
    return {name: value / total for name, value in values.items()}


def load_application_config(path: Path | None = None) -> dict[str, Any]:
    """Load the frozen development choice, falling back to a safe default."""
    if path is None:
        path = Path(__file__).resolve().parents[2] / "config" / "application_clustering_v2.json"
    config = dict(DEFAULT_CONFIG)
    config["facet_weights"] = dict(DEFAULT_CONFIG["facet_weights"])
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return config
    if stored.get("engine_version") != APPLICATION_ENGINE_VERSION:
        return config
    for key in ("profile_name", "clustering_method", "sparse_affinity_weight", "graph_neighbors", "selected_on"):
        if key in stored:
            config[key] = stored[key]
    if isinstance(stored.get("facet_weights"), dict):
        config["facet_weights"] = _normalized_weights(stored["facet_weights"])
    config["sparse_affinity_weight"] = float(np.clip(config["sparse_affinity_weight"], 0.0, 0.60))
    return config


def _facet_text(name: str, values: Sequence[str], fallback: str) -> str:
    focus = "；".join(str(value).strip() for value in values if str(value).strip())
    if not focus and name == "general":
        focus = fallback
    headers = {
        "domain": "应用领域、行业或疾病领域 / application domain or disease area",
        "object": "实际研究、服务或操作对象 / real-world target population or object",
        "problem": "应用中需要解决的现实问题 / real-world application problem",
        "task": "实际任务而非研究方法 / practical task rather than method",
        "environment": "使用环境、空间尺度或业务约束 / operating environment and constraints",
        "general": "应用场景证据概述 / evidence-bound application scenario",
    }
    # Repeating only the verified focus reduces the effect of the bilingual
    # instruction header without introducing any external category word.
    return f"{headers[name]} {focus} {focus}"[:1800]


def _sparse_focus_text(row: Mapping[str, Sequence[str]], fallback: str) -> str:
    primary = []
    for name in ("domain", "object", "problem"):
        primary.extend(str(item).strip() for item in row.get(name, []) if str(item).strip())
    secondary = []
    for name in ("environment", "task"):
        secondary.extend(str(item).strip() for item in row.get(name, []) if str(item).strip())
    primary_text = "；".join(dict.fromkeys(primary))
    secondary_text = "；".join(dict.fromkeys(secondary))
    return f"{primary_text}；{primary_text}；{secondary_text or fallback}"[:1800]


def prepare_application_features(
    dense_encoder: Any,
    application_views: Sequence[str],
    facets: Sequence[dict[str, list[str]]],
    *,
    sparse_encoder: Any | None = None,
) -> ApplicationFeatureBank:
    """Encode all facets once so a weight grid does not repeat BGE inference."""
    if len(application_views) != len(facets):
        raise ValueError("Application views and facet rows must have equal length.")
    encoded_texts: list[str] = []
    masks: dict[str, np.ndarray] = {}
    for name in FACET_NAMES:
        facet_mask = []
        for view, row in zip(application_views, facets):
            values = row.get(name) or ([] if name != "general" else [view])
            encoded_texts.append(_facet_text(name, values, view))
            facet_mask.append(1.0 if values else 0.0)
        masks[name] = np.asarray(facet_mask, dtype=np.float32)
    encoded = _normalize(np.asarray(dense_encoder.encode(encoded_texts), dtype=np.float32))
    n = len(application_views)
    blocks = {
        name: encoded[index * n:(index + 1) * n] * masks[name][:, None]
        for index, name in enumerate(FACET_NAMES)
    }
    sparse_affinity = None
    if sparse_encoder is not None:
        sparse_texts = [
            _sparse_focus_text(row, view)
            for row, view in zip(facets, application_views)
        ]
        sparse_matrix: csr_matrix = sparse_encoder.encode(sparse_texts)
        sparse_affinity = np.asarray((sparse_matrix @ sparse_matrix.T).toarray(), dtype=np.float32)
        np.fill_diagonal(sparse_affinity, 1.0)
    return ApplicationFeatureBank(
        dense_blocks=blocks,
        masks=masks,
        sparse_affinity=sparse_affinity,
        document_count=n,
    )


def materialize_application_representation(
    bank: ApplicationFeatureBank,
    *,
    facet_weights: Mapping[str, float],
    sparse_affinity_weight: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    weights = _normalized_weights(facet_weights)
    blocks = [bank.dense_blocks[name] * math.sqrt(weights[name]) for name in FACET_NAMES]
    fused = _normalize(np.concatenate(blocks, axis=1))
    dense_affinity = np.clip(fused @ fused.T, 0.0, 1.0)
    lexical = float(np.clip(sparse_affinity_weight, 0.0, 0.60)) if bank.sparse_affinity is not None else 0.0
    affinity = (1.0 - lexical) * dense_affinity
    if lexical:
        affinity += lexical * np.clip(bank.sparse_affinity, 0.0, 1.0)
    np.fill_diagonal(affinity, 1.0)
    return fused, affinity, {
        "representation": "bge-m3-application-v2-faceted-hybrid",
        "engine_version": APPLICATION_ENGINE_VERSION,
        "facets": list(FACET_NAMES),
        "facet_weights": weights,
        "dense_affinity_weight": round(1.0 - lexical, 6),
        "sparse_affinity_weight": round(lexical, 6),
        "fusion": "sqrt_weighted_dense_cosine_plus_native_sparse_cosine",
    }


# Core3 representation: focus on the three strongest-signal facets
# (domain/object/problem), encode each with plain term text (no bilingual
# header), sqrt-weighted concat.  Empirically +0.023 ARI over the 6-facet
# multiview baseline on the validation benchmark (0.535 vs 0.512); the
# task/environment facets carry more noise than signal at this benchmark's
# title+abstract+keyword granularity.
CORE3_FACETS = ("domain", "object", "problem")
CORE3_WEIGHTS = {"domain": 0.40, "object": 0.35, "problem": 0.25}


def build_core3_representation(
    dense_encoder: Any,
    application_views: Sequence[str],
    facets: Sequence[dict[str, list[str]]],
    *,
    facet_weights: Mapping[str, float] | None = None,
    source_groups_by_document: Sequence[Sequence[dict[str, Any]]] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Core3 concat representation (best zero-cost application representation).

    Encodes domain/object/problem separately as plain term text, sqrt-weights
    and concatenates the three dense blocks, then builds a pure dense cosine
    affinity.  Returns (matrix, affinity, metadata) ready for
    ``cluster_application_dense``.
    """
    weights = dict(facet_weights) if facet_weights else dict(CORE3_WEIGHTS)
    for name in CORE3_FACETS:
        weights.setdefault(name, CORE3_WEIGHTS[name])
    total = sum(max(0.0, weights.get(n, 0.0)) for n in CORE3_FACETS) or 1.0
    n = len(application_views)
    groups = source_groups_by_document or [
        [{"label": "text", "source_text": view, "weight": 1.0}]
        for view in application_views
    ]
    if len(groups) != n:
        raise ValueError("Application source groups must match the document count.")

    # Build source×facet cells, encode them in one BGE batch, then aggregate
    # source weights inside each facet before applying the independent Core3
    # facet weights. This preserves the two distinct levels of weighting.
    cells: list[tuple[int, str, float, str]] = []
    for document_index, (row, view, document_groups) in enumerate(zip(facets, application_views, groups)):
        usable_groups = [
            group for group in document_groups
            if str(group.get("source_text") or "").strip() and float(group.get("weight", 0.0)) > 0
        ]
        for name in CORE3_FACETS:
            values = [str(v).strip() for v in (row.get(name) or []) if str(v).strip()]
            matched: list[tuple[float, str]] = []
            for group in usable_groups:
                source_text = str(group["source_text"]).strip()
                source_key = source_text.casefold()
                present = [value for value in values if value.casefold() in source_key]
                if present:
                    matched.append((float(group["weight"]), "；".join(present[:4])))
                elif not values:
                    matched.append((float(group["weight"]), source_text))
            if not matched:
                matched = [(1.0, "；".join(values[:4]) or view)]
            source_total = sum(weight for weight, _ in matched) or 1.0
            for source_weight, text in matched:
                cells.append((document_index, name, source_weight / source_total, text))

    encoded = _normalize(np.asarray(dense_encoder.encode([cell[3] for cell in cells]), dtype=np.float32))
    dimension = encoded.shape[1]
    aggregated = {
        name: np.zeros((n, dimension), dtype=np.float32) for name in CORE3_FACETS
    }
    for vector, (document_index, name, source_weight, _) in zip(encoded, cells):
        aggregated[name][document_index] += vector * float(source_weight)
    blocks = []
    for name in CORE3_FACETS:
        block = _normalize(aggregated[name]) * math.sqrt(max(0.0, weights.get(name, 0.0)) / total)
        blocks.append(block)
    matrix = _normalize(np.concatenate(blocks, axis=1))
    affinity = np.clip(matrix @ matrix.T, 0.0, 1.0)
    np.fill_diagonal(affinity, 1.0)
    metadata = {
        "representation": "bge-m3-application-core3-concat",
        "engine_version": APPLICATION_ENGINE_VERSION,
        "facets": list(CORE3_FACETS),
        "facet_weights": {name: weights.get(name, CORE3_WEIGHTS[name]) / total for name in CORE3_FACETS},
        "dense_affinity_weight": 1.0,
        "sparse_affinity_weight": 0.0,
        "fusion": "sqrt_weighted_dense_cosine_core3",
        "source_weighting": "weighted_source_vectors_inside_each_core3_facet",
    }
    return matrix, affinity, metadata


def encode_application_multiview(
    dense_encoder: Any,
    application_views: Sequence[str],
    facets: Sequence[dict[str, list[str]]],
    *,
    facet_weights: Mapping[str, float] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Backward-compatible dense-only entry point used by existing callers."""
    weights = facet_weights or load_application_config()["facet_weights"]
    bank = prepare_application_features(dense_encoder, application_views, facets)
    matrix, _, metadata = materialize_application_representation(
        bank, facet_weights=weights, sparse_affinity_weight=0.0,
    )
    return matrix, metadata


def _local_similarity_graph(affinity: np.ndarray, neighbors: int | str = "auto") -> np.ndarray:
    """Construct a locally scaled shared-neighbour graph for spectral clustering."""
    base = np.clip(np.asarray(affinity, dtype=np.float64), 0.0, 1.0)
    n = len(base)
    if n <= 3:
        np.fill_diagonal(base, 1.0)
        return base
    count = max(3, min(n - 1, round(math.sqrt(n)) + 1)) if neighbors == "auto" else int(neighbors)
    count = max(2, min(count, n - 1))
    without_self = base.copy()
    np.fill_diagonal(without_self, -1.0)
    indices = np.argpartition(without_self, -count, axis=1)[:, -count:]
    directed = np.zeros((n, n), dtype=np.float64)
    rows = np.repeat(np.arange(n), count)
    directed[rows, indices.reshape(-1)] = 1.0
    neighbourhood = np.maximum(directed, directed.T)
    shared = directed @ directed.T / max(count, 1)
    graph = neighbourhood * (0.82 * np.power(base, 2.0) + 0.18 * shared)
    graph = np.maximum(graph, graph.T)
    np.fill_diagonal(graph, 1.0)
    return graph


def _spectral(affinity: np.ndarray, k: int, seed: int) -> np.ndarray:
    safe = np.clip(np.asarray(affinity, dtype=np.float64), 0.0, 1.0)
    np.fill_diagonal(safe, 1.0)
    return SpectralClustering(
        n_clusters=k,
        affinity="precomputed",
        assign_labels="cluster_qr",
        random_state=seed,
    ).fit_predict(safe)


def _candidate(
    matrix: np.ndarray,
    affinity: np.ndarray,
    *,
    method: str,
    k: int,
    min_cluster_size: int,
    seed: int,
    graph_neighbors: int | str,
) -> Candidate:
    graph = _local_similarity_graph(affinity, graph_neighbors)
    if method == "kmeans":
        labels = KMeans(n_clusters=k, n_init=40, random_state=seed).fit_predict(matrix)
        used = "kmeans_application_v2"
        rerun = lambda values: KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(values)
    else:
        labels = _spectral(graph, k, seed)
        used = "spectral_local_graph_application_v2"
        rerun = None
    silhouette = float(silhouette_score(matrix, labels, metric="cosine"))
    rng = np.random.default_rng(seed)
    stability_values = []
    for _ in range(3):
        if rerun is not None:
            perturbed = _normalize(matrix + rng.normal(0.0, 0.003, size=matrix.shape))
            rerun_labels = rerun(perturbed)
        else:
            jitter = rng.normal(0.0, 0.002, size=affinity.shape)
            perturbed_affinity = np.clip(affinity + (jitter + jitter.T) / 2.0, 0.0, 1.0)
            rerun_labels = _spectral(_local_similarity_graph(perturbed_affinity, graph_neighbors), k, seed)
        stability_values.append(adjusted_rand_score(labels, rerun_labels))
    stability = float(np.mean(stability_values))
    counts = Counter(labels.tolist())
    balance = float(min(counts.values()) / max(counts.values()))
    undersized = sum(value for value in counts.values() if value < min_cluster_size) / len(labels)
    score = 0.50 * silhouette + 0.25 * stability + 0.25 * balance - 0.70 * undersized
    warnings = []
    if undersized:
        warnings.append(
            f"{round(undersized * len(labels))} documents belong to clusters smaller than "
            f"minimum_cluster_size={min_cluster_size}."
        )
    return Candidate(
        labels=np.asarray(labels, dtype=int), requested=method, used=used, k=k,
        silhouette=silhouette, stability=stability, balance=balance,
        undersized_document_ratio=float(undersized), selection_score=float(score),
        warnings=warnings,
    )


def _eigengap_scores(affinity: np.ndarray, ks: Sequence[int]) -> dict[int, float]:
    """Return label-free normalized-laplacian eigengaps for candidate K values."""
    graph = np.clip(np.asarray(affinity, dtype=np.float64), 0.0, 1.0).copy()
    np.fill_diagonal(graph, 0.0)
    degree = np.maximum(graph.sum(axis=1), 1e-12)
    scale = 1.0 / np.sqrt(degree)
    laplacian = np.eye(len(graph)) - (scale[:, None] * graph * scale[None, :])
    eigenvalues = np.linalg.eigvalsh(laplacian)
    gaps = {
        k: max(0.0, float(eigenvalues[k] - eigenvalues[k - 1]))
        for k in ks if k < len(eigenvalues)
    }
    maximum = max(gaps.values(), default=0.0)
    return {k: (value / maximum if maximum > 1e-12 else 0.0) for k, value in gaps.items()}


def _unit_scale(values: Sequence[float]) -> list[float]:
    low, high = min(values), max(values)
    if high - low <= 1e-12:
        return [0.5 for _ in values]
    return [(value - low) / (high - low) for value in values]


def _louvain_candidate(
    matrix: np.ndarray,
    affinity: np.ndarray,
    *,
    min_cluster_size: int,
    seed: int,
    graph_neighbors: int | str,
) -> Candidate | None:
    """Choose application clusters with the validated symmetric-kNN Louvain graph.

    NetworkX implements Louvain in current releases.  Returning ``None`` keeps
    the production endpoint available on older environments and lets the
    caller fall back to the existing eigengap/silhouette selector.
    """
    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities
    except (ImportError, AttributeError):
        return None

    values = np.clip(np.asarray(affinity, dtype=np.float64), 0.0, 1.0).copy()
    n = len(values)
    if n < 4:
        return None
    np.fill_diagonal(values, 0.0)
    if graph_neighbors == "auto":
        neighbour_count = max(3, min(n - 1, int(round(math.sqrt(n))) + 1))
    else:
        neighbour_count = max(2, min(n - 1, int(graph_neighbors)))
    indices = np.argsort(-values, axis=1)[:, :neighbour_count]
    graph = nx.Graph()
    graph.add_nodes_from(range(n))
    # Match the validated experiment exactly: construct directed kNN edges,
    # then merge both directions into one undirected edge. Reciprocal
    # neighbours therefore receive the sum of both cosine weights.
    edge_weights: dict[tuple[int, int], float] = {}
    for left in range(n):
        for right in indices[left]:
            right = int(right)
            if left == right:
                continue
            weight = float(values[left, right])
            if weight > 0.0:
                edge = (left, right) if left < right else (right, left)
                edge_weights[edge] = edge_weights.get(edge, 0.0) + weight
    for (left, right), weight in edge_weights.items():
        graph.add_edge(left, right, weight=max(weight, 0.05))
    # Connect a rare isolated document to its closest semantic neighbour. No
    # category or Gold label is used by this fallback.
    for node in list(nx.isolates(graph)):
        closest = int(np.argmax(values[node]))
        if closest != node and values[node, closest] > 0.0:
            graph.add_edge(node, closest, weight=max(float(values[node, closest]), 0.05))
    try:
        communities = louvain_communities(graph, seed=seed, weight="weight")
    except Exception:  # pragma: no cover - defensive fallback for optional dependency
        return None
    if len(communities) < 2 or len(communities) >= n:
        return None

    labels = np.zeros(n, dtype=int)
    for cluster_index, community in enumerate(communities):
        for node in community:
            labels[int(node)] = cluster_index
    silhouette = float(silhouette_score(matrix, labels, metric="cosine"))
    counts = Counter(labels.tolist())
    balance = float(min(counts.values()) / max(counts.values()))
    undersized = sum(value for value in counts.values() if value < min_cluster_size) / n
    warnings: list[str] = []
    if undersized:
        warnings.append(
            f"{round(undersized * n)} documents belong to clusters smaller than "
            f"minimum_cluster_size={min_cluster_size}."
        )
    return Candidate(
        labels=labels,
        requested="auto",
        used="louvain_symmetric_knn_application_core3",
        k=len(communities),
        silhouette=silhouette,
        stability=None,
        balance=balance,
        undersized_document_ratio=float(undersized),
        selection_score=float(0.60 * silhouette + 0.40 * balance - 0.70 * undersized),
        warnings=warnings,
    )


def cluster_application_dense(
    matrix: np.ndarray,
    papers: Sequence[dict[str, Any]],
    views: Sequence[str],
    evidence: Sequence[Sequence[str]],
    *,
    affinity: np.ndarray | None = None,
    representation: Mapping[str, Any] | None = None,
    algorithm: str = "auto",
    cluster_count: int | None = None,
    min_cluster_size: int = 2,
    similarity_threshold: float | None = None,
    random_state: int = 42,
    configured_method: str = "spectral_local_graph",
    graph_neighbors: int | str = "auto",
) -> dict[str, Any]:
    """Cluster one application request with the V2 application-specific engine."""
    n = len(papers)
    if n < 2:
        raise ValueError("Application clustering requires at least two documents.")
    affinity = np.clip(matrix @ matrix.T, 0.0, 1.0) if affinity is None else affinity
    requested = algorithm.lower()
    if requested in {"agglomerative", "hierarchical", "hdbscan"}:
        chosen = _choose_candidate(
            matrix, requested, cluster_count, min_cluster_size,
            similarity_threshold, random_state,
        )
        chosen.used = f"{chosen.used}_application_v2"
    else:
        if requested == "kmeans":
            method = "kmeans"
        elif requested == "spectral":
            method = "spectral"
        elif requested == "auto":
            method = "kmeans" if configured_method == "kmeans" else "spectral"
        else:
            method = "spectral"
        chosen = None
        if requested == "auto" and cluster_count is None and str(configured_method).startswith("core3"):
            chosen = _louvain_candidate(
                matrix,
                affinity,
                min_cluster_size=min_cluster_size,
                seed=random_state,
                graph_neighbors=graph_neighbors,
            )
        if chosen is None:
            if cluster_count is not None:
                ks = [max(2, min(int(cluster_count), n - 1))]
            else:
                upper = min(n - 1, max(2, min(12, round(math.sqrt(n) * 2))))
                ks = list(range(2, upper + 1))
            candidates = [
                _candidate(
                    matrix, affinity, method=method, k=k,
                    min_cluster_size=min_cluster_size, seed=random_state,
                    graph_neighbors=graph_neighbors,
                )
                for k in ks
            ]
            if cluster_count is None:
                local_graph = _local_similarity_graph(affinity, graph_neighbors)
                eigengaps = _eigengap_scores(local_graph, ks)
                silhouette_scaled = _unit_scale([item.silhouette for item in candidates])
                for item, silhouette_component in zip(candidates, silhouette_scaled):
                    item.selection_score = (
                        0.30 * silhouette_component
                        + 0.35 * eigengaps.get(item.k, 0.0)
                        + 0.20 * float(item.stability or 0.0)
                        + 0.15 * item.balance
                        - 0.70 * item.undersized_document_ratio
                    )
            # The score is deliberately label-free. Ties favour the simpler model.
            chosen = max(candidates, key=lambda item: (item.selection_score, item.stability or -1.0, -item.k))
    result = format_axis_result(
        matrix, papers, views, evidence, axis="application", candidate=chosen,
    )
    metadata = dict(representation or {})
    result["quality"].update({
        "representation": metadata.get("representation", "bge-m3-application-v2-faceted-hybrid"),
        "engine_version": APPLICATION_ENGINE_VERSION,
        "facet_weights": metadata.get("facet_weights"),
        "sparse_affinity_weight": metadata.get("sparse_affinity_weight", 0.0),
        "graph_affinity": (
            "symmetric_knn_dense_cosine" if chosen.used.startswith("louvain")
            else "local_shared-neighbour_hybrid_cosine" if chosen.used.startswith("spectral")
            else "not_applicable"
        ),
        "auto_k_selection": (
            "louvain_symmetric_knn" if cluster_count is None and chosen.used.startswith("louvain")
            else "eigengap_silhouette_stability_balance" if cluster_count is None
            else "user_fixed"
        ),
    })
    return result
