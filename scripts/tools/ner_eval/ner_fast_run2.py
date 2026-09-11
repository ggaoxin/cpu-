# -*- coding: utf-8 -*-
"""快车道 v2：进程内直调引擎（与文件模式同口径：10k 截断 + 全文词表补抽 + 变体合并）。
用法：python3 /tmp/ner_fast_run2.py <research|domain>   → /tmp/ner_eval/fast_<tool>.json
"""
import sys, os, json, time, threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/root/autodl-tmp/semantic_toolkit')
os.chdir('/root/autodl-tmp/semantic_toolkit')
from infrastructure.llm.glm_client import glm_client
from infrastructure.rule_engine.rule_loader import rule_loader
from application.service.semantic_service import SemanticApplicationService
from application.dto.common_dto import SemanticRequest

TOOL = sys.argv[1] if len(sys.argv) > 1 else 'research'
CODE = {'research': 'ner_research', 'domain': 'ner_domain'}[TOOL]
CACHE = json.load(open('/tmp/ner_eval/parse_cache.json'))
gold = json.load(open(f'/tmp/ner_eval/gold_{TOOL}.json'))
OUT = f'/tmp/ner_eval/fast_{TOOL}.json'
targets = list(CACHE) if TOOL == 'research' else [f for f in CACHE if f in gold]
done = {}
if os.path.exists(OUT):
    try:
        done = {r['file']: r for r in json.load(open(OUT))}
    except Exception:
        done = {}
lock = threading.Lock()
_svc = SemanticApplicationService(glm=glm_client, rule_loader=rule_loader)

def run(name):
    text = CACHE.get(name)
    rec = {'file': name, 'error': ''}
    if not isinstance(text, str) or len(text) < 200:
        rec['error'] = 'no cached text'
        return rec
    t0 = time.time()
    try:
        req = SemanticRequest(text=text, params={}, meta={'source': 'fast_eval'})
        result = _svc.execute(CODE, req)
        ents = result.data if isinstance(result.data, list) else []
        rec['entities'] = [{'t': e.get('text'), 'y': e.get('type'),
                            'c': e.get('confidence')} for e in ents if isinstance(e, dict)]
    except Exception as e:
        rec['error'] = f'{type(e).__name__}: {e}'[:120]
    rec['sec'] = round(time.time() - t0, 1)
    with lock:
        done[name] = rec
        json.dump(list(done.values()), open(OUT, 'w'), ensure_ascii=False, indent=1)
    print(f"[{'ERR' if rec['error'] else 'ok '}] {len(rec.get('entities', [])):3} ents {rec['sec']:5.1f}s {name[:40]}", flush=True)
    return rec

todo = [f for f in targets if f not in done]
print(f'{TOOL}: 待跑 {len(todo)}/{len(targets)}', flush=True)
with ThreadPoolExecutor(max_workers=3) as ex:
    list(ex.map(run, todo))
print('done', flush=True)
