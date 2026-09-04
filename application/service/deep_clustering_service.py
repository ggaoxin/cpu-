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
    axis: str = "application",
) -> str | None:
    """用 GLM 为一个类簇生成简短中文标签（锚定不达门槛时的兜底），失败返回 None。

    喂给 GLM 的是该簇 representative_terms + 各成员 key_evidence + 代表性标题，
    让模型有完整证据上下文，而非仅靠 sparse 高频 token（避免 "training / our"
    类八股词被当标签）。原 sparse topic_name 由调用方保留溯源。
    axis=application 生成场景标签（研究对象/应用领域）；technical 生成技术路线
    标签（方法/算法/技术本质）。
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
    if axis == "technical":
        system = (
            "你是科技文献技术路线标签生成专家。下面给出深度聚类在技术路线轴上聚出的一个文献簇。"
            "请基于该簇的代表短语、文献标题与关键证据句段，生成一个简短、专业、自然的中文技术路线标签"
            "（4到12个汉字），概括该簇文献共同的方法、算法或技术本质（如：深度学习图像识别、"
            "运筹优化调度、有限元仿真）。不得罗列应用领域、研究对象或单篇文献专名，"
            "不得使用论文八股词（如 training/our/which/these/study/approach/research）。"
            "只返回JSON：{\"cluster_label\":\"技术路线标签\"}。"
        )
    else:
        system = (
            "你是科技文献场景标签生成专家。下面给出深度聚类在应用场景轴上聚出的一个文献簇。"
            "请基于该簇的代表短语、文献标题与关键证据句段，生成一个简短、专业、自然的中文场景标签"
            "（4到12个汉字），概括该簇文献共同的研究对象、应用领域或应用场景。"
            "标签须体现该簇的场景共性，不得罗列具体方法名或单篇文献专名，"
            "不得使用论文八股词（如 training/our/which/these/study/approach/research）。"
            "只返回JSON：{\"cluster_label\":\"场景标签\"}。"
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
        logger.warning("GLM 簇标签生成失败 cluster=%s：%s", cluster_id, exc)
        return None
    data = raw.get("data", raw) if isinstance(raw, dict) else {}
    label = str(
        data.get("cluster_label") or data.get("scene_label")
        or data.get("label") or data.get("topic_name") or ""
    ).strip()
    label = label.strip("\"'“”‘’。.：:：、 \t")
    if not label or len(label) > 30 or label == cluster.get("topic_name"):
        return None
    return label


def _regenerate_axis_cluster_labels(
    axis_payload: dict[str, Any],
    papers: list[dict[str, Any]],
    glm_client: Any,
    axis: str = "application",
) -> dict[str, Any]:
    """用 GLM 重写所选轴各簇 topic_name 为中文簇标签（锚定不达门槛的兜底）。

    仅替换 cluster.topic_name 与 doc_axis_info[index].topic_name 的展示值；
    不改 representative_terms、不改聚类归属。原 sparse topic_name 保留进
    cluster["sparse_topic_name"] 供溯源。已锚定(anchor_status=anchored)的簇
    保留人工标注类目名，不被生成标签覆盖。
    """
    clusters = axis_payload.get("clusters") or []
    doc_axis_info = axis_payload.get("doc_axis_info") or []
    succeeded = 0
    failed = 0
    skipped_anchored = 0
    for cluster in clusters:
        if str(cluster.get("cluster_id") or "") == "OUTLIER":
            continue
        if str(cluster.get("anchor_status") or "") == "anchored":
            # 人工标注类目已锚定本簇主题（高置信、可溯源），GLM 场景标签不再覆盖。
            # 场景标签只用于改写算法拼出的宽泛 sparse 名，不该盖过人工标注答案。
            skipped_anchored += 1
            continue
        new_label = _label_cluster_via_glm(glm_client, cluster, doc_axis_info, papers, axis)
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
        "scene_label_skipped_anchored": skipped_anchored,
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


def _repartition_anchor_aligned(
    axis_payload: dict[str, Any],
    papers: list[dict[str, Any]],
    doc_anchors: dict[str, Any],
) -> dict[str, Any]:
    """锚点对齐重划分：锚定成功的文献按人工标注类目直接成簇。

    与自由聚类的本质区别：划分本身受用户上传的标注数据引导——同一个人工
    类目的文献必然同簇（类簇偏向人工标注类目标签）；未通过锚定门槛的文献
    保留自由聚类归属（不足最小簇尺寸的并入 OUTLIER 待人工复核）。
    doc_axis_info 同步改写，保证 documents/document_assignments/趋势分析一致。
    """
    from sklearn.metrics import adjusted_rand_score

    doc_axis_info = axis_payload.get("doc_axis_info") or [dict() for _ in papers]
    free_clusters = axis_payload.get("clusters") or []
    free_label_of: dict[int, str] = {}
    for cluster in free_clusters:
        for index in cluster.get("doc_indices") or []:
            if isinstance(index, int) and 0 <= index < len(papers):
                free_label_of[index] = str(cluster.get("cluster_id") or "OUTLIER")

    groups: dict[str, list[int]] = {}
    free_remainder: list[int] = []
    for index, paper in enumerate(papers):
        match = doc_anchors.get(str(paper["document_id"]))
        if match and match.get("anchored_topic_id"):
            groups.setdefault(str(match["anchored_topic_id"]), []).append(index)
        else:
            free_remainder.append(index)

    remainder_groups: dict[str, list[int]] = {}
    for index in free_remainder:
        remainder_groups.setdefault(free_label_of.get(index, "OUTLIER"), []).append(index)

    new_clusters: list[dict[str, Any]] = []
    counter = 0
    for topic_id, indices in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        counter += 1
        cluster_id = f"C{counter:02d}"
        sample = doc_anchors.get(str(papers[indices[0]]["document_id"])) or {}
        topic_name = sample.get("anchored_topic_name") or topic_id
        keyword_counts: dict[str, int] = {}
        for index in indices:
            for term in (papers[index].get("keywords") or []):
                term = str(term).strip()
                if term:
                    keyword_counts[term] = keyword_counts.get(term, 0) + 1
        new_clusters.append({
            "cluster_id": cluster_id,
            "topic_name": topic_name,
            "anchored_topic_id": topic_id,
            "anchor_status": "anchored",
            "partition": "anchor_aligned",
            "size": len(indices),
            "doc_indices": indices,
            "representative_terms": [
                term for term, _ in sorted(keyword_counts.items(), key=lambda kv: -kv[1])[:6]
            ],
            "anchor_confidence": sample.get("anchor_confidence"),
        })
        for index in indices:
            if index < len(doc_axis_info):
                doc_axis_info[index]["topic_id"] = cluster_id
                doc_axis_info[index]["topic_name"] = topic_name
                doc_axis_info[index]["anchor_aligned"] = True

    # ---- 单例簇合并（2026-09-05）----
    # 锚定成功但只有 1 篇的簇（borderline 文献各成孤簇），三层合并策略：
    # ⓪ 同 free 社区的单例先互合并成新簇（交通+交通=2篇新簇）
    # ① 双候选第二类目匹配某已有簇 → 并入
    # ② 类目名公共子串（≥2字）匹配 → 并入
    # ③ 仍孤立的退回 free 归属（覆盖锚点库类目不足场景）
    singleton_clusters = [c for c in new_clusters if c.get("partition") == "anchor_aligned" and c.get("size") == 1]
    if len(new_clusters) - len(singleton_clusters) >= 2:
        multi_clusters = [c for c in new_clusters if c not in singleton_clusters]

        # ⓪ 同 free 社区的单例互合并
        by_free: dict[str, list] = {}
        for sc in singleton_clusters:
            s_idx = sc["doc_indices"][0]
            s_free = free_label_of.get(s_idx, "OUTLIER")
            by_free.setdefault(s_free, []).append(sc)
        for s_free, group in by_free.items():
            if len(group) >= 2:
                counter += 1
                merged_id = f"C{counter:02d}"
                all_indices = []
                for sc in group:
                    all_indices.extend(sc["doc_indices"])
                    new_clusters.remove(sc)
                sample_anchor = doc_anchors.get(str(papers[all_indices[0]]["document_id"])) or {}
                new_clusters.append({
                    "cluster_id": merged_id,
                    "topic_name": sample_anchor.get("anchored_topic_name") or group[0].get("topic_name"),
                    "anchored_topic_id": sample_anchor.get("anchored_topic_id"),
                    "anchor_status": "anchored",
                    "partition": "anchor_aligned",
                    "size": len(all_indices),
                    "doc_indices": sorted(all_indices),
                    "representative_terms": [],
                    "absorbed_singletons": [str(c.get("anchored_topic_id") or "") for c in group],
                })
                for index in all_indices:
                    if index < len(doc_axis_info):
                        doc_axis_info[index]["topic_id"] = merged_id
                        doc_axis_info[index]["topic_name"] = new_clusters[-1]["topic_name"]
                singleton_clusters = [c for c in new_clusters if c.get("partition") == "anchor_aligned" and c.get("size") == 1]
                multi_clusters = [c for c in new_clusters if c not in singleton_clusters and c.get("size") > 1]

        # ①②③ 逐个处理仍孤立的
        for sc in singleton_clusters[:]:
            s_idx = sc["doc_indices"][0]
            s_anchor = doc_anchors.get(str(papers[s_idx]["document_id"])) or {}
            s_topic = str(s_anchor.get("anchored_topic_id") or sc.get("anchored_topic_id") or "")
            s_cands = [str(c.get("topic_id") or "") for c in (s_anchor.get("candidate_topics") or [])]
            s_name = str(s_anchor.get("anchored_topic_name") or sc.get("topic_name") or "")
            merged = False

            def _absorb(mc, label):
                mc["doc_indices"].extend(sc["doc_indices"])
                mc["size"] = len(mc["doc_indices"])
                mc.setdefault("absorbed_singletons", []).append(label)
                new_clusters.remove(sc)
                for index in sc["doc_indices"]:
                    if index < len(doc_axis_info):
                        doc_axis_info[index]["topic_id"] = mc["cluster_id"]
                        doc_axis_info[index]["topic_name"] = mc["topic_name"]

            # ① 双候选第二类目匹配
            for mc in multi_clusters:
                m_topic = str(mc.get("anchored_topic_id") or "")
                if m_topic and m_topic in s_cands and m_topic != s_topic:
                    _absorb(mc, s_topic); merged = True; break
            if merged: continue

            # ② 类目名公共子串
            for mc in multi_clusters:
                m_name = str(mc.get("topic_name") or "")
                common = next((s_name[i:i+j] for i in range(len(s_name)-1)
                               for j in range(min(len(s_name)-i, len(m_name)), 1, -1)
                               if len(s_name[i:i+j]) >= 2 and s_name[i:i+j] in m_name), "")
                if common:
                    _absorb(mc, s_topic or s_name); merged = True; break
            if merged: continue

            # ③ 退回 free 归属
            s_free_label = free_label_of.get(s_idx, "OUTLIER")
            for mc in multi_clusters:
                if any(free_label_of.get(idx) == s_free_label for idx in mc["doc_indices"]):
                    _absorb(mc, s_topic or s_name); merged = True; break

    outlier_indices: list[int] = []
    for free_id, indices in sorted(remainder_groups.items(), key=lambda kv: -len(kv[1])):
        if free_id == "OUTLIER" or len(indices) < 2:
            outlier_indices.extend(indices)
            continue
        counter += 1
        cluster_id = f"C{counter:02d}"
        original = next(
            (c for c in free_clusters if str(c.get("cluster_id")) == free_id), {})
        new_clusters.append({
            "cluster_id": cluster_id,
            "topic_name": original.get("topic_name") or free_id,
            "partition": "free",
            "size": len(indices),
            "doc_indices": indices,
            "representative_terms": original.get("representative_terms") or [],
        })
        for index in indices:
            if index < len(doc_axis_info):
                doc_axis_info[index]["topic_id"] = cluster_id
                doc_axis_info[index]["topic_name"] = original.get("topic_name") or free_id
    if outlier_indices:
        new_clusters.append({
            "cluster_id": "OUTLIER", "topic_name": "待人工复核", "partition": "free",
            "size": len(outlier_indices), "doc_indices": sorted(outlier_indices),
            "representative_terms": [],
        })
        for index in outlier_indices:
            if index < len(doc_axis_info):
                doc_axis_info[index]["topic_id"] = "OUTLIER"
                doc_axis_info[index]["topic_name"] = "待人工复核"

    axis_payload["clusters"] = new_clusters
    axis_payload["doc_axis_info"] = doc_axis_info

    new_label_of = {
        index: str(cluster.get("cluster_id"))
        for cluster in new_clusters
        for index in (cluster.get("doc_indices") or [])
    }
    free_labels = [free_label_of.get(i, "OUTLIER") for i in range(len(papers))]
    new_labels = [new_label_of.get(i, "OUTLIER") for i in range(len(papers))]
    agreement = adjusted_rand_score(free_labels, new_labels) if len(papers) > 1 else None
    return {
        "mode": "anchor_aligned",
        "anchored_cluster_count": len(groups),
        "free_cluster_count": sum(1 for fid in remainder_groups if fid != "OUTLIER" and len(remainder_groups[fid]) >= 2),
        "outlier_count": len(outlier_indices),
        "coverage": round((len(papers) - len(free_remainder)) / len(papers), 4) if papers else 0.0,
        "agreement_ari": round(float(agreement), 4) if agreement is not None else None,
    }


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
        params.get("clustering_algorithm_type")
        or params.get("cluster_method") or params.get("algorithm") or "auto"
    ).strip()
    algorithm = _ALGORITHM_ALIASES.get(requested_algorithm.lower(), requested_algorithm.lower())
    if algorithm not in ALLOWED_ALGORITHMS:
        raise ValueError(
            "clustering_algorithm_type 必须为 auto(自动选择)、kmeans、spectral(谱聚类)、"
            "agglomerative(凝聚聚类)、hierarchical(层次聚类) 或 hdbscan。"
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
    partition_strategy = str(params.get("partition_strategy") or "free").strip().lower()
    if partition_strategy not in {"free", "anchor_aligned"}:
        raise ValueError("partition_strategy 必须为 free 或 anchor_aligned。")

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

    # ---- 锚点辅助：用户上传的训练样本/人工标注类目资源为主力（上传即主导，
    # 类簇向用户标注体系对齐）；内置槽位为辅——用户库不达门槛的文献由内置补位；
    # 用户未上传时仅用内置。use_builtin_anchor=false 可完全关闭内置。
    anchor_output: dict[str, Any] = {"enabled": False}
    try:
        from infrastructure.clustering.anchor_labeling import (
            resolve_anchor_libraries, anchor_assist, aggregate_cluster_anchor,
        )
        use_builtin = str(
            params.get("use_builtin_anchor", "true")
        ).strip().lower() not in {"0", "false", "no", "off"}
        libraries = resolve_anchor_libraries(
            params.get("resolved_resources"), use_builtin=use_builtin)
        if libraries["builtin"] is not None or libraries["user"] is not None:
            anchor_output = anchor_assist(
                normalized_papers, selected_axis,
                builtin_path=libraries["builtin"],
                user_path=libraries["user"],
                threshold=float(params.get("anchor_similarity_threshold", 0) or 0.45),
                min_combined=(
                    float(params["anchor_min_combined"])
                    if params.get("anchor_min_combined") not in (None, "") else None
                ),
                use_arbiter=str(
                    params.get("anchor_arbiter", "on")
                ).strip().lower() not in {"0", "false", "no", "off"},
                quality_margin=(
                    float(params["anchor_quality_margin"])
                    if params.get("anchor_quality_margin") not in (None, "") else None
                ),
            )
    except ImportError:
        logger.warning("锚点模块不可用，深度聚类按自由聚类执行", exc_info=True)
    doc_anchors = anchor_output.get("document_anchors") or {}

    # ---- 锚点对齐重划分（可选）：partition_strategy=anchor_aligned 时，用户上传的
    # 训练样本/人工标注类目不仅给类簇命名，还直接引导划分——锚定成功的文献按
    # 人工类目成簇（类簇偏向人工标注类目标签），未锚定文献保留自由聚类归属。
    # 划分决策来自用户标注库的语义近邻投票，与 LLM 无关。
    partition_stats: dict[str, Any] = {"mode": "free"}
    if partition_strategy == "anchor_aligned":
        if doc_anchors:
            target_payload = technical if selected_axis == "technical" else application
            if target_payload:
                partition_stats = _repartition_anchor_aligned(
                    target_payload, normalized_papers, doc_anchors)
            else:
                partition_stats = {"mode": "free", "requested": "anchor_aligned",
                                   "note": "所选轴无聚类结果，回落自由聚类划分。"}
        else:
            partition_stats = {
                "mode": "free", "requested": "anchor_aligned",
                "note": "锚点未启用（未选择资源）或锚点库为空，回落自由聚类划分。",
            }

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
        # 相似度与最近邻 gold 证据随行输出：锚定结论可人工核查（对得上是哪几篇标注文献）
        "anchor_similarity": (doc_anchors.get(str(item["document_id"])) or {}).get("anchor_similarity"),
        "nearest_gold_documents": (doc_anchors.get(str(item["document_id"])) or {}).get("nearest_gold_documents"),
        "anchor_source": (doc_anchors.get(str(item["document_id"])) or {}).get("anchor_source"),
        # 低置信双候选：胶着判断（判别头 top-2 概率差<0.10）并列给出两个类目
        "anchor_confidence_level": (doc_anchors.get(str(item["document_id"])) or {}).get("anchor_confidence_level"),
        "candidate_topics": (doc_anchors.get(str(item["document_id"])) or {}).get("candidate_topics"),
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
                # 簇内成员类目分布（主锚定 1 票 + 胶着双候选第二类目 1 票）：
                # 弹窗与聚类标签生成的共同参照——纯簇单一类目，混簇两个类目并列
                from collections import Counter
                distribution: Counter = Counter()
                for member_id in member_ids:
                    match = doc_anchors.get(str(member_id))
                    if not match:
                        continue
                    primary = str(match.get("anchored_topic_name") or "").strip()
                    if primary:
                        distribution[primary] += 1
                    for candidate in match.get("candidate_topics") or []:
                        name = str((candidate or {}).get("topic_name") or "").strip()
                        if name and name != primary:
                            distribution[name] += 1
                if distribution:
                    cluster["category_distribution"] = [
                        {"name": name, "count": count}
                        for name, count in distribution.most_common()
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
        "partition_strategy": partition_stats.get("mode", "free"),
        "anchor_partition_coverage": partition_stats.get("coverage"),
        "anchor_partition_agreement_ari": partition_stats.get("agreement_ari"),
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

    # 改动1: 所选轴跑完后，锚定不达门槛的簇由 GLM 生成中文簇标签兜底
    # （技术轴=技术路线标签，应用轴=场景标签），替换纯 sparse 高频 token 拼出的
    # topic_name（如 "training / our"）。已锚定的簇保留人工标注类目名；
    # 失败/未配置 GLM 时回退原 sparse 值，不阻断聚类。
    scene_labeling: dict[str, Any] = {}
    selected_payload = application if selected_axis == "application" else technical
    if selected_payload:
        scene_labeling = _regenerate_axis_cluster_labels(
            selected_payload, normalized_papers, glm_client, selected_axis
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
            "partition_strategy": partition_stats.get("mode", "free"),
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
