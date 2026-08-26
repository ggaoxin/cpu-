"""Run the production cluster-label engine on prepared phrase-set fixtures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.cluster_labeling import ClusterLabelGenerator
from infrastructure.rag.m3_encoder import m3_encoder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label-length-limit", type=int, default=12)
    parser.add_argument("--language-type", choices=("auto", "zh", "en"), default="auto")
    parser.add_argument("--distinctiveness-threshold", type=float, default=0.75)
    parser.add_argument("--use-glm", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    phrase_sets = payload.get("cluster_phrase_sets", payload)
    llm = None
    if args.use_glm:
        from infrastructure.llm.glm_client import glm_client

        llm = glm_client
    result = ClusterLabelGenerator(encoder=m3_encoder, llm_client=llm).generate(
        phrase_sets,
        label_length_limit=args.label_length_limit,
        language_type=args.language_type,
        distinctiveness_threshold=args.distinctiveness_threshold,
    )
    result["experiment_source"] = {
        "phrase_set_file": str(args.input),
        "axis": payload.get("axis"),
        "dataset": payload.get("dataset"),
        "deep_clustering_quality": payload.get("deep_clustering_quality"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "labels": len(result["labels"]),
        "average_confidence": result["generation_report"]["average_confidence"],
        "average_distinctiveness": result["generation_report"]["average_distinctiveness"],
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
