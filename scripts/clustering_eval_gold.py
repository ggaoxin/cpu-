"""对照 gold 评测：跑 map_documents 对比 gold 父类标注，输出错例清单 + 准确率 + 混淆分布。

用法：python -m scripts.clustering_eval_gold
"""
from __future__ import annotations

import csv
import json
import sys
import warnings
from collections import Counter

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.exceptions import InconsistentVersionWarning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

from config.settings import settings
from infrastructure.clustering.topicfusion_v7.runtime import load_input
from infrastructure.clustering.topicfusion_v8.memory import map_documents

ROOT = settings.RULES_DIR / "deep_clustering"


def _doc_num(doc_id: str) -> int:
    """ZH_00001 / ZH_0001 → 1，用序号对齐 gold 与 map_documents 输出。"""
    try:
        return int(str(doc_id).split("_")[-1])
    except Exception:
        return -1


def main() -> None:
    # 1. 跑 map_documents
    print("跑 map_documents on input_1000_chinese...", flush=True)
    df = load_input(str(ROOT / "input_1000_chinese_title_abstract_keywords.json"))
    out = map_documents(df, root=ROOT, top_k=3)
    out = out.set_index("document_id")

    # 2. 读 gold（按序号索引）
    gold_path = ROOT / "v7_reference" / "gold" / "gold_zh_reviewed_v2.csv"
    if not gold_path.exists():
        gold_path = ROOT / "v7_reference" / "gold" / "gold_zh_model_reviewed_round3_1000.csv"
    print(f"使用gold: {gold_path.name}", flush=True)
    gold = {_doc_num(r["document_id"]): r for r in
            csv.DictReader(open(gold_path, encoding="utf-8-sig"))}

    # 3. 对比父类
    tech_correct = app_correct = 0
    tech_errors, app_errors = [], []
    for doc_id, row in out.iterrows():
        num = _doc_num(doc_id)
        g = gold.get(num, {})
        pred_t = row.get("technical_parent_id", "")
        gold_t = g.get("technical_cluster_id", "")
        if pred_t == gold_t:
            tech_correct += 1
        else:
            tech_errors.append({"document_id": doc_id, "title": str(row.get("title", ""))[:30],
                                "pred": pred_t, "gold": gold_t,
                                "gold_secondary": g.get("technical_secondary_id", ""),
                                "status": row.get("technical_mapping_status", "")})
        pred_a = row.get("application_parent_id", "")
        gold_a = g.get("application_cluster_id", "")
        if pred_a == gold_a:
            app_correct += 1
        else:
            app_errors.append({"document_id": doc_id, "title": str(row.get("title", ""))[:30],
                               "pred": pred_a, "gold": gold_a,
                               "gold_secondary": g.get("application_secondary_id", ""),
                               "status": row.get("application_mapping_status", "")})

    n = len(out)
    print(f"\n===== 父类准确率 =====", flush=True)
    print(f"技术路线: {tech_correct}/{n} = {tech_correct/n:.3f}", flush=True)
    print(f"应用场景: {app_correct}/{n} = {app_correct/n:.3f}", flush=True)

    # 综合指标：macro F1 / ARI / NMI + 每类 P/R
    from sklearn.metrics import (f1_score, adjusted_rand_score,
                                  normalized_mutual_info_score, classification_report)
    pred_tech, gold_tech, pred_app, gold_app = [], [], [], []
    for doc_id, row in out.iterrows():
        num = _doc_num(doc_id)
        g = gold.get(num, {})
        pred_tech.append(row.get("technical_parent_id", ""))
        gold_tech.append(g.get("technical_cluster_id", ""))
        pred_app.append(row.get("application_parent_id", ""))
        gold_app.append(g.get("application_cluster_id", ""))

    print(f"\n===== 综合指标 =====", flush=True)
    for _name, _pred, _gold in [("技术路线", pred_tech, gold_tech), ("应用场景", pred_app, gold_app)]:
        _acc = sum(1 for p, g in zip(_pred, _gold) if p == g) / len(_pred)
        _f1 = f1_score(_gold, _pred, average="macro", zero_division=0)
        _ari = adjusted_rand_score(_gold, _pred)
        _nmi = normalized_mutual_info_score(_gold, _pred)
        print(f"{_name}: acc={_acc:.3f}  macroF1={_f1:.3f}  ARI={_ari:.3f}  NMI={_nmi:.3f}", flush=True)
        # 每类 recall 短板（recall<0.6 的父类）
        _rep = classification_report(_gold, _pred, zero_division=0, output_dict=True)
        _low = [(k, round(v["recall"], 2), v["support"]) for k, v in _rep.items()
                if isinstance(v, dict) and k not in ("accuracy", "macro avg", "weighted avg") and v["recall"] < 0.6]
        _low.sort(key=lambda x: x[1])
        if _low:
            print(f"  recall<0.6 的父类短板 (类,recall,样本数): {_low[:10]}", flush=True)

    print(f"\n===== 技术路线父类错例 {len(tech_errors)} =====", flush=True)
    confuse = Counter((e["pred"], e["gold"]) for e in tech_errors)
    print("混淆分布 top12 (pred->gold):", flush=True)
    for (p, g), c in confuse.most_common(12):
        print(f"  {p} -> {g}: {c}", flush=True)

    print(f"\n===== 应用场景父类错例 {len(app_errors)} =====", flush=True)
    confuse_a = Counter((e["pred"], e["gold"]) for e in app_errors)
    print("混淆分布 top12 (pred->gold):", flush=True)
    for (p, g), c in confuse_a.most_common(12):
        print(f"  {p} -> {g}: {c}", flush=True)

    # mapping_status 分布（细主题匹配质量：matched/review/candidate_new_topic）
    for _axis_name, _axis_col in [("技术路线", "technical"), ("应用场景", "application")]:
        _st = Counter(out[f"{_axis_col}_mapping_status"])
        print(f"{_axis_name} mapping_status: {dict(_st)}", flush=True)

    # 保存错例
    err_file = ROOT / "v7_reference" / "gold" / "gold_eval_errors.json"
    json.dump({"tech_errors": tech_errors, "app_errors": app_errors,
               "tech_acc": tech_correct / n, "app_acc": app_correct / n},
              open(err_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n错例已存: {err_file}", flush=True)


if __name__ == "__main__":
    main()
