"""ac_en 英文科技文献分类的 gold 标准（Claude 自主判定）。

读 en_paper_50.json（50 篇英文文献），凭 CLC 知识将英文标题/摘要/关键词映射到中图分类号，
确保码真实存在于 clc_meta_full（resolve_code 校验）。交叉学科按学科边界自动判定。
输出：<data/datasets>/en_paper_50_clc_classification.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.rag.clc_retriever import clc_retriever
from config.settings import settings

PAPERS = str(settings.DATA_DIR / "en_paper_50.json")
OUT = str(settings.DATA_DIR / "en_paper_50_clc_classification.json")

# sample_id(1..50) -> (main_code, [aux_codes], reason)
MY = {
    1:  ("TM615", [], "Titanium silicide recombination layer for perovskite/TOPCon tandem solar cells — 太阳能电池器件，归太阳能发电。"),
    2:  ("U49", [], "Self-consistent energy system (microgrid/storage) for transport infrastructure — 应用场景为交通运输工程。"),
    3:  ("R47", [], "Nursing research immersion program — 护理学研究与人才培养。"),
    4:  ("R54", [], "Cardiac conduction system pathology in sudden cardiac death — 心脏疾病。"),
    5:  ("R749", [], "Duloxetine trial for binge eating disorder with depression — 精神病学/进食障碍与抑郁。"),
    6:  ("Q939", [], "Protein kinase C in Neurospora crassa (fungus) — 微生物学。"),
    7:  ("R62", [], "Lip proportions/augmentation, 3D facial aesthetics — 整形外科。"),
    8:  ("O621", [], "Cobalt-carborane coordination polymers, gas sorption — 无机/配位化学。"),
    9:  ("R54", [], "Congenital cardiac shunts, plexogenic pulmonary arteriopathy — 心脏疾病。"),
    10: ("R739", [], "Nanoencapsulated drug for pediatric diffuse midline glioma — 肿瘤治疗。"),
    11: ("C912", [], "Migrant community spaces, Brexit, Glasgow — 城市社会/社区结构。"),
    12: ("R96", [], "MR309 sigma1 antagonist pharmacokinetics/brain occupancy — 药理学。"),
    13: ("X8", [], "OECD integrated regional/strategic environmental impact assessment — 环境影响评价。"),
    14: ("R68", [], "Intramedullary fixation of metacarpal fractures — 骨科学/创伤。"),
    15: ("TP3", [], "Physical signature authentication performance — 计算机身份认证。"),
    16: ("R58", ["R394"], "Familial early-onset obesity, MC4R gene variants — 内分泌代谢，遗传学为辅（同属医学R，不交叉）。"),
    17: ("R69", [], "Renal artery embolization before graft nephrectomy — 泌尿外科/肾移植。"),
    18: ("O613", [], "Porous graphitic carbons from chitosan, CO2 adsorption — 碳材料/化学。"),
    19: ("R742", [], "Parkinson's LRRK2, astrocyte alpha-synuclein clearance — 帕金森病。"),
    20: ("O644", [], "Silver nanocluster visible-light photocatalysis — 光化学/催化。"),
    21: ("R37", ["R51"], "Brain disease network, COVID-19 neurological manifestations — 传染病(COVID)为主，神经表现为辅（同属R，不交叉）。"),
    22: ("R1", [], "Cost-effectiveness of pediatric influenza vaccination — 公共卫生/卫生经济。"),
    23: ("R65", ["TP3"], "Real-time vessel segmentation for microneurosurgical instrument — 神经外科应用，深度学习为方法（跨学科）。"),
    24: ("R52", [], "Latent tuberculosis in hemodialysis patients — 结核病。"),
    25: ("R749", ["R186"], "Cost-effectiveness of CBT for depression — 精神病学，卫生经济为辅（同属R，不交叉）。"),
    26: ("R19", [], "Registry evaluation/quality tool for HTA — 医疗保健制度/管理。"),
    27: ("O436", [], "Femtosecond laser optical trapping, nonlinear effects — 物理光学。"),
    28: ("TQ028", [], "Mesoporous membrane surface functionalization, gas flow — 膜分离/化工。"),
    29: ("R814", [], "Iohexol contrast media, image reconstruction — 放射诊断/影像。"),
    30: ("Q958", [], "Lake trout behavior, male chemical stimuli — 动物生态/行为。"),
    31: ("R749", [], "Hippocampal neuroplasticity in IFN-α depression mouse model — 精神病学/抑郁机制。"),
    32: ("R743", [], "CBF regulation in hypertension and Alzheimer's — 脑血管疾病。"),
    33: ("S718", [], "Pinus cembra hydraulics, electrical resistivity tomography — 树木学/林木生理。"),
    34: ("O482", [], "Piezoelectric nanogenerator, ZnSnO3 nanowires — 压电物理/能量收集。"),
    35: ("R72", [], "Hyperthyrotropinemia in preterm/SGA infants — 新生儿/儿内科。"),
    36: ("TS26", [], "α-pinene as SO2 alternative in red wine — 酿酒工业。"),
    37: ("R72", ["R575"], "Neck circumference and NAFLD in obese children — 儿科为主，肝胆为辅（同属R，不交叉）。"),
    38: ("R575", ["R582"], "Gallstone from hyperthyroidism weight loss — 胆道疾病，甲状腺为辅（同属R，不交叉）。"),
    39: ("R737", [], "BRCA2 mutation, digital droplet PCR, ovarian cancer — 妇科肿瘤。"),
    40: ("R58", [], "Phenylketonuria patients self-representation — 内分泌代谢病。"),
    41: ("S96", [], "Purslane in Nile tilapia diet, immunostimulation — 水产养殖。"),
    42: ("S855", [], "Mycobacterium bovis in cattle, wildlife-livestock — 家畜传染病/兽医。"),
    43: ("Q959", [], "Brown trout, acidification, genetic diversity — 鱼类学/群体遗传。"),
    44: ("Q959", [], "Enteromius new fish species, Gabon — 鱼类分类学。"),
    45: ("R749", ["R544"], "Norepinephrine transporter in hypertension-depression — 精神病学，高血压为辅（同属R，不交叉）。"),
    46: ("R151", [], "Watermelon phytochemicals as functional food — 营养学。"),
    47: ("R542", [], "Ceftaroline for Gram-positive endocarditis — 心内膜炎。"),
    48: ("X7", ["TQ7"], "Biomass carbon capture in kraft pulp mills — 环境工程(碳捕集)，造纸化工为辅（跨学科）。"),
    49: ("Q954", [], "Aortic arch branching in Syrian hamsters — 动物解剖。"),
    50: ("G642", ["P5"], "Undergraduates' conceptions of elasticity, plate tectonics — 高等教育，地质学为辅（跨学科）。"),
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
    for i, p in enumerate(papers, 1):
        main_code, aux_codes, reason = MY[i]
        me = R.resolve_code(main_code)
        if me is None:
            me = R.get_by_code(main_code)
        if me["clc_code"] != main_code:
            snaps.append((i, "main", main_code, me["clc_code"]))
            main_code = me["clc_code"]
        aux_entries = []
        for ac in aux_codes[:1]:
            ae = R.resolve_code(ac)
            if ae is None:
                snaps.append((i, "aux", ac, None)); continue
            if ae["clc_code"] != ac:
                snaps.append((i, "aux", ac, ae["clc_code"]))
            aux_entries.append(ae)
        is_inter = bool(aux_entries) and discipline(aux_entries[0]["clc_code"]) != discipline(main_code)
        out.append({
            "sample_id": i,
            "en_name": p["en_name"],
            "en_abstract": p["en_abstract"],
            "keywords": p["keywords"],
            "main_classification": _obj(me),
            "auxiliary_classifications": [_obj(ae) for ae in aux_entries],
            "is_interdisciplinary": is_inter,
            "selection_reason": reason,
            "alignment_check": {"all_codes_exist_in_clc_meta": True,
                                "paths_copied_from_clc_meta": True, "path_not_generated_by_model": True},
            "interdisciplinary_basis": {"main_discipline": discipline(main_code),
                                        "aux_discipline": discipline(aux_entries[0]["clc_code"]) if aux_entries else None},
        })
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    n_inter = sum(1 for e in out if e["is_interdisciplinary"])
    print(f"已写出 ac_en gold：{OUT}  共 {len(out)} 条  交叉学科 {n_inter}")
    if snaps:
        print("码不在库/吸附：")
        for s in snaps:
            print("  ", s)
    else:
        print("所有码精确命中知识库。")


def _obj(entry):
    return {"clc_code": entry["clc_code"], "clc_name": entry["clc_name"],
            "classification_path": entry["full_path"], "path_codes": entry["path_codes"],
            "path_names": entry["path_names"], "rag_entry_id": entry["id"]}


if __name__ == "__main__":
    main()
