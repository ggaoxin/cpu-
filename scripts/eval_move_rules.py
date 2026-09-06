#!/usr/bin/env python3
"""语步识别规则库回归评估：改规则前后跑分对比，防止"改对这个弄错别的"。

用法：
    python3 scripts/eval_move_rules.py                # 全量评估，输出句级准确率
    python3 scripts/eval_move_rules.py --save baseline.json   # 存基线
    python3 scripts/eval_move_rules.py --compare baseline.json # 与基线逐句对比

评估集：scripts/fixtures/move_eval_set.json（输入摘要 + 人工标注的句子级语步标签）。
改规则库（yaml）后必须跑：准确率不降 + 与基线的差异都要是预期修复。
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_SET = ROOT / "scripts" / "fixtures" / "move_eval_set.json"

ENDPOINTS = {
    "zh": "http://127.0.0.1:8000/api/v1/move/abstract/zh/text",
    "en": "http://127.0.0.1:8000/api/v1/move/abstract/en/text",
}

SENT_SPLIT = re.compile(r"[。！？]|(?:\.)(?=[\s\"'”’\)\]]|$)")


def split_sentences(text: str) -> list:
    spans, start = [], 0
    for m in SENT_SPLIT.finditer(text):
        end = m.end()
        while end < len(text) and text[end] in "”’\"')]}":
            end += 1
        if text[start:end].strip():
            spans.append(text[start:end])
        start = end
    if start < len(text) and text[start:].strip():
        spans.append(text[start:])
    return spans


def call_api(lang: str, abstract: str) -> dict:
    body = json.dumps({"text": abstract, "input_type": "text"}).encode()
    req = urllib.request.Request(ENDPOINTS[lang], data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.load(r)
    moves = (res.get("data") or {}).get("moves") or []
    return {m.get("label"): m.get("text") or "" for m in moves}


def sentence_owner(pred_moves: dict, sentence: str) -> str:
    """预测的句子归属：去空白后看哪类语步 text 包含该句。"""
    flat = re.sub(r"\s+", "", sentence)
    for label, text in pred_moves.items():
        if flat and flat in re.sub(r"\s+", "", text or ""):
            return label
    return "(未覆盖)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", help="把本次结果存为基线 JSON")
    ap.add_argument("--compare", help="与指定基线 JSON 逐句对比")
    args = ap.parse_args()

    if not EVAL_SET.exists():
        print(f"评估集不存在: {EVAL_SET}")
        print("格式: [{\"lang\": \"en\", \"name\": \"...\", \"abstract\": \"...\", \"labels\": [\"Background\", ...]}]")
        sys.exit(1)
    samples = json.loads(EVAL_SET.read_text(encoding="utf-8"))

    results, total, correct = [], 0, 0
    for sample in samples:
        lang, name = sample["lang"], sample["name"]
        sentences = split_sentences(sample["abstract"])
        gold = sample["labels"]
        if len(gold) != len(sentences):
            print(f"⚠  {name}: 标注数({len(gold)})与句子数({len(sentences)})不一致，跳过")
            continue
        pred_moves = call_api(lang, sample["abstract"])
        rows = []
        for sent, gold_label in zip(sentences, gold):
            pred = sentence_owner(pred_moves, sent)
            ok = pred == gold_label
            total += 1
            correct += ok
            rows.append({"sentence": sent[:40], "gold": gold_label, "pred": pred, "ok": ok})
        acc = sum(r["ok"] for r in rows) / max(len(rows), 1)
        results.append({"name": name, "accuracy": round(acc, 3), "rows": rows})
        print(f"\n== {name} 句级准确率 {acc:.0%} ==")
        for r in rows:
            mark = "✓" if r["ok"] else "✗"
            print(f"  {mark} {r['gold']:<12} → {r['pred']:<12} {r['sentence']}")

    print(f"\n总体句级准确率: {correct}/{total} = {correct / max(total, 1):.1%}")

    if args.save:
        Path(args.save).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"基线已存: {args.save}")
    if args.compare:
        baseline = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        base_map = {b["name"]: b for b in baseline}
        print("\n===== 与基线差异（改规则的预期修复应在这里体现）=====")
        for cur in results:
            base = base_map.get(cur["name"])
            if not base:
                continue
            base_rows = {b["sentence"]: b for b in base["rows"]}
            for r in cur["rows"]:
                b = base_rows.get(r["sentence"])
                if b and b["pred"] != r["pred"]:
                    direction = "修复" if r["ok"] and not b["ok"] else ("回归!" if not r["ok"] and b["ok"] else "变动")
                    print(f"  [{direction}] {cur['name']} | {b['pred']} → {r['pred']} | {r['sentence']}")


if __name__ == "__main__":
    main()
