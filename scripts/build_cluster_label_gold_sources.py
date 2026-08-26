"""Build auditable phrase-set sources for manual cluster-label Gold review.

This file is evaluation-only.  The selectors create semantically coherent test
clusters from the two supplied JSON corpora; they are never imported by the
production label generator and are not a production topic library.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any


TECHNOLOGY_GROUPS = [
    ("T-ZH-01", "zh", ["空间杜宾", "空间计量", "空间溢出效应", "esda", "地理探测器"]),
    ("T-ZH-02", "zh", ["鲁棒优化", "分布鲁棒", "随机优化", "多目标优化", "优化调度"]),
    ("T-ZH-03", "zh", ["故障诊断", "故障定位", "异常检测", "状态评价", "故障检测"]),
    ("T-ZH-04", "zh", ["模型预测控制", "滑模控制", "虚拟阻抗", "虚拟同步机", "控制策略", "稳定性分析"]),
    ("T-ZH-05", "zh", ["深度学习", "transformer", "神经网络", "卷积网络", "图神经网络"]),
    ("T-ZH-06", "zh", ["复杂网络", "社会网络分析", "网络结构", "关联网络", "创新网络"]),
    ("T-ZH-07", "zh", ["综合评价", "评价指标", "耦合协调", "熵权", "topsis"]),
    ("T-ZH-08", "zh", ["数字孪生", "有限元", "数值模拟", "仿真分析", "仿真模型"]),
    ("T-EN-01", "en", ["systematic review", "meta-analysis"]),
    ("T-EN-02", "en", ["randomized controlled trial", "randomised controlled trial", "clinical trial"]),
    ("T-EN-03", "en", ["cox regression", "nomogram", "prognostic model", "survival analysis"]),
    ("T-EN-04", "en", ["density functional theory", "molecular dynamics", "first-principles"]),
    ("T-EN-05", "en", ["spectroscopy", "microscopy", "x-ray diffraction", "raman"]),
    ("T-EN-06", "en", ["deep learning", "machine learning", "neural network", "transformer"]),
    ("T-EN-07", "en", ["finite element", "computational simulation", "numerical simulation"]),
    ("T-EN-08", "en", ["self-assembly", "hydrothermal synthesis", "sol-gel", "synthesized", "synthesis"]),
]

APPLICATION_GROUPS = [
    ("A-ZH-01", "zh", ["配电网", "电力系统", "综合能源系统", "微电网", "风电"]),
    ("A-ZH-02", "zh", ["区域经济", "共同富裕", "城镇化", "城市群", "经济增长"]),
    ("A-ZH-03", "zh", ["旅游", "文化遗产", "景区"]),
    ("A-ZH-04", "zh", ["农业", "乡村振兴", "农村", "耕地", "粮食"]),
    ("A-ZH-05", "zh", ["城市交通", "国土空间", "城市规划", "城市更新", "公共交通"]),
    ("A-ZH-06", "zh", ["制造业", "智能制造", "工业企业", "质量检测", "生产系统"]),
    ("A-ZH-07", "zh", ["公共卫生", "医疗", "养老", "疾病防控", "照护", "卫生健康"]),
    ("A-ZH-08", "zh", ["生态环境", "碳中和", "绿色发展", "生态保护", "污染"]),
    ("A-EN-01", "en", ["cancer", "tumor", "carcinoma", "oncology"]),
    ("A-EN-02", "en", ["atrial fibrillation", "cardiac", "cardiovascular", "heart"]),
    ("A-EN-03", "en", ["covid-19", "infection", "infectious", "virus", "bacterial"]),
    ("A-EN-04", "en", ["alzheimer", "neurological", "brain", "depression", "schizophrenia"]),
    ("A-EN-05", "en", ["solar cell", "battery", "energy storage", "electrocatalyst", "hydrogen generation"]),
    ("A-EN-06", "en", ["climate change", "environmental", "pollution", "heavy metals", "conservation"]),
    ("A-EN-07", "en", ["fish", "zebrafish", "tilapia", "veterinary", "canine", "bovine", "sheep", "crayfish"]),
    ("A-EN-08", "en", ["medical imaging", "mri", "ultrasound", "surgical", "surgery"]),
]

GENERIC = {
    "study", "research", "analysis", "method", "methods", "model", "models", "result", "results",
    "研究", "分析", "方法", "模型", "结果", "影响因素", "中国",
}


def text_of(row: dict[str, Any], language: str) -> str:
    prefix = "ch" if language == "zh" else "en"
    title = str(row.get(f"{prefix}_name") or "")
    abstract = str(row.get(f"{prefix}_abstract") or "")
    keywords = " ".join(str(item) for item in row.get("keywords") or [])
    return f"{title} {abstract} {keywords}".casefold()


def title_of(row: dict[str, Any], language: str) -> str:
    return str(row.get("ch_name" if language == "zh" else "en_name") or "").strip()


def title_keyword_text(row: dict[str, Any], language: str) -> str:
    return (
        f"{title_of(row, language)} "
        + " ".join(str(item) for item in row.get("keywords") or [])
    ).casefold()


def build_axis(
    groups: list[tuple[str, str, list[str]]],
    chinese: list[dict[str, Any]],
    english: list[dict[str, Any]],
    *,
    maximum_documents: int,
    axis: str,
) -> dict[str, Any]:
    corpora = {"zh": chinese, "en": english}
    used = {"zh": set(), "en": set()}
    phrase_sets: list[dict[str, Any]] = []
    for cluster_id, language, selectors in groups:
        matches: list[tuple[int, dict[str, Any], list[str]]] = []
        for index, row in enumerate(corpora[language]):
            if index in used[language]:
                continue
            # Application identity must be explicit in the title or keywords;
            # an incidental abstract mention is not sufficient for Gold.
            text = title_keyword_text(row, language) if axis == "application" else text_of(row, language)
            hits = [term for term in selectors if term.casefold() in text]
            if hits:
                matches.append((index, row, hits))
        matches.sort(key=lambda item: (-len(item[2]), item[0]))
        selected = matches[:maximum_documents]
        if len(selected) < 3:
            raise ValueError(f"{cluster_id} has fewer than three source documents")
        used[language].update(index for index, _, _ in selected)

        keyword_df: Counter[str] = Counter()
        selector_df: Counter[str] = Counter()
        for _, row, hits in selected:
            keyword_df.update({str(value).strip() for value in row.get("keywords") or [] if str(value).strip()})
            selector_df.update(set(hits))
        ranked_keywords = [
            (value, count) for value, count in keyword_df.most_common()
            if value.casefold() not in GENERIC and len(value.strip()) >= 2
        ]
        ranked_selectors = sorted(selector_df.items(), key=lambda item: (-item[1], item[0]))
        phrases: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value, count in [*ranked_selectors, *ranked_keywords]:
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            phrases.append({
                "text": value,
                "frequency": count,
                "weight": round(0.55 + 0.45 * count / len(selected), 6),
                "source": "reviewed_json_evidence",
            })
            if len(phrases) == 12:
                break
        phrase_sets.append({
            "cluster_id": cluster_id,
            "language": language,
            "phrases": phrases,
            "document_count": len(selected),
            "evidence_documents": [{
                "document_id": f"{language}_{index + 1:04d}",
                "title": title_of(row, language),
                "matched_evidence": hits,
                "keywords": row.get("keywords") or [],
            } for index, row, hits in selected],
        })
    return {
        "construction": {
            "purpose": "manual_gold_source_only",
            "production_topic_library": False,
            "llm_used": False,
            "selection_note": "Evaluation-only evidence selectors; never imported by production code.",
        },
        "cluster_phrase_sets": phrase_sets,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chinese", type=Path, required=True)
    parser.add_argument("--english", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--maximum-documents", type=int, default=20)
    args = parser.parse_args()
    chinese = json.loads(args.chinese.read_text(encoding="utf-8"))
    english = json.loads(args.english.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for axis, groups in (("technology", TECHNOLOGY_GROUPS), ("application", APPLICATION_GROUPS)):
        payload = build_axis(
            groups, chinese, english,
            maximum_documents=args.maximum_documents,
            axis=axis,
        )
        payload["axis"] = axis
        payload["dataset"] = {"chinese_source_documents": len(chinese), "english_source_documents": len(english)}
        target = args.output_dir / f"{axis}_gold_sources.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"axis": axis, "clusters": len(payload["cluster_phrase_sets"]), "output": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
