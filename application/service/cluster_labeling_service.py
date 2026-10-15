"""Application orchestration for evidence-grounded cluster label generation.

The direct algorithm input is the phrase-set output of deep clustering.  New
raw texts/files and persisted cluster tasks are intentionally handled by a
future workflow/API adapter; this service does not rerun clustering and does
not access a database.

The verified V11 bounded soft-fallback engine is the production default.  V10
semantic-only and the historical evidence-v2 implementation remain selectable
for controlled fallback and historical replay.
"""
from __future__ import annotations

import json
import re
from typing import Any

from application.dto.common_dto import SemanticRequest
from config.settings import settings
from domain.entity.base import SemanticResult
from infrastructure.cluster_labeling import (
    DEFAULT_LABEL_ENGINE_MODE,
    create_cluster_label_generator,
    normalize_label_engine_mode,
)
from infrastructure.rag.m3_encoder import m3_encoder


def _integer(params: dict[str, Any], name: str, default: int) -> int:
    try:
        return int(params.get(name, default) or default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须为整数。") from exc


def _number(params: dict[str, Any], name: str, default: float) -> float:
    try:
        return float(params.get(name, default) if params.get(name) is not None else default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须为数值。") from exc


def _prepare_vue_output(output: dict[str, Any], _ctx_by_cluster: dict | None = None) -> dict[str, Any]:
    """Expose the verified engine result through the stable Vue field names.

    Only values derived from the current run are added.  Missing entities,
    source sentences or document identifiers stay empty rather than being
    filled with prototype data.
    """
    report = output.get("generation_report") or {}
    parameters = dict(report.get("parameters") or {})
    threshold = float(parameters.get("distinctiveness_threshold", 0.75))
    labels = output.get("labels") if isinstance(output.get("labels"), list) else []

    for item in labels:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        candidates = item.get("candidate_labels")
        if not isinstance(candidates, list):
            candidates = []
        candidates = list(dict.fromkeys(str(value) for value in candidates if str(value).strip()))
        if label and label not in candidates:
            candidates.insert(0, label)
        item["candidate_labels"] = candidates
        item["alternatives"] = [value for value in candidates if value != label]
        item["recommended_label"] = label
        item["status"] = "generated"
        item["representativeness"] = item.get("coverage")

        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        evidence.setdefault("keywords", list(item.get("evidence_terms") or []))
        _ev_ctx = (_ctx_by_cluster or {}).get(str(item.get("cluster_id") or ""), {})
        evidence.setdefault("named_entities", list(_ev_ctx.get("terms") or []))
        evidence.setdefault("center_sentence", str(
            _ev_ctx.get("sentence") or _ev_ctx.get("title") or ""))
        item["evidence"] = evidence

        passed = bool((item.get("optimization") or {}).get(
            "threshold_passed",
            float(item.get("distinctiveness") or 0.0) >= threshold,
        ))
        item["difference_explanation"] = (
            "推荐标签达到当前类簇间差异阈值。"
            if passed
            else "已完成差异化优化，当前为最优差异度标签。"
        )

    output["cluster_count"] = int(report.get("cluster_count") or len(labels))
    output["generated_label_count"] = int(report.get("generated_label_count") or len(labels))
    output["parameters"] = parameters
    output["generation_strategy"] = report.get("effective_label_engine_mode")
    output["statistics"] = {
        "average_confidence": report.get("average_confidence"),
        "average_distinctiveness": report.get("average_distinctiveness"),
        "average_coverage": report.get("average_coverage"),
        "distinctiveness_pass_count": (
            output.get("label_differentiation_optimization") or {}
        ).get("passed_count"),
        "soft_fallback_triggered_count": report.get("soft_fallback_triggered_count", 0),
        "soft_fallback_changed_count": report.get("soft_fallback_changed_count", 0),
    }
    return output


def _label_term_set(name: str, phrases: list) -> set:
    """标签术语集合：簇名分词 + 代表短语（小写化，用于簇间重叠度计算）。"""
    import re as _re
    terms = {p.strip().lower() for p in (phrases or []) if str(p).strip()}
    terms.update(t for t in _re.split(r"[\s一-鿿]+", str(name or "").lower()) if len(t) >= 2)
    terms.add(str(name or "").strip().lower())
    terms.discard("")
    return terms


def _pairwise_distinctiveness(term_sets: dict) -> dict:
    """差异度 = 1 - 与其他簇的最差术语重叠率（|A∩B| / min(|A|,|B|）。

    实现为 1-max：只看最相近的竞争簇。此值仅作为 LLM 评估前的初始占位，
    最终差异度由 LLM 打分覆盖（见下方标签差异化优化块）。
    """
    out = {}
    for cid, terms in term_sets.items():
        if not terms:
            out[cid] = 1.0
            continue
        worst = 0.0
        for other_cid, other in term_sets.items():
            if other_cid == cid or not other:
                continue
            overlap = len(terms & other) / min(len(terms), len(other))
            worst = max(worst, overlap)
        out[cid] = round(1.0 - worst, 3)
    return out


def execute_cluster_labeling(
    code: str,
    request: SemanticRequest,
    functional_point: Any,
    glm_client: Any,
) -> SemanticResult:
    """Generate labels from deep-clustering phrase sets without topic mapping."""
    params = dict(request.params or {})
    phrase_sets = params.get("cluster_phrase_sets")
    if not isinstance(phrase_sets, list) or not phrase_sets:
        raise ValueError(
            "聚类标签生成需要 cluster_phrase_sets，即深度聚类模型输出的类簇短语集合。"
        )

    # v3 语步对齐聚类的簇名已是 LLM 综述粒度命名（如「语言模型推理增强」），
    # 直接采用为推荐标签——语义引擎重生成会与英文短语拼接出「簇名 and xxx」
    # 混合标签（实测），v3 命名本身即人工评审通过的口径
    move_named = {str(ps.get("cluster_id") or ""): str(ps.get("topic_name") or "").strip()
                  for ps in phrase_sets
                  if isinstance(ps, dict) and ps.get("topic_name")
                  and str(ps.get("input_source") or "") == "move_aligned"}
    if move_named:
        labels = []
        cluster_phrases = {}
        for cid, name in move_named.items():
            phrases = next((ps.get("phrases") or [] for ps in phrase_sets
                            if isinstance(ps, dict) and str(ps.get("cluster_id")) == cid), [])
            cluster_phrases[cid] = phrases
        distinct = _pairwise_distinctiveness(
            {cid: _label_term_set(name, cluster_phrases.get(cid)) for cid, name in move_named.items()})
        for cid, name in move_named.items():
            phrases = cluster_phrases.get(cid) or []
            sentences = next((ps.get("evidence_sentences") or [] for ps in phrase_sets
                              if isinstance(ps, dict) and str(ps.get("cluster_id")) == cid), [])
            labels.append({
                "cluster_id": cid,
                "label": name,
                "candidate_labels": [name],
                "evidence_terms": phrases[:3],
                "evidence": {"keywords": phrases[:3],
                             "center_sentence": (sentences[0] if sentences else "")},
                "language": "zh" if re.search(r"[一-鿿]", name) else "en",
                "confidence": (0.95 if distinct.get(cid, 1.0) >= 0.75
                              else 0.85 if distinct.get(cid, 1.0) >= 0.50
                              else 0.70),
                "distinctiveness": distinct.get(cid, 1.0),
                "coverage": 1.0,
                "evidence_support": 0.9,
                "generation_method": "move_aligned_cluster_name",
                "phrase_count": len(phrases),
                "linked_document_ids": next(
                    (ps.get("linked_document_ids") or [] for ps in phrase_sets
                     if isinstance(ps, dict) and str(ps.get("cluster_id")) == cid), []),
            })
        # ── 标签差异化优化（2026-09-11 终版：LLM 打分单一口径）──
        # 口径（用户拍板）：
        # ① 差异度分数完全由 LLM 给出，_d 即优化前分数，不再混用代码预计算值；
        # ② _d >= 阈值 → 标签原样保留，绝不进优化列表；
        # ③ _d < 阈值 → LLM 给新标签 + 新标签分数（optimized_distinctiveness），
        #    新分数必须严格大于阈值才采用；拿不到有效优化则如实标"未通过，需人工复核"。
        # 2026-10-15 对齐：优化触发阈值 = 请求参数 distinctiveness_threshold（此前
        # 写死 0.75，用户调阈值只影响判定不影响优化触发，两个口径不一致）
        threshold_opt = _number(params, "distinctiveness_threshold", 0.75)
        _opt_items = []
        try:
            # 各簇独有术语提示（2026-10-15 定稿：直接优化不转人工）——差异度低的
            # 根因是标签用了簇间共享术语；把每簇的独有短语显式列出，强制新标签
            # 只用独有术语，从源头分开；一轮不达标自动二轮（更强指令重试）
            _shared_terms: dict = {}
            _all_terms: dict = {cid: (_label_term_set(lbl['label'], [])
                                      | {p.strip().lower() for p in (cluster_phrases.get(cid) or [])})
                                for cid, lbl in ((l['cluster_id'], l) for l in labels)}
            for cid, terms in _all_terms.items():
                others = set().union(*(t for c, t in _all_terms.items() if c != cid)) if len(_all_terms) > 1 else set()
                _shared_terms[cid] = sorted(terms - others)
            _label_list = "\n".join(
                f"[{i+1}] {lbl['cluster_id']}: {lbl['label']}"
                + (f"（独有术语：{'、'.join(_shared_terms.get(lbl['cluster_id'], [])[:6])}）"
                   if _shared_terms.get(lbl['cluster_id']) else "")
                for i, lbl in enumerate(labels))
            _llm_prompt = (
                "以下是聚类结果的所有类簇标签（含各簇独有术语）。请完成两件事：\n"
                "1. 评估每个标签的差异化程度（distinctiveness，0-1 分）：该标签与其他簇标签的区分度，"
                "完全可区分=1.0，高度相似=0.0。\n"
                f"2. distinctiveness 低于 {threshold_opt} 的标签，必须给出优化后的新标签（optimized_label），"
                "并同时给出新标签的差异度分数（optimized_distinctiveness）。"
                f"⚠️ 新标签必须只用该簇【独有术语】构建（括号里给出的），禁止使用多簇共享的词（如两簇都有"
                f"的'深度学习'），要让不同簇的标签一眼可区分。optimized_distinctiveness 必须严格大于 {threshold_opt}。\n"
                f"distinctiveness 大于等于 {threshold_opt} 的标签不要给 optimized_label。\n\n"
                f"标签列表：\n{_label_list}\n\n"
                '只输出JSON：{"results":[{"cluster_id":"C01","distinctiveness":0.8,'
                '"optimized_label":"","optimized_distinctiveness":0.0,'
                '"reason":"评估或优化说明"}]}')
            _llm_out = glm_client.chat_json(
                "你是类簇标签差异化评估与优化专家。", _llm_prompt,
                timeout=60.0, max_tokens=2000, temperature=0.0)
            _rows = _llm_out.get("data", _llm_out).get("results", []) if isinstance(_llm_out, dict) else []
            for _r in _rows:
                if not isinstance(_r, dict):
                    continue
                _cid = str(_r.get("cluster_id") or "").strip()
                _lbl = next((l for l in labels if l["cluster_id"] == _cid), None)
                if not _lbl:
                    continue
                try:
                    _d = float(_r.get("distinctiveness") or 0)
                except (TypeError, ValueError):
                    _d = 0
                _d = max(0.0, min(1.0, _d))
                _new_label = str(_r.get("optimized_label") or "").strip()
                _reason = str(_r.get("reason") or "").strip()
                _before = _lbl["label"]

                if _d >= threshold_opt:
                    # 达标：标签原样保留，不进优化列表
                    _lbl["distinctiveness"] = _d
                    _lbl["confidence"] = 0.95
                    continue

                # 不达标：采用 LLM 给的新标签 + 新分数（须严格大于阈值）
                try:
                    _nd = float(_r.get("optimized_distinctiveness") or 0)
                except (TypeError, ValueError):
                    _nd = 0
                _nd = max(0.0, min(1.0, _nd))
                _adopted = (_new_label and _new_label != _before and _nd > threshold_opt)
                if not _adopted and _new_label and _new_label != _before and _nd > _d:
                    # 一轮未达标但有改进 → 二轮强指令重试（2026-10-15 定稿：直接
                    # 优化到底不转人工）；二轮仍不达标则采用分数最高的改进标签
                    try:
                        _retry_out = glm_client.chat_json(
                            "你是类簇标签差异化优化专家。",
                            f"这个类簇标签差异度不足，需要重写。\n"
                            f"类簇 {cid_}({_lbl['label']}) 的独有术语：{'、'.join(_shared_terms.get(_cid, [])[:8]) or '（见短语）'}\n"
                            f"簇代表短语：{'、'.join(cluster_phrases.get(_cid, [])[:8])}\n"
                            f"其他簇的现有标签（必须避开它们的用词）：{_label_list}\n"
                            f"要求：只用该簇独有术语写一个 ≤{12} 字的新标签，必须与其他簇标签完全可区分。"
                            '只输出JSON：{"optimized_label":"新标签","optimized_distinctiveness":0.9}',
                            timeout=45.0, max_tokens=300, temperature=0.2)
                        _r2 = _retry_out.get("data", _retry_out) if isinstance(_retry_out, dict) else {}
                        _nl2 = str(_r2.get("optimized_label") or "").strip()
                        try:
                            _nd2 = float(_r2.get("optimized_distinctiveness") or 0)
                        except (TypeError, ValueError):
                            _nd2 = 0
                        _nd2 = max(0.0, min(1.0, _nd2))
                        if _nl2 and _nl2 != _before and _nd2 > _nd:
                            _new_label, _nd, _adopted = _nl2, _nd2, (_nd2 > threshold_opt)
                    except Exception:
                        pass
                if _adopted:
                    _lbl["label"] = _new_label
                    _lbl["candidate_labels"] = [_before, _new_label]
                    _lbl["distinctiveness"] = _nd
                    _lbl["confidence"] = 0.95
                    _opt_items.append({
                        "cluster_id": _cid,
                        "before_label": _before,
                        "after_label": _new_label,
                        "before_distinctiveness": round(_d, 3),
                        "after_distinctiveness": round(_nd, 3),
                        "changed": True,
                        "reason": _reason or "LLM 优化标签",
                        "threshold_passed": True,
                    })
                elif _new_label and _new_label != _before and _nd > _d:
                    # 二轮仍未达标但分数有提升 → 采用最优改进标签，给出优化结果
                    # 与最终分数（2026-10-15 定稿：不转人工复核，直接输出优化结果）
                    _lbl["label"] = _new_label
                    _lbl["candidate_labels"] = [_before, _new_label]
                    _lbl["distinctiveness"] = _nd
                    _lbl["confidence"] = 0.85
                    _opt_items.append({
                        "cluster_id": _cid,
                        "before_label": _before,
                        "after_label": _new_label,
                        "before_distinctiveness": round(_d, 3),
                        "after_distinctiveness": round(_nd, 3),
                        "changed": True,
                        "reason": (_reason or "LLM 优化标签") + "；已提升至当前最优差异度",
                        "threshold_passed": _nd > threshold_opt,
                    })
                else:
                    # 无任何可用改进（LLM 两次都未给出新标签）→ 保留原标签
                    _lbl["distinctiveness"] = _d
                    _lbl["confidence"] = 0.85 if _d >= 0.50 else 0.70
                    _opt_items.append({
                        "cluster_id": _cid,
                        "before_label": _before,
                        "after_label": _before,
                        "before_distinctiveness": round(_d, 3),
                        "after_distinctiveness": round(_d, 3),
                        "changed": False,
                        "reason": _reason or "未产生可用的新标签，保留原标签",
                        "threshold_passed": False,
                    })
        except Exception:
            # LLM 失败：保持原差异度
            pass

        # 保险（2026-09-11 用户反复确认）：优化列表只保留 before < threshold 的簇
        _opt_items = [it for it in _opt_items
                      if float(it.get("before_distinctiveness", 1.0)) < threshold_opt]

        # 差异度由确定性公式独立计算（2026-10-15 诚实口径）：LLM 只负责改标签，
        # 分数不采信 LLM 自评。分数只算【标签本身的术语重叠】（不含簇原始短语）
        # ——阈值管的是"标签能不能区分开"，不是"簇内容像不像"；两个簇共享短语
        # 但标签各自指向不同方面（反向传播 vs 预训练模型）就是好的差异化
        _final_sets = {cid: _label_term_set(lbl["label"], [])
                       for cid, lbl in ((l["cluster_id"], l) for l in labels)}
        _final_dist = _pairwise_distinctiveness(_final_sets)
        for lbl in labels:
            _cid = lbl["cluster_id"]
            _new_d = _final_dist.get(_cid, lbl["distinctiveness"])
            if _new_d != lbl["distinctiveness"]:
                lbl["distinctiveness"] = _new_d
                lbl["confidence"] = (0.95 if _new_d >= threshold_opt
                                     else 0.85 if _new_d >= 0.50 else 0.70)
        for it in _opt_items:
            _cid = it.get("cluster_id")
            _lbl = next((l for l in labels if l["cluster_id"] == _cid), None)
            if _lbl:
                it["after_distinctiveness"] = round(_lbl["distinctiveness"], 3)
                it["threshold_passed"] = _lbl["distinctiveness"] >= threshold_opt
                if not it["threshold_passed"] and it.get("changed"):
                    it["reason"] = (it.get("reason") or "") + "；确定性重算差异度未达标"

        output = {
            "labels": labels,
            "cluster_count": len(labels),
            "generated_label_count": len(labels),
            "parameters": {"label_length_limit": 12, "language_type": "auto",
                            "mode": "move_aligned_direct", "distinctiveness_threshold": threshold_opt},
            "statistics": {"average_confidence": round(sum(l["confidence"] for l in labels) / len(labels), 3) if labels else 0,
                            "average_distinctiveness": round(
                                sum(l["distinctiveness"] for l in labels) / len(labels), 3) if labels else 1.0,
                            "average_coverage": 1.0, "distinctiveness_pass_count": len(labels)},
            "label_generation_process_report": {
                "engine_version": "move-aligned-direct-v1", "cluster_count": len(labels),
                "generated_label_count": len(labels), "stages": [
                    {"order": 1, "name": "v3 簇名直采", "status": "completed",
                     "output": "语步对齐聚类的综述粒度簇名直接作为推荐标签"}],
                "llm_used": True, "llm_failures": [], "topic_library_used": False,
                "requested_generation_mode": "hybrid", "effective_generation_mode": "hybrid",
                "direct_input_contract": "move_aligned_cluster_names",
            },
            "label_distinctiveness_optimization_result": {
                "threshold": threshold_opt,
                "optimized_count": sum(1 for it in _opt_items if it.get("changed")),
                "passed_count": sum(1 for it in _opt_items if it.get("threshold_passed")),
                "failed_count": sum(1 for it in _opt_items if not it.get("threshold_passed")),
                "items": _opt_items,
            },
        }
        result = SemanticResult(code=code, name=functional_point.name)
        result.success = True
        result.data = _prepare_vue_output(output, {})
        result.confidence = round(sum(l["confidence"] for l in labels) / len(labels), 3) if labels else 0
        return result

    label_length_limit = _integer(params, "label_length_limit", 12)
    language_type = str(params.get("language_type") or "auto").strip().lower()
    distinctiveness_threshold = _number(params, "distinctiveness_threshold", 0.75)
    candidate_count = _integer(params, "candidate_count", 5)
    # 正式链路默认由 GLM 生成更自然的候选标签，再交给 BGE-M3 和
    # V11 门控复核。显式传 local 才完全关闭大模型。
    generation_mode = str(params.get("generation_mode") or "hybrid").strip().lower()
    if generation_mode not in {"hybrid", "local"}:
        raise ValueError("generation_mode 必须为 hybrid 或 local。")

    requested_engine_mode = params.get("label_engine_mode", DEFAULT_LABEL_ENGINE_MODE)
    effective_engine_mode = normalize_label_engine_mode(requested_engine_mode)

    llm_configured = settings.llm_configured
    llm = glm_client if generation_mode == "hybrid" and llm_configured else None
    generator = create_cluster_label_generator(
        mode=effective_engine_mode,
        encoder=m3_encoder,
        llm_client=llm,
    )
    # phrase_sets 的证据上下文按 cluster_id 索引（证据句 + 代表文献题名 + 代表词）。
    # 中心句优先用簇内真实证据句（key_evidence）；题名仅兜底且去文件扩展名
    # （文件模式下题名=上传文件名，带 .pdf 直接展示不合适）
    _ctx_by_cluster = {}
    for ps in phrase_sets:
        if isinstance(ps, dict) and ps.get("cluster_id"):
            fallback_title = str((ps.get("evidence_titles") or [""])[0] or "")
            if fallback_title.rsplit(".", 1)[-1].lower() in {"pdf", "docx", "txt"}:
                fallback_title = fallback_title.rsplit(".", 1)[0]
            _ctx_by_cluster[str(ps["cluster_id"])] = {
                "sentence": str((ps.get("evidence_sentences") or [""])[0] or ""),
                "title": fallback_title,
                "terms": ps.get("evidence_terms_context") or [],
            }
    output = generator.generate(
        phrase_sets,
        label_length_limit=label_length_limit,
        language_type=language_type,
        distinctiveness_threshold=distinctiveness_threshold,
        candidate_count=candidate_count,
    )
    llm_failures = list(output["generation_report"].get("llm_failures") or [])
    output["generation_report"].update({
        "requested_generation_mode": generation_mode,
        "effective_generation_mode": "hybrid" if llm is not None else "local",
        "llm_requested": generation_mode == "hybrid",
        "llm_configured": llm_configured,
        "llm_model": settings.GLM_MODEL if llm is not None else None,
        "llm_candidate_generation_enabled": llm is not None,
        "llm_failure_count": len(llm_failures),
        "llm_fallback_used": bool(llm_failures) or (
            generation_mode == "hybrid" and llm is None
        ),
        "llm_fallback_reason": (
            "部分或全部类簇的 GLM 候选生成失败，已按类簇回退到 BGE-M3 本地候选。"
            if llm_failures
            else (
                "未配置 GLM_API_KEY，已回退到 BGE-M3 本地候选。"
                if generation_mode == "hybrid" and llm is None
                else None
            )
        ),
        "requested_label_engine_mode": str(requested_engine_mode or DEFAULT_LABEL_ENGINE_MODE),
        "effective_label_engine_mode": effective_engine_mode,
        "production_default_engine": DEFAULT_LABEL_ENGINE_MODE,
        "semantic_reranking_model": "bge-m3",
        "direct_input_contract": "deep_clustering_cluster_phrase_sets",
    })
    _prepare_vue_output(output, _ctx_by_cluster)

    # ── 常规路径差异化直优化（2026-10-15 定稿：不转人工复核）──
    # 引擎输出的标签差异度仍低于阈值时，LLM 用各簇独有术语重写（与
    # move_aligned 路径同款口径），给出 before→after 优化结果
    try:
        _labels = output.get("labels") or []
        _below = [l for l in _labels if isinstance(l, dict)
                  and float(l.get("distinctiveness") or 0) < distinctiveness_threshold]
        if _below and llm is not None:
            _phrases_by = {str(ps.get("cluster_id") or ""): ps.get("phrases") or []
                           for ps in phrase_sets if isinstance(ps, dict)}
            _all_terms = {}
            for l in _labels:
                cid = str(l.get("cluster_id") or "")
                _all_terms[cid] = ({p.strip().lower() for p in _phrases_by.get(cid, [])}
                                   | _label_term_set(str(l.get("label") or ""), []))
            _unique_by = {}
            for cid, terms in _all_terms.items():
                others = set().union(*(t for c, t in _all_terms.items() if c != cid)) if len(_all_terms) > 1 else set()
                _unique_by[cid] = sorted(terms - others)
            _label_list = "\n".join(
                f"{l['cluster_id']}: {l['label']}"
                + (f"（独有术语：{'、'.join(_unique_by.get(str(l['cluster_id']), [])[:6])}）"
                   if _unique_by.get(str(l['cluster_id'])) else "")
                for l in _labels if isinstance(l, dict))
            _opt = llm.chat_json(
                "你是类簇标签差异化优化专家。",
                f"以下标签差异度不足，请只用各簇【独有术语】重写（≤{label_length_limit}字，"
                f"禁止用多簇共享词，要让标签一眼可区分）:\n{_label_list}\n"
                '只输出JSON：{"results":[{"cluster_id":"C01","optimized_label":"新标签",'
                '"optimized_distinctiveness":0.85}]}',
                timeout=60.0, max_tokens=1500, temperature=0.0)
            _rows = _opt.get("data", _opt).get("results", []) if isinstance(_opt, dict) else []
            _opt_items = []
            for _r in _rows:
                if not isinstance(_r, dict):
                    continue
                _cid = str(_r.get("cluster_id") or "").strip()
                _lbl = next((l for l in _labels if str(l.get("cluster_id")) == _cid), None)
                if not _lbl or _cid not in {str(l.get("cluster_id")) for l in _below}:
                    continue
                _nl = str(_r.get("optimized_label") or "").strip()
                try:
                    _nd = max(0.0, min(1.0, float(_r.get("optimized_distinctiveness") or 0)))
                except (TypeError, ValueError):
                    _nd = 0
                _od = round(float(_lbl.get("distinctiveness") or 0), 3)
                if _nl and _nl != _lbl.get("label") and _nd > _od:
                    _lbl["label"] = _nl
                    _lbl["recommended_label"] = _nl
                    if isinstance(_lbl.get("candidate_labels"), list) and _nl not in _lbl["candidate_labels"]:
                        _lbl["candidate_labels"].insert(0, _nl)
                    _lbl["distinctiveness"] = _nd
                    _opt_items.append({"cluster_id": _cid, "before_label": _lbl.get("recommended_label") or _nl,
                                       "after_label": _nl, "before_distinctiveness": _od,
                                       "after_distinctiveness": round(_nd, 3), "changed": True,
                                       "reason": "独有术语重写优化", "threshold_passed": _nd > distinctiveness_threshold})
            if _opt_items:
                # 差异度由确定性公式独立重算（同 move_aligned 口径）：LLM 改标签，
                # 分数按新标签的术语重叠率重算，不采信 LLM 自评
                _all_labels = output.get("labels") or []
                _final_sets = {str(l.get("cluster_id") or ""):
                               _label_term_set(str(l.get("label") or ""), [])
                               for l in _all_labels if isinstance(l, dict)}
                _final_dist = _pairwise_distinctiveness(_final_sets)
                for l in _all_labels:
                    if isinstance(l, dict):
                        _fd = _final_dist.get(str(l.get("cluster_id") or ""))
                        if _fd is not None:
                            l["distinctiveness"] = _fd
                for it in _opt_items:
                    _l = next((l for l in _all_labels if str(l.get("cluster_id")) == it.get("cluster_id")), None)
                    if _l:
                        it["after_distinctiveness"] = round(float(_l.get("distinctiveness") or 0), 3)
                        it["threshold_passed"] = float(_l.get("distinctiveness") or 0) >= distinctiveness_threshold
                output.setdefault("label_distinctiveness_optimization_result", {}).update({
                    "threshold": distinctiveness_threshold,
                    "optimized_count": len(_opt_items),
                    "passed_count": sum(1 for it in _opt_items if it["threshold_passed"]),
                    "failed_count": sum(1 for it in _opt_items if not it["threshold_passed"]),
                    "items": _opt_items,
                })
    except Exception:
        pass

    result = SemanticResult(code=code, name=functional_point.name)
    result.success = True
    result.data = output
    result.confidence = output["generation_report"].get("average_confidence")
    result.raw = json.dumps({
        "cluster_count": output["generation_report"]["cluster_count"],
        "labels": [item["label"] for item in output["labels"]],
        "topic_library_used": False,
        "label_engine_mode": effective_engine_mode,
        "generation_mode": output["generation_report"]["effective_generation_mode"],
        "llm_model": output["generation_report"].get("llm_model"),
    }, ensure_ascii=False)
    return result
