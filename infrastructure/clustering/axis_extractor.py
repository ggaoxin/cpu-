"""Evidence-bound LLM extraction for the two literature-clustering axes.

The model extracts phrases; it never assigns a document to a cluster and it is
never shown a topic catalogue.  Every accepted extraction must carry a quote
that can be found in the submitted document.  A failed or unverifiable item is
replaced by the deterministic local view for that item only.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

logger = logging.getLogger(__name__)

PROMPT_VERSION = "dual-axis-evidence-v4-full-text-excerpts"
_SPACE = re.compile(r"\s+")


SYSTEM_PROMPT = """你是科技文本的事实抽取器。输入可能是论文、科技报告、项目材料、标准说明或专利文本。
你的任务不是分类，也不是给文本分配主题或簇号。只从用户给出的 text 及可选的标题、关键词、摘要、
PDF全文证据片段中逐字抽取两个互不混淆的语义维度：

1. technical_route_terms：本文实际采用的研究设计、实验手段、算法、模型、测量或分析方法。
2. application_scenario_terms：本文实际研究或服务的场景核心短语。
3. application_domain_terms：应用行业、学科、疾病或现实业务领域；必须具体，不能只写“医学”“工业”等过宽词。
4. application_object_terms：研究、服务或操作的具体对象，例如疾病、患者、设备、作物、生态系统或交通系统。
5. application_problem_terms：应用中真正需要解决的现实问题，不是论文采用的算法名称。
6. application_task_terms：实际完成的任务，如诊断、监测、预测、治理或优化；不能单独用宽泛任务代替领域和对象。
7. application_environment_terms：使用环境、空间尺度或业务条件；原文没有则为空数组。

约束：
- 不允许使用任何预设主题库或类别表，不返回类别名称、类别编号或簇号。
- 每个维度返回1至6个简短术语，必须保持原文语言和原文措辞。
- 每个维度返回1至3条 evidence；evidence 必须是输入原文中可以逐字找到的连续短句。
- related work、背景中提及但本文没有采用的方法，不能写入 technical_route_terms。
- 研究结论、效果好坏、算法名称和泛词（研究、方法、模型、应用、分析）不能作为应用领域、对象或现实问题。
- application_scenario_evidence 应优先覆盖领域、对象和现实问题，不要只返回“预测”“评估”等通用任务句。
- 信息不足时返回空数组，不猜测、不补充常识。
- 必须逐个保留 document_id，不能漏项、合并或改变顺序。

只输出 JSON：
{"documents":[{"document_id":"...","technical_route_terms":["..."],
"technical_route_evidence":["原文短句"],"application_scenario_terms":["..."],
"application_domain_terms":["..."],"application_object_terms":["..."],
"application_problem_terms":["..."],"application_task_terms":["..."],
"application_environment_terms":["..."],
"application_scenario_evidence":["原文短句"]}]}"""


@dataclass
class AxisExtractionResult:
    technical_views: list[str]
    application_views: list[str]
    technical_evidence: list[list[str]]
    application_evidence: list[list[str]]
    metadata: dict[str, Any]
    application_facets: list[dict[str, list[str]]] = field(default_factory=list)


def _text(value: Any) -> str:
    return _SPACE.sub(" ", str(value or "")).strip()


_FULL_TEXT_CUES = re.compile(
    r"(?:方法|材料与方法|研究设计|实验设计|算法|模型|训练|测量|分析|流程|"
    r"应用于|用于|面向|场景|对象|诊断|检测|监测|预测|优化|治理|"
    r"method|methodology|materials and methods|study design|experimental setup|"
    r"algorithm|model|training|measurement|analysis|pipeline|applied to|"
    r"application|scenario|diagnosis|detection|monitoring|prediction|optimization)",
    re.IGNORECASE,
)


def _full_text_evidence_excerpt(paper: dict[str, Any], maximum: int = 16000) -> str:
    """Select source-grounded PDF text without sending an unbounded document.

    MinerU/PDF-reader text is retained verbatim apart from whitespace
    normalization.  Long files contribute the beginning plus windows around
    method/application cues.  This lets returned evidence pass exact-substring
    validation and prevents unrelated reference sections dominating the LLM.
    """
    if (paper.get("input_representation") or {}).get("mode") == "structured":
        return ""
    source = _text(paper.get("full_text"))
    if not source:
        return ""
    if len(source) <= maximum:
        return source
    windows = [source[:2600]]
    seen: set[tuple[int, int]] = set()
    for match in _FULL_TEXT_CUES.finditer(source):
        start = max(0, match.start() - 420)
        end = min(len(source), match.end() + 980)
        marker = (start // 300, end // 300)
        if marker in seen:
            continue
        seen.add(marker)
        windows.append(source[start:end])
        if sum(len(item) for item in windows) >= maximum:
            break
    return _text(" \n ".join(windows))[:maximum]


def _values(value: Any, *, maximum: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        item = _text(item).strip(" ,;，；。:：-—\"'")
        key = item.casefold()
        if not item or key in seen or len(item) > 240:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= maximum:
            break
    return result


def _source_text(paper: dict[str, Any]) -> str:
    return _text("\n".join((
        str(paper.get("semantic_title") or ""),
        "；".join(str(item) for item in paper.get("keywords") or []),
        str(paper.get("abstract") or "")[:6000],
        str(paper.get("semantic_text") or "")[:8000],
        _full_text_evidence_excerpt(paper),
    )))


def _verified_quotes(value: Any, source: str) -> list[str]:
    source_key = _text(source).casefold()
    quotes = _values(value, maximum=3)
    return [quote for quote in quotes if _text(quote).casefold() in source_key]


def _verified_terms(value: Any, source: str) -> list[str]:
    source_key = _text(source).casefold()
    terms = _values(value, maximum=6)
    return [term for term in terms if _text(term).casefold() in source_key]


def _view(axis: str, terms: list[str], evidence: list[str]) -> str:
    if axis == "technical":
        header = "scientific technical route, methodology, algorithm and study design"
    else:
        header = "scientific application scenario, studied object, task and domain"
    focus = "；".join(terms)
    # Repetition makes the chosen axis dominate the general-purpose embedding;
    # accepted content remains traceable to the document evidence.
    return _text(" ".join((header, focus, focus, focus, " ".join(evidence))))[:2400]


class EvidenceBoundAxisExtractor:
    """Batch GLM extractor with per-document evidence validation and cache."""

    def __init__(
        self,
        llm_client: Any,
        *,
        model_name: str,
        cache_dir: Path | None = None,
        batch_size: int = 6,
        required_axes: Sequence[str] = ("technical", "application"),
    ) -> None:
        self._llm = llm_client
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._batch_size = max(1, min(int(batch_size), 12))
        normalized_axes = tuple(dict.fromkeys(str(axis).strip().lower() for axis in required_axes))
        if not normalized_axes or any(axis not in {"technical", "application"} for axis in normalized_axes):
            raise ValueError("required_axes must contain technical and/or application")
        self._required_axes = normalized_axes
        self._service_unavailable = False
        self._service_error_type: str | None = None
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, paper: dict[str, Any]) -> str:
        payload = json.dumps({
            "prompt_version": PROMPT_VERSION,
            "model": self._model_name,
            "document_id": paper.get("document_id"),
            "source": _source_text(paper),
        }, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _read_cache(self, paper: dict[str, Any]) -> dict[str, Any] | None:
        if self._cache_dir is None:
            return None
        path = self._cache_dir / f"{self._key(paper)}.json"
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            return cached if cached.get("prompt_version") == PROMPT_VERSION else None
        except (OSError, json.JSONDecodeError, AttributeError):
            return None

    def _write_cache(self, paper: dict[str, Any], item: dict[str, Any]) -> None:
        if self._cache_dir is None:
            return
        path = self._cache_dir / f"{self._key(paper)}.json"
        payload = dict(item)
        payload["prompt_version"] = PROMPT_VERSION
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _request_item(paper: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_id": paper["document_id"],
            "text": (paper.get("semantic_text") or paper.get("abstract") or "")[:8000],
            "title": paper.get("semantic_title") or "",
            "keywords": paper.get("keywords") or [],
            "abstract": (paper.get("abstract") or "")[:6000],
            "full_text_evidence_excerpt": _full_text_evidence_excerpt(paper),
        }

    def _call(self, papers: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        payload = {"documents": [self._request_item(paper) for paper in papers]}
        if self._required_axes == ("application",):
            axis_instruction = (
                "本次只验收 application 相关字段；technical_route_terms 和 "
                "technical_route_evidence 可以返回空数组。"
            )
        elif self._required_axes == ("technical",):
            axis_instruction = (
                "本次只验收 technical 相关字段；所有 application 相关字段可以返回空数组。"
            )
        else:
            axis_instruction = "请完整抽取 technical 与 application 两个维度。"
        response = self._llm.chat_json(
            SYSTEM_PROMPT,
            axis_instruction + "\n请抽取以下文献：\n" + json.dumps(payload, ensure_ascii=False),
            timeout=120.0,
            max_tokens=max(1200, len(papers) * 420),
            temperature=0.0,
        )
        if isinstance(response.get("data"), dict):
            response = response["data"]
        rows = response.get("documents") if isinstance(response, dict) else None
        if not isinstance(rows, list):
            raise ValueError("Axis extractor response does not contain a documents array.")
        return {
            str(row.get("document_id")): row
            for row in rows if isinstance(row, dict) and row.get("document_id") is not None
        }

    def _call_resilient(
        self,
        papers: Sequence[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        """Bisect failed batches so one malformed document cannot drop peers."""
        if not papers:
            return {}, []
        try:
            rows = self._call(papers)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Axis extraction batch of %d failed: %s",
                len(papers), type(exc).__name__,
            )
            # Splitting cannot repair a global network/authentication failure
            # and would multiply API calls during an outage.
            if type(exc).__name__ in {
                "APIConnectionError", "AuthenticationError", "PermissionDeniedError",
            }:
                self._service_unavailable = True
                self._service_error_type = type(exc).__name__
                return {}, [paper["document_id"] for paper in papers]
            if len(papers) == 1:
                return {}, [papers[0]["document_id"]]
            middle = len(papers) // 2
            left_rows, left_failures = self._call_resilient(papers[:middle])
            right_rows, right_failures = self._call_resilient(papers[middle:])
            return {**left_rows, **right_rows}, left_failures + right_failures
        missing = [
            paper for paper in papers
            if paper["document_id"] not in rows
        ]
        if not missing:
            return rows, []
        # A syntactically valid response may still omit one item. Retry only
        # omitted items once through the same bisection path.
        retry_rows, failures = self._call_resilient(missing) if len(missing) < len(papers) else ({}, [
            paper["document_id"] for paper in missing
        ])
        return {**rows, **retry_rows}, failures

    def _validate(self, paper: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any] | None:
        source = _source_text(paper)
        technical_terms = _verified_terms(raw.get("technical_route_terms"), source)
        application_terms = _verified_terms(raw.get("application_scenario_terms"), source)
        # Facets may arrive as flat keys (live GLM JSON: application_domain_terms)
        # or as a nested dict (persisted cache: application_facets).  Accept both
        # so a cache round-trip does not silently drop every facet.
        nested = raw.get("application_facets") or {}
        application_facets = {
            "domain": _verified_terms(raw.get("application_domain_terms") or nested.get("domain"), source),
            "object": _verified_terms(raw.get("application_object_terms") or nested.get("object"), source),
            "problem": _verified_terms(raw.get("application_problem_terms") or nested.get("problem"), source),
            "task": _verified_terms(raw.get("application_task_terms") or nested.get("task"), source),
            "environment": _verified_terms(raw.get("application_environment_terms") or nested.get("environment"), source),
        }
        for values in application_facets.values():
            for term in values:
                if term not in application_terms:
                    application_terms.append(term)
        technical_evidence = _verified_quotes(raw.get("technical_route_evidence"), source)
        application_evidence = _verified_quotes(raw.get("application_scenario_evidence"), source)
        verified_axes = []
        if technical_terms and technical_evidence:
            verified_axes.append("technical")
        if application_terms and application_evidence:
            verified_axes.append("application")
        if any(axis not in verified_axes for axis in self._required_axes):
            return None
        return {
            "document_id": paper["document_id"],
            "technical_route_terms": technical_terms,
            "technical_route_evidence": technical_evidence,
            "application_scenario_terms": application_terms,
            "application_scenario_evidence": application_evidence,
            "application_facets": application_facets,
            "verified_axes": verified_axes,
        }

    def extract(
        self,
        papers: Sequence[dict[str, Any]],
        *,
        local_technical_views: Sequence[str],
        local_application_views: Sequence[str],
        local_technical_evidence: Sequence[Sequence[str]],
        local_application_evidence: Sequence[Sequence[str]],
    ) -> AxisExtractionResult:
        accepted: dict[str, dict[str, Any]] = {}
        pending: list[dict[str, Any]] = []
        cache_hits = 0
        failures: list[str] = []

        for paper in papers:
            cached = self._read_cache(paper)
            validated = self._validate(paper, cached) if cached else None
            if validated:
                accepted[paper["document_id"]] = validated
                cache_hits += 1
            else:
                pending.append(paper)

        for start in range(0, len(pending), self._batch_size):
            batch = pending[start:start + self._batch_size]
            if self._service_unavailable:
                failures.extend(paper["document_id"] for paper in batch)
                continue
            rows, call_failures = self._call_resilient(batch)
            failures.extend(call_failures)
            for paper in batch:
                row = rows.get(paper["document_id"], {})
                validated = self._validate(paper, row)
                if validated:
                    accepted[paper["document_id"]] = validated
                    self._write_cache(paper, validated)
                else:
                    failures.append(paper["document_id"])

        technical_views: list[str] = []
        application_views: list[str] = []
        technical_evidence: list[list[str]] = []
        application_evidence: list[list[str]] = []
        application_facets: list[dict[str, list[str]]] = []
        extraction_source: list[str] = []
        for index, paper in enumerate(papers):
            row = accepted.get(paper["document_id"])
            if row:
                if "technical" in row["verified_axes"]:
                    tech_evidence = row["technical_route_evidence"]
                    technical_views.append(_view("technical", row["technical_route_terms"], tech_evidence))
                    technical_evidence.append(tech_evidence)
                else:
                    technical_views.append(local_technical_views[index])
                    technical_evidence.append(list(local_technical_evidence[index]))
                if "application" in row["verified_axes"]:
                    app_evidence = row["application_scenario_evidence"]
                    application_views.append(_view("application", row["application_scenario_terms"], app_evidence))
                    application_evidence.append(app_evidence)
                    application_facets.append(row["application_facets"])
                else:
                    application_views.append(local_application_views[index])
                    application_evidence.append(list(local_application_evidence[index]))
                    application_facets.append({
                        "domain": [], "object": [], "problem": [], "task": [], "environment": [],
                        "general": [local_application_views[index]],
                    })
                extraction_source.append("llm_verified")
            else:
                technical_views.append(local_technical_views[index])
                application_views.append(local_application_views[index])
                technical_evidence.append(list(local_technical_evidence[index]))
                application_evidence.append(list(local_application_evidence[index]))
                application_facets.append({
                    "domain": [], "object": [], "problem": [], "task": [], "environment": [],
                    "general": [local_application_views[index]],
                })
                extraction_source.append("local_fallback")

        verified = len(accepted)
        fallback = len(papers) - verified
        mode = "llm_verified" if fallback == 0 else ("hybrid_fallback" if verified else "local_fallback")
        return AxisExtractionResult(
            technical_views=technical_views,
            application_views=application_views,
            technical_evidence=technical_evidence,
            application_evidence=application_evidence,
            metadata={
                "mode": mode,
                "prompt_version": PROMPT_VERSION,
                "model": self._model_name,
                "required_axes": list(self._required_axes),
                "document_count": len(papers),
                "verified_document_count": verified,
                "fallback_document_count": fallback,
                "cache_hit_count": cache_hits,
                "evidence_validation": "normalized_exact_substring",
                "llm_used": bool(accepted or pending),
                "llm_assigns_cluster_membership": False,
                "topic_library_used": False,
                "document_sources": extraction_source,
                "failed_document_ids": sorted(set(failures)),
                "service_error_type": self._service_error_type,
            },
            application_facets=application_facets,
        )
