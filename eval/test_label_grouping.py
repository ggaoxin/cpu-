"""LLM单篇打主题标签 → 按标签分组。

绕开 bge（它分不开中文主题）。每篇 LLM 独立打一个具体主题标签（500次并发），
按标签精确匹配分组。若标签一致性好 → ARI 高，说明 LLM 标签可替代 bge 做第一阶段聚类。
"""
from __future__ import annotations
import json, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
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
n = len(papers)
glm = GLMClient()

SYSP_LABEL = (
    "你是科技文献主题分析专家。阅读下面这篇文献的研究主题描述，给它一个【具体研究主题标签】。\n"
    "要求：\n"
    "- 3-8字中文，反映核心研究对象/问题（如 配电网故障定位/区域经济空间格局/旅游客流/储能系统控制/高压直流换相失败）\n"
    "- 用通用规范表述，便于同类文献撞到同一标签\n"
    "- 不要带'研究''分析'等泛词\n"
    "只输出JSON：{\"label\":\"标签\"}"
)


def label_one(i):
    try:
        out = glm.chat_json(SYSP_LABEL, f"研究主题：{routes[i][:400]}",
                            temperature=0.0, timeout=30.0, max_tokens=80)
        return i, (out.get("label") or "").strip()
    except Exception:
        return i, ""


print(f"单篇打标签 {n} 篇...")
t0 = time.time()
labels = [""] * n
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(label_one, i) for i in range(n)]
    done = 0
    for fut in as_completed(futs):
        i, lbl = fut.result()
        labels[i] = lbl
        done += 1
        if done % 100 == 0:
            print(f"  {done}/{n} ({time.time()-t0:.0f}s)")
print(f"完成 {time.time()-t0:.0f}s，去重标签数={len(set(labels))}")


def purity(gold, algo):
    cl = {}
    for g, a in zip(gold, algo):
        cl.setdefault(a, []).append(g)
    return sum(max(Counter(v).values()) for v in cl.values()) / len(gold)


ari = adjusted_rand_score(gold, labels)
nmi = normalized_mutual_info_score(gold, labels)
hom = homogeneity_score(gold, labels)
comp = completeness_score(gold, labels)
vm = v_measure_score(gold, labels)
pur = purity(gold, labels)
print(f"\n按标签直接分组: k={len(set(labels))} ARI={ari:.3f} NMI={nmi:.3f} "
      f"hom={hom:.3f} comp={comp:.3f} V={vm:.3f} pur={pur:.3f}")

print("\n标签分布(top30):")
for lbl, cnt in Counter(labels).most_common(30):
    print(f"  {lbl:16} {cnt}")

print("\ngold→标签:")
g2a = {}
for p, a in zip(papers, labels):
    g2a.setdefault(p["gold"], Counter())[a] += 1
for g in sorted(g2a, key=lambda x: -sum(g2a[x].values()))[:12]:
    tops = g2a[g].most_common(3)
    print(f"  {g:14} → {', '.join(f'{k}({v})' for k,v in tops)}")
