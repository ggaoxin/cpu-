"""Application-layer orchestration for the production dual-axis clusterer.

This module deliberately owns only deep clustering.  Keeping it separate from
``semantic_service.py`` prevents an algorithm replacement from changing any of
the already integrated move, classification, keyword, research-question or
citation features.
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from application.dto.common_dto import SemanticRequest
from config.settings import settings
from domain.entity.base import SemanticResult
from infrastructure.clustering.axis_router import run_selected_axis_clustering
from infrastructure.document_parser.document_parser import DocumentParser
from infrastructure.document_parser.upload_reader import extract_bytes
from infrastructure.rag.m3_encoder import m3_encoder


logger = logging.getLogger(__name__)

# 锚点行类目字段别名（语义名优先，编号 ID 兜底；与 build_anchor_profiles 的
# 读取顺序保持一致）
_ANCHOR_LABEL_KEYS = ("category", "category_id", "label", "class", "cluster", "cluster_name",
                      "topic", "technical_cluster_name", "application_cluster_name",
                      "人工标注类目标签", "人工标签", "标签", "类目", "分类", "所属类目", "类别",
                      "technical_cluster_id", "application_cluster_id")


def _anchor_label(row: dict[str, Any]) -> str:
    for key in _ANCHOR_LABEL_KEYS:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _join_anchor_rows(sample_rows: list[dict[str, Any]],
                      label_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """训练样本（编号+文本+题名）与人工标签（编号+类目）按编号关联成锚点行。

    兼容旧格式：行内自带类目的样本行、自带题名/文本的标签行都直接作锚点行。
    返回 (锚点行列表, 按编号关联成功的条数)。
    """
    label_by_id = {str(r.get("document_id") or "").strip(): _anchor_label(r)
                   for r in label_rows if r.get("document_id") and _anchor_label(r)}
    anchors = [r for r in label_rows if not r.get("document_id") and _anchor_label(r)]
    joined = 0
    for row in sample_rows:
        label = _anchor_label(row)
        if not label:
            rid = str(row.get("document_id") or "").strip()
            label = label_by_id.get(rid, "")
            if label:
                joined += 1
                anchors.append({**row, "category": label})
        else:
            anchors.append(row)
    return anchors, joined
ALLOWED_ALGORITHMS = {
    "auto", "kmeans", "spectral", "agglomerative", "hierarchical", "hdbscan",
}
# 契约字段 clustering_algorithm_type 的取值归一：前端下拉 historically 发中文
# 标签（"自动选择"/"层次聚类"），此处统一映射为引擎标识，字段名也一并兼容。
_ALGORITHM_ALIASES = {
    "auto": "auto", "自动选择": "auto", "自动": "auto", "": "auto",
    "kmeans": "kmeans", "k-means": "kmeans", "k-means++": "kmeans",
    "spectral": "spectral", "谱聚类": "spectral",
    "agglomerative": "agglomerative", "凝聚聚类": "agglomerative",
    "hierarchical": "hierarchical", "层次聚类": "hierarchical",
    "hdbscan": "hdbscan",
}

_PUBLICATION_DATE = re.compile(
    r"(?:发表时间|发布日期|出版日期|publication\s+date|published|publication)"
    r"[^\d]{0,24}((?:19|20)\d{2}(?:[-/.年](?:0?[1-9]|1[0-2])"
    r"(?:[-/.月](?:3[01]|[12]\d|0?[1-9])日?)?)?)",
    re.IGNORECASE,
)


def _publication_date_from_text(text: str) -> str | None:
    """Extract only a date with an explicit publication-context label."""
    match = _PUBLICATION_DATE.search(str(text or "")[:4000])
    return match.group(1) if match else None


def _year_of(value: Any) -> int | None:
    """publication_date → 年份（'2026-01-01'/'2026年3月'/2026 → 2026）。"""
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def _trend_summary(years: list, series: list, rising: str | None,
                  emerging: str | None, stable: str | None) -> str:
    """趋势摘要：解析上升/新兴/稳定类簇并给出可读结论（供决策参考）。"""
    if not years:
        return ""
    span = f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0])
    count_of = {r["cluster_id"]: sum(r["yearly_counts"]) for r in series}

    def describe(cid: str | None, label: str, detail: str) -> str | None:
        if not cid:
            return None
        n = count_of.get(cid, 0)
        return f"{label}类簇 {cid}（{detail}，{n} 篇）"

    parts = [
        x for x in (
            describe(rising, "上升", "近年增长最快"),
            describe(emerging, "新兴", "新出现的主题方向"),
            describe(stable, "稳定", "各年份持续产出"),
        ) if x
    ]
    if not parts:
        return f"{span} 年间各主题分布均衡，无明显上升或新兴趋势。"
    return f"{span} 年间趋势：" + "；".join(parts) + "。"


def _trend_analysis(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Build factual year×cluster counts; dates never affect membership."""
    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for document in documents:
        year = document.get("publication_year")
        cluster_id = (document.get("technical") or document.get("application") or {}).get("topic_id")
        if isinstance(year, int) and cluster_id:
            counts[year][cluster_id] += 1
    if not counts:
        return {}
    years = sorted(counts)
    cluster_ids = sorted({cluster_id for row in counts.values() for cluster_id in row})
    series = [{
        "cluster_id": cluster_id,
        "yearly_counts": [counts[year].get(cluster_id, 0) for year in years],
    } for cluster_id in cluster_ids]
    rising = emerging = stable = None
    for row in series:
        values = row["yearly_counts"]
        midpoint = max(1, len(values) // 2)
        early, late = sum(values[:midpoint]), sum(values[midpoint:])
        if emerging is None and early == 0 and late > 0:
            emerging = row["cluster_id"]
        elif rising is None and late > early:
            rising = row["cluster_id"]
        elif stable is None and late == early and late > 0:
            stable = row["cluster_id"]
    return {
        "years": years,
        "series": series,
        "rising_cluster_id": rising,
        "emerging_cluster_id": emerging,
        "stable_cluster_id": stable,
        "summary": _trend_summary(years, series, rising, emerging, stable),
    }


def _input_documents(values: list[Any]) -> list[dict[str, Any] | str]:
    """Recover structured text or parse a local file without changing API fields."""
    documents: list[dict[str, Any] | str] = []
    parser = DocumentParser()
    for value in values:
        # 字符串若为 JSON 对象，先转为 dict，统一走下方 dict 处理。
        # 此前 JSON 字符串经 json.loads 成 dict 后被直接 append，导致 file_path
        # 字段携带的本地文件路径从未被 extract_bytes 解析，文本为空（deep-cluster
        # 批量上传全部“文本为空”500 的根因）。
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("{"):
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError:
                    pass
        if isinstance(value, dict):
            file_path = str(value.get("file_path") or "").strip()
            path = Path(file_path) if file_path else None
            if path and path.is_file():
                full_text = extract_bytes(path.read_bytes(), path.name, light=settings.should_use_light("deep-cluster"))
                parsed = parser.parse_text(full_text, path)
                documents.append({
                    **value,
                    "id": value.get("document_id") or value.get("id") or path.stem,
                    "title": value.get("title") or parsed.get("title") or "",
                    "abstract": parsed.get("abstract") or "",
                    "keywords": value.get("keywords") or parsed.get("keywords") or [],
                    "full_text": full_text,
                    "publication_date": value.get("publication_date") or _publication_date_from_text(full_text),
                })
            else:
                row = dict(value)
                # 批量文本模式合并元数据后只有 text 键，而语步提取读 full_text/
                # abstract——不映射的话提取拿到空文本，聚类退化为仅按题名分组
                # （簇名=题名、每簇只剩 1 个短语）。这里统一补 full_text。
                if not str(row.get("full_text") or "").strip() and not str(row.get("abstract") or "").strip():
                    body = str(row.get("text") or row.get("content") or "").strip()
                    if body:
                        row["full_text"] = body
                documents.append(row)
            continue
        raw = str(value or "").strip()
        path = Path(raw)
        try:
            is_file = bool(raw) and len(raw) < 2048 and path.is_file()
        except OSError:
            is_file = False
        if is_file:
            full_text = extract_bytes(path.read_bytes(), path.name, light=settings.should_use_light("deep-cluster"))
            parsed = parser.parse_text(full_text, path)
            documents.append({
                "id": path.stem,
                "title": parsed.get("title") or "",
                "abstract": parsed.get("abstract") or "",
                "keywords": parsed.get("keywords") or [],
                "full_text": full_text,
                "publication_date": _publication_date_from_text(full_text),
            })
        else:
            # 纯字符串文献（API 直传 texts=["...", ...]，非 JSON 序列化 dict）：
            # 同样补 full_text 映射——语步提取只读 full_text/abstract/title，
            # 只给 text 键会拿到空文本，聚类退化为"空文献集"单簇（部署实测回归）
            documents.append({"text": raw, "full_text": raw})
    return documents


def _optional_float(params: dict[str, Any], name: str) -> float | None:
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是数值。") from exc
    if not 0 <= parsed <= 1:
        raise ValueError(f"{name} 必须在0到1之间。")
    return parsed


def _optional_cluster_count(params: dict[str, Any]) -> int | None:
    value = params.get("cluster_count")
    if value in (None, "", "auto", 0, "0"):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("cluster_count 必须为大于等于2的整数或 auto。") from exc
    if parsed < 2:
        raise ValueError("cluster_count 必须大于等于2。")
    return parsed


def _document_digest(mv: dict[str, Any], limit: int = 1200) -> str:
    """LLM 摘要失败时的回退：聚类已提取的语步句汇总（方法/背景/目的/结果）。"""
    parts: list[str] = []
    for key, label in (("研究方法", "方法"), ("研究背景", "背景"), ("研究目的", "目的"), ("研究结果", "结果")):
        sents = [str(s).strip() for s in (mv.get(key) or []) if str(s).strip()]
        if sents:
            parts.append(f"{label}：" + " ".join(sents[:4]))
    return "；".join(parts)[:limit]


def _llm_summary_one(paper: dict[str, Any], glm) -> str:
    """单篇 LLM 摘要：150-250 字概括研究内容/方法/结论，随结果落库供综述使用。"""
    title = str(paper.get("title") or "").strip()
    text = str(paper.get("full_text") or paper.get("abstract") or paper.get("text") or "").strip()
    if len(text) < 50:
        return ""
    try:
        raw = glm.chat_json(
            "你是科技文献摘要专家。用一段话（250-400字）概括文献的研究内容、采用的方法、"
            "主要研究结果与结论（含研究进展），语言与原文一致，不编造。只输出JSON：{\"summary\":\"...\"}",
            f"文献题名：{title}\n文献内容：\n{text[:12000]}",
            temperature=0.1, timeout=120.0, max_tokens=900)
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            raw = raw["data"]
        summary = str((raw or {}).get("summary") or "").strip() if isinstance(raw, dict) else ""
        return summary[:1200]
    except Exception:  # noqa: BLE001
        return ""


def _llm_summary_batch(papers: list[dict[str, Any]], glm) -> list[str]:
    """批量 LLM 摘要（3 篇/次，2026-09-08）：原逐篇 6 次并发→2 次调用。"""
    items = []
    for i, p in enumerate(papers):
        text = str(p.get("full_text") or p.get("abstract") or p.get("text") or "").strip()
        items.append({"index": i, "title": str(p.get("title") or "").strip()[:60], "text": text[:6000]})
    valid = [it for it in items if len(it["text"]) >= 50]
    if not valid:
        return [""] * len(papers)
    batches = [valid[j:j+3] for j in range(0, len(valid), 3)]
    summaries = {it["index"]: "" for it in items}
    from concurrent.futures import ThreadPoolExecutor
    def _one(batch):
        listing = "\n".join(f"({it['index']}) 题名：{it['title']}\n内容：{it['text'][:4000]}" for it in batch)
        try:
            raw = glm.chat_json(
                "你是科技文献摘要专家。对下面每篇文献各用一段话（250-400字）概括研究内容、"
                "采用的方法、主要结果与结论。语言与原文一致，不编造。\n"
                "只输出JSON：{\"items\":[{\"index\":编号,\"summary\":\"...\"},...]}",
                listing, temperature=0.1, timeout=120.0, max_tokens=2400)
            if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
                raw = raw["data"]
            for it in (raw or {}).get("items") or []:
                if isinstance(it, dict):
                    try: idx = int(it.get("index"))
                    except (TypeError, ValueError): continue
                    s = str(it.get("summary") or "").strip()
                    if s: summaries[idx] = s[:1200]
        except Exception:  # noqa: BLE001
            pass
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(_one, batches))
    return [summaries.get(i, "") for i in range(len(papers))]

def _llm_document_summaries(papers: list[dict[str, Any]], glm) -> list[str]:
    """批量摘要（3 篇/次并发）；空结果的由调用方回退语步句汇总。"""
    return _llm_summary_batch(papers, glm)


def execute_deep_clustering(
    code: str,
    request: SemanticRequest,
    functional_point: Any,
    glm_client: Any,
) -> SemanticResult:
    """v3 语步对齐双轴聚类（2026-09-06 替换原混合向量+锚点体系）。

    技术路线轴 = 文献研究方法句 → LLM 按方法综述粒度分组
    应用场景轴 = 背景+目的句+题名 → LLM 按场景综述粒度分组
    验证：合成集双轴 ARI=1.0；papers20 英文集簇可直接产出聚焦综述。
    """
    values = list(request.texts or [])
    if len(values) < 4:
        raise ValueError("深度聚类至少需要四篇科技文本。")
    papers = _input_documents(values)
    params = dict(request.params or {})

    dimension = str(params.get("cluster_dimension") or params.get("cluster_axis") or "technology").strip().lower()
    selected_axis = "application" if dimension in {"application", "application_scenario"} else "technical"
    dimension_name = "应用场景聚类" if selected_axis == "application" else "技术路线聚类"

    # 兼容参数校验（algorithm/cluster_count 对 v3 无实际作用，仅保留契约）
    requested_algorithm = str(params.get("clustering_algorithm_type") or params.get("cluster_method")
                              or params.get("algorithm") or "auto").strip().lower()
    algorithm = _ALGORITHM_ALIASES.get(requested_algorithm, requested_algorithm)
    if algorithm not in ALLOWED_ALGORITHMS:
        raise ValueError(
            "clustering_algorithm_type 必须为 auto(自动选择)、kmeans、spectral(谱聚类)、"
            "agglomerative(凝聚聚类)、hierarchical(层次聚类) 或 hdbscan。")
    _optional_cluster_count(params)

    from infrastructure.clustering.move_aligned import run_move_aligned_clustering
    from infrastructure.resources.normalize import normalized_rows_for
    encoder = m3_encoder

    # 用户上传的锚点训练样本（可选）：资源行 → 归一化样本行（题名/摘要/类目）。
    # 内置（默认）= 无锚点纯 v3 自由分组；上传 = 语步级锚点引导分组。
    # 上传资源落盘在 runtime/semantic_resources/（storage_uri 为绝对路径），预检
    # inspect_user_resource 已把归一化行注册到路径缓存，这里直接取用
    anchor_docs: list[dict[str, Any]] = []
    resolved = params.get("resolved_resources") or {}
    sample_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    for field in ("training_samples", "manually_labeled_category_data"):
        resource = resolved.get(field)
        if not isinstance(resource, dict) or str(resource.get("source_type") or "") != "upload":
            continue
        uri = str(resource.get("storage_uri") or "")
        if not uri:
            continue
        path = Path(uri.removeprefix("project://")) if uri.startswith("project://") else Path(uri)
        rows = normalized_rows_for(path) if path.is_file() else None
        if rows:
            target = sample_rows if field == "training_samples" else label_rows
            target.extend(r for r in rows if isinstance(r, dict))
    if sample_rows or label_rows:
        anchor_docs, joined = _join_anchor_rows(sample_rows, label_rows)
        if anchor_docs:
            logger.info("深度聚类锚点已加载：%d 条（人工标签 %d 条按编号关联）",
                        len(anchor_docs), joined)

    cluster_count = _optional_cluster_count(params)
    output_format = str(params.get("output_format") or "JSON").strip().upper()

    result = SemanticResult(code=code, name=functional_point.name)
    try:
        outcome = run_move_aligned_clustering(
            papers, selected_axis=selected_axis, glm_client=glm_client, encoder=encoder,
            anchor_docs=anchor_docs or None, cluster_count=cluster_count)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        result.success = False
        result.error = f"语步对齐聚类执行失败：{exc}"
        return result

    clusters = outcome["clusters"]
    quality = outcome["quality"]
    moves = outcome["moves"]
    projection = outcome["projection"]

    doc_axis_by_index = {row["index"]: row for row in outcome["doc_axis_info"]}
    n = len(papers)
    # 每篇 LLM 摘要（2026-09-06 用户定调：存汇总内容而非全文）——并发生成，
    # 单篇失败回退到聚类已提取的语步句汇总，绝不落空
    try:
        summaries = _llm_document_summaries(papers, glm_client)
    except Exception:  # noqa: BLE001
        summaries = [""] * n
    documents = [{
        "document_id": str(papers[i].get("id") or papers[i].get("document_id") or f"DOC{i + 1}"),
        "title": str(papers[i].get("title") or ""),
        "publication_year": papers[i].get("publication_year")
            or _year_of(papers[i].get("publication_date") or papers[i].get("published_at")),
        "published_at": papers[i].get("publication_date"),
        # 内容随结果落库（2026-09-06 用户定调）：不存全文（体积大且大部分冗余），
        # 存 LLM 生成的单篇摘要（150-250字）；LLM 失败回退语步句汇总
        "content_summary": summaries[i] or _document_digest(moves[i]),
        "input_representation": {"mode": "move_aligned", "selected_axis": selected_axis},
    } for i in range(n)]
    for i, doc in enumerate(documents):
        info = doc_axis_by_index.get(i) or {}
        doc["technical"] = info if selected_axis == "technical" else {}
        doc["application"] = info if selected_axis == "application" else {}

    document_assignments = [{
        "document_id": doc["document_id"],
        "title": doc["title"],
        "publication_date": doc["published_at"],
        "publication_year": doc["publication_year"],
        "cluster_id": (doc["technical"] or doc["application"]).get("topic_id"),
        "similarity_to_centroid": None,
        "key_evidence": " ".join(
            (moves[i]["研究方法"] if selected_axis == "technical"
             else moves[i]["研究背景"] + moves[i]["研究目的"])[:2])[:300],
    } for i, doc in enumerate(documents)]

    output = {
        "documents": documents,
        "input_summary": {
            "document_count": n,
            "parsed_sentence_count": sum(len(v) for m in moves for v in m.values()),
        },
        "cluster_dimension_name": dimension_name,
        "cluster_dimension": dimension,
        "clustering_quality": quality,
        "clusters": clusters,
        "document_assignments": document_assignments,
        "semantic_projection": projection,
        "theme_trend_analysis": _trend_analysis(documents),
        "partition_strategy": "move_aligned",
    }
    # 输出格式（需求评审：JSON 默认 / CSV 附 csv_content / 数据库写入结构附 database_records）
    fmt = output_format.upper()
    if fmt.startswith("CSV") or output_format.startswith("CSV"):
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        writer = _csv.writer(buf)
        writer.writerow(["cluster_id", "topic_name", "size", "representative_terms", "document_ids"])
        for c in clusters:
            writer.writerow([c["cluster_id"], c["topic_name"], c["size"],
                             "；".join(c.get("representative_terms") or []),
                             "；".join(m.get("document_id") or "" for m in (c.get("members") or []))])
        output["csv_content"] = buf.getvalue()
        output["output_format"] = "csv"
    elif "数据库" in output_format or "DATABASE" in fmt:
        output["database_records"] = [{
            "cluster_id": c["cluster_id"],
            "cluster_name": c["topic_name"],
            "document_count": c["size"],
            "document_ids": [m.get("document_id") for m in (c.get("members") or [])],
        } for c in clusters]
        output["output_format"] = "database"

    # 质量指标（v3 语义分组专用，轮廓系数对 LLM 分组无意义——已移除）：
    # ① 语义一致性（LLM 判定簇内文献是否讲同一方法/场景）——直接度量分组目标
    # ② 簇间区分度（LLM 判定任意两簇主题是否明确不同）——防伪聚类
    # ③ 综述可用率（≥2 篇的簇占比）——对应下游综述可选性
    # ④ 向量辅助诊断（intra/inter/中心相似度）——语义指标的数值佐证
    try:
        import numpy as _np
        axis_texts = []
        for i, mv in enumerate(moves):
            sents = (mv["研究方法"][:6] if selected_axis == "technical"
                     else (mv["研究背景"] + mv["研究目的"])[:6])
            if not sents:
                sents = [str(papers[i].get("title") or f"DOC{i + 1}")]
            v = _np.asarray(encoder.encode(sents)).mean(axis=0)
            axis_texts.append(v / max(float(_np.linalg.norm(v)), 1e-9))
        matrix = _np.asarray(axis_texts)
        centers = {}
        for c in clusters:
            vecs = matrix[c["doc_indices"]]
            centers[c["cluster_id"]] = vecs.mean(axis=0)
        for c in clusters:
            cid = c["cluster_id"]
            vecs = matrix[c["doc_indices"]]
            sims = [float(v @ centers[cid]) for v in vecs]
            intra = float(_np.mean(sims))
            inter_vec = float(min(
                float(centers[cid] @ centers[oc]) for oc in centers if oc != cid
            )) if len(centers) > 1 else 0.0
            # 类间分离度 = margin 口径：簇内相似度 − 最近异簇中心相似度（值域约
            # [-1,1]，正=簇内比最近异簇更近，越大越好）。旧口径 1−cosine 在文本
            # 向量上恒 0.3 左右（不同主题向量仍有 0.5-0.7 基线相似度），margin
            # 才能体现"本簇相对最近异簇的分离程度"
            margin = intra - inter_vec
            c["feature_statistics"] = {
                "intra_cluster_similarity": round(max(0.0, intra), 3),
                "inter_cluster_separation": round(margin, 3),
                "semantic_density": round(max(0.0, 1.0 - (max(sims) - min(sims)) if len(sims) >= 2 else intra), 3),
            }
        sim_by_doc = {}
        for c in clusters:
            for i in c["doc_indices"]:
                sim_by_doc[i] = round(max(0.0, float(matrix[i] @ centers[c["cluster_id"]])), 3)
        for i, a in enumerate(document_assignments):
            a["similarity_to_centroid"] = sim_by_doc.get(i)

        # LLM 语义指标：一次性判定全部簇的一致性 + 两两区分度（批量单调用）
        axis_label = "技术方法" if selected_axis == "technical" else "应用场景"
        cluster_lines = []
        for ci, c in enumerate(clusters, start=1):
            titles = [str((papers[i].get("title") or f"DOC{i + 1}")[:24]) for i in c["doc_indices"][:4]]
            cluster_lines.append(f"簇{ci}「{c['topic_name']}」（{c['size']}篇）: {'；'.join(titles)}")
        metrics_system = (
            f"你是聚类质量评审专家。下面是文献按{axis_label}分组的全部类簇。请评估两项：\n"
            f"1. 每个簇的语义一致性（0-1）：簇内文献是否确实研究同类{axis_label}（能合并为一篇聚焦综述=1.0；混入不同主题=明显低于1）\n"
            "2. 整体簇间区分度（0-1）：任意两簇的主题是否明确不同（同主题被拆散成多簇=明显低于1）\n"
            '只输出JSON：{"coherence":[{"cluster":1,"score":0.95},...],"distinctiveness":0.9}'
        )
        quality["silhouette_score"] = None  # 已弃用：轮廓系数量向量几何，不度量语义分组
        quality.pop("silhouette_score", None)
        try:
            raw_m = glm_client.chat_json(metrics_system, "\n".join(cluster_lines),
                                         temperature=0.0, timeout=120.0, max_tokens=1500)
            if isinstance(raw_m, dict) and isinstance(raw_m.get("data"), dict):
                raw_m = raw_m["data"]
            coh_map = {}
            for item in ((raw_m or {}).get("coherence") if isinstance(raw_m, dict) else []) or []:
                if isinstance(item, dict) and item.get("cluster") is not None:
                    try:
                        coh_map[int(item["cluster"]) - 1] = max(0.0, min(1.0, float(item.get("score", 0))))
                    except (TypeError, ValueError):
                        continue
            for ci, c in enumerate(clusters):
                if ci in coh_map:
                    c.setdefault("feature_statistics", {})
                    c["feature_statistics"]["semantic_coherence"] = round(coh_map[ci], 3)
        except Exception:  # noqa: BLE001
            logger.warning("LLM 语义指标评估失败", exc_info=True)
        # 质量指标口径与弹窗/响应示例完全一致（2026-09-06 用户定调）：
        # 汇总卡只展示 簇数 + 簇内平均相似度——类间区分度/综述可用率/簇规模
        # 等派生指标已从弹窗删除，真实响应不再输出
        multi_clusters = [c for c in clusters if c.get("size", 0) >= 2]
        intra_vals = [c["feature_statistics"]["intra_cluster_similarity"]
                      for c in multi_clusters
                      if c.get("feature_statistics", {}).get("intra_cluster_similarity") is not None]
        if intra_vals:
            quality["intra_cluster_similarity"] = round(sum(intra_vals) / len(intra_vals), 3)
    except Exception:  # noqa: BLE001 - 指标计算失败不阻塞聚类结果
        logger.warning("v3 质量指标计算失败", exc_info=True)

    result.success = True
    result.data = output
    result.confidence = None
    result.raw = json.dumps({"mode": "move_aligned", "n_clusters": len(clusters), "n_documents": n},
                            ensure_ascii=False)
    return result
