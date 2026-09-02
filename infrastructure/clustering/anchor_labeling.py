"""深度聚类锚点标注：人工标注类目对小样本聚类的主题锚定。

问题：深度聚类是纯数据驱动的——小样本(4~10篇)时聚类算法发现不了细粒度
结构,自由聚类的主题必然过于宽泛。

方案：把 1000 篇人工标注文献(训练样本 + 类目标签答案)作为**语义锚点库**。
待聚类文献与锚点库做 bge-m3 余弦近邻匹配,将文献/类簇锚定到人工标注的
类目标签(经主题映射表转为可读中文主题名),为小样本聚类注入监督先验。

- 文档级：每篇文献 top-k 近邻锚点按相似度加权投票 → 锚定类目
- 簇级：簇内成员的锚定结果聚合(加权多数) → 簇的锚定主题
- 置信门控：最佳相似度低于阈值时不强行归类,保留自由聚类主题
- 组合分门控：best + (best − 全库均值) 同时达标才锚定。绝对阈值挡不住
  "同方法、跨领域"的误锚——实测一篇电商推荐算法论文与"医学影像 AI"gold
  的相似度 0.55(≥0.45 门槛)但因同为深度学习方法而通过；其对全库背景均值
  0.44 的突出度远低于领域内文献(组合分 0.67 vs 领域内 0.78~1.08)，
  组合分下限把这类"均匀都不像"的文献挡在门外、保留自由聚类。

锚点向量首次构建后缓存到 rag_store/deep_clustering_anchor/(1000 篇纯 CPU
编码约数分钟,仅一次),后续请求秒级加载。主题映射表带每类目
direct_match_threshold,取其与全局下限的较大者做采纳门槛。
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = settings.PROJECT_ROOT
_TOPIC_MAP_FILES = {
    "technical": _PROJECT_ROOT / "rules" / "deep_clustering" / "mappings" / "technical_route_topic_map.json",
    "application": _PROJECT_ROOT / "rules" / "deep_clustering" / "mappings" / "application_scenario_topic_map.json",
}
_ANCHOR_CACHE_DIR = _PROJECT_ROOT / "rag_store" / "deep_clustering_anchor"
_DEFAULT_MATCH_THRESHOLD = 0.45  # bge-m3 余弦相似度采纳下限(类目表自带阈值时取较大者)
# 组合分下限：best_sim + (best_sim − 全库均值)。单独的绝对阈值无法区分
# "领域内弱匹配"与"同方法跨领域"(如序列建模论文对信号分类 gold 的方法相似)，
# 组合分同时考察"绝对接近程度"与"相对背景的突出程度"，实测领域内 0.78~1.08、
# 跨领域误锚样本 0.67，0.70 下限双边余量均衡。
_MIN_COMBINED_MATCH = 0.70
# 内置锚点库槽位：用户未上传标注资源时的默认库；用户上传后以内置为辅
# （用户库达门槛即采用，内置仅在用户未达门槛时补位）。
# 替换内置数据集 = 用新文件覆盖 anchor_gold_current.json，无需改代码。
BUILTIN_GOLD_PATH = _PROJECT_ROOT / "rules" / "deep_clustering" / "gold" / "anchor_gold_current.json"
# 质量保底裕度：用户库为主，但内置库绝对相似度超过用户库此值以上时反超。
# 用 best_sim 而非组合分做跨库比较——用户库通常稀疏（背景均值低→对比度
# 虚高），组合分跨库不可比；绝对相似度是公平口径。0 = 关闭保底。
BUILTIN_QUALITY_MARGIN = 0.10
# 低置信双候选：判别头 top-2 概率差小于此值时输出两个候选类目而非硬判一个。
# 全量校准（50,483 篇测试集）：胶着区 top-1 仅 73~78%，但 top-2 召回 92~94%——
# 双候选把胶着区的可用率抬到 9 成以上。primary 仍取 top-1，候选并列展示。
BORDERLINE_GAP = 0.10


def _gold_label_field(axis: str) -> str:
    return "technical_cluster_id" if axis == "technical" else "application_cluster_id"


# ---------- 判别头（边界仲裁）：在锚点库标签上训练的线性判别器 ----------
# 近邻投票只回答"谁在附近"，在相邻类目的边界区不会划线（实测 76.1%）；
# 判别头在 11.7 万已清洗标签上学习决策边界，仅对匹配结果的类目做仲裁
# （相似度证据、三道门槛、最近邻 gold 全部保持不变），实测 81.3%。
_HEAD_CACHE: Dict[str, Any] = {}
_HEAD_LOCK = threading.Lock()


def load_discriminative_head(axis: str = "technical") -> Optional[tuple]:
    """按轴懒加载判别头；缺失返回 None。

    technical → discriminative_head.pt；application → discriminative_head_application.pt。
    两轴类目体系不同，判别头必须与所选轴一致。
    """
    key = f"head_{axis}"
    with _HEAD_LOCK:
        if key in _HEAD_CACHE:
            return _HEAD_CACHE[key]
        filename = ("discriminative_head.pt" if axis == "technical"
                    else "discriminative_head_application.pt")
        path = _PROJECT_ROOT / "rules" / "deep_clustering" / "gold" / filename
        head = None
        if path.is_file():
            try:
                import torch  # noqa: PLC0415
                checkpoint = torch.load(path, map_location="cpu", weights_only=False)
                model = torch.nn.Linear(1024, len(checkpoint["classes"]))
                model.load_state_dict(checkpoint["state_dict"])
                model.eval()
                head = (model, list(checkpoint["classes"]))
                logger.info("判别头已加载（%s轴）：%d 类（边界仲裁启用）", axis, len(head[1]))
            except Exception:  # noqa: BLE001 - 判别头失败不影响近邻匹配主链路
                logger.warning("判别头加载失败（%s，回退纯近邻投票）", axis, exc_info=True)
                head = None
        _HEAD_CACHE[key] = head
        return head


def _anchor_text(title: str, abstract: str, keywords: Sequence[str]) -> str:
    """锚点侧文本配方：题名 + 摘要 + 关键词(两侧一致,保证向量可比)。"""
    parts = [str(title or "").strip(), str(abstract or "").strip()]
    kws = [str(k).strip() for k in (keywords or []) if str(k).strip()]
    if kws:
        parts.append("关键词：" + "；".join(kws[:10]))
    return "\n".join(p for p in parts if p)


def resolve_gold_path(resolved_resources: Optional[Dict[str, Any]]) -> Optional[Path]:
    """从 resolved_resources(训练样本/人工标注类目)解析 gold 数据文件路径。

    两个资源在交付包里指向同一份 1000 篇标注文件;任取其一。
    """
    if not isinstance(resolved_resources, dict):
        return None
    for field in ("manually_labeled_category_data", "training_samples"):
        descriptor = resolved_resources.get(field)
        uri = str((descriptor or {}).get("storage_uri") or "")
        if not uri:
            continue
        if uri.startswith("project://"):
            path = _PROJECT_ROOT / uri.removeprefix("project://")
        else:
            path = Path(uri)
        if path.is_file():
            return path
    return None


class GoldAnchorIndex:
    """人工标注文献锚点索引(按 gold 路径+轴 单例,向量缓存到磁盘)。"""

    _instances: Dict[tuple, "GoldAnchorIndex"] = {}
    _lock = threading.Lock()

    def __init__(self, gold_path: Path, axis: str):
        self._gold_path = gold_path
        self._axis = "technical" if axis == "technical" else "application"
        self._vectors: Optional[np.ndarray] = None
        self._labels: List[str] = []
        self._doc_ids: List[str] = []
        self._topic_names: Dict[str, str] = {}
        self._topic_thresholds: Dict[str, float] = {}
        self._loaded = False

    @classmethod
    def get(cls, gold_path: Path, axis: str) -> "GoldAnchorIndex":
        key = (str(gold_path.resolve()), axis)
        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = cls(gold_path, axis)
            return cls._instances[key]

    # ---------- 加载 / 构建 ----------

    def _cache_files(self) -> tuple[Path, Path]:
        stat = self._gold_path.stat()
        digest = hashlib.md5(
            f"{self._gold_path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{self._axis}".encode()
        ).hexdigest()[:16]
        return _ANCHOR_CACHE_DIR / f"anchors_{digest}.npy", _ANCHOR_CACHE_DIR / f"anchors_{digest}.json"

    def _load_topic_map(self) -> None:
        map_file = _TOPIC_MAP_FILES.get(self._axis)
        if not map_file or not map_file.is_file():
            logger.warning("锚点主题映射表缺失：%s（类目将以 ID 展示）", map_file)
            return
        rows = json.loads(map_file.read_text(encoding="utf-8"))
        for row in rows if isinstance(rows, list) else []:
            category_id = str(row.get("parent_category_id") or "").strip()
            if not category_id:
                continue
            if category_id not in self._topic_names:
                self._topic_names[category_id] = str(
                    row.get("topic_name_zh") or row.get("parent_label_zh") or category_id
                )
            try:
                thr = float(row.get("direct_match_threshold") or 0)
                if thr > 0:
                    self._topic_thresholds[category_id] = max(
                        thr, self._topic_thresholds.get(category_id, 0)
                    )
            except (TypeError, ValueError):
                pass

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return bool(self._labels)
        with GoldAnchorIndex._lock:
            if self._loaded:
                return bool(self._labels)
            rows = json.loads(self._gold_path.read_text(encoding="utf-8"))
            label_field = _gold_label_field(self._axis)
            texts, labels, doc_ids = [], [], []
            # 用户自建类目体系支持：gold 行自带类目中文名（如 technical_cluster_name）
            # 时优先于内置映射表——自定义类目 ID（如 UX01）也能显示中文名。
            row_topic_names: Dict[str, str] = {}
            name_field = f"{self._axis}_cluster_name"
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                label = str(row.get(label_field) or "").strip()
                if not label:
                    continue
                row_name = str(
                    row.get(name_field) or row.get("cluster_name") or row.get("topic_name") or ""
                ).strip()
                if row_name:
                    row_topic_names[label] = row_name
                text = _anchor_text(
                    row.get("ch_name") or row.get("title") or "",
                    row.get("ch_abstract") or row.get("abstract") or "",
                    row.get("keywords") or [],
                )
                if len(text.strip()) < 30:
                    continue
                labels.append(label)
                doc_ids.append(str(row.get("document_id") or f"GOLD_{index + 1:04d}"))
                texts.append(text)
            if not labels:
                self._loaded = True
                logger.warning("锚点库为空：%s（轴=%s）", self._gold_path.name, self._axis)
                return False
            self._labels = labels
            self._doc_ids = doc_ids
            self._load_topic_map()
            self._topic_names.update(row_topic_names)  # gold 行自带类目名优先

            vec_path, meta_path = self._cache_files()
            if vec_path.is_file() and meta_path.is_file():
                try:
                    self._vectors = np.load(vec_path)
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    if meta.get("labels") == labels and self._vectors.shape[0] == len(labels):
                        self._loaded = True
                        logger.info("锚点索引缓存命中：%d 篇 × 轴=%s", len(labels), self._axis)
                        return True
                    logger.warning("锚点索引缓存与 gold 不一致，重建")
                except Exception:  # noqa: BLE001
                    logger.warning("锚点索引缓存损坏，重建", exc_info=True)

            from infrastructure.rag.m3_encoder import m3_encoder
            logger.info("构建锚点索引：%d 篇 × 轴=%s（首次编码约数分钟）", len(texts), self._axis)
            self._vectors = m3_encoder.encode(texts)
            try:
                _ANCHOR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                np.save(vec_path, self._vectors)
                meta_path.write_text(
                    json.dumps({"labels": labels, "doc_ids": doc_ids}, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:  # noqa: BLE001
                logger.warning("锚点索引缓存写盘失败（不影响本次运行）", exc_info=True)
            self._loaded = True
            return True

    # ---------- 匹配 ----------

    def stats(self) -> Dict[str, Any]:
        """锚点库自描述信息：让"资源是否真正生效"可以在输出里直接核对。

        - anchor_library_size: 实际装进锚点库的文献数（行数≠库规模——缺类目
          标签或文本<30字的行会被跳过，这里暴露的是有效数）
        - category_count / categories: 覆盖的类目数与分布
        - unnamed_categories: 在主题映射表里查不到中文名的类目（锚定时会显示裸ID）
        """
        loaded = self._ensure_loaded()
        categories: Dict[str, int] = {}
        for label in self._labels:
            categories[label] = categories.get(label, 0) + 1
        unnamed = sorted({label for label in categories if label not in self._topic_names})
        if unnamed:
            logger.warning(
                "以下锚定类目在主题映射表中无中文名（锚定后将显示原始ID）：%s",
                ",".join(unnamed[:20]))
        return {
            "loaded": loaded,
            "gold_file": self._gold_path.name,
            "anchor_library_size": len(self._labels),
            "category_count": len(categories),
            "category_distribution": dict(sorted(categories.items(), key=lambda kv: -kv[1])),
            "unnamed_categories": unnamed[:20],
        }

    def match_documents(
        self, texts: Sequence[str], *, top_k: int = 10,
        threshold: float = _DEFAULT_MATCH_THRESHOLD,
        min_combined: Optional[float] = None,
        arbiter: Optional[tuple] = None,
    ) -> List[Optional[Dict[str, Any]]]:
        """逐篇文本与锚点库匹配,返回锚定结果(不达门槛为 None)。

        arbiter=(model, classes) 时启用判别头仲裁：类目在"近邻投票最优"与
        "判别器最优"之间取判别概率高者——仅改类目归属，相似度证据与门槛判定
        保持近邻口径。判别器给出的类目不在本库标签集内时忽略仲裁。
        """
        if not self._ensure_loaded() or self._vectors is None or not texts:
            return [None] * len(texts)
        from infrastructure.rag.m3_encoder import m3_encoder
        vectors = m3_encoder.encode(list(texts))
        sims = vectors @ self._vectors.T  # 双侧归一化,点积即余弦
        k = max(1, min(top_k, self._vectors.shape[0]))
        combined_floor = _MIN_COMBINED_MATCH if min_combined is None else float(min_combined)
        head_probs = None
        if arbiter is not None:
            try:
                import torch  # noqa: PLC0415
                model, classes = arbiter
                with torch.no_grad():
                    logits = model(torch.from_numpy(vectors))
                    probs = torch.softmax(logits, dim=1).numpy()
                head_probs = [{classes[i]: float(probs[r, i]) for i in range(len(classes))}
                              for r in range(len(probs))]
            except Exception:  # noqa: BLE001 - 仲裁失败回退纯近邻投票
                logger.warning("判别头仲裁失败（回退近邻投票）", exc_info=True)
                head_probs = None
        label_set = set(self._labels)
        results: List[Optional[Dict[str, Any]]] = []
        for position, row in enumerate(sims):
            top = np.argpartition(-row, k - 1)[:k]
            votes: Dict[str, float] = {}
            best_sim = float(row[top].max())
            for idx in top:
                votes[self._labels[int(idx)]] = votes.get(self._labels[int(idx)], 0.0) + float(row[idx])
            label = max(votes, key=votes.get)
            adopt = max(threshold, self._topic_thresholds.get(label, 0.0))
            score = round(float(votes[label] / k), 4)  # 归一到 0-1 的锚定置信
            background = float(row.mean())
            combined = best_sim + (best_sim - background)
            if best_sim < adopt or combined < combined_floor:
                logger.info(
                    "锚定不达门槛拒绝：best=%.4f(门槛%.4f) combined=%.4f(下限%.4f) 背景=%.4f",
                    best_sim, adopt, combined, combined_floor, background)
                results.append(None)
                continue
            arbiter_note = None
            if head_probs is not None:
                head_top = max(head_probs[position], key=head_probs[position].get)
                if head_top != label and head_top in label_set:
                    # 判别器在边界区改判：近邻结论保留在 nn_topic_* 供审计
                    arbiter_note = {
                        "nn_topic_id": label,
                        "nn_topic_name": self._topic_names.get(label, label),
                        "anchor_arbiter": "discriminative_head",
                        "head_probability": round(head_probs[position][head_top], 4),
                    }
                    label = head_top
            entry = {
                "anchored_topic_id": label,
                "anchored_topic_name": self._topic_names.get(label, label),
                "anchor_similarity": round(best_sim, 4),
                "anchor_confidence": score,
                "anchor_background": round(background, 4),
                "anchor_contrast": round(best_sim - background, 4),
                "nearest_gold_documents": [
                    {"document_id": self._doc_ids[int(i)], "similarity": round(float(row[i]), 4)}
                    for i in sorted(top, key=lambda j: -row[j])[:3]
                ],
            }
            if arbiter_note:
                entry.update(arbiter_note)
            # 低置信双候选：判别头 top-2 概率差小于 BORDERLINE_GAP 时并列输出两个类目
            if head_probs is not None:
                ranked = sorted(head_probs[position].items(), key=lambda kv: -kv[1])[:2]
                in_library = [(c, p) for c, p in ranked if c in label_set]
                if len(in_library) == 2 and in_library[0][0] == label and \
                        (in_library[0][1] - in_library[1][1]) < BORDERLINE_GAP:
                    entry["anchor_confidence_level"] = "borderline"
                    entry["candidate_topics"] = [
                        {"topic_id": c, "topic_name": self._topic_names.get(c, c),
                         "probability": round(p, 4)}
                        for c, p in in_library
                    ]
            results.append(entry)
        return results


def resolve_anchor_libraries(
    resolved_resources: Optional[Dict[str, Any]],
    *,
    use_builtin: bool = True,
) -> Dict[str, Optional[Path]]:
    """两级锚点资源解析：用户上传库为主力，内置库为辅（未上传则仅内置）。

    - user：用户选择/上传的标注资源（上传即为主力）
    - builtin：内置槽位 gold（默认启用，可用 use_builtin_anchor 关闭；
      用户库不达门槛的文献由它补位）；若用户选的就是内置资源则 user=None
    """
    builtin = BUILTIN_GOLD_PATH if use_builtin and BUILTIN_GOLD_PATH.is_file() else None
    user: Optional[Path] = None
    if isinstance(resolved_resources, dict):
        for field in ("manually_labeled_category_data", "training_samples"):
            descriptor = resolved_resources.get(field)
            uri = str((descriptor or {}).get("storage_uri") or "")
            if not uri:
                continue
            path = _PROJECT_ROOT / uri.removeprefix("project://") if uri.startswith("project://") else Path(uri)
            if path.is_file():
                if builtin is not None and path.resolve() == builtin.resolve():
                    break  # 选的就是内置资源：仅内置生效，用户层为空
                user = path
                break
    return {"builtin": builtin, "user": user}


def anchor_assist(
    papers: Sequence[Dict[str, Any]],
    axis: str,
    *,
    builtin_path: Optional[Path] = None,
    user_path: Optional[Path] = None,
    gold_path: Optional[Path] = None,  # 兼容旧签名：单库（视为用户辅助库）
    threshold: float = _DEFAULT_MATCH_THRESHOLD,
    top_k: int = 5,
    min_combined: Optional[float] = None,
    use_arbiter: bool = True,
    quality_margin: Optional[float] = None,
) -> Dict[str, Any]:
    """深度聚类锚点辅助主入口（用户上传为主、内置为辅；未上传则仅内置）。

    组合规则：
    - 用户上传的匹配达门槛 → 用用户类目（主力：用户自己的标注体系优先）
    - 质量保底：内置绝对相似度超过用户 best_sim + quality_margin 时反超内置
      （防止用户小库"勉强过线"的弱匹配压过内置库的高质量匹配；0=关闭）
    - 用户不达标且内置匹配达标 → 用内置（补位：覆盖用户库没有的领域）
    - 都不达标 → None（保留自由聚类）
    每条锚定结果带 anchor_source=builtin/user 供溯源。
    """
    if gold_path is not None and user_path is None:
        user_path = gold_path  # 向后兼容旧调用
    if quality_margin is None:
        quality_margin = BUILTIN_QUALITY_MARGIN
    libraries = {"builtin": builtin_path, "user": user_path}
    try:
        if axis == "application":
            # 应用轴查询文本用产线应用视图：库侧向量与判别头都在视图空间编码，
            # 摘要向量在应用维度信号弱（方法导向文体），两侧配方必须一致。
            from infrastructure.clustering.dual_axis_cluster import _view_text
            texts = []
            for paper in papers:
                safe = dict(paper)
                safe.setdefault("keywords", [])
                view, _evidence = _view_text(safe, "application")
                texts.append(view or _anchor_text(
                    paper.get("title") or "",
                    paper.get("abstract") or paper.get("semantic_text") or paper.get("full_text") or "",
                    paper.get("keywords") or [],
                ))
        else:
            texts = [
                _anchor_text(
                    paper.get("title") or "",
                    paper.get("abstract") or paper.get("semantic_text") or paper.get("full_text") or "",
                    paper.get("keywords") or [],
                )
                for paper in papers
            ]
        matches_by_role: Dict[str, List[Optional[Dict[str, Any]]]] = {}
        stats_by_role: Dict[str, Dict[str, Any]] = {}
        arbiter = load_discriminative_head(axis) if use_arbiter else None
        for role, path in libraries.items():
            if path is None:
                continue
            index = GoldAnchorIndex.get(path, axis)
            stats_by_role[role] = index.stats()
            if not stats_by_role[role].get("loaded") or not stats_by_role[role].get("anchor_library_size"):
                continue  # 空库跳过（stats 仍上报，保证可观测）
            matches_by_role[role] = index.match_documents(
                texts, top_k=top_k, threshold=threshold, min_combined=min_combined,
                arbiter=arbiter)
        if not matches_by_role:
            # 两个库都为空/未启用：显式报错而非静默 matched=0
            return {
                "enabled": False,
                "error": "锚点库为空：内置库缺失且用户资源未装进任何有效行。请检查 "
                         f"{'technical_cluster_id' if axis == 'technical' else 'application_cluster_id'} "
                         "类目标签字段是否存在且非空、文本是否≥30字。",
                "library": stats_by_role,
            }

        combined_floor = _MIN_COMBINED_MATCH if min_combined is None else float(min_combined)

        document_anchors: Dict[str, Any] = {}
        builtin_win_count = user_win_count = quality_override_count = 0
        for position, paper in enumerate(papers):
            doc_id = str(paper.get("document_id"))
            builtin_match = (matches_by_role.get("builtin") or [None] * len(papers))[position]
            user_match = (matches_by_role.get("user") or [None] * len(papers))[position]
            # 用户上传为主：用户库达门槛即采用；质量保底：内置显著更优时反超
            quality_override = False
            if user_match:
                if (
                    quality_margin > 0
                    and builtin_match
                    and float(builtin_match.get("anchor_similarity") or 0.0)
                    >= float(user_match.get("anchor_similarity") or 0.0) + quality_margin
                ):
                    chosen, source = dict(builtin_match), "builtin"
                    quality_override = True
                else:
                    chosen, source = dict(user_match), "user"
            elif builtin_match:
                chosen, source = dict(builtin_match), "builtin"
            else:
                chosen, source = None, None
            if chosen:
                chosen["anchor_source"] = source
                if source == "user":
                    user_win_count += 1
                else:
                    builtin_win_count += 1
                if quality_override:
                    quality_override_count += 1
                    chosen["quality_override"] = True
                    chosen["overridden_user_topic"] = user_match.get("anchored_topic_id")
                    chosen["overridden_user_topic_name"] = user_match.get("anchored_topic_name")
                    chosen["user_anchor_similarity"] = user_match.get("anchor_similarity")
            document_anchors[doc_id] = chosen
        matched = sum(1 for m in document_anchors.values() if m)
        return {
            "enabled": True,
            "anchor_document_count": len(papers),
            "matched_document_count": matched,
            "rejected_document_count": len(papers) - matched,
            "match_ratio": round(matched / len(papers), 4) if papers else 0.0,
            "builtin_anchored_count": builtin_win_count,
            "user_anchored_count": user_win_count,
            "quality_override_count": quality_override_count,
            "quality_margin": quality_margin,
            "document_anchors": document_anchors,
            "axis": axis,
            "threshold": threshold,
            "min_combined": combined_floor,
            "arbiter_active": arbiter is not None,
            # 库规模随行输出：锚定率必须分母可见才可核对
            "library": stats_by_role,
        }
    except Exception as exc:  # noqa: BLE001 - 锚定失败不影响自由聚类主链路
        logger.warning("锚点标注失败（回退自由聚类主题）：%s", exc)
        return {"enabled": False, "error": str(exc)[:200]}


def aggregate_cluster_anchor(
    document_anchors: Dict[str, Any],
    cluster_doc_ids: Sequence[str],
    *,
    anchored_threshold: float = 0.5,
    suggested_threshold: float = 0.35,
) -> Optional[Dict[str, Any]]:
    """簇级锚定：簇内成员的锚定结果按相似度加权投票，票数份额分级采纳。

    gold 语料实测（46-48 细类目、1000 篇留一验证）：票数份额 ≥0.5 精度 99%、
    ≥0.4 精度 82%。故分级：
    - share ≥ anchored_threshold → anchor_status="anchored"，可替换聚类主题
    - suggested_threshold ≤ share < anchored_threshold → "suggested"，仅展示建议
    - 更低 → 不锚定（返回 None），保留自由聚类主题
    """
    votes: Dict[str, Dict[str, Any]] = {}
    for doc_id in cluster_doc_ids:
        match = document_anchors.get(str(doc_id))
        if not match:
            continue
        label = match["anchored_topic_id"]
        weight = float(match.get("anchor_similarity") or 0.0)
        entry = votes.setdefault(label, {
            "anchored_topic_id": label,
            "anchored_topic_name": match["anchored_topic_name"],
            "weight": 0.0,
            "members": 0,
        })
        entry["weight"] += weight
        entry["members"] += 1
    if not votes:
        return None
    best = max(votes.values(), key=lambda e: e["weight"])
    members = [str(d) for d in cluster_doc_ids]
    matched_members = sum(
        1 for d in members
        if (document_anchors.get(d) or {}).get("anchored_topic_id") == best["anchored_topic_id"]
    )
    total_weight = sum(v["weight"] for v in votes.values())
    share = (best["weight"] / total_weight) if total_weight else 0.0
    if share < suggested_threshold:
        return None
    return {
        "anchored_topic_id": best["anchored_topic_id"],
        "anchored_topic_name": best["anchored_topic_name"],
        "anchor_status": "anchored" if share >= anchored_threshold else "suggested",
        "anchor_confidence": round(share, 4),
        "anchor_member_ratio": round(matched_members / len(members), 4) if members else 0.0,
        "matched_members": matched_members,
    }
