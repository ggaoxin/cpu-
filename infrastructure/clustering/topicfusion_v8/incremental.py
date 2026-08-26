from __future__ import annotations

import ast
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score


def _keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [x.strip() for x in re.split(r"[;,；，|]", value) if x.strip()]
    return []


def _candidate_rows(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        records = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        return pd.DataFrame(records)
    if p.suffix.lower() == ".json":
        obj = json.loads(p.read_text(encoding="utf-8"))
        return pd.DataFrame(obj if isinstance(obj, list) else obj.get("documents", obj.get("data", [])))
    return pd.read_csv(p)


def _axis_text(row: pd.Series, axis: str) -> str:
    title = str(row.get("title", ""))
    keywords = " ".join(_keywords(row.get("keywords", [])))
    view = str(row.get(f"{axis}_route_text" if axis == "technical" else "application_scenario_text", ""))
    if axis == "technical":
        view = str(row.get("technical_route_text", view))
        return f"{view} {keywords}"
    return f"{title} {title} {keywords} {view}"


def _choose_k(matrix, n: int, random_state: int) -> int:
    if n < 2:
        return 1
    maximum = min(6, max(2, n // 4))
    candidates = [k for k in range(2, maximum + 1) if n >= 3 * k]
    if not candidates:
        return 1
    best_k, best_score = 1, -1.0
    for k in candidates:
        labels = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit_predict(matrix)
        if np.bincount(labels).min() < 3:
            continue
        score = float(silhouette_score(matrix, labels, metric="cosine")) - 0.015 * (k - 2)
        if score > best_score:
            best_k, best_score = k, score
    return best_k


def _name_cluster(group: pd.DataFrame, indexes: np.ndarray, language: str) -> tuple[str, list[str]]:
    counter: Counter[str] = Counter()
    for _, row in group.iloc[indexes].iterrows():
        for term in _keywords(row.get("keywords", [])):
            term = re.sub(r"\s+", " ", term).strip()
            if len(term) >= (2 if language == "zh" else 3):
                counter[term.lower() if language == "en" else term] += 2
        title = str(row.get("title", ""))
        if language == "zh":
            for term in re.findall(r"[\u4e00-\u9fffA-Za-z0-9-]{3,12}", title):
                if term not in {"基于", "研究", "分析", "方法", "模型", "系统", "技术"}:
                    counter[term] += 1
        else:
            for term in re.findall(r"\b[A-Za-z][A-Za-z-]{3,}\b", title):
                if term.lower() not in {"using", "based", "study", "method", "model", "analysis"}:
                    counter[term.lower()] += 1
    evidence = [x for x, count in counter.most_common(8) if count >= 2]
    if not evidence:
        evidence = [x for x, _ in counter.most_common(5)]
    if language == "zh":
        name = "、".join(evidence[:3]) or "待命名候选主题"
    else:
        name = " / ".join(x.title() for x in evidence[:3]) or "Unnamed Candidate Topic"
    return name, evidence


def propose_incremental_topics(
    candidate_file: str | Path,
    output_file: str | Path,
    min_support: int = 12,
    random_state: int = 42,
) -> Path:
    """Group open-set candidates and propose new fine topics without committing them.

    Only groups with at least ``min_support`` documents under the same axis, language,
    and v7 parent category are eligible. The result is a review queue, not an automatic
    modification of the production mapping tables.
    """
    df = _candidate_rows(candidate_file)
    proposals: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []

    for axis in ("technical", "application"):
        status_col = f"{axis}_mapping_status"
        parent_col = f"{axis}_parent_id"
        if status_col not in df or parent_col not in df:
            continue
        subset = df[df[status_col] == "candidate_new_topic"].copy()
        for (language, parent_id), group in subset.groupby(["language", parent_col]):
            group = group.reset_index(drop=True)
            if len(group) < min_support:
                continue
            texts = [_axis_text(row, axis) for _, row in group.iterrows()]
            analyzer = "char" if language == "zh" else "word"
            ngram_range = (2, 5) if language == "zh" else (1, 2)
            vectorizer = TfidfVectorizer(
                analyzer=analyzer,
                ngram_range=ngram_range,
                min_df=2,
                max_features=8000,
                sublinear_tf=True,
                stop_words="english" if language == "en" else None,
            )
            matrix = vectorizer.fit_transform(texts)
            k = _choose_k(matrix, len(group), random_state)
            labels = np.zeros(len(group), dtype=int) if k == 1 else KMeans(
                n_clusters=k, n_init=20, random_state=random_state
            ).fit_predict(matrix)

            for cluster_id in sorted(set(labels)):
                indexes = np.where(labels == cluster_id)[0]
                if len(indexes) < max(5, min_support // 3):
                    continue
                name, evidence = _name_cluster(group, indexes, str(language))
                proposal_id = f"CAND-{axis[:2].upper()}-{parent_id}-{str(language).upper()}-{cluster_id + 1:03d}"
                documents = group.iloc[indexes]
                proposals.append({
                    "proposal_id": proposal_id,
                    "axis": axis,
                    "language": str(language),
                    "parent_category_id": str(parent_id),
                    "proposed_name": name,
                    "positive_evidence": evidence,
                    "support_count": int(len(indexes)),
                    "prototype_document_ids": documents["document_id"].astype(str).head(5).tolist(),
                    "prototype_titles": documents.get("title", pd.Series(dtype=str)).astype(str).head(5).tolist(),
                    "status": "candidate_for_human_review",
                    "commit_policy": "manual_review_required",
                })
                for _, row in documents.iterrows():
                    assignments.append({
                        "document_id": str(row.get("document_id", "")),
                        "proposal_id": proposal_id,
                        "axis": axis,
                        "language": str(language),
                        "parent_category_id": str(parent_id),
                    })

    output = Path(output_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "8.0",
        "candidate_file": str(candidate_file),
        "min_support": min_support,
        "proposals": proposals,
        "assignments": assignments,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output
