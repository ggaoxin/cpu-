"""审查 gold 标注：对 map_documents vs gold 的错例，GLM 逐个复核，修正 gold 错标，输出高质量 gold v2。

对每个错例（gold 与模型判定不一致），GLM 看文献+gold父类(定义)+模型父类(定义)，
判断 gold/pred/other 哪个对。correct=pred 或 other 的修正 gold。
输出 gold_zh_reviewed_v2.csv + 审查报告。
"""
from __future__ import annotations

import csv
import json
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.exceptions import InconsistentVersionWarning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

from config.settings import settings
from infrastructure.llm.glm_client import glm_client

ROOT = settings.RULES_DIR / "deep_clustering"

AXIS_FIELD = {"technical": "technical_cluster_id", "application": "application_cluster_id"}
AXIS_ERR = {"technical": "tech_errors", "application": "app_errors"}


def main() -> None:
    # 读 gold csv（文献内容 + 标注）
    gold_path = ROOT / "v7_reference" / "gold" / "gold_zh_model_reviewed_round3_1000.csv"
    gold_rows = {}
    for r in csv.DictReader(open(gold_path, encoding="utf-8-sig")):
        try:
            gold_rows[int(r["document_id"].split("_")[-1])] = r
        except Exception:
            continue

    tax = json.load(open(ROOT / "taxonomy" / "taxonomy_v7_unified.json"))
    errs = json.load(open(ROOT / "v7_reference" / "gold" / "gold_eval_errors.json"))

    all_errs = []
    for axis in ("technical", "application"):
        for e in errs[AXIS_ERR[axis]]:
            all_errs.append((axis, e))
    print(f"待审查错例: {len(all_errs)} (技术{len(errs['tech_errors'])}+应用{len(errs['app_errors'])})", flush=True)

    def audit_one(item):
        axis, e = item
        num = int(e["document_id"].split("_")[-1])
        r = gold_rows.get(num, {})
        gold_id, pred_id = e["gold"], e["pred"]
        gold_label = tax[axis].get(gold_id, {}).get("label_zh", "")
        pred_label = tax[axis].get(pred_id, {}).get("label_zh", "")
        sysp = (f"你是科技文献分类审查专家。审查一篇文献的{axis}父类标注是否正确。\n"
                f"文献有 gold 标注和模型判定两个父类。判断哪个更准确，或都不对则给正确父类ID。\n"
                f"只输出JSON：{{\"data\":{{\"correct\":\"gold|pred|other\",\"correct_id\":\"父类ID\",\"reason\":\"简短理由\"}}}}")
        user = (f"文献标题：{r.get('ch_name', '')}\n摘要：{r.get('ch_abstract', '')[:250]}\n"
                f"关键词：{r.get('keywords', '')}\n"
                f"gold标注：{gold_id} {gold_label}\n模型判定：{pred_id} {pred_label}\n")
        try:
            d = glm_client.chat_json(sysp, user, timeout=60.0, max_tokens=150, temperature=0.0)
            d = d.get("data", d) if isinstance(d, dict) else {}
            correct = (d.get("correct") or "gold").strip()
            if correct not in ("gold", "pred", "other"):
                correct = "gold"
            correct_id = (d.get("correct_id") or "").strip()
            if correct == "gold":
                correct_id = gold_id
            elif correct == "pred":
                correct_id = pred_id
            reason = (d.get("reason") or "").strip()
            return (axis, num, gold_id, pred_id, correct, correct_id, reason)
        except Exception as ex:  # noqa: BLE001
            return (axis, num, gold_id, pred_id, "gold", gold_id, f"异常:{ex}")

    # 并发复核
    results = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        for fut in as_completed([ex.submit(audit_one, x) for x in all_errs]):
            results.append(fut.result())
    print(f"复核完成: {len(results)}", flush=True)

    # 统计 + 修正
    stats = {"gold": 0, "pred": 0, "other": 0}
    corrections = {}  # (num, axis) -> correct_id
    for axis, num, gold_id, pred_id, correct, correct_id, reason in results:
        stats[correct] = stats.get(correct, 0) + 1
        if correct in ("pred", "other") and correct_id and correct_id != gold_id:
            corrections[(num, axis)] = correct_id

    print(f"\n===== 审查结果 =====", flush=True)
    print(f"gold正确: {stats.get('gold',0)} | 模型对(改gold→pred): {stats.get('pred',0)} | "
          f"都不对(改gold→other): {stats.get('other',0)}", flush=True)
    print(f"gold修正数: {len(corrections)}", flush=True)

    # 输出修正后 gold v2
    v2_path = ROOT / "v7_reference" / "gold" / "gold_zh_reviewed_v2.csv"
    with open(gold_path, encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    rows_out = []
    for r in csv.DictReader(open(gold_path, encoding="utf-8-sig")):
        try:
            num = int(r["document_id"].split("_")[-1])
        except Exception:
            rows_out.append(r); continue
        for axis in ("technical", "application"):
            key = (num, axis)
            if key in corrections:
                r[AXIS_FIELD[axis]] = corrections[key]
        rows_out.append(r)
    with open(v2_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows_out)
    print(f"\n修正后 gold v2: {v2_path}", flush=True)

    # 审查报告（修正明细）
    rep_path = ROOT / "v7_reference" / "gold" / "gold_audit_report.json"
    report = [{"axis": a, "doc": n, "gold": g, "pred": p, "correct": c, "correct_id": ci, "reason": r}
              for (a, n, g, p, c, ci, r) in results if c in ("pred", "other")]
    json.dump(report, open(rep_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"审查报告(修正明细): {rep_path} ({len(report)}条)", flush=True)


if __name__ == "__main__":
    main()
