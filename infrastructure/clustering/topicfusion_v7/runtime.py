from __future__ import annotations
import ast, json, re, importlib.util, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.linear_model import SGDClassifier

@dataclass
class Config:
    input_file: str
    output_dir: str = 'results_v7'
    calibration_file: str | None = None
    taxonomy_file: str | None = None
    rule_file: str | None = None
    random_state: int = 42


def clean(v: Any) -> str:
    s = '' if v is None else str(v)
    s = re.sub(r'<[^>]+>|https?://\S+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def kw_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [clean(x) for x in v if clean(x)]
    if isinstance(v, str):
        try:
            x = ast.literal_eval(v)
            if isinstance(x, list):
                return [clean(y) for y in x if clean(y)]
        except Exception:
            pass
        return [x.strip() for x in re.split(r'[;,；，]', v) if x.strip()]
    return []


def detect_language(title: str, abstract: str) -> str:
    text = title + abstract
    cjk = sum('\u4e00' <= x <= '\u9fff' for x in text)
    return 'zh' if cjk / max(1, len(text)) > 0.08 else 'en'


def sentences(text: str, lang: str) -> list[str]:
    if lang == 'zh':
        return [x.strip() for x in re.split(r'[。！？；\n]+', text) if len(x.strip()) >= 6]
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+|\n+', text) if len(x.strip()) >= 18]


def extract_views(title: str, abstract: str, keywords: list[str], lang: str) -> tuple[str, str]:
    ss = sentences(abstract, lang)
    kws = '；'.join(keywords) if lang == 'zh' else '; '.join(keywords)
    if lang == 'zh':
        method_re = re.compile(r'采用|提出|构建|建立|设计|基于|运用|模型|算法|方法|实验|仿真|分析|测度|评价|回归|聚类|控制|优化')
        app_re = re.compile(r'应用|场景|系统|疾病|区域|城市|农业|电网|能源|材料|生态|产业|服务|治理')
        method = [s for s in ss if method_re.search(s)] or ss[:5]
        app = [s for i, s in enumerate(ss) if i < 3 or app_re.search(s)] or ss[:5]
        return clean(f'标题：{title}。关键词：{kws}。方法证据：' + '。'.join(method[:12])), clean(f'标题：{title}。关键词：{kws}。研究对象：' + '。'.join(app[:10]))
    method_re = re.compile(r'\b(propos|present|introduc|develop|design|deriv|employ|use|evaluat|assess|investigat|method|approach|framework|model|algorithm|experiment|simulation|analysis|measurement|synthesi|fabricat|review|cohort|survey)\w*\b', re.I)
    app_re = re.compile(r'\b(aim|objective|application|patient|disease|treatment|diagnos|health|material|device|energy|environment|water|plant|animal|battery|sensor|antenna|transport|policy|education|ecolog)\w*\b', re.I)
    method = [s for s in ss if method_re.search(s)] or ss[:5]
    app = [s for i, s in enumerate(ss) if i < 3 or app_re.search(s)] or ss[:5]
    return clean(f'[TITLE] {title} [KEYWORDS] {kws} [METHOD] ' + ' '.join(method[:10])), clean(f'[TITLE] {title} [TITLE] {title} [KEYWORDS] {kws} [OBJECTIVE] ' + ' '.join(app[:9]))


def load_input(path: str) -> pd.DataFrame:
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(obj, dict):
        obj = obj.get('documents', obj.get('data', []))
    df = pd.DataFrame(obj)
    missing_document_id = 'document_id' not in df
    if 'keywords' not in df:
        df['keywords'] = [[] for _ in range(len(df))]
    df['keywords'] = df['keywords'].map(kw_list)
    titles, abstracts, langs = [], [], []
    for _, r in df.iterrows():
        title = clean(r.get('ch_name', r.get('en_name', r.get('title', ''))))
        abstract = clean(r.get('ch_abstract', r.get('en_abstract', r.get('abstract', ''))))
        lang = detect_language(title, abstract)
        titles.append(title); abstracts.append(abstract); langs.append(lang)
    df['title'] = titles; df['abstract'] = abstracts; df['language'] = langs
    if missing_document_id:
        counters = {'zh': 0, 'en': 0}
        generated = []
        for lang in langs:
            counters[lang] += 1
            prefix = 'ZH' if lang == 'zh' else 'EN'
            generated.append(f'{prefix}_{counters[lang]:05d}')
        df['document_id'] = generated
    else:
        df['document_id'] = df['document_id'].astype(str)
    # 双轴文本：如果已由上游LLM提取（technical_route_text列已存在且非空），则不覆盖
    if 'technical_route_text' not in df.columns or df['technical_route_text'].isna().all() or (df['technical_route_text'] == '').all():
        views = df.apply(lambda r: extract_views(r.title, r.abstract, r.keywords, r.language), axis=1)
        df[['technical_route_text', 'application_scenario_text']] = pd.DataFrame(views.tolist(), index=df.index)
    else:
        # 上游已提供（LLM提取），确保application_scenario_text也有值
        if 'application_scenario_text' not in df.columns:
            df['application_scenario_text'] = df['technical_route_text']
    return df


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max(axis=1, keepdims=True)
    e = np.exp(np.clip(x, -40, 40))
    return e / (e.sum(axis=1, keepdims=True) + 1e-12)


def phrase_score_zh(row: pd.Series, ids: list[str], rules: dict[str, list[str]]) -> np.ndarray:
    out = np.zeros(len(ids)); pos = {c: i for i, c in enumerate(ids)}
    fields = [(row.title.lower(), 3.5), ('；'.join(row.keywords).lower(), 3.0), (row.abstract.lower(), 1.0)]
    for cid, terms in rules.items():
        if cid not in pos: continue
        for term in terms:
            q = term.lower()
            for text, w in fields:
                if q and q in text: out[pos[cid]] += w
    return out


def phrase_score_en(row: pd.Series, ids: list[str], taxonomy: dict[str, dict[str, str]]) -> np.ndarray:
    # Lightweight English evidence from prototype phrases. The validated English v6 remains available in legacy_english_v6.
    out = np.zeros(len(ids)); text_t = row.title.lower(); text_k = ' '.join(row.keywords).lower(); text_a = row.abstract.lower()
    for j, cid in enumerate(ids):
        terms = [x for x in re.split(r'\s+', taxonomy[cid].get('prototype_en', '')) if len(x) >= 4]
        for term in terms:
            if term in text_t: out[j] += 1.2
            if term in text_k: out[j] += 1.0
            if term in text_a: out[j] += 0.25
    return out


def fit_axis(group: pd.DataFrame, taxonomy: dict[str, dict[str, str]], axis: str, rules_zh: dict[str, list[str]], calibration: pd.DataFrame | None, seed: int) -> pd.DataFrame:
    ids = list(taxonomy); lang = group.language.iloc[0]
    pkey = 'prototype_zh' if lang == 'zh' else 'prototype_en'
    textcol = 'technical_route_text' if axis == 'technical' else 'application_scenario_text'
    texts = group[textcol].tolist(); protos = [taxonomy[c]['label_zh'] + ' ' + taxonomy[c][pkey] for c in ids]
    vec = TfidfVectorizer(analyzer='char', ngram_range=(2, 5), min_df=1, max_features=50000, sublinear_tf=True)
    X = vec.fit_transform(texts + protos); dim = min(90, max(2, min(X.shape) - 1))
    Z = normalize(TruncatedSVD(n_components=dim, random_state=seed).fit_transform(X)); D, P = Z[:len(group)], Z[len(group):]
    proto = cosine_similarity(D, P); cent = proto.copy(); clfprob = np.full_like(proto, 1 / len(ids))
    if calibration is not None and len(calibration):
        cal = calibration[calibration.document_id.isin(group.document_id)].copy()
        if len(cal):
            pos = {x: i for i, x in enumerate(group.document_id)}; idx = np.array([pos[x] for x in cal.document_id]); y = cal[f'{axis}_cluster_id'].astype(str).to_numpy()
            centers = []
            for j, c in enumerate(ids):
                ii = idx[y == c]
                centers.append(normalize((.9 * D[ii].mean(axis=0) + .1 * P[j]).reshape(1, -1))[0] if len(ii) else P[j])
            cent = cosine_similarity(D, np.vstack(centers))
            anchors = protos; train = [texts[i] for i in idx] + anchors + anchors; yy = list(y) + ids + ids
            vv = TfidfVectorizer(analyzer='char', ngram_range=(2, 5), min_df=1, max_features=50000, sublinear_tf=True)
            Q = vv.fit_transform(train + texts)
            clf = SGDClassifier(loss='log_loss', max_iter=2000, tol=1e-4, class_weight='balanced', alpha=1e-5, random_state=seed)
            clf.fit(Q[:len(train)], yy); pr = clf.predict_proba(Q[len(train):]); cmap = {c: i for i, c in enumerate(clf.classes_)}
            clfprob = np.full((len(group), len(ids)), 1e-9)
            for j, c in enumerate(ids):
                if c in cmap: clfprob[:, j] = pr[:, cmap[c]]
            clfprob /= clfprob.sum(axis=1, keepdims=True)
    sem = _softmax(7 * (.35 * proto + .65 * cent))
    if lang == 'zh':
        rs = np.vstack([phrase_score_zh(r, ids, rules_zh) for _, r in group.iterrows()])
    else:
        # Reuse the validated English-v6 regex rules for preserved IDs, then add lightweight evidence for v7-added IDs.
        legacy_file = Path(__file__).resolve().parents[1] / 'legacy_english_v6' / 'topicfusion_v6' / 'pipeline.py'
        spec = importlib.util.spec_from_file_location('topicfusion_legacy_v6_pipeline', legacy_file)
        legacy = importlib.util.module_from_spec(spec); sys.modules[spec.name]=legacy; spec.loader.exec_module(legacy)
        temp = pd.DataFrame({'en_name': group.title, 'en_abstract': group.abstract, 'keywords': group.keywords})
        temp.index = range(len(temp))
        rs = legacy.rule_scores(temp, ids, axis)
        rs = legacy.boundary_adjust(temp, ids, rs, axis)
        added = set(ids) - (set(f'T{i:02d}' for i in range(1,34)) if axis == 'technical' else set(f'A{i:02d}' for i in range(1,31)))
        idpos = {c:i for i,c in enumerate(ids)}
        for i,(_,row) in enumerate(group.iterrows()):
            extra = phrase_score_en(row, ids, taxonomy)
            for cid in added: rs[i,idpos[cid]] += extra[idpos[cid]]
    rule = _softmax(rs / 2.7)
    if calibration is None or not len(calibration):
        total = (.70 * sem + .30 * rule) if lang == 'zh' else (.45 * sem + .55 * rule)
    else:
        rule_w = .20 if axis == 'technical' else .25
        total = (1 - .45 - rule_w) * sem + .45 * clfprob + rule_w * rule
    rank = np.argsort(-total, axis=1); vals = np.sort(total, axis=1); margin = vals[:, -1] - vals[:, -2]
    return pd.DataFrame({
        'document_id': group.document_id.to_numpy(),
        f'{axis}_cluster_id': [ids[j] for j in rank[:, 0]],
        f'{axis}_secondary_id': [ids[j] for j in rank[:, 1]],
        f'{axis}_confidence': np.round(np.clip(.4 + .42 * vals[:, -1] + 1.2 * margin, .4, .99), 4),
        f'{axis}_decision_margin': np.round(margin, 4),
        f'{axis}_needs_review': margin < .045,
    })


def run(config: Config) -> Path:
    root = Path(__file__).resolve().parents[1]
    tax_path = Path(config.taxonomy_file) if config.taxonomy_file else root / 'taxonomy' / 'taxonomy_v7_unified.json'
    rule_path = Path(config.rule_file) if config.rule_file else root / 'rules' / 'rule_library_v7.json'
    taxonomy = json.loads(tax_path.read_text(encoding='utf-8')); rulelib = json.loads(rule_path.read_text(encoding='utf-8'))
    df = load_input(config.input_file); cal = pd.read_csv(config.calibration_file) if config.calibration_file else None
    results = []
    for lang, group in df.groupby('language', sort=False):
        group = group.reset_index(drop=True)
        tech = fit_axis(group, taxonomy['technical'], 'technical', rulelib['zh']['model_technical'], cal, config.random_state)
        app = fit_axis(group, taxonomy['application'], 'application', rulelib['zh']['model_application'], cal, config.random_state)
        out = group.merge(tech, on='document_id').merge(app, on='document_id')
        results.append(out)
    out = pd.concat(results, ignore_index=True).set_index('document_id').loc[df.document_id].reset_index()
    out['technical_label_zh'] = out.technical_cluster_id.map(lambda x: taxonomy['technical'][x]['label_zh'])
    out['technical_label_en'] = out.technical_cluster_id.map(lambda x: taxonomy['technical'][x].get('label_en', taxonomy['technical'][x]['label_zh']))
    out['application_label_zh'] = out.application_cluster_id.map(lambda x: taxonomy['application'][x]['label_zh'])
    out['application_label_en'] = out.application_cluster_id.map(lambda x: taxonomy['application'][x].get('label_en', taxonomy['application'][x]['label_zh']))
    od = Path(config.output_dir); od.mkdir(parents=True, exist_ok=True)
    csv = od / 'dual_cluster_results_v7.csv'; js = od / 'dual_cluster_results_v7.json'
    out.to_csv(csv, index=False, encoding='utf-8-sig'); out.to_json(js, orient='records', force_ascii=False, indent=2)
    metadata = {'documents': len(out), 'languages': out.language.value_counts().to_dict(), 'taxonomy_version': taxonomy['version'], 'calibration': config.calibration_file}
    (od / 'run_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return csv
