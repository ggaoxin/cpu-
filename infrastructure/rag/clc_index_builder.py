"""CLC 向量索引构建（供建索引脚本与用户上传资源建库共用）。

从 scripts/encode_full_index.py 与 scripts/encode_m3_index.py 抽出的核心逻辑：
- build_index：用 bge-large 编码 full_path+rag_text（batch 64）、bge-m3 编码 full_path（batch 32），
  归一化存盘 + manifest。输出文件名与目录结构匹配 clc_retriever._load/_ensure_m3_loaded 的读取路径。

设计要点：
- base_dir 为库根目录，内含 clc_meta_full.json；large 向量存 base_dir/clc_index_large/，
  m3 向量存 base_dir/clc_index_m3/——与内置库（rag_store/clc_rag/）布局一致，供 for_path 复用；
- encoder 在 builder 内独立 load（建库是离线/异步任务，不在请求热路径，无 OOM 风险）；
  请求热路径的 encoder 共享缓存由 clc_retriever 类级管理（阶段2）；
- build_large/build_m3 可独立开关：scripts 调用行为不变（encode_full 只建 large，encode_m3 只建 m3），
  用户库异步建库则 build_large=build_m3=True 一次建全；
- progress_cb(progress, stage) 供异步任务更新进度（0-100），脚本调用不传（None）。
"""
from __future__ import annotations

import json
import os
import time
from typing import Callable, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from config.settings import settings

# bge-large 检索查询前缀（与 clc_retriever.QUERY_PREFIX 一致）
_LARGE_PREFIX = "为这个句子生成表示以用于检索相关文章："


def _gpu_device() -> str:
    return os.environ.get("BGE_DEVICE", "cuda")


def build_index(
    base_dir: str,
    *,
    build_large: bool = True,
    build_m3: bool = True,
    large_model_path: Optional[str] = None,
    m3_model_path: Optional[str] = None,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> None:
    """构建 CLC 向量索引。

    目录布局（与内置库 rag_store/clc_rag/ 一致，供 clc_retriever.for_path 复用）::

        {base_dir}/
            clc_meta_full.json          # 建库前应已存在
            clc_index_large/             # build_large=True
                clc_vectors_large_fullpath.npy   # 被 _load 主用
                clc_vectors_large_ragtext.npy     # 备用（_load 不读，保留生成）
                manifest.json
            clc_index_m3/                # build_m3=True
                clc_vectors_m3_fullpath.npy      # 被 _ensure_m3_loaded 主用
                manifest.json

    Args:
        base_dir: 库根目录（内含 clc_meta_full.json）。
        build_large: 是否建 bge-large 索引（full_path + rag_text）。
        build_m3: 是否建 bge-m3 跨语言索引（full_path）。
        large_model_path / m3_model_path: 覆盖默认编码器路径（默认取 settings.BGE_LARGE_PATH/BGE_M3_PATH）。
        progress_cb: 进度回调 (progress: 0-100, stage: str)，异常不影响建库。
    """
    meta_path = os.path.join(base_dir, "clc_meta_full.json")
    large_dir = os.path.join(base_dir, "clc_index_large")
    m3_dir = os.path.join(base_dir, "clc_index_m3")

    def _cb(progress: float, stage: str) -> None:
        if progress_cb:
            try:
                progress_cb(progress, stage)
            except Exception:  # noqa: BLE001
                pass  # 进度回调异常不影响建库

    _cb(2.0, "load_meta")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    n = len(meta)
    _cb(5.0, f"meta_loaded:{n}")

    # ---- bge-large：full_path + rag_text ----
    if build_large:
        os.makedirs(large_dir, exist_ok=True)
        large_path = large_model_path or str(settings.BGE_LARGE_PATH)
        _cb(8.0, "load_large_encoder")
        model = SentenceTransformer(large_path, device=_gpu_device())
        large_dim = model.get_sentence_embedding_dimension()
        large_manifest = {
            "encoder": "bge-large-zh-v1.5", "dim": large_dim, "entry_count": n,
            "meta_file": "clc_meta_full.json", "normalize_embeddings": True,
            "query_prefix": _LARGE_PREFIX,
            "note": "向量与 clc_meta_full.json 按顺序一一对应；查询需加 query_prefix",
        }
        for label, field in [("fullpath", "full_path"), ("ragtext", "rag_text")]:
            texts = [e[field] for e in meta]
            t = time.time()
            V = model.encode(texts, batch_size=64, normalize_embeddings=True,
                             show_progress_bar=True)
            np.save(os.path.join(large_dir, f"clc_vectors_large_{label}.npy"),
                    V.astype(np.float32))
            _cb(50.0 if label == "fullpath" else 70.0,
                f"large_{label}_encoded:{time.time()-t:.1f}s")
        json.dump(large_manifest,
                  open(os.path.join(large_dir, "manifest.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        del model  # 释放显存给 m3
        _cb(72.0 if build_m3 else 100.0, "large_done")

    # ---- bge-m3：full_path（跨语言）----
    if build_m3:
        os.makedirs(m3_dir, exist_ok=True)
        m3_path = m3_model_path or str(settings.BGE_M3_PATH)
        base_progress = 72.0 if build_large else 8.0
        _cb(base_progress, "load_m3_encoder")
        m3_model = SentenceTransformer(m3_path, device=_gpu_device())
        m3_dim = m3_model.get_sentence_embedding_dimension()
        texts = [e["full_path"] for e in meta]
        t = time.time()
        V = m3_model.encode(texts, batch_size=32, normalize_embeddings=True,
                           show_progress_bar=True)
        np.save(os.path.join(m3_dir, "clc_vectors_m3_fullpath.npy"), V.astype(np.float32))
        m3_manifest = {
            "encoder": "bge-m3", "dim": m3_dim, "entry_count": n,
            "meta_file": "clc_meta_full.json", "normalize_embeddings": True,
            "field": "full_path", "note": "多语言跨语言索引；bge-m3 dense 无需 query 前缀",
        }
        json.dump(m3_manifest,
                  open(os.path.join(m3_dir, "manifest.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        _cb(100.0, "m3_done")
