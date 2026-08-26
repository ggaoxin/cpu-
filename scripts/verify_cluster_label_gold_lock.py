"""Verify that locked cluster-label Gold and its evidence sources are unchanged."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_ROOT = PROJECT_ROOT / "eval" / "cluster_labeling" / "gold"
SOURCE_ROOT = PROJECT_ROOT / "eval" / "cluster_labeling" / "gold_sources"


def main() -> None:
    lock = json.loads((GOLD_ROOT / "gold_lock_v1.json").read_text(encoding="utf-8"))
    for item in lock["files"]:
        path = PROJECT_ROOT / item["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        if actual != item["sha256"]:
            raise ValueError(f"Gold hash mismatch: {path}")

    summary: dict[str, object] = {"hash_lock_valid": True, "axes": {}}
    for axis in ("technology", "application"):
        gold = json.loads((GOLD_ROOT / f"{axis}_gold_v1.json").read_text(encoding="utf-8"))
        source = json.loads((SOURCE_ROOT / f"{axis}_gold_sources.json").read_text(encoding="utf-8"))
        gold_items = {str(item["cluster_id"]): item for item in gold["items"]}
        source_items = {
            str(item["cluster_id"]): item for item in source["cluster_phrase_sets"]
        }
        if set(gold_items) != set(source_items):
            raise ValueError(f"{axis}: Gold/source cluster IDs differ")
        for cluster_id, item in gold_items.items():
            review = item.get("review", {})
            if review.get("status") != "approved" or int(review.get("rounds", 0)) < 3:
                raise ValueError(f"{cluster_id}: Gold is not approved through three rounds")
            evidence_ids = {
                str(row["document_id"])
                for row in source_items[cluster_id].get("evidence_documents", [])
            }
            unknown = set(map(str, item.get("evidence_document_ids", []))) - evidence_ids
            if unknown:
                raise ValueError(f"{cluster_id}: unknown evidence IDs {sorted(unknown)}")
        summary["axes"][axis] = {
            "cluster_count": len(gold_items),
            "approved_count": len(gold_items),
            "evidence_ids_valid": True,
        }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
