"""用户上传语义资源的公共 JSON 归一化层（确定性规则，不调用大模型）。

背景：/semantic-resources/upload 只做大小校验+落盘+登记，业务解析分散在各工具
内部且互不一致——用户上传字段名不对、外层多一层包装时"上传成功但解析 0 条"，
流程静默回退内置资源，用户无感知。本模块在资源解析分发层
（ToolIntegrationService._parameters）对**用户指定**的资源统一做：

1. JSON 解码校验（失败抛 ResourceParseError，明确报错不吞异常）；
2. 结构解包：顶层对象 → 取内部业务数组（labeled_documents/records/data 等）；
3. 字段别名映射：常见别名归一到各资源字段的标准 key（如 category→technical_cluster_id）；
4. 衍生补全：cluster_name 缺失时复用类目 id；
5. 无效条目过滤 + **零有效条目兜底**：抛 ResourceParseError（上层返回 42201
   业务信封，禁止静默回退内置继续跑）。

范围约束：仅处理 JSON；CSV/JSONL/TXT 与内置(bundled)资源不在本层处理。
归一化结果按解析后的绝对路径注册（register_normalized / normalized_rows_for），
各业务消费点优先取用，保证"预检"与"消费"看到同一份标准结构。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

# ---------------- 异常 ----------------


class ResourceParseError(ValueError):
    """用户指定资源解析失败（JSON 损坏 / 零有效条目）。

    继承 ValueError：ToolIntegrationService.execute 对 _parameters 的
    ValueError 已有统一 42201 业务信封出口，前端直接展示 message。
    """


# ---------------- 通用解包 ----------------

# 顶层对象里常见的主数据数组字段名（按优先级；命中即取出，其余包装字段丢弃）
_UNWRAP_KEYS: Sequence[str] = (
    "labeled_documents", "document_labels", "documents", "records", "entries",
    "items", "data", "rows", "list", "results", "samples", "training_samples",
    "term_list", "terms", "mappings", "labels", "categories", "category_data",
)


def unwrap_rows(raw: Any) -> Optional[List[Any]]:
    """顶层结构解包：list 原样返回；dict 取首个非空数组；单行 dict 包成 [dict]。

    返回 None 表示该结构不是行数据（如纯配置对象）。
    """
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in _UNWRAP_KEYS:
            value = raw.get(key)
            if isinstance(value, list) and value:
                return value
        for value in raw.values():  # 未知名称的业务数组也接受
            if isinstance(value, list) and value and all(isinstance(i, dict) for i in value):
                return value
        # 没有数组：若对象本身像单行数据（有可映射字段），按单行处理
        if _first_present(raw, ("title", "abstract", "text", "content", "term", "clc_code",
                                "technical_cluster_id", "category", "document_id")):
            return [raw]
    return None


def _first_present(row: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


# ---------------- 各资源字段的归一化配置 ----------------


def _normalize_anchor_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    """深度聚类锚点（训练样本/人工标注类目）。

    行有效性：有类目标注 +（可用文本≥30字 或 携带 document_id——纯标签映射
    如 gold_label.json 可在请求侧按 document_id 与输入文献关联补全文本）。
    别名 category/label/class/topic 等同时落到 technical_cluster_id、
    application_cluster_id 与 cluster_name（双轴共用同一用户类目体系）。
    """
    text_keys = ("abstract", "ch_abstract", "en_abstract", "text", "content",
                 "semantic_text", "full_text", "body")
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = _first_present(row, (
            "technical_cluster_id", "application_cluster_id", "category", "category_id",
            "label", "class", "cluster", "cluster_name", "topic", "类目", "分类",
        ))
        title = _first_present(row, ("ch_name", "en_name", "title", "name", "document_title"))
        body = _first_present(row, text_keys)
        doc_id = _first_present(row, ("document_id", "doc_id", "id"))
        if not label:
            continue
        text = "\n".join(p for p in (title or "", body or "") if p)
        if len(text.strip()) < 30 and not doc_id:
            continue  # 既无文本又无编号，无法参与锚点（也无法关联补全）
        new = dict(row)
        new["technical_cluster_id"] = label
        new["application_cluster_id"] = label
        new.setdefault("cluster_name", label)
        if title:
            new.setdefault("title", title)
        if doc_id:
            new.setdefault("document_id", doc_id)
        out.append(new)
    return out


def _normalize_clc_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    """中图分类体系（zh/en-classify 自定义 clc_labeled_data）：行需分类号。"""
    out: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, str) and row.strip():  # 纯分类号字符串数组
            row = {"clc_code": row.strip()}
        if not isinstance(row, dict):
            continue
        code = _first_present(row, ("clc_code", "code", "classification_code", "clc",
                                    "classification", "分类号", "clc号", "中图分类号"))
        if not code:
            continue
        new = dict(row)
        new["clc_code"] = code
        name = _first_present(row, ("clc_name", "name", "label", "title", "类目名称", "类目", "名称"))
        if name:
            new.setdefault("clc_name", name)
        out.append(new)
    return out


def _normalize_mapping_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    """英文关键词分类标准映射表：行需 term + clc_code。"""
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        term = _first_present(row, ("term", "en_term", "english_term", "keyword", "word",
                                    "术语", "英文术语"))
        code = _first_present(row, ("clc_code", "code", "classification_code", "clc",
                                    "分类号", "中图分类号"))
        if not (term and code):
            continue
        new = dict(row)
        new["term"] = term
        new["clc_code"] = code
        name = _first_present(row, ("clc_name", "name", "label", "类目名称", "类目"))
        if name:
            new.setdefault("clc_name", name)
        out.append(new)
    return out


def _normalize_term_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    """术语词典条目：行需 term（纯字符串数组也接受）。"""
    out: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, str) and row.strip():
            out.append({"term": row.strip()})
            continue
        if not isinstance(row, dict):
            continue
        term = _first_present(row, ("term", "keyword", "word", "name", "术语", "词", "词条"))
        if not term:
            continue
        new = dict(row)
        new["term"] = term
        out.append(new)
    return out


def _normalize_generic_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    """通用标注语料（NER 金标/训练数据等）：行是 dict 且含任一文本类字段即保留。"""
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _first_present(row, ("title", "abstract", "text", "content", "sentence",
                                "document_id", "name", "entities", "label", "category")):
            out.append(row)
    return out


# 字段 → (归一化函数, 中文名, 期望结构说明)
ROW_FIELD_CONFIG: Dict[str, Dict[str, Any]] = {
    "training_samples": {"fn": _normalize_anchor_rows, "label": "训练样本",
        "expect": "JSON 数组，每条含 title/abstract 与类目标注（technical_cluster_id 或 category 等别名）"},
    "manually_labeled_category_data": {"fn": _normalize_anchor_rows, "label": "人工标注类目标签数据",
        "expect": "JSON 数组，每条含 title/abstract 与类目标注（technical_cluster_id 或 category 等别名）"},
    "clc_labeled_data": {"fn": _normalize_clc_rows, "label": "中图分类标注数据",
        "expect": "JSON 数组，每条含分类号（clc_code 或 code 等别名）与可选类目名称"},
    "classification_standard_mapping_table": {"fn": _normalize_mapping_rows, "label": "分类标准映射表",
        "expect": "JSON 数组，每条含 term 与 clc_code（或别名）"},
    "domain_terminology_library": {"fn": _normalize_term_rows, "label": "领域术语库",
        "expect": "JSON 数组（术语字符串，或含 term 字段的对象）"},
    "manually_labeled_training_data": {"fn": _normalize_generic_rows, "label": "人工标注训练数据",
        "expect": "JSON 数组，每条为含文本/标注字段的对象"},
    "manually_labeled_data": {"fn": _normalize_generic_rows, "label": "人工标注数据",
        "expect": "JSON 数组，每条为含文本/标注字段的对象"},
    "domain_labeled_training_data": {"fn": _normalize_generic_rows, "label": "领域标注训练数据",
        "expect": "JSON 数组，每条为含文本/标注字段的对象"},
    "general_domain_annotated_corpus": {"fn": _normalize_generic_rows, "label": "通用领域标注语料",
        "expect": "JSON 数组，每条为含文本/标注字段的对象"},
    "multi_domain_scientific_corpus": {"fn": _normalize_generic_rows, "label": "多领域科研语料",
        "expect": "JSON 数组，每条为含文本/标注字段的对象"},
}

# 纯配置型资源：仅做 JSON 解码校验（不做行结构要求，消费端按原样使用）
CONFIG_FIELD_LABELS: Dict[str, str] = {
    "preprocessed_training_set": "引用预处理训练集",
    "ontology_classification_system": "专业领域本体映射体系",
    "domain_classification_rules": "专业领域分类规则",
}


# ---------------- 归一化主入口 ----------------


def normalize_resource_document(raw: Any, *, field: str) -> List[Dict[str, Any]]:
    """对用户资源 JSON 文档做解包+别名映射+衍生+过滤，返回标准行数组。"""
    config = ROW_FIELD_CONFIG.get(field)
    if config is None:  # 配置型：非行结构，原样透传（包装成单行由消费端自行取用）
        return [raw] if isinstance(raw, dict) else list(raw) if isinstance(raw, list) else []
    rows = unwrap_rows(raw)
    if rows is None:
        return []
    return config["fn"](rows)


# ---------------- 按路径注册/取用（消费端与预检共享同一份结果） ----------------

_NORMALIZED: Dict[str, List[Dict[str, Any]]] = {}
_LOCK = threading.Lock()
_CAP = 128  # 注册表上限：用户资源文件数量有限，超限淘汰最旧


def register_normalized(path: Path, rows: List[Dict[str, Any]]) -> None:
    key = str(Path(path).resolve())
    with _LOCK:
        if len(_NORMALIZED) >= _CAP and key not in _NORMALIZED:
            _NORMALIZED.pop(next(iter(_NORMALIZED)))
        _NORMALIZED[key] = rows


def normalized_rows_for(path: Path) -> Optional[List[Dict[str, Any]]]:
    key = str(Path(path).resolve())
    with _LOCK:
        rows = _NORMALIZED.get(key)
    return list(rows) if rows is not None else None


# ---------------- 读取+校验（预检入口） ----------------


def resource_path(storage_uri: str, project_root: Path) -> Optional[Path]:
    """storage_uri → 本地文件路径；project:// 前缀相对项目根。"""
    if not storage_uri:
        return None
    path = project_root / storage_uri.removeprefix("project://") \
        if storage_uri.startswith("project://") else Path(storage_uri)
    return path if path.is_file() else None


def inspect_user_resource(path: Path, *, field: str) -> List[Dict[str, Any]]:
    """读取并归一化用户资源文件；JSON 损坏或零有效条目抛 ResourceParseError。

    成功时把结果注册到路径缓存并返回，供业务消费端 normalized_rows_for 取用。
    """
    try:
        text = Path(path).read_text(encoding="utf-8-sig", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise ResourceParseError(f"资源文件读取失败（{field}）：{exc}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResourceParseError(
            f"资源文件 JSON 解析失败（{field}）：第 {exc.lineno} 行 {exc.msg}。"
            f"请上传标准 JSON 文件（CSV、JSONL、TXT 暂不支持）。"
        ) from exc
    rows = normalize_resource_document(raw, field=field)
    if not rows:
        expect = ROW_FIELD_CONFIG.get(field, {}).get("expect") or "JSON 对象/数组"
        raise ResourceParseError(
            f"文件解析完成，未提取到有效业务数据，请检查JSON文件结构（{field}）：期望 {expect}。"
            f"后端已自动兼容外层包装与常见字段别名；本次转换后有效条目为 0，资源不会生效。"
        )
    register_normalized(path, rows)
    return rows
