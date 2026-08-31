"""用户上传 CLC 条目的轻量作用域检索器（未建向量索引时使用）。

背景：用户在中文/英文科技文献分类中选择自定义 CLC 资源，但条目结构为散点表/
小表/标注样本（未触发向量索引构建）时，后置校验 ``resolve_code`` 若回退内置
中图法知识库，会把用户自定义分类号上溯成内置码——表现为"选了用户上传资源，
最后还是按后台内置分类"。

此检索器仅以用户条目为事实来源：resolve_code / children / retrieve 全部对用户
条目生效，接口与 ``CLCRetriever`` 对齐，供 ``_execute_classification`` 无缝替换。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _norm_code(value: Any) -> str:
    return str(value or "").strip().upper()


# 分类号/类名的常见字段别名（兼容用户上传数据的多种命名习惯）。
_CODE_KEYS = ("clc_code", "code", "classification_code", "class_code", "clc", "id", "manual_category_id", "category_id")
_NAME_KEYS = ("clc_name", "name", "classification_name", "class_name", "label", "title", "manual_category_name", "category_name")
# 标注样本里承载分类的嵌套对象字段名。
_NESTED_KEYS = ("main_classification", "classification", "clc", "category", "manual_category")


def _extract_code_name(entry: Dict[str, Any]) -> tuple[str, str]:
    """从条目提取 (code, name)，兼容分类表条目与标注样本两种结构。

    优先在顶层找 clc_code/clc_name；找不到则在嵌套对象（main_classification 等）里找。
    """
    for ck in _CODE_KEYS:
        code = _norm_code(entry.get(ck))
        if code:
            for nk in _NAME_KEYS:
                name = str(entry.get(nk) or "").strip()
                if name:
                    return code, name
            return code, ""  # 有码无名也先收，后续统一在 __init__ 过滤
    # 顶层无码，在嵌套对象里找（标注样本）
    for nk in _NESTED_KEYS:
        nested = entry.get(nk)
        if isinstance(nested, dict):
            for ck in _CODE_KEYS:
                code = _norm_code(nested.get(ck))
                if code:
                    name = ""
                    for nnk in _NAME_KEYS:
                        name = str(nested.get(nnk) or "").strip()
                        if name:
                            break
                    return code, name
    return "", ""


class UserCLCScopeRetriever:
    """以用户上传条目为唯一事实来源的 CLC 作用域检索器。

    支持两种条目结构（与 detect_taxonomy_kind 对齐）：
    - 分类表条目：``{clc_code, clc_name, parent_code?}``
    - 标注样本：``{ch_name|en_name, main_classification: {clc_code, clc_name}}``
      （有效分类号取样本 main_classification 的去重集合）
    """

    # 包装对象里承载条目列表的常见字段名（如 {label_version, document_labels:[...]}）。
    _ENTRY_LIST_KEYS = ("document_labels", "labels", "entries", "items", "data", "records")

    def __init__(self, entries: List[Any]):
        code_map: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        idx = 0
        # 包装对象解包：{label_version, document_labels:[...]} → document_labels 列表
        if isinstance(entries, dict):
            entries = next(
                (entries[k] for k in self._ENTRY_LIST_KEYS if isinstance(entries.get(k), list)),
                [],
            )
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            code, name = _extract_code_name(entry)
            if not code or not name:
                continue
            idx += 1
            item = {
                "id": f"user_clc_{idx}",
                "clc_code": code,
                "clc_name": name,
                "parent_code": _norm_code(
                    entry.get("parent_code") or entry.get("parent") or entry.get("parent_clc_code")),
                "full_path": name,
                "path_codes": [code],
                "path_names": [name],
                # 检索特征文本：类名 + 路径词（供关键词打分）
                "_text": name,
            }
            if code not in code_map:
                code_map[code] = item
                order.append(code)
        if not code_map:
            raise ValueError("用户 CLC 资源中无有效条目（缺少 clc_code/clc_name）")
        # 路径补全：有 parent 链的条目沿 code_map 上溯拼 full_path/path_names
        for code in order:
            item = code_map[code]
            parent = item.get("parent_code")
            if parent and parent in code_map and parent != code:
                chain_codes, chain_names = [code], [item["clc_name"]]
                cur, seen = parent, {code}
                while cur and cur in code_map and cur not in seen:
                    seen.add(cur)
                    chain_codes.insert(0, cur)
                    chain_names.insert(0, code_map[cur]["clc_name"])
                    cur = code_map[cur].get("parent_code")
                item["path_codes"] = chain_codes
                item["path_names"] = chain_names
                item["full_path"] = "/".join(chain_names)
            item["_text"] = " ".join(item["path_names"])
        self._code_map = code_map
        self._order = order

    # ---- 与 CLCRetriever 对齐的接口 ---- #

    def resolve_code(self, code: str) -> Optional[Dict[str, Any]]:
        """在用户条目内解析分类号：精确命中 → 去小数段 → 最长存在前缀；无则 None。"""
        code = _norm_code(code)
        if not code:
            return None
        if code in self._code_map:
            return self._entry(code)
        cands = []
        if "." in code:
            cands.append(code.split(".")[0])
        cur = code
        while cur:
            cur = cur[:-1]
            cands.append(cur)
        for cand in cands:
            if cand and cand in self._code_map:
                return self._entry(cand)
        return None

    def children(self, code: str) -> List[Dict[str, Any]]:
        code = _norm_code(code)
        return [self._entry(c) for c in self._order
                if self._code_map[c].get("parent_code") == code]

    def retrieve(
        self,
        title: str = "",
        abstract: str = "",
        keywords: Optional[List[str]] = None,
        k: int = 10,
        cross_lingual: bool = False,
    ) -> List[Dict[str, Any]]:
        """关键词重叠打分返回 top-K 用户条目（无向量索引的轻量替代）。

        用户条目通常 ≤ 数百条，词面匹配足以把相关类目排前；候选同时作为
        LLM 的"仅以下合法"约束来源。
        """
        terms = [t for t in re.split(r"[\s,，;；/]+", f"{title or ''} {' '.join(keywords or [])}")
                 if len(t) >= 2]
        if not terms and abstract:
            terms = [t for t in re.split(r"[\s,，;；。/]+", abstract) if len(t) >= 2][:40]
        scored = []
        for code in self._order:
            item = self._code_map[code]
            text = item["_text"]
            score = sum(1.0 for t in terms if t in text)
            # 类名词面占 title 的重叠也计分（标题词直接命中类名）
            if item["clc_name"] and item["clc_name"] in (title or ""):
                score += 2.0
            scored.append((score, code))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        cands = []
        for rank, (score, code) in enumerate(scored[: max(1, min(k, len(scored)))], start=1):
            item = self._entry(code)
            cands.append({**item, "rag_entry_id": item["id"],
                          "classification_path": item["full_path"],
                          "rank": rank, "score": float(score)})
        return cands

    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        code = _norm_code(code)
        return self._entry(code) if code in self._code_map else None

    # ---- 内部 ---- #

    def _entry(self, code: str) -> Dict[str, Any]:
        """对外条目去掉内部检索字段 _text。"""
        return {k: v for k, v in self._code_map[code].items() if not k.startswith("_")}
