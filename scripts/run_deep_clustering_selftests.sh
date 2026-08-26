#!/usr/bin/env bash
set -euo pipefail

python scripts/selftest_deep_cluster_contract_v1.py
python scripts/selftest_deep_cluster_input_representation_v1.py
python scripts/selftest_dual_axis_rules_v1.py
python scripts/selftest_dual_axis_production_v3.py
python scripts/selftest_deep_clustering_service.py

# Loads the existing BGE-M3 weights and runs both production routes. No GLM is
# called because the script forces axis_extraction=local.
python scripts/selftest_deep_clustering_local_model.py
