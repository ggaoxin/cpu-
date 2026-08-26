"""增量式 LLM 聚类 + 标签词汇传递。

每批≤50（LLM工作良好）。第一批建立标签词汇，后续批带上看已有标签列表，
优先复用已有标签、确属新主题才新增 → 标签跨批一致 → 按标签自然分组，无需跨桶合并。
顺序处理，词汇逐步积累。
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
n = len(papers)
glm = GLMClient()

SYSP_INCR = (
    "你是科技文献聚类专家。以下是若干篇文献的研究主题描述。请按【具体研究主题】聚类。\n\n"
    "要求：\n"
    "- 研究同一具体对象/问题的归同簇；同一主题的方法/角度不同仍归同簇\n"
    "- 不同具体主题分到不同簇（区域经济≠城市土地≠农业；配电网规划≠配电网故障保护）\n"
    "- 每簇给3-8字具体中文标签\n"
    "- 【优先复用已有标签】：若某篇与已有标签所指主题相同，就用那个标签，不要造同义新标签\n"
    "- 确属已有标签未覆盖的新主题，才新增标签\n"
    "- 只看本文核心主题\n"
    "只输出JSON：{{\"clusters\":[{{\"label\":\"标签\",\"indices\":[0,3]}}]}}\n"
    "indices是下方列表的0-based序号；每个序号必须且仅出现一次。"
)

BATCH = 45


def cluster_batch(batch_routes, vocab):
    listing = "\n".join(f"[{i}] {r[:150]}" for i, r in enumerate(batch_routes))
    vocab_str = "、".join(vocab) if vocab else "（暂无）"
    user = f"已有标签（优先复用）：{vocab_str}\n\n文献列表（共{len(batch_routes)}篇）：\n{listing}"
    try:
        out = glm.chat_json(SYSP_INCR, user, temperature=0.1, timeout=90.0, max_tokens=2000)
    except Exception as e:
        print(f"  批失败: {e}")
        return {}
    res = {}
    for cl in out.get("clusters", []):
        lbl = (cl.get("label") or "").strip() or "未分类"
        for idx in cl.get("indices", []):
            try:
                pos = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= pos < len(batch_routes):
                res[pos] = lbl
    return res


print(f"增量聚类 {n} 篇，批大小={BATCH}...")
t0 = time.time()
labels = ["未分类"] * n
vocab = []
nbatch = (n + BATCH - 1) // BATCH
for bi in range(nbatch):
    s = bi * BATCH
    e = min(s + BATCH, n)
    batch_routes = [routes[i] for i in range(s, e)]
    res = cluster_batch(batch_routes, vocab)
    # 更新标签 + 词汇
    new_labels = set()
    for pos, lbl in res.items():
        gi = s + pos
        labels[gi] = lbl
        new_labels.add(lbl)
    # 缺失的归未分类
    for pos in range(len(batch_routes)):
        if pos not in res:
            labels[s + pos] = "未分类"
    for lbl in new_labels:
        if lbl not in vocab and lbl != "未分类":
            vocab.append(lbl)
    print(f"  批{bi+1}/{nbatch} [{s}-{e}) 标签数={len(vocab)} ({time.time()-t0:.0f}s)")

print(f"\n词汇总数={len(vocab)}")


# === 标签层面合并：247个短标签 → 规范主题组 ===
SYSP_CONSOLIDATE = (
    "你是科技文献主题分析专家。下面是若干【主题标签】（来自分批聚类，存在同义/近义重复）。"
    "请把指【同一具体研究主题】的标签合并为一组，给一个3-8字规范名。\n"
    "- 只合并确属同一具体主题的（如 '区域经济差异'与'区域经济增长动力'与'区域经济空间格局'都研究区域经济→可合）\n"
    "- 相关但不同具体主题不要合（'配电网规划'≠'配电网故障保护'；'电力设备'≠'故障诊断'）\n"
    "- 保留细粒度，宁可多留组，不要并成大类\n"
    "输出JSON：{\"groups\":[{\"label\":\"规范名\",\"members\":[\"标签1\",\"标签2\"]}]}\n"
    "每个输入标签必须归且仅归一组。"
)
uniq_labels = sorted(set(labels) - {"未分类"})
listing = "\n".join(f"[{i}] {l}" for i, l in enumerate(uniq_labels))
print(f"标签合并：{len(uniq_labels)}个唯一标签...")
try:
    out = glm.chat_json(SYSP_CONSOLIDATE, f"标签列表：\n{listing}",
                        temperature=0.1, timeout=120.0, max_tokens=3000)
    label2canon = {}
    for g in out.get("groups", []):
        canon = (g.get("label") or "").strip() or "未分类"
        for m in g.get("members", []):
            label2canon[str(m).strip()] = canon
    canon_labels = [label2canon.get(l, l) for l in labels]
    print(f"合并后规范标签数={len(set(canon_labels))}")
except Exception as e:
    print(f"合并失败: {e}")
    canon_labels = labels


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
print(f"\n按标签分组(合并前): k={len(set(labels))} ARI={ari:.3f} NMI={nmi:.3f} "
      f"hom={hom:.3f} comp={comp:.3f} V={vm:.3f} pur={pur:.3f}  ({time.time()-t0:.0f}s)")

# 合并后评估
ari2 = adjusted_rand_score(gold, canon_labels)
nmi2 = normalized_mutual_info_score(gold, canon_labels)
hom2 = homogeneity_score(gold, canon_labels)
comp2 = completeness_score(gold, canon_labels)
vm2 = v_measure_score(gold, canon_labels)
pur2 = purity(gold, canon_labels)
print(f"按标签分组(合并后): k={len(set(canon_labels))} ARI={ari2:.3f} NMI={nmi2:.3f} "
      f"hom={hom2:.3f} comp={comp2:.3f} V={vm2:.3f} pur={pur2:.3f}")

print("\n标签分布(top30,合并后):")
for lbl, cnt in Counter(canon_labels).most_common(30):
    print(f"  {lbl:18} {cnt}")

print("\ngold→标签(合并后):")
g2a = {}
for p, a in zip(papers, canon_labels):
    g2a.setdefault(p["gold"], Counter())[a] += 1
for g in sorted(g2a, key=lambda x: -sum(g2a[x].values())):
    tops = g2a[g].most_common(3)
    tot = sum(g2a[g].values())
    print(f"  {g:14} → {', '.join(f'{k}({v})' for k,v in tops)}  ({100*tops[0][1]/tot:.0f}%)")
