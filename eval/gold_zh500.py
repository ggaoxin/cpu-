"""500篇中文摘要 gold 标注（人工逐篇阅读后标注，22个主题类簇）。

来源：data/datasets/chinese_abstracts.json 随机采样 500 篇（seed=42）。
标注方式：逐篇阅读摘要，按核心研究主题归类，保证跨篇标签一致。

类簇（22）：
  A高压直流输电 B配电网故障与保护 C配电网规划与韧性 D新能源发电与预测
  E储能系统 F综合能源系统 G电力市场与需求响应 H低碳电力与碳排
  I电力系统稳定与控制 J电网调度与优化 K电力设备与电能质量 L故障诊断与识别
  M旅游地理 N农业与粮食 O区域经济与产业 P城市与国土空间
  Q科技创新政策 R生态环境 S资源环境与减贫 T生命科学生物
  U海洋科学 V人文社会教育
"""
from __future__ import annotations
import json, random
from pathlib import Path

LABELS = {
    "A": "高压直流输电", "B": "配电网故障与保护", "C": "配电网规划与韧性",
    "D": "新能源发电与预测", "E": "储能系统", "F": "综合能源系统",
    "G": "电力市场与需求响应", "H": "低碳电力与碳排", "I": "电力系统稳定与控制",
    "J": "电网调度与优化", "K": "电力设备与电能质量", "L": "故障诊断与识别",
    "M": "旅游地理", "N": "农业与粮食", "O": "区域经济与产业",
    "P": "城市与国土空间", "Q": "科技创新政策", "R": "生态环境",
    "S": "资源环境与减贫", "T": "生命科学生物", "U": "海洋科学",
    "V": "人文社会教育",
}

# 逐篇标注，索引 i 对应 ZH_(i+1)，每行 50 篇
_LINES = [
    "RJKRGOEOLOFHJCMGNJMGIVSPPLRIMSVVORNNOKCQBHPKQACJRI",  # 0001-0050
    "AIRLMSQMSOBGNOQRSOPOOAQEKVMKDRKQVORVLEKINCOMQMAOQM",  # 0051-0100
    "OAROCOTRVQJCEOMPROJEQRPQHGNRPQODOOMHHOCKOKINFQUNIV",  # 0101-0150
    "LKOLIMOKOOMKTQMIOLCCGSITMOSBPVRSQOKCOLRINCHPOKKIBQ",  # 0151-0200
    "FOEOSQPMDHAFGIQQOFBIUGPAOPNPNKVDDTIDOSDHDKBPNOMQOI",  # 0201-0250
    "QQIOPKPVPJDGTCMPSSAMKESONJOVMSAAPNDKDOSRBKOCBKSKEJ",  # 0251-0300
    "NOBDEIKOJONSOGFNOIPQQMRDPKOIVOOVRLBOQDQQHINPMSNLDA",  # 0301-0350
    "VCCMBOLMQOGQRFOORMQOPVENUVOPOAABRNIKVNEJPGLPNTOGEU",  # 0351-0400
    "POONRSLBIMPPPONRCJESMOGOGBQIIBIOKVLOOPLPVOCVSMOOBO",  # 0401-0450
    "OKJQQVQGNRQBCMMMSCGIKCIKGMJGUNGVGNQNBKEMPFACBEBOSG",  # 0451-0500
]


def build() -> dict:
    seq = "".join(_LINES)
    assert len(seq) == 500, f"标注串长度 {len(seq)} != 500"
    data = json.load(open("data/datasets/chinese_abstracts.json", encoding="utf-8"))
    random.seed(42)
    sample = random.sample(data, 500)
    papers = []
    for i, d in enumerate(sample):
        tag = seq[i]
        papers.append({
            "document_id": f"ZH_{i+1:04d}",
            "abstract": d.get("ch_abstract", ""),
            "gold": LABELS.get(tag, "未分类"),
            "tag": tag,
        })
    from collections import Counter
    dist = Counter(p["gold"] for p in papers)
    return {
        "_desc": "500篇中文摘要人工gold标注，22主题类簇，逐篇阅读",
        "papers": papers,
        "n": len(papers),
        "n_clusters": len(dist),
        "distribution": dict(sorted(dist.items(), key=lambda x: -x[1])),
    }


if __name__ == "__main__":
    out = build()
    Path("eval/gold_zh500.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已生成 eval/gold_zh500.json  n={out['n']} 簇={out['n_clusters']}")
    print("分布:")
    for k, v in out["distribution"].items():
        print(f"  {k:12} {v}")
