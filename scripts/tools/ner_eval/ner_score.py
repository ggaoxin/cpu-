# -*- coding: utf-8 -*-
"""gold vs 工具结果对齐评分 + 三张补充表。
匹配规则（同类型内，包含式双向）：
  norm = casefold + 去全部空白与标点
  gold 命中 ⇔ ∃ tool 实体：norm(tool) 包含 norm(gold)（gold 是拆分的姓/名时反向）
  tool 正确 ⇔ ∃ gold：norm(gold) 与 norm(tool) 互相包含（带最短长度守卫）
产出：
  /tmp/ner_eval/score_summary.json    总/分类 P/R/F1（ch/en 分列）
  /tmp/ner_eval/misses.jsonl          未识别实体表（补充表1）
  /tmp/ner_eval/fps.jsonl             工具输出但 gold 无（补充表2，含 EVENT）
  /tmp/ner_eval/variants.json         变体/边界映射候选表（补充表3）
"""
import json, re, unicodedata

gold = json.load(open('/tmp/ner_eval/gold.json'))
tool = {r['file']: r for r in json.load(open('/tmp/ner_eval/tool_results.json'))}

def norm(s):
    s = unicodedata.normalize('NFKC', str(s)).casefold()
    return re.sub(r'[\s\.\-·\'’`,，、()（）:：;；!！?？/\\]+', '', s)

def min_ok(a, b):
    # 包含式匹配的最短长度守卫：latin≥3、CJK≥2
    n = min(len(a), len(b))
    if not n:
        return False
    if re.search(r'[a-z]', a + b):
        return n >= 3
    return n >= 2

def match(g, t):
    ng, nt = norm(g), norm(t)
    if not ng or not nt:
        return False
    return (ng in nt or nt in ng) and min_ok(ng, nt)

stats = {}
misses, fps, variants = [], [], []
for fname, g in gold.items():
    trec = tool.get(fname)
    if not trec or trec.get('error'):
        continue
    tents = [e for e in trec.get('entities', []) if e.get('t')]
    is_ch = bool(re.search(r'[一-鿿]', fname.replace('.pdf', ''))) or '?' in fname
    for typ in ('PERSON', 'ORGANIZATION', 'LOCATION'):
        gs = [x for x in g.get(typ, []) if x]
        ts = [e for e in tents if e['y'] == typ]
        hit_flags = []
        for gname in gs:
            hit = next((e for e in ts if match(gname, e['t'])), None)
            hit_flags.append(bool(hit))
            if not hit:
                misses.append({'file': fname, 'type': typ, 'gold': gname})
        for e in ts:
            if not any(match(gname, e['t']) for gname in gs):
                fps.append({'file': fname, 'type': typ, 'text': e['t'], 'conf': e.get('c')})
                # 变体候选：与某 gold 同类型共享显著词根但未互相包含
                for gname in gs:
                    ng, nt = norm(gname), norm(e['t'])
                    if ng and nt and (ng[:4] in nt or nt[:4] in ng) and abs(len(ng) - len(nt)) > 2:
                        variants.append({'file': fname, 'type': typ,
                                         'tool': e['t'], 'gold': gname})
                        break
        key = (typ, 'ch' if is_ch else 'en')
        s = stats.setdefault(key, {'g': 0, 'ghit': 0, 't': 0, 'tmatch': 0})
        s['g'] += len(gs); s['ghit'] += sum(hit_flags)
        s['t'] += len(ts); s['tmatch'] += sum(1 for e in ts if any(match(gname, e['t']) for gname in gs))
    # EVENT：gold 未挖事件，全部记 FP（供人工复核）
    for e in tents:
        if e['y'] not in ('PERSON', 'ORGANIZATION', 'LOCATION'):
            fps.append({'file': fname, 'type': e['y'], 'text': e['t'], 'conf': e.get('c')})

summary = {}
for (typ, lang), s in sorted(stats.items()):
    r = s['ghit'] / s['g'] if s['g'] else None
    p = s['tmatch'] / s['t'] if s['t'] else None
    f = (2 * p * r / (p + r)) if (p and r) else None
    summary[f'{typ}/{lang}'] = {**s,
        'recall': round(r, 3) if r is not None else None,
        'precision': round(p, 3) if p is not None else None,
        'f1': round(f, 3) if f is not None else None}
G = sum(s['g'] for s in stats.values()); GH = sum(s['ghit'] for s in stats.values())
T = sum(s['t'] for s in stats.values()); TM = sum(s['tmatch'] for s in stats.values())
R, P = GH / G, TM / T
summary['OVERALL'] = {'gold': G, 'gold_hit': GH, 'tool': T, 'tool_match': TM,
                      'recall': round(R, 3), 'precision': round(P, 3),
                      'f1': round(2 * P * R / (P + R), 3)}
json.dump(summary, open('/tmp/ner_eval/score_summary.json', 'w'), ensure_ascii=False, indent=1)
with open('/tmp/ner_eval/misses.jsonl', 'w') as f:
    for m in misses:
        f.write(json.dumps(m, ensure_ascii=False) + '\n')
with open('/tmp/ner_eval/fps.jsonl', 'w') as f:
    for m in fps:
        f.write(json.dumps(m, ensure_ascii=False) + '\n')
json.dump(variants, open('/tmp/ner_eval/variants.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
print(f"\nmisses {len(misses)} | fps {len(fps)} | variants {len(variants)}")

# ── 类型分类准确度（用户定义：准确度=分类结果准确度）──
# 对文本能对上 gold（任意类型）的工具实体，统计类型一致率与混淆分布
import collections as _c
confusion = _c.Counter()
n_textmatch, n_typeok = 0, 0
type_examples = _c.defaultdict(list)
for fname, g in gold.items():
    trec = tool.get(fname)
    if not trec or trec.get('error'):
        continue
    for e in trec.get('entities', []):
        if not e.get('t'):
            continue
        for typ in ('PERSON', 'ORGANIZATION', 'LOCATION'):
            for gname in g.get(typ, []):
                if match(gname, e['t']):
                    n_textmatch += 1
                    if e['y'] == typ:
                        n_typeok += 1
                    else:
                        confusion[(typ, e['y'])] += 1
                        if len(type_examples[(typ, e['y'])]) < 3:
                            type_examples[(typ, e['y'])].append(f"{fname[:14]}|{e['t'][:24]}")
                    break
            else:
                continue
            break
print(f"\n== 类型分类准确度: {n_typeok}/{n_textmatch} = {round(n_typeok/n_textmatch, 3) if n_textmatch else 0}")
print("混淆分布 (gold类型→工具类型):")
for (gt, tt), n in confusion.most_common():
    print(f"  {gt}→{tt}: {n}  例: {type_examples[(gt, tt)][:2]}")
