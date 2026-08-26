"""作者（Claude）基于完整 CLC 知识库对 50 篇论文的自主分类判定（v3 标准）。

不参考旧 gold，凭论文内容 + 完整中图法知识选最贴切的真实分类号（优先细码）。
交叉学科按"学科边界"规则自动判定：T 取二级类、其余取一级字母，主辅不同边界=交叉。
所有码经 resolve_code 校验存在于 clc_meta_full（不存在则上溯吸附并标记）。
输出：random_50_chinese_papers_clc_classification_v3.json
"""
from __future__ import annotations

import json

from infrastructure.rag.clc_retriever import clc_retriever
from config.settings import settings

PAPERS = str(settings.DATA_DIR / "random_50_chinese_papers.json")
OUT = str(settings.DATA_DIR / "random_50_chinese_papers_clc_classification_v3.json")

# sample_id -> (main_code, [aux_codes], reason)
# 交叉学科由 main/aux 的学科边界自动判定，不手填
MY = {
    1:  ("F291.1", ["F124.7"], "研究核心是省域新型城镇化与共同富裕的耦合协调，主场景城市化，共同富裕(国民收入)为次要经济主题，同属经济不交叉。"),
    2:  ("F320.1", ["TP311.13"], "应用场景是现代农业现代化与高质量发展，大数据/数据要素是支撑性信息技术方法，主为农业经济、辅为数据处理，跨学科。"),
    3:  ("F290", ["G301"], "研究科技创新城市的功能内涵与评价体系，主体城市经济理论，科技创新研究(科学学)为辅助，跨学科。"),
    4:  ("TM713", [], "高比例分布式电源接入配电网的短路故障计算与分析，属电力系统短路，方法为内部计算手段，不交叉。"),
    5:  ("TM714", ["TP181"], "度冬度夏日最大负荷预测属负荷分析，聚类/SVR等机器学习为辅助方法，跨学科。"),
    6:  ("TM46", [], "双有源桥(DAB)直流-直流变换器的控制与优化，属变流器，优化为内部手段，不交叉。"),
    7:  ("F407.2", ["O225"], "风电数据在电力市场的定价属能源工业经济，联盟合作博弈为方法，跨学科。"),
    8:  ("TM13", [], "DS-LCC无线电能传输拓扑建模与参数优化以电路理论为核心，不交叉。"),
    9:  ("TM93", ["TP183"], "非侵入式负荷监测属电气测量，CNN-GRU深度神经网络为辅助方法，跨学科。"),
    10: ("F550", ["F740.2"], "海运服务贸易网络属水路运输经济，国际贸易世界市场为次要经济主题，同属经济不交叉。"),
    11: ("F590.8", ["F126.1"], "文旅消费水平属旅游市场，居民消费结构为次要经济主题，同属经济不交叉。"),
    12: ("F590.7", ["F323.8"], "乡村旅游对农户生计的影响，各类型旅游为主，农业收入分配为次要经济主题，同属经济不交叉。"),
    13: ("F590.7", ["K928.7"], "世界文化遗产旅游地创新发展，各类型旅游为主，名胜古迹资源为辅助，跨学科。"),
    14: ("F293.2", [], "城市化进程中城市土地利用结构效率，DEA为评价工具不单列，不交叉。"),
    15: ("TM732", [], "含分散式风电的配电网双层优化重构属电力系统运行，优化算法为内部手段，不交叉。"),
    16: ("G301", ["F061.5"], "都市圈协同创新演化综述，科学学为主，都市圈区域经济为应用空间，跨学科。"),
    17: ("TM713", [], "35kV配电线路相间短路故障测距，属电力系统短路，时域阻抗法为内部手段，不交叉。"),
    18: ("TU984", ["F713.581"], "传统商业街更新发展属城市规划，城市商业市场为辅助主题，跨学科。"),
    19: ("F719", ["D923.4"], "服务业内部结构优化属服务业经济，知识产权保护为辅助法律主题，跨学科。"),
    20: ("TM773", [], "远海风电交流汇集线路单端量保护原理属线路保护，信号处理为内部手段，不交叉。"),
    21: ("F301.0", ["D922.3"], "土地征收补偿属土地政策与土地经济，土地法为辅助法律主题，跨学科。"),
    22: ("TM614", [], "附加储能的直驱型风电机组构网型控制属风能发电，变换器储能控制同属电力工程，不交叉。"),
    23: ("TM774", [], "含新能源交流电网继电保护整定的故障计算属继电保护装置，计算方法为内部手段，不交叉。"),
    24: ("F592.7", ["O415.3"], "湖南旅游系统演化属地方旅游事业，自组织理论为辅助方法，跨学科。"),
    25: ("TM721.1", [], "柔性直流换流站向无源交流线路供电的电压控制属直流制输电，换流器控制同属输电系统，不交叉。"),
    26: ("F291.1", [], "环鄱阳湖城市群城市规模结构演变属城市化，分形为分析方法不单列，不交叉。"),
    27: ("F207", ["TU98"], "省级区域规划实施评估属区域经济管理，区域/城乡规划为辅助，跨学科。"),
    28: ("K928.7", ["F224.5"], "遗产资源价值评价属名胜古迹，意愿调查法/费用效益分析为辅助方法，跨学科。"),
    29: ("TM5", ["O511"], "新型超导直流故障限流器属电器，超导电性为辅助物理学科，跨学科。"),
    30: ("TP18", ["G301"], "AI开源与闭源技术模式探讨属人工智能理论，科技创新研究为辅助，跨学科。"),
    31: ("F323.1", ["F061.5"], "青藏农牧企业区位与布局属农业区域规划，区域经济分析为次要经济主题，同属经济不交叉。"),
    32: ("TM924", [], "热泵温控负荷可行域聚合属电热，虚拟电池/数学聚合为内部方法，不交叉。"),
    33: ("F291.1", ["X22"], "城市化与生态环境协调发展属城市化，环境与发展为辅助环境学科，跨学科。"),
    34: ("F290", ["C912.81"], "基于QQ群的东北城市联系与层级属城市经济理论，城市社会学为辅助，跨学科。"),
    35: ("TM721.1", [], "中频分布式远海风电直流输电系统属直流制输电，换流器为系统核心设备不另列，不交叉。"),
    36: ("F323.8", [], "武陵山片区农民收入增长及县际差异属农业收入与分配，偏离份额法为内部方法，不交叉。"),
    37: ("TM3", [], "调相机失磁保护属电机，谐波检测为内部保护手段，不交叉。"),
    38: ("F061.5", [], "长三角城市群协同发展空间格局属区域经济学，不交叉。"),
    39: ("F061.5", ["X22"], "黄河上游数字经济与绿色发展耦合属区域经济，环境与发展为辅助，跨学科。"),
    40: ("TM734", ["F407.2"], "区域电网统一调频控制属电力系统调度自动化，调频辅助服务市场为辅助能源经济主题，跨学科。"),
    41: ("TM721.1", [], "MMC-HVDC输电系统阻抗建模与谐振机理属直流制输电，分析为内部手段，不交叉。"),
    42: ("TM93", ["TP181"], "智能变电站交流采样异常识别属电气测量，DBSCAN聚类为辅助机器学习方法，跨学科。"),
    43: ("F290", ["X22"], "西部河谷城市空间结构对碳排放的影响属城市经济理论，环境与发展为辅助，跨学科。"),
    44: ("X38", ["F403.3"], "生态工业园区属环境与清洁生产，工业生产布局为辅助，跨学科。"),
    45: ("TG13", [], "非晶合金材料的发展与科学问题属合金学，不交叉。"),
    46: ("TM732", [], "直流微电网多源并联均流控制属电力系统运行，控制为内部手段，不交叉。"),
    47: ("G316", [], "中国科技工作者70年贡献属科学工作者，不交叉。"),
    48: ("TM713", ["TP183"], "配电网故障行波波头标定属电力系统短路，CNN目标检测为辅助方法，跨学科。"),
    49: ("TM732", ["O225"], "微电网主动能量管理优化属电力系统运行，势博弈/CVaR为辅助数学方法，跨学科。"),
    50: ("TM732", ["X22"], "源网荷储协调的配电网低碳经济运行属电力系统运行，环境与低碳发展为辅助，跨学科。"),
}


def discipline(code: str) -> str:
    code = (code or "").strip()
    if not code:
        return ""
    if code[0] == "T":
        return code[:2]
    return code[:1]


def main():
    papers = json.load(open(PAPERS, encoding="utf-8"))
    R = clc_retriever
    R._ensure_loaded()
    snaps = []
    out = []
    for p in papers:
        sid = p.get("sample_id") or len(out) + 1
        # papers 文件无 sample_id，按顺序 1..50
        sid = len(out) + 1
        main_code, aux_codes, reason = MY[sid]
        # 校验码存在
        me = R.resolve_code(main_code)
        if me is None:
            me = R.get_by_code(main_code)
        if me["clc_code"] != main_code:
            snaps.append((sid, "main", main_code, me["clc_code"]))
            main_code = me["clc_code"]
        aux_entries = []
        for ac in aux_codes[:1]:
            ae = R.resolve_code(ac)
            if ae is None:
                snaps.append((sid, "aux", ac, None))
                continue
            if ae["clc_code"] != ac:
                snaps.append((sid, "aux", ac, ae["clc_code"]))
            aux_entries.append(ae)
        # 交叉学科：自动按学科边界
        is_inter = bool(aux_entries) and discipline(aux_entries[0]["clc_code"]) != discipline(main_code)
        out.append({
            "sample_id": sid,
            "ch_name": p["ch_name"],
            "ch_abstract": p["ch_abstract"],
            "keywords": p["keywords"],
            "main_classification": _obj(me, R),
            "auxiliary_classifications": [_obj(ae, R) for ae in aux_entries],
            "is_interdisciplinary": is_inter,
            "selection_reason": reason,
            "alignment_check": {
                "all_codes_exist_in_clc_meta": True,
                "paths_copied_from_clc_meta": True,
                "path_not_generated_by_model": True,
            },
            "interdisciplinary_basis": {
                "main_discipline": discipline(main_code),
                "aux_discipline": discipline(aux_entries[0]["clc_code"]) if aux_entries else None,
            },
        })

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    n_inter = sum(1 for e in out if e["is_interdisciplinary"])
    print(f"已写出 v3 标准：{OUT}  共 {len(out)} 条  交叉学科 {n_inter}")
    if snaps:
        print("以下码不在库，已上溯吸附：")
        for s in snaps:
            print("  ", s)
    else:
        print("所有码均精确命中知识库（无吸附）。")


def _obj(entry, R):
    return {
        "clc_code": entry["clc_code"],
        "clc_name": entry["clc_name"],
        "classification_path": entry["full_path"],
        "path_codes": entry["path_codes"],
        "path_names": entry["path_names"],
        "rag_entry_id": entry["id"],
    }


if __name__ == "__main__":
    main()
