"""Label-free clustering candidates for application-scenario experiments."""
from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering
from sklearn.metrics import adjusted_rand_score, silhouette_score


ALGORITHMS = ("spherical_kmeans", "average_linkage_consensus", "global_spectral")


def normalize(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float32)
    return values / np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-12)


def _agglomerative(matrix: np.ndarray, k: int, *, precomputed: bool = False) -> np.ndarray:
    kwargs = {"n_clusters": k, "linkage": "average"}
    metric = "precomputed" if precomputed else "cosine"
    try:
        return AgglomerativeClustering(metric=metric, **kwargs).fit_predict(matrix)
    except TypeError:  # scikit-learn < 1.2
        return AgglomerativeClustering(affinity=metric, **kwargs).fit_predict(matrix)


def _spectral(affinity: np.ndarray, k: int, seed: int) -> np.ndarray:
    safe = np.clip(np.asarray(affinity, dtype=np.float64), 0.0, 1.0)
    np.fill_diagonal(safe, 1.0)
    return SpectralClustering(
        n_clusters=k, affinity="precomputed", assign_labels="cluster_qr",
        random_state=seed,
    ).fit_predict(safe)


def consensus_agglomerative(
    matrix: np.ndarray,
    k: int,
    *,
    seed: int,
    repetitions: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Average-linkage consensus under small semantic perturbations."""
    matrix = normalize(matrix)
    n = len(matrix)
    repetitions = (9 if n <= 30 else 5) if repetitions is None else max(5, repetitions)
    coassignment = np.zeros((n, n), dtype=np.float64)
    rng = np.random.default_rng(seed)
    for _ in range(repetitions):
        perturbed = normalize(matrix + rng.normal(0.0, 0.006, size=matrix.shape))
        labels = _agglomerative(perturbed, k)
        coassignment += labels[:, None] == labels[None, :]
    coassignment /= repetitions
    np.fill_diagonal(coassignment, 1.0)
    labels = _agglomerative(1.0 - coassignment, k, precomputed=True)
    return labels, coassignment


def run_algorithm(
    matrix: np.ndarray,
    affinity: np.ndarray,
    algorithm: str,
    k: int,
    *,
    seed: int,
) -> np.ndarray:
    if algorithm == "spherical_kmeans":
        return KMeans(n_clusters=k, n_init=30, random_state=seed).fit_predict(normalize(matrix))
    if algorithm == "average_linkage_consensus":
        # Consensus is valuable for the user's typical 10-30 document upload.
        # On development/validation collections it adds substantial cost but
        # little information, so the same average-linkage family runs directly.
        return (
            consensus_agglomerative(matrix, k, seed=seed)[0]
            if len(matrix) <= 30 else _agglomerative(matrix, k)
        )
    if algorithm == "global_spectral":
        return _spectral(affinity, k, seed)
    raise ValueError(f"Unsupported algorithm: {algorithm}")


def _stability(
    matrix: np.ndarray,
    affinity: np.ndarray,
    labels: np.ndarray,
    algorithm: str,
    k: int,
    seed: int,
) -> float:
    scores = []
    rng = np.random.default_rng(seed + 7919)
    repeat_count = 3 if len(matrix) <= 30 else 2
    for repeat in range(repeat_count):
        perturbed = normalize(matrix + rng.normal(0.0, 0.006, size=matrix.shape))
        perturbed_affinity = np.clip(perturbed @ perturbed.T, 0.0, 1.0)
        try:
            # Avoid nesting a complete bootstrap-consensus run inside every
            # stability perturbation.  Average linkage is the base learner of
            # the consensus method and is the correct inexpensive probe here.
            rerun = (
                _agglomerative(perturbed, k)
                if algorithm == "average_linkage_consensus"
                else run_algorithm(
                    perturbed, perturbed_affinity, algorithm, k,
                    seed=seed + repeat + 1,
                )
            )
            scores.append(float(adjusted_rand_score(labels, rerun)))
        except Exception:  # noqa: BLE001
            continue
    return float(np.mean(scores)) if scores else 0.0


def _eigengaps(affinity: np.ndarray, ks: Sequence[int]) -> dict[int, float]:
    graph = np.clip(np.asarray(affinity, dtype=np.float64), 0.0, 1.0).copy()
    np.fill_diagonal(graph, 0.0)
    degree = np.maximum(graph.sum(axis=1), 1e-12)
    scale = 1.0 / np.sqrt(degree)
    laplacian = np.eye(len(graph)) - scale[:, None] * graph * scale[None, :]
    eigenvalues = np.linalg.eigvalsh(laplacian)
    raw = {k: max(0.0, float(eigenvalues[k] - eigenvalues[k - 1])) for k in ks if k < len(eigenvalues)}
    maximum = max(raw.values(), default=0.0)
    return {k: (value / maximum if maximum > 1e-12 else 0.0) for k, value in raw.items()}


def select_k(
    matrix: np.ndarray,
    affinity: np.ndarray,
    algorithm: str,
    *,
    min_cluster_size: int = 2,
    max_k: int | None = None,
    seed: int = 42,
) -> tuple[np.ndarray, dict]:
    """Choose K without Gold labels and return an auditable candidate table."""
    n = len(matrix)
    if n < 4:
        labels = np.zeros(n, dtype=int) if n == 1 else run_algorithm(matrix, affinity, algorithm, 2, seed=seed)
        return labels, {"selected_k": len(set(labels.tolist())), "candidates": []}
    upper = min(max_k or 12, n - 1, max(2, n // max(2, min_cluster_size)))
    ks = list(range(2, upper + 1))
    gaps = _eigengaps(affinity, ks)
    rows = []
    for k in ks:
        labels = run_algorithm(matrix, affinity, algorithm, k, seed=seed)
        counts = Counter(labels.tolist())
        undersized = sum(count for count in counts.values() if count < min_cluster_size) / n
        balance = min(counts.values()) / max(counts.values())
        silhouette = float(silhouette_score(matrix, labels, metric="cosine"))
        stability = _stability(matrix, affinity, labels, algorithm, k, seed)
        rows.append({
            "k": k, "labels": labels, "silhouette": silhouette,
            "stability": stability, "balance": balance,
            "eigengap": gaps.get(k, 0.0), "undersized_ratio": undersized,
        })
    silhouettes = [row["silhouette"] for row in rows]
    low, high = min(silhouettes), max(silhouettes)
    for row in rows:
        scaled = 0.5 if high - low <= 1e-12 else (row["silhouette"] - low) / (high - low)
        row["selection_score"] = (
            0.32 * scaled + 0.28 * row["stability"] + 0.25 * row["eigengap"]
            + 0.15 * row["balance"] - 0.80 * row["undersized_ratio"]
        )
    chosen = max(rows, key=lambda row: (row["selection_score"], row["stability"], -row["k"]))
    audit_rows = [
        {key: (round(float(value), 6) if isinstance(value, (float, np.floating)) else value)
         for key, value in row.items() if key != "labels"}
        for row in rows
    ]
    return chosen["labels"], {"selected_k": chosen["k"], "candidates": audit_rows}
