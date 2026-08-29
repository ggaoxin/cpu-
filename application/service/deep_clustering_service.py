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
ALLOWED_ALGORITHMS = {
    "auto", "kmeans", "spectral", "agglomerative", "hierarchical", "hdbscan",
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
        "summary": f"共 {len(years)} 个年份、{sum(sum(row['yearly_counts']) for row in series)} 条带发表时间的科技文本参与趋势统计。",
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
                documents.append(value)
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
            documents.append({"text": raw})
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


def _label_cluster_via_glm(
    glm_client: Any,
    cluster: dict[str, Any],
    doc_axis_info: list[dict[str, Any]],
    papers: list[dict[str, Any]],
) -> str | None:
    """用 GLM 为一个应用场景簇生成简短中文场景标签，失败返回 None。

    喂给 GLM 的是该簇 representative_terms + 各成员 key_evidence + 代表性标题，
    让模型有完整证据上下文，而非仅靠 sparse 高频 token（避免 "training / our"
    类八股词被当场景标签）。原 sparse topic_name 由调用方保留溯源。
    """
    if glm_client is None or not settings.llm_configured:
        return None
    cluster_id = str(cluster.get("cluster_id") or "")
    if not cluster_id or cluster_id == "OUTLIER":
        return None
    representative_terms = [
        str(term).strip() for term in (cluster.get("representative_terms") or []) if str(term).strip()
    ][:8]
    titles: list[str] = []
    evidence_snippets: list[str] = []
    for index in cluster.get("doc_indices") or []:
        if not isinstance(index, int) or index < 0 or index >= len(doc_axis_info):
            continue
        snippet = str(doc_axis_info[index].get("key_evidence") or "").strip()
        if snippet:
            evidence_snippets.append(snippet)
        paper = papers[index] if index < len(papers) else {}
        title = str(paper.get("title") or "").strip()
        doc_id = str(paper.get("document_id") or "").strip()
        # 跳过未抽到标题、退化为 document_id 的无意义值
        if title and title != doc_id:
            titles.append(title)
    titles = list(dict.fromkeys(titles))[:5]
    evidence_snippets = list(dict.fromkeys(evidence_snippets))[:6]
    payload = {
        "cluster_id": cluster_id,
        "size": cluster.get("size"),
        "representative_terms": representative_terms,
        "document_titles": titles,
        "key_evidence": evidence_snippets,
    }
    system = (
        "你是科技文献场景标签生成专家。下面给出深度聚类在应用场景轴上聚出的一个文献簇。"
        "请基于该簇的代表短语、文献标题与关键证据句段，生成一个简短、专业、自然的中文场景标签"
        "（4到12个汉字），概括该簇文献共同的研究对象、应用领域或应用场景。"
        "标签须体现该簇的场景共性，不得罗列具体方法名或单篇文献专名，"
        "不得使用论文八股词（如 training/our/which/these/study/approach/research）。"
        "只返回JSON：{\"scene_label\":\"场景标签\"}。"
    )
    try:
        raw = glm_client.chat_json(
            system,
            json.dumps(payload, ensure_ascii=False),
            temperature=0.0,
            timeout=60.0,
            max_tokens=200,
        )
    except Exception as exc:  # noqa: BLE001 - 失败回退原 sparse topic_name，不阻断聚类
        logger.warning("GLM 场景标签生成失败 cluster=%s：%s", cluster_id, exc)
        return None
    data = raw.get("data", raw) if isinstance(raw, dict) else {}
    label = str(
        data.get("scene_label") or data.get("label") or data.get("topic_name") or ""
    ).strip()
    label = label.strip("\"'“”‘’。.：:：、 \t")
    if not label or len(label) > 30 or label == cluster.get("topic_name"):
        return None
    return label


def _regenerate_application_scene_labels(
    application: dict[str, Any],
    papers: list[dict[str, Any]],
    glm_client: Any,
) -> dict[str, Any]:
    """用 GLM 重写 application 轴各簇 topic_name 为中文场景标签。

    仅替换 cluster.topic_name 与 doc_axis_info[index].topic_name 的展示值；
    不改 representative_terms、不改聚类归属。原 sparse topic_name 保留进
    cluster["sparse_topic_name"] 供溯源。technical 轴不动（技术标签不进综述）。
    """
    clusters = application.get("clusters") or []
    doc_axis_info = application.get("doc_axis_info") or []
    succeeded = 0
    failed = 0
    for cluster in clusters:
        if str(cluster.get("cluster_id") or "") == "OUTLIER":
            continue
        new_label = _label_cluster_via_glm(glm_client, cluster, doc_axis_info, papers)
        if not new_label:
            failed += 1
            continue
        cluster.setdefault("sparse_topic_name", cluster.get("topic_name"))
        cluster["topic_name"] = new_label
        for index in cluster.get("doc_indices") or []:
            if isinstance(index, int) and 0 <= index < len(doc_axis_info):
                doc_axis_info[index]["topic_name"] = new_label
        succeeded += 1
    return {
        "scene_label_generated": succeeded,
        "scene_label_failed": failed,
        "scene_label_used_glm": succeeded > 0,
        "scene_label_glm_configured": bool(settings.llm_configured),
    }


# 技术轴选 k 校准：算法自动选 k 后，GLM 读技术路线 views 判断该分几簇，
# 两者差异小且算法置信度够则信算法，否则用 GLM 的 k 重聚。
# LLM 管宏观（几簇）、算法管微观（哪篇归哪簇），破除小样本"silhouette+undersized
# 必然选 k=2 把孤儿技术路线误并"的缺陷。输入用算法实际聚类的 axis views
# （全文按技术 cue 浓缩），论文/基金/报告通用，不依赖 abstract/keywords。
_K_TOLERANCE = 1          # |k_algo - k_llm| ≤ 此值且分数够 → 信算法
_K_MIN_ALGO_SCORE = 0.55  # 算法 selection_score ≥ 此值才信算法


def _calibrate_k_via_glm(
    glm_client: Any,
    papers: list[dict[str, Any]],
    views: list[str],
    k_algo: int,
    selection_score: float | None,
    n: int,
) -> dict[str, Any]:
    """用 GLM 判断技术轴应分簇数，与算法选的 k 对比，差异大则改用 GLM 的 k。

    失败/未配置 GLM 时回退算法 k_algo，不阻断聚类。仅返回决策，不直接改归属——
    归属仍由 spectral 基于向量算，只是 k 被 GLM 校准后重跑一次。
    """
    result: dict[str, Any] = {
        "k_algo": k_algo, "k_llm": None, "final_k": k_algo,
        "calibrated": False, "used_glm": False, "reasoning": "",
        "algo_score": selection_score,
    }
    if glm_client is None or not settings.llm_configured or n < 4:
        return result
    entries: list[str] = []
    for index, paper in enumerate(papers):
        view = str(views[index] if index < len(views) else "")[:1200]
        entries.append(f"[{index}] {paper.get('title', '')}\n技术路线要点：{view}")
    payload = (
        f"共 {n} 篇文献，按技术路线（方法/算法/模型/研究设计）判断应分几簇：\n"
        + "\n---\n".join(entries)
    )
    system = (
        "你是科技文献技术路线聚类专家。按技术路线本质判断这些文献应分几个簇"
        "（2 到文献总数之间）。区分不同技术路线：深度学习图像识别、机器学习回归预测、"
        "运筹优化调度等是不同路线。只输出JSON："
        "{\"cluster_count\": 数字, \"reasoning\": \"简述依据\"}"
    )
    try:
        raw = glm_client.chat_json(
            system, payload, temperature=0.0, timeout=60.0, max_tokens=300,
        )
    except Exception as exc:  # noqa: BLE001 - 失败回退算法 k，不阻断聚类
        logger.warning("GLM 判k失败：%s", exc)
        return result
    data = raw.get("data", raw) if isinstance(raw, dict) else {}
    try:
        k_llm = int(data.get("cluster_count") or data.get("k") or data.get("cluster_k"))
    except (TypeError, ValueError):
        k_llm = None
    # 上界放宽到 n：n 篇全异质时 GLM 合理判 k=n（每篇独立），不应被当越界拒绝。
    # 算法重跑物理上限是 n-1（k=n 退化为全单点簇、spectral 无意义），故 final_k
    # 仍 clamp 到 n-1，但保留 k_llm 原值 + reasoning 供审计——避免静默退化 used_glm=False
    if k_llm is None or not (2 <= k_llm <= n):
        return result
    result["k_llm"] = k_llm
    result["reasoning"] = str(data.get("reasoning") or "")[:300]
    result["used_glm"] = True
    trust_algo = (
        abs(k_algo - k_llm) <= _K_TOLERANCE
        and selection_score is not None
        and selection_score >= _K_MIN_ALGO_SCORE
    )
    final_k_raw = k_algo if trust_algo else k_llm
    result["final_k"] = min(final_k_raw, n - 1)  # GLM 判 k=n 时 clamp 到算法上限
    if result["final_k"] != k_algo:
        result["calibrated"] = True
    return result


def execute_deep_clustering(
    code: str,
    request: SemanticRequest,
    functional_point: Any,
    glm_client: Any,
) -> SemanticResult:
    """Execute exactly one user-selected semantic axis, without a topic library."""
    values = list(request.texts or [])
    if len(values) < 4:
        raise ValueError("深度聚类至少需要四篇科技文本。")
    papers = _input_documents(values)
    params = dict(request.params or {})

    dimension = str(
        params.get("cluster_dimension") or params.get("cluster_axis") or "technology"
    ).strip().lower()
    selected_axis = "application" if dimension in {"application", "application_scenario"} else "technical"

    requested_algorithm = str(
        params.get("cluster_method") or params.get("algorithm") or "auto"
    ).strip().lower()
    algorithm = "auto" if requested_algorithm in {"", "semantic"} else requested_algorithm
    if algorithm not in ALLOWED_ALGORITHMS:
        raise ValueError(
            "algorithm 必须为 auto、kmeans、spectral、agglomerative、hierarchical 或 hdbscan。"
        )
    cluster_count = _optional_cluster_count(params)
    if algorithm == "hdbscan" and cluster_count is not None:
        raise ValueError("HDBSCAN 自动确定类簇数量，不能同时设置 cluster_count。")
    try:
        min_cluster_size = max(2, int(
            params.get("minimum_cluster_size", params.get("min_cluster_size", 2)) or 2
        ))
        random_state = int(params.get("random_state", 42) or 42)
    except (TypeError, ValueError) as exc:
        raise ValueError("minimum_cluster_size 和 random_state 必须为整数。") from exc
    similarity_threshold = _optional_float(params, "similarity_threshold")
    similarity_metric = str(params.get("similarity_metric") or "cosine").lower()
    if similarity_metric != "cosine":
        raise ValueError("当前 BGE-M3 深度聚类仅支持 cosine 相似度。")

    from infrastructure.clustering.evidence_rule_engine import load_rule_fusion_config

    rule_config = load_rule_fusion_config()
    rule_mode = str(
        params.get("rule_mode")
        or rule_config.get(f"{selected_axis}_rule_mode")
        or rule_config["rule_mode"]
    ).strip().lower()
    if rule_mode not in {"off", "audit", "enhance"}:
        raise ValueError("rule_mode 必须为 off、audit 或 enhance。")
    try:
        technical_rule_weight = float(params.get(
            "technical_rule_weight", rule_config["technical_rule_weight"]
        ))
        application_rule_weight = float(params.get(
            "application_rule_weight", rule_config["application_rule_weight"]
        ))
    except (TypeError, ValueError) as exc:
        raise ValueError("technical_rule_weight 和 application_rule_weight 必须为数值。") from exc
    if not 0 <= technical_rule_weight <= 0.40:
        raise ValueError("technical_rule_weight 必须在0到0.40之间。")
    if not 0 <= application_rule_weight <= 0.35:
        raise ValueError("application_rule_weight 必须在0到0.35之间。")
    technical_rule_policy = str(
        params.get("technical_rule_policy")
        or rule_config.get("technical_rule_policy", "fallback_only")
    ).strip().lower()
    application_rule_policy = str(
        params.get("application_rule_policy")
        or rule_config.get("application_rule_policy", "fallback_only")
    ).strip().lower()
    if technical_rule_policy not in {"fallback_only", "all"}:
        raise ValueError("technical_rule_policy 必须为 fallback_only 或 all。")
    if application_rule_policy not in {"fallback_only", "all"}:
        raise ValueError("application_rule_policy 必须为 fallback_only 或 all。")

    extraction_mode = str(
        params.get("axis_extraction")
        or rule_config.get(f"{selected_axis}_axis_extraction")
        or ("llm_verified" if selected_axis == "application" else "local")
    ).strip().lower()
    if extraction_mode not in {"llm_verified", "local"}:
        raise ValueError("axis_extraction 必须为 llm_verified 或 local。")

    application_extractor = None
    technical_extractor = None
    if extraction_mode == "llm_verified" and settings.llm_configured:
        from infrastructure.clustering.axis_extractor import EvidenceBoundAxisExtractor

        extractor = EvidenceBoundAxisExtractor(
            glm_client,
            model_name=settings.GLM_MODEL,
            cache_dir=settings.PROJECT_ROOT / "runtime" / "cache" / "axis_extraction",
            batch_size=int(params.get("axis_extraction_batch_size", 6) or 6),
            required_axes=(selected_axis,),
        )
        if selected_axis == "application":
            application_extractor = extractor
        else:
            technical_extractor = extractor
    elif extraction_mode == "llm_verified":
        logger.warning("GLM 未配置，深度聚类测试将显式使用本地 BGE-M3 回退表示。")

    # 技术轴选 k 校准（改动3）：仅技术轴 + 用户未显式定 k + n≥4 时，先让算法
    # 自动选 k_algo，再用 GLM 判 k_llm 对比（结合置信度），差异大则用 GLM 的 k 重聚。
    # cluster_count 透传无状态，二次调用安全；指定 k 重跑走 bge_m3_sparse.py:253-254。
    do_k_calib = (
        selected_axis == "technical"
        and cluster_count is None
        and glm_client is not None
        and len(papers) >= 4
    )
    clustered = run_selected_axis_clustering(
        papers,
        m3_encoder,
        selected_axis=selected_axis,
        model_path=settings.BGE_M3_PATH,
        application_extractor=application_extractor,
        technical_extractor=technical_extractor,
        algorithm=algorithm,
        cluster_count=(None if do_k_calib else cluster_count),
        min_cluster_size=min_cluster_size,
        similarity_threshold=similarity_threshold,
        random_state=random_state,
        rule_mode=rule_mode,
        technical_rule_weight=technical_rule_weight,
        technical_rule_policy=technical_rule_policy,
        application_rule_weight=application_rule_weight,
        application_rule_policy=application_rule_policy,
    )
    k_selection: dict[str, Any] = {
        "k_algo": None, "final_k": None, "calibrated": False, "used_glm": False,
    }
    if do_k_calib:
        algo_quality = clustered["selected"]["quality"]
        k_algo = int(algo_quality.get("cluster_count") or 0)
        k_selection = _calibrate_k_via_glm(
            glm_client,
            clustered["papers"],
            clustered.get("axis_views") or [],
            k_algo,
            algo_quality.get("selection_score"),
            len(papers),
        )
        if k_selection["calibrated"] and k_selection["final_k"] and k_selection["final_k"] != k_algo:
            clustered = run_selected_axis_clustering(
                papers,
                m3_encoder,
                selected_axis=selected_axis,
                model_path=settings.BGE_M3_PATH,
                application_extractor=application_extractor,
                technical_extractor=technical_extractor,
                algorithm=algorithm,
                cluster_count=k_selection["final_k"],
                min_cluster_size=min_cluster_size,
                similarity_threshold=similarity_threshold,
                random_state=random_state,
                rule_mode=rule_mode,
                technical_rule_weight=technical_rule_weight,
                technical_rule_policy=technical_rule_policy,
                application_rule_weight=application_rule_weight,
                application_rule_policy=application_rule_policy,
            )
            k_selection["rerun"] = True

    normalized_papers = clustered["papers"]
    selected = clustered["selected"]
    technical = clustered["technical"]
    application = clustered["application"]

    # ---- 锚点辅助（可选）：训练样本/人工标注类目资源存在时，把小样本聚类
    # 的主题锚定到人工标注类目标签（语义近邻匹配），避免自由聚类主题过于宽泛。
    anchor_output: dict[str, Any] = {"enabled": False}
    gold_path = None
    try:
        from infrastructure.clustering.anchor_labeling import resolve_gold_path, anchor_assist, aggregate_cluster_anchor
        gold_path = resolve_gold_path(params.get("resolved_resources"))
    except ImportError:
        gold_path = None
    if gold_path is not None:
        anchor_output = anchor_assist(
            normalized_papers, gold_path, selected_axis,
            threshold=float(params.get("anchor_similarity_threshold", 0) or 0.45),
        )
    doc_anchors = anchor_output.get("document_anchors") or {}

    documents = [{
        "document_id": paper["document_id"],
        "title": paper["title"],
        "language": paper["language"],
        "publication_year": paper["publication_year"],
        "published_at": paper["published_at"],
        "input_representation": paper["input_representation"],
        "technical": technical["doc_axis_info"][index] if technical else {},
        "application": application["doc_axis_info"][index] if application else {},
        **(doc_anchors.get(str(paper["document_id"])) or {}),
    } for index, paper in enumerate(normalized_papers)]
    document_assignments = [{
        "document_id": item["document_id"],
        "title": item["title"],
        "publication_date": item["published_at"],
        "publication_year": item["publication_year"],
        "cluster_id": (item["technical"] or item["application"]).get("topic_id"),
        "similarity_to_centroid": (item["technical"] or item["application"]).get("score"),
        "key_evidence": (item["technical"] or item["application"]).get("key_evidence"),
        "input_representation": item["input_representation"],
        "anchored_topic_id": (doc_anchors.get(str(item["document_id"])) or {}).get("anchored_topic_id"),
        "anchored_topic_name": (doc_anchors.get(str(item["document_id"])) or {}).get("anchored_topic_name"),
        "anchor_confidence": (doc_anchors.get(str(item["document_id"])) or {}).get("anchor_confidence"),
    } for item in documents]

    # 簇级锚定：锚定主题替换宽泛的自由聚类主题（原主题保留在 original_topic_name）
    if anchor_output.get("enabled"):
        for axis_payload in (technical, application):
            if not axis_payload or not axis_payload.get("clusters"):
                continue
            for cluster in axis_payload["clusters"]:
                if str(cluster.get("cluster_id") or "") == "OUTLIER":
                    continue
                member_ids = [
                    normalized_papers[i]["document_id"]
                    for i in (cluster.get("doc_indices") or [])
                    if isinstance(i, int) and 0 <= i < len(normalized_papers)
                ]
                cluster_anchor = aggregate_cluster_anchor(doc_anchors, member_ids)
                if not cluster_anchor:
                    continue
                if cluster_anchor.get("anchor_status") == "anchored":
                    # 高置信（票数份额≥0.5，gold 实测精度 99%）：锚定主题替换宽泛的自由聚类主题
                    cluster["original_topic_name"] = cluster.get("topic_name")
                    cluster["topic_name"] = cluster_anchor["anchored_topic_name"]
                cluster.update(cluster_anchor)
                cluster["anchored_member_ids"] = member_ids

    extraction = dict(clustered["axis_extraction"])
    selected_extractor = application_extractor if selected_axis == "application" else technical_extractor
    if extraction_mode == "llm_verified" and selected_extractor is None:
        extraction.update({
            "mode": "local_fallback",
            "fallback_reason": "llm_not_configured",
            "verified_document_count": 0,
            "fallback_document_count": len(documents),
            "document_sources": ["local_fallback"] * len(documents),
        })
    quality = dict(selected["quality"])
    verified_count = int(extraction.get("verified_document_count", 0) or 0)
    quality.update({
        "encoding_model": "bge-m3",
        "selected_axis": selected_axis,
        "anchor_assisted": bool(anchor_output.get("enabled")),
        "anchor_matched_document_count": anchor_output.get("matched_document_count", 0),
        "representation": clustered["representation"].get("representation"),
        "topic_library_used": False,
        "axis_extraction_mode": extraction.get("mode"),
        "axis_extraction_verified_documents": verified_count,
        "axis_extraction_fallback_documents": extraction.get("fallback_document_count", 0),
        "llm_affects_semantic_representation": verified_count > 0,
        "llm_assigns_cluster_membership": bool(k_selection.get("calibrated")),
    })
    if selected_axis == "technical":
        axis_engine = "bge_m3_native_sparse_technical"
    elif verified_count:
        axis_engine = "glm_evidence_core3_bge_m3_application"
    else:
        axis_engine = "local_core3_bge_m3_application_test_fallback"

    # 改动1: application 轴跑完后用 GLM 给每个场景簇生成中文场景标签，
    # 替换纯 sparse 高频 token 拼出的 topic_name（如 "training / our"）。
    # 失败/未配置 GLM 时回退原 sparse 值，不阻断聚类。
    scene_labeling: dict[str, Any] = {}
    if selected_axis == "application" and application:
        scene_labeling = _regenerate_application_scene_labels(
            application, normalized_papers, glm_client
        )

    # 改动2: 当前轴(selected)跑完后，按每个簇沉淀 1 个文献集，使结构化综述的
    # "已有文献集"下拉有内容可按主题语义检索。1 簇 = 1 文献集 = 下拉 1 选项。
    # 应用轴用 GLM 场景标签命名；技术轴 topic_name 为 sparse token（易脏），改用
    # 已清洗的代表短语命名。两轴对称沉淀，避免技术轴跑完下拉空。
    collection_persistence: dict[str, Any] = {"persisted": [], "failed": []}
    persist_axis = selected if selected else (application if selected_axis == "application" else technical)
    if persist_axis and persist_axis.get("clusters"):
        try:
            from application.service.resource_service import resource_service
            clusters_for_persist = persist_axis.get("clusters") or []
            doc_axis_info_persist = persist_axis.get("doc_axis_info") or []
            axis_label = "场景" if selected_axis == "application" else "技术路线"
            for cluster in clusters_for_persist:
                if str(cluster.get("cluster_id") or "") == "OUTLIER":
                    continue
                members = []
                for index in cluster.get("doc_indices") or []:
                    if not isinstance(index, int) or index < 0 or index >= len(normalized_papers):
                        continue
                    paper = normalized_papers[index]
                    info = doc_axis_info_persist[index] if index < len(doc_axis_info_persist) else {}
                    members.append({
                        "id": paper.get("document_id"),
                        "title": paper.get("title"),
                        "abstract": paper.get("abstract") or "",
                        "content": paper.get("full_text") or paper.get("semantic_text") or "",
                        "language": paper.get("language"),
                        "keywords": paper.get("keywords") or [],
                        "published_at": paper.get("published_at"),
                        "metadata": {
                            "cluster_id": cluster.get("cluster_id"),
                            "original_document_id": paper.get("document_id"),
                            "similarity_to_centroid": info.get("score"),
                            "source": f"deep_clustering_{selected_axis}",
                        },
                    })
                if not members:
                    continue
                rep_terms = [str(term) for term in (cluster.get("representative_terms") or [])][:4]
                if selected_axis == "application":
                    topic_name = str(cluster.get("topic_name") or cluster.get("cluster_id"))
                else:  # 技术轴 topic_name 为 sparse token 拼接（如"training / our"），改用代表短语命名
                    topic_name = "、".join(rep_terms) if rep_terms else str(cluster.get("cluster_id"))
                import datetime as _dt; _t = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
                payload = {
                    "name": f"{topic_name} · {_t}",
                    "description": (
                        f"深度聚类{axis_label}文献集 · {code} · 簇{cluster.get('cluster_id')}"
                        f" · {','.join(rep_terms)}"
                    ),
                    "documents": members,
                }
                try:
                    created = resource_service.create_collection(
                        payload, workspace_id=settings.DEFAULT_WORKSPACE_ID
                    )
                    collection_persistence["persisted"].append({
                        "cluster_id": cluster.get("cluster_id"),
                        "collection_id": created.get("id") if isinstance(created, dict) else None,
                        "collection_name": topic_name,
                        "document_count": len(members),
                    })
                except Exception as exc:  # noqa: BLE001 - 单簇失败不阻断聚类与后续簇
                    logger.warning("%s簇 %s 沉淀文献集失败：%s", axis_label, cluster.get("cluster_id"), exc)
                    collection_persistence["failed"].append({
                        "cluster_id": cluster.get("cluster_id"),
                        "error": str(exc)[:200],
                    })
        except Exception as exc:  # noqa: BLE001 - 整个沉淀不可阻断聚类
            logger.warning("文献集沉淀整体失败：%s", exc)
            collection_persistence["error"] = str(exc)[:200]

    output = {
        "documents": documents,
        "technical_topics": technical["clusters"] if technical else [],
        "application_topics": application["clusters"] if application else [],
        "anchor_assist": anchor_output,
        "n": len(documents),
        "input_summary": {
            "document_count": len(documents),
            "parsed_sentence_count": clustered["parsed_sentence_count"],
            "structured_document_count": sum(
                item["input_representation"]["mode"] == "structured" for item in documents
            ),
            "plain_text_document_count": sum(
                item["input_representation"]["mode"] == "plain_text" for item in documents
            ),
        },
        "cluster_dimension_name": "应用场景聚类" if selected_axis == "application" else "技术路线聚类",
        "clustering_quality": quality,
        "quality_metrics": quality,
        "axis_quality": {
            "technical": technical["quality"] if technical else None,
            "application": application["quality"] if application else None,
        },
        "axis_extraction": extraction,
        "representation_metadata": clustered["representation"],
        "rule_evidence": clustered["rule_evidence"],
        "semantic_projection": selected["projection"],
        "document_assignments": document_assignments,
        "theme_trend_analysis": _trend_analysis(documents),
        "input_representations": [
            {"document_id": item["document_id"], **item["input_representation"]}
            for item in documents
        ],
        "correction_status": "unreviewed",
        "algorithm_metadata": {
            "requested_algorithm": requested_algorithm or "auto",
            "effective_algorithm": quality.get("algorithm_used"),
            "selected_axis": selected_axis,
            "axis_engine": axis_engine,
            "representation": clustered["representation"].get("representation"),
            "cluster_count_mode": "fixed" if cluster_count is not None else "adaptive",
            "min_cluster_size": min_cluster_size,
            "similarity_threshold": similarity_threshold,
            "similarity_metric": similarity_metric,
            "topic_library_used": False,
            "llm_role": (
                "evidence_bound_application_facets" if verified_count
                else "technical_k_calibration" if (
                    selected_axis == "technical" and k_selection.get("calibrated")
                )
                else "none"
            ),
            "llm_assigns_cluster_membership": bool(k_selection.get("calibrated")),
            "local_test_fallback_used": extraction.get("mode") == "local_fallback",
            "rule_mode": rule_mode,
            "rule_affects_clustering": rule_mode == "enhance",
            "rules_assign_cluster_membership": False,
        },
        "scene_labeling": scene_labeling,
        "collection_persistence": collection_persistence,
        "k_selection": k_selection,
    }
    result = SemanticResult(code=code, name=functional_point.name)
    result.success = True
    result.data = output
    result.raw = json.dumps({
        "n": len(documents),
        "dimension": dimension,
        "algorithm": quality.get("algorithm_used"),
        "cluster_count": quality.get("cluster_count"),
        "silhouette": quality.get("silhouette_score"),
        "stability_ari": quality.get("stability_ari"),
        "axis_engine": axis_engine,
    }, ensure_ascii=False)
    return result
