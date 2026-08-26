"""500篇全量一次LLM聚类，强制细粒度目标。

之前500一次 k=6 塌掉，因旧prompt写死"3-8簇"。改强制"25-40个细主题簇"，
看全量视野(无分桶碎片)能否一次到位。若ARI高→分层不必要；若仍低→LLM在500规模注意力不行。
"""
from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             v_measure_score, homogeneity_score, completeness_score)
from infrastructure.llm.glm_client import GLMClient

gold_data = json.loads(Path("eval/gold_zh500.json").read_text(encoding="utf-8"))
papers = gold_data["papers"]
gold = [p["gold"] for p in papers]
doc_ids = [p["document_id"] for p in papers]
routes_by_id = json.loads(Path("/tmp/zh500_topic_routes.json").read_text(encoding="utf-8"))
routes = [routes_by_id[d] for d in doc_ids]
glm = GLMClient()

SYSP_FINE = (
    "你是科技文献聚类专家。以下是若干篇文献各自的研究主题描述。请按【具体研究主题】将它们聚成【30-45个细主题簇】。\n\n"
    "要求：\n"
    "- 研究同一具体对象/问题的归同簇（方法/角度不同算同簇）\n"
    "- 不同具体主题必须分到不同簇（区域经济≠城市土地≠农业≠旅游；电力设备≠故障诊断≠稳定控制）\n"
    "- 必须输出30-45个簇，不要合并成大类\n"
    "- 每簇给3-8字具体中文标签\n"
    "- 每篇归且仅归一簇\n"
    "只输出JSON：{\"clusters\":[{\"label\":\"标签\",\"document_ids\":[\"ZH_0001\",...]}]}"
)


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


for target_desc, sysp in [("强制30-45簇", SYSP_FINE)]:
    listing = "\n".join(f"[{did}] {r[:150]}" for did, r in zip(doc_ids, routes))
    print(f"{target_desc}: 输入{len(doc_ids)}篇...")
    t0 = time.time()
    try:
        out = glm.chat_json(sysp, f"文献列表（共{len(doc_ids)}篇）：\n{listing}",
                            temperature=0.2, timeout=180.0, max_tokens=6000)
        mp = {}
        for cl in out.get("clusters", []):
            lbl = (cl.get("label") or "").strip() or "未分类"
            for did in cl.get("document_ids", []):
                mp[str(did).strip()] = lbl
        algo = [mp.get(did, "未分类") for did in doc_ids]
        print(f"  k={len(set(algo))} ({time.time()-t0:.0f}s) ARI={adjusted_rand_score(gold,algo):.3f} "
              f"NMI={normalized_mutual_info_score(gold,algo):.3f} "
              f"hom={homogeneity_score(gold,algo):.3f} comp={completeness_score(gold,algo):.3f} "
              f"V={v_measure_score(gold,algo):.3f} pur={purity(gold,algo):.3f}")
        # 映射
        g2a = {}
        for p, a in zip(papers, algo):
            g2a.setdefault(p["gold"], Counter())[a] += 1
        for g in sorted(g2a, key=lambda x: -sum(g2a[x].values()))[:10]:
            tops = g2a[g].most_common(2)
            print(f"    {g:14} → {', '.join(f'{k}({v})' for k,v in tops)}")
    except Exception as e:
        print(f"  失败: {e}")
