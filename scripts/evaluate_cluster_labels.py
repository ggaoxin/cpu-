"""Evaluate generated cluster labels against manually reviewed Gold labels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


_ZH = re.compile(r"[\u3400-\u9fff]")
_EN = re.compile(r"[a-z][a-z0-9+#.-]*", re.I)


def normalize(value: Any) -> str:
    text = str(value or "").casefold().strip()
    zh = "".join(_ZH.findall(text))
    if zh:
        return zh
    return " ".join(singular(token) for token in _EN.findall(text))


def singular(token: str) -> str:
    """Mirror the light English inflection normalization used by the engine."""
    value = token.casefold()
    if len(value) > 4 and value.endswith("ies"):
        return value[:-3] + "y"
    if len(value) > 4 and value.endswith("ses"):
        return value[:-2]
    if len(value) > 3 and value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


def contains_concept(label: str, concept: str, synonyms: dict[str, list[str]]) -> bool:
    haystack = normalize(label)
    variants = [concept, *synonyms.get(concept, [])]
    return any(normalize(value) and normalize(value) in haystack for value in variants)


def label_length(value: Any, language: str) -> int:
    """Use the same Chinese-character/English-word rule as the production engine."""
    text = str(value or "")
    if language == "en":
        return len(_EN.findall(text))
    return len(_ZH.findall(text)) + len(_EN.findall(text))


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    if not count:
        return {"cluster_count": 0}
    tp = sum(int(item["concept_tp"]) for item in rows)
    fp = sum(int(item["concept_fp"]) for item in rows)
    fn = sum(int(item["concept_fn"]) for item in rows)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    semantic_values = [float(item["semantic_similarity"]) for item in rows if item["semantic_similarity"] is not None]
    labels = [normalize(item["prediction"]) for item in rows]
    return {
        "cluster_count": count,
        "acceptable_top1_accuracy": round(sum(bool(item["acceptable_top1"]) for item in rows) / count, 6),
        "candidate_recall_at_5": round(sum(bool(item["candidate_recall_at_5"]) for item in rows) / count, 6),
        "required_concept_precision": round(precision, 6),
        "required_concept_recall": round(recall, 6),
        "required_concept_f1": round(f1, 6),
        "semantic_similarity_mean": round(sum(semantic_values) / len(semantic_values), 6) if semantic_values else None,
        "semantic_pass_rate": (
            round(sum(bool(item["semantic_pass"]) for item in rows) / len(semantic_values), 6)
            if semantic_values else None
        ),
        "length_compliance_rate": round(sum(bool(item["length_compliant"]) for item in rows) / count, 6),
        "evidence_grounding_rate": round(sum(bool(item["evidence_grounded"]) for item in rows) / count, 6),
        "distinctiveness_pass_rate": round(sum(bool(item["distinctiveness_pass"]) for item in rows) / count, 6),
        "duplicate_label_rate": round((len(labels) - len(set(labels))) / count, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument("--semantic-threshold", type=float, default=0.82)
    args = parser.parse_args()

    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    gold_payload = json.loads(args.gold.read_text(encoding="utf-8"))
    gold_items = gold_payload.get("items", [])
    pred_by_id = {str(item["cluster_id"]): item for item in predictions.get("labels", [])}
    gold_by_id = {str(item["cluster_id"]): item for item in gold_items}
    if set(pred_by_id) != set(gold_by_id):
        missing = sorted(set(gold_by_id) - set(pred_by_id))
        extra = sorted(set(pred_by_id) - set(gold_by_id))
        raise ValueError(f"Gold/prediction cluster IDs differ; missing={missing}, extra={extra}")
    if not all(item.get("review", {}).get("status") == "approved" for item in gold_items):
        raise ValueError("Every Gold item must have review.status=approved")
    if not all(int(item.get("review", {}).get("rounds", 0)) >= 3 for item in gold_items):
        raise ValueError("Every Gold item must record at least three review rounds")
    length_limit = int(
        predictions.get("generation_report", {})
        .get("parameters", {})
        .get("label_length_limit", 12)
    )

    semantic_scores: dict[str, float] = {}
    if args.semantic:
        import numpy as np
        from infrastructure.rag.m3_encoder import m3_encoder

        ordered = sorted(gold_by_id)
        texts = [pred_by_id[key]["label"] for key in ordered] + [gold_by_id[key]["gold_label"] for key in ordered]
        vectors = m3_encoder.encode(texts)
        count = len(ordered)
        for index, key in enumerate(ordered):
            semantic_scores[key] = float(np.dot(vectors[index], vectors[index + count]))

    rows: list[dict[str, Any]] = []
    for cluster_id in sorted(gold_by_id):
        pred = pred_by_id[cluster_id]
        gold = gold_by_id[cluster_id]
        accepted = {normalize(gold["gold_label"]), *[normalize(value) for value in gold.get("acceptable_labels", [])]}
        label = pred["label"]
        candidates = [label, *pred.get("candidate_labels", [])]
        exact = normalize(label) in accepted
        candidate_hit = any(normalize(value) in accepted for value in candidates[:5])
        synonyms = gold.get("concept_synonyms", {})
        required = gold.get("required_concepts", [])
        matched = [concept for concept in required if contains_concept(label, concept, synonyms)]
        forbidden = gold.get("forbidden_concepts", [])
        forbidden_hits = [concept for concept in forbidden if contains_concept(label, concept, synonyms)]
        tp = len(matched)
        fn = max(0, len(required) - tp)
        fp = len(forbidden_hits)
        semantic_score = semantic_scores.get(cluster_id)
        semantic_pass = semantic_score is not None and semantic_score >= args.semantic_threshold
        language = str(pred.get("language") or "zh")
        measured_length = label_length(label, language)
        row = {
            "cluster_id": cluster_id,
            "split": gold.get("split", "development"),
            "prediction": label,
            "gold_label": gold["gold_label"],
            "acceptable_top1": exact,
            "candidate_recall_at_5": candidate_hit,
            "matched_required_concepts": matched,
            "missing_required_concepts": sorted(set(required) - set(matched)),
            "forbidden_concept_hits": forbidden_hits,
            "semantic_similarity": None if semantic_score is None else round(semantic_score, 6),
            "semantic_pass": semantic_pass if semantic_score is not None else None,
            "label_length": measured_length,
            "label_length_limit": length_limit,
            "length_compliant": 0 < measured_length <= length_limit,
            "evidence_grounded": bool(pred.get("evidence_terms")),
            "distinctiveness_pass": bool(pred.get("optimization", {}).get("threshold_passed")),
            "concept_tp": tp,
            "concept_fp": fp,
            "concept_fn": fn,
        }
        rows.append(row)
    metrics = aggregate(rows)
    split_metrics = {
        split: aggregate([item for item in rows if item["split"] == split])
        for split in sorted({item["split"] for item in rows})
    }
    report = {
        "evaluation_contract": "manual_three_round_cluster_label_gold_v1",
        "cluster_count": len(rows),
        "metrics": metrics,
        "metrics_by_split": split_metrics,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
