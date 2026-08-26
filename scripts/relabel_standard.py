"""按"学科边界"准则重新标注 ac_zh 的 50 篇标准结果（v2）。

准则（详见 docs/HANDOFF.md 与 ac_zh.yaml）：
  1. 主分类 = 应用场景（沿用 gold 的 main，已逐篇核对）。
  2. 辅助分类号 = 有分量的次要主题（方法/技术或并列应用主题），0-1 个（沿用 gold）。
  3. is_interdisciplinary = 辅助号与主号分属不同"学科边界"。
     - T（工业技术）是人为聚合大类，其下二级类（TM/TP/TQ/TU/TD…）为学科边界；
     - 其余大类（A-S, X, Z）以一级字母为学科边界。
     同学科边界的次要主题仍给辅助号，但 is_interdisciplinary=false。

输出：<data/datasets>/random_50_chinese_papers_clc_classification_v2.json
"""
from __future__ import annotations

import json
from config.settings import settings

GOLD = str(settings.DATA_DIR / "random_50_chinese_papers_clc_classification.json")
OUT = str(settings.DATA_DIR / "random_50_chinese_papers_clc_classification_v2.json")


def discipline(code: str) -> str:
    """学科边界：T 大类取前两字符（TM/TP/TQ…），其余取首字母。"""
    code = (code or "").strip()
    if not code:
        return ""
    if code[0] == "T":
        return code[:2]
    return code[:1]


def main():
    gold = json.load(open(GOLD, encoding="utf-8"))
    flips = []
    n_inter = 0
    for g in gold:
        main_code = g["main_classification"]["clc_code"]
        aux = g.get("auxiliary_classifications", [])
        old = g["is_interdisciplinary"]
        new = bool(aux) and discipline(aux[0]["clc_code"]) != discipline(main_code)
        g["is_interdisciplinary"] = new
        if new:
            n_inter += 1
        if old != new:
            flips.append({
                "sample_id": g["sample_id"],
                "main": main_code,
                "aux": [a["clc_code"] for a in aux],
                "old": old, "new": new,
                "disc_main": discipline(main_code),
                "disc_aux": discipline(aux[0]["clc_code"]) if aux else "",
            })
        # 标注判定依据，便于复核
        g["interdisciplinary_basis"] = {
            "main_discipline": discipline(main_code),
            "aux_discipline": discipline(aux[0]["clc_code"]) if aux else None,
            "rule": "T大类取二级类(TM/TP/..)，其余取一级字母；不同学科边界=交叉",
        }

    json.dump(gold, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"已写出：{OUT}")
    print(f"交叉学科数：{n_inter}/{len(gold)}  （gold 原 30）")
    print(f"翻转 {len(flips)} 条（True→False 的同大学科双主题）：")
    for f in flips:
        print(f"  id={f['sample_id']:>2}  main={f['main']} aux={f['aux']}  "
              f"{f['disc_main']}=={f['disc_aux']}  {f['old']}→{f['new']}")


if __name__ == "__main__":
    main()
