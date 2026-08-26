"""Dependency-light service orchestration self-test (no GLM and no model load)."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_deep_clustering_service import (  # noqa: E402
    test_application_route_runs_without_glm_and_reports_local_fallback,
    test_mixed_structured_and_plain_text_inputs_return_auditable_modes_and_trend,
)


if __name__ == "__main__":
    test_application_route_runs_without_glm_and_reports_local_fallback()
    test_mixed_structured_and_plain_text_inputs_return_auditable_modes_and_trend()
    print("DEEP_CLUSTERING_SERVICE_SELFTEST_PASS count=2 glm_used=false model_loaded=false")
