"""Dependency-light production routing self-test for the two deep-cluster axes."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_test_module():
    path = ROOT / "tests" / "test_routed_cluster_engines.py"
    spec = importlib.util.spec_from_file_location("dual_axis_production_tests", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load production tests: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = _load_test_module()
    names = [name for name in dir(module) if name.startswith("test_")]
    for name in sorted(names):
        getattr(module, name)()
        print(f"PASS {name}")
    print(f"DUAL_AXIS_PRODUCTION_SELFTEST_PASS count={len(names)}")


if __name__ == "__main__":
    main()
