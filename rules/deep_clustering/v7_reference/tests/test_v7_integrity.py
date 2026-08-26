import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def test_taxonomy_ids_preserved():
    v7=json.loads((ROOT/'taxonomy'/'taxonomy_v7_unified.json').read_text(encoding='utf-8'))
    v6=json.loads((ROOT/'legacy_english_v6'/'taxonomy_v6.json').read_text(encoding='utf-8'))
    assert list(v7['technical'])[:33]==list(v6['technical'])
    assert list(v7['application'])[:30]==list(v6['application'])
    for k in v6['technical']: assert v7['technical'][k]['label_zh']==v6['technical'][k]['label_zh']
    for k in v6['application']: assert v7['application'][k]['label_zh']==v6['application'][k]['label_zh']
def test_gold_counts_and_ids():
    g=pd.read_csv(ROOT/'gold'/'gold_zh_model_reviewed_round3_1000.csv')
    tax=json.loads((ROOT/'taxonomy'/'taxonomy_v7_unified.json').read_text(encoding='utf-8'))
    assert len(g)==1000
    assert set(g.technical_cluster_id)<=set(tax['technical'])
    assert set(g.application_cluster_id)<=set(tax['application'])
def test_locked_splits_disjoint():
    for axis in ['technical','application']:
        sets=[]
        for part in ['calibration','development','locked_test']:
            sets.append(set(pd.read_csv(ROOT/'evaluation'/f'{axis}_{part}_gold.csv').document_id))
        assert not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])
