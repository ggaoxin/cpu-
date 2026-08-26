"""CLC（中图分类法）RAG 检索器。

加载句向量编码器 + clc_meta 元数据 + 向量矩阵，提供
``retrieve(title, abstract, keywords, k)`` 返回 top-K 候选 CLC 条目。

设计要点：
- **编码器无关**：优先使用 bge-large 大向量索引（若已构建于
  ``clc_index_large/``，1024 维，recall 更高）；否则回退到 bge-small
  原生 RAG（512 维）。两套向量都与 ``clc_meta.json`` 按顺序一一对应。
- **防幻觉**：检索器只返回知识库中真实存在的条目，分类号 / 名称 / 路径
  全部从 ``clc_meta`` 复制，绝不由模型生成或拼接。
- **余弦相似度**：向量已归一化，点积即余弦；12468 条用 numpy 矩阵乘即可，
  无需 faiss。
- bge 系列检索需对查询加前缀 ``为这个句子生成表示以用于检索相关文章：``。

**路径可参数化（用户上传 CLC 资源建库后用 for_path 加载）**：
- 内置单例 ``clc_retriever`` 读 ``rag_store/clc_rag/``（默认）；
- 用户库经 ``CLCRetriever.for_path(storage_uri)`` 加载，按 LRU 缓存 max N 个实例，
  驱逐时释放向量矩阵（encoder 类级共享不释放，防多实例重复 load 爆 GPU）。
"""
from __future__ import annotations

import gc
import json
import logging
import os
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---- 路径（可由环境变量覆盖；默认 PROJECT_ROOT 相对，项目自包含）----
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RAG_STORE = os.environ.get(
    "CLC_RAG_DIR", os.path.join(_PROJECT_ROOT, "rag_store", "clc_rag"))
_LARGE_DIR = os.environ.get(
    "CLC_LARGE_DIR", os.path.join(_RAG_STORE, "clc_index_large"))
_M3_DIR = os.environ.get(
    "CLC_M3_DIR", os.path.join(_RAG_STORE, "clc_index_m3"))
_META_FILE = os.path.join(_RAG_STORE, "clc_meta_full.json")
_SMALL_VECTORS = os.path.join(_RAG_STORE, "clc_vectors.npy")  # 旧 12468 小向量（仅 large 缺失时回退）

_BGE_SMALL_PATH = os.environ.get(
    "BGE_SMALL_PATH", os.path.join(_PROJECT_ROOT, "models", "bge-small-zh-v1.5"))
_BGE_LARGE_PATH = os.environ.get(
    "BGE_LARGE_PATH", os.path.join(_PROJECT_ROOT, "models", "bge-large-zh-v1.5"))
_BGE_M3_PATH = os.environ.get(
    "BGE_M3_PATH", os.path.join(_PROJECT_ROOT, "models", "bge-m3"))

# bge 检索查询前缀
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

# 用户库 LRU 缓存上限（env 可覆盖；阶段2 改动点7 统一到 settings）
_USER_CACHE_MAX = max(1, int(os.environ.get("CLC_USER_CACHE_MAX", "4")))


class CLCRetriever:
    """CLC 知识库检索器（懒加载，线程安全；内置单例或 for_path 用户库实例）。"""

    # 类级共享 encoder 缓存：所有实例（内置 + 用户库）复用同一 encoder，
    # 防多实例重复 SentenceTransformer 加载爆 GPU（bge-large~1.3G + bge-m3~2.3G）。
    _ENCODERS: Dict[str, Any] = {}
    _ENCODER_LOCK = Lock()
    # 用户库 LRU 缓存：max N 个实例，驱逐时释放向量矩阵（encoder 类级共享不释放）。
    _USER_CACHE: "OrderedDict[str, CLCRetriever]" = OrderedDict()
    _USER_CACHE_LOCK = Lock()

    def __init__(
        self,
        meta_file: Optional[str] = None,
        large_dir: Optional[str] = None,
        m3_dir: Optional[str] = None,
        small_vectors: Optional[str] = None,
    ) -> None:
        self._lock = Lock()
        self._loaded = False
        self._meta: List[Dict[str, Any]] = []
        self._code_index: Dict[str, Dict[str, Any]] = {}  # clc_code -> entry
        self._code_set: set = set()
        self._vectors: Optional[np.ndarray] = None  # (N, D) 已归一化，bge-large-zh
        self._encoder = None
        self._encoder_name = ""
        self._dim = 0
        # 跨语言（bge-m3）索引，供 ac_en 英文query↔中文CLC 检索，懒加载
        self._m3_loaded = False
        self._m3_vectors: Optional[np.ndarray] = None
        self._m3_encoder = None
        # 实例路径（默认内置库）
        self._meta_file = meta_file or _META_FILE
        self._large_dir = large_dir or _LARGE_DIR
        self._m3_dir = m3_dir or _M3_DIR
        self._small_vectors = small_vectors or _SMALL_VECTORS

    # ------------------------------------------------------------------ #
    @classmethod
    def _get_encoder(cls, enc_path: str) -> Any:
        """类级共享 encoder（首次建、所有实例复用；防多实例重复 load 爆 GPU）。"""
        with cls._ENCODER_LOCK:
            enc = cls._ENCODERS.get(enc_path)
            if enc is None:
                from sentence_transformers import SentenceTransformer
                device = os.environ.get("BGE_DEVICE", "cuda" if _gpu_available() else "cpu")
                enc = SentenceTransformer(enc_path, device=device)
                cls._ENCODERS[enc_path] = enc
                logger.info("encoder 加载共享缓存：%s device=%s dim=%d",
                            os.path.basename(enc_path), device,
                            enc.get_sentence_embedding_dimension())
            return enc

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load()
            self._loaded = True

    def _load(self) -> None:
        # 1. 元数据
        with open(self._meta_file, encoding="utf-8") as f:
            self._meta = json.load(f)
        self._code_index = {e["clc_code"]: e for e in self._meta}
        self._code_set = set(self._code_index.keys())
        logger.info("CLC 元数据加载：%d 条（来源 %s）", len(self._meta), self._meta_file)

        # 2. 选择向量源 + 对应编码器（优先 large fullpath 变体）
        #    fullpath 编码了层级路径（如 "T 工业技术 > TM 电工技术 > TM7 输配电工程"），
        #    给检索更丰富的学科上下文，recall 高于 ragtext 变体。
        large_vec = os.path.join(self._large_dir, "clc_vectors_large_fullpath.npy")
        if os.path.exists(large_vec) and os.path.exists(_BGE_LARGE_PATH):
            self._vectors = np.load(large_vec).astype(np.float32)
            self._encoder_name = "bge-large-zh-v1.5"
            enc_path = _BGE_LARGE_PATH
        else:
            self._vectors = np.load(self._small_vectors).astype(np.float32)
            self._encoder_name = "bge-small-zh-v1.5"
            enc_path = _BGE_SMALL_PATH

        # 归一化兜底（防向量未归一化）
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._vectors /= norms
        self._dim = self._vectors.shape[1]
        logger.info("CLC 向量加载：%s shape=%s 编码器=%s",
                    os.path.basename(large_vec) if self._encoder_name.startswith("bge-large")
                    else os.path.basename(self._small_vectors),
                    self._vectors.shape, self._encoder_name)

        # 3. 编码器（类级共享缓存，避免无 GPU 环境启动报错）
        self._encoder = self._get_encoder(enc_path)
        got = self._encoder.get_sentence_embedding_dimension()
        if got != self._dim:
            raise RuntimeError(
                f"编码器维度 {got} 与向量维度 {self._dim} 不一致（编码器={self._encoder_name}）"
            )
        logger.info("编码器就绪：%s dim=%d", self._encoder_name, got)

    def _ensure_m3_loaded(self) -> None:
        """懒加载 bge-m3 跨语言索引（英文query↔中文CLC）。"""
        if self._m3_loaded:
            return
        with self._lock:
            if self._m3_loaded:
                return
            m3_vec = os.path.join(self._m3_dir, "clc_vectors_m3_fullpath.npy")
            self._m3_vectors = np.load(m3_vec).astype(np.float32)
            norms = np.linalg.norm(self._m3_vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._m3_vectors /= norms
            self._m3_encoder = self._get_encoder(_BGE_M3_PATH)
            got = self._m3_encoder.get_sentence_embedding_dimension()
            if got != self._m3_vectors.shape[1]:
                raise RuntimeError(
                    f"bge-m3 编码器维度 {got} 与向量维度 {self._m3_vectors.shape[1]} 不一致"
                )
            logger.info("bge-m3 跨语言索引就绪：shape=%s dim=%d（来源 %s）",
                        self._m3_vectors.shape, self._m3_vectors.shape[1], self._m3_dir)
            self._m3_loaded = True

    # ------------------------------------------------------------------ #
    @classmethod
    def _index_dir_for(cls, storage_uri: str) -> Path:
        """从 storage_uri 推导用户库索引目录。

        ``_store_uploaded_resource`` 落盘 ``{digest16}_{name}.json``，
        异步建索引把 ``clc_meta_full.json`` / ``clc_index_large`` / ``clc_index_m3``
        建在 ``{parent}/{digest16}/`` 下。
        """
        p = Path(storage_uri)
        digest = p.name.split("_", 1)[0] if "_" in p.name else p.stem
        return p.parent / digest

    @classmethod
    def for_path(cls, storage_uri: str) -> "CLCRetriever":
        """按用户库 storage_uri 加载检索器（LRU 缓存 max N，驱逐释放向量矩阵）。

        调用方需先 probe manifest 确认索引已建；for_path 不 probe，
        加载失败抛异常由调用方回退内置单例。
        """
        index_dir = cls._index_dir_for(storage_uri)
        key = str(index_dir)
        with cls._USER_CACHE_LOCK:
            if key in cls._USER_CACHE:
                cls._USER_CACHE.move_to_end(key)
                return cls._USER_CACHE[key]
            while len(cls._USER_CACHE) >= _USER_CACHE_MAX:
                _, old = cls._USER_CACHE.popitem(last=False)
                old._release_vectors()
            inst = cls(
                meta_file=str(index_dir / "clc_meta_full.json"),
                large_dir=str(index_dir / "clc_index_large"),
                m3_dir=str(index_dir / "clc_index_m3"),
            )
            inst._ensure_loaded()  # 触发加载（失败抛异常，不入缓存）
            cls._USER_CACHE[key] = inst
            return inst

    def _release_vectors(self) -> None:
        """释放向量矩阵（LRU 驱逐时调；encoder 类级共享不释放）。"""
        self._vectors = None
        self._m3_vectors = None
        self._m3_loaded = False
        self._loaded = False
        gc.collect()

    # ------------------------------------------------------------------ #
    def retrieve(
        self,
        title: str = "",
        abstract: str = "",
        keywords: Optional[List[str]] = None,
        k: int = 10,
        cross_lingual: bool = False,
    ) -> List[Dict[str, Any]]:
        """检索 top-K 候选 CLC 条目。

        Args:
            title:    文献标题。
            abstract: 文献摘要（不参与检索 query——实测摘要方法细节会淹没主题信号，
                      recall 下降；摘要仅供 LLM 分类推理，见 semantic_service）。
            keywords: 关键词列表。
            k:        返回候选数。
            cross_lingual: True 用 bge-m3 多语言索引（英文query↔中文CLC，ac_en 用）；
                           False 用 bge-large-zh（中文，ac_zh 用）。
        Returns:
            候选列表，每项含 clc_code/clc_name/classification_path/path_codes/
            path_names/rag_entry_id/rank/score，按相似度降序。
        """
        self._ensure_loaded()
        if cross_lingual:
            self._ensure_m3_loaded()
            vectors, encoder = self._m3_vectors, self._m3_encoder
            prefix = ""  # bge-m3 dense 无需 query 前缀
        else:
            vectors, encoder = self._vectors, self._encoder
            prefix = QUERY_PREFIX
        query = self._build_query(title, keywords or [], abstract)
        qv = encoder.encode(
            [prefix + query], normalize_embeddings=True,
            show_progress_bar=False,
        )[0].astype(np.float32)

        scores = vectors @ qv  # (N,) 余弦
        k = min(k, len(self._meta))
        # argpartition 取 top-k 再排序
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]

        cands: List[Dict[str, Any]] = []
        for rank, i in enumerate(idx, start=1):
            e = self._meta[int(i)]
            cands.append({
                "clc_code": e["clc_code"],
                "clc_name": e["clc_name"],
                "classification_path": e["full_path"],
                "path_codes": e["path_codes"],
                "path_names": e["path_names"],
                "rag_entry_id": e["id"],
                "rank": rank,
                "score": float(scores[int(i)]),
            })
        return cands

    @staticmethod
    def _build_query(title: str, keywords: List[str], abstract: str = "") -> str:
        """优先使用标题和关键词；二者都缺失时才用 text/摘要兜底。"""
        parts = [p.strip() for p in (title,) if p and p.strip()]
        kw = " ".join(k.strip() for k in keywords if k and k.strip())
        if kw:
            parts.append(kw)
        if not parts and abstract and abstract.strip():
            parts.append(abstract.strip()[:1200])
        return " ".join(parts) if parts else " "

    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """按 clc_code 精确查找元数据条目；不存在返回 None（用于后置校验防幻觉）。"""
        self._ensure_loaded()
        return self._code_index.get((code or "").strip())

    def children(self, code: str) -> List[Dict[str, Any]]:
        """返回某分类号的直接子条目（用于二阶段层级细化）。"""
        self._ensure_loaded()
        code = (code or "").strip()
        return [e for e in self._meta if e.get("parent_code") == code]

    def resolve_code(self, code: str) -> Optional[Dict[str, Any]]:
        """解析分类号到知识库中真实存在的条目（防幻觉 + 对齐知识库粒度）。

        GLM 常提出真实 CLC 但知识库未收录的细码（如 TM713），策略：
        1. 精确命中 → 返回；
        2. 否则去掉小数点后段，再逐字符去尾，找最长存在前缀（TM713→TM71→TM7）；
        3. 仍无 → 返回 None（由调用方回退检索）。
        """
        self._ensure_loaded()
        code = (code or "").strip()
        if not code:
            return None
        if code in self._code_set:
            return self._code_index[code]
        cands = []
        if "." in code:
            cands.append(code.split(".")[0])
        cur = code
        while cur:
            cur = cur[:-1]
            cands.append(cur)
        for c in cands:
            if c and c in self._code_set:
                return self._code_index[c]
        return None

    @property
    def encoder_name(self) -> str:
        self._ensure_loaded()
        return self._encoder_name

    @property
    def entry_count(self) -> int:
        self._ensure_loaded()
        return len(self._meta)


def _gpu_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:  # noqa: BLE001
        return False


# 内置单例（读 rag_store/clc_rag/，现有 import 调用零改动）
clc_retriever = CLCRetriever()
