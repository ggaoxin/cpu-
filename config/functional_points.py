"""功能点注册表（中央目录）。

语义计算工具库共 10 个功能项、19 个功能点。每个功能点在此登记：
- code：全局唯一短码，同时作为 API 路径与规则库文件定位 key
- name / functional_item：中文名称与所属功能项
- input_type：``text`` 单篇文本 | ``multi_text`` 多篇文本
- rule_path：相对 rules/ 的独立规则库文件路径（每个功能点独立，互不混用）

新增功能点只需在此登记并补一个对应规则库 YAML，控制器与路由会自动挂载。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class InputType(str, Enum):
    TEXT = "text"            # 单篇文献文本片段
    MULTI_TEXT = "multi_text"  # 多篇文献文本集合


@dataclass(frozen=True)
class FunctionalPoint:
    code: str
    name: str
    functional_item: str
    functional_item_code: str
    description: str
    input_type: InputType
    rule_path: str  # 相对 rules/ 目录


# ---- 10 个功能项 ----
ITEM_MOVE = "语步识别工具"
ITEM_CLASSIFY = "自动分类工具"
ITEM_KEYWORD = "关键词识别工具"
ITEM_RQ = "研究问题识别工具"
ITEM_CITATION = "引用句识别工具"
ITEM_CONCEPT = "概念定义识别工具"
ITEM_NER = "命名实体识别工具"
ITEM_CLUSTER = "深度聚类工具"
ITEM_LABEL = "聚类标签生成工具"
ITEM_REVIEW = "结构化自动综述工具"


FUNCTIONAL_POINTS: List[FunctionalPoint] = [
    # 1. 语步识别工具（3）
    FunctionalPoint("mr_zh_abstract", "中文摘要语步识别", ITEM_MOVE, "move_recognition",
        "从中文科技文献摘要中标注研究背景/目的/方法/结果/结论语步句。",
        InputType.TEXT, "move_recognition/mr_zh_abstract.yaml"),
    FunctionalPoint("mr_en_abstract", "英文摘要语步识别", ITEM_MOVE, "move_recognition",
        "从英文科技文献摘要中标注语步类别。",
        InputType.TEXT, "move_recognition/mr_en_abstract.yaml"),
    FunctionalPoint("mr_zh_fund", "中文基金项目语步识别", ITEM_MOVE, "move_recognition",
        "从基金申请书/立项书中识别立项依据、研究目标、技术方案等语步。",
        InputType.TEXT, "move_recognition/mr_zh_fund.yaml"),

    # 2. 自动分类工具（3）
    FunctionalPoint("ac_zh", "中文科技文献分类", ITEM_CLASSIFY, "auto_classification",
        "按中图分类法将中文科技文献细分到科学技术类目，交叉学科给备选号。",
        InputType.TEXT, "auto_classification/ac_zh.yaml"),
    FunctionalPoint("ac_en", "英文科技文献分类", ITEM_CLASSIFY, "auto_classification",
        "按中图分类法将英文科技文献分类并完成跨语言类目映射。",
        InputType.TEXT, "auto_classification/ac_en.yaml"),
    FunctionalPoint("ac_domain", "专业领域科技文献分类", ITEM_CLASSIFY, "auto_classification",
        "面向医学/材料/能源等专业领域的多层级细粒度分类。",
        InputType.TEXT, "auto_classification/ac_domain.yaml"),

    # 3. 关键词识别工具（2）
    FunctionalPoint("kw_zh", "中文科技文献关键词识别", ITEM_KEYWORD, "keyword_recognition",
        "从中文科技文献片段中抽取反映主题的关键短语/术语。",
        InputType.TEXT, "keyword_recognition/kw_zh.yaml"),
    FunctionalPoint("kw_en", "英文科技文献关键词识别", ITEM_KEYWORD, "keyword_recognition",
        "从英文科技文献片段中抽取主题关键词与跨领域术语。",
        InputType.TEXT, "keyword_recognition/kw_en.yaml"),

    # 4. 研究问题识别工具（1）
    FunctionalPoint("rq_identify", "研究问题识别", ITEM_RQ, "research_question",
        "识别表达研究问题的句子及句中研究问题短语。",
        InputType.TEXT, "research_question/rq_identify.yaml"),

    # 5. 引用句识别工具（2）
    FunctionalPoint("cr_sentiment", "引用情感识别", ITEM_CITATION, "citation_recognition",
        "判定引用句的引用情感：支持/中立/有局限性。",
        InputType.TEXT, "citation_recognition/cr_sentiment.yaml"),
    FunctionalPoint("cr_intent", "引用意图识别", ITEM_CITATION, "citation_recognition",
        "判定引用句的引用意图：背景介绍/方法引入/结果比较。",
        InputType.TEXT, "citation_recognition/cr_intent.yaml"),

    # 6. 概念定义识别工具（1）
    FunctionalPoint("cd_identify", "概念定义识别", ITEM_CONCEPT, "concept_definition",
        "识别描述概念定义的句子并提取被定义的概念词。",
        InputType.TEXT, "concept_definition/cd_identify.yaml"),

    # 7. 命名实体识别工具（4）
    FunctionalPoint("ner_general", "中英文通用领域命名实体识别", ITEM_NER, "ner",
        "识别人名/地名/机构名/事件等通用领域实体。",
        InputType.TEXT, "ner/ner_general.yaml"),
    FunctionalPoint("ner_research", "中英文通用科研实体识别", ITEM_NER, "ner",
        "识别模型方法/数据资料/仪器设备/理论原理/研究问题等科研实体。",
        InputType.TEXT, "ner/ner_research.yaml"),
    FunctionalPoint("ner_domain", "专业领域科研实体识别", ITEM_NER, "ner",
        "面向医学/化工/物理等专业领域的细粒度实体识别。",
        InputType.TEXT, "ner/ner_domain.yaml"),
    FunctionalPoint("ner_relation", "实体关系识别", ITEM_NER, "ner",
        "在实体识别基础上抽取实体间关系三元组，构建知识网络。",
        InputType.TEXT, "ner/ner_relation.yaml"),

    # 8. 深度聚类工具（1）
    FunctionalPoint("dc_cluster", "深度聚类", ITEM_CLUSTER, "deep_clustering",
        "按技术路线轴或应用场景轴执行无主题库语义聚类。",
        InputType.MULTI_TEXT, "deep_clustering/dc_cluster.yaml"),

    # 9. 聚类标签生成工具（1）
    FunctionalPoint("cl_label", "聚类标签生成", ITEM_LABEL, "cluster_labeling",
        "接收深度聚类输出的类簇短语集合，生成标签、过程报告和差异化优化结果。",
        InputType.MULTI_TEXT, "cluster_labeling/cl_label.yaml"),

    # 10. 结构化自动综述工具（1）
    FunctionalPoint("sr_review", "结构化自动综述", ITEM_REVIEW, "structured_review",
        "抽取并聚类相似研究问题，匹配研究方法，生成含原文证据的结构化综述。",
        InputType.MULTI_TEXT, "structured_review/sr_review.yaml"),
]


# 索引：code -> FunctionalPoint
_BY_CODE: Dict[str, FunctionalPoint] = {fp.code: fp for fp in FUNCTIONAL_POINTS}

# 索引：functional_item_code -> [FunctionalPoint]
_BY_ITEM: Dict[str, List[FunctionalPoint]] = {}
for _fp in FUNCTIONAL_POINTS:
    _BY_ITEM.setdefault(_fp.functional_item_code, []).append(_fp)


def get_functional_point(code: str) -> FunctionalPoint:
    """按 code 获取功能点；不存在则抛 KeyError。"""
    if code not in _BY_CODE:
        raise KeyError(f"未知功能点 code: {code}")
    return _BY_CODE[code]


def list_functional_points() -> List[FunctionalPoint]:
    return list(FUNCTIONAL_POINTS)


def list_points_by_item(item_code: str) -> List[FunctionalPoint]:
    return list(_BY_ITEM.get(item_code, []))


def list_items() -> List[str]:
    """按登记顺序返回 10 个功能项 code。"""
    seen, items = set(), []
    for fp in FUNCTIONAL_POINTS:
        if fp.functional_item_code not in seen:
            seen.add(fp.functional_item_code)
            items.append(fp.functional_item_code)
    return items
