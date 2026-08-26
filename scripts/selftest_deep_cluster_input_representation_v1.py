"""Dependency-light runner for the deep-clustering input representation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests.test_deep_cluster_input_representation as tests


def main() -> None:
    functions = [
        getattr(tests, name) for name in sorted(dir(tests))
        if name.startswith("test_") and callable(getattr(tests, name))
    ]
    for function in functions:
        function()
        print(f"PASS {function.__name__}", flush=True)
    print(f"DEEP_CLUSTER_INPUT_REPRESENTATION_SELFTEST_PASS count={len(functions)}", flush=True)


if __name__ == "__main__":
    main()
