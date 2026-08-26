"""Dependency-light self-test for the dual-axis evidence-rule extension."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests.test_evidence_rule_engine as tests


def main() -> None:
    functions = [
        getattr(tests, name)
        for name in sorted(dir(tests))
        if name.startswith("test_") and callable(getattr(tests, name))
    ]
    for function in functions:
        function()
        print(f"PASS {function.__name__}", flush=True)
    print(f"DUAL_AXIS_RULE_SELFTEST_PASS count={len(functions)}", flush=True)


if __name__ == "__main__":
    main()
