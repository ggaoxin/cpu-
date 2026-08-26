"""Vue 工具 ID 与 DDD 后端功能码的稳定映射。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class ToolContract:
    tool_id: str
    backend_code: str
    name: str
    collection_tool: bool = False
    export_formats: Tuple[str, ...] = ("json", "csv")
    min_items: int = 1
    max_items: int = 20


CONTRACTS = [
    ToolContract("zh-abstract-move", "mr_zh_abstract", "中文摘要语步识别"),
    ToolContract("en-abstract-move", "mr_en_abstract", "英文摘要语步识别"),
    ToolContract("fund-move", "mr_zh_fund", "中文基金项目语步识别", export_formats=("json", "csv", "database")),
    ToolContract("zh-classify", "ac_zh", "中文科技文献分类"),
    ToolContract("en-classify", "ac_en", "英文科技文献分类", export_formats=("json", "csv", "xml")),
    ToolContract("domain-classify", "ac_domain", "专业领域科技文献分类"),
    ToolContract("zh-keyword", "kw_zh", "中文科技文献关键词识别"),
    ToolContract("en-keyword", "kw_en", "英文科技文献关键词识别", export_formats=("json", "csv", "xml")),
    ToolContract("rq-detect", "rq_identify", "研究问题句及短语识别"),
    ToolContract("citation-sentiment", "cr_sentiment", "引用情感识别"),
    ToolContract("citation-intent", "cr_intent", "引用意图识别"),
    ToolContract("definition-detect", "cd_identify", "概念定义句及概念词识别"),
    ToolContract("general-ner", "ner_general", "中英文通用领域命名实体识别"),
    ToolContract("research-ner", "ner_research", "中英文通用科研实体识别"),
    ToolContract("domain-ner", "ner_domain", "专业领域科研实体识别"),
    ToolContract("relation-extract", "ner_relation", "实体关系识别", export_formats=("json", "csv", "rdf")),
    # 与 Vue 在线测试一致：至少 4 篇，避免极小样本无法形成有意义的多类簇结果。
    ToolContract("deep-cluster", "dc_cluster", "科技文献深度聚类", collection_tool=True, min_items=4, max_items=50),
    # 标签工具处理的是深度聚类输出的类簇短语集合。一个类簇也可以生成标签，
    # 不能沿用深度聚类对文献数量的下限。
    ToolContract("cluster-label", "cl_label", "类簇标签自动生成", collection_tool=True, min_items=1, max_items=50),
    ToolContract("structured-review", "sr_review", "结构化自动综述生成", collection_tool=True, export_formats=("json", "csv", "report"), min_items=3, max_items=50),
]

BY_TOOL_ID: Dict[str, ToolContract] = {item.tool_id: item for item in CONTRACTS}


def get_contract(tool_id: str) -> ToolContract:
    try:
        return BY_TOOL_ID[tool_id]
    except KeyError as exc:
        raise ValueError(f"未知 Vue 工具 ID：{tool_id}") from exc
