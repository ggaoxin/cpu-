"""BGE-M3 native sparse-head encoding and technical-route clustering."""
from __future__ import annotations

import hashlib
import math
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.sparse import csr_matrix, vstack
from sklearn.cluster import KMeans, SpectralClustering
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import normalize

from infrastructure.clustering.dual_axis_cluster import Candidate, _choose_candidate, format_axis_result


class BgeM3SparseEncoder:
    """Reuse the project's SentenceTransformer backbone and sparse_linear.pt."""

    def __init__(
        self,
        dense_encoder: Any,
        model_path: Path,
        *,
        batch_size: int = 8,
        max_length: int = 1024,
    ) -> None:
        self._dense_encoder = dense_encoder
        self.model_path = Path(model_path)
        self.batch_size = max(1, int(batch_size))
        self.max_length = max(64, int(max_length))
        self._linear = None
        self._tokenizer = None
        self._auto_model = None
        self._device = None

    @property
    def weight_path(self) -> Path:
        return self.model_path / "sparse_linear.pt"

    def _ensure_loaded(self) -> None:
        if self._linear is not None:
            return
        import torch  # noqa: PLC0415

        if not self.weight_path.is_file():
            raise FileNotFoundError(
                f"BGE-M3 sparse head not found: {self.weight_path}. "
                "Use the complete BGE-M3 model directory containing sparse_linear.pt."
            )
        self._dense_encoder._ensure_loaded()
        transformer = self._dense_encoder._model._first_module()
        self._tokenizer = transformer.tokenizer
        self._auto_model = transformer.auto_model
        self._device = next(self._auto_model.parameters()).device
        hidden_size = int(getattr(self._auto_model.config, "hidden_size", 1024))
        linear = torch.nn.Linear(hidden_size, 1).to(self._device)
        state = torch.load(self.weight_path, map_location=self._device)
        linear.load_state_dict(state)
        linear.eval()
        self._linear = linear

    def metadata(self) -> dict[str, Any]:
        self._ensure_loaded()
        return {
            "representation": "bge-m3-native-sparse-head",
            "model_path": str(self.model_path),
            "sparse_head_path": str(self.weight_path),
            "sparse_head_sha256": hashlib.sha256(self.weight_path.read_bytes()).hexdigest(),
            "vocab_size": int(self._tokenizer.vocab_size),
            "batch_size": self.batch_size,
            "max_length": self.max_length,
            "device": str(self._device),
        }

    def encode(self, texts: Sequence[str]) -> csr_matrix:
        """Return L2-normalized lexical-weight vectors in tokenizer vocabulary space."""
        import torch  # noqa: PLC0415

        self._ensure_loaded()
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        text_values = [str(text or "") for text in texts]
        with torch.inference_mode():
            for start in range(0, len(text_values), self.batch_size):
                batch_texts = text_values[start:start + self.batch_size]
                batch = self._tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                ).to(self._device)
                hidden = self._auto_model(**batch).last_hidden_state
                weights = torch.relu(self._linear(hidden).squeeze(-1))
                weights = weights * batch["attention_mask"]
                for local_index, (token_row, weight_row) in enumerate(zip(batch["input_ids"], weights)):
                    token_weights: dict[int, float] = {}
                    for token_id, weight in zip(token_row.tolist(), weight_row.tolist()):
                        if token_id in self._tokenizer.all_special_ids or weight <= 0:
                            continue
                        token_weights[token_id] = max(token_weights.get(token_id, 0.0), float(weight))
                    document_index = start + local_index
                    for token_id, weight in token_weights.items():
                        rows.append(document_index)
                        columns.append(token_id)
                        values.append(weight)
        matrix = csr_matrix(
            (values, (rows, columns)),
            shape=(len(text_values), int(self._tokenizer.vocab_size)),
            dtype=np.float32,
        )
        return normalize(matrix, norm="l2", copy=False).tocsr()

    def encode_weighted_documents(
        self,
        documents: Sequence[Sequence[dict[str, Any]]],
    ) -> csr_matrix:
        """Encode source fields/chunks once, then compute real weighted sums."""
        flattened: list[str] = []
        locations: list[tuple[int, float]] = []
        for document_index, groups in enumerate(documents):
            usable = [
                group for group in groups
                if str(group.get("source_text") or "").strip() and float(group.get("weight", 0.0)) > 0
            ]
            if not usable:
                raise ValueError(f"Document {document_index + 1} has no usable technical text.")
            total = sum(float(group["weight"]) for group in usable) or 1.0
            for group in usable:
                flattened.append(str(group["source_text"]))
                locations.append((document_index, float(group["weight"]) / total))
        encoded = self.encode(flattened)
        rows = []
        for document_index in range(len(documents)):
            selected = [position for position, row in enumerate(locations) if row[0] == document_index]
            weighted = encoded[selected[0]].multiply(locations[selected[0]][1])
            for position in selected[1:]:
                weighted = weighted + encoded[position].multiply(locations[position][1])
            rows.append(weighted)
        return normalize(vstack(rows).tocsr(), norm="l2", copy=False).tocsr()


def _compact(sparse_matrix: csr_matrix, random_state: int) -> np.ndarray:
    n = sparse_matrix.shape[0]
    if n <= 2:
        return normalize(sparse_matrix.toarray())
    components = min(64, n - 1, sparse_matrix.shape[1] - 1)
    if components < 2:
        return normalize(sparse_matrix.toarray())
    reduced = TruncatedSVD(n_components=components, random_state=random_state).fit_transform(sparse_matrix)
    return normalize(np.asarray(reduced, dtype=np.float32))


def _spectral(affinity: np.ndarray, k: int, seed: int) -> np.ndarray:
    safe = np.clip(np.asarray(affinity, dtype=np.float64), 0.0, 1.0)
    np.fill_diagonal(safe, 1.0)
    return SpectralClustering(
        n_clusters=k,
        affinity="precomputed",
        assign_labels="cluster_qr",
        random_state=seed,
    ).fit_predict(safe)


def _stability(affinity: np.ndarray, labels: np.ndarray, k: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    scores = []
    for _ in range(3):
        jitter = rng.normal(0.0, 0.002, size=affinity.shape)
        jitter = (jitter + jitter.T) / 2.0
        perturbed = np.clip(affinity + jitter, 0.0, 1.0)
        np.fill_diagonal(perturbed, 1.0)
        scores.append(adjusted_rand_score(labels, _spectral(perturbed, k, seed)))
    return float(np.mean(scores))


def _candidate(
    sparse_matrix: csr_matrix,
    compact: np.ndarray,
    affinity: np.ndarray,
    *,
    method: str,
    k: int,
    min_cluster_size: int,
    seed: int,
) -> Candidate:
    if method == "kmeans":
        labels = KMeans(n_clusters=k, n_init=40, random_state=seed).fit_predict(sparse_matrix)
        used = "kmeans_sparse"
        stability = None
    else:
        labels = _spectral(affinity, k, seed)
        used = "spectral_sparse_graph"
        stability = _stability(affinity, labels, k, seed)
    silhouette = float(silhouette_score(compact, labels, metric="cosine"))
    counts = Counter(labels.tolist())
    balance = float(min(counts.values()) / max(counts.values()))
    undersized = sum(value for value in counts.values() if value < min_cluster_size) / len(labels)
    stability_part = 0.0 if stability is None else stability
    score = 0.60 * silhouette + 0.25 * stability_part + 0.15 * balance - 0.60 * undersized
    warnings = []
    if undersized:
        warnings.append(
            f"{round(undersized * len(labels))} documents belong to clusters smaller than "
            f"minimum_cluster_size={min_cluster_size}."
        )
    return Candidate(
        labels=np.asarray(labels, dtype=int),
        requested=method,
        used=used,
        k=k,
        silhouette=silhouette,
        stability=stability,
        balance=balance,
        undersized_document_ratio=float(undersized),
        selection_score=float(score),
        warnings=warnings,
    )


def cluster_technical_sparse(
    sparse_matrix: csr_matrix,
    papers: Sequence[dict[str, Any]],
    views: Sequence[str],
    evidence: Sequence[Sequence[str]],
    *,
    algorithm: str = "auto",
    cluster_count: int | None = None,
    min_cluster_size: int = 2,
    similarity_threshold: float | None = None,
    random_state: int = 42,
) -> dict[str, Any]:
    """Cluster the technical axis using native sparse lexical weights."""
    n = len(papers)
    if n < 2:
        raise ValueError("Sparse technical clustering requires at least two documents.")
    compact = _compact(sparse_matrix, random_state)
    affinity = (sparse_matrix @ sparse_matrix.T).toarray()
    requested = algorithm.lower()
    if requested in {"agglomerative", "hierarchical", "hdbscan"}:
        chosen = _choose_candidate(
            compact, requested, cluster_count, min_cluster_size,
            similarity_threshold, random_state,
        )
        chosen.used = f"{chosen.used}_on_sparse_svd"
    else:
        method = "kmeans" if requested == "kmeans" else "spectral"
        if cluster_count is not None:
            ks = [max(2, min(int(cluster_count), n - 1))]
        else:
            upper = min(n - 1, max(2, min(12, round(math.sqrt(n) * 2))))
            ks = list(range(2, upper + 1))
        candidates = [
            _candidate(
                sparse_matrix, compact, affinity,
                method=method, k=k, min_cluster_size=min_cluster_size, seed=random_state,
            )
            for k in ks
        ]
        chosen = max(candidates, key=lambda item: (item.selection_score, item.stability or -1.0, -item.k))
    result = format_axis_result(
        compact, papers, views, evidence, axis="technical", candidate=chosen,
    )
    result["quality"]["representation"] = "bge-m3-native-sparse-head"
    result["quality"]["graph_affinity"] = "sparse_cosine"
    return result
