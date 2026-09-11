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
# 强方法动词：句子确实在叙述"做了什么/用什么方法"（区别于 model/experiment
# 这类弱线索——问题句 "it faces two major challenges... models..." 也含弱线索）
_METHOD_VERB = re.compile(
    r"采用|使用|运用|构建|提出|设计|基于|"
    r"\bwe\s+(?:use|using|apply|adopt|propose|develop|design|introduce|present|train)|"
    r"\b(?:using|based on|to address this|to tackle this|to this end)\b",
    re.IGNORECASE,
)

# 研究进展句线索：实验结果/性能提升/结论表述
_PROGRESS_CUES = re.compile(
    r"实验|结果|表明|证明|提升|提高|改善|优于|性能|准确率|收敛|消融|"
    r"experiments?|results?|show(?:s|ing)? that|improv|gain(?:s|ed)?|outperform|"
    r"achiev|yield|demonstrat|consistently|ablation",
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


# 英文句界：句号+空白后接大写开头的词（含引号/括号前缀）处断句。
# 不要求小写后接数字（避免 Fig. 3 / Table 2 误切）；缩写后小写不切（et al. propose 保持整句）。
# 另断章节标题头："reliability. 1 Introduction Scaling…" / "results. 2. Related Work"——
# PDF 换行被压平后编号标题粘连句尾，曾是溯源关键句段跨章的根因（2026-09-11）。
_EN_BOUNDARY = re.compile(r"(?<=[A-Za-z\)\]])\.\s+(?=[\"'(\[]*(?:[A-Z]|\d{1,2}\.?\s+[A-Z]))")
# 字面 \n 后紧跟编号列表/算法环境关键词 = 伪代码行粘连在句尾，从 \n 处截掉
_GLUED_PSEUDO = re.compile(
    r"\\n\s*(?=(?:\d+\s*[.:)：])|(?:Output|Input|Initialize|Algorithm|Require[ds]?|Ensure)\s*[:：])"
)


def _sentences(text: str) -> List[Tuple[str, int, int]]:
    """按中英文句末和段落切分，同时保留原文字符偏移。

    英文句号后接大写开头词处同样断句。PDF 抽取文本中的字面 \\n（反斜杠+n
    转义）不代表句界——它是行内换行，句子跨行继续；但 \\n 后紧跟编号列表
    或算法关键词（如 "\\n 3: Output:"）说明伪代码行粘连在句尾，从该处截掉。
    输出文本里的字面 \\n 由 _sanitize_fragment 统一剥掉（2026-09-11 热点/
    方法乱码根因）。
    """
    rows: List[Tuple[str, int, int]] = []
    for match in re.finditer(r"[^。！？!?；;\n]+(?:[。！？!?；;]+|\n|$)", text):
        raw = match.group(0)
        base = match.start()
        # 段内细分断点：英文句界（保留句号）
        ends = sorted({b.start() + 1 for b in _EN_BOUNDARY.finditer(raw) if 0 < b.start() + 1 < len(raw)})
        bounds = [0, *ends, len(raw)]
        for seg_start, seg_end in zip(bounds[:-1], bounds[1:]):
            segment = raw[seg_start:seg_end]
            left = len(segment) - len(segment.lstrip())
            sentence = segment.strip()
            if not sentence:
                continue
            start = base + seg_start + left
            glued = _GLUED_PSEUDO.search(sentence)
            if glued:
                sentence = sentence[:glued.start()].rstrip()
            if len(sentence) < 8:
                continue
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


# 伪代码/列表残片特征：算法环境标志词、编号列表开头、数学符号密度高
# （字面 \n 是 PDF 行内换行转义，正常句可含，不算伪代码特征）
_PSEUDO_LINE = re.compile(
    r"(?:Output|Input|Initialize|Algorithm|Require[ds]?|Ensure)\s*[:：]|"
    r"^\s*\d+\s*[.:)：]\s*|[πθρφαβγλμσωΦΨΩ].*[πθρφαβγλμσωΦΨΩ]"
)


def _is_table_like(sentence: str) -> bool:
    """表格/公式拍平文本判定（_clean 压平换行后表格行的典型形态）。

    ① 单句内 ≥3 个小数簇（"0.46 0.4 0.33" 指标行）；
    ② 字母占字母数字比 < 0.45（公式/数字矩阵，正常叙述句英文占比远高）。
    """
    stripped = str(sentence or "").strip()
    if not stripped:
        return False
    if len(re.findall(r"\d\.\d+", stripped)) >= 3:
        return True
    alnum = sum(ch.isalnum() for ch in stripped)
    alpha = sum(ch.isalpha() for ch in stripped)
    return alnum > 0 and alpha / alnum < 0.45
def _is_section_run(sentence: str) -> bool:
    """章节标题串判定："5 Experiment 5.1 Experimental Setting Models and Baselines"。

    编号开头的多级标题链（含 x.y 子编号或 ≥2 段编号+大写词），不是叙述句；
    "Experiment/Results" 等章节名会误中结果线索词，需在证据句池排除。
    """
    stripped = str(sentence or "").strip()
    if not re.match(r"^\d{1,2}(?:\.\d+)*\.?\s+[A-Z]", stripped):
        return False
    return bool(re.search(r"\d{1,2}\.\d{1,2}", stripped)
                or len(re.findall(r"(?:^|\s)\d{1,2}\.?\s+[A-Z]", stripped)) >= 2)


# 引用标记：括号内含四位年份，或 "Sohn et al., 2020)" 残缺形式
_CITATION_PAREN = re.compile(r"\([^()]{0,80}(?:19|20)\d{2}[a-z]?[^()]{0,10}\)")
_CITATION_TAIL = re.compile(
    r"(?:^|\s)[A-Z][A-Za-z\-']+(?:\s+et\s+al\.?|\s+and\s+[A-Z][A-Za-z\-']+)?,?\s*(?:19|20)\d{2}[a-z]?\)?[.,;:]?\s*"
)


def _sanitize_fragment(text: str) -> str:
    """清洗证据句残片：去引用标记（作者-年份与 [17, 3] 数字式）、字面 \\n
    转义、悬空标点。

    兜底抽取在未按英文句号切分的旧逻辑下会把 "(Huang et al., 2024). This
    limitation..." 这类句中残片当问题/方法主干；分句修复后仍有少量引用标记
    附着在句首/句中，此处统一剥掉，只删不补。
    """
    value = str(text or "").replace("\\n", " ")
    value = _CITATION_PAREN.sub(" ", value)
    value = _CITATION_TAIL.sub(" ", value)
    value = re.sub(r"\[\s*\d+(?:\s*[,，–-]\s*\d+)*\s*\]", " ", value)  # [17, 3, 7]
    value = re.sub(r"\s+", " ", value)
    # 引用删除后的标点空隙修复："adaptation , where" → "adaptation, where"
    value = re.sub(r"\s+([,.;:!?；：，。！？])", r"\1", value)
    return value.strip(" 。；;,.:：")


def _fallback_question_text(sentence: str) -> str:
    """从证据句中截取问题主干；先清洗引用/伪代码残片，只删不补外部概念。"""
    cleaned = _sanitize_fragment(sentence)
    core = re.split(
        r"[，,]\s*(?:并|并且|同时)?\s*(?:采用|使用|运用|基于|通过|构建|提出)|"
        r"\b(?:and|while)\s+(?:uses?|using|applies?|adopts?|proposes?|develops?)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" 。；;,")
    return f"研究问题：{_clip_at_word(core or cleaned, 120)}"


def _balance_parens(text: str) -> str:
    """截断/清洗后未闭合的括号尾巴（"problems (Zuo et al"）从括号前剪掉。"""
    value = str(text or "")
    if value.count("(") > value.count(")"):
        value = value[:value.rfind("(")].strip(" ，,")
    return value


def _clip_at_word(text: str, limit: int) -> str:
    """在词边界截断，避免 120 字符上限把 "reframe" 切成 "refra" 这类残词。"""
    if len(text) <= limit:
        return _balance_parens(text)
    clipped = text[:limit]
    cut = max(clipped.rfind(" "), clipped.rfind("，"), clipped.rfind(","))
    value = clipped[:cut].strip(" ，,") if cut > limit // 2 else clipped.strip(" ，,")
    return _balance_parens(value)


def _clip_method(text: str, limit: int = 120) -> str:
    """方法标签收敛：只保留首句，超长在词边界截断。

    LLM 抽取的 method 可能带回整段叙述（数百字符、多句）；三层树的方法
    节点是标签不是段落。证据溯源不受影响——evidence 仍存完整原句。
    """
    value = str(text or "").strip()
    if not value:
        return value
    first_sentence = re.split(r"(?<=[.!?。！？])\s+", value, maxsplit=1)[0]
    return _balance_parens(_clip_at_word(first_sentence, limit))


def _fallback_method_text(sentence: str) -> str:
    """从原文方法句截取方法短语，避免把整句当成方法名称。

    先过 _sanitize_fragment 清洗（引用标记/字面 \\n/悬空标点），英文从句
    在词边界截断——旧版固定 120 字符会把 "reframe" 切成 "refra" 残词。
    """
    cleaned = _sanitize_fragment(sentence)
    match = re.search(
        r"((?:采用|使用|运用|基于|通过|构建|提出|设计)[^。！？；;]{2,80})",
        cleaned,
    )
    if match:
        return match.group(1).strip(" ，,")
    match = re.search(
        r"((?:we\s+)?(?:use|uses|using|apply|applies|adopt|adopts|propose|proposes|"
        r"develop|develops|design|designs|based on)[^.?!;]{2,120})",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        fragment = match.group(1).strip(" ,")
        # 主语回带（2026-09-11）：动词片段以小写开头时取动词前紧邻的名词
        # 短语补全主语——"uses a single pretrained model…" 丢了 TTSR
        if fragment[:1].islower():
            prefix = cleaned[:match.start()]
            subject = re.search(
                r"([A-Z][A-Za-z0-9\-]*(?:\s+[A-Za-z0-9\-]+){0,3})[\s,;:]*$", prefix)
            if subject:
                fragment = f"{subject.group(1).strip()} {fragment}"
        # 尾部悬垂虚词剥除（最多两层）："…two functional roles: a" → "…roles"
        for _ in range(2):
            stripped_tail = re.sub(
                r"\s+(?:a|an|the|of|with|and|or|to|for|in|by|on|that|which)$",
                "", fragment, flags=re.IGNORECASE)
            if stripped_tail == fragment:
                break
            fragment = stripped_tail
        return _clip_at_word(fragment, 100)
    # 无动词匹配：整句清洗文本也须封顶（三层树方法节点是标签不是段落）
    return _clip_method(cleaned, 120)


def _clip_excerpt(text: str, limit: int = 400) -> str:
    """证据摘录展示截断：超长时回退到句末标点（无则词边界），并平衡括号。

    固定 400 字符上限会在句中拦腰截断（曾在句尾留下 "(Cobbe et al., 2021"
    残缺引用）——先找截断窗内最后一个句末标点，覆盖过半才在那截断。
    """
    value = _balance_parens(_sanitize_fragment(text))
    if len(value) <= limit:
        return value
    clipped = value[:limit]
    cut = -1
    for mark in (". ", "。", "? ", "！", "! ", "；", "; "):
        position = clipped.rfind(mark)
        if position > cut:
            cut = position
    if cut >= int(limit * 0.5):
        return value[:cut + 1].strip()
    return _balance_parens(_clip_at_word(clipped, limit))


def _strip_method_echo(summary: str, method_text: str) -> str:
    """剪掉 summary 开头对方法描述的复述（保留增量结果内容）。

    LLM 归纳常以 "该方法采用XXX（=方法原文）…" 起笔，三层树中 M 节点已
    展示方法，P 节点再复述一遍即"内容一样"。折叠标点后做最长公共子串
    （复述常丢逗号/量词，字面比对会漏），公共块覆盖方法文本 ≥50% 才剪，
    避免误伤正常表述；折叠坐标经索引映射回原文剪切位置。
    """
    def _fold(text: str) -> Tuple[str, List[int]]:
        chars: List[str] = []
        indices: List[int] = []
        for position, ch in enumerate(text):
            if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
                chars.append(ch)
                indices.append(position)
        return "".join(chars), indices

    if not summary or not method_text:
        return summary
    folded_method, _ = _fold(method_text)
    folded_summary, summary_indices = _fold(summary)
    if not folded_method or not folded_summary:
        return summary
    match = SequenceMatcher(None, folded_method, folded_summary, autojunk=False).find_longest_match(
        0, len(folded_method), 0, len(folded_summary))
    if match.size < 8 or match.size < 0.50 * len(folded_method):
        return summary
    raw_end = summary_indices[match.b + match.size - 1] + 1
    # 残尾清理：匹配点后 16 字符内的首个句读一并剪掉（"…两个｜角色进行自博弈，"）
    boundary = re.search(r"[，,；;。]", summary[raw_end:raw_end + 16])
    if boundary:
        raw_end += boundary.end()
    remainder = summary[raw_end:].lstrip(" ，,。；;：:、的该方法与和及并对")
    if len(remainder) < 12:  # 剪完剩太少说明 summary 本身就是方法复述，保留原文
        return summary
    return remainder


def _truncate_references(raw: str) -> str:
    """参考文献章节截断（与 NER 引擎同款行首判定）。

    条目里的作者/机构/arXiv 编号是著录信息不是正文（"Training verifiers to
    solve math word problems. arXiv preprint..." 即参考文献条目混入问题的
    根因）。必须在 _clean 压平换行之前做——压平后行首标记永久失效。
    """
    match = re.search(
        r"(?:^|\n)\s*#{0,3}\s*(参考文献|References|REFERENCES)\s*[：:．.\s]*(?:\n|$)",
        str(raw or ""),
    )
    return raw[:match.start()] if match else raw


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
                raw_text = str(
                    value.get("text") or value.get("content") or value.get("full_text")
                    or value.get("abstract") or value.get("abstract_text") or ""
                )
                # 防御：text 字段本身还是 JSON 字符串（上游双重包装）时再解一层，
                # 否则换行停留在字面 \n 转义态，References 行首截断失效
                if raw_text.lstrip().startswith("{"):
                    try:
                        inner = json.loads(raw_text)
                    except (TypeError, ValueError):
                        inner = None
                    if isinstance(inner, Mapping):
                        inner_text = str(
                            inner.get("text") or inner.get("content") or inner.get("full_text") or ""
                        )
                        if inner_text.strip():
                            raw_text = inner_text
                text = _clean(_truncate_references(raw_text))
                inline_meta = dict(value)
            else:
                document_id = f"DOC{index + 1:03d}"
                text = _clean(_truncate_references(str(value or "")))
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
        # 证据实体注册表：同一段原文切片（同文档同起止）只生成唯一 evidence_id，
        # 后续相同切片复用该 ID，由多个业务节点（RQxx/Mxx）在 supported_nodes 共同引用。
        evidence_registry: Dict[Tuple[str, int, int], str] = {}

        def extract_one(document_index: int, document: ReviewDocument) -> List[ResearchQuestionCandidate]:
            extracted = self._extract_with_llm(document, topic)
            valid = self._validate_extracted(document, extracted, document_index, evidence_registry)
            if not valid:
                valid = self._fallback_extract(document, topic, document_index, evidence_registry)
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

    @staticmethod
    def _register_evidence(
        registry: Dict[Tuple[str, int, int], str],
        document: ReviewDocument,
        quote: str,
        start: int,
        end: int,
        evidence_id: str,
    ) -> ReviewEvidence:
        """按（文档, 起点, 终点）注册证据：同一切片复用已有 evidence_id，
        不再复制生成内容完全重复的多条证据实体（如 EV-001-M01/EV-001-M02）。"""
        existing_id = registry.get((document.document_id, start, end))
        if existing_id is not None:
            return ReviewEvidence(
                evidence_id=existing_id, document_id=document.document_id,
                quote=quote, start=start, end=end,
            )
        registry[(document.document_id, start, end)] = evidence_id
        return ReviewEvidence(
            evidence_id=evidence_id, document_id=document.document_id,
            quote=quote, start=start, end=end,
        )

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
        evidence_registry: Dict[Tuple[str, int, int], str],
    ) -> List[ResearchQuestionCandidate]:
        results: List[ResearchQuestionCandidate] = []
        seen: set[str] = set()
        for item_index, row in enumerate(rows, start=1):
            question = _sanitize_fragment(row.get("question") or row.get("research_question"))
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
            question_evidence = self._register_evidence(
                evidence_registry, document, quote, start, end,
                f"EV-{document_index:03d}-Q{item_index:02d}",
            )
            method = _sanitize_fragment(row.get("method") or row.get("research_method"))
            method = _clip_method(method) if method else method
            method_location = self._locate_quote(
                document,
                _clean(row.get("method_evidence_quote") or row.get("method_evidence")),
            )
            method_evidence = None
            if method and method_location is not None:
                method_quote, method_start, method_end = method_location
                method_evidence = self._register_evidence(
                    evidence_registry, document, method_quote, method_start, method_end,
                    f"EV-{document_index:03d}-M{item_index:02d}",
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
        evidence_registry: Dict[Tuple[str, int, int], str],
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
        selected = [
            row for row in question_rows
            if _QUESTION_CUES.search(row[0]) and not _PSEUDO_LINE.search(row[0])
            and not _is_table_like(row[0]) and not _is_section_run(row[0])
        ][:2]
        if not selected:
            selected = [row for row in question_rows
                        if not _PSEUDO_LINE.search(row[0]) and not _is_table_like(row[0]) and not _is_section_run(row[0])][:1]
        method_rows = [row for row in sentences
                       if _METHOD_CUES.search(row[0]) and _METHOD_VERB.search(row[0])
                       and not _PSEUDO_LINE.search(row[0])
                       and not _is_table_like(row[0]) and not _is_section_run(row[0])]
        results: List[ResearchQuestionCandidate] = []
        for item_index, (sentence, start, end) in enumerate(selected, start=1):
            method_row = min(method_rows, key=lambda row: abs(row[1] - start)) if method_rows else None
            method = _fallback_method_text(method_row[0]) if method_row else ""
            method_evidence = None
            if method_row:
                # 多个问题可能共用同一条最近方法句：注册表保证该切片只有一个证据 ID
                method_evidence = self._register_evidence(
                    evidence_registry, document, method_row[0], method_row[1], method_row[2],
                    f"EV-{document_index:03d}-M{item_index:02d}",
                )
            results.append(ResearchQuestionCandidate(
                candidate_id=f"RQC-{document_index:03d}-{item_index:02d}",
                document_id=document.document_id,
                question=_fallback_question_text(sentence),
                question_evidence=self._register_evidence(
                    evidence_registry, document, sentence, start, end,
                    f"EV-{document_index:03d}-Q{item_index:02d}",
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
    def _select_labels(
        matrix: np.ndarray,
        requested_k: Optional[int],
        min_k: int = 1,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        n = len(matrix)
        if n == 1:
            return np.zeros(1, dtype=int), {"selected_k": 1, "candidates": []}
        if requested_k:
            k = max(1, min(int(requested_k), n))
            labels = np.zeros(n, dtype=int) if k == 1 else _agglomerative(matrix, k)
            return labels, {"selected_k": k, "selection_mode": "requested", "candidates": []}
        floor = max(1, min(int(min_k), n))
        similarity = np.clip(matrix @ matrix.T, -1.0, 1.0)
        off_diagonal = similarity[~np.eye(n, dtype=bool)]
        if floor < 2 and (n <= 3 or (off_diagonal.size and float(np.mean(off_diagonal)) >= 0.78)):
            return np.zeros(n, dtype=int), {
                "selected_k": 1, "selection_mode": "automatic", "candidates": [],
            }
        upper = min(8, n - 1, max(2, int(round(math.sqrt(n))) + 1))
        upper = max(upper, floor)
        candidates: List[Dict[str, Any]] = []
        best: Optional[Tuple[float, np.ndarray, int]] = None
        for k in range(max(2, floor), upper + 1):
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
        if best is None or best[2] < floor:
            # 文献数下限兜底：多篇文献时不允许全部问题合并为单一簇——
            # 每篇文献的核心研究问题保持独立展示（2026-09-11 用户定稿）
            forced = _agglomerative(matrix, floor)
            if len(Counter(forced.tolist())) >= 2:
                return forced, {
                    "selected_k": floor, "selection_mode": "document_floor",
                    "candidates": candidates,
                }
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
        document_count: int = 1,
    ) -> Tuple[List[ResearchQuestionCluster], Dict[str, Any]]:
        representations = [
            f"{item.question}\n原文证据：{item.question_evidence.quote}" for item in candidates
        ]
        matrix, representation_name = self._encode(representations)
        # 文献内聚类 + 跨文献同方向合并（2026-09-11 定稿，阈值经理想数据
        # 实测校准：同方向问题句两两相似 0.726-0.933、不同方向 ≤0.624）：
        # ① 每篇文献的问题先在文献内聚类——同一文献的多个子问题可合并；
        # ② 两文献问题组质心余弦 ≥ 0.70（同一研究方向的 paraphrase 变体）
        #    才跨文献合并——热点排行反映"研究方向"而非单篇碎片。
        doc_of = [item.document_id for item in candidates]
        doc_groups: Dict[str, List[int]] = defaultdict(list)
        for index, doc_id in enumerate(doc_of):
            doc_groups[doc_id].append(index)
        blocks: List[List[int]] = []
        for doc_id in sorted(doc_groups):
            indices = doc_groups[doc_id]
            if len(indices) == 1:
                blocks.append(indices)
                continue
            # 文献内语义聚类（k=1 起步，簇数下限1）
            inner_labels, _ = self._select_labels(matrix[indices], None, min_k=1)
            inner_groups: Dict[int, List[int]] = defaultdict(list)
            for pos, label in enumerate(inner_labels.tolist()):
                inner_groups[int(label)].append(indices[pos])
            blocks.extend(sorted(inner_groups.values(), key=lambda rows: min(rows)))
        # 跨文献合并：质心相似度 ≥ 0.85 的块合并（贪心，保序）
        merged: List[List[int]] = []
        centroids: List[np.ndarray] = []
        for block in blocks:
            centroid = matrix[block].mean(axis=0)
            attached = False
            for seat in range(len(merged)):
                similarity = float(np.dot(centroid, centroids[seat]))
                if similarity >= 0.70:
                    merged[seat].extend(block)
                    centroids[seat] = matrix[merged[seat]].mean(axis=0)
                    attached = True
                    break
            if not attached:
                merged.append(list(block))
                centroids.append(centroid)
        ordered_groups = sorted(merged, key=lambda indices: min(indices))
        diagnostics: Dict[str, Any] = {
            "selection_mode": "per_document_merge_0.70",
            "selected_k": len(ordered_groups),
            "candidates": [],
        }
        clusters: List[ResearchQuestionCluster] = []
        for cluster_index, indices in enumerate(ordered_groups, start=1):
            members = [candidates[index] for index in indices]
            label, summary = self._induce_cluster(topic, members)
            # 簇内聚度始终输出浮点值：单例簇按自身余弦相似度取 1.0；
            # 计算失败输出 -1.0 异常标记（正常值域 [0,1]），不返回 null。
            cohesion = 1.0
            if len(indices) > 1:
                try:
                    block = matrix[indices] @ matrix[indices].T
                    values = block[np.triu_indices(len(indices), 1)]
                    cohesion = round(float(np.mean(values)), 6) if len(values) else 1.0
                except Exception:  # noqa: BLE001 - 编码矩阵异常时不允许输出 null
                    cohesion = -1.0
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

    def _method_progress(
        self,
        members: Sequence[ResearchQuestionCandidate],
        document_map: Mapping[str, ReviewDocument],
        method_text: str,
        evidence_values: Optional[Dict[str, ReviewEvidence]] = None,
        evidence_nodes: Optional[Dict[str, set]] = None,
        method_id: str = "M",
    ) -> List[Dict[str, Any]]:
        """研究进展条目：方法的实验结果/阶段结论（第三层）。

        每个方法组对应一套具体做法，从其来源文献的结果句（实验表明/
        提升幅度/outperform 等）归纳研究进展与阶段结论；LLM 归纳失败时
        确定性兜底=最佳结果句原文（可溯源，不编造）。证据句注册进
        evidence_index，供前端溯源 chips。
        """
        source_docs: list[ReviewDocument] = []
        for member in members:
            doc = document_map.get(member.document_id)
            if doc is not None and doc not in source_docs:
                source_docs.append(doc)
        # (句子, 文档, 起点, 终点)：偏移保留供证据注册与溯源定位
        result_rows: List[Tuple[str, ReviewDocument, int, int]] = []
        for doc in source_docs:
            for sentence, start, end in _sentences(doc.text):
                if (_PROGRESS_CUES.search(sentence)
                        and not _PSEUDO_LINE.search(sentence)
                        and not _is_table_like(sentence)
                        and not _is_section_run(sentence)):
                    result_rows.append((sentence, doc, start, end))
        def _result_row_score(row: Tuple[str, ReviewDocument, int, int]) -> float:
            text = row[0]
            has_numbers = 3.0 if re.search(r"\d+(?:\.\d+)?\s*(?:%|pp|points?)?", text) else 0.0
            cue_hits = min(3.0, float(len(_PROGRESS_CUES.findall(text))))
            length_penalty = max(0.0, (len(text) - 500)) / 500.0
            return has_numbers + cue_hits - length_penalty

        result_rows.sort(key=_result_row_score, reverse=True)
        top = result_rows[:4]
        if not top:
            return []
        # 证据注册 + source_evidence（前端"溯源询证"抽屉的数据源：
        # document_id/title/source_section/evidence_excerpt/offsets）
        registry: Dict[Tuple[str, int, int], str] = {}
        source_evidence: List[Dict[str, Any]] = []
        evidence_sentences: List[Dict[str, Any]] = []
        for text, doc, start, end in top:
            evidence = self._register_evidence(
                registry, doc, text, start, end, f"{method_id}-EV{len(source_evidence) + 1:02d}")
            if evidence_values is not None:
                evidence_values[evidence.evidence_id] = evidence
            if evidence_nodes is not None:
                evidence_nodes[evidence.evidence_id].add(method_id)
            excerpt = _clip_excerpt(text, 400)
            source_evidence.append({
                "evidence_id": evidence.evidence_id,
                "document_id": doc.document_id,
                "title": doc.title,
                "source_section": evidence.source_section,
                "evidence_excerpt": excerpt,
                "start": evidence.start,
                "end": evidence.end,
            })
            evidence_sentences.append(
                {"document_id": doc.document_id, "result": excerpt})
        summary = conclusion = ""
        if self.glm is not None:
            try:
                response = self.glm.chat_json(
                    "你是研究进展归纳器。仅依据给定的方法描述与实验结果句，归纳该方法的"
                    "研究进展（summary，1-2句，含关键数字）与阶段结论（conclusion，1句）；"
                    "summary 开头禁止复述方法做法本身，直接从实验设置/结果写起；"
                    "不得增加证据中没有的方法、数据或结论。"
                    '只输出JSON：{"data":{"summary":"...","conclusion":"..."}}',
                    json.dumps({
                        "method": method_text[:300],
                        "result_sentences": evidence_sentences,
                    }, ensure_ascii=False),
                    temperature=0.0, timeout=60.0, max_tokens=400,
                )
                data = response.get("data", response) if isinstance(response, dict) else {}
                summary = _clean(data.get("summary"))[:300]
                conclusion = _clean(data.get("conclusion"))[:200]
            except Exception:  # noqa: BLE001 - LLM 失败走原文兜底
                summary = conclusion = ""
        # 方法文本复述去重（用户定稿：内容一样就合并）：summary 开头与
        # 方法描述重叠（前缀最长公共块覆盖方法文本 55% 以上）时剪掉重复段
        if summary:
            summary = _strip_method_echo(summary, method_text)
        if not summary:
            summary = _clip_at_word(_sanitize_fragment(top[0][0]), 160)
        if not conclusion:
            conclusion = (_clip_at_word(_sanitize_fragment(top[1][0]), 120)
                          if len(top) > 1 else summary)
        return [{
            "progress_id": None,  # 由 build_output 按方法编号回填（M-01-P1）
            "summary": summary,
            "conclusion": conclusion,
            "source_ids": list(dict.fromkeys(doc.document_id for _, doc, _, _ in top)),
            "source_evidence": source_evidence,
            "evidence_sentences": evidence_sentences,
        }]

    def _trend_hotspot_distribution(
        self,
        documents: Sequence[ReviewDocument],
        cluster_rows: Sequence[Dict[str, Any]],
        topic: str = "",
    ) -> Dict[str, Any]:
        """趋势分析与研究热点分布（确定性计算，无额外 LLM 调用）。

        2026-09-11 用户定稿口径（理想数据校准后）：
        - 强度 = 0.4×年份新鲜度 + 0.25×主题相关性 + 0.2×连续年份覆盖度
          + 0.15×数量占比。跨文献合并阈值降至 0.70 后，同一研究方向的多篇
          文献会合并成簇，数量占比恢复区分度（碎片化时期曾移除）。
        - 年份新鲜度：簇内文献平均年份在全集时间窗的相对位置
          [0,1]（越靠窗尾越新）；窗口退化（单年份）时取 0.5。
        - 主题相关性：簇研究问题与综述主题的语义相似度（bge-m3 编码
          余弦，[-1,1] 映射到 [0,1]），编码失败取 0.5。
        - 连续年份覆盖度：簇出现的不连续年份占时间窗年数的比例——连续
          多年都有 → 方向持续热（状态升级为「持续热门」）；单年份窗口
          取 0.5 中性。
        - 趋势状态仍按年份分布判定；小样本/同年集合给出可靠性提示，
          不硬造区分度。
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
        year_span = known_years[-1] - known_years[0]
        max_docs = max((row.get("document_count", 0) for row in cluster_rows), default=0)

        # 主题相关性：主题与各簇研究问题一次批量编码
        relevance: Dict[str, float] = {str(row.get("cluster_id")): 0.5 for row in cluster_rows}
        try:
            texts = [str(topic or "")]
            for row in cluster_rows:
                questions = row.get("research_questions") or []
                cluster_text = " ".join(str(q) for q in questions[:6]).strip() \
                    or str(row.get("label") or "")
                texts.append(cluster_text)
            matrix, _ = self._encode(texts)
            topic_vector = matrix[0]
            for offset, row in enumerate(cluster_rows, start=1):
                similarity = float(np.dot(matrix[offset], topic_vector))
                relevance[str(row.get("cluster_id"))] = max(0.0, min(1.0, (similarity + 1.0) / 2.0))
        except Exception:  # noqa: BLE001 - 编码失败保持 0.5 中性值
            pass

        hotspots = []
        for row in cluster_rows:
            count = row.get("document_count", 0)
            years = [
                doc_year[doc_id]
                for doc_id in (row.get("document_ids") or [])
                if doc_year.get(doc_id)
            ]
            # 年份新鲜度：簇平均年份在时间窗的相对位置
            if years and year_span > 0:
                freshness = (sum(years) / len(years) - known_years[0]) / year_span
            else:
                freshness = 0.5
            # 连续年份覆盖度：簇出现过的年份数占时间窗年数的比例
            if year_span > 0:
                persistence = min(1.0, len(set(years)) / (year_span + 1)) if years else 0.0
            else:
                persistence = 0.5
            rel = relevance.get(str(row.get("cluster_id")), 0.5)
            count_ratio = (count / max_docs) if max_docs else 0.0
            score = round(max(0.05, min(1.0, 0.4 * freshness + 0.25 * rel
                                        + 0.2 * persistence + 0.15 * count_ratio)), 3)
            if years and len(known_years) > 1:
                recent = sum(1 for y in years if y >= median_year)
                if persistence >= 0.6:
                    status = "持续热门"
                elif recent == len(years) and min(years) >= median_year:
                    # 新兴热点须是"方向"新兴（≥2个年份或多篇文献），单篇新文献只算上升
                    status = "新兴热点" if (len(set(years)) >= 2 or count >= 2) else "上升趋势"
                elif recent * 2 >= len(years):
                    status = "上升趋势"
                else:
                    status = "持续关注"
            else:
                status = "持续关注"
            # 热点名优先用 LLM 归纳的类簇名（简洁主题短语）；类簇名缺失才退回
            # 首条研究问题——原始问题句是长句证据，直接当热点名会带出引用标记
            # 和句中残片（2026-09-11 热点乱码根因）
            questions = row.get("research_questions") or []
            name = (str(row.get("label") or "").strip()
                    or (str(questions[0]) if questions else str(row.get("cluster_id") or "")))
            hotspots.append({
                "name": name[:80],
                "score": score,
                "status": status,
                "cluster_id": row.get("cluster_id"),
                "document_count": count,
                "supporting_years": years,
                "year_coverage": round(persistence, 3),
            })
        hotspots.sort(key=lambda item: (-item["score"], item.get("cluster_id") or ""))
        # 可靠性提示：小样本/年份集中时如实降级，不硬造区分度
        notes = []
        if len(documents) < 5:
            notes.append(f"样本量小（{len(documents)}篇），强度与趋势仅供参考")
        if len(known_years) <= 1:
            notes.append("文献年份集中，趋势方向参考价值有限")
        return {
            "time_range": time_range,
            "hotspots": hotspots,
            "reliability_note": "；".join(notes) or None,
        }

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
            # 三层严格结构（用户定稿）：同一文献的方法面合并为一个方法节点——
            # 研究问题—研究方法—研究进展不重复罗列同文献的多个侧面；跨文献
            # （0.85 合并簇）的方法仍各自独立。文本取信息量最大者。
            _raw_groups = self._group_method_candidates(cluster.candidates)
            _group_docs: List[set] = []
            _method_groups: List[List[ResearchQuestionCandidate]] = []
            for _group in _raw_groups:
                _docs = {m.document_id for m in _group}
                _seat = next((i for i, ds in enumerate(_group_docs) if ds & _docs), None)
                if _seat is None:
                    _method_groups.append(list(_group))
                    _group_docs.append(_docs)
                else:
                    _method_groups[_seat].extend(_group)
                    _group_docs[_seat] |= _docs
            for members in _method_groups:
                method_sequence += 1
                method_id = f"M-{method_sequence:02d}"
                method_text = max((item.method for item in members if item.method), key=len)
                method_evidence_ids: List[str] = []
                source_ids: List[str] = []
                if len(method_text) < 30:
                    # 过短方法标签（LLM 抽到问题句的从句片段）→ 从来源文献
                    # 强动词方法句恢复：取"距问题证据最近"与"信息量最大"两句
                    # 中提取文本更长者；恢复句同样注册证据可溯源
                    for member in members:
                        document = document_map.get(member.document_id)
                        if document is None:
                            continue
                        verb_rows = [
                            row for row in _sentences(document.text)
                            if _METHOD_CUES.search(row[0]) and _METHOD_VERB.search(row[0])
                            and not _PSEUDO_LINE.search(row[0])
                            and not _is_table_like(row[0]) and not _is_section_run(row[0])
                        ]
                        if not verb_rows:
                            continue
                        nearest = min(verb_rows, key=lambda r: abs(r[1] - member.question_evidence.start))
                        richest = max(verb_rows, key=lambda r: min(len(r[0]), 420))
                        row = max((nearest, richest),
                                  key=lambda r: len(_fallback_method_text(r[0])))
                        better = _fallback_method_text(row[0])
                        if len(better) >= 30:
                            method_text = better
                            recovered_evidence = self._register_evidence(
                                {}, document, row[0], row[1], row[2],
                                f"EV-RC{method_sequence + 1:02d}")
                            evidence_values[recovered_evidence.evidence_id] = recovered_evidence
                            evidence_nodes[recovered_evidence.evidence_id].update({question_id})
                            method_evidence_ids.append(recovered_evidence.evidence_id)
                            break
                for member in members:
                    source_ids.append(member.document_id)
                    if member.method_evidence:
                        evidence = member.method_evidence
                        evidence_values[evidence.evidence_id] = evidence
                        evidence_nodes[evidence.evidence_id].update({question_id, method_id})
                        method_evidence_ids.append(evidence.evidence_id)
                # 第三层研究进展：方法组的结果句归纳（LLM，原文兜底）；
                # 证据注册进 evidence_index 并生成前端溯源询证的 source_evidence
                progress_rows = self._method_progress(
                    members, document_map, method_text,
                    evidence_values=evidence_values, evidence_nodes=evidence_nodes,
                    method_id=method_id)
                for progress_index, progress_row in enumerate(progress_rows, start=1):
                    progress_row["progress_id"] = f"{method_id}-P{progress_index}"
                methods.append({
                    "method_id": method_id,
                    "method": method_text,
                    "source_ids": list(dict.fromkeys(source_ids)),
                    "evidence_ids": list(dict.fromkeys(method_evidence_ids)),
                    "progress": progress_rows,
                })
            if not methods:
                # 空方法簇兜底（LLM 方法句定位失败的逐轮波动）：从来源文献
                # 证据句最近的方法句恢复，证据同样注册可溯源
                fallback_registry: Dict[Tuple[str, int, int], str] = {}
                seen_texts: set[str] = set()
                for candidate in cluster.candidates:
                    document = document_map.get(candidate.document_id)
                    if document is None:
                        continue
                    method_rows = [
                        row for row in _sentences(document.text)
                        if _METHOD_CUES.search(row[0]) and _METHOD_VERB.search(row[0])
                        and not _PSEUDO_LINE.search(row[0])
                        and not _is_table_like(row[0]) and not _is_section_run(row[0])
                    ]
                    if not method_rows:
                        continue
                    row = min(method_rows, key=lambda r: abs(r[1] - candidate.question_evidence.start))
                    method_text = _fallback_method_text(row[0])
                    if not method_text or _normal_key(method_text) in seen_texts:
                        continue
                    seen_texts.add(_normal_key(method_text))
                    method_sequence += 1
                    method_id = f"M-{method_sequence:02d}"
                    evidence = self._register_evidence(
                        fallback_registry, document, row[0], row[1], row[2],
                        f"EV-FB{method_sequence:02d}")
                    evidence_values[evidence.evidence_id] = evidence
                    evidence_nodes[evidence.evidence_id].update({question_id, method_id})
                    progress_rows = self._method_progress(
                        [candidate], document_map, method_text,
                        evidence_values=evidence_values, evidence_nodes=evidence_nodes,
                        method_id=method_id)
                    for progress_index, progress_row in enumerate(progress_rows, start=1):
                        progress_row["progress_id"] = f"{method_id}-P{progress_index}"
                    methods.append({
                        "method_id": method_id,
                        "method": method_text,
                        "source_ids": [candidate.document_id],
                        "evidence_ids": [evidence.evidence_id],
                        "progress": progress_rows,
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
            "induction_basis": "研究问题语义相似度、研究方法共现与来源证据一致性",
            "diagnostics": dict(diagnostics),
        }
        trend_hotspot = self._trend_hotspot_distribution(documents, cluster_rows, topic)
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
                "热点、时间演化或证据中不存在的结论。篇幅要求：概述 150-250 字；每章 "
                "200-400 字，需综合该簇全部文献写透——覆盖研究问题、代表方法与主要结果，"
                "文献间有对比或递进关系要写出来，不得只罗列文献名。只输出JSON："
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
                    temperature=0.0, timeout=180.0, max_tokens=4200,
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
        clusters, diagnostics = self.cluster_candidates(
            candidates, topic, requested_k, document_count=len(documents))
        return self.build_output(documents, clusters, topic, diagnostics)
