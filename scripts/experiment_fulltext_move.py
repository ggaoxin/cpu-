#!/usr/bin/env python3
"""实验：全文版语步导向双轴聚类（v2-全文）——基金语步式切块+并发提取。

设计（用户 2026-09-06）：
  PDF 全文 → 按字数切块（基金语步式 map-reduce：短文直送、长文 CHUNK_SIZE 块）
  → 并发逐块 LLM 提取三类语步句：研究背景（立项依据）、研究目的（研究目标）、
    研究方法（技术实施方案）
  → 全文汇总：方法句集合 / 背景目的句集合
  → bge 向量聚合 → 技术轴聚类（方法相似）/ 应用轴聚类（场景相似）

用法（真实 PDF 小样本定性验证 + 聚类合理性）：
    python3 scripts/experiment_fulltext_move.py /root/autodl-tmp/pdf
独立实验，不改动生产代码。
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHUNK_SIZE = 6000        # 全文切块大小（字）——提取用块可比基金汇总块小（句级信息密度需求）
MAX_WORKERS = 6          # 并发块处理

EXTRACT_SYSTEM = (
    "你是科技文献语步提取专家。从给定文献片段中逐字摘录三类句子（保留原文）：\n"
    "- 研究背景：领域现状、问题由来、前人工作不足（对应立项依据）\n"
    "- 研究目的：本文要解决什么问题、达成什么目标（对应研究目标）\n"
    "- 研究方法：采用的数据、模型、算法、实验手段、技术路线（对应技术实施方案）\n"
    "只摘录句子原文，不得改写；片段中没有的类别输出空数组。只输出JSON："
    '{"研究背景":["句子",...],"研究目的":["句子",...],"研究方法":["句子",...]}'
)


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list:
    """按字数切块（基金语步式；块间留 200 字重叠防句子截断）。"""
    text = text.strip()
    if len(text) <= size:
        return [text]
    chunks, step, i = [], size - 200, 0
    while i < len(text):
        chunks.append(text[i:i + size])
        i += step
    return chunks


def extract_chunk(glm, chunk: str) -> dict:
    try:
        raw = glm.chat_json(EXTRACT_SYSTEM, f"文献片段：\n{chunk}",
                            temperature=0.0, timeout=120.0, max_tokens=3000)
    except Exception:  # noqa: BLE001
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    out = {}
    for key in ("研究背景", "研究目的", "研究方法"):
        values = raw.get(key) if isinstance(raw, dict) else None
        out[key] = [str(v).strip() for v in values if str(v).strip()] if isinstance(values, list) else []
    return out


def extract_fulltext(glm, text: str) -> dict:
    """全文 → 切块 → 并发提取 → 汇总去重。"""
    chunks = chunk_text(text)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(lambda c: extract_chunk(glm, c), chunks))
    merged = {"研究背景": [], "研究目的": [], "研究方法": []}
    for part in results:
        for key in merged:
            merged[key].extend(part.get(key) or [])
    for key in merged:
        merged[key] = list(dict.fromkeys(merged[key]))[:20]
    return merged, len(chunks)


def main():
    pdf_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/root/autodl-tmp/pdf")
    pdfs = sorted(p for p in pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"目录无 PDF: {pdf_dir}")
        return

    from infrastructure.document_parser.mineru_reader import process_to_text
    from infrastructure.rag.m3_encoder import m3_encoder
    from infrastructure.llm.glm_client import glm_client

    print(f"处理 {len(pdfs)} 篇 PDF 全文...\n")
    docs = []
    for pdf in pdfs:
        text = (process_to_text(str(pdf)).get("full_text") or "").strip()
        if not text:
            print(f"✗ {pdf.name}: 全文解析为空")
            continue
        merged, n_chunks = extract_fulltext(glm_client, text)
        docs.append({"file": "".join(c for c in pdf.name if not 0xD800 <= ord(c) <= 0xDFFF), "chars": len(text), "chunks": n_chunks, **merged})
        print(f"✓ {pdf.name}（{len(text)}字/{n_chunks}块）: "
              f"方法{len(merged['研究方法'])}句 背景{len(merged['研究背景'])}句 目的{len(merged['研究目的'])}句")

    out_path = Path("/tmp/fulltext_moves.json")
    out_path.write_text(json.dumps(docs, ensure_ascii=True, indent=2), encoding="utf-8")  # 文件名含代理字符，ASCII 转义写入
    print(f"\n提取明细已存: {out_path}")

    # ---- 打印每篇的方法句/背景目的句样例（人工核对抽取质量）----
    for d in docs:
        print(f"\n===== {d['file'][:36]} =====")
        print("  [方法句]", " | ".join(s[:38] for s in d["研究方法"][:3]) or "（空）")
        print("  [背景句]", " | ".join(s[:38] for s in d["研究背景"][:2]) or "（空）")
        print("  [目的句]", " | ".join(s[:38] for s in d["研究目的"][:2]) or "（空）")

    # ---- 双轴向量与小样本聚类（语义合理性观察，无金标签）----
    if len(docs) >= 4:
        def axis_vector(key_list):
            vecs = []
            for d in docs:
                sents = sum((d[k] for k in key_list), [])
                if not sents:
                    sents = [d["file"]]
                v = np.asarray(m3_encoder.encode(sents)).mean(axis=0)
                vecs.append(v / max(np.linalg.norm(v), 1e-9))
            return np.asarray(vecs)

        from sklearn.cluster import AgglomerativeClustering
        for axis, keys, label in [
            ("技术路线（方法句）", ["研究方法"], "方法相似"),
            ("应用场景（背景+目的句）", ["研究背景", "研究目的"], "场景相似"),
        ]:
            matrix = axis_vector(keys)
            k = max(2, len(docs) // 2)
            labels = AgglomerativeClustering(n_clusters=min(k, len(docs) - 1), metric="cosine", linkage="average").fit_predict(matrix)
            groups = {}
            for d, lab in zip(docs, labels):
                groups.setdefault(int(lab), []).append(d["file"][:16])
            print(f"\n===== {axis} 聚类（{label}）=====")
            for lab, files in sorted(groups.items()):
                print(f"  簇{lab + 1}: {files}")


if __name__ == "__main__":
    main()
