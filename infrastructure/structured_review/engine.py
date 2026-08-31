"""证据约束的结构化自动综述引擎。

核心顺序严格遵循需规：研究问题抽取 → 研究问题语义聚类 → 研究方法匹配
→ 结构化文本综述。深度聚类历史任务不参与本引擎。
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

from domain.value_object.structured_review import (
    ResearchQuestionCandidate,
    ResearchQuestionCluster,
    ReviewDocument,
    ReviewEvidence,
)


_QUESTION_CUES = re.compile(
    r"研究问题|关键问题|科学问题|挑战|瓶颈|不足|缺乏|难以|有待|旨在|目的|"
    r"针对|解决|探讨|研究|分析|investigat|research question|challenge|problem|"
    r"limitation|aim(?:s|ed)? to|seek(?:s)? to|address(?:es|ed)?|how to|whether",
    re.IGNORECASE,
)
_METHOD_CUES = re.compile(
    r"采用|使用|运用|构建|提出|设计|基于|模型|算法|实验|调查|回归|分析方法|"
    r"method|model|algorithm|framework|approach|experiment|survey|regression|"
    r"we propose|we develop|we use|using|based on",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}")
_STOPWORDS = {
    "本文", "本研究", "文章", "研究", "分析", "方法", "结果", "问题", "提出",
    "采用", "使用", "基于", "通过", "以及", "进行", "the", "and", "for", "with",
    "this", "study", "research", "method", "methods", "using", "based", "from",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normal_key(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.casefold())


def _sentences(text: str) -> List[Tuple[str, int, int]]:
    """按中英文句末和段落切分，同时保留原文字符偏移。"""
    rows: List[Tuple[str, int, int]] = []
    for match in re.finditer(r"[^。！？!?；;\n]+(?:[。！？!?；;]+|\n|$)", text):
        raw = match.group(0)
        left = len(raw) - len(raw.lstrip())
        sentence = raw.strip()
        if len(sentence) < 8:
            continue
        start = match.start() + left
        rows.append((sentence, start, start + len(sentence)))
    if not rows and _clean(text):
        value = _clean(text)
        start = text.find(value)
        rows.append((value, max(0, start), max(0, start) + len(value)))
    return rows


def _topic_terms(topic: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(topic) if token.casefold() not in _STOPWORDS}


def _sentence_score(sentence: str, cue: re.Pattern[str], topic_terms: set[str]) -> float:
    score = 1.0 if cue.search(sentence) else 0.0
    lowered = sentence.casefold()
    score += min(0.8, 0.2 * sum(term in lowered for term in topic_terms))
    score += min(0.3, len(sentence) / 500.0)
    return score


def _fallback_question_text(sentence: str) -> str:
    """从证据句中截取问题主干；只删除方法从句，不补充外部概念。"""
    core = re.split(
        r"[，,]\s*(?:并|并且|同时)?\s*(?:采用|使用|运用|基于|通过|构建|提出)|"
        r"\b(?:and|while)\s+(?:uses?|using|applies?|adopts?|proposes?|develops?)\b",
        sentence,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" 。；;,")
    return f"研究问题：{core or sentence}"


def _fallback_method_text(sentence: str) -> str:
    """从原文方法句截取方法短语，避免把整句当成方法名称。"""
    match = re.search(
        r"((?:采用|使用|运用|基于|通过|构建|提出|设计)[^。！？；;]{2,80})",
        sentence,
    )
    if match:
        return match.group(1).strip(" ，,")
    match = re.search(
        r"((?:we\s+)?(?:use|using|apply|adopt|propose|develop|design|based on)[^.?!;]{2,120})",
        sentence,
        re.IGNORECASE,
    )
    return match.group(1).strip(" ,") if match else sentence


def _agglomerative(matrix: np.ndarray, k: int) -> np.ndarray:
    kwargs = {"n_clusters": k, "linkage": "average"}
    try:
        return AgglomerativeClustering(metric="cosine", **kwargs).fit_predict(matrix)
    except TypeError:  # scikit-learn < 1.2
        return AgglomerativeClustering(affinity="cosine", **kwargs).fit_predict(matrix)


class StructuredReviewEngine:
    """不依赖主题库的结构化自动综述核心引擎。"""

    def __init__(self, glm: Any = None, encoder: Any = None) -> None:
        self.glm = glm
        self.encoder = encoder

    @staticmethod
    def normalize_documents(
        raw_documents: Sequence[Any],
        metadata_rows: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    ) -> List[ReviewDocument]:
        metadata_map: Dict[str, Dict[str, Any]] = {}
        if isinstance(metadata_rows, Mapping):
            if "document_id" in metadata_rows:
                metadata_map[str(metadata_rows["document_id"])] = dict(metadata_rows)
            else:
                metadata_map = {
                    str(key): dict(value) for key, value in metadata_rows.items()
                    if isinstance(value, Mapping)
                }
        else:
            for row in metadata_rows or []:
                # 文献编号认 id 别名（与下方 documents 的别名归一保持一致）
                if isinstance(row, Mapping) and (row.get("document_id") or row.get("id")):
                    key = str(row.get("document_id") or row.get("id"))
                    metadata_map[key] = dict(row)

        documents: List[ReviewDocument] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_documents):
            value: Any = raw
            if isinstance(raw, str) and raw.lstrip().startswith("{"):
                try:
                    decoded = json.loads(raw)
                    value = decoded if isinstance(decoded, dict) else raw
                except (TypeError, ValueError):
                    value = raw
            if isinstance(value, Mapping):
                document_id = _clean(
                    value.get("document_id") or value.get("id") or value.get("input_id")
                    or f"DOC{index + 1:03d}"
                )
                text = _clean(
                    value.get("text") or value.get("content") or value.get("full_text")
                    or value.get("abstract") or value.get("abstract_text")
                )
                inline_meta = dict(value)
            else:
                document_id = f"DOC{index + 1:03d}"
                text = _clean(value)
                inline_meta = {}
            if document_id in seen:
                raise ValueError(f"文献编号重复：{document_id}")
            seen.add(document_id)
            merged = {**inline_meta, **metadata_map.get(document_id, {})}
            title = _clean(merged.get("title") or merged.get("ch_name") or merged.get("en_name"))
            document = ReviewDocument(document_id=document_id, text=text, title=title, metadata=merged)
            document.validate()
            documents.append(document)
        return documents

    def extract_candidates(
        self,
        documents: Sequence[ReviewDocument],
        topic: str,
    ) -> List[ResearchQuestionCandidate]:
        def extract_one(document_index: int, document: ReviewDocument) -> List[ResearchQuestionCandidate]:
            extracted = self._extract_with_llm(document, topic)
            valid = self._validate_extracted(document, extracted, document_index)
            if not valid:
                valid = self._fallback_extract(document, topic, document_index)
            return valid

        candidates: List[ResearchQuestionCandidate] = []
        if self.glm is None or len(documents) == 1:
            for document_index, document in enumerate(documents, start=1):
                candidates.extend(extract_one(document_index, document))
        else:
            ordered: Dict[int, List[ResearchQuestionCandidate]] = {}
            with ThreadPoolExecutor(max_workers=min(3, len(documents))) as executor:
                futures = {
                    executor.submit(extract_one, index, document): index
                    for index, document in enumerate(documents, start=1)
                }
                for future in as_completed(futures):
                    ordered[futures[future]] = future.result()
            for document_index in range(1, len(documents) + 1):
                candidates.extend(ordered.get(document_index, []))
        if not candidates:
            raise ValueError("未能从文献集中识别出有原文证据的研究问题")
        return candidates

    def _extract_with_llm(self, document: ReviewDocument, topic: str) -> List[Dict[str, Any]]:
        if self.glm is None:
            return []
        system_prompt = (
            "你是科技文献信息抽取器。只依据输入 text 抽取该文献明确研究或试图解决的研究问题，"
            "只保留与给定研究主题或关键词相关的问题，并匹配文献实际采用的研究方法。"
            "不得补充原文没有的信息。evidence_quote 和 "
            "method_evidence_quote 必须逐字复制自 text；无法确定方法时 method 留空。最多返回3项。"
            "只输出 JSON：{\"data\":{\"items\":[{\"question\":\"...\","
            "\"evidence_quote\":\"...\",\"method\":\"...\","
            "\"method_evidence_quote\":\"...\"}]}}"
        )
        user_prompt = (
            f"研究主题或关键词：{topic}\n文献编号：{document.document_id}\n"
            f"题名（可能为空）：{document.title}\ntext：\n{document.text[:8000]}"
        )
        try:
            response = self.glm.chat_json(
                system_prompt, user_prompt, temperature=0.0, timeout=90.0, max_tokens=1200,
            )
            data = response.get("data", response) if isinstance(response, dict) else {}
            items = data.get("items") or data.get("research_questions") or []
            return [dict(item) for item in items if isinstance(item, Mapping)][:3]
        except Exception:  # noqa: BLE001 - 模型不可用时必须可降级运行
            return []

    def _locate_quote(self, document: ReviewDocument, quote: str) -> Optional[Tuple[str, int, int]]:
        quote = _clean(quote)
        if not quote:
            return None
        start = document.text.find(quote)
        if start >= 0:
            return quote, start, start + len(quote)
        best: Optional[Tuple[str, int, int]] = None
        best_score = 0.0
        key = _normal_key(quote)
        for sentence, sentence_start, sentence_end in _sentences(document.text):
            score = SequenceMatcher(None, key, _normal_key(sentence)).ratio()
            if score > best_score:
                best_score = score
                best = sentence, sentence_start, sentence_end
        return best if best_score >= 0.86 else None

    def _group_method_candidates(
        self,
        candidates: Sequence[ResearchQuestionCandidate],
    ) -> List[List[ResearchQuestionCandidate]]:
        """在一个研究问题类簇内合并语义相同的研究方法表述。"""
        usable = [item for item in candidates if item.method]
        if len(usable) <= 1:
            return [usable] if usable else []
        matrix, _ = self._encode([
            f"{item.method}\n{item.method_evidence.quote if item.method_evidence else ''}"
            for item in usable
        ])
        similarity = matrix @ matrix.T
        parents = list(range(len(usable)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            root_left, root_right = find(left), find(right)
            if root_left != root_right:
                parents[root_right] = root_left

        for left in range(len(usable)):
            for right in range(left + 1, len(usable)):
                same_text = _normal_key(usable[left].method) == _normal_key(usable[right].method)
                if same_text or float(similarity[left, right]) >= 0.84:
                    union(left, right)
        groups: Dict[int, List[ResearchQuestionCandidate]] = defaultdict(list)
        for index, item in enumerate(usable):
            groups[find(index)].append(item)
        return list(groups.values())

    def _validate_extracted(
        self,
        document: ReviewDocument,
        rows: Sequence[Mapping[str, Any]],
        document_index: int,
    ) -> List[ResearchQuestionCandidate]:
        results: List[ResearchQuestionCandidate] = []
        seen: set[str] = set()
        for item_index, row in enumerate(rows, start=1):
            question = _clean(row.get("question") or row.get("research_question"))
            located = self._locate_quote(
                document, _clean(row.get("evidence_quote") or row.get("evidence") or row.get("quote"))
            )
            if not question or located is None:
                continue
            key = _normal_key(question)
            if not key or key in seen:
                continue
            seen.add(key)
            quote, start, end = located
            question_evidence = ReviewEvidence(
                evidence_id=f"EV-{document_index:03d}-Q{item_index:02d}",
                document_id=document.document_id,
                quote=quote,
                start=start,
                end=end,
            )
            method = _clean(row.get("method") or row.get("research_method"))
            method_location = self._locate_quote(
                document,
                _clean(row.get("method_evidence_quote") or row.get("method_evidence")),
            )
            method_evidence = None
            if method and method_location is not None:
                method_quote, method_start, method_end = method_location
                method_evidence = ReviewEvidence(
                    evidence_id=f"EV-{document_index:03d}-M{item_index:02d}",
                    document_id=document.document_id,
                    quote=method_quote,
                    start=method_start,
                    end=method_end,
                )
            elif method:
                # 方法没有逐字证据时不输出方法，避免模型生成无法溯源的内容。
                method = ""
            results.append(ResearchQuestionCandidate(
                candidate_id=f"RQC-{document_index:03d}-{item_index:02d}",
                document_id=document.document_id,
                question=question,
                question_evidence=question_evidence,
                method=method,
                method_evidence=method_evidence,
                extraction_mode="llm",
            ))
        return results

    def _fallback_extract(
        self,
        document: ReviewDocument,
        topic: str,
        document_index: int,
    ) -> List[ResearchQuestionCandidate]:
        sentences = _sentences(document.text)
        if not sentences:
            return []
        terms = _topic_terms(topic)
        question_rows = sorted(
            sentences,
            key=lambda row: _sentence_score(row[0], _QUESTION_CUES, terms),
            reverse=True,
        )
        selected = [row for row in question_rows if _QUESTION_CUES.search(row[0])][:2]
        if not selected:
            selected = question_rows[:1]
        method_rows = [row for row in sentences if _METHOD_CUES.search(row[0])]
        results: List[ResearchQuestionCandidate] = []
        for item_index, (sentence, start, end) in enumerate(selected, start=1):
            method_row = min(method_rows, key=lambda row: abs(row[1] - start)) if method_rows else None
            method = _fallback_method_text(method_row[0]) if method_row else ""
            method_evidence = None
            if method_row:
                method_evidence = ReviewEvidence(
                    evidence_id=f"EV-{document_index:03d}-M{item_index:02d}",
                    document_id=document.document_id,
                    quote=method_row[0], start=method_row[1], end=method_row[2],
                )
            results.append(ResearchQuestionCandidate(
                candidate_id=f"RQC-{document_index:03d}-{item_index:02d}",
                document_id=document.document_id,
                question=_fallback_question_text(sentence),
                question_evidence=ReviewEvidence(
                    evidence_id=f"EV-{document_index:03d}-Q{item_index:02d}",
                    document_id=document.document_id,
                    quote=sentence, start=start, end=end,
                ),
                method=method,
                method_evidence=method_evidence,
                extraction_mode="evidence_rule_fallback",
            ))
        return results

    def _encode(self, texts: Sequence[str]) -> Tuple[np.ndarray, str]:
        if self.encoder is not None:
            try:
                matrix = np.asarray(self.encoder.encode(list(texts)), dtype=np.float32)
                if matrix.ndim == 2 and len(matrix) == len(texts):
                    return normalize(matrix), "bge-m3"
            except Exception:  # noqa: BLE001
                pass
        vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 5), min_df=1, max_features=12000,
        )
        matrix = vectorizer.fit_transform(texts)
        return normalize(matrix).toarray().astype(np.float32), "tfidf-fallback"

    @staticmethod
    def _select_labels(matrix: np.ndarray, requested_k: Optional[int]) -> Tuple[np.ndarray, Dict[str, Any]]:
        n = len(matrix)
        if n == 1:
            return np.zeros(1, dtype=int), {"selected_k": 1, "candidates": []}
        if requested_k:
            k = max(1, min(int(requested_k), n))
            labels = np.zeros(n, dtype=int) if k == 1 else _agglomerative(matrix, k)
            return labels, {"selected_k": k, "selection_mode": "requested", "candidates": []}
        similarity = np.clip(matrix @ matrix.T, -1.0, 1.0)
        off_diagonal = similarity[~np.eye(n, dtype=bool)]
        if n <= 3 or (off_diagonal.size and float(np.mean(off_diagonal)) >= 0.78):
            return np.zeros(n, dtype=int), {
                "selected_k": 1, "selection_mode": "automatic", "candidates": [],
            }
        upper = min(8, n - 1, max(2, int(round(math.sqrt(n))) + 1))
        candidates: List[Dict[str, Any]] = []
        best: Optional[Tuple[float, np.ndarray, int]] = None
        for k in range(2, upper + 1):
            labels = _agglomerative(matrix, k)
            counts = Counter(labels.tolist())
            if len(counts) < 2:
                continue
            silhouette = float(silhouette_score(matrix, labels, metric="cosine"))
            singleton_ratio = sum(size for size in counts.values() if size == 1) / n
            score = silhouette - 0.45 * singleton_ratio - 0.015 * k
            candidates.append({
                "k": k, "silhouette": round(silhouette, 6),
                "singleton_ratio": round(singleton_ratio, 6), "selection_score": round(score, 6),
            })
            if best is None or score > best[0]:
                best = score, labels, k
        if best is None:
            return np.zeros(n, dtype=int), {"selected_k": 1, "candidates": candidates}
        return best[1], {
            "selected_k": best[2], "selection_mode": "automatic", "candidates": candidates,
        }

    def cluster_candidates(
        self,
        candidates: Sequence[ResearchQuestionCandidate],
        topic: str,
        requested_k: Optional[int] = None,
    ) -> Tuple[List[ResearchQuestionCluster], Dict[str, Any]]:
        representations = [
            f"{item.question}\n原文证据：{item.question_evidence.quote}" for item in candidates
        ]
        matrix, representation_name = self._encode(representations)
        labels, diagnostics = self._select_labels(matrix, requested_k)
        groups: Dict[int, List[int]] = defaultdict(list)
        for index, label in enumerate(labels.tolist()):
            groups[int(label)].append(index)
        ordered_groups = sorted(groups.values(), key=lambda indices: min(indices))
        clusters: List[ResearchQuestionCluster] = []
        for cluster_index, indices in enumerate(ordered_groups, start=1):
            members = [candidates[index] for index in indices]
            label, summary = self._induce_cluster(topic, members)
            cohesion = None
            if len(indices) > 1:
                block = matrix[indices] @ matrix[indices].T
                values = block[np.triu_indices(len(indices), 1)]
                cohesion = round(float(np.mean(values)), 6) if len(values) else None
            clusters.append(ResearchQuestionCluster(
                cluster_id=f"PC-{cluster_index:03d}", label=label, summary=summary,
                candidates=members, cohesion=cohesion,
            ))
        diagnostics["representation"] = representation_name
        diagnostics["candidate_count"] = len(candidates)
        return clusters, diagnostics

    def _induce_cluster(
        self,
        topic: str,
        candidates: Sequence[ResearchQuestionCandidate],
    ) -> Tuple[str, str]:
        evidence_rows = [{
            "question": item.question,
            "evidence_quote": item.question_evidence.quote,
            "document_id": item.document_id,
        } for item in candidates]
        if self.glm is not None:
            system_prompt = (
                "你是研究问题类簇归纳器。仅根据给定研究问题及原文证据，为该类簇生成一个"
                "简洁、可区分的类簇名称和一句归纳；不得增加证据中没有的研究对象、方法或结论。"
                "只输出JSON：{\"data\":{\"label\":\"...\",\"summary\":\"...\"}}"
            )
            try:
                response = self.glm.chat_json(
                    system_prompt,
                    f"总主题：{topic}\n类簇内容：{json.dumps(evidence_rows, ensure_ascii=False)}",
                    temperature=0.0, timeout=90.0, max_tokens=500,
                )
                data = response.get("data", response) if isinstance(response, dict) else {}
                label = _clean(data.get("label"))
                summary = _clean(data.get("summary"))
                if label and summary:
                    return label, summary
            except Exception:  # noqa: BLE001
                pass
        medoid = min(candidates, key=lambda item: len(item.question)).question
        label = re.sub(r"^(研究问题[:：]\s*)", "", medoid).strip()[:36]
        questions = "；".join(item.question for item in candidates[:3])
        return label or topic[:36], f"该类簇包含以下有原文依据的研究问题：{questions}"

    def _trend_hotspot_distribution(
        self,
        documents: Sequence[ReviewDocument],
        cluster_rows: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """趋势分析与研究热点分布（确定性计算，无额外 LLM 调用）。

        - time_range：支持文献发表年份的跨度；
        - hotspots：按类簇支持文献数归一为强度（0.3–1.0），趋势状态按支持
          文献的年份分布判定——集中在窗口后半段为「上升/新兴」，前半段
          为主为「持续关注」。排序按强度降序，与前端热点强度排行条对应。
        """
        doc_year: Dict[str, Optional[int]] = {}
        for item in documents:
            meta = item.metadata or {}
            raw = str(
                meta.get("publication_date")
                or meta.get("published_at")
                or meta.get("year")
                or meta.get("publish_year")
                or ""
            )
            match = re.search(r"(?:19|20)\d{2}", raw)
            if not match:
                # 文件上传无手填元数据时，从正文抽发表年份（收稿/出版/Received 等
                # 标志词限定，避免误取参考文献年份）
                head = item.text[:3000]
                match = re.search(
                    r"(?:收稿日期|投稿日期|出版日期|发表日期|上网日期|Received|Accepted|Published)"
                    r"[^0-9\n]{0,15}((?:19|20)\d{2})",
                    head,
                    re.IGNORECASE,
                )
            doc_year[item.document_id] = int(match.group(1) if match.lastindex else match.group(0)) if match else None

        known_years = sorted({y for y in doc_year.values() if y})
        if not known_years:
            return {"time_range": None, "hotspots": []}
        time_range = (
            f"{known_years[0]}–{known_years[-1]}" if len(known_years) > 1 else f"{known_years[0]}年"
        )
        all_years = [y for y in doc_year.values() if y]
        median_year = sorted(all_years)[len(all_years) // 2]

        max_docs = max((row.get("document_count", 0) for row in cluster_rows), default=0)
        hotspots = []
        for row in cluster_rows:
            count = row.get("document_count", 0)
            score = round(0.3 + 0.7 * (count / max_docs), 3) if max_docs else 0.3
            years = [
                doc_year[doc_id]
                for doc_id in (row.get("document_ids") or [])
                if doc_year.get(doc_id)
            ]
            if years and len(known_years) > 1:
                recent = sum(1 for y in years if y >= median_year)
                if recent == len(years):
                    status = "新兴热点" if min(years) >= median_year else "上升趋势"
                elif recent * 2 >= len(years):
                    status = "上升趋势"
                else:
                    status = "持续关注"
            else:
                status = "持续关注"
            questions = row.get("research_questions") or []
            name = str(questions[0]) if questions else str(row.get("label") or row.get("cluster_id", ""))
            hotspots.append({
                "name": name[:80],
                "score": score,
                "status": status,
                "cluster_id": row.get("cluster_id"),
                "document_count": count,
                "supporting_years": years,
            })
        hotspots.sort(key=lambda item: (-item["score"], item.get("cluster_id") or ""))
        return {"time_range": time_range, "hotspots": hotspots}

    def build_output(
        self,
        documents: Sequence[ReviewDocument],
        clusters: Sequence[ResearchQuestionCluster],
        topic: str,
        diagnostics: Mapping[str, Any],
    ) -> Dict[str, Any]:
        document_map = {item.document_id: item for item in documents}
        tree: List[Dict[str, Any]] = []
        cluster_rows: List[Dict[str, Any]] = []
        evidence_nodes: Dict[str, set[str]] = defaultdict(set)
        evidence_values: Dict[str, ReviewEvidence] = {}
        method_sequence = 0

        for question_index, cluster in enumerate(clusters, start=1):
            question_id = f"RQ-{question_index:02d}"
            for candidate in cluster.candidates:
                evidence_values[candidate.question_evidence.evidence_id] = candidate.question_evidence
                evidence_nodes[candidate.question_evidence.evidence_id].add(question_id)
            methods: List[Dict[str, Any]] = []
            for members in self._group_method_candidates(cluster.candidates):
                method_sequence += 1
                method_id = f"M-{method_sequence:02d}"
                method_text = min((item.method for item in members if item.method), key=len)
                method_evidence_ids: List[str] = []
                source_ids: List[str] = []
                for member in members:
                    source_ids.append(member.document_id)
                    if member.method_evidence:
                        evidence = member.method_evidence
                        evidence_values[evidence.evidence_id] = evidence
                        evidence_nodes[evidence.evidence_id].update({question_id, method_id})
                        method_evidence_ids.append(evidence.evidence_id)
                methods.append({
                    "method_id": method_id,
                    "method": method_text,
                    "source_ids": list(dict.fromkeys(source_ids)),
                    "evidence_ids": list(dict.fromkeys(method_evidence_ids)),
                    # 研究进展与阶段结论属于下一阶段，当前绝不生成演示内容。
                    "progress": [],
                })
            document_ids = list(dict.fromkeys(item.document_id for item in cluster.candidates))
            question_evidence_ids = [item.question_evidence.evidence_id for item in cluster.candidates]
            tree.append({
                "question_id": question_id,
                "research_question": cluster.label,
                "question_summary": cluster.summary,
                "document_count": len(document_ids),
                "document_ids": document_ids,
                "evidence_ids": question_evidence_ids,
                "methods": methods,
            })
            cluster_rows.append({
                "cluster_id": cluster.cluster_id,
                "label": cluster.label,
                "summary": cluster.summary,
                "question_count": len(cluster.candidates),
                "document_count": len(document_ids),
                "document_ids": document_ids,
                "research_questions": [item.question for item in cluster.candidates],
                "evidence_ids": question_evidence_ids,
                "cohesion": cluster.cohesion,
            })

        evidence_index = []
        for evidence_id, evidence in evidence_values.items():
            document = document_map[evidence.document_id]
            evidence_index.append({
                "evidence_id": evidence_id,
                "document_id": evidence.document_id,
                "title": document.title,
                "source_section": evidence.source_section,
                "evidence_excerpt": evidence.quote,
                "quote": evidence.quote,
                "start": evidence.start,
                "end": evidence.end,
                "supported_nodes": sorted(evidence_nodes[evidence_id]),
            })

        report = self._generate_report(topic, cluster_rows, evidence_index)
        cluster_induction = {
            "cluster_count": len(cluster_rows),
            "clusters": cluster_rows,
            "induction_basis": "研究问题的BGE-M3语义表示与余弦距离；模型不可用时使用TF-IDF降级表示",
            "diagnostics": dict(diagnostics),
        }
        trend_hotspot = self._trend_hotspot_distribution(documents, cluster_rows)
        return {
            "topic": topic,
            "document_count": len(documents),
            "tree": tree,
            "cluster_induction_results": cluster_induction,
            "structured_report": report,
            "trend_hotspot_distribution": trend_hotspot,
            "evidence_index": evidence_index,
            "statistics": {
                "document_count": len(documents),
                "research_question_count": len(tree),
                "method_count": sum(len(item["methods"]) for item in tree),
                "evidence_sentence_count": len(evidence_index),
                "trend_hotspot_status": (
                    "computed" if trend_hotspot["hotspots"] else "no_publish_years"
                ),
            },
        }

    def _generate_report(
        self,
        topic: str,
        cluster_rows: Sequence[Mapping[str, Any]],
        evidence_index: Sequence[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        evidence_by_id = {str(item["evidence_id"]): item for item in evidence_index}
        if self.glm is not None:
            system_prompt = (
                "你是证据约束的科技综述写作器。只能使用给定类簇和证据句，生成报告概述及"
                "与类簇一一对应的章节。每个章节必须列出支撑它的 evidence_ids；不得写趋势、"
                "热点、时间演化或证据中不存在的结论。只输出JSON："
                "{\"data\":{\"overview\":\"...\",\"sections\":[{\"cluster_id\":\"PC-001\","
                "\"title\":\"...\",\"content\":\"...\",\"evidence_ids\":[\"EV-...\"]}]}}"
            )
            prompt_data = {
                "topic": topic,
                "clusters": list(cluster_rows),
                "evidence": [{
                    "evidence_id": item["evidence_id"], "document_id": item["document_id"],
                    "quote": item["evidence_excerpt"],
                } for item in evidence_index],
            }
            try:
                response = self.glm.chat_json(
                    system_prompt, json.dumps(prompt_data, ensure_ascii=False),
                    temperature=0.0, timeout=120.0, max_tokens=2200,
                )
                data = response.get("data", response) if isinstance(response, dict) else {}
                overview = _clean(data.get("overview"))
                raw_sections = data.get("sections") or []
                sections = []
                cluster_map = {str(item["cluster_id"]): item for item in cluster_rows}
                for item in raw_sections:
                    if not isinstance(item, Mapping):
                        continue
                    cluster_id = str(item.get("cluster_id") or "")
                    cluster = cluster_map.get(cluster_id)
                    if cluster is None:
                        continue
                    valid_ids = [
                        str(value) for value in item.get("evidence_ids", [])
                        if str(value) in evidence_by_id and str(value) in cluster.get("evidence_ids", [])
                    ]
                    if not valid_ids:
                        valid_ids = list(cluster.get("evidence_ids", []))
                    content = _clean(item.get("content"))
                    if content:
                        sections.append({
                            "section_id": f"SEC-{len(sections) + 1:02d}",
                            "cluster_id": cluster_id,
                            "title": _clean(item.get("title")) or str(cluster.get("label") or ""),
                            "content": content,
                            "evidence_ids": valid_ids,
                        })
                if overview and sections:
                    return {"title": f"{topic}结构化综述", "overview": overview, "sections": sections}
            except Exception:  # noqa: BLE001
                pass

        sections = [{
            "section_id": f"SEC-{index + 1:02d}",
            "cluster_id": str(cluster["cluster_id"]),
            "title": str(cluster["label"]),
            "content": str(cluster["summary"]),
            "evidence_ids": list(cluster.get("evidence_ids", [])),
        } for index, cluster in enumerate(cluster_rows)]
        overview = (
            f"本报告围绕“{topic}”组织{len(cluster_rows)}个研究问题类簇；"
            "所有章节均保留可返回原文的证据编号。"
        )
        return {"title": f"{topic}结构化综述", "overview": overview, "sections": sections}

    def run(
        self,
        documents: Sequence[ReviewDocument],
        topic: str,
        requested_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        candidates = self.extract_candidates(documents, topic)
        clusters, diagnostics = self.cluster_candidates(candidates, topic, requested_k)
        return self.build_output(documents, clusters, topic, diagnostics)
