"""放宽英文 rq gold：把"目标句"（we propose/study/present/develop/introduce...）也标为 RQ。

英文摘要常把"问题/缺口句"和"目标句"分写两句，原 gold 只标了 gap 句。
本脚本从摘要里自动抽取含目标动词的句子（verbatim，by construction），
作为额外 RQ 标注加入 gold，使评测口径同时接受 gap 句与目标句。
"""
import json
import re
from config.settings import settings

GOLD = str(settings.DATA_DIR / "rq_sample_72_gold.json")
OUT = str(settings.DATA_DIR / "rq_sample_72_gold_broad.json")

# 目标句动词线索（句中出现即视为目标句）
OBJ_CUES = [
    "we present", "we propose", "we study", "we develop", "we introduce",
    "we formulate", "we explore", "we build", "we train", "we model",
    "this paper proposes", "this paper presents", "this paper introduces",
    "in this paper, we", "in this work, we", "in this work we",
    "we propose", "we present a", "we introduce a",
]


def split_sentences_en(abs_):
    # 按 ". " 分句，保留缩写（粗略）
    parts = re.split(r'(?<=[.!?])\s+', abs_)
    return [p.strip() for p in parts if p.strip()]


def extract_phrase(sent):
    # 从目标句里抽核心短语：取 "we propose/present/study" 后到第一个逗号/句号的内容
    m = re.search(r'(?:we (?:present|propose|study|develop|introduce|explore|build|formulate|train|model|show|demonstrate|introduce|present a|propose a|study the|study how)[^\s]*\s+)([^,.;]+)', sent, re.I)
    if m:
        return m.group(1).strip()[:80]
    return ""


def main():
    gold = json.load(open(GOLD, encoding="utf-8"))
    n_added = 0
    for g in gold:
        if g["lang"] != "en":
            continue
        abs_ = g["abstract"]
        existing = {r["sentence"] for r in g["rq"]}
        for sent in split_sentences_en(abs_):
            low = sent.lower()
            if any(cue in low for cue in OBJ_CUES) and sent not in existing:
                phrase = extract_phrase(sent)
                # 短语须为句子子串（extract 已保证，兜底校验）
                if phrase and phrase not in sent:
                    phrase = ""
                g["rq"].append({"sentence": sent, "phrase": phrase, "source": "objective"})
                existing.add(sent)
                n_added += 1
    json.dump(gold, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    en = [g for g in gold if g["lang"] == "en"]
    print(f"已写出放宽版 gold：{OUT}")
    print(f"英文新增目标句 {n_added} 条")
    print(f"英文篇均 RQ 数：{sum(len(g['rq']) for g in en)/len(en):.2f}")
    for g in en[:5]:
        print(f"  [{g['id']}] RQ数={len(g['rq'])}: {[r['sentence'][:45] for r in g['rq']]}")


if __name__ == "__main__":
    main()
