"""构建 bge-m3 父类中心（替代 TF-IDF 父类中心，用于对照试验）。

用 gold 文献（已知父类）的 txt(axis) 文本，bge-m3 编码，按父类算归一化中心，
存 parent_{axis}_{lang}_bge.npy。_parent_scores 检测到此文件则用 bge 语义打分。
"""
from __future__ import annotations

import csv
import sys
import warnings
from pathlib import Path

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.exceptions import InconsistentVersionWarning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

import numpy as np
from sklearn.preprocessing import normalize

from config.settings import settings
from infrastructure.clustering.topicfusion_v7.runtime import load_input
from infrastructure.clustering.topicfusion_v8.memory import txt, load_model
from infrastructure.rag.m3_encoder import m3_encoder

ROOT = settings.RULES_DIR / "deep_clustering"


def build_axis(axis: str, lang: str = "zh") -> None:
    # gold 父类标注（用 v1 原版，覆盖更全；v2 修正后某些父类文献少导致中心覆盖降）
    gold = {}
    gold_path = ROOT / "v7_reference" / "gold" / "gold_zh_model_reviewed_round3_1000.csv"
    print(f"构建bge中心用gold: {gold_path.name}", flush=True)
    for r in csv.DictReader(open(gold_path, encoding="utf-8-sig")):
        try:
            gold[int(r["document_id"].split("_")[-1])] = r
        except Exception:
            continue

    df = load_input(str(ROOT / "input_1000_chinese_title_abstract_keywords.json"))
    pm = load_model(str(ROOT / "models" / f"parent_{axis}_{lang}.joblib"))
    ids = pm["parent_ids"]
    pos = {x: i for i, x in enumerate(ids)}

    # 每篇 txt + gold 父类
    texts, labels = [], []
    for _, r in df.iterrows():
        try:
            num = int(str(r["document_id"]).split("_")[-1])
        except Exception:
            continue
        g = gold.get(num, {})
        cid = g.get(f"{axis}_cluster_id", "")
        if cid and cid in pos:
            texts.append(txt(r, axis))
            labels.append(cid)

    # bge-m3 编码
    print(f"{axis}/{lang}: 编码 {len(texts)} 篇...", flush=True)
    vecs = m3_encoder.encode(texts)  # (N, 1024) 已 L2 归一化

    # 按父类算中心
    centroids = np.zeros((len(ids), vecs.shape[1]), dtype=np.float32)
    counts = {x: 0 for x in ids}
    for i, cid in enumerate(labels):
        centroids[pos[cid]] += vecs[i]
        counts[cid] += 1
    for cid in ids:
        if counts[cid] > 0:
            centroids[pos[cid]] /= counts[cid]
    centroids = normalize(centroids)

    out = ROOT / "models" / f"parent_{axis}_{lang}_bge.npy"
    np.save(str(out), centroids)
    covered = sum(1 for c in counts.values() if c > 0)
    print(f"{axis}/{lang}: 父类 {len(ids)} 个（{covered} 个有 gold 文献），中心 shape={centroids.shape} → {out}", flush=True)


if __name__ == "__main__":
    for axis in ("technical", "application"):
        build_axis(axis)
    print("\nbge 父类中心构建完成", flush=True)
