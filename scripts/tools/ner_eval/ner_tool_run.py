# -*- coding: utf-8 -*-
"""通用 NER 工具全量评测：74 篇 → parse + /ner/general/file → 结果增量落盘。"""
import json, os, glob, subprocess, time, threading
from concurrent.futures import ThreadPoolExecutor

files = sorted(glob.glob('/root/autodl-tmp/datasets/ch_papers/*.pdf')) + \
        sorted(glob.glob('/root/autodl-tmp/datasets/papers/*.pdf'))
OUT = '/tmp/ner_eval/tool_results.json'
os.makedirs('/tmp/ner_eval', exist_ok=True)
done = {}
if os.path.exists(OUT):
    try:
        done = {r['file']: r for r in json.load(open(OUT))}
    except Exception:
        done = {}
lock = threading.Lock()

def run(f):
    name = os.path.basename(f).encode('utf-8', 'replace').decode('utf-8')
    rec = {'file': name, 'error': ''}
    t0 = time.time()
    try:
        r = subprocess.run(['curl', '-s', '-X', 'POST', 'http://127.0.0.1:8000/api/v1/files/parse',
                            '-F', 'tool_id=general-ner', '-F', f'files=@{f}', '--max-time', '300'],
                           capture_output=True, text=True)
        pid = json.loads(r.stdout)['data']['results'][0]['parse_id']
        r2 = subprocess.run(['curl', '-s', '-X', 'POST', 'http://127.0.0.1:8000/api/v1/ner/general/file',
                             '-F', f'preparsed=["{pid}"]', '--max-time', '300'],
                            capture_output=True, text=True)
        d = json.loads(r2.stdout)
        ents = d.get('data', {}).get('entities', [])
        rec['entities'] = [{'t': e.get('text'), 'y': e.get('type'), 'c': e.get('confidence')} for e in ents]
    except Exception as e:
        rec['error'] = str(e)[:100]
    rec['sec'] = round(time.time() - t0, 1)
    with lock:
        done[name] = rec
        json.dump(list(done.values()), open(OUT, 'w'), ensure_ascii=False, indent=1)
    flag = 'ERR' if rec['error'] else 'ok'
    print(f"[{flag}] {len(rec.get('entities', [])):3} ents {rec['sec']:5.1f}s {name[:44]}", flush=True)
    return rec

todo = [f for f in files if os.path.basename(f).encode('utf-8', 'replace').decode('utf-8') not in done]
print(f"待跑 {len(todo)}/{len(files)}", flush=True)
with ThreadPoolExecutor(max_workers=3) as ex:
    list(ex.map(run, todo))
print('done', flush=True)
