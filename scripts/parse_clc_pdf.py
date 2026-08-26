"""解析完整中图分类法 PDF（zh_classify.pdf，1100页）→ clc_meta.json。

PDF 有两套表：简表（页~5-30，数字行无字母前缀）和详表（页~30-1100，全码如 TM713）。
详表是简表的超集且更细，本脚本只取**字母开头的全码行**（自动跳过简表数字行、目录、页眉页脚）。

输出条目 schema 与现有 clc_meta 一致：
  clc_code / clc_name / parent_code / level / full_path / path_codes / path_names / rag_text
父类关系由码本身的前缀层级推出（TM714.1 → TM714 → TM71 → TM7 → TM → T）。
"""
from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict

import pdfplumber
from config.settings import settings

PDF = str(settings.PROJECT_ROOT / "data" / "zh_classify.pdf")
OUT = str(settings.CLC_META_FULL)

# CLC 代码：1-2 字母 + 可选数字/点/+/斜杠段。如 A / A1 / A121 / B0-0 / TM7 / TM713 / TM714.1 / TN949.6+1 / R443+.6
CODE_RE = re.compile(r"^\[?([A-Z]{1,2}(?:[0-9]+(?:[.+\-/][0-9]+)*|[0-9A-Za-z]*))\]?\s+\S")
# 页眉页脚/噪声行
NOISE_RE = re.compile(r"^(-\s*\d+\s*-|中图法|目\s*录|中国图书分类法|http|.*\.{5,}.*)$")
# 纯字母大类行也算（A 马克思主义 / TQ 化学工业）——已被 CODE_RE 覆盖


def is_code_line(line: str):
    line = line.strip()
    if not line or NOISE_RE.match(line):
        return None
    if not CODE_RE.match(line):
        return None
    parts = line.split(None, 1)
    raw_code = parts[0].strip("[]")
    name = parts[1].strip() if len(parts) > 1 else ""
    if not name:
        return None
    return raw_code, name


def parent_of(code: str, all_codes: set):
    """按前缀层级找父码（最长存在前缀）。"""
    # 候选：去小数点末段，再逐字符去尾
    cands = []
    if "." in code:
        cands.append(code.rsplit(".", 1)[0])
    # 按 CLC 段切：字母段 + 数字段
    # 通用：逐字符去尾
    cur = code
    while cur:
        cur = cur[:-1]
        cands.append(cur)
    for c in cands:
        if c and c in all_codes and c != code:
            return c
    return None


def main():
    pdf = pdfplumber.open(PDF)
    raw = OrderedDict()  # code -> name (保留首次出现)
    for i, pg in enumerate(pdf.pages):
        t = pg.extract_text() or ""
        for line in t.split("\n"):
            r = is_code_line(line)
            if not r:
                continue
            code, name = r
            # 过滤明显非类目（名称全为数字/符号、或 code 异常长）
            if len(code) > 20:
                continue
            if code not in raw:
                raw[code] = name
            # 名称更长时更新（去重保留更完整名）
            elif len(name) > len(raw[code]):
                raw[code] = name
    print(f"提取到原始条目：{len(raw)}")

    all_codes = set(raw.keys())
    entries = []
    for code, name in raw.items():
        parent = parent_of(code, all_codes)
        entries.append({"clc_code": code, "clc_name": name, "parent_code": parent})
    # 排序：按 code 字典序（字母+数字），便于 path 构建
    entries.sort(key=lambda e: e["clc_code"])

    # 构建 code->entry 索引，补 level/full_path/path_codes/path_names/rag_text
    idx = {e["clc_code"]: e for e in entries}
    for e in entries:
        # level
        path_codes = []
        path_names = []
        cur = e["clc_code"]
        chain = []
        while cur and cur in idx:
            chain.append(cur)
            cur = idx[cur]["parent_code"]
        chain.reverse()
        e["level"] = len(chain)
        e["path_codes"] = chain
        e["path_names"] = [idx[c]["clc_name"] for c in chain]
        e["full_path"] = " > ".join(f"{c} {idx[c]['clc_name']}" for c in chain)
        e["rag_text"] = (
            f"分类号：{e['clc_code']}\n分类名称：{e['clc_name']}\n"
            f"上位分类号：{e['parent_code'] or '无'}\n分类路径：{e['full_path']}\n"
            f"路径分类号：{' / '.join(e['path_codes'])}\n"
            f"路径名称：{' / '.join(e['path_names'])}\n"
            f"检索文本：{e['clc_code']} {e['clc_name']} {e['full_path']} {e['clc_name']}"
        )
        e["id"] = entries.index(e)

    # 重排 id
    for i, e in enumerate(entries):
        e["id"] = i

    json.dump(entries, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"已写出：{OUT}  共 {len(entries)} 条")

    # 与旧库对比
    old = json.load(open(str(settings.CLC_RAG_DIR / "clc_meta.json"), encoding="utf-8"))
    old_codes = {e["clc_code"] for e in old}
    new_codes = all_codes
    print(f"旧库：{len(old_codes)}  新库：{len(new_codes)}")
    print(f"旧库中不在新库的（应尽少）：{len(old_codes - new_codes)}  例：{sorted(old_codes - new_codes)[:10]}")
    print(f"新库新增：{len(new_codes - old_codes)}")
    # 关键验证：TM7 子码
    tm7 = sorted([c for c in new_codes if c.startswith("TM7")])
    print(f"TM7 系列新库：{len(tm7)} 条  例：{tm7[:12]}")
    return entries


if __name__ == "__main__":
    main()
