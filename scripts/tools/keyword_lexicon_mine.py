"""关键词过滤词表挖掘与晋升（2026-09-09 数据驱动词典体系）。

三种模式：
  python3 scripts/tools/keyword_lexicon_mine.py              # 聚合垃圾词沉淀日志（默认）
  python3 scripts/tools/keyword_lexicon_mine.py --promote    # 高频垃圾词晋升进 lexicon auto_learned
  python3 scripts/tools/keyword_lexicon_mine.py --corpus     # 语料统计挖掘泛意词候选（文档频率）

闭环：线上被防线丢弃的词落盘 runtime/keyword_drops.jsonl → 本脚本聚合 →
丢弃 ≥N 次（--min-count，默认 5）的词候选 → --promote 写入
rules/keyword_recognition/lexicon_{lang}.json 的 auto_learned（改文件即热生效）。
晋升后建议跑关键词 gold 评估（37 篇召回回归）确认无误伤。

语料模式：扫描 PDF 语料的 light 全文，单 token 文档频率 ≥ --df（默认 0.3）且
不在词表 → 泛意词候选（只报告不自动晋升，人工确认后手工加入 function_words）。
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DROPS = ROOT / "runtime" / "keyword_drops.jsonl"
LEX = {
    "en": ROOT / "rules" / "keyword_recognition" / "lexicon_en.json",
    "zh": ROOT / "rules" / "keyword_recognition" / "lexicon_zh.json",
}
CORPORA = {
    "en": "/root/autodl-tmp/datasets/papers/*.pdf",
    "zh": "/root/autodl-tmp/datasets/ch_papers/*.pdf",
}


def aggregate(min_count: int) -> dict:
    """聚合丢弃日志：{(lang, word): count}，附原因分布。"""
    if not DROPS.exists():
        print("暂无丢弃日志（runtime/keyword_drops.jsonl）——线上跑过含垃圾词的请求后自动积累")
        return {}
    counter: dict = collections.Counter()
    reasons: dict = collections.defaultdict(collections.Counter)
    for line in DROPS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (row.get("lang"), str(row.get("word") or "").strip().casefold())
        if key[1]:
            counter[key] += 1
            reasons[key][row.get("reason")] += 1
    print(f"丢弃日志聚合（共 {sum(counter.values())} 次 / {len(counter)} 个词）：")
    cands = {k: v for k, v in counter.items() if v >= min_count}
    for (lang, word), n in sorted(cands.items(), key=lambda x: -x[1]):
        print(f"  [{lang}] {word:<24} ×{n}  {dict(reasons[(lang, word)])}")
    if not cands:
        print(f"  （丢弃 ≥{min_count} 次的候选暂无；可调低 --min-count 观察全量）")
    return cands


def promote(cands: dict) -> None:
    if not cands:
        print("无可晋升候选")
        return
    by_lang: dict = collections.defaultdict(list)
    for (lang, word), n in cands.items():
        by_lang[lang].append((word, n))
    for lang, words in by_lang.items():
        path = LEX[lang]
        data = json.loads(path.read_text(encoding="utf-8"))
        have = {str(w).casefold() for w in data.get("function_words") or []}
        have |= {str(w).casefold() for w in data.get("auto_learned") or []}
        fresh = [w for w, _ in sorted(words) if w not in have]
        if not fresh:
            print(f"[{lang}] 候选均已在词表")
            continue
        data.setdefault("auto_learned", []).extend(fresh)
        data["version"] = f"auto-{len(fresh)}词-{json.loads(json.dumps(data.get('version', '')))and '' or ''}{path.stat().st_mtime_ns // 10**9}"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{lang}] 晋升 {len(fresh)} 词 → auto_learned: {fresh}（热生效，无需重启）")
    print("提示：建议跑关键词 gold 评估（/tmp/eval_ab.py 体系）确认无误伤")


def corpus_mine(df_threshold: float) -> None:
    from infrastructure.document_parser.upload_reader import extract_bytes
    for lang, pattern in CORPORA.items():
        paths = sorted(glob.glob(pattern))
        if not paths:
            continue
        data = json.loads(LEX[lang].read_text(encoding="utf-8"))
        block = {str(w).casefold() for w in data.get("function_words") or []}
        block |= {str(w).casefold() for w in data.get("auto_learned") or []}
        doc_freq: dict = collections.Counter()
        token_re = re.compile(r"[A-Za-z]{2,}") if lang == "en" else re.compile(r"[一-鿿]{2,6}")
        for p in paths:
            try:
                text = extract_bytes(open(p, "rb").read(), Path(p).name, light=True)
            except Exception:  # noqa: BLE001
                continue
            if not text:
                continue
            # 中文按 2-6 字滑窗过粗——用 jieba 分词
            if lang == "zh":
                try:
                    import jieba
                    tokens = {t.strip() for t in jieba.cut(text) if 2 <= len(t.strip()) <= 6}
                except ImportError:
                    tokens = set(token_re.findall(text))
            else:
                tokens = {t.casefold() for t in token_re.findall(text)}
            for t in tokens:
                doc_freq[t] += 1
        n = len(paths)
        hits = [(t, c / n) for t, c in doc_freq.items()
                if c / n >= df_threshold and t not in block]
        print(f"\n[{lang}] 语料 {n} 篇，文档频率 ≥{df_threshold:.0%} 的泛意词候选 {len(hits)} 个：")
        for t, r in sorted(hits, key=lambda x: -x[1])[:30]:
            print(f"  {t:<28} {r:.0%}")
        if hits:
            print("  （人工确认后手工加入 lexicon function_words；建议先跑 gold 评估）")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--promote", action="store_true", help="把高频丢弃词晋升进词表 auto_learned")
    parser.add_argument("--corpus", action="store_true", help="语料统计挖掘泛意词候选")
    parser.add_argument("--min-count", type=int, default=5, help="晋升的丢弃次数阈值")
    parser.add_argument("--df", type=float, default=0.3, help="语料模式文档频率阈值")
    args = parser.parse_args()
    if args.corpus:
        corpus_mine(args.df)
    else:
        cands = aggregate(args.min_count)
        if args.promote:
            promote(cands)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
