"""构建 bge-m3 细主题中心+原型（替代 TF-IDF，用于细主题匹配对照试验）。

对每个 topic_{axis}_{lang}_{pid}.joblib：
- 中心：用 assignments.csv 的 high quality 文献（该细主题）bge 编码算均值
- 原型：用 joblib 的 prototype_document_ids 文献 bge 编码
存 topic_{axis}_{lang}_{pid}_bge.joblib（{topic_ids, centroids, prototype_vectors, prototype_topic_ids}）。
map_one_axis 检测到此文件则用 bge，否则 fallback TF-IDF。
"""
from __future__ import annotations

import csv
import sys
import warnings
from collections import defaultdict

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.exceptions import InconsistentVersionWarning
warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

import joblib
import numpy as np
from sklearn.preprocessing import normalize

from config.settings import settings
from infrastructure.clustering.topicfusion_v7.runtime import load_input
from infrastructure.clustering.topicfusion_v8.memory import txt
from infrastructure.rag.m3_encoder import m3_encoder

ROOT = settings.RULES_DIR / "deep_clustering"


def main() -> None:
    df = load_input(str(ROOT / "input_1000_chinese_title_abstract_keywords.json"))
    doc_by_num = {int(str(r["document_id"]).split("_")[-1]): r for _, r in df.iterrows()}

    # 读 assignments（high quality，按 axis+parent 分组）
    assigns = defaultdict(list)  # (axis, parent) -> [(num, topic_id)]
    for r in csv.DictReader(open(ROOT / "mappings" / "discovery_document_topic_assignments.csv",
                                 encoding="utf-8-sig")):
        if r.get("source_quality", "") != "high" or r.get("language", "") != "zh":
            continue
        try:
            num = int(r["document_id"].split("_")[-1])
        except Exception:
            continue
        assigns[(r["axis"], r["parent_category_id"])].append((num, r["topic_id"]))

    n_built = 0
    for axis in ("technical", "application"):
        for path in sorted((ROOT / "models").glob(f"topic_{axis}_zh_*.joblib")):
            if path.name.endswith("_bge.joblib"):
                continue
            pid = path.stem.split("_")[3]
            tm = joblib.load(path)
            topic_ids = tm["topic_ids"]
            proto_doc_ids = tm.get("prototype_document_ids", [])
            proto_topic_ids = tm.get("prototype_topic_ids", [])

            # 该父类 assignments 按主题分组
            topic_docs = {tid: [] for tid in topic_ids}
            for num, tid in assigns.get((axis, pid), []):
                if tid in topic_docs and num in doc_by_num:
                    topic_docs[tid].append(num)

            # 原型文献
            proto_nums = []
            for d in proto_doc_ids:
                try:
                    n = int(str(d).split("_")[-1])
                    if n in doc_by_num:
                        proto_nums.append(n)
                except Exception:
                    continue

            # bge 编码（中心文献 + 原型文献，去重）
            all_nums = list(set([n for ns in topic_docs.values() for n in ns] + proto_nums))
            if not all_nums:
                continue
            texts = [txt(doc_by_num[n], axis) for n in all_nums]
            vecs = m3_encoder.encode(texts)
            num_to_vec = {n: vecs[i] for i, n in enumerate(all_nums)}

            # 中心：每主题 high quality 文献 bge 均值
            centroids = np.zeros((len(topic_ids), vecs.shape[1]), dtype=np.float32)
            for ti, tid in enumerate(topic_ids):
                vs = [num_to_vec[n] for n in topic_docs[tid] if n in num_to_vec]
                if vs:
                    centroids[ti] = np.mean(vs, axis=0)
            centroids = normalize(centroids)

            # 原型向量 + topic_id
            proto_vecs = np.array([num_to_vec[n] for n in proto_nums if n in num_to_vec])
            proto_tids = []
            for i, n in enumerate(proto_nums):
                if n in num_to_vec:
                    # 原型 topic_id 来自原 joblib 的 prototype_topic_ids（同序）
                    proto_tids.append(proto_topic_ids[i] if i < len(proto_topic_ids) else topic_ids[0])

            out = ROOT / "models" / f"topic_{axis}_zh_{pid}_bge.joblib"
            joblib.dump({"topic_ids": topic_ids, "centroids": centroids,
                         "prototype_vectors": proto_vecs,
                         "prototype_topic_ids": proto_tids}, out)
            n_built += 1
            print(f"{axis}/{pid}: {len(topic_ids)}主题 中心{centroids.shape} 原型{proto_vecs.shape} → {out.name}", flush=True)

    print(f"\n构建完成：{n_built} 个 bge 细主题模型", flush=True)


if __name__ == "__main__":
    main()
