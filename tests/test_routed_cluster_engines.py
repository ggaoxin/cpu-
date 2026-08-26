from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score

from infrastructure.clustering.application_dense import (
    FACET_NAMES,
    WEIGHT_PROFILES,
    build_core3_representation,
    cluster_application_dense,
    encode_application_multiview,
)
from infrastructure.clustering.bge_m3_sparse import BgeM3SparseEncoder, cluster_technical_sparse


class CharEncoder:
    def encode(self, texts):
        return TfidfVectorizer(analyzer="char", ngram_range=(2, 4)).fit_transform(texts).toarray()


class WeightedSparseEncoder(BgeM3SparseEncoder):
    def __init__(self):
        pass

    def encode(self, texts):
        rows = []
        for text in texts:
            if "title" in text:
                rows.append([1.0, 0.0])
            elif "abstract" in text:
                rows.append([0.0, 1.0])
            else:
                rows.append([1.0, 1.0])
        return csr_matrix(rows, dtype=np.float32)


def test_sparse_source_weighting_uses_vector_fusion_not_text_repetition():
    matrix = WeightedSparseEncoder().encode_weighted_documents([[
        {"label": "title", "source_text": "title", "weight": 0.2},
        {"label": "abstract", "source_text": "abstract", "weight": 0.8},
    ]])
    row = matrix.toarray()[0]
    assert row[1] > row[0] * 3.5


def _papers():
    rows = []
    for method in range(3):
        for scenario in range(3):
            for repeat in range(2):
                rows.append({
                    "document_id": f"D{method}{scenario}{repeat}",
                    "title": f"method-{method} scenario-{scenario}",
                    "abstract": f"method-{method} is applied to scenario-{scenario}",
                    "keywords": [f"method-{method}", f"scenario-{scenario}"],
                    "language": "en",
                    "publication_year": 2024,
                    "published_at": "2024-01-01",
                })
    return rows


def _labels(result):
    ids = [item["topic_id"] for item in result["doc_axis_info"]]
    mapping = {value: index for index, value in enumerate(sorted(set(ids)))}
    return [mapping[value] for value in ids]


def test_sparse_technical_engine_uses_sparse_membership_and_stable_contract():
    papers = _papers()
    matrix = np.zeros((len(papers), 9), dtype=np.float32)
    expected = []
    for index in range(len(papers)):
        method = index // 6
        scenario = (index % 6) // 2
        matrix[index, method] = 4.0
        matrix[index, 3 + scenario] = 0.15
        matrix[index, 6 + (index % 2)] = 0.05
        expected.append(method)
    views = [paper["title"] for paper in papers]
    evidence = [[paper["title"]] for paper in papers]
    result = cluster_technical_sparse(
        csr_matrix(matrix), papers, views, evidence,
        algorithm="auto", cluster_count=3, min_cluster_size=2,
    )

    assert adjusted_rand_score(expected, _labels(result)) == 1.0
    assert result["quality"]["representation"] == "bge-m3-native-sparse-head"
    assert result["quality"]["algorithm_used"] == "spectral_sparse_graph"
    assert len(result["projection"]) == len(papers)
    assert all(item["key_evidence"] for item in result["doc_axis_info"])


def test_application_engine_clusters_faceted_dense_views_independently():
    papers = _papers()
    views = [f"application scenario-{(index % 6) // 2}" for index in range(len(papers))]
    facets = []
    expected = []
    for index in range(len(papers)):
        scenario = (index % 6) // 2
        expected.append(scenario)
        facets.append({
            "domain": [f"domain-{scenario}"],
            "object": [f"object-{scenario}"],
            "problem": [f"problem-{scenario}"],
            "task": [f"task-{scenario}"],
            "environment": [],
            "general": [views[index]],
        })
    matrix, metadata = encode_application_multiview(CharEncoder(), views, facets)
    result = cluster_application_dense(
        matrix, papers, views, [[view] for view in views],
        algorithm="auto", cluster_count=3, min_cluster_size=2,
    )

    assert adjusted_rand_score(expected, _labels(result)) == 1.0
    assert metadata["representation"] == "bge-m3-application-v2-faceted-hybrid"
    assert result["quality"]["algorithm_used"] == "spectral_local_graph_application_v2"
    weights = metadata["facet_weights"]
    assert tuple(weights) == FACET_NAMES
    assert weights["domain"] + weights["object"] > weights["task"] + weights["general"]


def test_application_v2_weight_profiles_are_small_and_semantically_bounded():
    assert len(WEIGHT_PROFILES) == 4
    for weights in WEIGHT_PROFILES.values():
        assert tuple(weights) == FACET_NAMES
        assert abs(sum(weights.values()) - 1.0) < 1e-9
        assert weights["domain"] + weights["object"] >= 0.45
        assert weights["task"] <= 0.12


def test_core3_representation_uses_only_domain_object_problem():
    papers = _papers()
    views = [f"scenario-{(index % 6) // 2}" for index in range(len(papers))]
    facets = []
    for index in range(len(papers)):
        scenario = (index % 6) // 2
        facets.append({
            "domain": [f"domain-{scenario}"],
            "object": [f"object-{scenario}"],
            "problem": [f"problem-{scenario}"],
            "task": [f"noisy-task-{index}"],
            "environment": [f"noisy-environment-{index}"],
        })
    matrix, affinity, metadata = build_core3_representation(CharEncoder(), views, facets)
    assert matrix.shape[0] == len(papers)
    assert affinity.shape == (len(papers), len(papers))
    assert metadata["representation"] == "bge-m3-application-core3-concat"
    assert metadata["facets"] == ["domain", "object", "problem"]
    assert abs(sum(metadata["facet_weights"].values()) - 1.0) < 1e-9


def test_core3_auto_k_uses_louvain_and_returns_stable_contract():
    papers = _papers()
    views = [f"application scenario-{(index % 6) // 2}" for index in range(len(papers))]
    facets = []
    for index in range(len(papers)):
        scenario = (index % 6) // 2
        facets.append({
            "domain": [f"domain-{scenario}"],
            "object": [f"object-{scenario}"],
            "problem": [f"problem-{scenario}"],
        })
    matrix, affinity, metadata = build_core3_representation(CharEncoder(), views, facets)
    result = cluster_application_dense(
        matrix,
        papers,
        views,
        [[view] for view in views],
        affinity=affinity,
        representation=metadata,
        algorithm="auto",
        cluster_count=None,
        min_cluster_size=2,
        configured_method="core3_spectral_local_graph",
    )
    assert result["quality"]["representation"] == "bge-m3-application-core3-concat"
    assert result["quality"]["algorithm_used"] == "louvain_symmetric_knn_application_core3"
    assert result["quality"]["auto_k_selection"] == "louvain_symmetric_knn"
    assert result["quality"]["cluster_count"] >= 2
    assert len(result["doc_axis_info"]) == len(papers)
