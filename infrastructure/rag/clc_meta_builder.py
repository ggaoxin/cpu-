"""CLC 元数据构建与判定（供建索引脚本与用户上传资源建库共用）。

从 scripts/merge_clc_kb.py 与 scripts/parse_clc_pdf.py 抽出的核心逻辑：
- normalize_meta：补全 entry 的 parent_code/level/path_codes/path_names/full_path/rag_text/id
  （用户上传数据可能只有 clc_code/clc_name，统一补全供检索与防幻觉 resolve_code 使用）
- detect_taxonomy_kind：判定用户上传数据的结构类型，供分治（few-shot vs 建外部向量库）

设计要点：
- 父码按 CLC 前缀层级推导（去小数点末段 + 逐字符去尾找最长存在前缀），与 parse_clc_pdf 一致；
- detect 不修改原数据，parent_code 缺失时用 parent_of 推导覆盖率，判 complete/scattered。
"""
from __future__ import annotations

from typing import Any, Dict, List


def parent_of(code: str, codes: set) -> str | None:
    """按前缀层级找最长存在父码（去小数点末段 + 逐字符去尾）。

    TM714.1 → TM714（去小数点末段）→ TM71 → TM7 → TM → T，取集合内最长存在者。
    """
    cands = []
    if "." in code:
        cands.append(code.rsplit(".", 1)[0])
    cur = code
    while cur:
        cur = cur[:-1]
        cands.append(cur)
    for c in cands:
        if c and c in codes and c != code:
            return c
    return None


def _build_rag_text(e: Dict[str, Any]) -> str:
    """构造检索文本（模板与 parse_clc_pdf.py / merge_clc_kb.py 一致）。"""
    return (
        f"分类号：{e['clc_code']}\n分类名称：{e['clc_name']}\n"
        f"上位分类号：{e['parent_code'] or '无'}\n分类路径：{e['full_path']}\n"
        f"路径分类号：{' / '.join(e['path_codes'])}\n"
        f"路径名称：{' / '.join(e['path_names'])}\n"
        f"检索文本：{e['clc_code']} {e['clc_name']} {e['full_path']} {e['clc_name']}"
    )


def normalize_meta(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """补全每条 entry 的 parent_code/level/path_codes/path_names/full_path/rag_text/id。

    输入条目至少需 clc_code + clc_name（parent_code 可选，缺则按前缀推导）。
    level/path_codes/path_names/full_path/rag_text 统一重算以保证一致性（即便已存在也覆盖）。
    就地修改并返回同一 list；id 按 list 顺序重排。
    """
    if not isinstance(entries, list):
        return []
    codes = {str(e.get("clc_code", "")).strip() for e in entries
             if isinstance(e, dict) and e.get("clc_code")}
    # 1. parent_code：缺则按前缀推导
    for e in entries:
        if not isinstance(e, dict):
            continue
        code = str(e.get("clc_code", "")).strip()
        if not code:
            continue
        if not e.get("parent_code"):
            e["parent_code"] = parent_of(code, codes)
    # 2. chain walk 补 level/path/full_path/rag_text/id
    idx = {str(e.get("clc_code", "")).strip(): e for e in entries
           if isinstance(e, dict) and e.get("clc_code")}
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            continue
        code = str(e.get("clc_code", "")).strip()
        if not code:
            continue
        chain, cur, seen = [], code, set()
        while cur and cur in idx and cur not in seen:
            chain.append(cur)
            seen.add(cur)
            cur = idx[cur].get("parent_code")
        chain.reverse()
        e["id"] = i
        e["level"] = len(chain)
        e["path_codes"] = chain
        e["path_names"] = [idx[c].get("clc_name", "") for c in chain]
        e["full_path"] = " > ".join(f"{c} {idx[c].get('clc_name', '')}" for c in chain)
        e["rag_text"] = _build_rag_text(e)
    return entries


def detect_taxonomy_kind(entries: Any) -> str:
    """判定用户上传 CLC 数据的结构类型，供分治（不改原数据）。

    - labeled_papers：文献标注样本（首条有 ch_name|en_name + main_classification.clc_code，
      或顶层 manual_category_id + manual_category_name）
    - taxonomy_complete：分类树且父链可上溯覆盖≥60%（parent_code 显式在集合内或前缀可推导）
    - taxonomy_scattered：有 clc_code+clc_name 但父链覆盖<60%（散点，建库会让 resolve_code 上溯失效）
    - unknown：非 CLC 数据
    """
    if isinstance(entries, dict):
        # 包装对象解包：{label_version, document_labels:[...]} → 条目列表
        entries = next(
            (entries[k] for k in ("document_labels", "labels", "entries", "items", "data", "records")
             if isinstance(entries.get(k), list)),
            None,
        )
    if not isinstance(entries, list) or not entries:
        return "unknown"
    first = entries[0] if isinstance(entries[0], dict) else {}
    code = str(first.get("clc_code", "")).strip()
    name = str(first.get("clc_name", "")).strip()
    if not code or not name:
        # 字段别名（code/name、manual_category_id/manual_category_name 等）→ 分类表
        code = str(first.get("manual_category_id") or first.get("code") or "").strip()
        name = str(first.get("manual_category_name") or first.get("name") or "").strip()
    if code and name:
        codes = {str(e.get("clc_code", "")).strip() for e in entries
                 if isinstance(e, dict) and e.get("clc_code")}
        n = len(entries)
        has_parent = 0
        for e in entries:
            if not isinstance(e, dict):
                continue
            c = str(e.get("clc_code", "")).strip()
            if not c:
                continue
            p = str(e.get("parent_code") or "").strip()
            if p and p in codes and p != c:
                has_parent += 1
            elif parent_of(c, codes):  # 无显式 parent → 按前缀推导
                has_parent += 1
        coverage = has_parent / n if n else 0
        return "taxonomy_complete" if coverage >= 0.6 else "taxonomy_scattered"
    # labeled_papers：文献标注样本
    title = str(first.get("ch_name") or first.get("en_name")
                or first.get("title") or first.get("document_id") or "").strip()
    main = first.get("main_classification")
    if not isinstance(main, dict):
        main = first.get("manual_category") if isinstance(first.get("manual_category"), dict) else {}
    main_code = str(main.get("clc_code") or main.get("code") or "").strip() \
        or str(first.get("manual_category_id") or "").strip()
    if title and main_code:
        return "labeled_papers"
    return "unknown"
