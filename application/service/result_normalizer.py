"""把现有 19 个算法的内部输出转换为 Vue 可视化需要的稳定结构。"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


def _list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _confidence(item: Dict[str, Any], default: Optional[float] = None) -> Optional[float]:
    value = item.get("confidence", item.get("score", item.get("weight")))
    if value in (None, ""):
        return default
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def normalize_result(tool_id: str, raw: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    if tool_id in {"zh-abstract-move", "en-abstract-move", "fund-move"}:
        return _moves(raw, tool_id, payload)
    if tool_id in {"zh-classify", "en-classify"}:
        result = _classification(raw, tool_id)
        # 用户题目优先于引擎原始数据(引擎可能带空 document_title,setdefault 会被挡住)
        if payload.get("document_title") or payload.get("title"):
            result["document_title"] = payload.get("document_title") or payload.get("title")
        result.setdefault("classification_confidence", _confidence(result.get("primary_classification") or {}, 0.0))
        if tool_id == "en-classify":
            if not result.get("literature_distribution_analysis_report"):
                report = _en_distribution_report(result)
                result["distribution_report"] = report
                result["literature_distribution_analysis_report"] = report
            if not result.get("cross_language_mapping"):
                result["cross_language_mapping"] = _en_cross_language_mapping(result, payload)
        return result
    if tool_id == "domain-classify":
        return _domain_classification(raw, payload)
    if tool_id in {"zh-keyword", "en-keyword"}:
        return _keywords(raw, payload)
    if tool_id == "rq-detect":
        return _research_questions(raw, payload)
    if tool_id in {"citation-sentiment", "citation-intent"}:
        return _citations(raw, tool_id, payload)
    if tool_id == "definition-detect":
        data = raw if isinstance(raw, dict) else {}
        defs = _list(data.get("definitions") if data else raw)
        mappings = _list(data.get("concept_definition_mappings") or data.get("mappings")) if data else []
        if not mappings:
            mappings = [{
                "concept": item.get("concept") or item.get("term") or "",
                "definition": item.get("definition") or item.get("definition_content") or item.get("sentence") or "",
            } for item in defs if isinstance(item, dict)]
        report = data.get("statistical_analysis_report") if isinstance(data.get("statistical_analysis_report"), dict) else {
            "definition_sentence_count": len(defs),
            "concept_count": len({item.get("concept") for item in mappings if isinstance(item, dict) and item.get("concept")}),
            "mapping_count": len(mappings),
            "section_distribution": [],
        }
        return {**data, "definitions": defs, "definition_results": defs,
                "mappings": mappings, "concept_definition_mappings": mappings,
                "statistics": report, "statistical_analysis_report": report,
                "document": {"title": payload.get("document_title") or payload.get("title") or ""},
                "input_type": payload.get("input_type")}
    if tool_id in {"general-ner", "research-ner", "domain-ner"}:
        return _entities(raw, payload)
    if tool_id == "relation-extract":
        data = raw if isinstance(raw, dict) else {}
        source = _list(data.get("triples", data.get("relations", [])) if data else raw)
        original_sentence = str(payload.get("text") or data.get("original_sentence") or "")
        # 句子切分 + 句号映射，用于为每条三元组分配 sentence_id 与上下文片段
        import re as _re
        sentences = [s.strip() for s in _re.split(r'(?<=[。！？!?])\s*|\n+', original_sentence) if s.strip()]

        def _sentence_id_of(text_a: str, text_b: str) -> str:
            for idx, sent in enumerate(sentences):
                if text_a and text_a in sent:
                    return f"SENT-{idx:03d}"
                if text_b and text_b in sent:
                    return f"SENT-{idx:03d}"
            return "SENT-000"

        triples = []
        for index, item in enumerate(source, 1):
            value = item if isinstance(item, dict) else {"relation": str(item)}
            head_text = value.get("subject") or value.get("source") or value.get("head")
            tail_text = value.get("object") or value.get("target") or value.get("tail")
            relation_str = value.get("relation")
            if isinstance(relation_str, dict):
                relation_str = relation_str.get("label") or relation_str.get("code")
            relation_str = relation_str or value.get("predicate") or value.get("type")
            triple_id = value.get("triple_id") or f"TRIPLE_{index:03d}"
            sentence_id = value.get("sentence_id") or _sentence_id_of(str(head_text or ""), str(tail_text or ""))
            # 上下文：优先用 LLM 给的 context，否则定位包含句
            context = value.get("context") or value.get("evidence") or value.get("sentence") or ""
            if not context:
                idx = int(sentence_id.split("-")[-1]) if sentence_id.startswith("SENT-") else 0
                if 0 <= idx < len(sentences):
                    context = sentences[idx]
                elif original_sentence:
                    context = original_sentence[:160]
            # 依存路径：优先用 LLM 给的，否则用触发词/关系词占位，确保非空（前端空时显示"未返回"）
            dep_path = value.get("dependency_path")
            if not dep_path:
                trigger = value.get("trigger") or (relation_str if isinstance(relation_str, str) else "")
                left = str(head_text or "")
                right = str(tail_text or "")
                dep_path = f"{left} ←[{trigger or '关系'}]→ {right}".strip()
            triples.append({
                **value,
                "triple_id": triple_id,
                "sentence_id": sentence_id,
                "subject": head_text,
                "relation": relation_str,
                "object": tail_text,
                "trigger": value.get("trigger") or (relation_str if isinstance(relation_str, str) else ""),
                "context": context,
                "dependency_path": dep_path,
                "confidence": _confidence(value),
            })
        dependency_parse = _list(data.get("dependency_parse") or data.get("dependencies"))
        # dependency_paths 兜底：从每条 triple 的 dependency_path 聚合
        dependency_paths = _list(data.get("dependency_paths"))
        if not dependency_paths:
            dependency_paths = [
                {"triple_id": t.get("triple_id"), "path": t.get("dependency_path")}
                for t in triples if t.get("dependency_path")
            ]
        # context_fragments 兜底：从每条 triple 的 sentence_id + context 聚合（按 sentence_id 去重）
        context_fragments = _list(data.get("context_fragments"))
        if not context_fragments:
            seen_sent = set()
            for t in triples:
                sid = t.get("sentence_id")
                if sid in seen_sent:
                    continue
                seen_sent.add(sid)
                context_fragments.append({"sentence_id": sid, "text": t.get("context") or ""})
        rdf = data.get("rdf_representation")
        if not rdf and triples:
            rdf = "\n".join(
                f'<urn:entity:{index}:subject> <urn:relation:{str(item.get("relation") or "related_to").replace(" ", "_")}> <urn:entity:{index}:object> .'
                for index, item in enumerate(triples, 1)
            )
        return {
            **data,
            "upstream_ner_record_id": payload.get("upstream_ner_record_id") or payload.get("upstream_entity_record_id"),
            "original_sentence": original_sentence,
            "dependency_parse_executed_internally": True,
            "dependency_parse": dependency_parse,
            "dependency_paths": dependency_paths,
            "source_records": data.get("source_records") or {
                "entity_record_id": payload.get("upstream_entity_record_id"),
                "dependency_record_id": payload.get("upstream_dependency_record_id"),
            },
            "triples": triples,
            "relation_triples": triples,
            "relation_results": triples,
            "relations": triples,
            "context_fragments": context_fragments,
            "rdf_representation": rdf or "",
            "statistics": data.get("statistics") or {"triple_count": len(triples)},
        }
    if tool_id == "deep-cluster":
        return _clusters(raw, payload)
    if tool_id == "cluster-label":
        return _labels(raw, payload)
    if tool_id == "structured-review":
        return _review(raw, payload)
    return raw if isinstance(raw, dict) else {"value": raw}


# 语步类别 → 规范化标签（中英文摘要语步识别的 GLM 输出是「类别→文本」扁平 dict，
# 不是 moves 列表；这里给出有序类别集合，供 _moves 把扁平 dict 还原成结构化 moves）。
_MOVE_CATEGORIES_ZH = ["研究背景", "研究目的", "研究方法", "研究结果", "研究结论"]


def _title_text(*values: Any) -> str:
    """取第一个非空字符串作标题;批量模式 document_title 是列表,不能平铺当标题。"""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _detect_language(text: Any) -> str:
    """按字符构成判断文本主语言：CJK 汉字与拉丁字母数量比较。

    摘要语步工具的中英文页面共用引擎，document.language 不能按工具页面写死，
    要按输入文本实际语言输出（英文摘要进中文页 → language=en）。
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    if cjk == 0 and latin == 0:
        return ""
    return "zh" if cjk >= latin else "en"
_MOVE_CATEGORIES_EN = ["Background", "Objective", "Methods", "Results", "Conclusion"]


def _move_char_range(abstract: str, text: str) -> tuple:
    """语步文本在摘要中的字符范围（与前端 charRange 同款两级匹配）。

    ① 精确 indexOf；② 去空白差异匹配（GLM 切分可能增减空格/换行）并映射回原始下标。
    语步句子在摘要中不相邻时（拼接文本非连续子串）返回 (None, None)，
    由 sentence_indices 承担定位。返回 (start, end)，end 为开区间。
    """
    idx = abstract.find(text)
    if idx >= 0:
        return idx, idx + len(text)
    norm_chars, map_to_original = [], []
    for i, ch in enumerate(abstract):
        if not ch.isspace() and ch != "　":
            norm_chars.append(ch)
            map_to_original.append(i)
    norm_abs = "".join(norm_chars)
    norm_text = "".join(ch for ch in text if not ch.isspace() and ch != "　")
    if not norm_text:
        return None, None
    n_start = norm_abs.find(norm_text)
    if n_start < 0:
        n_start = norm_abs.lower().find(norm_text.lower())
    if n_start < 0:
        return None, None
    start_idx = map_to_original[n_start]
    last_idx = map_to_original[min(n_start + len(norm_text) - 1, len(map_to_original) - 1)]
    return start_idx, (last_idx if last_idx is not None else start_idx) + 1


def _moves(raw: Any, tool_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    overall_confidence = data.get("confidence")
    move_confidence = data.pop("move_confidence", None) or {}
    source = _list(data.get("moves", data.get("spans", [])) if data else raw)
    moves = []
    # GLM 按规则库 output_schema 直接输出「类别→文本」扁平 dict（如 {研究方法: "..."}），
    # 既无 moves 也无 spans。此时按有序类别集合还原成结构化 moves，否则 moves 恒为空、
    # 前端与 move_segments 投影表都拿不到数据。
    if not source and isinstance(raw, dict):
        categories = _MOVE_CATEGORIES_EN if tool_id == "en-abstract-move" else _MOVE_CATEGORIES_ZH
        # 引擎输出的每语步句序号（语步句子在摘要中可能不相邻，拼接文本无法
        # indexOf 定位；句序号是非连续语步唯一忠实的定位方式）
        sent_idx_map = data.get("sentence_indices_by_move") if isinstance(data.get("sentence_indices_by_move"), dict) else {}
        # 摘要原文（优先 document.abstract，文件模式由 _result_payload 回填）
        abstract_text = ""
        document_data = data.get("document") if isinstance(data.get("document"), dict) else {}
        if document_data.get("abstract"):
            abstract_text = str(document_data["abstract"])
        elif isinstance(payload.get("text"), str):
            abstract_text = payload["text"]
        for label in categories:
            text = raw.get(label)
            has_text = text not in (None, "")
            start = end = None
            if has_text and abstract_text:
                start, end = _move_char_range(abstract_text, str(text))
            moves.append({
                "move_code": label,
                "move_name": label,
                "label": label,
                "text": text or "",
                "sentence_indices": sent_idx_map.get(label) or None,
                "start": start,
                "end": end,
                "confidence": move_confidence.get(label, overall_confidence) if has_text
                              else move_confidence.get(label, overall_confidence),
            })
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            item = {"text": str(item)}
        label = item.get("label") or item.get("move_name") or item.get("move_type") or item.get("move") or item.get("type")
        content = item.get("content") or item.get("text") or item.get("sentence") or ""
        moves.append({
            **item,
            "move_code": item.get("move_code") or label,
            "move_name": item.get("move_name") or label,
            "label": label,
            "text": content,
            "sentence_index": item.get("sentence_index"),
            "sentence_indices": item.get("sentence_indices") or item.get("position") or (
                {"start": item.get("start"), "end": item.get("end")}
                if item.get("start") is not None or item.get("end") is not None else None
            ),
            "source_sections": _list(item.get("source_sections") or item.get("source_section")),
            "confidence": _confidence(item, move_confidence.get(label, overall_confidence)),
        })
    statistics = data.get("move_statistics")
    data.pop("sentence_indices_by_move", None)  # 中间字段，不进公开响应
    if not statistics:
        # 5 类语步框架完整统计：空语步也以 0 出现，而非被丢弃
        _counter = Counter(item["label"] for item in moves if item.get("label") and item.get("text"))
        statistics = {}
        for item in moves:
            lbl = item.get("label")
            if lbl and lbl not in statistics:
                statistics[lbl] = _counter.get(lbl, 0)
    document = data.get("document") if isinstance(data.get("document"), dict) else {}
    document.setdefault("title", _title_text(payload.get("project_name"), payload.get("document_title"), payload.get("title")))
    # language 按输入文本实际语言判定（而非按工具页面写死）；引擎已显式给出时保留引擎值
    _detected_lang = _detect_language(document.get("abstract") or payload.get("text") or payload.get("project_document_text") or payload.get("abstract"))
    document.setdefault("language", _detected_lang or ("en" if tool_id == "en-abstract-move" else "zh"))
    # 摘要原文：引擎输出不回传输入文本，这里从请求 payload 补回，供前端可视化弹窗
    # 按字符范围定位每个语步（move.text 在 abstract 内 indexOf 算起止）。
    # 单篇 text / 基金项目 project_document_text；data.document.abstract 优先。
    if not document.get("abstract"):
        document["abstract"] = (payload.get("text") or payload.get("project_document_text")
                                or payload.get("abstract") or data.get("abstract") or "")
    result = {
        **data,
        "document": document,
        "moves": moves,
        "move_count": len(moves),
        "sentence_count": data.get("sentence_count") or len(moves),
        "input_type": payload.get("input_type"),
        "move_statistics": statistics,
        "move_confidence": move_confidence,
    }
    # 精简：删除顶层平铺的「类别→文本」字段（GLM 原始输出残留，与 moves 数组重复；
    # 前端专用渲染与 move_segments 投影均只读 moves 数组，不读顶层平铺）。
    for _cat in _MOVE_CATEGORIES_ZH + _MOVE_CATEGORIES_EN:
        result.pop(_cat, None)
    # 跨语言输入提示：中文页收到纯英文文本(或反向)时告知用户切换识别页
    if _detected_lang and tool_id in {"zh-abstract-move", "en-abstract-move"}:
        _expected_lang = "en" if tool_id == "en-abstract-move" else "zh"
        if _detected_lang != _expected_lang:
            _lang_name = "英文" if _detected_lang == "en" else "中文"
            _page_name = "英文摘要语步识别" if _detected_lang == "en" else "中文摘要语步识别"
            result["language_mismatch"] = f"检测到输入文本为{_lang_name}，请切换到{_page_name}功能页后重新识别"
    if tool_id == "fund-move":
        result.setdefault("writeback", {"status": "not_requested", "project_record_id": None, "performance_evaluation_task_id": None})
    return result


def _domain_classification(raw: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """专业领域分类：按 Vue 契约输出 document/selected_domain/domain_match_result/
    multilevel_classification_results/classification_confidence/domain_labels/
    candidate_classifications/manual_confirmation/data_distribution_report。"""
    data = raw if isinstance(raw, dict) else {}

    # 1. document — 从 payload 取真实输入
    document = {
        "document_id": None,
        "title": str(payload.get("title") or ""),
        "abstract": str(payload.get("abstract") or ""),
        "keywords": [str(k) for k in _list(payload.get("keywords")) if k],
        "language": None,
        "source_file": payload.get("file_name"),
    }

    # 2. selected_domain
    domain_code = str(data.get("domain_code") or "")
    domain_name = str(data.get("domain_name") or "")
    selected_domain = {"code": domain_code, "name": domain_name}

    # 3. domain_match_result — 根据分类号是否解析成功判定匹配
    clc = data.get("clc_classification") or {}
    clc_resolved = bool(clc.get("clc_code"))
    match_status = "matched" if clc_resolved else "mismatched"
    # 用主分类真实置信度（检索佐证度）作领域匹配分，不再写死 0.9；clc 未解析才给低分
    match_score = (clc.get("confidence") or 0.5) if clc_resolved else 0.3
    domain_match_result = {
        "selected_domain": selected_domain,
        "status": match_status,
        "match_score": match_score,
        "message": f"文献分类号{'已成功解析' if clc_resolved else '未能解析'}，与所选领域「{domain_name}」{'匹配' if clc_resolved else '可能不匹配'}",
        "evidence": document["keywords"][:5],
    }

    # 4. multilevel_classification_results — 从 clc_classification 拆层级
    multilevel = []
    if clc:
        pn = clc.get("path_names") or []
        pc = clc.get("path_codes") or []
        cpath = [f"{c} {n}" for c, n in zip(pc, pn)] if pc and pn else []
        l1 = cpath[0] if cpath else ""
        l2 = cpath[1] if len(cpath) > 1 else l1
        l3 = cpath[-1] if cpath else l1
        multilevel.append({
            "order": 1, "role": "main",
            "classification_code": clc.get("clc_code"),
            "level_1": l1, "level_2": l2, "level_3": l3,
            "classification_path": cpath,
            "confidence": clc.get("confidence", 0.0),
            "evidence": [],
        })

    # 5. classification_confidence
    overall = clc.get("confidence", 0.0) if clc else 0.0
    classification_confidence = {"overall": overall, "level_1": overall, "level_2": overall, "level_3": overall}

    # 6. domain_labels
    domain_labels = []
    if domain_name:
        domain_labels.append({"label": domain_name, "confidence": match_score})
    if clc.get("clc_name"):
        domain_labels.append({"label": clc["clc_name"], "confidence": overall})

    # 7. candidate_classifications — 首条为主分类（与"专业领域多层级分类结果"一致），
    #    其后追加检索候选（按 clc_code 去重，跳过与主分类重复者）。
    cands_raw = _list(data.get("rag_top_k_candidates"))[:5]
    candidate_classifications = []
    main_code = clc.get("clc_code") if clc else None
    _seen_codes = set()
    # 首选 = 主分类路径（与上方多层级分类结果表第一行一致）
    if clc and main_code:
        m = multilevel[0] if multilevel else {}
        candidate_classifications.append({
            "candidate_id": "cand_main",
            "rank": 1,
            "role": "main",
            "classification_code": main_code,
            "level_1": m.get("level_1", ""),
            "level_2": m.get("level_2", ""),
            "level_3": m.get("level_3", ""),
            "classification_path": m.get("classification_path", []),
            "confidence": clc.get("confidence", 0.0),
            "evidence": [],
        })
        _seen_codes.add(main_code)
    for i, cand in enumerate(cands_raw):
        code = cand.get("clc_code")
        if not code or code in _seen_codes:
            continue
        score = cand.get("score")
        try:
            score = float(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        # 候选规则：置信度 ≥0.8 且严格低于主分类置信度（候选须比主结果小；低于0.8不进候选区）
        if score is None or score < 0.8:
            continue
        if overall and score >= overall:
            continue
        _seen_codes.add(code)
        cpn = cand.get("path_names") or []
        cpc = cand.get("path_codes") or []
        cpath = [f"{c} {n}" for c, n in zip(cpc, cpn)] if cpc and cpn else []
        candidate_classifications.append({
            "candidate_id": f"cand_{i + 1}",
            "rank": cand.get("rank", len(candidate_classifications) + 1),
            "role": "main",
            "classification_code": code,
            "level_1": cpath[0] if cpath else "",
            "level_2": cpath[1] if len(cpath) > 1 else (cpath[0] if cpath else ""),
            "level_3": cpath[-1] if cpath else "",
            "classification_path": cpath,
            "confidence": round(score, 2),
            "evidence": [],
        })

    # 8. manual_confirmation
    manual_confirmation = {
        "status": "pending",
        "confirmed_candidate_id": None,
        "confirmed_path": None,
        "candidate_count": len(candidate_classifications),
        "confirmed_by": None,
        "confirmed_at": None,
    }

    # 9. data_distribution_report（单篇也返回统一结构）
    l2_label = multilevel[0]["level_2"] if multilevel else ""
    l3_label = multilevel[0]["level_3"] if multilevel else ""
    data_distribution_report = {
        "document_count": 1,
        "classified_document_count": 1 if multilevel else 0,
        "classification_assignment_count": len(multilevel),
        "by_level_2": [{"category": l2_label, "assignment_count": 1, "document_count": 1, "percentage": 100.0}] if l2_label else [],
        "by_level_3": [{"category": l3_label, "assignment_count": 1, "document_count": 1, "percentage": 100.0}] if l3_label else [],
    }

    return {
        **data,
        "document": document,
        "selected_domain": selected_domain,
        "professional_domain": domain_name or selected_domain.get("name") or "",
        "domain_match_result": domain_match_result,
        "multilevel_classification_results": multilevel,
        "classification_confidence": classification_confidence,
        "domain_labels": domain_labels,
        "candidate_classifications": candidate_classifications,
        "manual_confirmation": manual_confirmation,
        "data_distribution_report": data_distribution_report,
        "taxonomy_version": data.get("taxonomy_version"),
        # 向后兼容旧字段
        "classifications": multilevel,
        "candidates": candidate_classifications,
        "levels": multilevel,
        "primary_classification": multilevel[0] if multilevel else None,
        "confirmation_status": "pending",
    }


def _derive_application_domain(primary: Any) -> List[Dict[str, Any]]:
    """从主分类派生"应用场景领域"标签。

    ac_zh 核心规则：主分类 = 应用场景。故应用场景领域取主分类的大类名——
    T 工业技术是人为聚合大类，其下二级类（TM 电工 / TP 自动化计算机 / TQ 化工…）
    才是学科边界，故 T 下取 path_names[1]；其余大类取 path_names[0]（一级类名）。
    与 _is_cross_discipline 的学科边界判定保持一致。
    """
    src = primary if isinstance(primary, dict) else {}
    if not src:
        return []
    code = str(src.get("clc_code") or src.get("code") or "")
    path_names = _list(src.get("path_names"))
    if code.startswith("T") and len(path_names) >= 2:
        label = str(path_names[1]).strip()
    elif path_names:
        label = str(path_names[0]).strip()
    else:
        # 兜底：从 classification_path 字符串取首段
        full = str(src.get("classification_path") or "")
        label = full.split(">")[0].strip() if full else ""
    label = label or str(src.get("clc_name") or src.get("label") or "").strip()
    if not label:
        return []
    return [{"label": label, "confidence": _confidence(src)}]


def _avg(values: List[Any]) -> Optional[float]:
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 4)


def _en_distribution_report(result: Dict[str, Any]) -> Dict[str, Any]:
    """en-classify 文献分布分析报告：从归一化后的 classifications + domain_labels 汇总。

    镜像前端 renderClassification 的 fallback 逻辑（visualizationRenderers.js:213-244），
    让契约字段 literature_distribution_analysis_report 被真实数据填充而非恒空。
    en-classify 为单篇输入，document_count=1。
    """
    items = _list(result.get("classifications"))
    domains = _list(result.get("domain_labels"))

    cat_map: Dict[str, Dict[str, Any]] = {}
    for item in items:
        code = str(item.get("clc_code") or item.get("code") or "").strip()
        if not code:
            continue
        entry = cat_map.setdefault(code, {
            "clc_code": code,
            "category_name": str(item.get("clc_name") or item.get("label") or "").strip(),
            "classification_path": _list(item.get("classification_path")) or _list(item.get("path_names")),
            "document_count": 0,
            "confidences": [],
        })
        entry["document_count"] += 1
        conf = _confidence(item)
        if conf is not None:
            entry["confidences"].append(conf)
    by_clc_category = []
    for entry in cat_map.values():
        confs = entry.pop("confidences")
        entry["document_ratio"] = round(entry["document_count"] / max(len(items), 1), 4)
        entry["document_percentage"] = round(entry["document_ratio"] * 100, 1)
        entry["average_confidence"] = _avg(confs)
        by_clc_category.append(entry)

    dom_map: Dict[str, Dict[str, Any]] = {}
    for dom in domains:
        name = str(dom.get("label") or dom.get("name") or "").strip() if isinstance(dom, dict) else str(dom or "").strip()
        if not name:
            continue
        entry = dom_map.setdefault(name, {"label": name, "document_count": 0, "confidences": []})
        entry["document_count"] += 1
        if isinstance(dom, dict):
            conf = _confidence(dom)
            if conf is not None:
                entry["confidences"].append(conf)
    by_domain_label = []
    for entry in dom_map.values():
        confs = entry.pop("confidences")
        entry["document_percentage"] = round(entry["document_count"] / max(len(domains), 1) * 100, 1)
        entry["average_confidence"] = _avg(confs)
        by_domain_label.append(entry)

    return {
        "document_count": 1,
        "classified_document_count": 1 if items else 0,
        "clc_category_count": len(by_clc_category),
        "domain_label_count": len(by_domain_label),
        "by_clc_category": by_clc_category,
        "by_domain_label": by_domain_label,
        "domain_label_scope": "primary_only",
    }


def _en_cross_language_mapping(result: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """en-classify 跨语言映射：英文文献必然经 英文→中文CLC 跨语言检索，分类成功即"已映射"。

    前端 enMappingCell 只读 status 与 source_terms[].label（visualizationRenderers.js:158）。
    source_terms 取 document_title，回退到英文正文前若干实词。
    """
    primary = result.get("primary_classification") or {}
    title = str(payload.get("document_title") or payload.get("title") or "").strip()
    source_terms = []
    if title:
        source_terms.append({"label": title})
    else:
        en_text = str(payload.get("english_scientific_document_text") or "").strip()
        if en_text:
            # 取前若干英文实词作为映射源术语
            words = [w for w in en_text.split() if any(c.isalpha() for c in w)][:8]
            if words:
                source_terms.append({"label": " ".join(words)})
    return {
        "status": "已映射",
        "source_language": "en",
        "target_language": "zh",
        "source_terms": source_terms,
        "target_classification": {
            "clc_code": str(primary.get("clc_code") or primary.get("code") or "").strip(),
            "clc_name": str(primary.get("clc_name") or primary.get("label") or "").strip(),
        },
    }


def _classification(raw: Any, tool_id: str) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    items = []
    if tool_id == "domain-classify":
        main = data.get("clc_classification")
        if main:
            items.append({**main, "role": "primary", "clc_code": main.get("clc_code") or main.get("code"), "label": main.get("clc_name") or main.get("label"), "confidence": main.get("score", main.get("confidence"))})
        domain_name = data.get("domain_name")
        domains = [{"code": data.get("domain_code"), "label": domain_name}] if domain_name else []
    else:
        main = data.get("main_classification")
        if main:
            items.append({**main, "role": "primary", "clc_code": main.get("clc_code") or main.get("code"), "label": main.get("clc_name") or main.get("label"), "confidence": main.get("score", main.get("confidence"))})
        for aux in _list(data.get("auxiliary_classifications")):
            items.append({**aux, "role": "secondary", "clc_code": aux.get("clc_code") or aux.get("code"), "label": aux.get("clc_name") or aux.get("label"), "confidence": aux.get("score", aux.get("confidence"))})
        domains = _list(data.get("domain_labels"))
    candidates_raw = _list(data.get("rag_top_k_candidates"))[:5]
    primary = items[0] if items else None
    # 应用场景领域：主分类=应用场景，从主分类大类派生（ac_zh/en-classify 后端不产出 domain_labels）
    if not domains and primary:
        domains = _derive_application_domain(primary)

    # 候选分类（供前端"候选分类与人工确认"下拉框）：以 (主,次) 组合为单元。
    # 后端 _execute_classification 产出 candidate_combinations（1-3 组）；旧结果无此字段时
    # 从 main_classification + auxiliary_classifications 合成 1 组，保证下拉框永不空。
    combos = _list(data.get("candidate_combinations"))
    if not combos:
        combos = [{
            "rank": 1,
            "main_classification": data.get("main_classification"),
            "auxiliary_classifications": _list(data.get("auxiliary_classifications")),
            "is_interdisciplinary": bool(data.get("is_interdisciplinary", False)),
            "confidence": _confidence(primary) if primary else None,
            "reason": data.get("selection_reason", ""),
        }]

    def _path_of(obj: Any) -> List[str]:
        """从分类对象构建 "code name" 路径列表。"""
        src = obj if isinstance(obj, dict) else {}
        cpc = _list(src.get("path_codes"))
        cpn = _list(src.get("path_names"))
        if cpc and cpn:
            return [f"{c} {n}" for c, n in zip(cpc, cpn)]
        return _list(src.get("classification_path"))

    def _code_of(obj: Any) -> str:
        src = obj if isinstance(obj, dict) else {}
        return str(src.get("clc_code") or src.get("code") or "").strip()

    def _name_of(obj: Any) -> str:
        src = obj if isinstance(obj, dict) else {}
        return str(src.get("clc_name") or src.get("label") or "").strip()

    candidate_classifications = []
    # 主结果置信度：rank==1 的首选组合；候选须严格低于此值且 >0.6 才进下拉框
    _primary_conf = None
    for _c in combos:
        if isinstance(_c, dict) and _c.get("rank") == 1:
            _primary_conf = _confidence(_c)
            if _primary_conf is None:
                _primary_conf = _confidence(_c.get("main_classification"))
            break
    _seen_combos = set()
    for combo in combos:
        main_obj = combo.get("main_classification") if isinstance(combo, dict) else None
        if not main_obj:
            continue
        m_code = _code_of(main_obj)
        if not m_code:
            continue
        aux_list = _list(combo.get("auxiliary_classifications")) if isinstance(combo, dict) else []
        aux_obj = aux_list[0] if aux_list else None
        a_code = _code_of(aux_obj) if aux_obj else ""

        # 复合去重键：主+次组合
        combo_key = f"{m_code}+{a_code}" if a_code else m_code
        if combo_key in _seen_combos:
            continue
        _seen_combos.add(combo_key)

        # 候选规则：非首选候选须置信度 ≥0.8 且严格低于主结果置信度；首选(rank==1)作为主结果始终保留（低于0.8不进候选区）
        combo_conf = _confidence(combo) if _confidence(combo) is not None else _confidence(main_obj)
        if combo.get("rank") not in (None, 1):
            if combo_conf is None or combo_conf < 0.8:
                continue
            if _primary_conf is not None and combo_conf >= _primary_conf:
                continue

        m_path = _path_of(main_obj)
        a_path = _path_of(aux_obj) if aux_obj else []
        m_path_str = " > ".join(m_path) if m_path else f"{m_code} {_name_of(main_obj)}".strip()
        a_path_str = " > ".join(a_path) if a_path else (f"{a_code} {_name_of(aux_obj)}".strip() if a_code else "")
        if a_code:
            # 下拉框只显示"类号+名称"（完整路径在上方明细表展示）
            label = f"主：{m_code} {_name_of(main_obj)} ／ 次：{a_code} {_name_of(aux_obj)}"
            class_path = [f"主：{m_path_str}", f"次：{a_path_str}"]
            combined_code = f"{m_code}+{a_code}"
        else:
            label = f"主：{m_code} {_name_of(main_obj)}"
            class_path = m_path if m_path else [m_code]
            combined_code = m_code

        rank = combo.get("rank") if isinstance(combo, dict) else None
        candidate_classifications.append({
            "candidate_id": f"combo_{rank}",
            "rank": rank,
            "role": "combination",
            "classification_code": combined_code,
            "main_code": m_code,
            "main_name": _name_of(main_obj),
            "main_path": m_path,
            "aux_code": a_code or None,
            "aux_name": _name_of(aux_obj) if aux_obj else None,
            "aux_path": a_path or None,
            "level_1": m_path[0] if m_path else "",
            "level_2": m_path[1] if len(m_path) > 1 else (m_path[0] if m_path else ""),
            "level_3": m_path[-1] if m_path else "",
            "classification_path": class_path,
            "label": label,
            "confidence": _confidence(combo) if _confidence(combo) is not None else _confidence(main_obj),
            "is_interdisciplinary": bool(combo.get("is_interdisciplinary")) if isinstance(combo, dict) else False,
            "evidence": [{"reason": combo.get("reason", "")}] if isinstance(combo, dict) else [],
        })

    # 检索候选补充：把检索 top-K 候选作为"仅主分类"候选单元加入下拉框（去重 + 置信度阈值过滤）。
    # 检索候选是知识库真实类号、有检索依据；按检索相似度 score 过滤，低于阈值的不进下拉框。
    _seen_mains = {c.get("main_code") for c in candidate_classifications if c.get("main_code")}
    for cand in candidates_raw:
        score = _confidence(cand)  # 检索候选的 score 字段
        # 候选规则：置信度 ≥0.8 且严格低于主结果置信度（候选须比主结果小；低于0.8不进候选区）
        if score is None or score < 0.8:
            continue
        if _primary_conf is not None and score >= _primary_conf:
            continue
        code = _code_of(cand)
        if not code or code in _seen_mains:
            continue
        _seen_mains.add(code)
        cpath = _path_of(cand)
        rank = cand.get("rank")
        candidate_classifications.append({
            "candidate_id": f"rag_{rank}" if rank else f"rag_{len(candidate_classifications) + 1}",
            "rank": None,
            "role": "retrieval",
            "classification_code": code,
            "main_code": code,
            "main_name": _name_of(cand),
            "main_path": cpath,
            "aux_code": None,
            "aux_name": None,
            "aux_path": None,
            "level_1": cpath[0] if cpath else "",
            "level_2": cpath[1] if len(cpath) > 1 else (cpath[0] if cpath else ""),
            "level_3": cpath[-1] if cpath else "",
            "classification_path": cpath if cpath else [code],
            "label": f"主：{code} {_name_of(cand)}",
            "confidence": score,
            "is_interdisciplinary": False,
            "evidence": [{"reason": "语义检索候选（CLC 知识库）"}],
        })

    manual_confirmation = {
        "status": "pending",
        "confirmed_candidate_id": None,
        "confirmed_path": None,
        "candidate_count": len(candidate_classifications),
        "confirmed_by": None,
        "confirmed_at": None,
    }
    result = {
        **data,
        "classifications": items,
        "primary_classification": primary,
        "candidates": candidates_raw,
        "candidate_classifications": candidate_classifications,
        "manual_confirmation": manual_confirmation,
        "domain_labels": domains,
        "confirmation_status": "pending" if items else "not_applicable",
    }
    if tool_id == "domain-classify":
        result.setdefault("selected_domain", {
            "code": data.get("domain_code"),
            "name": data.get("domain_name"),
        })
        result.setdefault("levels", items)
    return result


def _keywords(raw: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    source = _list(data.get("keywords", data.get("keyword_results", [])) if data else raw)
    items = []
    for index, item in enumerate(source):
        value = item if isinstance(item, dict) else {"keyword": str(item)}
        term = value.get("keyword") or value.get("term") or ""
        items.append({
            **value,
            "keyword": term,
            "term": term,
            "normalized_term": value.get("normalized_term") or term,
            "score": _confidence(value),
            "confidence": _confidence(value),
            "rank": value.get("rank", index + 1),
            "terminology_source": value.get("terminology_source") or value.get("source"),
        })
    is_english = any(item.get("term") for item in items) or payload.get("english_scientific_abstract") is not None
    document = data.get("document") if isinstance(data.get("document"), dict) else {}
    document.setdefault("title", payload.get("document_title") or payload.get("title") or "")
    document.setdefault("language", "en" if is_english else "zh")
    result = {
        **data,
        "document": document,
        "input_type": payload.get("input_type"),
        "keywords": items,
        "keywords_or_topic_phrases": items,
        "statistics": data.get("statistics") or {"keyword_count": len(items)},
        "dictionary_usage": data.get("dictionary_usage"),
    }
    result["keyword_count"] = len(items)
    result["term_count"] = len(items)
    return result


def _research_questions(raw: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    if data and any(key in data for key in ("research_question_sentences", "research_question_phrases", "structured_research_questions")):
        statistics = data.get("research_question_statistics") or data.get("statistics") or {}
        return {
            **data,
            "document": data.get("document") or {"title": payload.get("document_title") or payload.get("title") or ""},
            "input_type": payload.get("input_type"),
            "research_question_sentences": _list(data.get("research_question_sentences")),
            "research_question_phrases": _list(data.get("research_question_phrases")),
            "structured_research_questions": _list(data.get("structured_research_questions")),
            "statistics": statistics,
            "research_question_statistics": statistics,
        }
    items = _list(raw)
    sentences, phrases, structured = [], [], []
    expr_counts = {"explicit": 0, "implicit": 0}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        sentence = item.get("sentence", "")
        phrase = item.get("phrase", "")
        expr_raw = str(item.get("expression_type") or "").strip().lower()
        expression_type = "explicit" if expr_raw.startswith("exp") else ("implicit" if expr_raw.startswith("imp") else "")
        if expression_type:
            expr_counts[expression_type] += 1
        sentence_id = item.get("id") or f"RQS{index + 1}"
        sentences.append({**item, "expression_type": expression_type, "id": sentence_id, "text": sentence, "confidence": _confidence(item)})
        # 规范化问题：优先 normalized_question，回退 implication/phrase/sentence
        norm_q = item.get("normalized_question") or item.get("implication") or phrase or sentence
        if phrase:
            phrases.append({
                "id": f"RQP{index + 1}",
                "text": phrase,
                "sentence_id": sentence_id,                       # 来源句（指向 RQS{index+1}）
                "source_sentence_index": index,
                "normalized_question": norm_q,                      # 规范化问题
                "confidence": _confidence(item),
            })
        # 研究对象/约束条件：LLM 产出（可能为空）；主次层级：LLM 给 role，无则首句兜底 main、其余 sub 属 RQ1
        role = item.get("role") or ""
        if not role:
            role = "main" if index == 0 else "sub"
        parent_idx = item.get("parent_index")
        if role == "sub" and parent_idx is None:
            parent_idx = 0
        parent_id = ""
        if role == "sub":
            try:
                parent_id = f"RQ{(int(parent_idx) if parent_idx is not None else 0) + 1}"
            except (TypeError, ValueError):
                parent_id = "RQ1"
        structured.append({
            "research_question_id": f"RQ{index + 1}",
            "question": norm_q,
            "normalized_question": norm_q,
            "question_type": item.get("question_type") or "未分类",
            "research_object": item.get("research_object") or "",
            "constraints": item.get("constraints") or [],
            "role": role,
            "parent_id": parent_id,
            "confidence": _confidence(item),
        })
    total = max(len(sentences), 1)
    expression_types = [
        {"type": "显式（explicit）", "count": expr_counts["explicit"], "ratio": round(expr_counts["explicit"] / total, 3)},
        {"type": "隐式（implicit）", "count": expr_counts["implicit"], "ratio": round(expr_counts["implicit"] / total, 3)},
    ]
    statistics = {"sentence_count": len(sentences), "phrase_count": len(phrases), "expression_types": expression_types}
    return {
        "document": {"title": payload.get("document_title") or payload.get("title") or ""},
        "input_type": payload.get("input_type"),
        "research_question_sentences": sentences,
        "research_question_phrases": phrases,
        "structured_research_questions": structured,
        "statistics": statistics,
        "research_question_statistics": statistics,
    }


def _citations(raw: Any, tool_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    result_key = "citation_sentiment_results" if tool_id == "citation-sentiment" else "citation_intent_results"
    items = _list(data.get(result_key, data.get("citations", [])) if data else raw)
    normalized = []
    label_key = "sentiment" if tool_id == "citation-sentiment" else "intent"
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        normalized.append({
            **item,
            "citation_id": item.get("citation_id"),
            "citation_sentence": item.get("citation_sentence") or item.get("sentence", ""),
            "citation_markers": _list(item.get("citation_markers") or item.get("citation_marker")),
            "context": item.get("context") or {
                "before": item.get("context_before", ""),
                "current_sentence": item.get("citation_sentence") or item.get("sentence", ""),
                "after": item.get("context_after", ""),
            },
            "confidence": _confidence(item),
        })
    statistics = data.get(f"{result_key.removesuffix('_results')}_statistics") or data.get("statistics") or dict(Counter(item.get(label_key) for item in normalized if item.get(label_key)))
    return {
        **data,
        "document": data.get("document") or {"title": payload.get("document_title") or payload.get("title") or ""},
        "input_type": payload.get("input_type"),
        "citations": normalized,
        result_key: normalized,
        "statistics": statistics,
        ("citation_sentiment_statistics" if tool_id == "citation-sentiment" else "citation_intent_statistics"): statistics,
    }


def _entities(raw: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    source = _list(data.get("entities", data.get("entity_results", [])) if data else raw)
    items = []
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            continue
        entity_type = item.get("type") or item.get("entity_type") or item.get("label")
        confidence = _confidence(item)
        items.append({
            **item,
            "entity_id": item.get("entity_id"),
            "text": item.get("text") or item.get("entity") or item.get("name") or "",
            "type": entity_type,
            "confidence": confidence,
        })
    statistics = data.get("summary") or data.get("statistics") or {
        "entity_count": len(items),
        "by_type": dict(Counter(item.get("type") for item in items if item.get("type"))),
    }
    result = {
        **data,
        "document": data.get("document") or {"title": payload.get("document_title") or payload.get("title") or ""},
        "input_type": payload.get("input_type"),
        "entities": items,
        "entity_results": items,
        "mappings": items,
        "entity_mappings": items,
        "standard_term_mappings": items,
        "ontology_mappings": items,
        "statistics": statistics,
        "summary": statistics,
    }
    if payload.get("domain") is not None:
        result.setdefault("selected_domain", {
            "code": payload.get("domain"),
            "name": payload.get("domain"),
        })
    if payload.get("ontology_version_id") is not None:
        result.setdefault("ontology_version", payload.get("ontology_version_id"))
    result.setdefault("standard_term_mappings", data.get("standard_term_mappings") or items)
    result.setdefault("ontology_mappings", data.get("ontology_mappings") or items)
    return result


_CLUSTER_TERM_LEADS = (
    "该", "但", "可以", "能够", "通过", "使用", "采用", "基于", "为了", "由于",
    "因此", "本文", "本研", "研究", "提出", "实现", "结果", "实验", "表明", "说明",
    "针对", "利用", "借助", "根据", "结合", "随着", "目前", "近年", "进行", "具有",
    "属于", "得到", "发现", "验证", "测试", "如图", "如表", "公式", "式中", "其中",
    "从图", "由图", "从而", "进而", "以及", "并且", "或者", "虽然", "尽管", "值得",
    "需要",
    # 列举/分组句首（"第一组为大震级"类残句）
    "第一", "第二", "第三", "第四", "第五", "第六",
    "第一组", "第二组", "第三组", "组为", "分别为", "包括", "包含", "组成", "构成",
    "分为", "选取", "选择", "采用",
)


def _clean_cluster_term(term: Any) -> str:
    """清洗聚类代表短语：去前后标点、去尾缀虚词、过滤句子片段。

    聚类算法（dual_axis_cluster._terms_from_text）用正则抓连续中文块（2-18 字）
    不分词，会混入句子片段（"该方法可以有效挖"/"但训练过程不稳定"）与带标点词
    （"]混凝土"）。在归一化层统一清洗，保证簇代表短语是干净术语。
    """
    import re as _re
    t = str(term).strip()
    # 去前后标点 / 分隔符（]混凝土 的 ] 前缀等）
    t = _re.sub(r"^[^\w一-鿿]+|[^\w一-鿿]+$", "", t)
    if len(t) < 2:
        return ""
    # 去尾缀虚词
    t = _re.sub(r"(?:的|了|和|与|及|或|等|之|其|此|该|这|那)$", "", t)
    if len(t) < 2:
        return ""
    # 过滤句子片段：以句首/连接词开头的多为残句而非术语
    if any(t.startswith(w) for w in _CLUSTER_TERM_LEADS):
        return ""
    return t


def _clusters(raw: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """深度聚类 → Vue 渲染契约（renderDeepCluster）。

    后端 _execute_clustering 产出 documents[{document_id,title,technical,application}]、
    technical_topics/application_topics[{topic_id,topic_name,doc_indices}]、n。
    renderDeepCluster 期望 clusters[{cluster_id,size,ratio,representative_terms,
    representative_documents}]、input_summary、cluster_dimension_name、document_assignments、
    clustering_quality。这里从真实输出组装，无法计算的（2D投影/轮廓系数/年度趋势）留空，
    由前端友好降级。
    """
    data = raw if isinstance(raw, dict) else {}
    dimension = payload.get("cluster_dimension") or payload.get("cluster_axis") or "technology"
    axis = "application" if dimension in ("application", "application_scenario") else "technical"
    documents = _list(data.get("documents") or payload.get("documents") or payload.get("texts"))
    n = data.get("n") or len(documents)
    source = _list(data.get(f"{axis}_topics")) or _list(data.get("technical_topics")) \
        or _list(data.get("application_topics")) or _list(data.get("clusters"))
    clusters = []
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            continue
        cid = item.get("cluster_id") or item.get("topic_id") or f"C{index + 1}"
        doc_indices = _list(item.get("doc_indices"))
        members = _list(item.get("members"))
        if not members and doc_indices:
            members = [
                {
                    "document_id": documents[pos].get("document_id") or documents[pos].get("id") or f"D{pos + 1:02d}",
                    "title": documents[pos].get("title", ""),
                }
                for pos in doc_indices
                if isinstance(pos, int) and 0 <= pos < len(documents) and isinstance(documents[pos], dict)
            ]
        rep_terms = list(dict.fromkeys(
            t for t in (_clean_cluster_term(x) for x in _list(item.get("representative_terms") or item.get("keywords")))
            if t
        ))
        topic_name = item.get("topic_name") or item.get("topic_name_zh") or ""
        if not rep_terms and topic_name:
            rep_terms = [topic_name]
        size = item.get("size") or item.get("document_count") or len(doc_indices) or len(members)
        # 簇内文档在选定轴的匹配分（用于质量指标派生）
        in_scores = []
        for pos in doc_indices:
            if isinstance(pos, int) and 0 <= pos < len(documents) and isinstance(documents[pos], dict):
                s = (documents[pos].get(axis) or {}).get("score")
                if isinstance(s, (int, float)):
                    in_scores.append(float(s))
        clusters.append({
            **item,
            "cluster_id": cid,
            "topic_id": cid,
            "topic_name": topic_name,
            "size": size,
            "ratio": round(size / n, 3) if n else 0,
            "representative_terms": rep_terms,
            "representative_documents": members[:3],
            "members": members,
            "_in_scores": in_scores,
        })
    # 派生类簇质量指标（基于主题匹配分；双轴主题路径非向量聚类，故无轮廓系数）
    def _jaccard(a, b):
        sa, sb = set(a), set(b)
        return len(sa & sb) / len(sa | sb) if sa and sb else 0.0
    all_rep = [c.get("representative_terms") or [] for c in clusters]
    for i, c in enumerate(clusters):
        scores = c.pop("_in_scores", [])
        intra = (sum(scores) / len(scores)) / 0.6 if scores else 0.0
        intra = min(1.0, max(0.0, intra))
        inter = 1.0 - max((_jaccard(all_rep[i], all_rep[j]) for j in range(len(clusters)) if j != i), default=0.0)
        density = 1.0 - min(1.0, (max(scores) - min(scores)) / 0.6) if len(scores) >= 2 else intra
        c["feature_statistics"] = {
            "intra_cluster_similarity": round(intra, 3),
            "inter_cluster_separation": round(inter, 3),
            "semantic_density": round(density, 3),
        }
    # 文献归属：每篇文献 → 其所选轴的类簇
    assignments = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        axis_info = doc.get(axis) or {}
        assignments.append({
            "document_id": doc.get("document_id") or doc.get("id") or "",
            "title": doc.get("title", ""),
            "publication_year": doc.get("publication_year") or doc.get("year"),
            "publication_date": doc.get("published_at") or doc.get("publication_date"),
            "cluster_id": axis_info.get("topic_id", ""),
            "similarity_to_centroid": axis_info.get("score"),
            "key_evidence": axis_info.get("key_evidence") or axis_info.get("topic_name", ""),
            "input_representation": doc.get("input_representation") or {},
        })
    dimension_name = data.get("cluster_dimension_name") or ("应用场景聚类" if axis == "application" else "技术路线聚类")
    quality = data.get("clustering_quality") if isinstance(data.get("clustering_quality"), dict) else {}
    quality.setdefault("cluster_count", len(clusters))
    # 二维语义投影：以(选定轴匹配分, 另一轴匹配分)为坐标，归一化到[5,95]供前端散点图
    other_axis = "application" if axis == "technical" else "technical"
    _xs, _ys, _pts = [], [], []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        _xs.append(float((doc.get(axis) or {}).get("score") or 0))
        _ys.append(float((doc.get(other_axis) or {}).get("score") or 0))
        _pts.append(doc)

    def _norm(vals):
        if not vals:
            return []
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-9:
            return [50.0] * len(vals)
        return [(v - lo) / (hi - lo) * 90 + 5 for v in vals]
    _nx, _ny = _norm(_xs), _norm(_ys)
    projection = [
        {
            "document_id": _pts[i].get("document_id") or _pts[i].get("id") or "",
            "cluster_id": (_pts[i].get(axis) or {}).get("topic_id", ""),
            "x": round(_nx[i], 2),
            "y": round(_ny[i], 2),
        }
        for i in range(len(_pts))
    ]
    # 主题趋势：仅当文献带真实发表年份时派生年度分布，否则留空（前端隐藏 trends tab）
    year_cluster = {}
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        y = doc.get("publication_year")
        if not isinstance(y, int):
            continue
        cid = (doc.get(axis) or {}).get("topic_id") or "未归类"
        year_cluster.setdefault(y, {})
        year_cluster[y][cid] = year_cluster[y].get(cid, 0) + 1
    trend = {}
    if year_cluster:
        years = sorted(year_cluster)
        rep_map = {c["cluster_id"]: c.get("representative_terms") or [] for c in clusters}
        seen_cids = sorted({cid for yc in year_cluster.values() for cid in yc})
        series = [{
            "cluster_id": cid,
            "representative_terms": rep_map.get(cid, []),
            "yearly_counts": [year_cluster.get(y, {}).get(cid, 0) for y in years],
        } for cid in seen_cids]

        def _tag(counts):
            mid = len(counts) // 2
            early = sum(counts[:mid]) if mid else 0
            late = sum(counts[mid:])
            if sum(counts) == 0:
                return None
            if early == 0 and late > 0:
                return "emerging"
            if late > early:
                return "rising"
            if late == early and late > 0:
                return "stable"
            return None
        rising = emerging = stable = "—"
        for s in series:
            t = _tag(s["yearly_counts"])
            if t == "rising" and rising == "—":
                rising = s["cluster_id"]
            elif t == "emerging" and emerging == "—":
                emerging = s["cluster_id"]
            elif t == "stable" and stable == "—":
                stable = s["cluster_id"]
        total_with_year = sum(sum(s["yearly_counts"]) for s in series)
        trend = {
            "years": years,
            "series": series,
            "rising_cluster_id": rising,
            "emerging_cluster_id": emerging,
            "stable_cluster_id": stable,
            "summary": f"共 {len(years)} 个年份、{total_with_year} 篇带年份文献参与趋势统计。",
        }
    return {
        **data,
        "input_type": payload.get("input_type"),
        "cluster_dimension": dimension,
        "clusters": clusters,
        "input_summary": data.get("input_summary") or {"document_count": n, "parsed_sentence_count": data.get("parsed_sentence_count", 0)},
        "cluster_dimension_name": dimension_name,
        "clustering_quality": quality,
        "document_assignments": data.get("document_assignments") or assignments,
        "semantic_projection": data.get("semantic_projection") or projection,
        "theme_trend_analysis": data.get("theme_trend_analysis") or trend,
        "training_evaluation": data.get("training_evaluation") or {
            "dataset_version": None,
            "evidence_status": "not_evaluated",
            "notice": "本次仅执行用户文献聚类，未运行独立模型性能评测。",
            "metrics": {},
        },
        "dimension": dimension,
        "quality_metrics": data.get("quality_metrics"),
        "correction_status": data.get("correction_status", "unreviewed"),
    }


_CLUSTER_LABEL_STAGE_META = {
    "evidence_normalization": ("证据归一化", "类簇短语证据清洗与归一化"),
    "bge_phrase_encoding": ("短语语义编码", "BGE-M3 短语向量编码完成"),
    "semantic_centroid_construction": ("语义中心构建", "构建类簇语义中心向量"),
    "semantic_candidate_generation": ("候选标签生成", "基于语义中心生成候选标签"),
    "evidence_coverage_scoring": ("证据覆盖打分", "候选标签证据覆盖率评分"),
    "low_confidence_soft_fallback": ("低置信软回退", "低置信类簇软规则回退补全"),
    "cross_cluster_distance_reporting": ("类簇差异度量", "计算类簇间差异距离"),
    "phrase_cleaning_and_normalization": ("短语清洗归一", "类簇短语清洗与归一化"),
    "frequency_ngram_and_cooccurrence_candidates": ("频次与共现候选", "提取频次/N-gram/共现候选"),
    "evidence_grounded_candidate_scoring": ("证据打分", "候选标签证据打分"),
    "cross_cluster_differentiation": ("类簇差异化", "类簇间差异化筛选"),
    "global_label_selection": ("全局标签筛选", "全局择优输出推荐标签"),
}


def _labels(raw: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """聚类标签 → Vue 渲染契约（renderClusterLabels）。

    后端 _execute_labeling 产出 clusters[{cluster_id,label,doc_indices,n}]、n。
    renderClusterLabels 期望 labels[{cluster_id,recommended_label,linked_document_ids,
    candidate_labels,evidence}]、cluster_count、generated_label_count、statistics。
    """
    data = raw if isinstance(raw, dict) else {}
    source = data.get("labels") or data.get("clusters") or []
    labels = []
    for index, item in enumerate(_list(source)):
        if not isinstance(item, dict):
            continue
        label = item.get("label") or item.get("recommended_label") or item.get("name") or ""
        doc_indices = _list(item.get("doc_indices") or item.get("linked_document_ids"))
        labels.append({
            **item,
            "cluster_id": item.get("cluster_id") or item.get("topic_id") or f"C{index + 1}",
            "recommended_label": item.get("recommended_label") or label,
            "label": label,
            "confidence": _confidence(item),
            "distinctiveness": item.get("distinctiveness"),
            "linked_document_ids": doc_indices,
            "candidate_labels": _list(item.get("candidate_labels") or item.get("alternatives") or item.get("candidates")),
            "alternatives": _list(item.get("alternatives") or item.get("candidate_labels")),
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), dict) else {},
        })
    statistics = data.get("statistics") if isinstance(data.get("statistics"), dict) else {}
    generation_report = data.get("label_generation_process_report") or data.get("generation_report") or {
        "generated_count": len(labels),
    }
    # 引擎输出的 stages 是流程标识字符串数组（如 ["evidence_normalization", ...]），
    # 前端 renderClusterLabelReview 的"处理阶段/阶段输出"表格期望对象数组
    # [{order,name,status,output}]；若不归一化，stage.name/output 为 undefined，
    # 走后端分支（stages 非空不触发 fallback）导致阶段输出显示空。在此转成对象数组。
    if isinstance(generation_report, dict):
        generation_report = dict(generation_report)
        _raw_stages = generation_report.get("stages")
        if isinstance(_raw_stages, list) and _raw_stages and not isinstance(_raw_stages[0], dict):
            generation_report["stages"] = [
                {
                    "order": _i + 1,
                    "name": _CLUSTER_LABEL_STAGE_META.get(_s, (_s, _s))[0],
                    "status": "completed",
                    "output": _CLUSTER_LABEL_STAGE_META.get(_s, (_s, _s))[1],
                }
                for _i, _s in enumerate(str(_s) for _s in _raw_stages)
            ]
    optimization = data.get("label_distinctiveness_optimization_result") or data.get("label_differentiation_optimization") or {
        "threshold": payload.get("distinctiveness_threshold"),
        "clusters": [],
    }
    return {
        **data,
        "labels": labels,
        "cluster_count": data.get("cluster_count") or len(labels),
        "generated_label_count": data.get("generated_label_count") or len(labels),
        "statistics": statistics,
        "parameters": data.get("parameters") or {
            "label_length_limit": payload.get("label_length_limit"),
            "language_type": payload.get("language_type"),
            "distinctiveness_threshold": payload.get("distinctiveness_threshold"),
        },
        "source_cluster_task_id": data.get("source_cluster_task_id") or payload.get("cluster_task_id"),
        "generation_report": generation_report,
        "label_generation_process_report": generation_report,
        "label_distinctiveness_optimization_result": optimization,
    }


def _review(raw: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """结构化综述 → 最新 Vue 渲染契约。

    新引擎已经直接产出需规的四项业务结果，这里只做类型稳定和兼容保护，
    不再把历史深度聚类输出映射成研究问题。
    """
    data = raw if isinstance(raw, dict) else {}
    tree = [item for item in _list(data.get("tree")) if isinstance(item, dict)]
    cluster_induction = (
        data.get("cluster_induction_results")
        if isinstance(data.get("cluster_induction_results"), dict)
        else {"cluster_count": 0, "clusters": [], "induction_basis": ""}
    )
    cluster_induction.setdefault("cluster_count", len(_list(cluster_induction.get("clusters"))))
    cluster_induction.setdefault("clusters", [])
    structured_report = (
        data.get("structured_report")
        if isinstance(data.get("structured_report"), dict)
        else {"title": "", "overview": "", "sections": []}
    )
    structured_report.setdefault("title", "")
    structured_report.setdefault("overview", "")
    structured_report.setdefault("sections", [])
    trend_hotspot = (
        data.get("trend_hotspot_distribution")
        if isinstance(data.get("trend_hotspot_distribution"), dict)
        else {"time_range": None, "hotspots": []}
    )
    trend_hotspot.setdefault("time_range", None)
    trend_hotspot.setdefault("hotspots", [])
    hotspots = [item for item in _list(trend_hotspot.get("hotspots")) if isinstance(item, dict)]
    trend_analysis = None
    if trend_hotspot.get("time_range") or hotspots:
        rising = [
            str(item.get("name") or "") for item in hotspots
            if any(k in str(item.get("status") or "") for k in ("上升", "新兴"))
        ]
        parts = []
        if trend_hotspot.get("time_range"):
            parts.append(f"文献发表时间跨度 {trend_hotspot['time_range']}")
        if hotspots:
            parts.append(f"共识别 {len(hotspots)} 个研究热点，首要热点为「{hotspots[0].get('name') or ''}」")
        if rising:
            parts.append("呈上升或新兴趋势的方向包括：" + "、".join(name for name in rising[:3] if name))
        trend_analysis = "；".join(parts) + "。" if parts else None
    evidence_index = [item for item in _list(data.get("evidence_index")) if isinstance(item, dict)]
    statistics = data.get("statistics") if isinstance(data.get("statistics"), dict) else {}
    statistics.setdefault("research_question_count", len(tree))
    statistics.setdefault("method_count", sum(len(_list(t.get("methods"))) for t in tree))
    statistics.setdefault("evidence_sentence_count", len(evidence_index))
    documents = _list(payload.get("document_set") or payload.get("documents") or payload.get("texts"))
    document_count = data.get("document_count") or len(documents)
    return {
        **data,
        "input_type": payload.get("input_type"),
        "document_count": document_count,
        "tree": tree,
        "cluster_induction_results": cluster_induction,
        "structured_report": structured_report,
        "trend_hotspot_distribution": trend_hotspot,
        "trend_analysis": trend_analysis,
        "hotspots": hotspots,
        "evidence_index": evidence_index,
        "evidence": _list(data.get("evidence")) or evidence_index,
        "statistics": statistics,
        "topic": data.get("topic") or payload.get("topic_or_keywords"),
    }
