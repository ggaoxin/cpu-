#!/usr/bin/env python3
"""真实论文集双轴测试（v3）：20 篇 ch_papers PDF 全文。

流程：mineru 全文 → 切块并发语步提取（方法/背景/目的句）→
  技术路线轴 = 方法句向量聚类
  应用场景轴 = 背景+目的句+题名向量聚类
层次聚类（余弦/平均链接）+ 轮廓系数自动选 k（不使用 oracle k）。
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from experiment_fulltext_move import chunk_text, EXTRACT_SYSTEM  # 复用切块与提取 prompt


def extract_chunk(glm, chunk):
    try:
        raw = glm.chat_json(EXTRACT_SYSTEM, f"文献片段：\n{chunk}", temperature=0.0, timeout=120.0, max_tokens=3000)
    except Exception:  # noqa: BLE001
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    return {k: ([str(v).strip() for v in raw.get(k) or [] if str(v).strip()] if isinstance(raw, dict) else [])
            for k in ("研究背景", "研究目的", "研究方法")}


def main(pdf_dir):
    pdfs = sorted(Path(pdf_dir).glob("*.pdf"))
    print(f"处理 {len(pdfs)} 篇 PDF...")

    from infrastructure.document_parser.mineru_reader import process_to_text
    from infrastructure.llm.glm_client import glm_client
    from infrastructure.rag.m3_encoder import m3_encoder
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    # 1) 全文解析（并发）
    def parse(p):
        try:
            return {"name": "".join(c for c in p.stem if not 0xD800 <= ord(c) <= 0xDFFF) or p.name,
                    "text": (process_to_text(str(p)).get("full_text") or "").strip()}
        except Exception:  # noqa: BLE001
            return {"name": p.stem, "text": ""}
    with ThreadPoolExecutor(max_workers=4) as pool:
        docs = list(pool.map(parse, pdfs))
    docs = [d for d in docs if len(d["text"]) > 200]
    print(f"全文解析成功 {len(docs)} 篇")

    # 2) 切块 + 并发语步提取
    def extract(doc):
        chunks = chunk_text(doc["text"])
        with ThreadPoolExecutor(max_workers=6) as pool:
            parts = list(pool.map(lambda c: extract_chunk(glm_client, c), chunks))
        merged = {k: [] for k in ("研究背景", "研究目的", "研究方法")}
        for part in parts:
            for k in merged:
                merged[k].extend(part.get(k) or [])
        for k in merged:
            merged[k] = list(dict.fromkeys(merged[k]))[:20]
        return {"name": doc["name"], "chars": len(doc["text"]), "chunks": len(chunks), **merged}

    for i, doc in enumerate(docs):
        docs[i] = extract(doc)
        print(f"  ✓ {doc['name'][:24]}（{docs[i]['chunks']}块）: 方法{len(docs[i]['研究方法'])} 背景{len(docs[i]['研究背景'])} 目的{len(docs[i]['研究目的'])}", flush=True)

    Path("/tmp/ch_papers_moves.json").write_text(json.dumps(docs, ensure_ascii=True, indent=1), encoding="utf-8")

    # 3) 双轴向量 + 层次聚类（自动 k：轮廓 2..8）
    def vec(texts):
        v = np.asarray(m3_encoder.encode(texts)).mean(axis=0)
        return v / max(np.linalg.norm(v), 1e-9)

    def auto_cluster(matrix):
        best, best_s = None, -2
        for k in range(2, min(9, len(matrix))):
            lab = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(matrix)
            s = silhouette_score(matrix, lab, metric="cosine")
            if s > best_s:
                best_s, best = s, (k, lab)
        return best

    for axis, key_fn in [
        ("技术路线轴（研究方法句）", lambda d: d["研究方法"] or [d["name"]]),
        ("应用场景轴（背景+目的句+题名）", lambda d: d["研究背景"] + d["研究目的"] + [d["name"]]),
    ]:
        matrix = np.asarray([vec(key_fn(d)) for d in docs])
        k, labels = auto_cluster(matrix)
        print(f"\n===== {axis} | 自动 k={k}（轮廓最优）=====")
        clusters = {}
        for d, lab in zip(docs, labels):
            clusters.setdefault(int(lab), []).append(d["name"][:20])
        for lab in sorted(clusters):
            print(f"  簇{lab + 1}（{len(clusters[lab])}篇）:")
            for name in clusters[lab]:
                print(f"    - {name}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/root/autodl-tmp/datasets/ch_papers")
