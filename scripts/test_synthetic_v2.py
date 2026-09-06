#!/usr/bin/env python3
"""合成测试：构造符合真实用户形态的文献集（主题群 × 表述各异），验证 v2 双轴聚类。

技术轴集（20 篇 = 4 个方法群 × 5 篇）：群内方法同类、应用对象各不相同
  ——检验：方法句向量能否把"用同类方法做不同事"的文献聚到一起
场景轴集（20 篇 = 4 个场景群 × 5 篇）：群内场景同类、方法各不相同
  ——检验：背景+目的句向量能否把"围绕同一问题的不同方法"聚到一起
流程：GLM 生成合成摘要（真实语步结构）→ 生产语步引擎提取 → 双轴向量聚类 → 对照设计分组。
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TECH_GROUPS = {
    "YOLO目标检测": ["钢筋缺陷检测", "肺结节影像筛查", "工地安全帽监测", "农作物病虫害识别", "森林火焰预警"],
    "WGCNA基因网络分析": ["糖尿病肾病标志物", "肺癌预后基因", "结直肠癌分型", "阿尔茨海默病通路", "类风湿关节炎靶点"],
    "有限元结构仿真": ["桥梁振动响应", "芯片散热分析", "髋关节假体应力", "车身碰撞吸能", "反应堆压力容器疲劳"],
    "知识图谱构建": ["中医方剂知识组织", "企业风险关联挖掘", "农产品溯源关系", "军事装备体系建模", "古籍人物关系抽取"],
}
SCENE_GROUPS = {
    "糖尿病诊疗": ["WGCNA筛选标志基因", "深度学习视网膜筛查", "胰岛素给药算法", "并发症护理方案", "流行病学风险模型"],
    "混凝土结构耐久": ["机器学习强度预测", "超声波损伤检测", "碳化深度回归分析", "掺合料配比优化", "裂缝图像识别"],
    "移动机器人导航": ["强化学习路径规划", "视觉SLAM建图", "多机协同避障", "动态障碍物预测", "语义地图匹配"],
    "空气污染治理": ["深度学习PM2.5预测", "传感器网络监测", "排放源反演模型", "催化剂脱硝实验", "健康暴露评估"],
}


def generate_docs(client, groups, axis):
    """GLM 按主题群生成合成摘要（每篇含背景/目的/方法的真实语步结构）。"""
    spec = []
    for group, subs in groups.items():
        for sub in subs:
            spec.append((group, sub))
    system = (
        f"你是科技文献摘要写作专家。针对给定的{'研究方法+应用对象' if axis == 'tech' else '应用场景+研究方法'}，"
        "写一段 180-240 字的中文摘要，必须包含清晰的三类句子：研究背景句（领域现状/问题）、"
        "研究目的句（本文要做什么）、研究方法句（采用什么数据/模型/算法/手段，方法句要具体写出方法名）。"
        "表述自然多样，不要模板化。只输出JSON："
        '{"docs":[{"group":"主题群名","sub":"子题","abstract":"摘要全文"},...]}'
    )
    lines = [f"{i + 1}. 主题群「{g}」子题「{s}」" for i, (g, s) in enumerate(spec)]
    raw = client.chat_json(system, "\n".join(lines), temperature=0.3, timeout=180.0, max_tokens=6000)
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    return [d for d in (raw.get("docs") or []) if isinstance(d, dict) and d.get("abstract")]


def run_axis(client, encoder, docs, groups, axis_name, sent_kind):
    from training.move_classifier import classify_full
    from training.rule_lib import RuleLib
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import adjusted_rand_score

    rule_lib = RuleLib.load(ROOT / "rules/move_recognition/mr_zh_abstract.yaml")
    gold, method_sents, scene_sents = [], [], []
    for d in docs:
        try:
            res = classify_full(str(d["abstract"]), rule_lib, do_review=False)
            pairs = [(s.get("text") or "", s.get("llm_label") or "") for s in (res.get("evidence") or [])]
        except Exception:  # noqa: BLE001
            pairs = []
        method_sents.append([s for s, mv in pairs if mv == "研究方法"] or [str(d["abstract"])[:60]])
        scene_sents.append([s for s, mv in pairs if mv in ("研究背景", "研究目的")] or [str(d["abstract"])[:60]])
        gold.append(d["group"])
    k = len(set(gold))

    vecs = np.asarray([
        (lambda v: v / max(np.linalg.norm(v), 1e-9))(
            np.asarray(encoder.encode(s)).mean(axis=0))
        for s in (method_sents if sent_kind == "method" else scene_sents)])
    labels = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(vecs)

    print(f"\n===== {axis_name}（{sent_kind}句向量，{len(docs)} 篇，设计 {k} 群）=====")
    ari = adjusted_rand_score(gold, labels)
    print(f"ARI = {ari:.3f}")
    clusters = {}
    for d, lab in zip(docs, labels):
        clusters.setdefault(int(lab), []).append(f"{d['group'][:6]}·{d['sub'][:10]}")
    for lab in sorted(clusters):
        print(f"  簇{lab + 1}: {clusters[lab]}")
    return ari


def main():
    from infrastructure.llm.glm_client import glm_client
    from infrastructure.rag.m3_encoder import m3_encoder

    print("生成技术轴测试集（4 方法群 × 5 篇，群内应用对象各不相同）...")
    tech_docs = generate_docs(glm_client, TECH_GROUPS, "tech")
    print(f"生成 {len(tech_docs)} 篇")
    print("生成场景轴测试集（4 场景群 × 5 篇，群内方法各不相同）...")
    scene_docs = generate_docs(glm_client, SCENE_GROUPS, "scene")
    print(f"生成 {len(scene_docs)} 篇")
    Path("/tmp/synthetic_docs.json").write_text(
        json.dumps({"tech": tech_docs, "scene": scene_docs}, ensure_ascii=False, indent=1), encoding="utf-8")

    # 打印样例（人工核对合成质量）
    if tech_docs:
        print("\n样例[0]:", tech_docs[0]["group"], "|", str(tech_docs[0]["abstract"])[:100])
    if scene_docs:
        print("样例[0]:", scene_docs[0]["group"], "|", str(scene_docs[0]["abstract"])[:100])

    ari_t = run_axis(glm_client, m3_encoder, tech_docs, TECH_GROUPS, "技术轴测试", "method")
    ari_s = run_axis(glm_client, m3_encoder, scene_docs, SCENE_GROUPS, "场景轴测试", "scene")
    print(f"\n总结: 技术轴 ARI={ari_t:.3f} | 场景轴 ARI={ari_s:.3f}（合成集已存 /tmp/synthetic_docs.json）")


if __name__ == "__main__":
    main()
