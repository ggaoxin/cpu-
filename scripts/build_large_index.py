"""在 GPU 服务器上用 bge-large-zh-v1.5 重建 CLC 向量索引。

用法（在 GPU 服务器上）：
  1. 把本脚本 + rag_store/clc_rag/clc_meta.json + 两个数据集 json 拷到服务器
     （数据集可选，仅用于测 recall；不带就只编码不测）
  2. 安装依赖：pip install sentence_transformers transformers torch numpy
  3. 下载 bge-large-zh-v1.5（ModelScope：snapshot_download('BAAI/bge-large-zh-v1.5') 或 HF）
  4. 修改下面 MODEL_PATH / META_FILE / DATASETS 路径
  5. python build_large_index.py
  6. 把生成的 clc_vectors_large_fullpath.npy / clc_vectors_large_ragtext.npy / manifest.json 给我

输出向量维度 1024，归一化，与 clc_meta.json 一一对应（按顺序）。
"""
import json
import time
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from config.settings import settings

# ===== 改这几行路径 =====
MODEL_PATH = str(settings.BGE_LARGE_PATH)  # bge-large 模型目录
META_FILE = str(settings.CLC_RAG_DIR / "clc_meta.json")                            # 12468 条 CLC 元数据
OUT_DIR = str(settings.CLC_INDEX_LARGE)          # 输出目录
# 数据集（可选，用于 recall 测试）
PAPERS_FILE = str(settings.DATA_DIR / "random_50_chinese_papers.json")
GOLD_FILE = str(settings.DATA_DIR / "random_50_chinese_papers_clc_classification.json")
PREFIX = "为这个句子生成表示以用于检索相关文章："  # bge 检索查询前缀
# ========================

os.makedirs(OUT_DIR, exist_ok=True)
print("加载编码器...", flush=True)
model = SentenceTransformer(MODEL_PATH, device="cuda")
print("dim =", model.get_sentence_embedding_dimension(), flush=True)

meta = json.load(open(META_FILE, encoding="utf-8"))
print(f"CLC 条目数: {len(meta)}", flush=True)

manifest = {
    "encoder": "bge-large-zh-v1.5",
    "dim": model.get_sentence_embedding_dimension(),
    "entry_count": len(meta),
    "normalize_embeddings": True,
    "query_prefix": PREFIX,
    "note": "向量与 clc_meta.json 按顺序一一对应；查询需加 query_prefix",
}

# 可选：recall 测试
def make_recall_test(V):
    if not (os.path.exists(PAPERS_FILE) and os.path.exists(GOLD_FILE)):
        print("  (未找到数据集，跳过 recall 测试)", flush=True)
        return
    papers = json.load(open(PAPERS_FILE, encoding="utf-8"))
    gold = json.load(open(GOLD_FILE, encoding="utf-8"))
    def rec(K, formula):
        hit = 0
        for p, g in zip(papers, gold):
            kw = " ".join(k["ch_name"] for k in p["keywords"])
            v = model.encode([PREFIX + formula(p, kw)], normalize_embeddings=True)[0]
            top = np.argsort(-(V @ v))[:K]
            if g["main_classification"]["clc_code"] in {meta[i]["clc_code"] for i in top}:
                hit += 1
        return hit / len(papers)
    f = lambda p, kw: p["ch_name"] + " " + p["ch_abstract"]
    print(f"  recall@3={rec(3,f):.2f} @5={rec(5,f):.2f} @10={rec(10,f):.2f}", flush=True)

for label, field in [("ragtext", "rag_text"), ("fullpath", "full_path")]:
    texts = [e[field] for e in meta]
    t = time.time()
    V = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    print(f"[{label}] 编码 {time.time()-t:.1f}s shape={V.shape}", flush=True)
    out = os.path.join(OUT_DIR, f"clc_vectors_large_{label}.npy")
    np.save(out, V)
    print(f"  已保存 {out}", flush=True)
    make_recall_test(V)

json.dump(manifest, open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("DONE. 把", OUT_DIR, "下的 3 个文件给我即可。", flush=True)
