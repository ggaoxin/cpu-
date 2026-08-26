"""合并旧 CLC 知识库（12468，名称已校验）+ PDF 解析新库（38712，含 TM713 等细码）。

两库互补：旧库缺 TM7 下位类等细码，PDF 缺部分 F5/G3/A8 等码。取并集：
- 重复码：保留旧库的干净名称（PDF 有少量提取乱码），忽略新名；
- 仅 PDF 有的码：加入，过滤 187 条乱码名称（含 PUA/�/?）；
- 仅旧库有的码：保留（如 G301、F590.8）。
最后按完整码集重算 parent/level/full_path/path/rag_text，输出 clc_meta_full.json。
"""
from __future__ import annotations

import json
from config.settings import settings
from infrastructure.rag.clc_meta_builder import normalize_meta

OLD = str(settings.CLC_RAG_DIR / "clc_meta.json")
NEW = str(settings.CLC_META_FULL)  # PDF 解析结果，将被合并版覆盖
GOLD = str(settings.DATA_DIR / "random_50_chinese_papers_clc_classification_v2.json")


def is_garbage(name: str) -> bool:
    for ch in name:
        o = ord(ch)
        if 0xE000 <= o <= 0xF8FF:  # PUA
            return True
    return ("�" in name) or ("?" in name)


def main():
    old = json.load(open(OLD, encoding="utf-8"))
    new = json.load(open(NEW, encoding="utf-8"))

    merged: dict[str, str] = {}  # code -> name
    n_old = n_new_clean = n_dup = n_garbage = 0
    # 1) 旧库全量（名称可信）
    for e in old:
        if e["clc_code"] not in merged:
            merged[e["clc_code"]] = e["clc_name"]
            n_old += 1
    # 2) 新库补齐
    for e in new:
        c, nm = e["clc_code"], e["clc_name"]
        if c in merged:
            n_dup += 1  # 重复，保留旧名
            continue
        if is_garbage(nm):
            n_garbage += 1
            continue
        merged[c] = nm
        n_new_clean += 1

    print(f"旧库: {n_old}  新库干净补充: {n_new_clean}  重复(用旧名): {n_dup}  新库乱码丢弃: {n_garbage}")
    print(f"合并后总条目: {len(merged)}")

    codes = set(merged.keys())
    entries = [{"clc_code": c, "clc_name": merged[c]} for c in sorted(merged.keys())]
    normalize_meta(entries)  # 补全 parent_code/level/path_codes/path_names/full_path/rag_text/id

    json.dump(entries, open(NEW, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"已写出合并版：{NEW}  共 {len(entries)} 条")

    # 验证：gold 码全在 + TM713 在
    gold = json.load(open(GOLD, encoding="utf-8"))
    miss = []
    for g in gold:
        for c in [g["main_classification"]["clc_code"]] + [a["clc_code"] for a in g.get("auxiliary_classifications", [])]:
            if c not in codes:
                miss.append((g["sample_id"], c))
    print(f"gold 码不在合并库: {miss if miss else '无（全部命中）'}")
    print(f"TM713(电力系统短路) 在库: {'TM713' in codes}  名称={merged.get('TM713')}")
    print(f"TM7 系列条目数: {len([c for c in codes if c.startswith('TM7')])}")
    # 层级分布
    from collections import Counter
    lv = Counter(e["level"] for e in entries)
    print(f"层级分布: {dict(sorted(lv.items()))}")


if __name__ == "__main__":
    main()
