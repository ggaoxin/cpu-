"""ac_domain 专业领域分类 gold 标准（Claude 自主判定，两层）。

读 professional_domain_classification_32x2_zh_simple.json（64篇，32领域×2），
对每篇产出：
  layer1: 32 个专业领域之一（用户划定的自定义分类体系）
  layer2: 基于 RAG(clc_meta_full) 的细粒度中图法分类号（resolve_code 校验存在）
输出：<data/datasets>/professional_domain_64_classification.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.rag.clc_retriever import clc_retriever
from config.settings import settings

PAPERS = str(settings.DATA_DIR / "professional_domain_classification_32x2_zh_simple.json")
OUT = str(settings.DATA_DIR / "professional_domain_64_classification.json")

# 32 个专业领域
DOMAINS = [
    "01 数学与计算科学", "02 力学与工程力学", "03 物理学与应用物理", "04 化学与化学科学",
    "05 天文学与空间科学", "06 地球科学与地质资源", "07 测绘遥感与地理信息", "08 气象海洋科学",
    "09 生物科学与生物技术", "10 医学与卫生健康", "11 药学与毒理学", "12 农业科学与农业工程",
    "13 林业畜牧兽医与水产", "14 材料科学与材料工程", "15 矿业与矿物加工", "16 石油与天然气工程",
    "17 冶金与金属加工", "18 机械工程与智能制造", "19 仪器仪表与计量检测", "20 能源与动力工程",
    "21 核科学与核工程", "22 电气工程与电力系统", "23 电子通信与半导体", "24 自动化与控制工程",
    "25 人工智能与计算机技术", "26 化学工程与过程工业", "27 轻工食品与纺织", "28 建筑与土木工程",
    "29 水利与水电工程", "30 交通运输工程", "31 航空航天工程", "32 环境与安全工程",
]

# sample_id(1..64) -> 细粒度 CLC 号（按内容判定，resolve_code 校验）
# 领域号 = ceil(id/2)
CLC = {
    1: "O241", 2: "O22",            # 01 数学：数值计算 / 运筹优化
    3: "O357", 4: "O322",           # 02 力学：渗流力学 / 非线性振动
    5: "O472", 6: "O436",           # 03 物理：固体物理(自旋) / 光学
    7: "O644", 8: "O621",           # 04 化学：光化学 / 无机配位
    9: "P154", 10: "P157",          # 05 天文：恒星行星 / 河外星系AGN
    11: "P319", 12: "P5",           # 06 地质：地热 / 地质学
    13: "P237", 14: "P228",         # 07 测绘：遥感 / 卫星大地测量
    15: "P458", 16: "P733",         # 08 气象海洋：降水 / 海洋水文
    17: "Q78", 18: "Q93",           # 09 生物：分子生物 / 微生物
    19: "R575", 20: "R68",          # 10 医学：肝疾病 / 骨科学
    21: "R943", 22: "R99",          # 11 药学毒理：药剂学 / 毒理学
    23: "S513", 24: "S22",          # 12 农业：禾本科作物 / 农业工程
    25: "S714", 26: "S96",          # 13 林业水产：森林土壤 / 水产养殖
    27: "TG13", 28: "TM615",        # 14 材料：合金学 / 太阳能电池
    29: "TD32", 30: "TD923",        # 15 矿业：金属矿开采 / 选矿浮选
    31: "TE37", 32: "TE88",         # 16 石油天然气：压裂 / 输气管道
    33: "TF777", 34: "TG45",        # 17 冶金：连铸 / 焊接
    35: "TG537", 36: "TH16",        # 18 机械：数控加工 / 机械制造
    37: "TH741", 38: "TP212",       # 19 仪器：光学仪器 / 传感器
    39: "TM911", 40: "TM73",        # 20 能源动力：燃料电池 / 电力系统运行
    41: "TL4", 42: "TL9",           # 21 核：反应堆 / 放射性废物
    43: "TM712", 44: "TM21",        # 22 电气：电力系统稳定 / 高电压绝缘
    45: "TN929", 46: "TN386",       # 23 电子通信：移动通信 / 半导体器件
    47: "TP13", 48: "TP24",         # 24 自动化：自适应控制 / 机器人
    49: "TP18", 50: "TP18",         # 25 人工智能：AI(RAG) / AI(联邦学习)
    51: "TQ03", 52: "TQ42",         # 26 化工：反应过程 / 催化剂
    53: "TS201", 54: "TS19",        # 27 轻工食品纺织：食品微生物 / 染整
    55: "TU37", 56: "TU47",         # 28 建筑土木：混凝土结构 / 土方基坑
    57: "TV62", 58: "TV7",          # 29 水利水电：水库调度 / 水电站
    59: "U49", 60: "U44",           # 30 交通：交通工程(自动驾驶) / 桥梁工程
    61: "V22", 62: "V47",           # 31 航空航天：飞行器结构 / 人造卫星
    63: "X70", 64: "X9",            # 32 环境安全：污水处理 / 安全工程
}


def main():
    papers = json.load(open(PAPERS, encoding="utf-8"))
    R = clc_retriever
    R._ensure_loaded()
    snaps = []
    out = []
    for i, p in enumerate(papers, 1):
        domain_idx = (i - 1) // 2  # 0..31
        domain = DOMAINS[domain_idx]
        code = CLC[i]
        entry = R.resolve_code(code)
        if entry is None:
            entry = R.get_by_code(code)
        if entry["clc_code"] != code:
            snaps.append((i, code, entry["clc_code"]))
            code = entry["clc_code"]
        out.append({
            "sample_id": i,
            "title": p["title"],
            "abstract": p["abstract"],
            "keywords": p["keywords"],
            "domain_code": f"{domain_idx+1:02d}",
            "domain_name": domain,
            "clc_classification": {
                "clc_code": entry["clc_code"],
                "clc_name": entry["clc_name"],
                "classification_path": entry["full_path"],
                "path_codes": entry["path_codes"],
                "path_names": entry["path_names"],
                "rag_entry_id": entry["id"],
            },
            "alignment_check": {"clc_code_exists_in_rag": True, "path_copied_from_rag": True},
        })
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"已写出 ac_domain gold：{OUT}  共 {len(out)} 条")
    # 领域分布
    from collections import Counter
    dc = Counter(e["domain_code"] for e in out)
    print(f"领域覆盖：{len(dc)} 个（每领域 {min(dc.values())}-{max(dc.values())} 篇）")
    if snaps:
        print("CLC 码吸附：")
        for s in snaps:
            print("  ", s)
    else:
        print("所有 CLC 码精确命中 RAG 知识库。")


if __name__ == "__main__":
    main()
