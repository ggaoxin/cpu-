"""高质量 gold 标注生成器：LLM 多轮独立标注 + 一致性定置信度。

思路（用户提出）：手动标 gold 易错（5.pdf 就标错过），改用 GLM 独立读全文给主题
标签，跑 N 轮带温度扰动；同一篇 N 轮标签一致→高置信 gold，不一致→ambiguous 剔除。
gold 独立于算法2，可复现，带置信度。

用法:
    python eval/gold_gen.py [--rounds 5] [--papers 1,2,4,5,6,7,8,9,10,11,12,14]
    → 生成 eval/gold_12_consensus.json
"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from infrastructure.document_parser.mineru_reader import process_to_text, _cache_get
from infrastructure.llm.glm_client import GLMClient

# 论文 PDF 编号（请求 texts 顺序）
DEFAULT_PAPERS = [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14]
PAPERS_DIR = "/root/autodl-tmp/data/papers"

SYSP = (
    "你是科技文献主题分类专家。阅读给定文献全文，判断其核心技术路线主题，"
    "给出一个 3-8 字的中文主题标签。\n\n"
    "要求：\n"
    "- 标签须具体反映核心技术方法/任务，例如：强化学习、对比学习、实体检索、"
    "合成数据、推荐系统、视觉定位、知识蒸馏、分布表征、推理、材料科学\n"
    "- 禁止泛词：研究/方法/模型/分析/基于/深度学习/机器学习/人工智能/神经网络\n"
    "- 只看本文核心技术，不看 related work 里提的其他方法\n"
    "只输出JSON：{\"topic\":\"主题标签\"}"
)

# 近义归一化（合并同类变体）
_SYNONYMS = [
    ("强化学习", ["强化学习", "rl", "策略梯度", "强化", "奖励模型", "人类反馈强化学习"]),
    ("对比学习", ["对比学习", "对比", "对比聚类", "对比训练"]),
    ("实体检索", ["实体检索", "自回归检索", "检索增强", "检索增强生成"]),
    ("合成数据", ["合成数据", "数据合成", "合成数据生成", "数据生成"]),
    ("知识蒸馏", ["知识蒸馏", "蒸馏", "自蒸馏"]),
    ("分布表征", ["分布表征", "分布", "表征学习", "表征"]),
    ("视觉定位", ["视觉定位", "视觉grounding", "视觉指代"]),
]


def _normalize(label: str) -> str:
    l = (label or "").strip().lower()
    for canon, variants in _SYNONYMS:
        if l in [v.lower() for v in variants]:
            return canon
    return label.strip() if label else ""


def _label_one(glm: GLMClient, full_text: str, title: str, temp: float) -> str:
    try:
        d = glm.chat_json(SYSP, f"文献标题：{title}\n文献全文（前8000字）：\n{full_text[:8000]}",
                          temperature=temp, timeout=60.0, max_tokens=80)
        return _normalize(d.get("topic", ""))
    except Exception as e:  # noqa: BLE001
        print(f"  LLM 标注失败: {e}")
        return ""


def generate(papers: list[int], rounds: int, temps: list[float]) -> dict:
    glm = GLMClient()
    # 1. 取全文（命中缓存即 MinerU 解析结果）
    docs = []
    for n in papers:
        p = f"{PAPERS_DIR}/{n}.pdf"
        cached = _cache_get(p)
        if cached:
            doc = cached
        else:
            doc = process_to_text(p)
        docs.append({"pdf": n, "path": p,
                     "title": doc.get("title", ""), "full_text": doc.get("full_text", "")})
        print(f"  [{n}.pdf] {doc.get('title', '')[:50]}")

    # 2. 每篇跑 rounds 轮（温度扰动），并发
    print(f"\n每篇标注 {rounds} 轮（温度 {temps}）...")
    results = []
    tasks = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for di, doc in enumerate(docs):
            for r in range(rounds):
                temp = temps[r % len(temps)]
                tasks.append((di, r, ex.submit(_label_one, glm, doc["full_text"], doc["title"], temp)))
        for di, r, fut in tasks:
            label = fut.result()
            if len(results) <= di:
                results.append([])
            while len(results[di]) <= r:
                results[di].append("")
            results[di][r] = label
            print(f"  [{docs[di]['pdf']}.pdf r{r}] → {label!r}")

    # 3. 算一致性
    print("\n" + "=" * 60)
    print("一致性分析")
    print("=" * 60)
    papers_out = []
    for di, doc in enumerate(docs):
        labels = [l for l in results[di] if l]
        if not labels:
            consistency, majority = 0.0, ""
        else:
            cnt = Counter(labels)
            majority, mc = cnt.most_common(1)[0]
            consistency = mc / len(labels)
        did = f"EN_{di+1:05d}"
        conf = "高" if consistency >= 0.8 else ("中" if consistency >= 0.6 else "低(ambiguous)")
        print(f"  {did} [{doc['pdf']}.pdf] {doc['title'][:32]:32} → {majority:8} "
              f"一致={consistency:.2f} {conf}  labels={labels}")
        papers_out.append({
            "document_id": did,
            "pdf": doc["pdf"],
            "title": doc["title"],
            "labels_rounds": labels,
            "gold": majority,
            "consistency": round(consistency, 3),
            "confidence": conf,
        })

    high = [p for p in papers_out if p["consistency"] >= 0.8]
    ambig = [p for p in papers_out if p["consistency"] < 0.8]
    print(f"\n高置信(≥0.8): {len(high)}/{len(papers_out)}, ambiguous: {len(ambig)}")
    if ambig:
        print(f"  ambiguous: {[p['document_id'] for p in ambig]}")

    return {
        "_desc": "LLM多轮一致性gold。consistency=N轮标签一致比例。≥0.8高置信,<0.8 ambiguous。",
        "_rounds": rounds, "_temps": temps,
        "papers": papers_out,
        "high_confidence_count": len(high),
        "ambiguous_count": len(ambig),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--papers", default=",".join(map(str, DEFAULT_PAPERS)))
    ap.add_argument("--out", default="eval/gold_12_consensus.json")
    args = ap.parse_args()
    papers = [int(x) for x in args.papers.split(",") if x.strip()]
    temps = [0.4, 0.5, 0.3, 0.6, 0.4][:args.rounds]
    out = generate(papers, args.rounds, temps)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写出: {args.out}")
