# -*- coding: utf-8 -*-
"""快车道·解析缓存：MinerU md + NER 头部补丁 一次性缓存到本地。
后续评测迭代直接用缓存文本打 text 端点，跳过 MinerU（50min→~15min）。"""
import sys, os, json, glob, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/root/autodl-tmp/semantic_toolkit')
os.chdir('/root/autodl-tmp/semantic_toolkit')
from presentation.api.v1.integration_controller import _mineru_parse_one, _patch_ner_header_lines

files = sorted(glob.glob('/root/autodl-tmp/datasets/ch_papers/*.pdf')) + \
        sorted(glob.glob('/root/autodl-tmp/datasets/papers/*.pdf'))
OUT = '/tmp/ner_eval/parse_cache.json'
done = {}
if os.path.exists(OUT):
    try:
        done = json.load(open(OUT))
    except Exception:
        done = {}

def build(f):
    name = os.path.basename(f).encode('utf-8', 'replace').decode('utf-8')
    try:
        content = open(f, 'rb').read()
        md = (_mineru_parse_one(content, os.path.basename(f), None) or {}).get('text', '')
        if md:
            md = _patch_ner_header_lines(md, content, os.path.basename(f))
        return name, md
    except Exception as e:
        return name, {'__error__': str(e)[:80]}

todo = [f for f in files if os.path.basename(f).encode('utf-8', 'replace').decode('utf-8') not in done]
print(f'待解析 {len(todo)}/{len(files)}', flush=True)
t0 = time.time()
with ThreadPoolExecutor(max_workers=3) as ex:
    for i, (name, md) in enumerate(ex.map(build, todo)):
        done[name] = md
        json.dump(done, open(OUT, 'w'), ensure_ascii=False)
        if i % 10 == 0:
            print(f'[{i+1}/{len(todo)}] {time.time()-t0:.0f}s', flush=True)
n_ok = sum(1 for v in done.values() if isinstance(v, str) and len(v) > 500)
print(f'缓存完成: {n_ok}/{len(done)} 篇有效 → {OUT}', flush=True)
