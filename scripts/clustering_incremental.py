"""增量主题发现链路：候选池 → propose提案 → GLM自动审核 → 入库报告。

用法：
  python -m scripts.clustering_incremental --candidates <new_topic_candidates.jsonl> [--min-support 12]

流程：
  1. 读运行时产生的候选文献（map_documents 输出的 candidate_new_topic）
  2. propose_incremental_topics：同轴×同语言×同父类攒够 min_support → 聚类提案新主题
  3. GLM 逐个审核提案（命名/边界/重复 → accept/rename/reject）
  4. accept/rename 的标记为可入库，输出审核报告

审核通过的主题后续通过 build_topic_memory 重建模型时入库（需配套文献数据）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.settings import settings
from infrastructure.clustering.topicfusion_v8.incremental import propose_incremental_topics
from infrastructure.clustering.topic_review import review_proposal

ROOT = settings.RULES_DIR / "deep_clustering"


def load_existing_topics() -> dict:
    """读现有主题库，按 (axis, parent_id) 分组主题名。"""
    topics: dict = {}
    for axis_file, axis in [("technical_route_topic_map.json", "technical"),
                            ("application_scenario_topic_map.json", "application")]:
        p = ROOT / "mappings" / axis_file
        if not p.exists():
            continue
        for t in json.loads(p.read_text(encoding="utf-8")):
            key = (axis, t.get("parent_category_id", ""))
            name = t.get("topic_name_zh") or t.get("topic_name_zh") or t.get("topic_name", "")
            if name:
                topics.setdefault(key, []).append(name)
    return topics


def main() -> None:
    ap = argparse.ArgumentParser(description="增量主题发现：候选池→提案→GLM审核")
    ap.add_argument("--candidates", required=True, help="new_topic_candidates.jsonl 路径")
    ap.add_argument("--output", default=None, help="审核报告输出路径")
    ap.add_argument("--min-support", type=int, default=12, help="最小支持数（默认12）")
    args = ap.parse_args()

    output = Path(args.output) if args.output else ROOT / "candidate_pool" / "reviewed_proposals.json"

    # 1. 提案
    proposal_file = ROOT / "candidate_pool" / "proposed_topic_updates.json"
    propose_incremental_topics(args.candidates, proposal_file, min_support=args.min_support)
    payload = json.loads(proposal_file.read_text(encoding="utf-8"))
    proposals = payload.get("proposals", [])
    print(f"步骤1：候选池生成 {len(proposals)} 个候选主题提案（min_support={args.min_support}）", flush=True)
    if not proposals:
        print("无候选主题（候选池未攒够 min_support 或为空），结束。")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"proposals": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    # 2. 四层审核（①相似度阈值 ②③GLM判断+查表 ④pending待人工）
    existing = load_existing_topics()
    reviewed = []
    for i, p in enumerate(proposals, 1):
        key = (p.get("axis"), p.get("parent_category_id"))
        ex = existing.get(key, [])
        r = review_proposal(p, ex)
        commit = {"accept": "auto_approved",
                  "use_existing": "mapped_to_existing",
                  "pending": "manual_review_required"}.get(r["decision"], "manual_review_required")
        reviewed.append({**p, "review": r, "status": "reviewed", "commit_policy": commit})
        extra = f" → 归入已有'{r['existing_match']}'" if r["decision"] == "use_existing" and r.get("existing_match") else ""
        print(f"  [{i}/{len(proposals)}] {p['proposal_id']} [{p['proposed_name']}] "
              f"-> {r['decision']} ({r['final_name']}){extra}", flush=True)

    # 3. 输出审核报告
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"proposals": reviewed}, ensure_ascii=False, indent=2), encoding="utf-8")

    accepted = [p for p in reviewed if p["review"]["decision"] == "accept"]
    use_existing = [p for p in reviewed if p["review"]["decision"] == "use_existing"]
    pending = [p for p in reviewed if p["review"]["decision"] == "pending"]
    print(f"\n步骤2：四层审核完成", flush=True)
    print(f"  accept（新主题，可入库）：{len(accepted)} 个", flush=True)
    print(f"  use_existing（归已有主题）：{len(use_existing)} 个", flush=True)
    print(f"  pending（待人工确认，记录不自动）：{len(pending)} 个", flush=True)
    print(f"审核报告：{output}", flush=True)
    if accepted:
        print(f"\n新主题（后续 build_topic_memory 重建时入库）：", flush=True)
        for p in accepted:
            print(f"  {p['proposal_id']} -> {p['review']['final_name']} "
                  f"({p['axis']}/{p['parent_category_id']}, n={p['support_count']})", flush=True)
    if pending:
        print(f"\n待人工确认（你手动添加，不让LLM再审）：", flush=True)
        for p in pending:
            print(f"  {p['proposal_id']} [{p['proposed_name']}] - {p['review']['reason'][:60]}", flush=True)


if __name__ == "__main__":
    main()
