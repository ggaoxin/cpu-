from __future__ import annotations
import ast, json, re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

@lru_cache(maxsize=256)
def load_model(path: str):
    return joblib.load(path)

def kws(v):
    if isinstance(v, list):
        return [str(x) for x in v]
    try:
        x = ast.literal_eval(v) if isinstance(v, str) else []
        return [str(y) for y in x] if isinstance(x, list) else []
    except Exception:
        return [x.strip() for x in re.split(r'[;,；，]', str(v)) if x.strip()]

def txt(r, axis):
    title = str(r.title)
    ks = kws(r.keywords)
    view = str(r.technical_route_text if axis == 'technical' else r.application_scenario_text)
    if axis == 'technical':
        cue = re.compile(r'模型|算法|方法|分析|回归|估计|优化|规划|仿真|模拟|控制|预测|聚类|网络|方程|评估|评价|试验|实验|测量|检测|诊断|制备|合成|表征|测序|PCR|博弈|计量|有限元|数字孪生|数据驱动|机器学习|深度学习|Transformer|神经|model|algorithm|analysis|regression|optimization|simulation|control|prediction|clustering|network|assay|synthesis|characterization|sequencing', re.I)
        mks = [k for k in ks if cue.search(str(k))]
        return ' '.join([view] + mks * 2)
    return ' '.join([title] * 3 + ks * 2 + [view])

def transform(model, texts):
    X = model['vectorizer'].transform(texts)
    return normalize(X) if model.get('svd') is None else normalize(model['svd'].transform(X))

def lexical_score(text, terms):
    if not terms:
        return 0.0
    q = text.lower()
    hits = sum(1 for x in terms if str(x).lower() in q)
    return min(1.0, hits / max(2.0, min(5.0, len(terms))))

def _parent_scores(df, axis, lang, root, rules):
    texts = [txt(r, axis) for _, r in df.iterrows()]
    pm = load_model(str(root / 'models' / f'parent_{axis}_{lang}.joblib'))
    ids = pm['parent_ids']
    # bge-m3 语义打分（若 bge 父类中心存在则用 bge，否则 fallback TF-IDF）
    bge_path = root / 'models' / f'parent_{axis}_{lang}_bge.npy'
    if bge_path.exists():
        from infrastructure.rag.m3_encoder import m3_encoder
        vecs = m3_encoder.encode(texts)
        bge_centroids = np.load(str(bge_path))
        semantic = cosine_similarity(vecs, bge_centroids)
    else:
        Z = transform(pm, texts)
        semantic = cosine_similarity(Z, pm['centroids'])
    pos = {x: i for i, x in enumerate(ids)}
    lexical = np.zeros_like(semantic)
    rule_key = 'model_technical' if axis == 'technical' else 'model_application'
    lang_rules = rules.get(lang, {})
    rdict = lang_rules.get(rule_key, {}) if isinstance(lang_rules, dict) else {}
    for i, (_, row) in enumerate(df.iterrows()):
        fields = [
            (str(row.title).lower(), 3.5),
            (' '.join(kws(row.keywords)).lower(), 3.0),
            (str(row.abstract).lower(), 1.0),
        ]
        for cid, terms in rdict.items():
            if cid not in pos:
                continue
            for term in terms:
                q = str(term).lower()
                for field, weight in fields:
                    if q and q in field:
                        lexical[i, pos[cid]] += weight
    lexical /= lexical.max(axis=1, keepdims=True) + 1e-9
    score = 0.72 * semantic + 0.28 * lexical
    # High-precision v8 boundary overrides repair known parent-level confusions before fine-topic retrieval.
    overrides = rules.get('v8_parent_overrides', {}).get(lang, {}).get(axis, [])
    for i, (_, row) in enumerate(df.iterrows()):
        full = (str(row.title) + ' ' + ' '.join(kws(row.keywords)) + ' ' + str(row.abstract)).lower()
        for rule in overrides:
            if any(str(term).lower() in full for term in rule.get('include', [])):
                cid = rule['id']
                if cid in pos:
                    score[i, pos[cid]] += float(rule.get('boost', 0.5))
                for neg in rule.get('penalize', []):
                    if neg in pos:
                        score[i, pos[neg]] -= 0.22
    return texts, ids, score, np.argsort(-score, axis=1)

def map_one_axis(df, axis, lang, root, topics, taxonomy, rules, top_k):
    texts, parent_ids, parent_score, parent_rank = _parent_scores(df, axis, lang, root, rules)
    topic_lookup = {x['topic_id']: x for x in topics if x['axis'] == axis and x['language'] == lang}
    candidates = [[] for _ in range(len(df))]

    # Batch-transform all documents sharing the same candidate parent.
    grouped = defaultdict(list)
    for i in range(len(df)):
        for pj in parent_rank[i, :min(2, len(parent_ids))]:
            grouped[parent_ids[pj]].append((i, int(pj)))

    for pid, pairs in grouped.items():
        path = root / 'models' / f'topic_{axis}_{lang}_{pid}.joblib'
        if not path.exists():
            continue
        tm = load_model(str(path))
        doc_indices = [x[0] for x in pairs]
        bge_path = root / 'models' / f'topic_{axis}_{lang}_{pid}_bge.joblib'
        if bge_path.exists():
            from infrastructure.rag.m3_encoder import m3_encoder
            bge_tm = load_model(str(bge_path))
            Z = m3_encoder.encode([texts[i] for i in doc_indices])
            topic_ids = bge_tm['topic_ids']
            centroids = bge_tm['centroids']
            proto_vecs = bge_tm['prototype_vectors']
            proto_tids = bge_tm['prototype_topic_ids']
        else:
            Z = transform(tm, [texts[i] for i in doc_indices])
            topic_ids = tm['topic_ids']
            centroids = tm['centroids']
            proto_vecs = tm['prototype_vectors']
            proto_tids = tm['prototype_topic_ids']
        centroid_sim = cosine_similarity(Z, centroids)
        if proto_vecs.shape[0] > 0 and proto_vecs.ndim == 2:
            prototype_sim = cosine_similarity(Z, proto_vecs)
        else:
            prototype_sim = np.zeros((len(doc_indices), 0))
        proto_by_topic = {
            tid: np.array([j for j, t in enumerate(proto_tids) if t == tid], dtype=int)
            for tid in topic_ids
        }
        for local, (doc_i, parent_j) in enumerate(pairs):
            for topic_j, tid in enumerate(topic_ids):
                pidx = proto_by_topic[tid]
                pmax = float(prototype_sim[local, pidx].max()) if len(pidx) else 0.0
                info = topic_lookup[tid]
                lex = lexical_score(texts[doc_i], info.get('positive_evidence', []))
                score = (
                    0.50 * float(centroid_sim[local, topic_j])
                    + 0.23 * pmax
                    + 0.17 * lex
                    + 0.10 * float(parent_score[doc_i, parent_j])
                )
                candidates[doc_i].append((score, tid, pid, float(centroid_sim[local, topic_j]), pmax, lex, float(parent_score[doc_i, parent_j])))

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        cand = sorted(candidates[i], reverse=True)
        if not cand:
            pid = parent_ids[parent_rank[i, 0]]
            rows.append({'document_id': str(row.document_id), f'{axis}_parent_id': pid,
                         f'{axis}_parent_label_zh': taxonomy[axis][pid]['label_zh'],
                         f'{axis}_parent_label_en': taxonomy[axis][pid]['label_en'],
                         f'{axis}_topic_id': None, f'{axis}_topic_name_zh': None, f'{axis}_topic_name_en': None,
                         f'{axis}_mapping_score': 0.0, f'{axis}_mapping_status': 'candidate_new_topic', f'{axis}_topk': '[]'})
            continue
        best = cand[0]
        info = topic_lookup[best[1]]
        direct = 0.72 * float(info.get('direct_match_threshold', 0.65))
        review = 0.72 * float(info.get('review_match_threshold', 0.52))
        status = 'matched' if best[0] >= direct else ('review' if best[0] >= review else 'candidate_new_topic')
        rows.append({
            'document_id': str(row.document_id),
            f'{axis}_parent_id': best[2],
            f'{axis}_parent_label_zh': taxonomy[axis][best[2]]['label_zh'],
            f'{axis}_parent_label_en': taxonomy[axis][best[2]]['label_en'],
            f'{axis}_topic_id': best[1],
            f'{axis}_topic_name_zh': info['topic_name_zh'],
            f'{axis}_topic_name_en': info['topic_name_en'],
            f'{axis}_mapping_score': round(float(best[0]), 4),
            f'{axis}_centroid_score': round(best[3], 4),
            f'{axis}_prototype_score': round(best[4], 4),
            f'{axis}_lexical_score': round(best[5], 4),
            f'{axis}_parent_score': round(best[6], 4),
            f'{axis}_mapping_status': status,
            f'{axis}_topk': json.dumps([{'topic_id': x[1], 'score': round(float(x[0]), 4)} for x in cand[:top_k]], ensure_ascii=False),
        })
    return pd.DataFrame(rows)

def map_documents(df, root, top_k=3):
    root = Path(root)
    taxonomy = json.loads((root / 'taxonomy' / 'taxonomy_v7_unified.json').read_text(encoding='utf-8'))
    rules = json.loads((root / 'rules' / 'rule_library_v7.json').read_text(encoding='utf-8'))
    topics = json.loads((root / 'mappings' / 'technical_route_topic_map.json').read_text(encoding='utf-8'))
    topics += json.loads((root / 'mappings' / 'application_scenario_topic_map.json').read_text(encoding='utf-8'))
    outputs = []
    for lang, group in df.groupby('language', sort=False):
        group = group.reset_index(drop=True)
        # _llm_extract_dual_views 强制双轴文本(technical_route_text/application_scenario_text)
        # 为中文；英文文献走 en TF-IDF 时中文文本全 OOV(词表 0 中文词)导致低分错配。
        # 统一用 zh 模型：parent 级走 zh bge-m3 语义(跨语言对齐)，topic 级走 zh TF-IDF(中文词表)。
        match_lang = 'zh'
        tech = map_one_axis(group, 'technical', match_lang, root, topics, taxonomy, rules, top_k)
        app = map_one_axis(group, 'application', match_lang, root, topics, taxonomy, rules, top_k)
        outputs.append(group.merge(tech, on='document_id').merge(app, on='document_id'))
    out = pd.concat(outputs, ignore_index=True)
    return out.set_index('document_id').loc[df.document_id].reset_index()
