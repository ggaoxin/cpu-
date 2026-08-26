"""Cluster-label engine selection for the application layer.

V11 is the production default.  V10 is retained as a rule-free semantic
baseline, while the former evidence-v2 engine remains available only for
backward-compatible replay of historical jobs.
"""
from __future__ import annotations

from typing import Any

from .engine import ClusterLabelGenerator
from .semantic_engine import SemanticClusterLabelGenerator
from .soft_fallback_engine import SoftFallbackClusterLabelGenerator


DEFAULT_LABEL_ENGINE_MODE = "bounded_soft_fallback"
SUPPORTED_LABEL_ENGINE_MODES = (
    "bounded_soft_fallback",
    "semantic_only",
    "legacy_evidence_v2",
)

_MODE_ALIASES = {
    "": DEFAULT_LABEL_ENGINE_MODE,
    "default": DEFAULT_LABEL_ENGINE_MODE,
    "soft_fallback": DEFAULT_LABEL_ENGINE_MODE,
    "bounded_soft_fallback": DEFAULT_LABEL_ENGINE_MODE,
    "v11": DEFAULT_LABEL_ENGINE_MODE,
    "semantic": "semantic_only",
    "semantic_only": "semantic_only",
    "v10": "semantic_only",
    "legacy": "legacy_evidence_v2",
    "evidence_v2": "legacy_evidence_v2",
    "legacy_evidence_v2": "legacy_evidence_v2",
}


def normalize_label_engine_mode(value: Any) -> str:
    """Return a canonical, auditable engine mode."""
    requested = str(value or "").strip().lower().replace("-", "_")
    mode = _MODE_ALIASES.get(requested)
    if mode is None:
        supported = "、".join(SUPPORTED_LABEL_ENGINE_MODES)
        raise ValueError(f"label_engine_mode 必须为：{supported}。")
    return mode


def create_cluster_label_generator(
    *,
    mode: Any = DEFAULT_LABEL_ENGINE_MODE,
    encoder: Any,
    llm_client: Any = None,
) -> Any:
    """Create the selected engine without changing its output contract."""
    canonical = normalize_label_engine_mode(mode)
    if canonical == "bounded_soft_fallback":
        return SoftFallbackClusterLabelGenerator(encoder=encoder, llm_client=llm_client)
    if canonical == "semantic_only":
        return SemanticClusterLabelGenerator(encoder=encoder, llm_client=llm_client)
    return ClusterLabelGenerator(encoder=encoder, llm_client=llm_client)


__all__ = [
    "DEFAULT_LABEL_ENGINE_MODE",
    "SUPPORTED_LABEL_ENGINE_MODES",
    "create_cluster_label_generator",
    "normalize_label_engine_mode",
]
