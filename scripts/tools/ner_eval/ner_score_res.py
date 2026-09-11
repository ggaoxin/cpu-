# -*- coding: utf-8 -*-
"""科研/专业领域 NER 评分：召回 + 类型分类准确度 + 混淆矩阵。
用法：python3 /tmp/ner_score_res.py <research|domain>
"""
import json, re, sys, unicodedata, collections

TOOL = sys.argv[1] if len(sys.argv) > 1 else 'research'
gold = json.load(open(f'/tmp/ner_eval/gold_{TOOL}.json'))
tool = {r['file']: r for r in json.load(open(f'/tmp/ner_eval/fast_{TOOL}.json'))}

def norm(s):
    s = unicodedata.normalize('NFKC', str(s)).casefold()
    return re.sub(r'[\s\.\-·\'’`,，、()（）:：;；!！?？/\\]+', '', s)

def match(g, t):
    ng, nt = norm(g), norm(t)
    if not ng or not nt:
        return False
    n = min(len(ng), len(nt))
    if re.search(r'[a-z]', ng + nt) and n < 3:
        return False
    if not re.search(r'[a-z]', ng + nt) and n < 2:
        return False
    return ng in nt or nt in ng

TYPES = ('METHOD', 'DATASET', 'INSTRUMENT', 'TOPIC') if TOOL == 'research' else ('DISEASE', 'DRUG', 'TREATMENT')
stats = collections.defaultdict(lambda: [0, 0])
confusion = collections.Counter()
n_text, n_ok = 0, 0
misses = []
for fname, g in gold.items():
    trec = tool.get(fname)
    if not trec or trec.get('error'):
        continue
    ents = [e for e in trec.get('entities', []) if e.get('t')]
    for typ in TYPES:
        gs = [x for x in g.get(typ, []) if x]
        if not gs:
            continue
        ts = [e for e in ents if e['y'] == typ]
        hit = sum(1 for x in gs if any(match(x, e['t']) for e in ents))
        stats[typ][0] += hit
        stats[typ][1] += len(gs)
        for x in gs:
            if not any(match(x, e['t']) for e in ents):
                misses.append({'file': fname, 'type': typ, 'gold': x})
    for e in ents:
        for typ in TYPES:
            if any(match(x, e['t']) for x in g.get(typ, [])):
                n_text += 1
                if e['y'] == typ:
                    n_ok += 1
                else:
                    confusion[(typ, e['y'])] += 1
                break

print(f"== {TOOL}-ner ==")
tot_h = tot_g = 0
for typ in TYPES:
    h, g_ = stats[typ]
    if g_:
        print(f"  {typ:12}: {h}/{g_} = {h/g_:.3f}")
        tot_h += h; tot_g += g_
print(f"  整体召回: {tot_h}/{tot_g} = {tot_h/tot_g:.3f}" if tot_g else "  无锚点")
if n_text:
    print(f"  类型分类准确度: {n_ok}/{n_text} = {n_ok/n_text:.3f}")
for (gt, tt), n in confusion.most_common(8):
    print(f"  混淆 {gt}→{tt}: {n}")
with open(f'/tmp/ner_eval/misses_{TOOL}.jsonl', 'w') as f:
    for m in misses:
        f.write(json.dumps(m, ensure_ascii=False) + '\n')
print(f"  misses → /tmp/ner_eval/misses_{TOOL}.jsonl ({len(misses)})")
