"""Evidence-grounded cluster label generation package."""

from .engine import ClusterLabelGenerator, generate_cluster_labels
from .factory import (
    DEFAULT_LABEL_ENGINE_MODE,
    SUPPORTED_LABEL_ENGINE_MODES,
    create_cluster_label_generator,
    normalize_label_engine_mode,
)
from .semantic_engine import SemanticClusterLabelGenerator
from .soft_fallback_engine import SoftFallbackClusterLabelGenerator

__all__ = [
    "ClusterLabelGenerator",
    "DEFAULT_LABEL_ENGINE_MODE",
    "SUPPORTED_LABEL_ENGINE_MODES",
    "SemanticClusterLabelGenerator",
    "SoftFallbackClusterLabelGenerator",
    "create_cluster_label_generator",
    "generate_cluster_labels",
    "normalize_label_engine_mode",
]

