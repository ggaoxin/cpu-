"""面向 Vue 的任务编排服务：输入适配、算法调用、结果归一化与持久化。"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import threading
from threading import Event
from typing import Any, Dict, List, Optional, Tuple

from application.dto.common_dto import SemanticRequest
import logging

logger = logging.getLogger(__name__)

from application.service.result_normalizer import normalize_result, _clean_cluster_term
from application.service.semantic_service import SemanticApplicationService
from config.settings import settings
from config.tool_contracts import ToolContract, get_contract
from config.vue_contracts import get_vue_contract
from domain.entity.analysis_task import AnalysisTask, ResultRecord, TaskStatus
from infrastructure.database.task_repository import DatabaseTaskRepository, task_repository
from infrastructure.database.resource_repository import DatabaseResourceRepository


DOMAIN_CODE_MAP = {
    "biomedical_informatics": "10",
    "medical_imaging": "10",
    "materials_science": "14",
    "new_energy": "20",
    "agricultural_technology": "12",
    "intelligent_manufacturing": "18",
    "environmental_science": "32",
}

# ------------------------------------------------------------------ #
# 引用句识别文本模式自动派生：文献文本 + 参考文献条目 → 引用句上下文 + 被引元数据
# ------------------------------------------------------------------ #
_CITE_MARKER_RE = re.compile(r"\[(\d+(?:\s*[,，\-–~]\s*\d+)*)\]")
# 短编号标题整行（"0 引 言"/"1 绪论"）：数字+空格+短中文、无标点，
# PyMuPDF 硬换行下若不识别会粘连进正文句首
_SHORT_HEADING_RE = re.compile(r"\d{1,2}(?:\.\d{1,2}){0,2}\s+[一-鿿][一-鿿\s]{1,11}")
# 整行作者署名（全行仅人名[+星号/括号单位]，逗号分隔）："蒲兴梅,熊成艳*,陈秋媛(单位)"
# fullmatch 防误杀：正文"不断积累,护理实习生的学习…"含谓语余文不匹配
_AUTHOR_LINE_RE = re.compile(
    r"[一-鿿]{2,4}[*\s]*(?:[,，、]\s*[一-鿿]{2,4}[*\s]*)+[,，。]?\s*(?:[\(（].*|\*.*)?")


def _split_sentences_for_citation(text: str) -> list:
    """中英混排分句(句末标点)，供引用句定位与上下文截取。

    不按裸换行分句（2026-09-10，BOPPS.pdf 案例）：PyMuPDF 文本硬换行，
    原 ``|\\n+`` 会把句尾碎片当独立句——"…技能熟\\n练度提出了较高要求[1]”被
    切成"练度提出了较高要求[1]"，引用句/上下文全成碎片。改为只按句末标点
    分句；markdown 标题/#编号行/参考文献条目行([n]开头)保留独立成句，
    其余换行并入上一句续接。与引擎内 _extract_citations 的分句口径一致。
    """
    # 缩写句点保护（与引擎 _extract_citations 同款）：et al./Fig./Eq. 等的句点
    # 不是句边界——35.pdf "Shumailov et al. [2024] that…" 曾在 et al. 处断成
    # "[2024] that…" 碎片句。先替换占位符，分完句再还原。
    for _abbr in ("et al.", "et al．", "Fig.", "Eq.", "No.", "Vol.", "pp.", "cf.", "i.e.", "e.g.", "w.r.t."):
        text = text.replace(_abbr, _abbr.replace(".", "§"))
    parts = re.split(r"(?<=[。！？!?])\s*|(?<=\.)\s+", text)
    # 期刊首页元数据行（收稿日期/基金项目/作者简介等）：整行丢弃，不进句流
    # ——否则无句末标点的元数据块会向前/向后粘连污染引用句（BOPPS.pdf 案例）。
    # 不能加 re.IGNORECASE：^[a-z]+[A-Z]（驼峰粘连 ofTraditional…）忽略大小写
    # 后退化成"任意两字母"，会误杀所有英文正文行（35.pdf 踩过）；大小写
    # 变体（doi/www/Keywords）在模式里显式枚举。
    _meta_line = re.compile(
        r"^[\[【（(]?\s*(收稿日期|网络首发|基金项目|作者简介|通信作者|作者单位|单位地址|"
        r"中图分类号|文献标识码|文章编号|引用格式|[dD][oO][iI]|ISSN|CN\s?\d|https?://|[wW][wW][wW]\.)"
        r"|^\*?\*?基金|^[Kk]eywords?\s*[:：]|^KEYWORDS\s*[:：]|^关键词\s*[:：]"
        # 期刊首页非正文行：页脚（—932—/纯数字）、作者署名列表（"名,名,*"）、
        # 括号单位行（"(xx大学/医院…550000)"）——无句末标点，会向前粘连污染引用句
        r"|^—\d+—$|^\d{1,4}$"
        r"|^[—–]+\s*\*?"
        # 英文脚注/作者/单位行（"* CHEN…" / "Department of…" / "…University"）：
        # 无句末标点会向后粘进摘要首句
        r"|^\*+\s*[A-Za-z]"
        r"|^(Department|College|School|Hospital|Institute|Faculty)\s+(of|in)\b"
        r"|[A-Za-z]{2,}(University|Hospital|College|Institute)\b"
        r"|^[a-z]+[A-Z]"
        r"|^[\(（].{0,60}?(大学|学院|医院|研究所|中心|实验室|附属医院).*\d{4,}"
        r"|^\*{1,2}通信作者|^〔\(（]通信作者")
    out: list = []
    for part in parts:
        first_line_of_part = True
        last_line_boundary = False
        for line in part.split("\n"):
            line = line.strip()
            if not line or _meta_line.match(line) or _AUTHOR_LINE_RE.fullmatch(line):
                continue
            # 行首边界：markdown #、[n] 参考文献条目、"1.1/1．/1、"编号标题、
            # 摘要/关键词段标——这些行独立成句，后续正文行不与其粘连
            starts_new = bool(re.match(
                r"^#{1,6}\s"
                # [n] 行首：仅当 ] 后是正常文字（参考文献条目）；] 后紧跟
                # 逗号/顿号/句号 = PDF 换行恰落在句中标记前，是续行并入上一句
                r"|^\[\d+(?:[-–,，]\d+)*\]\s*[^，,、。；;]"
                r"|^\d+(?:[.．、]|\.\d+)"
                r"|^[【\[]?\s*(?:摘\s*要|Abstract|ABSTRACT)\s*[】\]]?\s*[:：]?", line))
            # 行首 [n] 且上一行未结句（last_line_boundary=False）= PDF 硬换行
            # 恰好落在句中标记前（35.pdf "Dey and Donoho\n[2024] provide…"），
            # 是续行并入上一句，不是参考文献条目；行首 ] 是括号跨行，同理。
            # 参考文献条目（"[2]杨发奋…"）总在上一句结束后出现——那时它是
            # 标点切分后新 part 的首行，走 first_line_of_part 分支独立成句。
            if out and not first_line_of_part and not last_line_boundary and (
                    re.match(r"^\[\d+(?:[-–,，]\d+)*\]", line)
                    or line.startswith(("]", "］"))):
                starts_new = False
            # 短编号标题整行（"0 引 言"：数字+空格+短中文、无标点）= 句边界
            if _SHORT_HEADING_RE.fullmatch(line):
                starts_new = True
            if out and not first_line_of_part and not starts_new and not last_line_boundary:
                # 普通硬换行：续接上一句。英文词间补空格防粘连（CJK 不需要）
                if out[-1] and line and out[-1][-1].isascii() and out[-1][-1].isalnum() \
                        and line[0].isascii() and line[0].isalnum():
                    out[-1] += " " + line
                else:
                    out[-1] += line
            else:
                out.append(line)
            first_line_of_part = False
            # 行尾冒号/分号（如"…如公式(3)所示:"）后常跟公式/图表段，
            # 保守视为句边界，防止跨段粘连成超长句
            last_line_boundary = starts_new or line.endswith(("：", ":", "；", ";"))
    return [s.replace("§", ".") for s in out]


def _marker_nums_of(marker: str) -> list:
    """单个引用标记文本(如 "[4-6]"/"[1,3]"/"[2]")展开为文献编号列表。
    区间 [4-6] 展开为 4,5,6（findall 只能取到端点 4/6，会漏区间内编号）。"""
    nums: list = []
    for part in re.split(r"[,，]", marker.strip().lstrip("[").rstrip("]")):
        part = part.strip()
        if re.fullmatch(r"\d+\s*[-–~]\s*\d+", part):
            a, b = re.split(r"[-–~]", part)
            nums.extend(range(int(a), int(b) + 1))
        elif part.isdigit():
            nums.append(int(part))
    return nums


def _citation_sub_span(sentence: str, marker_num: int) -> str:
    """句内多引用拆分的局部子片段：[num] 标记所在子句(按，,；;切分)去掉全部
    引用标记后的语义片段；所在子句去标记后为空时回退整句去标记。
    [n,m] 复合标记内的逗号不是子句边界(扫描时跳过方括号内的分隔符)。"""
    marker_re = re.compile(r"\[\d+(?:\s*[,，\-–~]\s*\d+)*\]")
    target_pos = -1
    for m in marker_re.finditer(sentence):
        if marker_num in _marker_nums_of(m.group()):
            target_pos = m.start()
            break
    if target_pos < 0:
        return ""
    start, end = 0, len(sentence)
    in_bracket = False
    for i, ch in enumerate(sentence):
        if ch == "[":
            in_bracket = True
        elif ch == "]":
            in_bracket = False
        elif ch in "，,；;" and not in_bracket and i < target_pos:
            start = i + 1
    in_bracket = False
    for i in range(target_pos, len(sentence)):
        ch = sentence[i]
        if ch == "[":
            in_bracket = True
        elif ch == "]":
            in_bracket = False
        elif ch in "，,；;" and not in_bracket:
            end = i
            break
    def _clean(fragment: str) -> str:
        return re.sub(r"\s+", " ", marker_re.sub("", fragment)).strip().rstrip("。．.!！?？；;，,、").strip()
    return _clean(sentence[start:end]) or _clean(sentence)


def _extract_citation_contexts(document_text: str, limit: int = 30) -> list:
    """定位带引用标记([1]/[2,3]/[4-6])的句子,取前句/后句为上下文。

    句内含多个文献编号时按编号拆分为多条:citation_sentence 保留完整原句,
    citation_marker 绑定单个编号,citation_sub_span 为该编号所在子句的局部
    语义片段(意图判定优先采用)。返回 contexts 条目(含 previous_context/
    next_context 与内部 _marker_nums),超出 limit 截断。
    """
    # 全角标记归一化（与引擎 _extract_citations 同款）：中文期刊 PDF 常用
    # ［1］/［1-2］/［1，2］，_CITE_MARKER_RE 只认半角（LSTM.pdf 34 处全角
    # 曾全部漏抽，掉进引擎全文兜底）。仅归一化纯数字/连字符/逗号内容。
    document_text = re.sub(
        r"［\s*([0-9\-–,，\s]+?)\s*］",
        lambda m: "[" + m.group(1).replace("，", ",") + "]", document_text)
    sentences = _split_sentences_for_citation(document_text)
    contexts = []
    for i, sent in enumerate(sentences):
        markers = _CITE_MARKER_RE.findall(sent)
        if not markers:
            continue
        nums = []
        for m in markers:
            nums.extend(_marker_nums_of(m))
        if not nums:
            continue
        for num in sorted(set(nums)):
            contexts.append({
                "citation_sentence": sent,
                "previous_context": sentences[i - 1] if i > 0 else "（文档开头，无上文）",
                "next_context": sentences[i + 1] if i + 1 < len(sentences) else "（文档结尾，无下文）",
                "citation_marker": f"[{num}]",
                "citation_sub_span": _citation_sub_span(sent, num),
                "_marker_nums": [num],
            })
            if len(contexts) >= limit:
                return contexts
    return contexts


def _parse_reference_entries(entries_raw: str) -> list:
    """GLM 解析参考文献条目原文 → 结构化元数据列表(按条目序号)。

    兼容逐行条目与单行长文本(按 [n]/n. 序号切分),单次 GLM 调用批量解析,
    上限 60 条。解析结果带 reference_index 供引用标记匹配。
    """
    from infrastructure.llm.glm_client import glm_client
    lines = [l.strip() for l in entries_raw.splitlines() if l.strip()]
    if len(lines) <= 1 and entries_raw.strip():
        lines = [s.strip() for s in re.split(r"(?=\[\d+\])|(?=\d+[.、]\s)", entries_raw) if s.strip()]
    if not lines:
        return []
    lines = lines[:60]
    system = ("你是参考文献解析器。把用户给出的每条参考文献条目解析为结构化字段，"
              "严格按条目原文，不得编造。返回 JSON {data:[{index, authors, title, year, venue, doi}]}："
              "index=条目序号(条目开头的[n]或n.的数字,无序号按顺序1起)；authors=作者数组(原文人名)；"
              "title=题名；year=发表年份整数(无则null)；venue=期刊/会议/出版社；doi=DOI(无则空串)。")
    user = "解析以下参考文献条目：\n" + "\n".join(lines)
    out = glm_client.chat_json(system, user, timeout=90.0, max_tokens=4000)
    data = out.get("data", out) if isinstance(out, dict) else []
    metadata = []
    for pos, item in enumerate(data if isinstance(data, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index") or pos)
        except (TypeError, ValueError):
            idx = pos
        metadata.append({
            "citation_id": f"cite-{idx}",
            "reference_index": idx,
            "authors": item.get("authors") if isinstance(item.get("authors"), list) else
                       ([str(item.get("authors"))] if item.get("authors") else []),
            "title": str(item.get("title") or ""),
            "year": item.get("year"),
            "venue": str(item.get("venue") or ""),
            "doi": str(item.get("doi") or ""),
        })
    return metadata

# Public V7.74 field used as the actual document/text input for each tool.
# These names are intentionally duplicated from config.vue_contracts only as a
# defensive adapter table: the public request is preserved in the task record,
# while the internal aliases below keep the existing algorithms unchanged.
PRIMARY_TEXT_FIELDS = {
    "zh-abstract-move": "chinese_scientific_abstract",
    "en-abstract-move": "english_scientific_abstract",
    "fund-move": "project_document_text",
    "zh-classify": "chinese_scientific_document_text",
    "en-classify": "english_scientific_document_text",
    "domain-classify": "domain_scientific_literature_data",
    "zh-keyword": "chinese_scientific_abstract",
    "en-keyword": "english_scientific_abstract",
    "rq-detect": "scientific_document_fragment",
    "citation-sentiment": "scientific_document_full_text",
    "citation-intent": "scientific_document_full_text",
    "definition-detect": "scientific_document_fragment_or_batch_text",
    "general-ner": "bilingual_scientific_document_text",
    "research-ner": "academic_abstract_or_technical_report_text",
    "domain-ner": "domain_scientific_document_text",
    "deep-cluster": "scientific_document_texts",
    "structured-review": "document_set",
}

REQUIRED_RESOURCE_FIELDS = {
    "zh-classify": ("clc_labeled_data",),
    "en-classify": ("clc_labeled_data",),  # zh/en 共用同一份 CLC 资源（DB 一行、下拉一致、建库一次）
    "domain-classify": ("domain_classification_rules", "manually_labeled_training_data"),
    "en-keyword": ("domain_terminology_library", "classification_standard_mapping_table"),
    "citation-intent": ("preprocessed_training_set",),
    "general-ner": ("general_domain_annotated_corpus",),
    "research-ner": ("multi_domain_scientific_corpus", "manually_labeled_data"),
    "domain-ner": ("ontology_classification_system", "domain_labeled_training_data"),
}

SEMANTIC_RESOURCE_FIELDS = frozenset(field for fields in REQUIRED_RESOURCE_FIELDS.values() for field in fields)


def _extract_domain_term_entries(payload: Dict[str, Any]) -> list:
    """解包"领域术语资源"嵌套格式为词典条目列表 [{term, weight}]。

    支持格式：
    {
      "domain_term_resource": {"材料科学": {"term_list": ["晶格缺陷", ...], "base_weight": 1.7}, ...},
      "general_sci_term": ["实验结果", ...],
      "general_weight": 1.0
    }
    """
    entries: list = []
    resource = payload.get("domain_term_resource")
    if isinstance(resource, dict):
        for _domain, spec in resource.items():
            if not isinstance(spec, dict):
                continue
            weight = spec.get("base_weight")
            for term in spec.get("term_list") or []:
                text = str(term or "").strip()
                if text:
                    entries.append({"term": text, "weight": weight})
    general = payload.get("general_sci_term")
    if isinstance(general, list):
        general_weight = payload.get("general_weight")
        for term in general:
            text = str(term or "").strip()
            if text:
                entries.append({"term": text, "weight": general_weight})
    return entries


_TASK_EXECUTOR = ThreadPoolExecutor(max_workers=settings.ASYNC_WORKERS, thread_name_prefix="semantic-task")

# 进程级 GLM 并发闸口：解决 _TASK_EXECUTOR(4) × group线程池(6) 嵌套导致的线程爆炸。
# 多个批量任务同时跑时，全进程在途 GLM 调用总数不超过此值，钳制 GLM QPS 不超限。
# 阻塞在信号量上的线程不占 CPU（OS 级 wait），仅占线程栈内存。

# ---- 批量执行进程池 worker（fork 继承，无需 pickle service）----
_FORK_SERVICE: Any = None
_FORK_LOCK = threading.Lock()
_FORK_ACTIVE = 0          # 当前活跃 fork 子进程数（防多任务同时批量时进程爆炸）
_FORK_MAX_TOTAL = 12      # 全局 fork 子进程上限（6 worker × 2 任务 = 12 已饱和 8 核）

def _fork_execute_group(args: tuple) -> Dict[str, Any]:
    """子进程 worker：重新初始化 DB 连接（fork 的连接已失效），执行单篇。

    fork 语义：子进程继承父进程全部内存（含 _FORK_SERVICE=ToolIntegrationService
    实例，内含 GLM client / semantic_service 等），只需重建 DB 连接。
    args = (index, group_dicts, params, payload, tool_id, contract_tuple, task_id)
    """
    (index, group_dicts, params, payload, tool_id, backend_code, task_id) = args
    service = _FORK_SERVICE
    if service is None:
        return {"index": index, "status": "failed", "error": "fork service 未初始化",
                "item_id": None, "record_id": None, "input_id": None,
                "file_name": None, "source": {}, "result": {}}
    # DB 连接 fork 后失效：重建（SQLAlchemy 连接池不可跨进程）
    try:
        from infrastructure.database.connection import database as _db
        _db.dispose()
        _db.initialize()
        service.repository = type(service.repository)()
    except Exception:  # noqa: BLE001
        pass
    # OpenAI SDK httpx 连接池 fork 后 TCP 连接失效（实测 RemoteProtocolError:
    # Server disconnected）——子进程重建 GLM client
    try:
        from infrastructure.llm.glm_client import GLMClient
        service.semantic_service._glm = GLMClient()
    except Exception:  # noqa: BLE001
        pass
    # 构造 InputItem（dict → NamedTuple）
    group = [InputItem(**d) if isinstance(d, dict) else d for d in group_dicts]
    contract = get_contract(tool_id)
    try:
        result = service._execute_group_once(
            task_id=task_id, tool_id=tool_id, contract=contract,
            index=index, group=group, params=params, payload=payload,
            cancelled=threading.Event(),  # fork 无跨进程取消，空 Event 即不取消
        )
        return result
    except Exception as exc:  # noqa: BLE001
        return {"index": index, "status": "failed", "error": f"进程执行异常: {exc}",
                "item_id": None, "record_id": None, "input_id": None,
                "file_name": None, "source": {}, "result": {}}

_GLM_SEMAPHORE = threading.BoundedSemaphore(settings.GLM_MAX_CONCURRENCY)


def _today_str() -> str:
    """当前日期 YYYY-MM-DD(发表时间不得晚于今天的一致判据)。"""
    from datetime import date
    return date.today().isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    # 北京时间（+08:00）：记录/展示统一用标准北京时间，不再存 UTC
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


@dataclass
class InputItem:
    input_id: str
    text: str
    source: Dict[str, Any]


class ToolIntegrationService:
    def __init__(
        self,
        semantic_service: SemanticApplicationService,
        repository: Optional[DatabaseTaskRepository] = None,
        resource_repository: Optional[DatabaseResourceRepository] = None,
    ) -> None:
        self.semantic_service = semantic_service
        self.repository = repository or task_repository
        self.resource_repository = resource_repository or DatabaseResourceRepository(self.repository.db)

    def execute(
        self,
        tool_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        file_inputs: Optional[List[Dict[str, str]]] = None,
        workspace_id: Optional[str] = None,
        _task_id: Optional[str] = None,
        _created_event: Optional[Event] = None,
    ) -> Dict[str, Any]:
        try:
            return self._run_execute(
                tool_id,
                payload,
                file_inputs=file_inputs,
                workspace_id=workspace_id,
                _task_id=_task_id,
                _created_event=_created_event,
            )
        finally:
            self._cleanup_temp_files(file_inputs)
            # 一次性上传语义（2026-09-04 用户定调）：用户上传的资源随本次测试结束即删
            # （数据库行 + 磁盘文件），不保存复用；内置 bundled 资源不受影响
            try:
                self._cleanup_request_resources(payload)
            except Exception:  # noqa: BLE001 - 清理失败不影响结果返回
                logger.warning("一次性上传资源清理失败", exc_info=True)

    def _cleanup_request_resources(self, payload: Optional[Dict[str, Any]]) -> None:
        """删除本次请求引用的全部用户上传型资源（行 + 文件）。

        递归收集 payload 里的 resource_id（含 {source:'upload'} 描述符与
        {source:'database', resource_id} 两种形态），逐个查库：source_type='upload'
        才删（内置 bundled 永不删）。同步 execute 与异步 submit（经执行器最终也走
        execute）都在 finally 触发，保证测试结束即清理。
        """
        from pathlib import Path as _P
        ids: set = set()

        def _walk(value: Any) -> None:
            if isinstance(value, dict):
                rid = value.get("resource_id")
                if isinstance(rid, str) and rid.startswith("res_"):
                    ids.add(rid)
                for v in value.values():
                    _walk(v)
            elif isinstance(value, (list, tuple)):
                for v in value:
                    _walk(v)

        _walk(payload or {})
        for rid in sorted(ids):
            row = self.resource_repository.get_semantic_resource(rid)
            if not row or row.get("source_type") != "upload":
                continue
            uri = str(row.get("storage_uri") or "")
            if uri:
                path = _P(uri.removeprefix("project://")) if uri.startswith("project://") else _P(uri)
                try:
                    if "semantic_resources" in path.parts and path.is_file():
                        path.unlink()
                except OSError:
                    logger.warning("一次性资源文件删除失败: %s", path, exc_info=True)
            self.resource_repository.delete_semantic_resource(rid)
            logger.info("一次性上传资源已清理: %s (%s)", rid, row.get("name"))

    @staticmethod
    def _cleanup_temp_files(file_inputs: Optional[List[Dict[str, str]]]) -> None:
        """清理 save_uploads_to_temp 落盘的临时上传文件（_temp 标记）。"""
        for item in file_inputs or []:
            path = item.get("path") if isinstance(item, dict) else None
            if path and item.get("_temp"):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _run_execute(
        self,
        tool_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        file_inputs: Optional[List[Dict[str, str]]] = None,
        workspace_id: Optional[str] = None,
        _task_id: Optional[str] = None,
        _created_event: Optional[Event] = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        request_id = _id("req")
        contract = get_contract(tool_id)
        payload = self._adapt_vue_payload(contract, dict(payload or {}))
        # 引用工具文本模式自动派生：文献文本+参考文献条目 → 引用句上下文+被引元数据
        # （用户只需提供两项输入；手动提供 citation_sentence_and_context 时不覆盖）。
        # 文件/批量文件模式的 PDF 解析与引用句拆分在 _semantic_request 内完成
        # （路径透传延迟解析后才能拿到全文，详见 citation- 分支）。
        if tool_id.startswith("citation-") and str(payload.get("input_type") or "text") == "text":
            try:
                self._derive_citation_inputs(payload)
            except ValueError as exc:
                fallback_type = str(payload.get("input_type") or "text")
                return self._validation_error(contract, request_id, fallback_type, started, str(exc))
            except Exception as exc:  # noqa: BLE001 - 派生失败回落手动输入校验
                logger.warning("引用句自动派生异常：%s", exc)
        workspace_id = workspace_id or settings.DEFAULT_WORKSPACE_ID
        input_type = str(payload.get("input_type") or ("files" if file_inputs else "text"))
        try:
            params = self._parameters(contract, payload)
        except ValueError as exc:
            return self._validation_error(contract, request_id, input_type, started, str(exc))
        payload_error = self._payload_error(contract, payload)
        if payload_error:
            return self._validation_error(contract, request_id, input_type, started, payload_error)
        try:
            inputs = self._inputs(contract, payload, file_inputs or [])
        except ValueError as exc:
            return self._validation_error(contract, request_id, input_type, started, str(exc))
        if not inputs:
            return self._validation_error(contract, request_id, input_type, started, "没有可处理的输入数据")
        minimum = 1 if input_type in {"cluster_task", "upstream_records"} else contract.min_items
        if len(inputs) < minimum:
            detail = f"（当前 {len(inputs)} 项）"
            if input_type == "collection":
                detail = f"（指定文献集仅包含 {len(inputs)} 篇）"
            return self._validation_error(
                contract, request_id, input_type, started, f"至少需要 {minimum} 项输入数据{detail}",
            )
        if len(inputs) > contract.max_items:
            return self._validation_error(contract, request_id, input_type, started, f"输入数据不能超过 {contract.max_items} 项")
        # cluster_count 预检：非法值在任务创建前拦截（服务层校验保留为兜底），
        # 避免"任务已创建、执行后才失败"。
        if contract.tool_id == "deep-cluster":
            cluster_count_error = self._cluster_count_error(payload.get("cluster_count"), len(inputs))
            if cluster_count_error:
                return self._validation_error(contract, request_id, input_type, started, cluster_count_error)

        task_id = _task_id or _id("tsk")
        task = AnalysisTask(
            id=task_id,
            workspace_id=workspace_id,
            tool_id=tool_id,
            backend_code=contract.backend_code,
            input_type=input_type,
            total=1 if contract.collection_tool else len(inputs),
            parameters=params,
            request_payload=self._safe_payload(payload, file_inputs or []),
            model_version=settings.MODEL_VERSION,
        )
        self.repository.create_task(task)
        if _created_event:
            _created_event.set()
        self.repository.update_task_status(task_id, TaskStatus.RUNNING, progress=1)

        results: List[Dict[str, Any]] = []
        success_count = 0
        failed_count = 0
        execution_groups = [inputs] if contract.collection_tool else [[item] for item in inputs]
        total = len(execution_groups)

        # 并发启用条件：逐篇工具 + group 数 ≥ 2 + 并发配置 > 1。
        # collection_tool（整体一个 group）和单篇输入走串行，避免线程池开销。
        use_concurrent = (
            not contract.collection_tool
            and total >= 2
            and settings.GLM_MAX_CONCURRENCY > 1
        )

        if use_concurrent:
            success_count, failed_count = self._run_groups_concurrent(
                task_id=task_id, tool_id=tool_id, contract=contract,
                execution_groups=execution_groups, params=params, payload=payload,
                results_out=results,
            )
        else:
            cancelled_event = threading.Event()
            for index, group in enumerate(execution_groups):
                if self._task_cancelled(task_id):
                    break
                result = self._execute_group_once(
                    task_id=task_id, tool_id=tool_id, contract=contract, index=index,
                    group=group, params=params, payload=payload, cancelled=cancelled_event,
                )
                results.append(result)
                if result["status"] == "succeeded":
                    success_count += 1
                elif result["status"] == "failed":
                    failed_count += 1
                if self._task_cancelled(task_id):
                    cancelled_event.set()
                    break
                self.repository.update_task_status(
                    task_id,
                    TaskStatus.RUNNING,
                    progress=min(95, max(1, int((index + 1) / total * 95))),
                    success_count=success_count,
                    failed_count=failed_count,
                )

        current_task = self.repository.get_task(task_id)
        if current_task and current_task.get("status") == TaskStatus.CANCELLED.value:
            status = TaskStatus.CANCELLED
        elif success_count == total:
            status = TaskStatus.SUCCEEDED
        elif success_count:
            status = TaskStatus.PARTIAL_FAILED
        else:
            status = TaskStatus.FAILED
        error_summary = next((item.get("error") for item in results if item.get("error")), None)
        # 引用工具文件模式整批解析失败（损坏/扫描 PDF）：升级为 42201 业务响应，
        # 在线测试页直接展示 message（业务提示文案由 _semantic_request 注入），
        # 不以 50001/"failed" 暴露给用户；部分失败维持逐条 failed 明细
        if (
            status is TaskStatus.FAILED
            and tool_id.startswith("citation-")
            and input_type in {"file", "files"}
            and error_summary
            and str(error_summary).startswith("文件解析失败")
        ):
            self.repository.update_task_status(
                task_id, TaskStatus.FAILED, progress=100,
                success_count=success_count, failed_count=failed_count,
                error_summary=error_summary,
            )
            return self._validation_error(contract, request_id, input_type, started, str(error_summary))

        # 全部失败且错误同类（2026-09-10 用户需求）：批量上传整批同类错误（如英文论文
        # 全部进中文工具的语言不匹配）不逐条重复 6 次，直接返回一条干净的错误提示
        if status is TaskStatus.FAILED and results:
            _all_errors = [str(r.get("error") or "") for r in results if r.get("error")]
            _common_prefixes = ("语言不匹配", "文件解析失败", "预解析结果已过期")
            for _prefix in _common_prefixes:
                if _all_errors and all(e.startswith(_prefix) for e in _all_errors):
                    self.repository.update_task_status(
                        task_id, TaskStatus.FAILED, progress=100,
                        success_count=0, failed_count=failed_count,
                        error_summary=_all_errors[0],
                    )
                    return self._validation_error(
                        contract, request_id, input_type, started, _all_errors[0])
        self.repository.update_task_status(
            task_id, status, progress=100,
            success_count=success_count, failed_count=failed_count,
            error_summary=error_summary,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "code": 0 if status != TaskStatus.FAILED else 50001,
            "message": status.value,
            "data": {
                "task_id": task_id,
                "tool_id": tool_id,
                "status": status.value,
                "input_type": input_type,
                "progress": 100,
                "total": total,
                "success_count": success_count,
                "failed_count": failed_count,
                "error_summary": error_summary,
                "results": results,
                "summary": self._summary(results),
                "available_exports": list(contract.export_formats),
            },
            "meta": {
                "request_id": request_id,
                "schema_version": "1.0",
                "model_version": settings.MODEL_VERSION,
                "taxonomy_version": payload.get("taxonomy_version_id"),
                "ontology_version": payload.get("ontology_version_id"),
                "elapsed_ms": elapsed_ms,
                "created_at": _now(),
                "database_dialect": self.repository.db.dialect,
            },
        }

    def _task_cancelled(self, task_id: str) -> bool:
        """查询任务是否已被取消（供串行/并发路径共用，避免重复 get_task 样板）。"""
        current = self.repository.get_task(task_id)
        return bool(current and current.get("status") == TaskStatus.CANCELLED.value)

    def _execute_group_once(
        self,
        *,
        task_id: str,
        tool_id: str,
        contract: ToolContract,
        index: int,
        group: List[InputItem],
        params: Dict[str, Any],
        payload: Dict[str, Any],
        cancelled: threading.Event,
    ) -> Dict[str, Any]:
        """执行单个 group 的全流程：create_item → execute(GLM) → save_result → update_item。

        永不向上抛异常：失败时返回 ``status='failed'`` 的结果 dict，保证并发 ``as_completed``
        不会因一个 group 崩溃而中断其余 future。``cancelled`` 由调用方在发现取消时 set，
        本方法在启动前与拿到 GLM 信号量后双重自检。
        """
        # 启动前取消自检：已取消则不建 item、不调 GLM
        if cancelled.is_set():
            return {
                "index": index, "item_id": None, "record_id": None, "status": "skipped",
                "input_id": group[0].input_id if len(group) == 1 else None,
                "file_name": None, "source": {}, "error": "任务已取消，未启动", "result": {},
            }

        source = dict(group[0].source) if len(group) == 1 else {"input_count": len(group)}
        # Entity-relation recognition is a real downstream workflow.  Keep
        # the exact NER input on its task item so a selected batch record
        # can always be replayed independently (including uploaded files).
        if len(group) == 1 and tool_id in {"general-ner", "research-ner", "domain-ner"}:
            source.setdefault("text", group[0].text)

        item_id = self.repository.create_item(task_id, index, source)
        self.repository.update_item(item_id, "running")
        input_id = group[0].input_id if len(group) == 1 else None
        try:
            request = self._semantic_request(contract, group, params, payload)
            # 信号量只包最耗时的 GLM 调用；DB 操作不限流（快且独立 session 线程安全）。
            # 全局 _GLM_SEMAPHORE 钳制全进程在途 GLM 请求数，防多任务嵌套线程爆炸。
            with _GLM_SEMAPHORE:
                if cancelled.is_set():  # 拿到信号量后二次自检，避免取消后仍打 GLM
                    self.repository.update_item(item_id, "failed", "任务已取消")
                    return {
                        "index": index, "item_id": item_id, "record_id": None,
                        "status": "skipped", "input_id": input_id,
                        "file_name": source.get("file_name"), "source": source,
                        "error": "任务已取消", "result": {},
                    }
                semantic_result = self.semantic_service.execute(contract.backend_code, request)
            if not semantic_result.success:
                raise RuntimeError(semantic_result.error or "算法执行失败")
            record_id = _id("rec")
            result_payload = self._result_payload(payload, group)
            normalized = normalize_result(tool_id, semantic_result.data, result_payload)
            self._attach_result_identity(tool_id, normalized, task_id, record_id, payload)
            self._complete_vue_result(tool_id, normalized)
            self.repository.save_result(ResultRecord(
                id=record_id,
                task_id=task_id,
                task_item_id=item_id,
                tool_id=tool_id,
                backend_code=contract.backend_code,
                result=normalized,
            ))
            upstream_ids = self._upstream_ids(payload)
            if upstream_ids:
                self.repository.add_dependencies(record_id, upstream_ids, self._dependency_type(tool_id))
            self.repository.update_item(item_id, "succeeded")
            return {
                "index": index, "item_id": item_id, "record_id": record_id,
                "status": "succeeded", "input_id": input_id,
                "file_name": source.get("file_name"), "source": source, "result": normalized,
            }
        except Exception as exc:  # noqa: BLE001  异常隔离：失败不上抛，不影响其他 group
            error = str(exc)
            self.repository.update_item(item_id, "failed", error)
            return {
                "index": index, "item_id": item_id, "record_id": None, "status": "failed",
                "input_id": input_id, "file_name": source.get("file_name"), "source": source,
                "error": error, "result": {},
            }

    def _run_groups_concurrent(
        self,
        *,
        task_id: str,
        tool_id: str,
        contract: ToolContract,
        execution_groups: List[List[InputItem]],
        params: Dict[str, Any],
        payload: Dict[str, Any],
        results_out: List[Dict[str, Any]],
    ) -> Tuple[int, int]:
        """逐篇 group 线程池并发执行。

        - ``ThreadPoolExecutor`` 限单任务线程数；``_GLM_SEMAPHORE`` 限全进程在途 GLM 调用数。
        - ``as_completed`` 流式收集：每完成一篇上报一次进度（前端轮询看到的 progress 单调递增）。
        - ``progress_lock`` 只护内存计数与快照，``update_task_status`` 在锁外写库（避免持锁做 IO
          串行化 worker）；写到 DB 的是聚合快照三元组，不会回退。
        - ``bucket`` 按 index 收集，``as_completed`` 完成顺序无序，最后 ``sorted`` 还原输入顺序。
        - 取消：发现 CANCELLED 则 set event + cancel 未启动 future；已 running 的跑完（HTTP 无法
          安全中断，强杀泄漏连接）。
        """
        total = len(execution_groups)
        cancelled = threading.Event()
        progress_lock = threading.Lock()
        bucket: Dict[int, Dict[str, Any]] = {}
        success_count = 0
        failed_count = 0
        completed = 0
        workers = min(settings.GLM_MAX_CONCURRENCY, total)

        # 线程池（2026-09-08 回退自进程池）：fork 进程池继承 uvicorn socket fd，
        # 连续 4-5 次批量请求后子进程累积→后端崩溃（稳定性致命缺陷）。
        # GLM IO 是主耗时（释放 GIL），CPU 段已通过轮次合并从 ~3s/篇压到 ~1s/篇，
        # 线程并发的 GIL 开销可接受；sys.setswitchinterval(0.05) 已减轻切换。
        from concurrent.futures import ThreadPoolExecutor, as_completed
        _bucket: Dict[int, Dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="glm-group") as pool:
            _future_to_index = {
                pool.submit(
                    self._execute_group_once,
                    task_id=task_id, tool_id=tool_id, contract=contract,
                    index=index, group=group, params=params, payload=payload,
                    cancelled=cancelled,
                ): index
                for index, group in enumerate(execution_groups)
            }
            for future in as_completed(_future_to_index):
                index = _future_to_index[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "index": index, "item_id": None, "record_id": None, "status": "failed",
                        "input_id": None, "file_name": None, "source": {},
                        "error": "线程异常: %s" % exc, "result": {},
                    }
                with progress_lock:
                    _bucket[index] = result
                    if result["status"] == "succeeded":
                        success_count += 1
                    elif result["status"] == "failed":
                        failed_count += 1
                    completed += 1
                    snap_success, snap_failed, snap_done = success_count, failed_count, completed
                if self._task_cancelled(task_id):
                    cancelled.set()
                    for fut in _future_to_index:
                        fut.cancel()
        _results = [_bucket[i] for i in range(total)]
        # 按序收集进度（进程池 map 有序返回）
        success_count = sum(1 for r in _results if r["status"] == "succeeded")
        failed_count = sum(1 for r in _results if r["status"] == "failed")
        completed = len(_results)
        from domain.entity.analysis_task import TaskStatus as _TS
        self.repository.update_task_status(
            task_id,
            _TS.SUCCEEDED if failed_count == 0 else _TS.PARTIAL_FAILED,
            progress=total, success_count=success_count, failed_count=failed_count)
        results_out.extend(_results)
        return success_count, failed_count


        return success_count, failed_count

    @staticmethod
    def _attach_result_identity(
        tool_id: str,
        result: Dict[str, Any],
        task_id: str,
        record_id: str,
        payload: Dict[str, Any],
    ) -> None:
        if tool_id == "deep-cluster":
            result.setdefault("cluster_task_id", task_id)
        elif tool_id == "cluster-label":
            result.setdefault("source_cluster_task_id", payload.get("cluster_task_id"))
        elif tool_id == "structured-review":
            result.setdefault("review_id", record_id)

    @staticmethod
    def _result_payload(payload: Dict[str, Any], group: List[InputItem]) -> Dict[str, Any]:
        """Return the exact per-item context used to normalize a batch result.

        Without this step a title or project name from the batch-level request
        can leak into every row.  File names and structured batch metadata are
        intentionally copied only for the item currently being normalized.
        """
        value = dict(payload)
        # 批量模式 document_title 是逐篇列表:平铺进单篇结果会让 normalizer/projection
        # 把列表当单值标题写入(实测 MySQL 1241)。单篇真实题目以 source.title 为准。
        if isinstance(value.get("document_title"), list):
            value["document_title"] = None
        if not group:
            return value
        source = group[0].source if len(group) == 1 else {}
        if source.get("title") is not None:
            value["title"] = source.get("title")
            value["document_title"] = source.get("title")
        if source.get("project_name") is not None:
            value["project_name"] = source.get("project_name")
        if source.get("file_name"):
            value["file_name"] = source.get("file_name")
            value.setdefault("title", source.get("file_name"))
            value.setdefault("document_title", source.get("file_name"))
        if value.get("input_type") == "upstream_records":
            value["text"] = group[0].text
        elif group[0].text:
            # 文件输入时把本篇解析出的摘要回填到 result_payload.text，供 normalizer
            # 给 document.abstract 补值——前端弹窗按字符范围定位每个语步（move.text
            # 在 abstract 内 indexOf 算起止）。单篇 text 输入时与 payload.text 一致，
            # setdefault 不覆盖；批量文件 payload 无 text，这里补上本篇 abstract。
            value.setdefault("text", group[0].text)
        return value

    @staticmethod
    def _complete_vue_result(tool_id: str, result: Dict[str, Any]) -> None:
        """固定 Vue 结果字段；未知业务值仅返回空值，绝不使用演示数据补齐。"""
        list_fields = {
            "moves", "classifications", "candidates", "domain_labels", "levels",
            "cross_language_mapping", "keywords", "research_question_sentences",
            "research_question_phrases", "structured_research_questions", "citations",
            "citation_sentiment_results", "citation_intent_results", "definitions",
            "entities", "triples", "clusters", "labels", "tree", "sections",
            "evidence", "trend_analysis", "hotspots", "candidate_classifications",
            "multilevel_classification_results", "keywords_or_topic_phrases",
            "concept_definition_mappings", "standard_term_mappings", "ontology_mappings",
            "dependency_parse", "dependency_paths", "relation_triples", "context_fragments",
            "document_assignments", "semantic_projection", "evidence_index",
        }
        dict_fields = {
            "move_statistics", "project_metadata", "writeback", "primary_classification",
            "selected_domain", "distribution_report", "dictionary_usage", "statistics",
            "source_records", "quality_metrics", "generation_report",
            "cluster_induction_results", "structured_report", "trend_hotspot_distribution",
            "document", "summary", "classification_confidence", "data_distribution_report",
            "literature_distribution_analysis_report", "research_question_statistics",
            "citation_sentiment_statistics", "citation_intent_statistics",
            "statistical_analysis_report", "clustering_quality",
            "input_summary", "theme_trend_analysis", "parameters",
            "label_generation_process_report", "label_distinctiveness_optimization_result",
        }
        for field in get_vue_contract(tool_id).result_fields:
            if field in result:
                continue
            if field in list_fields:
                result[field] = []
            elif field in dict_fields:
                result[field] = {}
            else:
                result[field] = None

    def submit(
        self,
        tool_id: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        file_inputs: Optional[List[Dict[str, str]]] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建后台任务并立即返回任务编号；用于批量、文件和集合计算。"""
        task_id = _id("tsk")
        created = Event()
        future = _TASK_EXECUTOR.submit(
            self.execute,
            tool_id,
            payload,
            file_inputs=file_inputs,
            workspace_id=workspace_id,
            _task_id=task_id,
            _created_event=created,
        )
        if not created.wait(timeout=3):
            if future.done():
                return future.result()
            raise RuntimeError("后台任务创建超时")
        task = self.repository.get_task(task_id) or {}
        contract = get_contract(tool_id)
        return {
            "code": 0,
            "message": "accepted",
            "data": {
                "task_id": task_id,
                "tool_id": tool_id,
                "status": task.get("status", TaskStatus.QUEUED.value),
                "input_type": task.get("input_type"),
                "progress": task.get("progress", 0),
                "total": task.get("total", 0),
                "success_count": task.get("success_count", 0),
                "failed_count": task.get("failed_count", 0),
                "results": [],
                "summary": {},
                "available_exports": list(contract.export_formats),
            },
            "meta": {
                "request_id": _id("req"),
                "schema_version": "1.0",
                "model_version": settings.MODEL_VERSION,
                "created_at": _now(),
                "database_dialect": self.repository.db.dialect,
            },
        }

    @staticmethod
    def _adapt_vue_payload(contract: ToolContract, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add internal aliases without removing any public Vue field.

        ``request_payload`` therefore remains auditable against the UI, while
        the existing algorithm services can continue consuming ``text``,
        ``texts``, ``domain`` and the other established internal names.
        """
        adapted = dict(payload)
        tool_id = contract.tool_id
        public_field = PRIMARY_TEXT_FIELDS.get(tool_id)
        public_value = adapted.get(public_field) if public_field else None

        if not adapted.get("input_type"):
            if tool_id == "relation-extract":
                adapted["input_type"] = "upstream_records"
            elif tool_id == "structured-review" and isinstance(public_value, dict):
                adapted["input_type"] = "collection"
            elif isinstance(public_value, list):
                adapted["input_type"] = "texts"
            else:
                adapted["input_type"] = "text"

        input_type = str(adapted.get("input_type") or "text")
        is_many = input_type in {"texts", "files", "batch", "batch-text"}

        if public_field and public_value is not None and not isinstance(public_value, (bytes, bytearray)):
            if is_many and isinstance(public_value, list):
                adapted.setdefault("texts", public_value)
                adapted.setdefault("documents", public_value)
            elif isinstance(public_value, str):
                adapted.setdefault("text", public_value)
            elif isinstance(public_value, list) and len(public_value) == 1:
                # text 模式收到单元素列表(如 domain_scientific_literature_data:[{...}]):
                # 解包取该元素的文本,否则 input_type=text 时不走 texts 映射,文本丢失
                only = public_value[0] if isinstance(public_value[0], dict) else {"text": public_value[0]}
                single_text = ToolIntegrationService._document_text(only) if isinstance(public_value[0], dict) else str(public_value[0] or "")
                if single_text:
                    adapted.setdefault("text", single_text)

        if isinstance(adapted.get("document_title"), str) and adapted["document_title"].strip():
            adapted.setdefault("title", adapted["document_title"])
        if adapted.get("professional_domain") is not None:
            adapted.setdefault("domain", adapted.get("professional_domain"))
        if adapted.get("domain_label") is not None:
            adapted.setdefault("domain", adapted.get("domain_label"))

        if tool_id == "fund-move" and adapted.get("project_name"):
            adapted.setdefault("title", adapted.get("project_name"))

        if tool_id.startswith("citation-"):
            contexts = adapted.get("citation_sentence_and_context")
            citation_metadata = adapted.get("citation_metadata")
            full_text = adapted.get("scientific_document_full_text")
            if isinstance(contexts, list) and contexts:
                citation_documents = []
                full_texts = full_text if isinstance(full_text, list) else []
                for index, context in enumerate(contexts):
                    row = context if isinstance(context, dict) else {"citation_sentence": str(context or "")}
                    paired_full_text = ""
                    if index < len(full_texts):
                        value = full_texts[index]
                        paired_full_text = ToolIntegrationService._document_text(value) if isinstance(value, dict) else str(value or "")
                    elif isinstance(full_text, str):
                        paired_full_text = full_text
                    context_text = "\n".join(str(row.get(key) or "") for key in (
                        "previous_context", "citation_sentence", "next_context",
                    ) if row.get(key))
                    citation_documents.append({
                        "id": row.get("id") or f"CIT{index + 1:03d}",
                        "text": paired_full_text or context_text,
                        "citation_context": row,
                        "citation_metadata": (
                            citation_metadata[index]
                            if isinstance(citation_metadata, list) and index < len(citation_metadata)
                            else citation_metadata
                        ),
                    })
                if input_type == "texts":
                    adapted["texts"] = citation_documents
                    adapted["documents"] = citation_documents
                elif citation_documents:
                    adapted["text"] = citation_documents[0]["text"]
            adapted.setdefault("citation_contexts", contexts or [])

        if tool_id == "relation-extract" and adapted.get("upstream_ner_record_id"):
            adapted["input_type"] = "upstream_records"
            adapted.setdefault("upstream_entity_record_id", adapted["upstream_ner_record_id"])

        if tool_id == "deep-cluster":
            documents = adapted.get("scientific_document_texts")
            metadata = adapted.get("document_metadata")
            if isinstance(documents, list):
                metadata_by_id = {
                    str(item.get("document_id") or item.get("id")): item
                    for item in metadata or [] if isinstance(item, dict)
                } if isinstance(metadata, list) else {}
                merged = []
                for index, value in enumerate(documents):
                    row = dict(value) if isinstance(value, dict) else {"text": str(value or "")}
                    document_id = str(row.get("document_id") or row.get("id") or f"DOC{index + 1:03d}")
                    merged.append({**metadata_by_id.get(document_id, {}), **row, "document_id": document_id})
                adapted["documents"] = merged
                adapted["texts"] = merged

        if tool_id == "cluster-label":
            phrase_sets = adapted.get("cluster_phrase_sets")
            if isinstance(phrase_sets, list):
                adapted["documents"] = [
                    {
                        "id": str(item.get("cluster_id") or f"CLUSTER_{index + 1:03d}"),
                        "text": json.dumps(item, ensure_ascii=False),
                    }
                    for index, item in enumerate(phrase_sets) if isinstance(item, dict)
                ]
                adapted["texts"] = adapted["documents"]
            adapted.setdefault("label_length_max", adapted.get("label_length_limit"))
            adapted.setdefault("output_language", adapted.get("language_type"))

        if tool_id == "structured-review" and isinstance(adapted.get("document_set"), dict):
            document_set = adapted["document_set"]
            collection_id = document_set.get("collection_id") or document_set.get("resource_id")
            if collection_id:
                adapted["collection_id"] = collection_id
                adapted["input_type"] = "collection"

        dictionary = adapted.get("domain_terminology_dictionary")
        if tool_id == "zh-keyword" and isinstance(dictionary, dict):
            if dictionary.get("resource_id"):
                adapted.setdefault("dictionary_id", dictionary["resource_id"])
            if dictionary.get("terms") or dictionary.get("file"):
                # 词典文件接线（2026-09-05）：手填术语为空时解析上传文件
                # （规则 4 格式 + LLM 兜底），文件不再静默无效
                if not dictionary.get("terms") and (
                        dictionary.get("text_content") or dictionary.get("storage_uri")):
                    parsed = self._dictionary_terms_from_upload(dictionary)
                    if parsed:
                        dictionary = {**dictionary, "terms": parsed}
                adapted.setdefault("custom_dictionary", dictionary)
        return adapted

    def _inputs(self, contract: ToolContract, payload: Dict[str, Any], files: List[Dict[str, str]]) -> List[InputItem]:
        if files:
            items: List[InputItem] = []
            metadata = payload.get("document_metadata")
            for index, value in enumerate(files):
                path = value.get("path")
                text = path or value.get("text", "")
                if not text:
                    continue
                item_metadata = metadata[index] if isinstance(metadata, list) and index < len(metadata) and isinstance(metadata[index], dict) else {}
                items.append(InputItem(f"file{index + 1}", text, {
                    "file_name": value.get("file_name"), "media_type": value.get("media_type"),
                    "is_path": bool(path),
                    # 文件解析层回传的真实标题，供 _result_payload 取作题名（无标题时
                    # 为 None，由其后的 file_name 兜底）。放在 item_metadata 前，
                    # 让用户显式提供的 document_metadata.title 优先于文件提取值。
                    "title": value.get("title"),
                    **item_metadata,
                }))
            return items

        if payload.get("input_type") == "upstream_records":
            text = self._text_from_upstream(payload)
            return [InputItem("upstream", text, {"source_mode": "structured"})] if text else []

        if payload.get("input_type") == "collection" or payload.get("collection_id"):
            _cid = str(payload.get("collection_id") or "")
            # 复合 id "{task_id}:{cluster_id}" = 聚类标签生成任务的簇文献集；
            # 普通纯 collection_id 仍走数据库文献集表
            documents = self._cluster_set_documents(_cid) if ":" in _cid else self._collection_documents(_cid)
            return [InputItem(str(item.get("id", index)), self._document_text(item), item) for index, item in enumerate(documents)]

        if contract.tool_id == "cluster-label" and payload.get("cluster_task_id"):
            upstream_inputs = self._inputs_from_task(str(payload["cluster_task_id"]))
            if upstream_inputs:
                return upstream_inputs
            upstream_result = self._result_from_task(str(payload["cluster_task_id"]))
            return [InputItem("cluster-result", json.dumps(upstream_result, ensure_ascii=False), {"source_task_id": payload["cluster_task_id"]})] if upstream_result else []

        texts = payload.get("document_set") or payload.get("documents") or payload.get("texts")
        if isinstance(texts, list):
            items = []
            # 批量题目逐条映射:document_title 为列表时按下标对应各篇文献
            batch_titles = payload.get("document_title") if isinstance(payload.get("document_title"), list) else None
            for index, value in enumerate(texts):
                if isinstance(value, dict):
                    text = self._document_text(value)
                    input_id = str(value.get("document_id") or value.get("id") or value.get("input_id") or f"text{index + 1}")
                    source = {**value, "input_id": input_id, "title": value.get("title")}
                else:
                    text = str(value or "").strip()
                    input_id = f"text{index + 1}"
                    source = {"input_id": input_id}
                if batch_titles and index < len(batch_titles) and str(batch_titles[index] or "").strip():
                    source["title"] = str(batch_titles[index])
                if text:
                    items.append(InputItem(input_id, text, source))
            return items

        text = self._single_text(contract, payload)
        # 单文本：把用户填写的题目（document_title/title）带进 source，供
        # _result_payload 回填 document.title，弹窗题名列显示论文题目。
        source: Dict[str, Any] = {"input_id": "text1"}
        title = payload.get("document_title") or payload.get("title")
        if title:
            source["title"] = title
        return [InputItem("text1", text, source)] if text else []

    def _semantic_request(
        self,
        contract: ToolContract,
        group: List[InputItem],
        params: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> SemanticRequest:
        if contract.collection_tool:
            if contract.tool_id == "structured-review":
                texts = []
                for item in group:
                    value = item.text
                    if value.lstrip().startswith("{"):
                        try:
                            decoded = json.loads(value)
                        except (TypeError, ValueError):
                            decoded = None
                        if isinstance(decoded, dict):
                            decoded.setdefault("document_id", decoded.get("id") or item.input_id)
                            decoded.setdefault("text", decoded.get("content") or decoded.get("full_text") or "")
                            if not decoded.get("title"):
                                decoded["title"] = item.source.get("title") or item.source.get("file_name") or ""
                            texts.append(json.dumps(decoded, ensure_ascii=False))
                            continue
                    texts.append(json.dumps({
                        "document_id": item.source.get("document_id") or item.source.get("id") or item.input_id,
                        "title": item.source.get("title") or item.source.get("file_name") or "",
                        "authors": item.source.get("authors") or [],
                        "institutions": item.source.get("institutions") or [],
                        "publication_date": item.source.get("publication_date") or item.source.get("published_at"),
                        "source": item.source.get("source") or "",
                        "keywords": item.source.get("keywords") or [],
                        "text": value,
                    }, ensure_ascii=False))
            elif contract.tool_id == "deep-cluster":
                texts = []
                for item in group:
                    if item.source.get("is_path"):
                        texts.append(json.dumps({
                            "document_id": item.source.get("document_id") or item.input_id,
                            "file_path": item.text,
                            "title": item.source.get("title") or item.source.get("file_name") or "",
                            "publication_date": item.source.get("publication_date"),
                            "authors": item.source.get("authors") or [],
                            "source": item.source.get("source") or "",
                            "keywords": item.source.get("keywords") or [],
                        }, ensure_ascii=False))
                    else:
                        texts.append(self._backend_text(contract, item.text, payload))
            else:
                texts = [self._backend_text(contract, item.text, payload) for item in group]
            effective_params = dict(params)
            if contract.tool_id == "cluster-label":
                # 有 cluster_task_id 时始终从上游任务重建完整 phrase_sets
                # （含 linked_document_ids/evidence_titles/evidence_terms_context），
                # 前端简化版 cluster_phrase_sets 只作无任务ID时的直传兜底
                if payload.get("cluster_task_id"):
                    upstream = self._result_from_task(str(payload["cluster_task_id"]))
                    phrase_sets = self._cluster_phrase_sets(upstream)
                else:
                    phrase_sets = payload.get("cluster_phrase_sets")
                if phrase_sets:
                    # The production label generator consumes phrase sets from
                    # params; request.texts exists only for the shared task and
                    # persistence pipeline.  Do not drop the public primary
                    # field merely because it is excluded from generic params.
                    effective_params["cluster_phrase_sets"] = phrase_sets
            return SemanticRequest(texts=texts, params=effective_params, meta={"source": payload.get("input_type", "texts")})

        _item = group[0]
        _text = _item.text
        source_pdf_path = None  # 原始PDF路径：light取文0结果时回退mineru重抽用（双栏sort拆句/layout漏段）
        if _item.source.get("is_path"):
            # 路径透传(PATH_PASSTHROUGH_TOOLS)：延迟到此处解析该篇 PDF，让
            # mineru(GPU, PageBudgetPool 控制) 与它篇 LLM 处理(GLM) 并行流水线。
            from pathlib import Path
            from infrastructure.document_parser.upload_reader import extract_bytes
            from infrastructure.document_parser.mineru_api_client import _count_pages
            from infrastructure.document_parser.concurrency_pool import get_page_budget_pool
            _p = Path(_text)
            _content = _p.read_bytes()
            _name = _item.source.get("file_name") or _p.name
            try:
                if settings.should_use_light(contract.tool_id):
                    # PyMuPDF 毫秒级直抽，不耗 GPU，无需页数预算约束
                    source_pdf_path = str(_p) if _name.lower().endswith(".pdf") else None
                    _text = extract_bytes(_content, _name, light=True) or ""
                else:
                    _pages = _count_pages(_content) if _name.lower().endswith(".pdf") else 1
                    _pool = get_page_budget_pool()
                    _pool.acquire(_pages)
                    try:
                        _text = extract_bytes(_content, _name, light=False) or ""
                    finally:
                        _pool.release(_pages)
            except Exception as exc:
                if contract.tool_id.startswith("citation-"):
                    # 引用工具文件解析失败（损坏 PDF/mineru 不可用等）转业务可读提示，
                    # 由 _execute_group_once 兜底为失败项，全败时 _run_execute 升级为
                    # 42201 业务响应（不暴露底层报错，不报参数缺失类 422）
                    raise ValueError(
                        f"文件解析失败，无法执行引用识别：{exc}。请上传含文本层的 PDF/DOCX/TXT 文件（扫描版请先转为文字版）。"
                    ) from exc
                raise
        text = self._backend_text(contract, _text, payload)
        effective_params = dict(params)
        if source_pdf_path:
            effective_params["_source_pdf_path"] = source_pdf_path
        if contract.tool_id.startswith("citation-"):
            context = group[0].source.get("citation_context")
            metadata = group[0].source.get("citation_metadata")
            if context:
                effective_params["citation_sentence_and_context"] = [context]
            elif str(payload.get("input_type") or "") in {"file", "files"} and not effective_params.get("citation_sentence_and_context"):
                # 文件模式内置 PDF 完整解析链路：上传 PDF（路径透传延迟解析或直传文本）
                # 已得全文 → 定位引用标记 → 按文献编号拆分引用句（含局部子片段），
                # 自动填充 citation_sentence_and_context 后再执行识别；未发现引用标记时
                # 不填充，由引擎走全文抽取兜底（无引用返回空结果而非参数错误）。
                document_text = str(_text or "").strip()
                if not document_text:
                    raise ValueError(
                        "文件解析失败，无法执行引用识别：未能从上传文件提取文本。"
                        "请上传含文本层的 PDF/DOCX/TXT 文件（扫描版请先转为文字版）。"
                    )
                contexts = _extract_citation_contexts(document_text)
                if contexts:
                    effective_params["citation_sentence_and_context"] = contexts
            if metadata:
                effective_params["citation_metadata"] = [metadata] if isinstance(metadata, dict) else metadata
        return SemanticRequest(text=text, params=effective_params, meta=self._meta(payload))

    @staticmethod
    def _backend_text(contract: ToolContract, text: str, payload: Dict[str, Any]) -> str:
        if contract.tool_id in {"zh-classify", "en-classify", "domain-classify"}:
            if text.lstrip().startswith("{"):
                return text
            # 批量模式 document_title 为逐篇列表,不能当单字符串拼 JSON(list.strip 崩溃);
            # 逐篇题目由 _inputs 按 document_title[index] 映射到各条的 source.title
            _title = payload.get("title")
            _abstract = payload.get("abstract")
            _keywords = payload.get("keywords")
            _title = _title if isinstance(_title, str) else ""
            _abstract = _abstract if isinstance(_abstract, str) else ""
            _keywords = _keywords if isinstance(_keywords, list) else []
            if not (_title or _abstract or _keywords):
                return text
            return json.dumps({
                "title": _title,
                "abstract": _abstract or text,
                "keywords": _keywords,
            }, ensure_ascii=False)
        if not contract.collection_tool and text.lstrip().startswith("{"):
            try:
                document = json.loads(text)
            except (TypeError, ValueError):
                document = None
            if isinstance(document, dict):
                return str(
                    document.get("text") or document.get("content") or document.get("abstract")
                    or document.get("abstract_text") or text
                ).strip()
        return text

    @staticmethod
    def _single_text(contract: ToolContract, payload: Dict[str, Any]) -> str:
        if contract.tool_id in {"zh-classify", "en-classify", "domain-classify"}:
            plain_text = str(payload.get("text") or "").strip()
            if plain_text:
                return plain_text
            if not (payload.get("title") or payload.get("abstract")):
                return ""
            return json.dumps({
                "title": payload.get("title", ""),
                "abstract": payload.get("abstract", ""),
                "keywords": payload.get("keywords") or [],
            }, ensure_ascii=False)
        return str(payload.get("text") or payload.get("abstract") or payload.get("content") or "").strip()

    @staticmethod
    def _document_text(document: Dict[str, Any]) -> str:
        raw_metadata = document.get("metadata_json") or {}
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except (TypeError, ValueError):
                metadata = {}
        elif isinstance(raw_metadata, dict):
            metadata = raw_metadata
        else:
            metadata = {}

        content = (
            document.get("content")
            or document.get("text")
            or document.get("content_text")
            or document.get("abstract")
            or document.get("abstract_text")
            or ""
        )
        publication_date = (
            document.get("publication_date")
            or document.get("published_at")
            or metadata.get("publication_date")
            or metadata.get("published_at")
            or metadata.get("publication_year")
            or metadata.get("year")
        )
        if any(document.get(field) is not None for field in (
            "document_id", "id", "input_id", "title", "keywords", "publication_date", "published_at", "metadata_json",
        )):
            return json.dumps({
                "document_id": document.get("document_id") or document.get("id") or document.get("input_id"),
                "title": document.get("title") or metadata.get("title") or "",
                "abstract": document.get("abstract") or document.get("abstract_text") or metadata.get("abstract") or "",
                "text": document.get("text") or document.get("content") or document.get("content_text") or "",
                "keywords": document.get("keywords") or metadata.get("keywords") or [],
                "authors": document.get("authors") or metadata.get("authors") or [],
                "institutions": document.get("institutions") or metadata.get("institutions") or [],
                "source": document.get("source") or metadata.get("source") or metadata.get("venue") or "",
                "doi": document.get("doi") or metadata.get("doi") or "",
                "published_at": document.get("published_at") or metadata.get("published_at"),
                "publication_date": publication_date,
                "full_text": document.get("full_text") or document.get("content_text") or metadata.get("full_text") or "",
            }, ensure_ascii=False)
        return str(content).strip()

    def _inspect_user_resource_file(self, field: str, resource: Dict[str, Any]) -> None:
        """用户指定资源统一预检（公共归一化层，全部工具共用）。

        - 内置(bundled)资源跳过（量大且为已知标准结构，也避免重复读 11.7 万行 gold）；
        - 仅处理 .json 文件：CSV/JSONL/TXT 不在归一化改造范围；
        - JSON 损坏 / 归一化后有效条目为 0 → ResourceParseError(ValueError)，
          由 execute 的既有 ValueError 出口返回 42201 业务信封（前端直接展示）；
        - 成功则按路径注册归一化行，业务消费端经 normalized_rows_for 取同一份结构。
        """
        if str(resource.get("source_type") or "") == "bundled":
            return
        from infrastructure.resources.normalize import (
            ROW_FIELD_CONFIG, ResourceParseError, inspect_user_resource, resource_path,
        )
        path = resource_path(str(resource.get("storage_uri") or ""), settings.PROJECT_ROOT)
        if path is None or path.suffix.lower() != ".json":
            return
        try:
            inspect_user_resource(path, field=field)
        except ResourceParseError:
            # LLM 容错层（2026-09-05 用户定调，全功能点兜底）：规则归一失败
            # （JSON 损坏/0 有效条目/字段不合规）时，用 GLM 把任意结构重构成该
            # 字段的标准 JSON 后复检；重构失败维持原报错（42201 业务信封）。
            if not self._llm_adapt_resource_file(field, path):
                raise
            inspect_user_resource(path, field=field)

    def _llm_adapt_resource_file(self, field: str, path) -> bool:
        """LLM 结构化适配：任意格式 → 字段标准结构。成功重写原文件并返回 True。"""
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")[:20000]
        except OSError:
            return False
        cfg = ROW_FIELD_CONFIG.get(field) or {}
        label = cfg.get("label") or field
        expect = cfg.get("expect") or "JSON 数组，每条为符合该资源字段含义的对象"
        sysp = (
            "你是数据格式转换专家。用户上传的 JSON 不符合目标字段的标准结构，"
            f"请把它完整重构为标准结构。\n目标字段：{label}\n期望结构：{expect}\n"
            "要求：保留全部原始信息不得丢弃条目；字段名用英文标准 key；值保持原文语言；"
            "中文 key（如 标准词/变体/题名/摘要）必须映射到对应英文标准 key。"
            "只输出 JSON 数组本身，不要任何解释或代码块标记。"
        )
        try:
            out = self.semantic_service._glm.chat_json(
                sysp, "用户上传内容：\n" + raw, timeout=90.0, temperature=0.0)
        except Exception:  # noqa: BLE001 - LLM 不可用/失败 → 维持规则层报错
            logger.warning("资源 LLM 容错重构调用失败: %s", path.name, exc_info=True)
            return False
        rows = out.get("data", out) if isinstance(out, dict) else out
        if not isinstance(rows, list) or not rows:
            return False
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        logger.info("资源已由 LLM 容错层重构: %s (字段=%s, %d 条)", path.name, field, len(rows))
        return True

    def _dictionary_terms_from_upload(self, dictionary: Dict[str, Any]) -> list:
        """用户词典文件 → 术语列表（规则解析 4 格式；复杂结构 LLM 兜底抽取）。

        文件内容来自 _store_uploaded_resource 并入的 text_content（文本类）或
        storage_uri 落盘文件（xlsx 等二进制）。规则解析产出 <2 条或结构复杂
        （嵌套对象/中英混合 key）时，用 GLM 从内容中抽取术语列表兜底。
        """
        import csv as _csv
        import io as _io

        def _llm_extract(content: str) -> list:
            try:
                out = self.semantic_service._glm.chat_json(
                    "你是术语抽取器。从用户上传的词典文件内容中抽取全部术语，"
                    "输出 JSON：{\"data\": [\"术语1\", \"术语2\", ...]}。"
                    "要求：保留原文语言不翻译；去重；跳过表头/编号/权重等非术语字段。",
                    "文件内容：\n" + content[:20000], timeout=60.0, temperature=0.0)
                rows = out.get("data", out) if isinstance(out, dict) else out
                return [str(t).strip() for t in rows if str(t).strip()] if isinstance(rows, list) else []
            except Exception:  # noqa: BLE001
                return []

        content = str(dictionary.get("text_content") or "")
        fname = str(dictionary.get("file_name") or "").lower()
        terms: list = []
        if fname.endswith(".json") and content:
            try:
                data = json.loads(content)
                rows = data if isinstance(data, list) else (
                    next((v for v in data.values() if isinstance(v, list)), []) if isinstance(data, dict) else [])
                for r in rows:
                    if isinstance(r, str) and r.strip():
                        terms.append(r.strip())
                    elif isinstance(r, dict):
                        t = r.get("term") or r.get("术语") or r.get("word") or r.get("name")
                        if t:
                            terms.append(str(t).strip())
            except (ValueError, TypeError):
                pass
        elif fname.endswith(".txt") and content:
            terms = [line.strip() for line in content.splitlines() if line.strip()]
        elif fname.endswith(".csv") and content:
            try:
                for row in _csv.reader(_io.StringIO(content)):
                    if row and row[0].strip() and not str(row[0]).strip().isdigit():
                        terms.append(row[0].strip())
            except _csv.Error:
                pass
        elif fname.endswith(".xlsx"):
            uri = str(dictionary.get("storage_uri") or "")
            if uri:
                from pathlib import Path as _P
                xp = _P(uri.removeprefix("project://")) if uri.startswith("project://") else _P(uri)
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(xp, read_only=True, data_only=True)
                    ws = wb.worksheets[0]
                    for row in ws.iter_rows(values_only=True):
                        if row and row[0] is not None and str(row[0]).strip():
                            terms.append(str(row[0]).strip())
                except Exception:  # noqa: BLE001
                    pass
        # 去重；不足 2 条（解析失败/结构复杂）→ LLM 兜底
        terms = list(dict.fromkeys(terms))
        if len(terms) < 2 and content:
            llm_terms = _llm_extract(content)
            if len(llm_terms) >= len(terms):
                terms = list(dict.fromkeys(llm_terms))
        return terms

    def _parameters(self, contract: ToolContract, payload: Dict[str, Any]) -> Dict[str, Any]:
        excluded = {
            "input_type", "text", "texts", "title", "abstract", "keywords", "documents", "file", "files",
            "async", "rerun_from_task_id", "upstream_entity_record_id", "upstream_dependency_record_id",
            "cluster_task_id", "collection_id", "source_mode", "document_set",
        }
        excluded.update(PRIMARY_TEXT_FIELDS.values())
        excluded.update({"document_title", "scientific_document_full_text"})
        params = {key: value for key, value in payload.items() if key not in excluded and value is not None}
        resolved_resources: Dict[str, Any] = {}
        # 深度聚类的训练样本/人工标注类目是可选锚点资源（v3 语步级锚点引导）：
        # 用户上传时内部提取语步做类目档案引导分组；默认（内置/不选）纯 v3 自由分组
        resource_fields = set(SEMANTIC_RESOURCE_FIELDS)
        if contract.tool_id == "deep-cluster":
            resource_fields.update({"training_samples", "manually_labeled_category_data"})
        for field in resource_fields:
            descriptor = payload.get(field)
            if not isinstance(descriptor, dict) or not descriptor.get("resource_id"):
                continue
            resource = self.resource_repository.get_semantic_resource(str(descriptor["resource_id"]))
            if resource:
                # 用户指定资源统一预检：JSON 解码 + 结构归一化 + 零有效条目兜底。
                # 失败抛 ResourceParseError(ValueError) → execute 统一 42201 业务信封，
                # 杜绝"上传成功但解析 0 条、静默回退内置"（内置 bundled 资源跳过）。
                self._inspect_user_resource_file(field, resource)
                resolved_resources[field] = resource
        if resolved_resources:
            params["resolved_resources"] = resolved_resources
        # zh-keyword 前端发送 domain_terminology_dictionary（Vue 公共字段名），后端
        # 历史上只认 dictionary_id / custom_dictionary——字段名不匹配导致用户词典
        # 完全不生效（custom_dictionary_hit 恒为 false）。此处归一成既有两条路径。
        if contract.tool_id in {"zh-keyword", "en-keyword"}:
            dtd = payload.get("domain_terminology_dictionary")
            if isinstance(dtd, dict):
                dtd_mode = str(dtd.get("use_mode") or dtd.get("source") or "").strip()
                if dtd_mode == "saved" and dtd.get("resource_id"):
                    payload.setdefault("dictionary_id", dtd.get("resource_id"))
                elif dtd_mode == "custom":
                    custom_terms = dtd.get("terms") or []
                    # 词典文件接线（2026-09-05）：手填术语为空时解析上传文件
                    # （规则 4 格式 + LLM 兜底抽取），文件不再静默无效
                    if not custom_terms and (dtd.get("text_content") or dtd.get("storage_uri")):
                        parsed = self._dictionary_terms_from_upload(dtd)
                        if parsed:
                            custom_terms = parsed
                    payload.setdefault("custom_dictionary", {
                        "dictionary_name": dtd.get("dictionary_name") or dtd.get("name"),
                        "weight_boost": dtd.get("weight_boost", 0.08),
                        "terms": custom_terms,
                        # 上传的词典文件：_store_uploaded_resource 的 descriptor 顶层带
                        # text_content（解码后的文件内容），交由下方 text_content 解析
                        "text_content": str(dtd.get("text_content") or ""),
                    })
        if contract.tool_id in {"zh-keyword", "en-keyword"} and payload.get("dictionary_id"):
            selected = self.resource_repository.get_dictionary(
                str(payload["dictionary_id"]),
                int(payload["dictionary_version"]) if payload.get("dictionary_version") else None,
            )
            if not selected:
                raise ValueError("用户词典或指定版本不存在")
            expected_language = "en" if contract.tool_id == "en-keyword" else "zh"
            if str(selected.get("language") or "").lower() != expected_language:
                raise ValueError(f"当前关键词工具只能使用 {expected_language} 词典")
            params["custom_dictionary"] = {
                "id": selected["id"],
                "version_id": selected["version_id"],
                "version": selected["version"],
                "name": selected["name"],
                "weight_boost": selected["weight_boost"],
                "terms": selected["terms"],
            }
        elif contract.tool_id == "zh-keyword" and isinstance(payload.get("custom_dictionary"), dict):
            custom = dict(payload["custom_dictionary"])
            terms = custom.get("terms") or []
            if not terms and custom.get("text_content"):
                raw_text = str(custom["text_content"])
                try:
                    decoded = json.loads(raw_text)
                    if isinstance(decoded, list):
                        terms = decoded
                    elif isinstance(decoded, dict):
                        # 领域术语资源嵌套格式：{domain_term_resource:{领域:{term_list,base_weight}}, general_sci_term}
                        terms = _extract_domain_term_entries(decoded) or decoded.get("terms") or []
                except json.JSONDecodeError:
                    terms = [item.strip() for item in re.split(r"[\r\n,，;；]+", raw_text) if item.strip()]
            if terms:
                created = self.resource_repository.create_dictionary(
                    settings.DEFAULT_WORKSPACE_ID,
                    {
                        "name": custom.get("dictionary_name") or custom.get("name") or f"用户自定义领域词典_{datetime.now().strftime('%Y%m%d_%H%M')}",
                        "language": "zh",
                        "weight_boost": custom.get("weight_boost", 0.08),
                        "terms": terms,
                    },
                )
                selected = self.resource_repository.get_dictionary(created["id"], created["version"])
                params["custom_dictionary"] = {
                    "id": selected["id"], "version_id": selected["version_id"],
                    "version": selected["version"], "name": selected["name"],
                    "weight_boost": selected["weight_boost"], "terms": selected["terms"],
                }
        if contract.tool_id == "domain-classify":
            domain = str(payload.get("domain") or "")
            params["domain_code"] = DOMAIN_CODE_MAP.get(domain, domain)
        if contract.tool_id in {"en-abstract-move", "en-keyword", "en-classify"}:
            params.setdefault("lang", "en")
        if contract.tool_id == "deep-cluster":
            params["cluster_axis"] = "technical" if payload.get("cluster_dimension", "technology") == "technology" else "application"
        if contract.tool_id == "cluster-label":
            params["cluster_axis"] = "technical" if payload.get("cluster_dimension", "technology") == "technology" else "application"
        return params

    @staticmethod
    def _meta(payload: Dict[str, Any]) -> Dict[str, str]:
        return {"domain": str(payload.get("domain") or payload.get("discipline") or "auto")}

    def _derive_citation_inputs(self, payload: Dict[str, Any]) -> None:
        """引用工具文本模式自动派生：文献文本 + 参考文献条目 → 其余全部参数。

        用户只需提供 scientific_document_full_text（文献文本）与 reference_entries
        （参考文献条目原文，粘贴或上传）。派生：
        ① 引用句及上下文（正则定位 [n] 标记句 + 前后句）
        ② 被引文献元数据（GLM 解析条目 → 作者/题名/年份/来源/DOI）
        ③ 标记号 ↔ 条目序号匹配（citation_id = cite-<n>）
        已手动提供 citation_sentence_and_context 时不覆盖（高级路径保留）。
        """
        if payload.get("citation_sentence_and_context"):
            return
        document_text = str(
            payload.get("scientific_document_full_text") or payload.get("text") or ""
        ).strip()
        if not document_text:
            return  # 无文献文本：回落手动输入校验
        contexts = _extract_citation_contexts(document_text)
        if not contexts:
            raise ValueError(
                "未能从文献文本中定位引用句（未发现 [n] 形式的引用标记）；"
                "请确认文本包含引用标记，或手动提供引用句及上下文"
            )
        # 元数据取用优先级：用户已补充的 citation_metadata > 参考文献条目解析 > 报错
        metadata = payload.get("citation_metadata")
        if not (isinstance(metadata, list) and metadata):
            entries_raw = payload.get("reference_entries")
            if isinstance(entries_raw, dict):  # 文件上传场景 {file_name, text_content}
                entries_raw = entries_raw.get("text_content") or entries_raw.get("content") or ""
            entries_raw = str(entries_raw or "").strip()
            if not entries_raw:
                raise ValueError(
                    "请补充被引文献元数据（粘贴/上传参考文献条目），或提供 reference_entries"
                )
            metadata = _parse_reference_entries(entries_raw)
            if not metadata:
                raise ValueError("参考文献条目解析失败，请检查条目格式")
            payload["citation_metadata"] = metadata
        # 引用句按标记号匹配元数据；未匹配到条目的引用句仍保留（元数据留空由引擎降级）
        ref_indexes = {m.get("reference_index") for m in payload.get("citation_metadata") or []
                       if isinstance(m, dict) and m.get("reference_index")}
        for ctx in contexts:
            nums = ctx.pop("_marker_nums", None) or []
            ctx["citation_id"] = f"cite-{nums[0]}" if nums else "cite-0"
            ctx["matched_reference"] = nums[0] in ref_indexes if ref_indexes else None
        payload["citation_sentence_and_context"] = contexts

    def _payload_error(self, contract: ToolContract, payload: Dict[str, Any]) -> Optional[str]:
        # 在线测试中的手工文本统一限制为 8000 个清洗后字符。
        # 文件和数据库集合不走这里，仍可保留全文并由各算法分段处理。
        candidates: List[tuple[str, Any]] = []
        for field in ("text", "abstract", "content"):
            if payload.get(field) is not None:
                candidates.append((field, payload.get(field)))
        for collection_name in ("document_set", "documents", "texts"):
            documents = payload.get(collection_name)
            if not isinstance(documents, list):
                continue
            for index, document in enumerate(documents):
                if isinstance(document, dict):
                    identifier = str(document.get("id") or document.get("input_id") or f"第{index + 1}条文本")
                    for field in ("text", "abstract", "content"):
                        if document.get(field) is not None:
                            candidates.append((f"{identifier} 的 {field}", document.get(field)))
                elif document is not None:
                    candidates.append((f"第{index + 1}条文本", document))
        for label, value in candidates:
            cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
            if len(cleaned) > 8000:
                return f"{label} 清洗后不能超过8000个字符"
        for field in ("minimum_confidence", "difference_threshold", "distinctiveness_threshold"):
            if payload.get(field) is not None:
                try:
                    value = float(payload[field])
                except (TypeError, ValueError):
                    return f"{field} 必须是数值"
                if not 0 <= value <= 1:
                    return f"{field} 必须在 0—1 之间"
        custom_dictionary = payload.get("custom_dictionary")
        if isinstance(custom_dictionary, dict):
            try:
                weight_boost = float(custom_dictionary.get("weight_boost", 0))
            except (TypeError, ValueError):
                return "用户词典 weight_boost 必须是数值"
            if not 0 <= weight_boost <= 0.5:
                return "用户词典 weight_boost 必须在 0—0.5 之间"
        try:
            minimum_keywords = int(payload.get("min_keywords", 5) or 5)
            maximum_keywords = int(payload.get("max_keywords", 8) or 8)
        except (TypeError, ValueError):
            return "min_keywords 和 max_keywords 必须是整数"
        if minimum_keywords < 1 or maximum_keywords < minimum_keywords or maximum_keywords > 50:
            return "关键词数量必须满足 1 ≤ min_keywords ≤ max_keywords ≤ 50"
        if contract.tool_id == "cluster-label":
            if not payload.get("cluster_phrase_sets") and not payload.get("cluster_task_id"):
                return "聚类标签生成必须提供深度聚类输出的类簇短语集合"
            try:
                minimum_length = int(payload.get("label_length_min", 1) or 1)
                maximum_length = int(payload.get("label_length_max", 12) or 12)
            except (TypeError, ValueError):
                return "label_length_min 和 label_length_max 必须是整数"
            if minimum_length < 1 or maximum_length < minimum_length or maximum_length > 100:
                return "标签长度必须满足 1 ≤ label_length_min ≤ label_length_max ≤ 100"
        if contract.tool_id == "domain-classify" and not str(payload.get("domain") or "").strip():
            return "domain 为必填项"
        for field in REQUIRED_RESOURCE_FIELDS.get(contract.tool_id, ()):
            descriptor = payload.get(field)
            # 内置模式（2026-09-06 定调）：不提交该资源字段 = 使用系统预置资源，
            # 消费端均有内置回退；仅当显式携带 descriptor 时才校验来源与内容
            if descriptor is None:
                continue
            if not isinstance(descriptor, dict):
                return f"{field} 资源格式不正确"
            source = str(descriptor.get("source") or "database")
            if source == "database":
                resource_id = str(descriptor.get("resource_id") or "")
                if not resource_id:
                    return f"{field} 未选择数据库资源"
                resource = self.resource_repository.get_semantic_resource(resource_id)
                if not resource or resource.get("resource_key") != field or resource.get("status") != "current":
                    return f"{field} 所选资源不存在、类型不匹配或不是当前资源"
            elif source == "upload":
                if not (descriptor.get("file_name") or descriptor.get("file") or descriptor.get("storage_uri")):
                    return f"{field} 已选择上传方式，但没有上传资源文件"
            else:
                return f"{field} 的资源来源必须是 database 或 upload"
        if contract.tool_id.startswith("citation-"):
            contexts = payload.get("citation_sentence_and_context")
            metadata = payload.get("citation_metadata")
            if payload.get("input_type") in {"text", "texts"}:
                if not isinstance(contexts, list) or not contexts:
                    return "citation_sentence_and_context 为必填项；文本输入必须提供引用句及其上下文"
                for index, item in enumerate(contexts):
                    if not isinstance(item, dict) or not str(item.get("citation_sentence") or "").strip():
                        return f"第 {index + 1} 条引用数据缺少引用句文本"
                    if not str(item.get("previous_context") or "").strip() or not str(item.get("next_context") or "").strip():
                        return f"第 {index + 1} 条引用数据必须同时提供引用句上文和下文"
                if not metadata:
                    return "citation_metadata 为必填项；文本输入必须提供被引文献元数据"
        if contract.tool_id == "deep-cluster":
            documents = payload.get("documents") or []
            metadata = payload.get("document_metadata")
            if payload.get("input_type") == "texts":
                if not isinstance(metadata, list) or len(metadata) != len(documents):
                    return "document_metadata 必须与科技文献文本逐篇对应"
                for index, item in enumerate(metadata):
                    # 文献编号认 id 别名（前端历史版本/第三方调用可能发 id）
                    if not isinstance(item, dict) or not str(item.get("document_id") or item.get("id") or "").strip() or not str(item.get("title") or "").strip() or not str(item.get("publication_date") or "").strip():
                        return f"第 {index + 1} 篇文献的文献编号、题名和发表时间为必填项"
                    if str(item.get("publication_date") or "").strip() > _today_str():
                        return f"第 {index + 1} 篇文献的发表时间不能晚于今天"
        if contract.tool_id == "structured-review":
            if not str(payload.get("topic_or_keywords") or "").strip():
                return "topic_or_keywords 为必填项"
            if payload.get("input_type") == "texts":
                documents = payload.get("document_set") or []
                metadata = payload.get("document_metadata")
                if not isinstance(metadata, list) or len(metadata) != len(documents):
                    return "document_metadata 必须与文献集逐篇对应"
                for index, item in enumerate(metadata):
                    if not isinstance(item, dict) or not str(item.get("title") or "").strip():
                        return f"第 {index + 1} 篇文献的题名为必填项"
        if payload.get("input_type") == "upstream_records" and not payload.get("upstream_entity_record_id"):
            return "实体关系识别必须选择一条已完成的命名实体识别记录"
        return None

    @staticmethod
    def _cluster_count_error(value: Any, item_count: int) -> Optional[str]:
        """深度聚类 cluster_count 预检：最低 1、最大类簇数量必须小于输入文献数。

        auto 语义（None/""/"auto"/0）与 ``deep_clustering_service._optional_cluster_count``
        保持一致；非法值返回错误消息，合法返回 None。
        """
        if value in (None, "", "auto", 0, "0"):
            return None
        try:
            parsed = float(value)  # noqa: PLW2904 - 先按数值解析再验整数
        except (TypeError, ValueError):
            return "cluster_count 必须为整数或 auto。"
        if not parsed.is_integer():
            return "cluster_count 必须为整数或 auto。"
        parsed = int(parsed)
        if parsed < 1:
            return "cluster_count 必须大于等于 1。"
        if item_count > 1 and parsed >= item_count:
            return f"cluster_count 必须小于输入文献数量（当前 {item_count} 篇，最大 {item_count - 1}）。"
        return None

    @staticmethod
    def _usable_upstream_text(text: Any) -> str:
        """上游原文可用性校验：空或纯文件路径（旧路径透传项）返回空串。

        /files/parse 架构下 NER 任务项存的是解析后全文，直接可用；旧架构存的
        是临时文件路径，relation 阶段多半已失效——路径仍存在则现场重抽文本
        （PyMuPDF 毫秒级），不存在则返回空，由调用方回落实体组装。
        """
        t = str(text or "").strip()
        if not t:
            return ""
        if t.lower().endswith((".pdf", ".docx", ".txt", ".md", ".xlsx")):
            import os as _os
            if not _os.path.exists(t):
                return ""
            try:
                from infrastructure.document_parser.upload_reader import extract_bytes as _eb
                with open(t, "rb") as _f:
                    return str(_eb(_f.read(), _os.path.basename(t)) or "").strip()
            except Exception:  # noqa: BLE001  重抽失败（损坏/格式异常）→ 回落实体组装
                return ""
        return t

    def _text_from_upstream(self, payload: Dict[str, Any]) -> str:
        for key in ("upstream_entity_record_id", "upstream_dependency_record_id"):
            record_id = str(payload.get(key) or "")
            if not record_id:
                continue
            record = self.repository.get_result(record_id)
            if not record:
                continue
            # ① 优先复用上游 NER 的原始全文（契约 2026-09-08：关系抽取须基于所选
            # 批次成员的原文——实体清单组装会丢跨句关系）。/files/parse 架构下
            # NER 任务项已持久化解析后全文；旧路径透传项经 _usable_upstream_text
            # 现场重抽或判失效。
            item = self.repository.get_task_item(str(record.get("task_item_id") or ""))
            item_text = self._usable_upstream_text(self._text_from_task_item(item))
            if not item_text:
                task = self.repository.get_task(record["task_id"]) if record.get("task_id") else None
                if task:
                    source = task.get("request_payload") or {}
                    item_index = item.get("input_index") if item else None
                    item_text = self._usable_upstream_text(
                        self._text_from_task_payload(source, item_index, str(task.get("tool_id") or "")))
                    if not item_text:
                        text = source.get("text") or source.get("abstract")
                        if not text:
                            public_field = PRIMARY_TEXT_FIELDS.get(str(task.get("tool_id") or ""))
                            text = source.get(public_field) if public_field else None
                        item_text = self._usable_upstream_text(text)
                        if not item_text:
                            texts = source.get("texts")
                            if isinstance(texts, list) and texts:
                                first = texts[0]
                                item_text = self._usable_upstream_text(
                                    self._document_text(first) if isinstance(first, dict) else str(first))
            if item_text:
                return item_text
            # ② 原文不可用（旧路径透传且临时文件已失效）→ 复用已识别实体 + 各实体
            # 语境句子组装关系抽取输入（best-effort，跨句关系可能漏，宁缺毋滥）。
            _res = record.get("result") or {}
            _ents = _res.get("entities") or _res.get("entity_results") or []
            if isinstance(_ents, list) and _ents:
                _composed = self._compose_entity_context(_ents)
                if _composed:
                    return _composed
        raise ValueError("上游历史记录不存在，或未保存可复用的原始文本")

    @staticmethod
    def _compose_entity_context(ents: List[Dict[str, Any]]) -> str:
        """把上游 NER 已识别实体组装成关系抽取输入文本。

        上游 NER 的原始全文多为 PDF 临时路径，relation 阶段常已失效且 NER 未
        持久化全文，故复用已识别实体 + 各实体语境句子送 LLM 抽关系；跨句关系
        可能漏，宁缺毋滥（符合抽取召回阈值原则）。
        """
        ent_lines: List[str] = []
        seen_ctx: List[str] = []
        _seen = set()
        for _i, _e in enumerate(ents, 1):
            if not isinstance(_e, dict):
                continue
            _txt = str(_e.get("text") or "").strip()
            if not _txt:
                continue
            _typ = str(_e.get("type") or "").strip()
            _line = f"[{_i}] {_txt}"
            if _typ:
                _line += f"（{_typ}）"
            ent_lines.append(_line)
            _ctx = str(_e.get("context") or "").strip()
            if _ctx and _ctx not in _seen:
                _seen.add(_ctx)
                seen_ctx.append(_ctx)
        if not ent_lines:
            return ""
        _parts = [f"上游命名实体识别已完成，共识别 {len(ent_lines)} 个实体：",
                  "\n".join(ent_lines)]
        if seen_ctx:
            _parts.append("\n实体出现的语境句子（去重）：")
            _parts.append("\n".join(f"S{_j}: {_c}" for _j, _c in enumerate(seen_ctx, 1)))
        _parts.append(
            "\n\n请基于以上已识别实体及其语境句子，抽取实体之间的语义关系三元组 "
            "(头实体, 关系, 尾实体)。关系如治疗/抑制/使用/属于/任职于/应用于等；"
            "同一语境句中共现且存在语义关系的实体优先抽取；关系须语境可支撑，不得臆造。"
        )
        return "\n".join(_parts)

    @classmethod
    def _text_from_task_item(cls, item: Optional[Dict[str, Any]]) -> str:
        if not item:
            return ""
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        for key in ("text", "content", "content_text", "abstract", "abstract_text"):
            if str(source.get(key) or "").strip():
                return str(source[key]).strip()
        return ""

    @classmethod
    def _text_from_task_payload(cls, payload: Dict[str, Any], input_index: Any, tool_id: str = "") -> str:
        """Recover the matching batch member instead of silently using member zero."""
        if not isinstance(input_index, int):
            return ""
        for key in ("texts", "documents"):
            values = payload.get(key)
            if isinstance(values, list) and 0 <= input_index < len(values):
                value = values[input_index]
                if isinstance(value, dict):
                    for field in ("text", "content", "content_text", "abstract", "abstract_text"):
                        if str(value.get(field) or "").strip():
                            return str(value[field]).strip()
                    return cls._document_text(value)
                return str(value or "").strip()
        public_field = PRIMARY_TEXT_FIELDS.get(tool_id)
        values = payload.get(public_field) if public_field else None
        if isinstance(values, list) and 0 <= input_index < len(values):
            value = values[input_index]
            return cls._document_text(value) if isinstance(value, dict) else str(value or "").strip()
        return ""

    def cluster_set_options(self, workspace_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """聚类标签生成任务的簇 → 结构化综述"指定文献集"选项（簇名/时间/篇数）。

        每个已完成的标签生成任务展开为多个文献集（每簇一个）：id 为
        "{task_id}:{cluster_id}"，name 用簇推荐标签。综述按此 id 取簇内文献。
        按任务时间倒序全量返回（2026-09-06 用户定调：移除主题语义相似度
        过滤，研究主题不再影响文献集列表）。
        """
        workspace = workspace_id or settings.DEFAULT_WORKSPACE_ID
        options: List[Dict[str, Any]] = []
        tasks = [
            task for task in self.repository.list_tasks(workspace, limit=200)
            if task.get("tool_id") == "cluster-label" and task.get("status") == "succeeded"
        ][:limit]
        for summary in tasks:
            task = self.repository.get_task(summary["id"]) or summary
            records = self.repository.list_results(summary["id"])
            result = records[0]["result"] if records else {}
            # 人工复核状态（2026-09-06 用户定调）：待复核的簇只有在人工确认
            # （✓ 正确 / 修改标签）后才进入文献集供结构化综述使用；已通过差异
            # 化检查的直接进入；人工改过的标签优先作为簇名
            confirmed_labels: Dict[str, str] = (
                self.repository.label_confirmations_by_record(records[0]["id"]) if records else {})
            threshold = float((result.get("parameters") or {}).get("distinctiveness_threshold") or 0.75)
            # 上游文献题名映射（相似度证据之一）
            payload = task.get("request_payload") or {}
            upstream_id = str(payload.get("cluster_task_id") or "")
            doc_titles: Dict[str, str] = {}
            if upstream_id:
                upstream_result = self._result_from_task(upstream_id)
                doc_titles = {
                    str(a.get("document_id")): str(a.get("title") or "")
                    for a in (upstream_result.get("document_assignments") or [])
                    if isinstance(a, dict)
                }
            for item in result.get("labels") or []:
                if not isinstance(item, dict):
                    continue
                cluster_id = str(item.get("cluster_id") or "")
                confirmed = confirmed_labels.get(cluster_id)
                passed = str(item.get("optimization_status") or "") == "passed" or (
                    isinstance(item.get("distinctiveness"), (int, float))
                    and float(item["distinctiveness"]) >= threshold)
                if not passed and not confirmed:
                    continue  # 待复核且未人工确认：不入文献集
                docs = item.get("linked_document_ids") or []
                name = str(confirmed or item.get("recommended_label") or item.get("label") or cluster_id)
                phrases = [str(p) for p in (item.get("phrases") or item.get("representative_terms") or [])[:6]]
                titles = [doc_titles.get(str(d), "") for d in docs if doc_titles.get(str(d))]
                options.append({
                    "id": f"{summary['id']}:{item.get('cluster_id')}",
                    "name": name,
                    "document_count": len(docs),
                    "created_at": task.get("created_at"),
                    "source_tool": "聚类标签生成工具",
                    "sim_text": " ".join([name] + phrases + titles),
                })
        for opt in options:
            opt.pop("sim_text", None)
        return sorted(options, key=lambda o: str(o.get("created_at") or ""), reverse=True)

    def _cluster_set_documents(self, set_id: str) -> List[Dict[str, Any]]:
        """"{task_id}:{cluster_id}" → 簇内文献（题名+文本）。

        簇成员取自标签生成结果 labels[].linked_document_ids；文献全文从标签任务
        的上游深度聚类任务（cluster_task_id）的请求文献恢复（批量文本输入时
        每篇带 title/text）。
        """
        task_id, _, cluster_id = str(set_id or "").partition(":")
        if not task_id or not cluster_id:
            return []
        label_result = self._result_from_task(task_id)
        label = next((row for row in (label_result.get("labels") or [])
                      if isinstance(row, dict) and str(row.get("cluster_id")) == cluster_id), None)
        if not label:
            return []
        wanted = {str(doc) for doc in (label.get("linked_document_ids") or [])}
        if not wanted:
            return []
        label_task = self.repository.get_task(task_id) or {}
        payload = label_task.get("request_payload") or {}
        upstream_id = str(payload.get("cluster_task_id") or "")
        source_task = (self.repository.get_task(upstream_id) or {}) if upstream_id else label_task
        source_payload = source_task.get("request_payload") or {}
        documents = (source_payload.get("scientific_document_texts")
                     or source_payload.get("documents") or source_payload.get("texts") or [])
        # 文献定位：文件模式上游 payload 文献 id 是适配层编号（FILE001…），而
        # 聚类引擎输出的簇成员用 document_metadata 的编号（DOC001…）——两套
        # 体系错位会全部匹配失败（综述"没有可处理的输入数据"的根因）。按
        # document_metadata 与文献数组同序建立 DOCxxx→FILExxx 别名，两种编号都认
        meta_rows = [row for row in (source_payload.get("document_metadata") or []) if isinstance(row, dict)]
        alias: Dict[str, str] = {}
        for idx, row in enumerate(meta_rows):
            meta_id = str(row.get("document_id") or row.get("id") or "").strip()
            if meta_id and idx < len(documents) and isinstance(documents[idx], dict):
                file_id = str(documents[idx].get("document_id") or documents[idx].get("id") or "").strip()
                if file_id and file_id != meta_id:
                    alias[meta_id] = file_id
        wanted = {alias.get(doc, doc) for doc in wanted}
        # 题名/元数据映射：texts 只带 document_id+text；文件模式的发表时间/作者/
        # 关键词都在上游 document_metadata（DOCxxx 编号，过别名映射到 FILExxx）。
        # 综述的趋势分析/热点分布依赖发表年份，缺了整块为空
        meta_by_file_id: Dict[str, Dict[str, Any]] = {}
        for row in (source_payload.get("document_metadata") or []):
            if isinstance(row, dict):
                meta_id = str(row.get("document_id") or row.get("id") or "")
                meta_by_file_id[alias.get(meta_id, meta_id)] = dict(row)
        titles = {fid: str(row.get("title") or "") for fid, row in meta_by_file_id.items()}
        # 文献内容恢复（2026-09-06）：文件模式任务载荷的 content 为空（轻量透传），
        # 依次回退 ① 上游聚类结果 documents[].content_summary（新链路存 LLM 单篇
        # 摘要）② document_assignments[].key_evidence（每篇的关键证据句，老任务也有）
        upstream_result = self._result_from_task(upstream_id) if upstream_id else {}
        text_by_id: Dict[str, str] = {}
        for row in upstream_result.get("documents") or []:
            if isinstance(row, dict):
                body = str(row.get("content_summary") or row.get("text") or row.get("full_text") or "").strip()
                if body:
                    text_by_id[str(row.get("document_id") or "")] = body
        for row in upstream_result.get("document_assignments") or []:
            if isinstance(row, dict):
                rid = str(row.get("document_id") or "")
                if rid and not text_by_id.get(rid):
                    evidence = " ".join(str(e) for e in (row.get("key_evidence") or []) if str(e).strip()) \
                        if isinstance(row.get("key_evidence"), list) else str(row.get("key_evidence") or "")
                    if evidence.strip():
                        text_by_id[rid] = evidence.strip()
        out: List[Dict[str, Any]] = []
        for index, item in enumerate(documents):
            if not isinstance(item, dict):
                continue
            doc_id = str(item.get("document_id") or item.get("id") or f"DOC{index + 1}")
            if doc_id in wanted:
                # 载荷无文本时用恢复的内容（DOC 编号同样过别名映射）
                recovered = (text_by_id.get(doc_id)
                             or text_by_id.get(next((m for m, f in alias.items() if f == doc_id), ""), ""))
                if not str(item.get("content") or item.get("text") or "").strip() and recovered:
                    item = {**item, "content": recovered}
                meta_row = meta_by_file_id.get(doc_id) or {}
                item = {**meta_row, **item} if meta_row else item
                out.append({
                    "id": doc_id,
                    "title": str(item.get("title") or titles.get(doc_id) or doc_id),
                    "abstract_text": "",
                    "content_text": self._document_text(item),
                    "metadata_json": item,
                })
        return out

    def _inputs_from_task(self, task_id: str) -> List[InputItem]:
        task = self.repository.get_task(task_id)
        if not task:
            raise ValueError(f"历史任务不存在：{task_id}")
        payload = task.get("request_payload") or {}
        documents = payload.get("documents") or payload.get("texts") or []
        return [InputItem(str(item.get("id", index)), self._document_text(item), item) if isinstance(item, dict)
                else InputItem(f"text{index + 1}", str(item), {"input_id": f"text{index + 1}"})
                for index, item in enumerate(documents)]

    def _result_from_task(self, task_id: str) -> Dict[str, Any]:
        records = self.repository.list_results(task_id)
        return records[0]["result"] if records else {}

    @staticmethod
    def _cluster_evidence_sentences(cluster: Dict[str, Any], result: Dict[str, Any]) -> List[str]:
        """簇内成员文献的关键证据句（document_assignments.key_evidence）。

        文件模式下文献题名=上传文件名（含 .pdf），直接当"中心句"展示不合适；
        key_evidence 是每篇文献内容里的真实句子（如方法句/结论句），取簇内
        最长（信息量最高）的前 2 句作为证据句。
        """
        member_ids = {
            str(m.get("document_id")) for m in (cluster.get("members") or [])
            if isinstance(m, dict) and m.get("document_id")
        }
        if not member_ids:
            return []
        sentences = [
            str(a.get("key_evidence") or "").strip()
            for a in (result.get("document_assignments") or [])
            if isinstance(a, dict) and str(a.get("document_id")) in member_ids
            and str(a.get("key_evidence") or "").strip()
        ]
        # 每篇文献一句（key_evidence 本身每篇一条）：语义中心式标签需要
        # 每个成员的视角，漏掉任何一篇都会让标签偏向其余篇目
        return sentences[:6]

    @staticmethod
    def _cluster_phrase_sets(result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recover the label-generator input from a persisted cluster result.

        优先用簇内成员的【人工类目候选分布】作为标签生成输入：主锚定类目计 1 票、
        胶着双候选的第二类目计 1 票，类目名按票数重复进入短语列表——高频类目自然
        成为标签证据，混簇的两个类目共同出现供 GLM 融合命名（如 心血管+脑神经 →
        心脑血管临床诊疗）。锚定信息缺失时回退原代表短语。
        """
        from collections import Counter

        assignments: Dict[str, Dict[str, Any]] = {}
        for item in result.get("document_assignments") or []:
            if isinstance(item, dict) and item.get("document_id"):
                assignments[str(item["document_id"])] = item

        phrase_sets: List[Dict[str, Any]] = []
        for index, cluster in enumerate(result.get("clusters") or []):
            if not isinstance(cluster, dict):
                continue
            # v3 语步对齐聚类：短语集 = 簇代表词（来自语步句关键词，本身就是
            # 综述粒度的内容词）；锚定类目分布分支已随主题库删除（体系级抽象词
            # 会把标签带偏成"智能感知XX"类变体）
            content_terms = [
                t for t in (_clean_cluster_term(value) for value in (
                    cluster.get("representative_terms") or cluster.get("keywords")
                    or cluster.get("top_terms") or cluster.get("phrases") or []))
                if t
            ]
            # v3 簇名（LLM 综述粒度命名，如「语言模型推理增强」）置于短语首位——
            # 标签引擎的胜者多出自首短语，簇名优先保证标签语义；内容词随后佐证
            cluster_name = str(cluster.get("topic_name") or "").strip()
            phrases = list(dict.fromkeys(([cluster_name] if cluster_name else []) + content_terms))
            if not phrases:
                phrases = [cluster_name] if cluster_name else []
            if not phrases:
                continue
            entry = {
                "cluster_id": str(cluster.get("cluster_id") or cluster.get("topic_id") or f"C{index + 1}"),
                "phrases": phrases,
                # 成员文献 ID 透传给标签引擎 → 输出 linked_document_ids（弹窗「关联文献」列）
                "linked_document_ids": [
                    str(m.get("document_id")) for m in (cluster.get("members") or [])
                    if isinstance(m, dict) and m.get("document_id")
                ] or [str(a) for a in (cluster.get("doc_indices") or []) if a],
                # 证据上下文：成员题名 + 代表词（供标签引擎填充 evidence 字段）
                "evidence_titles": [
                    str(d.get("title") or "").strip() for d in (cluster.get("members") or [])
                    if isinstance(d, dict) and str(d.get("title") or "").strip()
                ][:3],
                "evidence_terms_context": [
                    str(t).strip() for t in (cluster.get("representative_terms") or []) if str(t).strip()
                ][:6],
                # 证据句（簇内成员文献的关键证据句，真实句子非文件名）：
                # 标签引擎 evidence.center_sentence 优先取此处的首句
                "evidence_sentences": ToolIntegrationService._cluster_evidence_sentences(cluster, result),
                # v3 标记：簇名即 LLM 综述粒度命名，标签工具直采（不再重生成）
                "topic_name": cluster_name,
                "input_source": "move_aligned" if cluster_name else "legacy",
            }
            phrase_sets.append(entry)
        return phrase_sets
    def _collection_documents(self, collection_id: str) -> List[Dict[str, Any]]:
        if not collection_id:
            return []
        with self.repository.db.session() as session:
            return session.fetchall(
                """SELECT d.id, d.title, d.abstract_text, d.content_text, d.metadata_json
                FROM collection_documents cd JOIN documents d ON d.id=cd.document_id
                WHERE cd.collection_id=? ORDER BY cd.order_no, d.created_at""",
                (collection_id,),
            )

    def _upstream_ids(self, payload: Dict[str, Any]) -> List[str]:
        result_ids = [str(payload[key]) for key in (
            "upstream_entity_record_id", "upstream_dependency_record_id",
        ) if payload.get(key)]
        cluster_task_id = str(payload.get("cluster_task_id") or "")
        if cluster_task_id:
            result_ids.extend(record["id"] for record in self.repository.list_results(cluster_task_id))
        return list(dict.fromkeys(result_ids))

    @staticmethod
    def _dependency_type(tool_id: str) -> str:
        return {"relation-extract": "entity_and_dependency", "cluster-label": "cluster_task", "structured-review": "collection_or_cluster"}.get(tool_id, "upstream")

    @staticmethod
    def _safe_payload(payload: Dict[str, Any], files: List[Dict[str, str]]) -> Dict[str, Any]:
        value = dict(payload)
        if files:
            value["files"] = [{"file_name": item.get("file_name"), "media_type": item.get("media_type")} for item in files]
            value["documents"] = [{
                "id": f"FILE{index + 1:03d}",
                "title": item.get("file_name"),
                "content": item.get("text", ""),
                "media_type": item.get("media_type"),
            } for index, item in enumerate(files)]
        return value

    @staticmethod
    def _summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "succeeded": sum(item["status"] == "succeeded" for item in results),
            "failed": sum(item["status"] == "failed" for item in results),
        }

    def _validation_error(self, contract: ToolContract, request_id: str, input_type: str, started: float, message: str) -> Dict[str, Any]:
        return {
            "code": 42201,
            "message": message,
            "data": {
                "task_id": "", "tool_id": contract.tool_id, "status": "failed", "input_type": input_type,
                "progress": 0, "total": 0, "success_count": 0, "failed_count": 0,
                "results": [], "summary": {}, "available_exports": list(contract.export_formats),
            },
            "meta": {
                "request_id": request_id, "schema_version": "1.0", "model_version": settings.MODEL_VERSION,
                "elapsed_ms": int((time.perf_counter() - started) * 1000), "created_at": _now(),
                "database_dialect": self.repository.db.dialect,
            },
        }
