"""bge-m3 编码器单例（供深度聚类等需要文献向量编码的功能复用）。

懒加载，线程安全。复用项目已有的 bge-m3 模型权重，不耦合 clc_retriever 的索引逻辑。
"""
from __future__ import annotations

import logging
import os
import threading

import numpy as np

logger = logging.getLogger(__name__)

_BGE_M3_PATH = os.environ.get(
    "BGE_M3_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "models", "bge-m3"))


def _gpu_available() -> bool:
    try:
        import torch  # noqa: PLC0415
        return torch.cuda.is_available()
    except Exception:  # noqa: BLE001
        return False


class M3Encoder:
    """bge-m3 句向量编码器（单例）。"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._model = None
                    cls._instance._loaded = False
        return cls._instance

    def _ensure_loaded(self):
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            device = os.environ.get("BGE_DEVICE", "cuda" if _gpu_available() else "cpu")
            logger.info("加载 bge-m3 编码器：%s device=%s", _BGE_M3_PATH, device)
            self._model = SentenceTransformer(_BGE_M3_PATH, device=device)
            self._loaded = True

    def encode(self, texts: list[str]) -> np.ndarray:
        """编码文本列表，返回 L2 归一化的向量矩阵 (N, 1024)。"""
        self._ensure_loaded()
        vecs = self._model.encode(
            texts, batch_size=16, show_progress_bar=False,
            normalize_embeddings=True, convert_to_numpy=True,
        ).astype(np.float32)
        return vecs


m3_encoder = M3Encoder()
