"""Create realistic cluster phrase-set fixtures from the two 1,000-paper JSON files.

This script calls the project's topic-library-free deep-clustering service.  It
uses local axis extraction so that the experiment does not require an LLM.  The
output is the exact phrase-set contract consumed by the label generator.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import random
import sys


@dataclass
class FunctionalPoint:
    name: str = "Deep Clustering Evaluation"


class NoNetworkLLM:
    def chat_json(self, *args, **kwargs):  # pragma: no cover - local mode must not call it
        raise RuntimeError("LLM must not be called in local axis-extraction mode")


def load_documents(
    chinese_path: Path,
    english_path: Path,
    sample_per_language: int | None,
) -> tuple[list[str], dict[str, int], dict[str, int]]:
    rows: list[dict] = []
    source_counts: dict[str, int] = {}
    rng = random.Random(42)
    for language, path in (("zh", chinese_path), ("en", english_path)):
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise ValueError(f"{path} must contain a JSON array")
        if sample_per_language is not None and sample_per_language < len(value):
            value = [value[index] for index in sorted(rng.sample(range(len(value)), sample_per_language))]
        source_counts[language] = len(value)
        rows.extend(item for item in value if isinstance(item, dict))
    documents: list[str] = []
    quality = {"missing_abstract": 0, "title_keyword_fallback": 0, "discarded_empty": 0}
    for index, row in enumerate(rows):
        normalized = dict(row)
        normalized.setdefault("id", f"paper_{index + 1:04d}")
        abstract = str(
            normalized.get("abstract") or normalized.get("ch_abstract")
            or normalized.get("en_abstract") or ""
        ).strip()
        if not abstract:
            quality["missing_abstract"] += 1
            title = str(normalized.get("title") or normalized.get("ch_name") or normalized.get("en_name") or "").strip()
            keywords = normalized.get("keywords") or []
            if not isinstance(keywords, list):
                keywords = [str(keywords)]
            source_text = "；".join([title, *[str(item).strip() for item in keywords if str(item).strip()]]).strip("；")
            if not source_text:
                quality["discarded_empty"] += 1
                continue
            normalized["text"] = source_text
            quality["title_keyword_fallback"] += 1
        documents.append(json.dumps(normalized, ensure_ascii=False))
    return documents, quality, source_counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--chinese", type=Path, required=True)
    parser.add_argument("--english", type=Path, required=True)
    parser.add_argument("--axis", choices=("technology", "application"), required=True)
    parser.add_argument("--cluster-count", type=int, default=12)
    parser.add_argument("--sample-per-language", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sys.path.insert(0, str(args.project))
    from application.dto.common_dto import SemanticRequest
    from application.service.deep_clustering_service import execute_deep_clustering

    documents, input_quality, source_counts = load_documents(
        args.chinese, args.english, args.sample_per_language
    )
    request = SemanticRequest(
        texts=documents,
        params={
            "cluster_dimension": args.axis,
            "algorithm": "kmeans",
            "cluster_count": args.cluster_count,
            "minimum_cluster_size": 4,
            "axis_extraction": "local",
            "rule_mode": "off",
            "random_state": 42,
        },
    )
    result = execute_deep_clustering("dc_cluster", request, FunctionalPoint(), NoNetworkLLM())
    if not result.success:
        raise RuntimeError(result.error or "deep clustering failed")
    data = result.data
    cluster_key = "application_topics" if args.axis == "application" else "technical_topics"
    clusters = data[cluster_key]
    phrase_sets = [{
        "cluster_id": item["cluster_id"],
        "language": "auto",
        "phrases": [
            {"text": phrase, "weight": max(0.2, 1.0 - rank * 0.07), "frequency": 1}
            for rank, phrase in enumerate(item.get("representative_terms", [])[:12])
        ],
        "document_count": item.get("size", 0),
        "representative_documents": item.get("representative_documents", []),
        "feature_statistics": item.get("feature_statistics", {}),
    } for item in clusters if item.get("cluster_id") != "OUTLIER"]
    payload = {
        "dataset": {
            "chinese_documents": source_counts["zh"],
            "english_documents": source_counts["en"],
            "combined_documents": len(documents),
            "input_quality": input_quality,
        },
        "axis": args.axis,
        "deep_clustering_quality": data.get("clustering_quality", {}),
        "cluster_phrase_sets": phrase_sets,
        "source_clusters": clusters,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "axis": args.axis,
        "documents": len(documents),
        "clusters": len(phrase_sets),
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
