"""NER gold 标注脚本（Claude 自主标注，带中/英/缩写变体分组）。

仿 author_rq_standard.py 模式：Claude 读文档，硬编码 MY 标注（每个实体给 canonical + variants），
断言每个变体是原文子串（防幻觉），输出 data/ner/<type>_gold.json。

gold 是"正确答案"：同一实体的中文/英文/缩写归到一组。eval_ner.py 据此对照 LLM 输出，
把 LLM 漏/错的实体的正确形式存进映射表，并随数据积累变体。

用法：
  python -m scripts.author_ner_standard --type ner_general
  python -m scripts.author_ner_standard --type ner_research
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from config.settings import settings

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data" / "ner"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 文档 id → mineru markdown 路径（原文来源，用于断言变体是子串）
MINERU_BASE = Path(str(settings.DATA_DIR / "PdfFiles" / "minerutest" / "mineru_all"))
DOCS = {
    "ch3": MINERU_BASE / "ch3" / "auto" / "ch3.md",
}


def _clean(md_text: str) -> str:
    return re.sub(r"<[^>]+>", "", md_text)


def _load_text(doc_id: str) -> str:
    p = DOCS[doc_id]
    return _clean(p.read_text(encoding="utf-8"))


# ============================== ner_general gold ============================== #
# 实体类型：PERSON / LOCATION / ORGANIZATION / EVENT
NER_GENERAL_GOLD = {
    "ch3": [
        {"canonical": "侯晓洁", "type": "PERSON",
         "variants": ["侯晓洁", "Hou Xiaojie"]},
        {"canonical": "四川传媒学院", "type": "ORGANIZATION",
         "variants": ["四川传媒学院", "Sichuan University of Media and Communications"]},
        {"canonical": "表演学院", "type": "ORGANIZATION",
         "variants": ["表演学院", "School of Performance"]},
        {"canonical": "成都", "type": "LOCATION",
         "variants": ["成都", "Chengdu", "四川成都"]},
    ],
}

# ============================== ner_research gold ============================= #
# 实体类型：METHOD / DATASET / INSTRUMENT / THEORY / TOPIC
NER_RESEARCH_GOLD = {
    "ch3": [
        {"canonical": "大数据与 AI 画像", "type": "METHOD",
         "variants": ["大数据与 AI 画像", "big data and AI portrait technologies",
                      "AI 画像技术", "AI 画像模型"]},
        {"canonical": "动态画像模型", "type": "METHOD",
         "variants": ["动态画像模型", "dynamic portrait models"]},
        {"canonical": "四维思政画像", "type": "METHOD",
         "variants": ["四维思政画像"]},
        {"canonical": "轻量化 AI 工具矩阵", "type": "METHOD",
         "variants": ["轻量化 AI 工具矩阵"]},
        {"canonical": "算法审核与纠错机制", "type": "METHOD",
         "variants": ["算法审核与纠错机制"]},
        {"canonical": "算法黑箱", "type": "THEORY", "variants": ["算法黑箱"]},
        {"canonical": "算法偏见", "type": "THEORY", "variants": ["算法偏见"]},
        {"canonical": "算法歧视", "type": "THEORY", "variants": ["算法歧视"]},
        {"canonical": "高校思想政治教育个性化实践", "type": "TOPIC",
         "variants": ["高校思想政治教育个性化实践",
                      "Personalized Practice in Ideological and Political Education"]},
        {"canonical": "学生思想监测", "type": "TOPIC",
         "variants": ["学生思想监测", "student ideological monitoring"]},
        {"canonical": "重点群体预警", "type": "TOPIC", "variants": ["重点群体预警"]},
        {"canonical": "数据安全与伦理规范", "type": "TOPIC",
         "variants": ["数据安全与伦理规范", "安全伦理规范"]},
    ],
}

# ============================== ner_relation gold ============================ #
# 实体 + 关系三元组。关系无映射表（关系是开放语义断言，非有限字典），仅用于 eval 测
# relation-level P/R/F1 + 找 LLM 漏例（含蓄关系）→ 补泛化规则兜底。
NER_RELATION_GOLD = {
    "ch3": {
        "entities": [
            {"canonical": "侯晓洁", "type": "PERSON",
             "variants": ["侯晓洁", "Hou Xiaojie"]},
            {"canonical": "四川传媒学院", "type": "ORGANIZATION",
             "variants": ["四川传媒学院", "Sichuan University of Media and Communications"]},
            {"canonical": "表演学院", "type": "ORGANIZATION",
             "variants": ["表演学院", "School of Performance"]},
            {"canonical": "大数据与 AI 画像", "type": "METHOD",
             "variants": ["大数据与 AI 画像", "big data and AI portrait technologies"]},
            {"canonical": "高校思想政治教育", "type": "TOPIC",
             "variants": ["高校思想政治教育", "思政教育"]},
        ],
        "relations": [
            {"head": "侯晓洁", "relation": "任职于", "tail": "四川传媒学院",
             "context": "侯晓洁(四川传媒学院 表演学院,成都 611745)"},
            {"head": "大数据与 AI 画像", "relation": "应用于", "tail": "高校思想政治教育",
             "context": "大数据与 AI 画像:高校思想政治教育"},
            {"head": "表演学院", "relation": "隶属", "tail": "四川传媒学院",
             "context": "四川传媒学院 表演学院"},
        ],
    },
}

# ============================== ner_domain gold =============================== #
# 需领域文档（医学/化工/物理），ch3 不适用；框架就绪，标注待领域数据
NER_DOMAIN_GOLD: dict = {}


GOLD_MAP = {
    "ner_general": NER_GENERAL_GOLD,
    "ner_research": NER_RESEARCH_GOLD,
    "ner_domain": NER_DOMAIN_GOLD,
    "ner_relation": NER_RELATION_GOLD,
}


def build(t: str) -> list:
    gold_dict = GOLD_MAP[t]
    out = []
    for doc_id, payload in gold_dict.items():
        text = _load_text(doc_id)
        if t == "ner_relation":
            entities = payload["entities"]
            relations = payload["relations"]
            # 断言实体变体 + 关系 head/tail/context 是原文子串
            for e in entities:
                for v in e["variants"]:
                    if v not in text:
                        raise AssertionError(f"[{t}] {doc_id} 实体变体不是原文子串: {v!r}")
            for r in relations:
                for k in ("context",):
                    if r.get(k) and r[k] not in text:
                        raise AssertionError(f"[{t}] {doc_id} 关系 {k} 不是原文子串: {r[k]!r}")
                # head/tail 须是某实体的 canonical
                names = {e["canonical"] for e in entities}
                if r["head"] not in names or r["tail"] not in names:
                    raise AssertionError(f"[{t}] {doc_id} 关系 head/tail 未在 entities 中: {r}")
            out.append({"doc_id": doc_id, "type": t,
                        "entities": entities, "relations": relations})
        else:
            for e in payload:
                for v in e["variants"]:
                    if v not in text:
                        raise AssertionError(f"[{t}] {doc_id} 变体不是原文子串: {v!r}")
            out.append({"doc_id": doc_id, "type": t, "entities": payload})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", required=True, choices=list(GOLD_MAP.keys()))
    args = ap.parse_args()
    out = build(args.type)
    path = DATA_DIR / f"{args.type}_gold.json"
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if args.type == "ner_relation":
        ne = sum(len(d["entities"]) for d in out)
        nr = sum(len(d["relations"]) for d in out)
        print(f"{args.type}: {len(out)} 篇 / {ne} 实体 / {nr} 关系 → {path}")
    else:
        n = sum(len(d["entities"]) for d in out)
        print(f"{args.type}: {len(out)} 篇 / {n} 实体 → {path}")


if __name__ == "__main__":
    main()
