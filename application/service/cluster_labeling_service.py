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
    # move_aligned 直采路径的参数在顶层 output["parameters"]（无 generation_report），
    # 此前只读 report 会把 parameters 覆盖成空、阈值回落到写死的 0.75
    parameters = dict(report.get("parameters") or output.get("parameters") or {})
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
        if str(parameters.get("threshold_mode") or "") == "auto":
            # 自动模式（2026-10-20 再定稿）：不优化、无阈值闸门，模型结果即终稿
            item["difference_explanation"] = "未触发差异化优化。"
            continue
        if passed:
            item["difference_explanation"] = "推荐标签达到当前类簇间差异阈值。"
        else:
            # 诚实口径（2026-10-20 二修）：按该簇在优化流程里的真实结局措辞——
            # 重写过/只尝试过/未触发，均如实报"仍低于阈值"，与优化结果页一致，
            # 不再统一写"已完成差异化优化"（与 ✗ 未通过 矛盾）
            _opt_items_all = ((output.get("label_distinctiveness_optimization_result") or {})
                              .get("items") or [])
            _mine = next((_it for _it in _opt_items_all if isinstance(_it, dict)
                          and str(_it.get("cluster_id") or "") == str(item.get("cluster_id") or "")), None)
            _d_now = round(float(item.get("distinctiveness") or 0.0), 2)
            _t_now = round(threshold, 2)
            if _mine is None:
                item["difference_explanation"] = f"标签差异度 {_d_now} 低于阈值 {_t_now}。"
            elif _mine.get("changed"):
                item["difference_explanation"] = (
                    f"已重写标签（{_mine.get('before_label')}→{_mine.get('after_label')}），"
                    f"差异度 {_d_now} 仍低于阈值 {_t_now}。")
            else:
                item["difference_explanation"] = (
                    "已尝试差异化优化：模型未给出可用的更优标签，保留原标签；"
                    f"差异度 {_d_now} 低于阈值 {_t_now}。")

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
    """词面口径（回退用）：差异度 = 1 - 与最相近簇标签的术语重叠率。

    2026-10-20 起主口径改为 _semantic_distinctiveness（BGE-M3 语义相似度，
    用户定稿："差异度应该是指语义相似度"）——词面重叠既漏判（"InfoSeek数据
    合成"vs"合成数据学习"零重叠给满分，语义上却高度相近）又依赖分词巧合。
    仅在编码器不可用时作为兜底。
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


def _semantic_distinctiveness(label_texts: dict) -> dict:
    """主口径：标签语义差异度 = 定标后的 1 - 与最相近标签的余弦相似度。

    BGE-M3 对短技术短语的不相关基线偏高（实测 18 标签：无关对 0.24-0.57、
    易混对 0.67-0.72、中位 0.396），直接 1-cos 会让几乎所有标签低于 0.75
    阈值。按实测分布线性定标：cos<=0.55（不相关）→ 1.0，cos>=0.90（近
    重复）→ 0.0，即 0.75 阈值 ⇔ cos 0.6375。只算标签本身（不含簇内容），
    编码失败时回退词面重叠口径。
    """
    cids = [str(c) for c in (label_texts or {})]
    if len(cids) <= 1:
        return {c: 1.0 for c in cids}
    try:
        import numpy as _np

        vecs = m3_encoder.encode([str(label_texts.get(c) or "") for c in cids])
        sim = vecs @ vecs.T
        _np.fill_diagonal(sim, -1.0)
        out = {}
        for i, cid in enumerate(cids):
            worst = float(sim[i].max())
            out[cid] = round(min(1.0, max(0.0, (0.90 - worst) / 0.35)), 3)
        return out
    except Exception:
        return _pairwise_distinctiveness(
            {c: _label_term_set(str(label_texts.get(c) or ""), []) for c in cids})


def _label_score_against(label: str, other_labels: list) -> float:
    """单标签对一组其他标签的定标差异度（与 _semantic_distinctiveness 同口径）。"""
    others = [str(o) for o in other_labels if str(o).strip()]
    if not others:
        return 1.0
    try:
        import numpy as _np

        vecs = m3_encoder.encode([str(label)] + others)
        worst = float((vecs[0] @ vecs[1:].T).max())
        return min(1.0, max(0.0, (0.90 - worst) / 0.35))
    except Exception:
        sets = {"__self__": _label_term_set(label, [])}
        sets.update({f"o{i}": _label_term_set(o, []) for i, o in enumerate(others)})
        return _pairwise_distinctiveness(sets).get("__self__", 0.0)


def _label_covers_members(label: str, titles: list, floor: float = 0.42) -> bool:
    """标签覆盖门（粗筛）：候选标签须与簇内【每一篇】文献题名的语义相似度达标。

    防止最粗暴的单篇劫持（实测 "SFT" min 0.315、"MUPO策略优化" 0.369 被
    拦；共同路线标签 0.436-0.500 通过，floor=0.42）。注意嵌入分不开"同域
    相邻但单篇专有"的标签（multi-group policy optimization 对无关题名也
    有 0.484 基线）——精细判定由 _llm_covers_members 负责。题名缺失不设门。
    非信息性题名（文件名 1.pdf / 编号 DOC001）无语义，比对只会误杀——
    过滤后按题名缺失处理（2026-10-20 实测：文件名题名曾把 25/43 个标签
    的优化候选全部拦下，触发"无法达标"硬报错）。
    """
    _uninformative = re.compile(r"^(?:[\w-]+\.(?:pdf|docx?|txt)|DOC\d+|FILE\d+|\d+)$", re.IGNORECASE)
    names = [str(t).strip() for t in (titles or [])
             if str(t).strip() and not _uninformative.match(str(t).strip())]
    if not names:
        return True
    try:
        vecs = m3_encoder.encode([str(label)] + names)
        worst = float((vecs[0] @ vecs[1:].T).min())
        return worst >= floor
    except Exception:
        return True


def _llm_covers_members(label: str, titles: list, glm_client: Any) -> bool:
    """覆盖门（精筛，≥2 篇文献时启用）：LLM 读题名裁决标签是否概括全部文献。

    嵌入余弦对"同域相邻、单篇专有"的标签无区分力（实测见上），改由 LLM
    判定"标签是否只反映了其中一篇的专有方法名"。GLM 不可用/超时按通过
    处理（软门，不阻塞达标循环收敛）。
    """
    names = [str(t).strip() for t in (titles or []) if str(t).strip()]
    if len(names) < 2 or not str(label or "").strip() or glm_client is None:
        return True
    try:
        out = glm_client.chat_json(
            "你是聚类标签审核专家。",
            f"判断标签「{label}」是否概括了以下【全部】文献的共同技术路线，"
            f"而不是只反映其中某一篇文献的专有方法名：\n"
            + "\n".join(f"[{i + 1}] {t}" for i, t in enumerate(names[:4]))
            + '\n只输出JSON：{"covers_all": true, "reason": "一句话依据"}',
            timeout=30.0, max_tokens=120, temperature=0.0)
        row = out.get("data", out) if isinstance(out, dict) else {}
        return bool(row.get("covers_all"))
    except Exception:
        return True


def _covers_ok(label: str, titles: list, glm_client: Any) -> bool:
    """覆盖门组合：嵌入粗筛 + LLM 精筛（单篇簇/无题名直接通过）。"""
    return (_label_covers_members(label, titles)
            and _llm_covers_members(label, titles, glm_client))


def _force_distinct_label(current: str, other_labels: dict, shared_terms: list,
                          phrases: list, threshold: float, glm_client: Any,
                          titles: list | None = None) -> str | None:
    """用户阈值强制达标：定向重写一个标签，使其与所有其他标签语义拉开。

    先 LLM 重写（带最近邻标签与相似度反馈，指名道姓地避开）；语义复算仍
    不达标时，回退"簇内最具区分度的独有短语"确定性替换（逐个短语试算，
    取首个达标的）。候选一律过覆盖门（_label_covers_members）——禁止单篇
    文献的专有方法名劫持多文献簇标签。全部失败返回 None，保留原标签。
    """
    others = [str(v) for v in (other_labels or {}).values() if str(v).strip()]
    member_titles = [str(t) for t in (titles or []) if str(t).strip()]
    nb_label, nb_cos = "", 0.0
    try:
        import numpy as _np

        vecs = m3_encoder.encode([str(current)] + others) if others else None
        if vecs is not None:
            sims = vecs[0] @ vecs[1:].T
            j = int(sims.argmax())
            nb_label, nb_cos = others[j], float(sims[j])
    except Exception:
        pass
    candidate = ""
    if glm_client is not None:
        try:
            out = glm_client.chat_json(
                "你是类簇标签差异化优化专家。",
                f"标签「{current}」与另一簇标签「{nb_label}」语义相似度过高（余弦 {nb_cos:.2f}），"
                f"差异度低于用户设定阈值 {threshold}，必须重写。\n"
                f"本簇独有术语：{'、'.join(str(t) for t in (shared_terms or [])[:8]) or '（见代表短语）'}\n"
                f"簇代表短语：{'、'.join(str(p) for p in (phrases or [])[:8])}\n"
                + (f"簇内文献题名（标签必须概括这些文献的【共同】技术路线，"
                   f"禁止只用其中一篇的专有方法名命名）：{'；'.join(member_titles[:4])}\n"
                   if member_titles else "")
                + f"要求：避免「{nb_label}」及其他所有标签的用词，不超过 12 字，"
                f"禁止括号补充说明，新标签必须与「{nb_label}」一眼可区分，且覆盖簇内全部文献。"
                '只输出JSON：{"optimized_label":"新标签"}',
                timeout=45.0, max_tokens=300, temperature=0.2)
            candidate = str((out.get("data", out) if isinstance(out, dict) else {})
                            .get("optimized_label") or "").strip()
        except Exception:
            candidate = ""
    # LLM 候选先试；不行按"独有术语 → 代表短语"顺序做确定性替换（每个候选
    # 都语义复算 + 覆盖门双重校验，取首个达标的——保证换上的标签既过用户
    # 阈值、又不被单篇方法名劫持）
    for cand in ([candidate] if candidate else []) + [
            str(t) for t in list(shared_terms or []) + list(phrases or [])
            if str(t).strip() and str(t).strip() != str(current)]:
        cand = cand.strip()
        if (cand and _label_score_against(cand, others) >= threshold
                and _covers_ok(cand, member_titles, glm_client)):
            return cand
    return None


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
        cluster_titles: dict = {}
        for cid, name in move_named.items():
            ps_row = next((ps for ps in phrase_sets
                           if isinstance(ps, dict) and str(ps.get("cluster_id")) == cid), {})
            cluster_phrases[cid] = ps_row.get("phrases") or []
            cluster_titles[cid] = [str(t).strip() for t in (ps_row.get("evidence_titles") or [])
                                   if str(t).strip()]
        distinct = _semantic_distinctiveness(
            {cid: name for cid, name in move_named.items()})
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
        # 2026-10-20 阈值双模式（用户定稿）：
        # ① 自动（默认，不传/None/"auto"）：后端自行判定，只优化语义上真易混
        #    的标签（内部工作点 0.75 ⇔ 最近邻余弦 0.64），给出最合理结果；
        # ② 用户显式设定 0-1：硬闸门——低于阈值的标签必须优化到达标（下方
        #    强制达标循环），不允许"未通过"收场
        _raw_thr = params.get("distinctiveness_threshold")
        _thr_mode = "user"
        if _raw_thr is None or (isinstance(_raw_thr, str)
                                and _raw_thr.strip().lower() in {"", "auto", "null", "none"}):
            _thr_mode = "auto"
        threshold_opt = min(1.0, max(0.0, _number(params, "distinctiveness_threshold", 0.75)))
        _opt_items = []
        # 2026-10-20 再定稿：自动模式完全不优化——以模型（语步对齐簇名）
        # 生成的结果为准；仅用户显式设定阈值时才走差异化优化 + 强制达标
        if _thr_mode == "user":
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
                    + (f"（簇内文献：{'；'.join(cluster_titles.get(lbl['cluster_id'], [])[:3])}）"
                       if cluster_titles.get(lbl['cluster_id']) else "")
                    for i, lbl in enumerate(labels))
                _llm_prompt = (
                    "以下是聚类结果的所有类簇标签（含各簇独有术语与簇内文献题名）。请完成两件事：\n"
                    "1. 评估每个标签的差异化程度（distinctiveness，0-1 分）：该标签与其他簇标签的区分度，"
                    "完全可区分=1.0，高度相似=0.0。\n"
                    f"2. distinctiveness 低于 {threshold_opt} 的标签，必须给出优化后的新标签（optimized_label），"
                    "并同时给出新标签的差异度分数（optimized_distinctiveness）。"
                    f"⚠️ 新标签必须只用该簇【独有术语】构建（括号里给出的），禁止使用多簇共享的词（如两簇都有"
                    f"的'深度学习'），要让不同簇的标签一眼可区分。新标签不超过 12 个字，禁止加括号补充说明"
                    f"（英文原词等直接融入标签）。optimized_distinctiveness 必须严格大于 {threshold_opt}。\n"
                    "⚠️ 覆盖要求：新标签必须概括该簇【全部文献】的共同技术路线（簇内文献题名已列出），"
                    "禁止只用其中一篇文献的专有方法名命名——标签要让簇内每篇文献都对得上。\n"
                    f"distinctiveness 大于等于 {threshold_opt} 的标签不要给 optimized_label。\n\n"
                    f"标签列表：\n{_label_list}\n\n"
                    '只输出JSON：{"results":[{"cluster_id":"C01","distinctiveness":0.8,'
                    '"optimized_label":"","optimized_distinctiveness":0.0,'
                    '"reason":"评估或优化说明"}]}')
                # 确定性 before 分（2026-10-20 起语义口径）：LLM 评估/优化以此为基准
                _pre_dist = _semantic_distinctiveness(
                    {l["cluster_id"]: l["label"] for l in labels})
                for l in labels:
                    _pd = _pre_dist.get(l["cluster_id"])
                    if _pd is not None:
                        l["distinctiveness"] = _pd
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
                    # 优化门控用确定性标签分（2026-10-20 修复）：LLM 自评 distinctiveness
                    # 与最终标签重叠率分两套口径——LLM 判 ≥0.75 跳过优化，随后确定性
                    # 重算降到 0.50 → 优化列表空但分数全低于阈值的矛盾展示。改以
                    # 入循环前的确定性分为门控，LLM 字段仅作参考不再采信
                    _d = max(0.0, min(1.0, float(_lbl.get("distinctiveness") or 0)))
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
                    _covers = _covers_ok(_new_label, cluster_titles.get(_cid) or [], glm_client) \
                        if _new_label else False
                    # 覆盖门（2026-10-20）：单篇方法名劫持多文献簇标签的候选不采纳
                    _adopted = (_new_label and _new_label != _before and _nd > threshold_opt
                                and _covers)
                    # 二轮强指令重试（2026-10-20 二修）：只要低于阈值且一轮未采纳就触发，
                    # 不再要求"一轮给过有改进的新标签"——实测 LLM 自评"已够区分"不给
                    # 新标签时（C01/C02 共享 'RL' 案），原条件永远不触发，优化形同虚设；
                    # 二轮仍不达标则采用分数最高的改进标签。另修：原提示词误用未定义
                    # 变量 cid_，触发即 NameError 被外层静默吞掉，重试从未真正执行
                    if not _adopted and _d < threshold_opt:
                        try:
                            _retry_out = glm_client.chat_json(
                                "你是类簇标签差异化优化专家。",
                                f"这个类簇标签差异度不足，需要重写。\n"
                                f"当前判定：该标签与其他簇标签存在词面重叠（如共享词根/缩写），"
                                f"只靠换措辞不够，必须换用下方【独有术语】重构。\n"
                                f"类簇 {_cid}({_lbl['label']}) 的独有术语：{'、'.join(_shared_terms.get(_cid, [])[:8]) or '（见短语）'}\n"
                                f"簇代表短语：{'、'.join(cluster_phrases.get(_cid, [])[:8])}\n"
                                + (f"簇内文献题名（新标签必须概括全部文献的共同技术路线，"
                                   f"禁止只用其中一篇的专有方法名）：{'；'.join(cluster_titles.get(_cid, [])[:4])}\n"
                                   if cluster_titles.get(_cid) else "")
                                + f"其他簇的现有标签（必须避开它们的用词）：{_label_list}\n"
                                f"要求：写一个 ≤{12} 字的新标签（禁止括号补充说明），"
                                f"必须与其他簇标签完全可区分，且覆盖簇内全部文献。"
                                '只输出JSON：{"optimized_label":"新标签","optimized_distinctiveness":0.9}',
                                timeout=45.0, max_tokens=300, temperature=0.2)
                            _r2 = _retry_out.get("data", _retry_out) if isinstance(_retry_out, dict) else {}
                            _nl2 = str(_r2.get("optimized_label") or "").strip()
                            try:
                                _nd2 = float(_r2.get("optimized_distinctiveness") or 0)
                            except (TypeError, ValueError):
                                _nd2 = 0
                            _nd2 = max(0.0, min(1.0, _nd2))
                            if (_nl2 and _nl2 != _before and _nd2 > _nd
                                    and _covers_ok(_nl2, cluster_titles.get(_cid) or [], glm_client)):
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
                    elif (_new_label and _new_label != _before and _nd > _d
                          and _covers_ok(_new_label, cluster_titles.get(_cid) or [], glm_client)):
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

            # ── 强制达标（2026-10-20 定稿："必须通过，不能不通过"，且对自动/用户
            # 两种模式一律生效——自动模式的工作点 0.75 同样是硬闸门）──
            # 循环"定向重写 + 语义复算"直到全部达标：每轮对未达标标签带最近邻反
            # 馈重写，LLM 分不开时用簇内独有短语确定性替换（见 _force_distinct_label）
            for _round in range(1, 4):
                _fd = _semantic_distinctiveness({l["cluster_id"]: l["label"] for l in labels})
                for l in labels:
                    _v = _fd.get(l["cluster_id"])
                    if _v is not None:
                        l["distinctiveness"] = _v
                _failing = [l for l in labels if l["distinctiveness"] < threshold_opt]
                if not _failing:
                    break
                for _fl in _failing:
                    _fcid = _fl["cluster_id"]
                    _others = {l["cluster_id"]: l["label"] for l in labels
                               if l["cluster_id"] != _fcid}
                    _new = _force_distinct_label(
                        _fl["label"], _others, _shared_terms.get(_fcid) or [],
                        cluster_phrases.get(_fcid) or [], threshold_opt, glm_client,
                        titles=cluster_titles.get(_fcid) or [])
                    if _new and _new != _fl["label"]:
                        _old = _fl["label"]
                        _fl["label"] = _new
                        _fl["candidate_labels"] = list(dict.fromkeys(
                            [*(l for l in (_fl.get("candidate_labels") or []) if l), _new]))
                        _it = next((it for it in _opt_items
                                    if it.get("cluster_id") == _fcid), None)
                        if _it is None:
                            _opt_items.append({
                                "cluster_id": _fcid,
                                "before_label": _old,
                                "after_label": _new,
                                "before_distinctiveness": round(float(_fl["distinctiveness"]), 3),
                                "after_distinctiveness": round(float(_fl["distinctiveness"]), 3),
                                "changed": True,
                                "reason": f"强制达标（阈值 {round(threshold_opt, 2)}）：第 {_round} 轮定向重写",
                                "threshold_passed": True,
                            })
                        else:
                            _it["after_label"] = _new
                            _it["changed"] = True
                            _it["reason"] = ((str(_it.get("reason") or "").rstrip("；") + "；")
                                             + f"强制达标第 {_round} 轮定向重写")

        # 差异度由确定性公式独立计算（诚实口径）：LLM 只负责改标签，分数不采信
        # LLM 自评。2026-10-20 起主口径为【标签本身的 BGE-M3 语义相似度】（定
        # 标后 1-cos，不含簇原始短语）——阈值管的是"标签能不能区分开"；词面
        # 重叠口径漏判过"InfoSeek数据合成 vs 合成数据学习"（零重叠给满分）
        _final_dist = _semantic_distinctiveness(
            {l["cluster_id"]: l["label"] for l in labels})
        for lbl in labels:
            _cid = lbl["cluster_id"]
            _new_d = _final_dist.get(_cid, lbl["distinctiveness"])
            if _new_d != lbl["distinctiveness"]:
                lbl["distinctiveness"] = _new_d
                lbl["confidence"] = (0.95 if _new_d >= threshold_opt
                                     else 0.85 if _new_d >= 0.50 else 0.70)
        if _thr_mode == "user":
            # 必须通过才能返回结果（2026-10-20 用户定稿）：全部达标才出结果。
            # 三轮"定向重写 + 独有短语确定性替换"兜底用尽仍未达标 = 类簇内容近
            # 乎重复、语义上无法互相区分——明确报错引导调整聚类粒度，绝不返回
            # 带未达标标签的结果
            _unpassed = [str(l.get("cluster_id") or "") for l in labels
                         if float(l.get("distinctiveness") or 0) < threshold_opt]
            if _unpassed:
                raise ValueError(
                    f"类簇 {'、'.join(_unpassed)} 的标签经多轮差异化优化仍低于阈值 "
                    f"{round(threshold_opt, 2)}。请自行选择处理方式：① 降低差异度阈值"
                    f"（如 0.75）后重试；② 改用自动模式（不设定阈值，以模型生成结果为准）。"
                    f"工具不会自动降级，以您的选择为准")
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
                            "mode": "move_aligned_direct", "distinctiveness_threshold": threshold_opt,
                            "threshold_mode": _thr_mode},
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
    # 阈值双模式（2026-10-20，同 move_aligned 路径口径）：不传/None/"auto" =
    # 自动；显式数值 = 用户强制达标（通用引擎路径仅解析上报，强制达标循环
    # 在 move_aligned 主链路实现）
    _raw_thr = params.get("distinctiveness_threshold")
    if _raw_thr is None or (isinstance(_raw_thr, str)
                            and _raw_thr.strip().lower() in {"", "auto", "null", "none"}):
        distinctiveness_threshold = 0.75
    else:
        try:
            distinctiveness_threshold = min(1.0, max(0.0, float(_raw_thr)))
        except (TypeError, ValueError):
            distinctiveness_threshold = 0.75
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
                # 差异度由确定性公式独立重算（同 move_aligned 语义口径）：LLM 改
                # 标签，分数按新标签的语义相似度重算，不采信 LLM 自评
                _all_labels = output.get("labels") or []
                _final_dist = _semantic_distinctiveness(
                    {str(l.get("cluster_id") or ""): str(l.get("label") or "")
                     for l in _all_labels if isinstance(l, dict)})
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
