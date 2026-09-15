"""应用层服务：编排“大模型 + 规则库”的统一执行链路。

职责：
1. 依据功能点 code 加载其独立规则库；
2. 校验输入（单篇/多篇）；
3. 拼装 system prompt（含规则库）与 user prompt（含输入文本）；
4. 调用 GLM 大模型，解析 JSON；
5. 组装领域实体 SemanticResult 返回。

各功能点的“差异”完全封装在各自的规则库 YAML 中，本服务保持通用。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import random
import re
from typing import Any, Dict, List, Optional

from application.dto.common_dto import SemanticRequest
from config.functional_points import InputType, get_functional_point
from domain.entity.base import SemanticResult
from domain.service.base_semantic_service import ISemanticService
from infrastructure.llm.glm_client import GLMClient
from infrastructure.rule_engine.rule_loader import RuleLoader
from domain.value_object.text_input import MultiTextInput, TextInput

logger = logging.getLogger(__name__)


def _number_or_default(value: Any, default: float) -> float:
    """Return a numeric score without inventing one when a malformed value is supplied."""
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# 分中英文场景的功能点（2026-09-08 需求）：严格语言预检，跨语言输入逐篇报错，
# 不再静默退化（如 zh 档收英文 → 中文分句器整篇坍缩成 1 句、中文规则关键词永不
# 命中，逐句证据/句序号输出全废；en 档收中文同理）。值为 (预期语言, 对侧功能点名称)。
LANGUAGE_BY_CODE = {
    "mr_zh_abstract": ("zh", "英文摘要语步识别"),
    "mr_en_abstract": ("en", "中文摘要语步识别"),
    "ac_zh": ("zh", "英文科技文献分类"),
    "ac_en": ("en", "中文科技文献分类"),
    "kw_zh": ("zh", "英文科技文献关键词识别"),
    "kw_en": ("en", "中文科技文献关键词识别"),
    # 基金语步为纯中文场景（NSFC 申请书/结题报告，无英文变体）：英文基金文档
    # 过去会静默通过入口中文结构词闸门，返回五类语步全空的"非基金类文本"，
    # 预检后改为明确报语言不匹配（counterpart=None → 文案不引导切换功能点）。
    "mr_zh_fund": ("zh", None),
}


# 英文功能词防线（2026-09-09，"he/At/ti" 垃圾关键词案例）：kw_en.yaml 的停用词
# 全是学术泛词（study/method/results…），不含基础虚词；LLM 低温下偶发输出虚词时
# 后置清洗拦截不住。此表为英文闭类词（冠词/代词/介词/连词/助动词等），与 yaml
# 学术停用词互补，_clean_keywords 的 en 分支强制套用。

# 公认缩写白名单（2026-09-09）：2~3 字母全大写 token 仅此表放行为关键词，
# 其余按标题/正文大写残片拦截（"MA" 案例）

# ── 关键词过滤词表（数据驱动，2026-09-09）──────────────────────────────
# 词表外置为 rules/keyword_recognition/lexicon_{en,zh}.json（改文件即生效，mtime
# 热加载），取代此前硬编码在源码里的 frozenset——补充停用词/泛意词/碎片/缩写
# 不再需要改代码重启。垃圾词沉淀闭环（runtime/keyword_drops.jsonl）+
# scripts/tools/keyword_lexicon_mine.py 聚类晋升，构成可持续扩充体系。
_LEXICON_CACHE: dict = {}


def _keyword_lexicon(lang: str) -> dict:
    """加载关键词过滤词表（mtime 缓存热加载）。返回 {"block": 拦截词集, "acronyms": 缩写白名单}。"""
    import json as _json
    from pathlib import Path as _P
    from config.settings import settings as _st
    path = _P(_st.RULES_DIR) / "keyword_recognition" / f"lexicon_{'en' if lang == 'en' else 'zh'}.json"
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return {"block": frozenset(), "acronyms": frozenset()}
    cached = _LEXICON_CACHE.get(str(path))
    if cached and cached[0] == mtime:
        return cached[1]
    data = _json.loads(path.read_text(encoding="utf-8"))
    words = {str(w).strip().casefold() for w in data.get("function_words") or [] if str(w).strip()}
    words |= {str(w).strip().casefold() for w in data.get("auto_learned") or [] if str(w).strip()}
    value = {
        "block": frozenset(words),
        "acronyms": frozenset(str(a).strip().upper() for a in data.get("acronym_whitelist") or []),
        # 裸用无领域区分度的实义泛词（damage/model/analysis…）：单单词命中时若
        # 本批存在以其为成分的更长术语则让位（见 _clean_keywords），组合词不受影响
        "generic": frozenset(str(w).strip().casefold() for w in data.get("generic_content_words") or []),
    }
    _LEXICON_CACHE[str(path)] = (mtime, value)
    return value


# 沉淀闭环可晋升的丢弃原因（词质量问题；长度越界/重复等结构性丢弃不进闭环）
_LEXICON_DROP_REASONS = {"英文虚词", "短碎片", "短大写碎片", "原文无此独立词", "中文虚词", "裸泛词让位"}


def _log_keyword_drop(lang: str, word: str, reason: str) -> None:
    """垃圾词丢弃落盘（runtime/keyword_drops.jsonl，词表挖掘脚本的数据源）。"""
    if reason not in _LEXICON_DROP_REASONS:
        return
    try:
        from pathlib import Path as _P
        from config.settings import settings as _st
        p = _P(_st.RULES_DIR).parent / "runtime" / "keyword_drops.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        import datetime as _dt
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                                "lang": lang, "word": word[:60], "reason": reason},
                               ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001  落盘失败不影响主流程
        pass


# 中文虚词/自指词防线（2026-09-09，与英文防线同批）：kw_zh.yaml 停用词同为学术
# 泛词，不含基础虚词。单字虚词本被 2 字下限挡住，但双字词（本文/我们/以及…）
# 可过长度关，且补齐路径无最小长度——统一在此拦截。表内词不可能作为主题关键词。


def _norm_surface(s: str) -> str:
    """实体表面形式归一（去重/变体匹配用）：NFKC + casefold + 去空白与常见标点。"""
    import unicodedata as _ud
    import re as _re
    return _re.sub(r"[\s\.\-·'’`,，、()（）:：;；!！?？/\\]+", "",
                   _ud.normalize("NFKC", str(s)).casefold())


def _lex_contains(nt: str, h: str) -> bool:
    """词表词 nt 是否整体出现在已有实体归一文本 h 中（词表补抽去重用）。
    拉丁词要求整词包含：china ⊂ powerchina 不算（ResNet 篇 China 被
    PowerChina 吞掉的教训）；CJK 无词边界按普通包含。"""
    if not nt or not h or nt not in h:
        return False
    import re as _re
    if _re.search(r"[a-z0-9]", nt + h):
        i = h.find(nt)
        if i > 0 and h[i - 1].isalnum():
            return False
        j = i + len(nt)
        if j < len(h) and h[j].isalnum():
            return False
    return True


def _language_mismatch_error(expected: str, text: str, counterpart: str) -> Optional[str]:
    """语言预检：跨语言输入返回可读错误消息（None=通过）。

    用户规则（2026-09-14 定稿）：中文 >20 字即判中文文献——含中文摘要、
    中英双语论文、带中文参考文献的英文论文（双语=中文）、短中文测试片段
    （2026-09-12 的 >50 门槛曾把 45 字纯中文误判英文）。有效字符
    （CJK+拉丁字母）<30 不判，避免标题类短输入误伤。
    """
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    if cjk + latin < 30:
        return None
    is_chinese = cjk > 20
    if expected == "zh" and not is_chinese:
        return "语言不匹配：该功能点面向中文文献，但输入疑似英文文本。"
    if expected == "en" and is_chinese:
        return "语言不匹配：该功能点面向英文文献，但输入疑似中文文本。"
    return None


class SemanticApplicationService(ISemanticService):
    """语义计算应用服务（单例，由控制器共享）。"""

    def __init__(
        self,
        glm: GLMClient,
        rule_loader: RuleLoader,
    ) -> None:
        self._glm = glm
        self._rule_loader = rule_loader

    @staticmethod
    def _resource_context(request: SemanticRequest, max_chars: int = 12000) -> str:
        """Load a bounded, auditable excerpt from request-selected resources.

        Resource versions are resolved by ``ToolIntegrationService``. Text-like
        uploaded resources therefore affect the current GLM call instead of
        being stored only for display. Large/binary model assets remain version
        references and continue to be consumed by their dedicated local engine.

        对 CLC 资源（clc_labeled_data，zh/en 共用同一份）不塞 raw：
        按内容结构（labeled_papers/taxonomy_complete/taxonomy_scattered）渲染
        few-shot 标注样本或有效分类号范围约束块，供 GLM 当标引风格参考与防幻觉边界。
        非 CLC 资源走原 raw 内容截断逻辑。
        """
        resolved = (request.params or {}).get("resolved_resources") or {}
        if not isinstance(resolved, dict):
            return ""
        blocks = []
        remaining = max_chars
        from pathlib import Path
        from config.settings import settings as _settings
        for field, resource in resolved.items():
            if not isinstance(resource, dict) or remaining <= 0:
                continue
            uri = str(resource.get("storage_uri") or "")
            path = _settings.PROJECT_ROOT / uri.removeprefix("project://") if uri.startswith("project://") else Path(uri)
            excerpt = ""
            if path.is_file() and path.suffix.lower() in {".txt", ".json", ".jsonl", ".yaml", ".yml", ".csv", ".tsv"}:
                try:
                    excerpt = path.read_text(encoding="utf-8-sig", errors="replace")
                except OSError:
                    excerpt = ""
                # JSON 资源优先注入公共归一化行（规则/LLM 容错层产出的标准字段结构，
                # 与预检/引擎消费同一口径）——中文 key 原文不再直接进提示词
                if path.suffix.lower() == ".json":
                    try:
                        from infrastructure.resources.normalize import normalized_rows_for as _nrf
                        import json as _jsonc
                        _rows = _nrf(path)
                        if _rows:
                            excerpt = _jsonc.dumps(_rows, ensure_ascii=False)
                    except Exception:  # noqa: BLE001 - 归一化行不可用时回退原文
                        pass
            # CLC 资源：按 verdict 渲染 few-shot/范围块（非 CLC 走原 raw 截断）
            clc_block = SemanticApplicationService._render_clc_block(field, resource, excerpt, remaining)
            if clc_block is not None:
                block = clc_block
            else:
                header = f"[{field}] 资源ID={resource.get('id')}，版本={resource.get('version')}"
                block = f"{header}\n{excerpt[:remaining]}" if excerpt else header
            blocks.append(block)
            remaining -= len(block)
        return "\n\n".join(blocks)

    # ------------------------------------------------------------------ #
    # CLC 用户上传资源渲染（few-shot 注入 / 范围约束）——阶段1
    # ------------------------------------------------------------------ #
    @staticmethod
    def _render_clc_block(field: str, resource: dict, excerpt: str, budget: int) -> Optional[str]:
        """对 CLC 资源按内容结构渲染 few-shot/范围块；非 CLC 返回 None。

        verdict 优先取 register 时下沉的 metadata.clc_verdict（阶段2），
        缺失则现算 detect_taxonomy_kind；unknown / 非 JSON / 非数组 → None 走原 raw。
        """
        if not excerpt:
            return None
        # 优先取公共归一化行（与 _parameters 预检同一份结构，保证 prompt 注入
        # 与检索作用域看到一致的用户体系）；未注册时维持原 tolerant 解析。
        from config.settings import settings as _cfg
        from infrastructure.resources.normalize import normalized_rows_for, resource_path
        _np = resource_path(str(resource.get("storage_uri") or ""), _cfg.PROJECT_ROOT)
        _norm = normalized_rows_for(_np) if _np is not None else None
        if _norm is not None:
            entries = _norm
        else:
            try:
                entries = json.loads(excerpt)
            except (json.JSONDecodeError, ValueError):
                return None
            # 包装对象解包：{label_version, document_labels:[...]} → 取条目列表，
            # 否则 dict 直接 return None，用户分类体系完全注入不进 prompt。
            if isinstance(entries, dict):
                entries = next(
                    (entries[k] for k in ("document_labels", "labels", "entries", "items", "data", "records")
                     if isinstance(entries.get(k), list)),
                    None,
                )
        if not isinstance(entries, list) or not entries:
            return None
        from infrastructure.rag.clc_meta_builder import detect_taxonomy_kind
        meta = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
        verdict = meta.get("clc_verdict") if isinstance(meta.get("clc_verdict"), dict) else {}
        kind = str(verdict.get("kind") or "").strip() or detect_taxonomy_kind(entries)
        if kind == "unknown":
            return None
        count = len(entries)
        size = len(excerpt)
        from config.settings import settings as _cfg
        is_small = count <= _cfg.CLC_SMALL_MAX_RECORDS and size <= _cfg.CLC_SMALL_MAX_BYTES
        header = f"[{field}] 资源ID={resource.get('id')}，版本={resource.get('version')}"
        framework = ("【用户上传 CLC 资源（" + kind + "）】"
                     "作为标引风格参考与范围约束；分类号须在用户库内真实存在。")
        if kind == "labeled_papers":
            # 2026-09-14 用户定稿：分类资源统一按类目表处理——标注样本不再渲染
            # few-shot 示范，仅提取其中出现过的分类号并入"有效分类号范围"清单。
            # 机制统一为两条：大表建库（向量检索）/ 小表提示词注入范围清单。
            pairs: list = []
            _seen: set = set()
            for e in entries:
                if not isinstance(e, dict):
                    continue
                _mc = e.get("main_classification") if isinstance(e.get("main_classification"), dict) else {}
                _code = str(e.get("clc_code") or _mc.get("clc_code") or e.get("code") or "").strip()
                _name = str(e.get("clc_name") or _mc.get("clc_name") or e.get("name") or "").strip()
                if _code and _code not in _seen:
                    _seen.add(_code)
                    pairs.append({"clc_code": _code, "clc_name": _name})
            body = (SemanticApplicationService._render_clc_scope_list(
                pairs, 50, "有效分类号（仅以下合法，其余禁止）") if pairs else None)
        elif kind == "taxonomy_scattered":
            body = SemanticApplicationService._render_clc_scope_list(
                entries, 50, "有效分类号（仅以下合法，其余禁止）")
        elif kind == "taxonomy_complete":
            if is_small:
                body = SemanticApplicationService._render_clc_scope_list(entries, 50, "有效分类号（仅以下合法）")
            else:
                body = SemanticApplicationService._render_clc_compact_scope(entries)
        else:
            return None
        if not body:
            return None
        block = f"{header}\n{framework}\n{body}"
        return block[:budget] if len(block) > budget else block

    @staticmethod
    def _parse_clc_keywords(kw: Any) -> str:
        """解析关键词（en keywords 可能是 JSON 字符串）。"""
        if not kw:
            return ""
        if isinstance(kw, str):
            try:
                kw = json.loads(kw)
            except (json.JSONDecodeError, ValueError):
                return kw[:120]
        if isinstance(kw, list):
            names = []
            for k in kw:
                if isinstance(k, dict):
                    names.append(str(k.get("ch_name") or k.get("en_name") or k.get("name") or "").strip())
                elif isinstance(k, str):
                    names.append(k.strip())
            return "；".join(n for n in names if n)
        return str(kw)[:120]

    @staticmethod
    def _render_clc_few_shot(entries: list, budget: int) -> str:
        """渲染 labeled_papers few-shot 块（采样≤50，按完整记录边界截断）。"""
        n = len(entries)
        sample = list(entries) if n <= 50 else random.Random(42).sample(entries, 50)
        lines, used = [], 0
        for e in sample:
            if not isinstance(e, dict):
                continue
            title = str(e.get("ch_name") or e.get("en_name") or e.get("title")
                        or e.get("document_id") or "").strip()
            abstract = str(e.get("ch_abstract") or e.get("en_abstract") or "").strip()[:200]
            kw = SemanticApplicationService._parse_clc_keywords(e.get("keywords"))
            main = e.get("main_classification") if isinstance(e.get("main_classification"), dict) else {}
            # 分类字段别名：嵌套 main_classification / 顶层 manual_category_id 等
            code = str(main.get("clc_code") or e.get("manual_category_id")
                       or e.get("clc_code") or "").strip()
            name = str(main.get("clc_name") or e.get("manual_category_name")
                       or e.get("clc_name") or "").strip()
            path = str(main.get("classification_path") or " / ".join(main.get("path_names") or []) or "").strip()
            reason = str(e.get("selection_reason") or "").strip()[:120]
            rec = (f"- 标题：{title}\n  摘要：{abstract}\n  关键词：{kw}\n"
                   f"  → 主分类：{code} {name}\n  路径：{path}\n  理由：{reason}")
            if used + len(rec) > budget:
                break
            lines.append(rec)
            used += len(rec)
        return "\n".join(lines) if lines else ""

    @staticmethod
    def _render_clc_scope_list(entries: list, limit: int, label: str) -> str:
        """渲染有效分类号列表（采样≤limit）。"""
        codes = []
        for e in entries:
            if isinstance(e, dict):
                # 分类号字段别名（clc_code / manual_category_id / code 等）
                c = str(e.get("clc_code") or e.get("manual_category_id")
                        or e.get("classification_code") or e.get("code") or "").strip()
                if c and c not in codes:
                    codes.append(c)
        if len(codes) > limit:
            codes = random.Random(42).sample(codes, limit)
        return f"【{label}】\n" + "\n".join(codes) if codes else ""

    @staticmethod
    def _render_clc_compact_scope(entries: list) -> str:
        """渲染精简范围块（N 条 + 根类，检索细节由 retriever 承载）。"""
        n = len(entries)
        roots = []
        for e in entries:
            if isinstance(e, dict) and not e.get("parent_code"):
                nm = str(e.get("clc_name") or "").strip()
                if nm:
                    roots.append(nm)
        return f"【用户分类树：{n} 条，根类：{' / '.join(roots[:20])}】"

    def _system_prompt(self, rule: Any, request: SemanticRequest, *args: Any) -> str:
        base = rule.render_system_prompt(*args)
        context = self._resource_context(request)
        if not context:
            return base
        return (
            f"{base}\n\n以下为本次请求明确选择的资源版本及其可读取内容，"
            "代表用户单位的自定义口径。**优先级规则：资源块内的补充规则、范围约束、"
            "术语规范与基础提示词冲突时，以资源块为准**（如【用户上传 CLC 资源】的"
            "范围约束、用户规则中的强制分类指令、术语规范中的规范名映射），"
            "不得编造资源中不存在的事实：\n"
            f"{context}"
        )

    def execute(self, code: str, request: SemanticRequest) -> SemanticResult:
        fp = get_functional_point(code)
        result = SemanticResult(code=code, name=fp.name)

        try:
            # 1. 加载该功能点的独立规则库
            rule = self._rule_loader.load(code)

            # 1.5 分中英文功能点语言预检（2026-09-08）：跨语言输入逐篇报错（进响应
            # results 的 error 字段与 error_summary），批量场景只错该篇不影响其余篇。
            # 逐篇工具每次 execute 只带一篇（request.text）；texts 为批量多篇形态。
            _lang_pair = LANGUAGE_BY_CODE.get(code)
            if _lang_pair:
                _expected, _counterpart = _lang_pair
                _texts = list(request.texts or []) if request.texts else ([request.text] if request.text else [])
                for _i, _t in enumerate(_texts):
                    _lang_err = _language_mismatch_error(_expected, str(_t or ""), _counterpart)
                    if _lang_err:
                        raise ValueError(f"第 {_i + 1} 篇输入{_lang_err}" if len(_texts) > 1 else _lang_err)

            # 引擎型规则库走分层式混合管线：
            # - auto_classification（ac_zh）：RAG 检索 → LLM 选/提议 → 后置校验防幻觉
            # - 其它（语步识别）：GLM 主调用（prompt 只含抽象原则）→ 后置规则引擎校验/调分 → 冲突二次审核
            if rule.has_engine:
                if rule.engine_type == "auto_classification":
                    return self._execute_classification(code, request, fp, rule)
                if rule.engine_type == "keyword":
                    return self._execute_keyword(code, request, fp, rule)
                if rule.engine_type == "domain_classification":
                    return self._execute_domain_classification(code, request, fp, rule)
                if rule.engine_type == "rq_identify":
                    return self._execute_rq_identify(code, request, fp, rule)
                if rule.engine_type == "fund_move":
                    return self._execute_fund_move(code, request, fp, rule)
                if rule.engine_type == "clustering":
                    return self._execute_clustering(code, request, fp, rule)
                if rule.engine_type == "labeling":
                    return self._execute_labeling(code, request, fp, rule)
                if rule.engine_type == "structured_review":
                    return self._execute_structured_review(code, request, fp, rule)
                if rule.engine_type == "citation_recognition":
                    return self._execute_citation_recognition(code, request, fp, rule)
                if rule.engine_type == "concept_definition":
                    return self._execute_concept_definition(code, request, fp, rule)
                if rule.engine_type == "ner":
                    return self._execute_ner(code, request, fp, rule)
                return self._execute_with_engine(code, request, fp, rule)

            # 2. 校验输入
            user_payload = self._build_user_payload(fp.input_type, request)

            # 3. 拼装 prompt
            system_prompt = self._system_prompt(rule, request)
            user_prompt = self._render_user_prompt(user_payload, request.params)

            # 4. 调用大模型（强制 JSON 输出）
            data = self._glm.chat_json(system_prompt, user_prompt)

            # 5. 组装结果
            result.success = True
            result.data = data.get("data", data)
            result.evidence = data.get("evidence", [])
            result.confidence = data.get("confidence")
            result.raw = json.dumps(data, ensure_ascii=False)
            return result

        except Exception as exc:  # noqa: BLE001
            logger.exception("功能点 [%s] 执行失败", code)
            result.success = False
            result.error = str(exc)
            return result

    def _execute_with_engine(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """分层式混合管线：Prompt 抽象原则 + 后置规则引擎 + 冲突二次审核。"""
        from pathlib import Path
        from config.settings import settings as _settings
        from training.profile import set_profile_by_code
        from training.rule_lib import RuleLib
        from training.move_classifier import classify_full

        # 按功能点切换语言 profile（mr_zh_abstract→中文，mr_en_abstract→英文）
        set_profile_by_code(code)
        result = SemanticResult(code=code, name=fp.name)
        # 校验单篇文本输入
        user_payload = self._build_user_payload(fp.input_type, request)
        abstract = user_payload.get("text", "")
        if not abstract:
            raise ValueError("语步识别需提供 text 字段（单篇摘要）")
        # 清洗代码仓库地址/URL/邮箱（2026-09-09 需求：不属于任何语步）。
        # 与 result_normalizer 的句子对齐共用同一口径（strip_non_move_artifacts），
        # 避免"service 已清、normalizer 按原文重对齐又拼回"。
        from application.service.result_normalizer import strip_non_move_artifacts
        abstract = strip_non_move_artifacts(abstract)
        import re as _re  # 下方脏输入归一/LaTeX 清理仍用局部 _re
        # 脏输入归一（测试缺陷用例：制表符/多余换行/LaTeX 公式导致分句器碎片化、语步漏检）：
        # ① $...$、$$...$$、\begin{equation}...\end{equation} 公式块内部换行压成单空格
        # ② 制表符/全角空格/连续空格压成单空格 ③ 多余空行合并为单个换行
        def _flatten_math(_m: "_re.Match") -> str:
            return _re.sub(r'\s+', ' ', _m.group(0))
        abstract = _re.sub(r'\$\$[\s\S]+?\$\$|\$[^$\n]+\$', _flatten_math, abstract)
        # LaTeX 环境整块压平:① \begin{...} 到最近的 \end{...} 内部换行压成空格
        # ② 剩余的环境边界行(\end{cases}\n\end{equation})再拼接成单行
        abstract = _re.sub(r'\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\}', _flatten_math, abstract)
        abstract = _re.sub(r'\n(?=\\(?:begin|end)\{)', ' ', abstract)
        abstract = _re.sub(r'[ \t\u3000]+', ' ', abstract)
        abstract = _re.sub(r'\s*\n\s*', '\n', abstract)
        abstract = _re.sub(r'\n{2,}', '\n', abstract)
        abstract = abstract.strip()

        # 加载训练用 RuleLib（与运行时同一 YAML）
        path = Path(_settings.RULES_DIR) / fp.rule_path
        rule_lib = RuleLib.load(path)

        res = classify_full(
            abstract, rule_lib,
            temperature=getattr(_settings, "GLM_TEMPERATURE", 0.1),
            do_review=True,
            domain=request.meta.get("domain") if request.meta else None,
            client=self._glm,
        )

        if res.get("failed"):
            raise RuntimeError("GLM-5.2 未返回有效语步识别结果")

        result.success = True
        # 梯度置信度：基础分来自 LLM 自评的语步级置信度（llm_confidence），规则在其上微调。
        # 这样即使规则关键词未命中（_boost=0），不同语步的 LLM 置信度差异仍能产生梯度，
        # 不会全部退化为常数。规则命中则在此基础上 +boost / -penalty。
        #   - 无冲突：llm_conf(语步) + 每条支持证据 +0.08(上限 +0.25) − 惩罚调整(下限 −0.15)，clamp [0.55, 1.0]
        #   - 冲突经 review 裁决：维持 LLM 判定 → 0.70；改判 → 0.62(说明 LLM 原判有误)
        #   - 冲突未触发 review：0.50
        # 每语步置信度 = 该语步下所有句子置信度的均值；整体置信度 = 全部句子置信度的均值。
        _llm_conf = res.get("llm_confidence") or {}
        from collections import defaultdict as _dd
        _sent_conf_by_move = _dd(list)
        _all_sent_conf = []
        for _sa in res["evidence"]:
            _lbl = _sa.get("review_label") or _sa.get("llm_label")
            if not _lbl:
                continue
            _scores = _sa.get("scores") or {}
            _ev = _sa.get("evidence") or []
            _adj = _sa.get("adjustments") or []
            _n_support = sum(1 for e in _ev if e.get("target") == _lbl)
            _penalty = sum(-a.get("delta", 0.0) for a in _adj
                           if a.get("action") == "-score" and a.get("move") == _lbl)
            if _sa.get("conflict"):
                if _sa.get("review_label"):
                    # review 已裁决：维持→中等，改判→LLM 原判有误，略低
                    _sc = 0.62 if _sa.get("review_label") != _sa.get("llm_label") else 0.70
                else:
                    _sc = 0.50
            else:
                _boost = min(_n_support * 0.08, 0.25)
                _base = _llm_conf.get(_lbl, 0.70)  # LLM 自评的语步置信度作基础分（替代固定 0.70）
                _sc = _base + _boost - min(_penalty * 0.3, 0.15)
                _sc = max(0.55, min(1.0, _sc))
            _sc = round(_sc, 3)
            _sent_conf_by_move[_lbl].append(_sc)
            _all_sent_conf.append(_sc)
        _move_confidence = {
            _m: round(sum(_v) / len(_v), 3)
            for _m, _v in _sent_conf_by_move.items() if _v
        }
        # 每语步的句序号（基于 evidence 逐句标注，按摘要原句顺序）。
        # 语步文本是若干句子的拼接（reassemble_spans），语步句子在摘要中可能
        # 不相邻（如 Background=第1句+第5句），拼接文本无法在原文 indexOf 定位；
        # 句序号供前端字符范围列降级展示，也是非连续语步唯一忠实的定位方式。
        _sent_idx_by_move: Dict[str, List[int]] = {}
        for _i, _sa in enumerate(res["evidence"]):
            _lbl = _sa.get("review_label") or _sa.get("llm_label")
            if _lbl:
                _sent_idx_by_move.setdefault(_lbl, []).append(_i)
        _overall_conf = round(sum(_all_sent_conf) / len(_all_sent_conf), 3) if _all_sent_conf else res["confidence"]
        # 空语步缺失置信度：算法判定该语步缺失，本身是有确信度的识别结果（不是「不确定」）。
        # 默认与整体置信度一致——算法选择空，就是认为该语步大概率不存在；
        # 仅当规则曾建议指向该语步（rule_suggestion 命中但 LLM 未归入）时适度降低，提示可能漏识别。
        _rule_hint = _dd(int)
        for _sa in res["evidence"]:
            _rs = _sa.get("rule_suggestion")
            if _rs:
                _rule_hint[_rs] += 1
        for _m in res["spans"]:
            if _m in _move_confidence:
                continue
            _hints = _rule_hint.get(_m, 0)
            if _m in _llm_conf:
                # LLM 给了判空确信度，直接用（规则曾建议指向该语步时适度降低，提示可能漏识别）
                _move_confidence[_m] = round(max(0.5, _llm_conf[_m] - (0.15 if _hints else 0.0)), 3)
            else:
                _move_confidence[_m] = _overall_conf if not _hints else round(max(0.5, _overall_conf - 0.15), 3)
        result.data = {
            **res["spans"],
            "confidence": _overall_conf,
            "sentence_count": len(res["evidence"]),
            "move_confidence": _move_confidence,
            "sentence_indices_by_move": _sent_idx_by_move,
        }
        result.evidence = [
            {"sentence": s["text"], "llm_label": s["llm_label"],
             "rule_suggestion": s["rule_suggestion"], "conflict": s["conflict"],
             "adjustments": s["adjustments"]}
            for s in res["evidence"]
        ]
        result.confidence = _overall_conf
        result.raw = json.dumps(
            {"spans": res["spans"], "n_conflicts": res["n_conflicts"],
             "n_reviewed": res["n_reviewed"],
             "deterministic_issues": res["deterministic_issues"]},
            ensure_ascii=False,
        )
        return result

    def _resolve_clc_retriever(self, code: str, request: SemanticRequest, cross_lingual: bool = False):
        """按请求选择的 CLC 资源解析检索器：用户库（已建索引）优先，否则内置单例。

        resolved_resources 由 _parameters 按需 resolve（仅 SEMANTIC_RESOURCE_FIELDS），
        每个 resource 含 storage_uri；遍历其值 probe index_dir/clc_index_large/
        manifest.json：存在即该资源已建 CLC 索引→for_path，不存在则跳过试下一个
        （非 CLC 资源/散点/未触发建库均无 manifest）。filesystem 为 ground truth，
        不信 DB 状态防 stale。cross_lingual 且无 clc_index_m3/manifest.json → 告警+内置。
        """
        from infrastructure.rag.clc_retriever import clc_retriever, CLCRetriever
        resolved = (request.params or {}).get("resolved_resources") or {}
        for field, resource in resolved.items():
            if not isinstance(resource, dict):
                continue
            storage_uri = str(resource.get("storage_uri") or "")
            if not storage_uri:
                continue
            index_dir = CLCRetriever._index_dir_for(storage_uri)
            large_manifest = index_dir / "clc_index_large" / "manifest.json"
            if not large_manifest.exists():
                continue  # 该资源未建 CLC 索引，试下一个
            # 命中续期（2026-09-14 索引缓存生命周期）：TTL 闲置判定依据目录 mtime
            try:
                import os as _os
                _os.utime(index_dir)
            except OSError:
                pass
            if cross_lingual:
                m3_manifest = index_dir / "clc_index_m3" / "manifest.json"
                if not m3_manifest.exists():
                    logger.warning("CLC 用户库 %s 无 m3 manifest，ac_en 回退内置 m3", index_dir)
                    return clc_retriever
            try:
                return CLCRetriever.for_path(storage_uri)
            except Exception as e:  # noqa: BLE001
                logger.warning("CLC 用户库 %s 加载失败(%s)，回退内置单例", storage_uri, e)
                return clc_retriever
        if resolved:
            logger.info("CLC _resolve code=%s 有资源但无用户 CLC 索引，用内置单例（resolved_keys=%s）",
                        code, list(resolved.keys()))
        return clc_retriever

    def _user_scope_retriever(self, request: SemanticRequest):
        """从用户选择的 clc_labeled_data 资源条目构建作用域检索器(无索引路径)。

        返回 UserCLCScopeRetriever 或 None(资源不可读/无有效条目时回退内置)。
        """
        resolved = (request.params or {}).get("resolved_resources") or {}
        resource = resolved.get("clc_labeled_data") if isinstance(resolved, dict) else None
        if not isinstance(resource, dict):
            logger.warning("CLC 用户作用域检索器未生效：clc_labeled_data 资源未解析到，回退内置库")
            return None
        uri = str(resource.get("storage_uri") or "")
        if not uri:
            logger.warning("CLC 用户作用域检索器未生效：资源无 storage_uri，回退内置库")
            return None
        from pathlib import Path
        from config.settings import settings as _settings
        path = _settings.PROJECT_ROOT / uri.removeprefix("project://") if uri.startswith("project://") else Path(uri)
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}:
            logger.warning("CLC 用户作用域检索器未生效：资源文件不存在或非 json/jsonl(%s)，回退内置库", path)
            return None
        # 优先取公共归一化结果（_parameters 已对用户 JSON 资源预检+注册）；
        # 未注册（如 .jsonl 等范围外格式）维持原有解析路径。
        from infrastructure.resources.normalize import normalized_rows_for, ResourceParseError
        _normalized = normalized_rows_for(path)
        if _normalized is not None:
            entries = _normalized
        else:
            try:
                text = path.read_text(encoding="utf-8-sig", errors="replace").strip()
                entries = [json.loads(line) for line in text.splitlines() if line.strip()] \
                    if path.suffix.lower() == ".jsonl" else json.loads(text)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                logger.warning("CLC 用户作用域检索器未生效：资源文件读取/解析失败(%s)，回退内置库", exc)
                return None
        from infrastructure.rag.clc_user_scope import UserCLCScopeRetriever
        try:
            retriever = UserCLCScopeRetriever(entries)
        except ValueError as exc:
            if _normalized is not None:
                # 用户指定的 JSON 资源已通过公共归一化预检，此处不可静默回退内置
                raise ResourceParseError(
                    "中图分类资源条目不可用作检索作用域："
                    f"{exc}。请检查每条是否含分类号（clc_code 或别名）。"
                ) from exc
            logger.warning("用户 CLC 资源条目不可用作作用域(%s)，回退内置库。请检查条目是否含 clc_code/clc_name（或别名 code/name）字段", exc)
            return None
        logger.info("CLC 用户作用域检索器生效:%d 个用户条目", len(retriever._order))
        return retriever

    def _execute_classification(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """自动分类管线：LLM 优先（凭 CLC 知识提议）→ 后置校验（resolve_code 防幻觉）。

        设计要点（实测驱动）：
        - bge 检索 recall 低（K=25 约 0.48）且对 TM 电工类系统性跑偏（top-1 常为 TQ/TV/P），
          把候选喂给 LLM 会**锚定**其照抄错误候选（实测 4/4 TM 论文被带偏）；
        - 反之不给候选时 GLM 自身 CLC 知识 4/4 判对二级类（TM7/TM4）——故 LLM 优先，
          检索仅用于产出 rag_top_k_candidates 输出字段，不代替 GLM 的分类结果。
        - GLM 常提出知识库未收录的细码（如 TM713），后置 resolve_code 沿层级上溯到
          最长存在前缀（TM713→TM7），既保留学科判断又确保号真实存在（防幻觉）。
        """

        result = SemanticResult(code=code, name=fp.name)

        # 1. 解析结构化输入（full_text 非 None 时输入为全文，下游直送 LLM 看全文判学科）
        title, abstract, keywords, full_text = self._parse_paper_input(request)
        if not (title or abstract or full_text):
            raise ValueError("自动分类需提供 ch_name/ch_abstract（text 传 paper JSON 或摘要文本）")

        # 2. LLM 凭自身 CLC 知识提议（不含候选，防锚定）；全文输入时附全文供 LLM 参考。
        # 先调用远端 GLM-5.2，成功后再加载体积较大的本地向量检索资源。
        # ——例外：用户自定义 CLC 体系（已建索引）时，GLM 不可能凭参数知识知道自定义
        # 分类号（其先验是中图法，会返回 TP/C 等内置码导致 resolve 失败），此时必须
        # 先检索候选喂给 LLM——候选是自定义体系下唯一的事实来源，不存在锚定问题。
        cross_lingual = bool(getattr(rule, "cross_lingual", False))
        top_k = int((request.params or {}).get("top_k", 5))
        # ── 映射规则·翻译增强（2026-09-15 定稿架构）──
        # 中图分类法是中文构建的：英文要先映射为标准中文表达，再用中文匹配中图分类。
        # 内置 = bge-m3 跨语言向量隐式翻译（默认）；用户上传映射规则 = 词表显式翻译：
        # 标题/摘要/关键词命中表内英文术语 → 对应中文标准表达并入检索查询与提示词，
        # 候选与选择仍走语义判断（不锁定结果）。命中事实透出到跨语言映射块。
        _mapping_hits: dict = {}   # {中文标准表达: 英文术语}——纯翻译表
        _map_res = ((request.params or {}).get("resolved_resources") or {}).get(
            "classification_standard_mapping_table")
        if isinstance(_map_res, dict) and cross_lingual:
            try:
                for _r in self._load_clc_mapping_rows(_map_res):
                    _t = str(_r.get("term") or "").strip()
                    _zh = str(_r.get("clc_name") or _r.get("label") or "").strip()
                    if _t and _zh and _zh not in _mapping_hits:
                        _hay = f"{title}\n{abstract}\n{keywords}".casefold()
                        if _t.casefold() in _hay:
                            _mapping_hits[_zh] = _t
            except Exception:  # noqa: BLE001
                logger.warning("en分类映射规则加载失败，忽略", exc_info=True)
        _keywords_eff = keywords
        if _mapping_hits:
            # 命中术语的中文标准表达并入检索查询（翻译增强检索）。
            # keywords 可能是 list（_parse_paper_input 解析产物）——先归一为字符串
            _kw_str = " ".join(keywords) if isinstance(keywords, list) else str(keywords or "")
            _keywords_eff = (_kw_str + " " + " ".join(_mapping_hits)).strip()

        custom_retriever = None
        custom_candidates: list = []
        if isinstance((request.params or {}).get("resolved_resources"), dict) \
                and (request.params or {}).get("resolved_resources", {}).get("clc_labeled_data"):
            from infrastructure.rag.clc_retriever import clc_retriever as _builtin
            resolved_retriever = self._resolve_clc_retriever(code, request, cross_lingual)
            if resolved_retriever is not _builtin:
                custom_retriever = resolved_retriever
                custom_candidates = custom_retriever.retrieve(
                    title, abstract, _keywords_eff, k=max(top_k, 12), cross_lingual=cross_lingual)
            else:
                # 用户选了资源但未建向量索引(散点表/小表/标注样本):用资源条目本身构建
                # 作用域检索器,resolve_code/children 均对用户条目生效——否则后置校验会把
                # 用户分类号上溯成内置中图法码,表现为"选了用户上传资源仍按后台分类"
                custom_retriever = self._user_scope_retriever(request)
                if custom_retriever is not None:
                    custom_candidates = custom_retriever.retrieve(
                        title, abstract, _keywords_eff, k=max(top_k, 12), cross_lingual=cross_lingual)

        system_prompt = self._system_prompt(rule, request)
        user_prompt = self._render_classification_user_prompt(title, abstract, keywords, full_text)
        if custom_candidates:
            lines = []
            for i, cand in enumerate(custom_candidates):
                path = " > ".join(cand.get("path_names") or []) or str(cand.get("full_path") or "")
                lines.append(f"[{i + 1}] {cand.get('clc_code')} {cand.get('clc_name')}"
                             + (f" | 路径: {path}" if path else ""))
            user_prompt += (
                "\n\n【重要】本次使用用户自定义分类体系（非中图法）。"
                "main_code 与 auxiliary_codes 必须且只能从下列候选分类号中选择，"
                "禁止使用任何不在候选中的分类号（包括你已知的中图法分类号）：\n"
                + "\n".join(lines)
            )
        if _mapping_hits:
            user_prompt += (
                "\n\n【用户映射规则·术语对照】用户上传的映射规则给出以下标准中文表达，"
                "分类判断时请优先按这些中文表达对应的类目理解原文：\n"
                + "\n".join(f"- {_t} → {_zh}" for _zh, _t in _mapping_hits.items()))
        data = self._glm.chat_json(system_prompt, user_prompt, timeout=120.0, max_tokens=1500)
        data = data.get("data", data) if isinstance(data, dict) else {}

        # 3. 检索 top-K（仅用于输出 rag_top_k_candidates + 兜底，不喂给 LLM；
        #    自定义体系路径已在第 2 步提前检索并喂给 LLM，此处复用）
        retriever = custom_retriever if custom_retriever is not None else \
            self._resolve_clc_retriever(code, request, cross_lingual)
        if custom_candidates:
            candidates = custom_candidates
        else:
            candidates = retriever.retrieve(title, abstract, _keywords_eff, k=top_k,
                                            cross_lingual=cross_lingual)

        # 3b. 解析候选组合（1-3 组，按推荐度降序）；兼容旧版 main_code/auxiliary_codes 单组合响应
        combos_raw = data.get("combinations") or []
        if not combos_raw:
            legacy_main = (data.get("main_code") or "").strip()
            legacy_aux = [c.strip() for c in (data.get("auxiliary_codes") or []) if c and c.strip()]
            if legacy_main:
                combos_raw = [{"main_code": legacy_main, "auxiliary_codes": legacy_aux[:1],
                               "confidence": 1.0, "reason": data.get("selection_reason", "")}]
        if not combos_raw:
            raise RuntimeError("GLM-5.2 未返回有效分类组合")
        combos_raw = combos_raw[:3]

        # 4. 二阶段层级细化：仅对首选组合(组合1)的主分类号细化
        #    （层级引导，非语义检索候选——不会锚定到错误学科，只在该学科内选子码）
        refine = (request.params or {}).get("refine", True)
        if combos_raw:
            c0_main = (combos_raw[0].get("main_code") or "").strip()
            proposed_entry = retriever.resolve_code(c0_main)
            if refine and proposed_entry is not None:
                picked = self._refine_main_hierarchy(title, abstract, keywords, proposed_entry, retriever)
                if picked and picked != c0_main:
                    combos_raw[0]["reason"] = ("[二阶段细化 %s→%s] " % (c0_main, picked)) + (combos_raw[0].get("reason") or "")
                    combos_raw[0]["main_code"] = picked

        # 5. 逐组后置校验：resolve_code 上溯到知识库真实条目，名称/路径从 meta 复制
        candidate_combinations = []
        all_resolved = True
        for idx, combo in enumerate(combos_raw):
            mc = (combo.get("main_code") or "").strip()
            if not mc:
                continue
            main_entry = retriever.resolve_code(mc)
            if main_entry is None:
                all_resolved = False
                continue
            main_obj = self._entry_to_obj(main_entry, candidates) if main_entry else None
            if not main_obj:
                all_resolved = False
                continue

            llm_conf = float(combo.get("confidence") or 0)
            # 用 LLM 返回的真实置信度，不再把首选组合写死成 1.0；封顶 0.95 防虚高
            main_obj["confidence"] = min(llm_conf, 0.95)
            combo_conf = main_obj["confidence"]

            # 次分类 = 跨学科主次配对中的"次"：仅保留与主分类跨学科边界的辅助号（至多1个）。
            # 同边界的辅助号无意义（非跨学科不该有次分类）→ 丢弃；解析失败也丢弃。
            aux_objs = []
            for ac in (combo.get("auxiliary_codes") or [])[:1]:
                ac = ac.strip() if ac else ""
                if not ac:
                    continue
                ae = retriever.resolve_code(ac)
                if ae is None:
                    continue
                if not self._is_cross_discipline(mc, ae["clc_code"]):
                    continue  # 同边界：非跨学科，次分类无意义，丢弃
                ao = self._entry_to_obj(ae, candidates)
                # 次分类同样用真实组合置信度，不再写死 0.8 / 0.6
                ao["confidence"] = min(llm_conf, 0.95)
                aux_objs.append(ao)

            # 后置纠正：GLM 偶尔把"方法/技术"当主分类、应用场景当次分类（违反 ac_zh 核心规则"主分类=应用场景"）。
            # 若主分类是 AI/图像识别/遥感图像处理等方法类、且有跨学科次分类（应用领域），交换主次：
            # 应用领域升为主分类、方法类降为次分类；inter 由新主次边界客观重算。
            if mc.startswith(("TP18", "TP391", "TP751")) and aux_objs:
                main_obj, aux_objs = aux_objs[0], [main_obj]
                mc = (main_obj.get("clc_code") or "").strip()
                combo["reason"] = "[后置纠正：主分类由方法类交换为应用场景] " + (combo.get("reason") or "")

            # 有次分类 ⟺ 跨学科：inter 由主次码边界关系客观决定（不依赖 LLM 的 is_interdisciplinary）
            aux_code = aux_objs[0].get("clc_code") if aux_objs else ""
            inter = self._is_cross_discipline(mc, aux_code)
            candidate_combinations.append({
                "rank": idx + 1,
                "main_classification": main_obj,
                "auxiliary_classifications": aux_objs,
                "is_interdisciplinary": inter,
                "confidence": combo_conf,
                "reason": combo.get("reason") or "",
            })

        if not candidate_combinations:
            raise RuntimeError("GLM-5.2 返回的分类号无法在 CLC 知识库中验证")

        # 6. 组装结果（与 gold 结构对齐）：旧字段从首选组合派生
        primary = candidate_combinations[0]
        main_obj = primary["main_classification"]
        aux_objs = primary["auxiliary_classifications"]
        rag_cands = [self._candidate_to_obj(c, with_rank=True) for c in candidates]
        alignment_check = {
            "all_codes_exist_in_clc_meta": all_resolved,
            "paths_copied_from_clc_meta": True,
            "path_not_generated_by_model": True,
        }
        out = {
            # 文献题目回传：前端 recordsOf 第一列取 document_title，缺失会落到 file_name/input_id
            "document_title": title,
            "rag_top_k_candidates": rag_cands,
            "candidate_combinations": candidate_combinations,
            "main_classification": main_obj,
            "auxiliary_classifications": aux_objs,
            "is_interdisciplinary": primary["is_interdisciplinary"],
            "selection_reason": primary["reason"],
            "alignment_check": alignment_check,
        }
        # 映射规则命中透出（出口层既有契约 user_mapping_applied →
        # cross_language_mapping.status="已映射（用户映射规则命中）"，前端
        # enMappingCell 展示命中术语与来源）
        if _mapping_hits:
            out["user_mapping_applied"] = {
                "term": "; ".join(_mapping_hits.values()),
                "matched_terms": list(_mapping_hits.values()),
                "zh_terms": list(_mapping_hits.keys()),
            }

        result.success = True
        result.data = out
        result.confidence = main_obj.get("confidence") if main_obj else None
        result.raw = json.dumps(out, ensure_ascii=False)
        return result

    # ---- 分类管线辅助 ---- #
    def _parse_paper_input(self, request: SemanticRequest):
        """从 request.text 解析 (title, abstract, keywords, full_text)。

        text 可为：① paper 的 JSON（含 ch_name/ch_abstract/keywords）；
                  ② 文件路径（.pdf/.md）→ MinerU全文；
                  ③ 原始全文（mineru markdown）→ LLM提取标题/摘要/关键词；
                  ④ 纯摘要文本。
        返回的 full_text 在输入为全文（情形②③）时为原始全文文本，下游可直接用全文
        送 LLM（LLM 优先版：不只看摘要）；其余情形为 None，下游退回用 abstract。
        """
        import json as _json
        text = (request.text or "").strip()
        title, abstract, keywords = "", "", []
        full_text = None
        if text and text[0] in "{[":
            try:
                obj = _json.loads(text)
                title = (obj.get("ch_name") or obj.get("en_name")
                         or obj.get("title") or "")
                abstract = (obj.get("ch_abstract") or obj.get("en_abstract")
                            or obj.get("abstract") or "")
                kws = obj.get("keywords", []) or []
                keywords = [(k.get("en_name") or k.get("ch_name") or "") if isinstance(k, dict) else k
                            for k in kws]
                keywords = [k for k in keywords if k]
                generic_text = (obj.get("text") or obj.get("content") or obj.get("full_text") or "").strip()
                if generic_text and not (title and abstract and keywords):
                    from infrastructure.clustering.input_representation import parse_labeled_structure
                    parsed = parse_labeled_structure(generic_text)
                    if parsed:
                        title = title or parsed["title"]
                        abstract = abstract or parsed["abstract"]
                        keywords = keywords or parsed["keywords"]
                    else:
                        abstract = abstract or generic_text
            except _json.JSONDecodeError:
                abstract = text
        elif text and os.path.exists(text) and text.lower().endswith(('.pdf', '.md')):
            # 文件路径 → MinerU全文
            from infrastructure.document_parser.mineru_reader import process_to_text
            doc = process_to_text(text)
            text = doc.get("full_text", "")
            title = self._extract_paper_title(text)
            # 全文 → LLM提取摘要/关键词；同时保留 full_text 供下游直送 LLM
            if text:
                full_text = text
                ext_title, abstract, keywords = self._llm_extract_paper_fields(text, title)
                title = title or ext_title
        elif self._looks_like_full_document(text):
            # 原始全文 → LLM提取标题/摘要/关键词；同时保留 full_text 供下游直送 LLM
            full_text = text
            title, abstract, keywords = self._llm_extract_paper_fields(text, title)
        else:
            from infrastructure.clustering.input_representation import parse_labeled_structure
            parsed = parse_labeled_structure(text)
            if parsed:
                title, abstract, keywords = parsed["title"], parsed["abstract"], parsed["keywords"]
            else:
                abstract = text
                # 纯文本全文（MinerU 失败回退 pypdf 的 PDF 全文，无 ## 标题行 → 落到本分支）：
                # 文本足够长且多行才视作全文，从首部提取论文题目，避免 document_title 落空
                # 回退到文件名（前端批量 recordsOf 在 document_title 为空时显示 item.file_name）。
                # 粘贴的单条摘要（短、少换行）不提取，避免把摘要首句误当题目。
                if len(text) > 1500 and text.count("\n") >= 20:
                    title = self._extract_paper_title(text) or ""
        # meta 兜底
        if request.meta:
            title = title or request.meta.get("ch_name", "")
            if not keywords and "keywords" in request.meta:
                keywords = request.meta["keywords"]
        return title, abstract, keywords, full_text

    @staticmethod
    def _looks_like_full_document(text: str) -> bool:
        """判断 text 是否为 mineru 输出的原始文档全文（含多个 markdown 标题行）。"""
        import re as _re
        if not text:
            return False
        heading_lines = len(_re.findall(r'^#{1,6}\s+\S', text, _re.MULTILINE))
        return heading_lines >= 2

    def _llm_extract_paper_fields(self, text: str, title_hint: str = ""):
        """LLM从全文提取标题/摘要/关键词（替代DocumentParser的结构化提取）。"""
        title = title_hint
        abstract = ""
        keywords = []
        # 标题：跳过期刊名/出版信息行，取首个真正的论文题目行
        if not title:
            title = self._extract_paper_title(text)
        # 摘要+关键词：LLM提取
        sysp = ("你是文献信息提取专家。从给定文献全文前3000字中提取摘要和关键词。\n"
                "摘要：文献的核心内容概述（100-300字）\n"
                "关键词：3-8个专业术语\n"
                "只输出JSON：{\"data\":{\"abstract\":\"...\",\"keywords\":[\"词1\",\"词2\"]}}")
        d = self._glm.chat_json(sysp, f"文献全文（前3000字）：\n{text[:3000]}",
                                timeout=60.0, max_tokens=500, temperature=0.0)
        d = d.get("data", d) if isinstance(d, dict) else {}
        abstract = (d.get("abstract") or "").strip()
        kws = d.get("keywords", []) or []
        keywords = [k.strip() for k in kws if k and k.strip()]
        if not abstract:
            raise RuntimeError("GLM-5.2 未从全文中返回有效摘要")
        return title, abstract, keywords

    @staticmethod
    def _render_classification_user_prompt(title, abstract, keywords, full_text=None) -> str:
        """渲染 user prompt：只给文献信息，不给检索候选（防锚定，LLM 凭 CLC 知识提议）。

        full_text 非 None 时附前 6000 字全文，让 LLM 从全文判断学科（不只看摘要）。
        """
        import json as _json
        obj = {
            "ch_name": title, "ch_abstract": abstract, "keywords": keywords,
            "说明": "凭你对中图分类法的知识预测分类号；main_code 给最贴切的真实中图法类号"
                    "（可细到下位类）；auxiliary_codes 0-1 个；按输出格式返回 JSON。",
        }
        if full_text:
            obj["全文（前6000字，供从全文判断学科，勿照抄小节标题作分类号）"] = full_text[:6000]
        return "请为以下中文科技文献预测中图分类号：\n" + _json.dumps(
            obj, ensure_ascii=False, indent=2)

    @staticmethod
    def _candidate_to_obj(cand: dict, with_rank: bool = False) -> dict:
        """把检索候选拐成 gold 兼容的分类对象（保留 score 供前端/归一化过滤）。"""
        obj = {
            "clc_code": cand.get("clc_code") or "",
            "clc_name": cand.get("clc_name") or "",
            "classification_path": cand.get("classification_path")
                or cand.get("full_path") or "",
            "path_codes": cand.get("path_codes") or [],
            "path_names": cand.get("path_names") or [],
            "rag_entry_id": cand.get("rag_entry_id") or cand.get("id") or "",
            "score": cand.get("score"),
        }
        if with_rank:
            obj["rank"] = cand.get("rank") or 0
        return obj

    @staticmethod
    @staticmethod
    @staticmethod
    def _load_rules_taxonomy(descriptor: dict) -> list:
        """读领域分类规则资源 → CLC 条目列表（供作用域检索器构建）。

        支持两种格式：
        ① 数组：[{clc_code, clc_name, parent_code?}, ...]（与 clc_labeled_data 同构）
        ② 包装：{categories: [...]} / {taxonomy: [...]} 等 → 自动解包
        """
        from infrastructure.resources.normalize import normalized_rows_for, resource_path
        from config.settings import settings as _st
        path = resource_path(str((descriptor or {}).get("storage_uri") or ""), _st.PROJECT_ROOT)
        if path is None:
            return []
        rows = normalized_rows_for(path)
        if not rows:
            import json as _json
            try:
                doc = _json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
            except Exception:  # noqa: BLE001
                return []
            if isinstance(doc, dict):
                doc = next((doc[k] for k in ("categories", "taxonomy", "entries", "items", "data", "labels")
                            if isinstance(doc.get(k), list)), [])
            rows = [r for r in (doc or []) if isinstance(r, dict)]
        # 提取 CLC 条目（与 clc_labeled_data 同构的字段别名）
        out = []
        for r in rows:
            code = str(r.get("clc_code") or r.get("code") or r.get("id") or "").strip()
            name = str(r.get("clc_name") or r.get("name") or r.get("label") or "").strip()
            parent = str(r.get("parent_code") or r.get("parent") or "").strip()
            if code and name:
                out.append({"clc_code": code, "clc_name": name, "parent_code": parent,
                            "id": code})
        # 沿 parent_code 链构建层级路径（大类算一级，最多展示三级）
        _by_code = {e["clc_code"]: e for e in out}
        for e in out:
            chain = []
            cur = e
            seen = set()
            while cur and cur["clc_code"] not in seen:
                seen.add(cur["clc_code"])
                chain.insert(0, cur)
                parent_code = cur.get("parent_code") or ""
                cur = _by_code.get(parent_code) if parent_code else None
            # 压缩到三级：一级=根节点，二级=根的直接子节点，三级=分类结果本身
            if len(chain) >= 3:
                display = [chain[0], chain[1], chain[-1]]
            elif len(chain) == 2:
                display = chain
            else:
                display = chain
            e["path_codes"] = [c["clc_code"] for c in display]
            e["path_names"] = [c["clc_name"] for c in display]  # 纯名称，码前缀由 normalizer 拼接
            e["full_path"] = " > ".join(f"{c} {n}" for c, n in zip(e["path_codes"], e["path_names"]))
        return out

    @staticmethod
    def _build_scope_retriever_from_entries(entries: list):
        """从 CLC 条目列表构建作用域检索器（与 _user_scope_retriever 同理）。

        条目少（≤200），用 bge-m3 向量编码做余弦检索；无需建磁盘索引。
        """
        if not entries:
            return None
        try:
            import numpy as _np
            from infrastructure.rag.m3_encoder import m3_encoder as _m3
            texts = [f"{e['clc_code']} {e['clc_name']}" for e in entries]
            vecs = _np.asarray(_m3.encode(texts), dtype="float32")
            norms = _np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            vecs = vecs / norms

            class _ScopeRetriever:
                def resolve_code(self, code: str):
                    for e in entries:
                        if e["clc_code"] == code:
                            return e
                    return None

                def children(self, parent_code: str):
                    return [e for e in entries if e.get("parent_code") == parent_code]

                def retrieve(self, title, abstract, keywords, k=5, cross_lingual=False):
                    query = f"{title or ''} {abstract or ''} {keywords or ''}".strip()[:2000]
                    if not query:
                        return entries[:k]
                    qv = _np.asarray(_m3.encode([query]), dtype="float32")
                    qn = _np.linalg.norm(qv, axis=1, keepdims=True)
                    qn[qn == 0] = 1.0
                    qv = qv / qn
                    sims = (vecs @ qv.T).flatten()
                    order = _np.argsort(-sims)[:k]
                    out = []
                    for idx in order:
                        e = dict(entries[int(idx)])
                        e["score"] = float(sims[int(idx)])
                        out.append(e)
                    return out

            return _ScopeRetriever()
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _render_fewshot_examples(descriptor: dict, max_examples: int = 5) -> str:
        """读人工标注训练数据 → few-shot 样本文本（注入提示词）。

        支持格式：[{text, label}, ...] 或 [{text, 分类标签}, ...] 等别名。
        """
        from infrastructure.resources.normalize import normalized_rows_for, resource_path
        from config.settings import settings as _st
        path = resource_path(str((descriptor or {}).get("storage_uri") or ""), _st.PROJECT_ROOT)
        if path is None:
            return ""
        rows = normalized_rows_for(path)
        if not rows:
            import json as _json
            try:
                rows = _json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
            except Exception:  # noqa: BLE001
                return ""
            if isinstance(rows, dict):
                rows = next((rows[k] for k in ("samples", "examples", "data", "entries", "items")
                             if isinstance(rows.get(k), list)), [])
        lines = []
        for r in (rows or []):
            if not isinstance(r, dict):
                continue
            text = str(r.get("text") or r.get("content") or r.get("示例文本") or "").strip()
            label = str(r.get("label") or r.get("category") or r.get("classification")
                        or r.get("标签") or r.get("分类") or r.get("标注") or "").strip()
            if text and label:
                lines.append(f"- 文本「{text[:120]}」→ 分类「{label}」")
            if len(lines) >= max_examples:
                break
        return "\n".join(lines)

    @staticmethod
    def _match_training_examples(descriptor: dict, input_text: str, threshold: float = 0.45) -> dict:
        """计算输入文本与训练样本的语义相似度，返回匹配结果。

        相似度 ≥ threshold 的样本视为"命中"，其标签类别并入检索关键词
        ——训练数据有了不依赖领域规则的独立可观察效果。
        返回 {"match_count": N, "matched_labels": [...], "matched_examples": [...]}
        """
        if not input_text or not input_text.strip():
            return {}
        from infrastructure.resources.normalize import normalized_rows_for, resource_path
        from config.settings import settings as _st
        path = resource_path(str((descriptor or {}).get("storage_uri") or ""), _st.PROJECT_ROOT)
        if path is None:
            return {}
        rows = normalized_rows_for(path)
        if not rows:
            import json as _json
            try:
                rows = _json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
            except Exception:  # noqa: BLE001
                return {}
            if isinstance(rows, dict):
                rows = next((rows[k] for k in ("samples", "examples", "data", "entries")
                             if isinstance(rows.get(k), list)), [])
        pairs = []
        for r in (rows or []):
            if not isinstance(r, dict):
                continue
            text = str(r.get("text") or r.get("content") or "").strip()
            label = str(r.get("label") or r.get("category") or r.get("classification")
                        or r.get("标签") or "").strip()
            if text and label:
                pairs.append((text, label))
        if not pairs:
            return {}
        try:
            import numpy as _np
            from infrastructure.rag.m3_encoder import m3_encoder as _m3
            texts = [p[0] for p in pairs] + [input_text]
            vecs = _np.asarray(_m3.encode(texts), dtype="float32")
            norms = _np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            vecs = vecs / norms
            sims = (vecs[:-1] @ vecs[-1]).flatten()
            matched = []
            labels = []
            for (text, label), sim in zip(pairs, sims):
                if float(sim) >= threshold:
                    matched.append({"text": text[:80], "label": label, "similarity": round(float(sim), 3)})
                    if label not in labels:
                        labels.append(label)
            if not matched:
                return {}
            return {"match_count": len(matched), "matched_labels": labels, "matched_examples": matched}
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def _parse_training_pairs(descriptor: dict) -> list:
        """解析训练数据 → [(text, label), ...]。"""
        from pathlib import Path as _P
        from config.settings import settings as _st
        uri = str((descriptor or {}).get("storage_uri") or "")
        path = _P(uri.removeprefix("project://")) if uri else None
        if path is not None and not path.is_absolute():
            path = _st.PROJECT_ROOT / path
        if path is None or not path.is_file():
            return []
        import json as _json
        try:
            rows = _json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except Exception:  # noqa: BLE001
            return []
        if isinstance(rows, dict):
            rows = next((rows[k] for k in ("samples", "examples", "data", "entries", "items")
                         if isinstance(rows.get(k), list)), [])
        return [(str(r.get("text") or r.get("content") or "").strip(),
                 str(r.get("label") or r.get("category") or r.get("classification")
                     or r.get("标签") or "").strip())
                for r in (rows or []) if isinstance(r, dict)
                and str(r.get("text") or r.get("content") or "").strip()
                and str(r.get("label") or r.get("category") or r.get("classification")
                        or r.get("标签") or "").strip()]

    @staticmethod
    def _compute_training_similarity(pairs: list, input_text: str, threshold: float = 0.45) -> dict:
        """输入文本与训练样本的语义相似度 → 匹配结果（标签并入检索）。"""
        if not input_text.strip() or not pairs:
            return {}
        try:
            import numpy as _np
            from infrastructure.rag.m3_encoder import m3_encoder as _m3
            texts = [p[0] for p in pairs] + [input_text]
            vecs = _np.asarray(_m3.encode(texts), dtype="float32")
            norms = _np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            vecs = vecs / norms
            sims = (vecs[:-1] @ vecs[-1]).flatten()
            matched, labels = [], []
            for (text, label), sim in zip(pairs, sims):
                if float(sim) >= threshold:
                    matched.append({"text": text[:80], "label": label, "similarity": round(float(sim), 3)})
                    if label not in labels:
                        labels.append(label)
            return ({"match_count": len(matched), "matched_labels": labels, "matched_examples": matched}
                    if matched else {})
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def _load_clc_mapping_rows(descriptor: dict) -> list:
        """读用户映射规则资源 → [{term, clc_code, clc_name}]（归一化行优先）。"""
        from infrastructure.resources.normalize import normalized_rows_for, resource_path
        from config.settings import settings as _st
        path = resource_path(str((descriptor or {}).get("storage_uri") or ""), _st.PROJECT_ROOT)
        if path is None:
            return []
        rows = normalized_rows_for(path)
        if not rows:
            import json as _json
            try:
                rows = _json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
            except Exception:  # noqa: BLE001
                return []
        # 2026-09-15 定稿：en分类的映射规则=纯翻译表（英文术语→中文术语），
        # 分类号在分类工具里没有意义（分类由语义定案），行内带码也忽略
        return [r for r in (rows or [])
                if isinstance(r, dict) and str(r.get("term") or "").strip()
                and str(r.get("clc_name") or r.get("label") or "").strip()]

    @staticmethod
    def _entry_to_obj(entry: dict, candidates) -> dict:
        """把 clc_meta 条目拐成 gold 兼容的分类对象；命中候选时复用其 rag_entry_id。"""
        rag_id = entry.get("id") or entry.get("clc_code") or ""
        for c in candidates:
            if c.get("clc_code") == entry.get("clc_code"):
                rag_id = c.get("rag_entry_id") or rag_id
                break
        return {
            "clc_code": entry["clc_code"],
            "clc_name": entry["clc_name"],
            "classification_path": entry["full_path"],
            "path_codes": entry["path_codes"],
            "path_names": entry["path_names"],
            "rag_entry_id": rag_id,
        }

    @staticmethod
    def _is_cross_discipline(main_code: str, aux_code: str) -> bool:
        """判断主/辅分类号是否分属不同学科边界（用于备选组合的交叉学科重算）。

        规则与 prompt 一致：T 大类是人为聚合，其下二级类（TM/TP/TQ/TU…）才是学科边界；
        其余大类按一级字母。同边界不算交叉。
        """
        if not main_code or not aux_code:
            return False

        def boundary(code: str) -> str:
            c = code.strip()
            if not c:
                return ""
            # T 工业技术大类下取二级类（如 TG115.28 → TG）
            if c[0] == "T" and len(c) > 1 and c[1].isalpha():
                return "T" + c[1]
            return c[0]

        return boundary(main_code) != boundary(aux_code)

    def _refine_main_hierarchy(self, title, abstract, keywords, proposed_entry, retriever) -> str:
        """二阶段层级细化：把初判码的同级（父的子）+ 下位子码列给 LLM，选最贴切的具体号。

        与语义检索候选的区别：只在初判码所属学科内提供层级邻居，不会把 LLM 拉到
        另一个错误学科；解决"学科对但子码选错"（如 TM712稳定 vs TM713短路）。
        """
        proposed = proposed_entry["clc_code"]
        parent = proposed_entry.get("parent_code")
        neigh = []
        seen = set()
        for e in (retriever.children(parent) if parent else []) + retriever.children(proposed):
            if e["clc_code"] not in seen:
                seen.add(e["clc_code"])
                neigh.append(e)
        if len(neigh) <= 1:
            return proposed  # 无可选邻居，保留初判
        view = [{"clc_code": e["clc_code"], "clc_name": e["clc_name"],
                 "path": e["full_path"]} for e in neigh]
        sysp = ("你是中图分类法标引专家。已初判主分类，现需在其同级与下位类目中选最贴切的具体号。"
                "只输出JSON：{\"data\":{\"main_code\":\"\"}}")
        usr = ("标题：%s\n关键词：%s\n摘要：%s\n初判：%s %s\n可选类目（同级与下位）：\n%s\n"
               "请从中选最贴切文献主题的一个 main_code（可保留初判）。") % (
            title, " ".join(keywords), abstract, proposed, proposed_entry["clc_name"],
            json.dumps(view, ensure_ascii=False))
        d = self._glm.chat_json(sysp, usr, timeout=120.0, max_tokens=200)
        d = d.get("data", d) if isinstance(d, dict) else {}
        picked = (d.get("main_code") or "").strip()
        if not picked:
            raise RuntimeError("GLM-5.2 未返回层级细化分类号")
        return picked

    def _llm_title_abstract(self, src_text: str) -> tuple:
        """LLM 标题+摘要提取（2026-09-09 用户需求：英文关键词识别参考摘要语步识别的
        LLM 主路径提取标题和摘要）。

        正则路径对未见版式不稳：标题误抓作者名（3.pdf）、摘要段误命中或缺失，
        污染关键词的挖掘信号源与展示标题。输出逐字校验（abstract 去空白 find +
        相似度 0.93 兜底；title 宽松 casefold 包含——标题常被版面拆行打散），
        校验不过返回空串由调用方回退正则结果。
        """
        import re as _re
        from difflib import SequenceMatcher
        src = str(src_text or "").strip()
        if len(src) < 60:
            return "", ""
        system = (
            "你是科技文献解析器。从给定文献前几页文本中提取论文标题和摘要。规则："
            "1) 标题是论文题目本身，不得返回作者名、单位、期刊名或日期行；"
            "2) 摘要逐字摘录（摘要/Abstract 段全文），不得改写增删；中文论文若中英摘要并存取中文摘要；"
            "3) 无标题或无摘要时对应字段输出空串。"
            "只输出 JSON：{\"title\": \"...\", \"abstract\": \"...\"}"
        )
        try:
            data = self._glm.chat_json(system, f"文献文本：\n{src[:5000]}", timeout=60.0,
                                       max_tokens=3000, temperature=0.0)
        except Exception:  # noqa: BLE001  GLM 不可用 → 回退正则
            return "", ""
        d = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
        if not isinstance(d, dict):
            return "", ""
        title = str(d.get("title") or "").strip().lstrip("#").strip()[:200]
        abstract = str(d.get("abstract") or "").strip()
        norm = lambda s: _re.sub(r"\s+", "", s)
        if abstract and len(abstract) >= 50:
            n_a, n_s = norm(abstract), norm(src)
            # 逐句核验（双栏 sort 文本按 y 坐标行列交错，整段连续匹配必失败）：
            # ≥40 字的句子逐句在源文中找，命中率 ≥70% 即通过
            probes = [norm(s) for s in _re.split(r"(?<=[.!?])\s+", abstract) if len(norm(s)) >= 40]
            if probes:
                hit = sum(1 for p in probes if p in n_s)
                if hit / len(probes) < 0.7:
                    abstract = ""
            elif n_a not in n_s and n_a[:300] not in n_s:
                if SequenceMatcher(None, n_a[:1500], n_s).find_longest_match(
                        0, len(n_a[:1500]), 0, len(n_s)).size / max(1, min(len(n_a), 1500)) < 0.93:
                    abstract = ""
        else:
            abstract = ""
        if title and norm(title).casefold() not in norm(src).casefold():
            title = ""
        return title, abstract

    def _execute_keyword(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """关键词识别管线：确定性短语候选（高召回）→ 特征打分 → LLM 选/精炼 → 后置清洗。

        设计（与训练产物解耦，数据多了只重训模型文件，管线不动）：
        - 候选挖掘（keyword_phrase_miner）无 LLM、可复现，实测对 author keyword 召回 ~100%；
        - 特征权重 + few-shot 从 kw_zh_model.json 加载（训练脚本生成），缺失则用默认；
        - LLM 从 top 候选里选最主题词、可精炼措辞、可补概念词；
        - 后置引擎去重/停用词/长度/排序。
        """
        from pathlib import Path
        is_en = getattr(rule, "lang", "") == "en"
        if is_en:
            from training.keyword_phrase_miner_en import mine_candidates, score_candidates
        else:
            from training.keyword_phrase_miner import mine_candidates, score_candidates

        result = SemanticResult(code=code, name=fp.name)
        user_payload = self._build_user_payload(fp.input_type, request)
        text = user_payload.get("text", "")
        if not text:
            raise ValueError("关键词识别需提供 text 字段（文献片段）")

        # 全文输入支持：文件路径或 mineru markdown 全文 → 截断 5000 字直送 LLM
        # （LLM 优先版：从全文提取关键词，不只看摘要）；同时作为短语挖掘源提高召回
        full_text = None
        if text and os.path.exists(text) and text.lower().endswith(('.pdf', '.md')):
            from infrastructure.document_parser.mineru_reader import process_to_text
            doc = process_to_text(text)
            full_text = doc.get("full_text", "") or ""
        if not full_text and self._looks_like_full_document(text):
            full_text = text

        # 摘要优先（2026-09-02 召回修复）：论文/基金/专利的关键词源自标题+摘要；
        # 此前全文路径把前 8000 字当"摘要"、挖掘面向全文，全文高频泛化术语（方法名/
        # 实验对象/章节主题词）挤掉摘要级主题词，实测对作者关键词召回仅 ~0.3。
        # 现改为：结构化提取摘要段（与摘要语步识别工具同款 DocumentParser 规则），
        # 有摘要 → 挖掘与 LLM 面向 标题+摘要；无摘要（科技报告等）→ 保持全文路径。
        from infrastructure.document_parser.document_parser import extract_abstract_text
        paste_full_text = None  # 无##标题的粘贴全文/light解析走结构化摘要时，字面校验仍面向全文
        if full_text:
            # 剥离论文已列作者关键词段落：默认不把作者关键词喂给 LLM，促其基于内容自主生成
            full_text = self._strip_author_keywords(full_text)
            # 提取论文题目：跳过期刊名/出版信息行（MinerU 常把《xx》网络首发论文标成首个 #）
            title = self._extract_paper_title(full_text)
            abstract = extract_abstract_text(full_text, "zh_paper" if not is_en else "en_paper")
            # 摘要过短视为误命中（正文中孤立的"摘要"字样），回退全文路径
            if len(abstract.strip()) >= 50:
                mine_source = ((title or "") + "\n" + abstract).strip()
            else:
                mine_source = full_text      # 无摘要段：全文挖掘不截断（科技报告长正文也参与召回）
                abstract = full_text[:8000]  # LLM 上下文截断（与全文提取口径一致 8000）
        elif is_en:
            # 纯文本输入：先试结构化摘要段（粘贴的论文首页/含 Abstract 的报告），
            # 无摘要才整段作挖掘源（无摘要科技报告），并尝试从首部提取标题
            _stripped = self._strip_author_keywords(text)
            title = self._extract_paper_title(_stripped) or ""
            abstract = extract_abstract_text(_stripped, "en_paper")
            if len(abstract.strip()) >= 50:
                mine_source = ((title or "") + "\n" + abstract).strip()
                paste_full_text = _stripped
            else:
                mine_source = _stripped
                abstract = mine_source[:8000]
        else:
            # 中文纯文本：长文本（粘贴全文/双栏 light 解析无 ## 标题）先试结构化摘要段——
            # 双栏 PDF 走内置分栏读取后没有 markdown 标题，_looks_like_full_document 判不出，
            # 若不在此探测摘要，双栏论文会退回整段挖掘、丢失摘要优先
            _stripped = self._strip_author_keywords(text)
            _abstract = extract_abstract_text(_stripped, "zh_paper")
            if len(text) >= 2000 and len(_abstract.strip()) >= 50:
                title = self._extract_paper_title(_stripped) or ""
                abstract = _abstract
                mine_source = ((title or "") + "\n" + abstract).strip()
                paste_full_text = _stripped
            else:
                title, abstract = self._split_title_abstract(text)
                abstract = self._strip_author_keywords(abstract)
                mine_source = (title or "") + (abstract or "")
        # 英文信号源 LLM 升级（2026-09-09 用户需求，参考摘要语步识别的 LLM 主路径；
        # 统一收口在分支级联之后——full_text/纯文本两路的正则标题摘要都可能误抓：
        # 3.pdf 标题成了作者名 "Lan Yang1, Honggang Zhang1"、6.pdf 成了摘要首句）。
        # LLM 逐字校验后覆盖（摘要逐句核验双栏交错友好，标题 casefold 包含独立生效），
        # 失败回退正则结果。中文关键词实测良好，保持原路径不动。
        if is_en:
            _ta_src = (full_text or paste_full_text or text or "")[:5000]
            _llm_title, _llm_abstract = self._llm_title_abstract(_ta_src)
            if _llm_abstract and len(_llm_abstract) >= 50:
                abstract = _llm_abstract
                if _llm_title:
                    title = _llm_title
                mine_source = ((title or "") + "\n" + abstract).strip()
            elif _llm_title:
                title = _llm_title
        title = (title or "").lstrip('#').strip()
        # 原词校验/排序定位面向全文（不限定摘要段；关键词可出自全文任意位置）——
        # 摘要优先只收窄"挖掘与 LLM 的信号源"，不收窄字面校验范围
        searchable_text = full_text or paste_full_text or mine_source

        # 1. 确定性候选 + 特征打分
        model = self._load_keyword_model(fp)
        # 用户上传的领域术语库（en-keyword 的 domain_terminology_library 资源）合并进
        # 归一索引：资源文件每次请求现读，届时上传/替换即直接生效（无需重启或改模型文件）。
        # 条目格式 [{canonical: 标准术语, variants: [变体/缩写/同义词]}]，按 canonical 去重。
        _user_lib_cf: set = set()   # 用户库簇内全部字面形式(casefold)：命中词标 terminology_source
        _user_lib_name = ""
        _lib_hits: list = []        # 库内字面命中形式（注入候选池头部）
        if is_en:
            _lib_res = ((request.params or {}).get("resolved_resources") or {}).get("domain_terminology_library")
            _lib_uri = str((_lib_res or {}).get("storage_uri") or "")
            if _lib_uri:
                from pathlib import Path as _P
                _lib_path = _P(_lib_uri.removeprefix("project://")) if _lib_uri.startswith("project://") else _P(_lib_uri)
                if _lib_path.is_file():
                    try:
                        # 优先取归一化行（上传/运行预检已缓存，canonical→term 别名已折算），
                        # 未缓存再裸读 JSON。行内 canonical 或 term 任一存在即成簇：
                        # variants 缺失视为空簇（术语字面命中仍可注入候选池）。
                        from infrastructure.resources.normalize import normalized_rows_for as _rows_for
                        _lib_rows = _rows_for(_lib_path)
                        if _lib_rows is None:
                            import json as _json2
                            _lib = _json2.loads(_lib_path.read_text(encoding="utf-8"))
                            _lib_rows = _lib if isinstance(_lib, list) else []
                        _extra = []
                        for _e in _lib_rows:
                            if not isinstance(_e, dict):
                                continue
                            _canon = str(_e.get("canonical") or _e.get("term") or "").strip()
                            if not _canon:
                                continue
                            _vars = [str(v).strip() for v in (_e.get("variants") or []) if str(v).strip()]
                            _extra.append({"canonical": _canon, "variants": _vars})
                        if _extra:
                            _seen = {str(c.get("canonical")) for c in model.get("domain_terms") or []}
                            model["domain_terms"] = list(model.get("domain_terms") or []) + [
                                e for e in _extra if e["canonical"] not in _seen]
                            # 库命中标记素材：canonical+全部变体（casefold），
                            # 命中词的 terminology_source = {type:external, library_name}
                            _user_lib_cf = {e["canonical"].casefold() for e in _extra} | {
                                v.casefold() for e in _extra for v in e["variants"]}
                            _user_lib_name = str(_lib_res.get("name") or "")

                    except Exception:  # noqa: BLE001 - 术语库损坏不影响主流程
                        logger.warning("领域术语库资源解析失败：%s", _lib_path.name, exc_info=True)
        # zh 也面向全文挖掘（与 en 一致）：仅看前 8000 字会埋掉低频但全文高频的核心术语
        # （如 ch4 反应谱全文 23 次、前 8000 仅 2-4 次）。挖掘器内置垃圾过滤+子串去膨胀。
        cands = mine_candidates(mine_source) if is_en else mine_candidates(title, mine_source)
        cands = score_candidates(cands, model.get("feature_weights", {}))
        # 候选池扩容（2026-09-09 miss 归因：燃气泄漏/遗传模拟退火/深度学习等
        # 正文领域复合词从未进池，占中文 miss 约一半）：标题+摘要挖掘 ∪ 全文挖掘
        # top20（特征分排序）。2026-09-02 全文挖掘召回 0.3 的教训是"全文高频泛化
        # 词挤掉摘要词"——现有 fitness 轮 + 词表防线双兜底，泛意词进池也会被拦。
        if searchable_text and len(searchable_text) > len(mine_source) + 200:
            try:
                _full_c = (mine_candidates(searchable_text) if is_en
                           else mine_candidates(title, searchable_text))
                _full_c = score_candidates(_full_c, model.get("feature_weights", {}))
                _lx_en, _lx_zh = _keyword_lexicon("en"), _keyword_lexicon("zh")
                _seen = {c["phrase"] for c in cands}
                _extra = []
                for _c in _full_c:
                    _ph = str(_c.get("phrase") or "")
                    if (not _ph or _ph in _seen or len(_ph) > 30
                            or _ph.casefold() in _lx_en["block"] or _ph in _lx_zh["block"]):
                        continue
                    _extra.append(_c)
                    if len(_extra) >= 20:
                        break
                cands = list(cands) + _extra
            except Exception:  # noqa: BLE001  全文挖掘失败不影响主池
                pass
        top_cands = [c["phrase"] for c in cands[:40]]
        # 归一索引：domain_terms 簇内 variant(cf) -> {canonical, variants_cf}，
        # 供 preserve_original_form 归一匹配 + normalized_term 填 canonical
        # （仅英文；domain_terms 空时降级原逻辑，中文 is_en=False 不构建）
        _norm_index = {}
        if is_en and model.get("domain_terms"):
            for _c in model["domain_terms"]:
                _canon = _c.get("canonical", "")
                _vcfs = [v.casefold() for v in _c.get("variants", [])]
                for _vcf in _vcfs:
                    _norm_index[_vcf] = {"canonical": _canon, "variants_cf": _vcfs}
        params = request.params or {}
        preserve_order = bool(params.get("preserve_order", True))
        preserve_original_form = bool(params.get("preserve_original_form", True))
        custom_dictionary = params.get("custom_dictionary") or {}
        custom_terms = []
        if isinstance(custom_dictionary, dict):
            for value in custom_dictionary.get("terms") or []:
                if isinstance(value, dict):
                    term = str(value.get("term") or "").strip()
                    term_id = value.get("id")
                    term_weight = value.get("weight")
                else:
                    term = str(value or "").strip()
                    term_id = None
                    term_weight = None
                if not term:
                    continue
                # 拆分：用户可能一行写多个词（"气源压力、模型迎角、阀门开度"）
                # → 按中英文分隔符拆开逐个匹配，不再整串当一个词条
                _split_parts = [p.strip() for p in re.split(r"[、，,;；/|\s]+", term) if len(p.strip()) >= 2]
                if len(_split_parts) > 1:
                    for part in _split_parts:
                        custom_terms.append({"term": part, "id": term_id, "weight": term_weight})
                else:
                    custom_terms.append({"term": term, "id": term_id, "weight": term_weight})
            matching_dictionary_terms = [
                value["term"] for value in custom_terms
                if value["term"].casefold() in searchable_text.casefold()
            ]
            top_cands = list(dict.fromkeys(matching_dictionary_terms + top_cands))[:40]

        # 领域术语库增强(en-keyword)：库内术语/变体字面出现在原文的，注入候选池头部——
        # 缩写/短变体常被短语挖掘漏掉，进候选后 LLM 即可按主题相关性选出；选出的变体
        # 再由归一索引映射回标准术语(normalized_term)。用户上传/替换术语库即时生效。
        if is_en and model.get("domain_terms"):
            _lib_hits = []
            for _c in model["domain_terms"]:
                for _f in [str(_c.get("canonical") or "")] + [str(v) for v in _c.get("variants") or []]:
                    _f = _f.strip()
                    if _f and self._ws_substr_find(searchable_text.casefold(), _f.casefold()) >= 0:
                        _lib_hits.append(_f)
                        break  # 每簇注入一个命中形式（canonical 优先，否则首个命中的变体）
            if _lib_hits:
                top_cands = list(dict.fromkeys(_lib_hits + top_cands))[:40]
        # 用户术语库命中的形式单列传给选词 LLM：要求作为独立关键词原样输出——
        # 缩写若被嵌进更长短语（"CNN autoencoder"）会错过归一索引的精确匹配，
        # 指令引导输出裸缩写（"CNN"）才能触发 normalized_term 折算标准术语
        _lib_prompt_terms = [f for f in (_lib_hits or []) if f.casefold() in _user_lib_cf][:10]

        # 2. LLM 选/精炼（带 few-shot + 候选）
        system_prompt = self._system_prompt(rule, request)
        _min_kw = max(1, min(50, int(params.get("min_keywords", 5) or 5)))
        _max_kw = max(_min_kw, min(50, int((request.params or {}).get("max_keywords", 8) or 8)))
        # 正文语境实验（2026-09-09 用户提议，A/B 开关）：KEYWORD_BODY_CONTEXT=1 时
        # 选词 LLM 额外读全文前 5000 字——正文含研究对象/方法/结论/创新点（规范亦要求
        # "从正文核心内容提炼"），C 类 gold（需通读全文拟词）召回 0.583 为三层最低。
        # 频率挖掘仍面向标题+摘要不动（2026-09-02 全文挖掘召回 0.3 的教训只适用于
        # 词频统计，LLM 有语义判断力可按指令以标题摘要为主）。
        _body_ctx = os.getenv("KEYWORD_BODY_CONTEXT", "") == "1"
        _body_excerpt = (full_text or paste_full_text or text or "")[:5000] if _body_ctx else ""
        user_prompt = self._render_keyword_user_prompt(
            title, abstract, top_cands, model.get("few_shot", []), lang=getattr(rule, "lang", ""),
            preserve_original_form=preserve_original_form, count_min=_min_kw, count_max=_max_kw,
            body_excerpt=_body_excerpt, library_terms=_lib_prompt_terms)
        # 低温采样：关键词选词要稳定可复现（高温导致同文档跑次间 0.8↔0.2 波动），与 fitness 评分轮一致
        # A/B 开关（2026-09-09）：KEYWORD_MERGED_SELECT=1 时选词调用同时输出每词的
        # prob(内容适配度)+scene(应用场景)，跳过独立的 fitness/scenes 轮（省 ~4s/篇）。
        # 合并输出缺 prob（LLM 未按 schema）则回退独立轮，保证质量不降级。
        _merge_select = os.getenv("KEYWORD_MERGED_SELECT", "") == "1"
        if _merge_select:
            user_prompt += (
                "\nAdditionally, for EACH selected keyword also output two fields:\n"
                "- prob: 0-1 probability that it is a core topic term of THIS document. "
                "Judge each keyword independently (no mutual comparison, no mechanical "
                "decrement by order); generic function words get low scores even if frequent; "
                "core terms get high scores even if they appear only once.\n"
                "- scene: 该术语在此文献中的应用场景中文描述（用于中图法类目锚定学科，"
                "必须带具体应用场景，不能只重复关键词字面）。\n"
                "Return JSON {data:[{keyword,weight,type,prob,scene}]}"
            )
        data = self._glm.chat_json(system_prompt, user_prompt, timeout=60.0,
                                   max_tokens=2400 if _merge_select else None,
                                   temperature=0.1)
        raw_kw = data.get("data", data) if isinstance(data, dict) else []
        if not isinstance(raw_kw, list):
            raise RuntimeError("GLM-5.2 未返回有效关键词列表")
        _merged_prob: dict = {}
        _merged_scene: dict = {}
        if _merge_select:
            for _it in raw_kw:
                if isinstance(_it, dict):
                    _k = str(_it.get("keyword") or "").strip()
                    if not _k:
                        continue
                    try:
                        _merged_prob[_k] = max(0.0, min(1.0, float(_it.get("prob"))))
                    except (TypeError, ValueError):
                        pass
                    _s = str(_it.get("scene") or "").strip()
                    if _s:
                        _merged_scene[_k] = _s

        # 3. 后置清洗（强制字面原词 + 包含去重 + 停用词）
        stopwords = set(rule.dictionaries.get("stopwords", []))
        cleaned, dropped = self._clean_keywords(raw_kw, stopwords, searchable_text, lang=getattr(rule, "lang", ""))

        # preserve_original_form=true：强制保留原文词形，丢弃 LLM 概括/改写出的非字面词。
        # 校验面向全文（searchable_text），故全文任意位置出现的术语都能保留，不限于摘要段。
        if preserve_original_form:
            _searchable_cf = searchable_text.casefold()
            _literal = []
            for _item in cleaned:
                _kw_cf = _item["keyword"].casefold()
                # 1. 精确子串校验（空白不敏感：双栏/分栏读取在词内插换行如"反应\n谱"，
                #    LLM 还原成"反应谱"后字面 `in` 会误判非原文而丢词，故用 _ws_substr_find）
                if self._ws_substr_find(_searchable_cf, _kw_cf) >= 0:
                    _literal.append(_item)
                    continue
                # 2. 归一匹配：命中术语库簇则簇内任一 variant 在原文出现即保留
                _hit = _norm_index.get(_kw_cf)
                if _hit and any(self._ws_substr_find(_searchable_cf, _vcf) >= 0 for _vcf in _hit["variants_cf"]):
                    _literal.append(_item)
                else:
                    dropped.append({"keyword": _item["keyword"], "reason": "非原文原词/簇内无原词(preserve_original_form)"})
            cleaned = _literal

        # 用算法特征分数（真实）替换 LLM 机械递减的 weight 作置信度。
        # LLM 倾向按排名给 1.0/0.9/0.8... 机械递减，不代表真实主题代表性；
        # score_candidates 基于 标题命中/词频/位置/长度 算特征分，更可信。
        _cand_scores = {c["phrase"]: c.get("score", 0.0) for c in cands} if cands else {}

        def _alg_conf(kw, llm_w):
            # 特征权重和=1.0，score 已在 [0,1]，直接作绝对置信度；
            # 不再除 max 相对归一化（曾把非最高分词系统性压到 0.2-0.3，
            # 即便该术语确为核心——相对排名被误当绝对置信度）。
            for _ph, _sc in _cand_scores.items():
                if kw == _ph or kw in _ph or _ph in kw:
                    return round(min(_sc, 0.95), 3)
            # 不在算法候选（LLM 自行摘取的原词）：用 LLM weight 封顶 0.85 防虚高
            return round(min(float(llm_w or 0.5), 0.85), 3)

        for _item in cleaned:
            _item["weight"] = _alg_conf(_item["keyword"], _item.get("weight"))

        # 两轮 LLM（用户方案：第一轮 LLM 提取关键词+类型，第二轮 LLM 判"是否符合本文内容"=置信度）：
        #   fitness = LLM 对每个候选词独立判"是否本文核心主题术语"概率(0-1)，即内容适配度，
        #     直接作为该关键词的置信度（不再与统计分融合——统计分被频次主导会压低低频核心
        #     术语、抬高高频功能词，与"主题代表性"相悖，是 0.183 误导低分根源）。
        #   stat_conf（词频/位置/标题命中，_alg_conf 绝对分）仅保留作"fitness 同分时的平局
        #     打破"，不进入置信度。逐词独立送各自上下文（不拼全候选防 term 信号淹没）；
        #     要绝对概率非排名（防机械递减 1.0/0.9/0.8）；不带同任务 few-shot（防泄漏）。
        _merged_scenes: dict = {}
        if cleaned:
            # 合并模式（A/B）：选词轮已带出 prob/scene 且覆盖全部入选词 → 跳过独立评分轮；
            # 覆盖不全（LLM 未按 schema 输出）→ 回退原两轮路径，质量不降级
            _use_merged = _merge_select and all(c["keyword"] in _merged_prob for c in cleaned)
            if _use_merged:
                _sem_scores = {c["keyword"]: _merged_prob.get(c["keyword"], 0.5) for c in cleaned}
                _merged_scenes = {c["keyword"]: _merged_scene[c["keyword"]]
                                  for c in cleaned if c["keyword"] in _merged_scene}
            else:
                _sem_ctxs = {c["keyword"]: self._term_context(c["keyword"], searchable_text) for c in cleaned}
                _sem_scores, _merged_scenes = self._llm_keyword_scores_and_scenes(
                    [c["keyword"] for c in cleaned], _sem_ctxs, title, abstract)
            for _item in cleaned:
                _stat = float(_item.get("weight") or 0)                          # 统计显著性(仅平局打破)
                _sem = _sem_scores.get(_item["keyword"])
                _fit = _sem if _sem is not None else 0.5
                _item["stat_conf"] = round(_stat, 3)
                _item["fitness"] = round(_fit, 3)                               # 内容适配度=置信度

        # 用户词典属于算法输入，在后端候选合并阶段生效，而不是由 Vue 或输出适配器伪造。
        # 权重增量完全按用户设置——设多少加多少，没设就不加（2026-09-15 用户反馈：设0.08就该统一+0.08）
        _raw_boost = float(custom_dictionary.get("weight_boost", 0) or 0) if isinstance(custom_dictionary, dict) else 0
        boost = min(0.5, _raw_boost)
        matched_terms = []
        by_term = {item["keyword"].casefold(): item for item in cleaned}
        searchable = searchable_text.casefold()
        for dictionary_term in custom_terms:
            term = dictionary_term["term"]
            if term.casefold() not in searchable:
                continue
            current = by_term.get(term.casefold())
            if current is None:
                # 包含匹配：识别关键词包含词典词条（如「急性心肌梗死」⊃「心肌梗死」）
                # 时标记该关键词命中，而不是把词典词条作为新词重复注入结果列表。
                current = next(
                    (item for item in cleaned
                     if term.casefold() in str(item["keyword"]).casefold()),
                    None,
                )
            if current is None:
                base_weight = _number_or_default(dictionary_term.get("weight"), 0.5)
                new_weight = min(1.0, base_weight + boost)
                current = {"keyword": term, "weight": new_weight, "weight_change": round(new_weight - base_weight, 4)}
                cleaned.append(current)
                by_term[term.casefold()] = current
            else:
                old_weight = _number_or_default(current.get("weight"), 0.5)
                new_weight = min(1.0, old_weight + boost)
                current["weight"] = new_weight
                current["weight_change"] = round(new_weight - old_weight, 4)
            current["custom_dictionary_hit"] = True
            current["dictionary_term_id"] = dictionary_term.get("id")
            matched_terms.append(dictionary_term)

        # 第二轮选词（用户方案"两个置信度"）：
        #   门槛过滤：类内 fitness<_FITNESS_MIN 的候选剔除（"是否符合本文内容"置信度过低要去掉
        #     不要）——含被统计分虚高但不适配本文的词。
        #   每类取 fitness 最高 1 个（"最后只能要置信度最高的一个"）；fitness 同分时以 stat_conf
        #     （统计显著性）打破平局。整类无人过门槛则不留该类。
        # custom_terms（用户词典，无 fitness、type=None）不参与此筛选，全保留走原逻辑。
        _FITNESS_MIN = 0.40
        _DYNAMIC_GAP = 0.15   # 动态1-or-2：次优 fitness 与最优差距≤此值才留第二个。固定N=1过严
                              #   (ch8四作者关键词仅命中1个)、N=2会留凑数的弱次优；动态则强簇留2、
                              #   弱尾留1。受 max_keywords=8 兜底防爆增。
        if any(c.get("type") for c in cleaned):
            _by_t = {}
            for c in cleaned:
                _by_t.setdefault(c.get("type"), []).append(c)
            _kept = []
            for _t, _grp in _by_t.items():
                if _t is None:
                    _kept.extend(_grp)
                    continue
                # 用户词典命中的词豁免类内筛选（用户显式给的术语必须保留，
                # 不能被"每类只留最优"挤掉——否则词典命中了也不出现在结果里）
                _dict_hits = [c for c in _grp if c.get("custom_dictionary_hit")]
                _rest = [c for c in _grp if not c.get("custom_dictionary_hit")]
                _fit = [c for c in _rest if c.get("fitness", 0.5) >= _FITNESS_MIN]   # 门槛:不适配本文剔除
                if _fit:
                    _fit.sort(key=lambda x: (x.get("fitness", 0), x.get("stat_conf", 0)), reverse=True)
                    _kept.append(_fit[0])                                          # 类内最优必留
                    if (len(_fit) >= 2
                            and _fit[1].get("fitness", 0) >= _fit[0].get("fitness", 0) - _DYNAMIC_GAP):
                        _kept.append(_fit[1])                                      # 次优贴近最优才留(动态1或2)
                _kept.extend(_dict_hits)                                           # 词典命中词全保留
            cleaned = _kept
        _lex_en = _keyword_lexicon("en")
        _lex_zh = _keyword_lexicon("zh")
        # 数量下限补齐（min_keywords 接线）：LLM 输出不足下限时（如只给 4 个），
        # 从未入选的高分候选按特征分补齐——字面须在原文（不引入幻觉词）、非停用词
        minimum_keywords = max(1, min(50, int((request.params or {}).get("min_keywords", 5) or 5)))
        if len(cleaned) < minimum_keywords:
            _have = {str(c.get("keyword", "")).casefold() for c in cleaned}
            for _c in cands:
                if len(cleaned) >= minimum_keywords:
                    break
                _ph = str(_c.get("phrase", "")).strip()
                if not _ph or len(_ph) > 30 or _ph.casefold() in _have:
                    continue
                if _ph in stopwords:
                    continue
                # 虚词/短碎片防线（与 _clean_keywords 同口径，2026-09-09 "th" 案例：
                # 补齐路径此前只查 yaml 停用词，闭类词与 1~2 字母小写碎片可漏入）
                if _ph.casefold() in _lex_en["block"]:
                    continue
                if _ph in _lex_zh["block"]:
                    continue
                if is_en:
                    if len(_ph) <= 2 and not _ph.isupper():
                        continue
                elif len(_ph) < 2:
                    continue
                if self._ws_substr_find(searchable_text.casefold(), _ph.casefold()) < 0:
                    continue
                _have.add(_ph.casefold())
                cleaned.append({"keyword": _ph, "weight": round(float(_c.get("score", 0) or 0), 3)})
        # 最终置信度=内容适配度 fitness；用户词典 boost 经 weight_change 叠加
        #（custom_terms 无 fitness，保留 boost 后的 weight 不变）
        # 词典命中词封顶 1.0（用户显式收录=确定性知识）；非词典词封顶 0.95（防LLM过度自信）
        for _item in cleaned:
            if "fitness" in _item:
                _cap = 1.0 if _item.get("custom_dictionary_hit") else 0.95
                _item["weight"] = round(min(_item["fitness"] + _item.get("weight_change", 0), _cap), 3)
                # 用户词典命中的词置信度下限 0.75：用户显式收录的术语重要性有保障，
                # 不因 LLM 误判"内容适配度"而输出刺眼低分
                if _item.get("custom_dictionary_hit"):
                    _item["weight"] = max(_item["weight"], 0.75)

        # 排序：preserve_order=true 时置信度按 0.05 分档降序为主，档内按摘要出现顺序（稳定）；
        #       false 时纯置信度降序。
        if preserve_order:
            _searchable_pos = searchable_text.casefold()

            def _appear_pos(item):
                p = _searchable_pos.find(item["keyword"].casefold())
                return p if p >= 0 else len(_searchable_pos)

            cleaned.sort(key=lambda item: (-int(_number_or_default(item.get("weight"), 0) * 20 + 1e-9), _appear_pos(item)))
        else:
            cleaned.sort(key=lambda item: _number_or_default(item.get("weight"), 0), reverse=True)
        maximum_keywords = max(1, min(50, int((request.params or {}).get("max_keywords", 8) or 8)))
        # 数量上限只约束模型候选：词典命中词是用户显式收录的术语，全部保留
        # （否则命中数被 max_keywords 截断，词典形同虚设）。
        _dict_kept = [item for item in cleaned if item.get("custom_dictionary_hit")]
        if len(_dict_kept) > maximum_keywords:
            cleaned = _dict_kept
        else:
            cleaned = _dict_kept + [item for item in cleaned if not item.get("custom_dictionary_hit")][:maximum_keywords - len(_dict_kept)]

        # 英文关键词：批量场景重写 + CLC 映射并发（降时延：N 词串行 rerank→并发 max）
        _en_clc_map = {}
        # 用户上传的分类标准映射表(显式 term→clc_code 条目)——按数量分级:
        # ① 显式命中(任意规模):term 完全匹配 → 确定性直接覆盖(用户给了明确映射
        #    就不该再让检索猜)
        # ② 大表(>50 条):构建向量索引(外部知识库),关键词近邻检索用户术语,
        #    相似度达标即用该条映射(中图分类资源同款分级设计)
        # ③ 小表(≤50 条):维持提示词注入(_resource_context 原路径),软影响
        _user_map_index = {}
        _user_map_vecs = None
        _user_map_rows = []
        _resolved = (request.params or {}).get("resolved_resources") or {}
        _map_res = _resolved.get("classification_standard_mapping_table") if isinstance(_resolved, dict) else None
        if isinstance(_map_res, dict) and is_en:
            from pathlib import Path as _Path
            from config.settings import settings as _st
            _uri = str(_map_res.get("storage_uri") or "")
            _mp = _st.PROJECT_ROOT / _uri.removeprefix("project://") if _uri.startswith("project://") else _Path(_uri)
            if _mp.is_file():
                try:
                    from infrastructure.resources.normalize import normalized_rows_for as _norm_rows
                    _raw_rows = _norm_rows(_mp)
                    if _raw_rows is None:
                        _mdata = json.loads(_mp.read_text(encoding="utf-8-sig", errors="replace"))
                        _raw_rows = (_mdata.get("entries") or _mdata.get("mappings") or []) \
                            if isinstance(_mdata, dict) else (_mdata if isinstance(_mdata, list) else [])
                    _rows = [e for e in _raw_rows
                             if isinstance(e, dict) and e.get("term") and e.get("clc_code")]
                    for _e in _rows:
                        _user_map_index[str(_e["term"]).casefold()] = {
                            "system": "CLC", "code": str(_e["clc_code"]),
                            "label": str(_e.get("clc_name") or _e.get("name") or ""),
                            "classification_path": _e.get("classification_path") or [],
                            "confidence": 1.0,
                            "mapping_engine": "user_resource_direct",
                            "dense_score": 1.0, "scene": "用户映射表直接覆盖",
                        }
                    if len(_rows) > 50:
                        # 大表:用户术语建 m3 向量索引(按资源ID缓存,避免重复编码)
                        _cache_key = f"kwmap_{_map_res.get('id')}_{_map_res.get('content_hash') or len(_rows)}"
                        _cached = getattr(SemanticApplicationService, "_user_map_cache", None) or {}
                        if _cache_key in _cached:
                            _user_map_vecs, _user_map_rows = _cached[_cache_key]
                        else:
                            from infrastructure.rag.m3_encoder import m3_encoder as _m3
                            import numpy as _np
                            _terms = [str(e["term"]) for e in _rows]
                            _user_map_vecs = _m3.encode(_terms)
                            _user_map_rows = _rows
                            if len(_cached) > 4:
                                _cached.clear()
                            _cached[_cache_key] = (_user_map_vecs, _user_map_rows)
                            SemanticApplicationService._user_map_cache = _cached
                except Exception:  # noqa: BLE001
                    pass
        if is_en and cleaned:
            from concurrent.futures import ThreadPoolExecutor
            _en_terms = [c["keyword"] for c in cleaned if c["keyword"].casefold() not in _user_map_index]
            _en_ctxs = {c["keyword"]: self._term_context(c["keyword"], searchable_text) for c in cleaned}
            _en_scenes = {k: v for k, v in _merged_scenes.items() if k in _en_ctxs}
            _missing = [t for t in _en_terms if t not in _en_scenes]
            if _missing:
                _en_scenes.update(self._llm_scene_rewrite_batch(_missing, _en_ctxs, title))
            from infrastructure.rag.clc_retriever import clc_retriever as _clc_r
            _en_clc_map: Dict[str, Any] = {}
            _rerank_jobs: list = []
            _cand_by_term: Dict[str, list] = {}
            _en_scenes_having = [_kw for _kw in _en_terms if _en_scenes.get(_kw)]
            _q_en = list(_en_terms)
            _q_zh = [_en_scenes[_kw] for _kw in _en_scenes_having]
            _en_results = _clc_r.retrieve_batch(_q_en, k=8, cross_lingual=True) if _q_en else []
            _zh_results = _clc_r.retrieve_batch(_q_zh, k=8, cross_lingual=False) if _q_zh else []
            _zh_by_term = dict(zip(_en_scenes_having, _zh_results))
            for _ki, _kw in enumerate(_en_terms):
                try:
                    _ctx = _en_ctxs.get(_kw, "")
                    _scene = _en_scenes.get(_kw, "")
                    _cands = list(_en_results[_ki] or [])
                    _cands += list(_zh_by_term.get(_kw) or [])
                    _best: Dict[str, Any] = {}
                    for _c in _cands:
                        _code = str(_c.get("clc_code") or "")
                        if not _code:
                            continue
                        _sc = float(_c.get("score") or 0)
                        if _code not in _best or _sc > float(_best[_code].get("score") or 0):
                            _best[_code] = _c
                    _uniq = sorted(_best.values(), key=lambda x: -float(x.get("score") or 0))[:6]
                    if not _uniq or float(_uniq[0].get("score") or 0) < 0.40:
                        continue
                    _cand_by_term[_kw] = _uniq
                    _rerank_jobs.append({"term": _kw, "context": _ctx + (" [场景]" + _scene if _scene else ""), "candidates": _uniq})
                except Exception:  # noqa: BLE001
                    continue
            _batch_rerank = self._llm_rerank_clc_batch(_rerank_jobs)
            for _kw, _uniq in _cand_by_term.items():
                _chosen, _conf = _batch_rerank.get(_kw, (-1, 0.0))
                if _chosen < 0 or _conf < 0.45:
                    continue
                _c = _uniq[_chosen] if _chosen < len(_uniq) else None
                if _c is None:
                    continue
                _en_clc_map[_kw] = {
                    "system": "CLC",
                    "code": _c.get("clc_code"),
                    "label": _c.get("clc_name"),
                    "classification_path": _c.get("path_names") or [],
                    "confidence": round(min(1.0, _conf), 4),
                    "mapping_engine": "clc_retriever+batch_rerank",
                    "dense_score": round(float(_c.get("score") or 0), 4),
                    "scene": _en_scenes.get(_kw, ""),
                }
            for _uk, _uv in _user_map_index.items():
                _en_clc_map[_uk] = _uv
            # 大表向量索引:剩余词近邻匹配用户术语(≥0.62 视为同术语)
            if _user_map_vecs is not None and _user_map_vecs.size:
                import numpy as _np2
                _remain = [c["keyword"] for c in cleaned
                           if c["keyword"].casefold() not in _user_map_index]
                if _remain:
                    from infrastructure.rag.m3_encoder import m3_encoder as _m3e
                    _qv = _m3e.encode(_remain)
                    _sims = _qv @ _user_map_vecs.T
                    for _ri, _kw in enumerate(_remain):
                        _best = int(_np2.argmax(_sims[_ri]))
                        if float(_sims[_ri][_best]) >= 0.62:
                            _e = _user_map_rows[_best]
                            _en_clc_map[_kw] = {
                                "system": "CLC", "code": str(_e["clc_code"]),
                                "label": str(_e.get("clc_name") or _e.get("name") or ""),
                                "classification_path": _e.get("classification_path") or [],
                                "confidence": round(float(_sims[_ri][_best]), 4),
                                "mapping_engine": "user_resource_index",
                                "dense_score": round(float(_sims[_ri][_best]), 4),
                                "scene": "用户映射表向量索引近邻",
                            }
            # 归一反查兜底（2026-09-15 用户反馈：CNN 归一成 convolutional neural
            # network 后仍显示未映射——缩写本身检索不到，但其标准术语检索得到）：
            # 对未映射且可归一的关键词，用标准术语补一轮内置检索。双查询：裸 canon
            # （英文跨语言）+ canon×变体词中文场景混合——实测裸英文术语召回差
            # （reinforcement learning→医学记忆类），中英混合能把学科词带进查询
            # （TP181 自动推理、机器学习 0.58）显著改善召回
            if _norm_index:
                _canon_of = {}
                _pairs = []  # (canon, query)
                for _c in cleaned:
                    _k = _c["keyword"]
                    if _en_clc_map.get(_k) or _en_clc_map.get(_k.casefold()):
                        continue
                    _h = _norm_index.get(_k.casefold())
                    if _h:
                        _canon = _h["canonical"]
                        if _canon not in _canon_of.values():
                            _canon_of[_k] = _canon
                            _pairs.append((_canon, _canon))
                            _scene = str(_en_scenes.get(_k) or "").strip()
                            if _scene:
                                _pairs.append((_canon, f"{_canon} {_scene}"))
                if _pairs:
                    _canon_hits = _clc_r.retrieve_batch([q for _, q in _pairs], k=8, cross_lingual=True)
                    _cands_by_canon: Dict[str, list] = {}
                    for (_canon, _q), _hs in zip(_pairs, _canon_hits):
                        _cands_by_canon.setdefault(_canon, []).extend(_hs or [])
                    _canon_cands, _canon_jobs = {}, []
                    for _canon, _pool in _cands_by_canon.items():
                        _best: Dict[str, Any] = {}
                        for _c in _pool:
                            _code = str(_c.get("clc_code") or "")
                            if not _code:
                                continue
                            _sc = float(_c.get("score") or 0)
                            if _code not in _best or _sc > float(_best[_code].get("score") or 0):
                                _best[_code] = _c
                        _uniq = sorted(_best.values(), key=lambda x: -float(x.get("score") or 0))[:6]
                        if not _uniq or float(_uniq[0].get("score") or 0) < 0.40:
                            continue
                        _canon_cands[_canon] = _uniq
                        _canon_jobs.append({"term": _canon, "context": _canon,
                                            "candidates": _uniq})
                    _canon_rerank = self._llm_rerank_clc_batch(_canon_jobs)
                    for _canon, _uniq in _canon_cands.items():
                        _chosen, _conf = _canon_rerank.get(_canon, (-1, 0.0))
                        if _chosen < 0 or _conf < 0.45:
                            continue
                        _c = _uniq[_chosen] if _chosen < len(_uniq) else None
                        if _c is None:
                            continue
                        for _k, _cv in _canon_of.items():
                            if _cv == _canon:
                                _en_clc_map[_k] = {
                                    "system": "CLC",
                                    "code": _c.get("clc_code"),
                                    "label": _c.get("clc_name"),
                                    "classification_path": _c.get("path_names") or [],
                                    "confidence": round(min(1.0, _conf), 4),
                                    "mapping_engine": "clc_retriever+batch_rerank",
                                    "dense_score": round(float(_c.get("score") or 0), 4),
                                    "scene": f"术语归一：{_canon}",
                                }
        keyword_rows = []
        # 置信度下限 + 3~5 个收口（2026-09-09 用户需求）：低置信度关键词（<0.5，
        # 如 0.4 的泛化词）无参考价值；关键词规范通常 3-5 个。低于 0.5 丢弃；
        # 不足 3 个时按置信度保留前 3（避免输出过少），超过 8 个截断（2026-09-09 用户试 8+0.5）。
        # 用户词典命中词有 0.75 置信度下限，不受下限影响。
        cleaned.sort(key=lambda x: float(x.get("weight") or 0), reverse=True)
        _ranked_all = list(cleaned)  # 全量排序（场景保座救援池，含 <0.5 候选）
        _conf_keep = [c for c in cleaned if float(c.get("weight") or 0) >= 0.6]
        cleaned = _conf_keep if len(_conf_keep) >= 3 else cleaned[:3]
        # 终局包含去重（2026-09-09，大小写不敏感）：补齐路径只查精确重复会绕过
        # 包含去重（"REINFORCEMENT LEARNING" 与 rank1 "Test-time reinforcement
        # learning" 并存案例）——高置信优先保留，与已保留词互为包含的丢弃
        _kept_final: list = []
        for _c in cleaned:
            _k = _c["keyword"].casefold()
            if any(_k != _k2 and (_k in _k2 or _k2 in _k)
                   for _k2 in (x["keyword"].casefold() for x in _kept_final)):
                continue
            _kept_final.append(_c)
        cleaned = _kept_final
        # 场景词保座（2026-09-09 miss 归因：标题里的研究对象/应用场景词——风洞试验/
        # 桥梁工程/高校辅导员——在名额内被技术词挤掉，占 miss 约一半）：终局若没有
        # application_scenario/research_object 类型的词，从被门裁掉的高分候选里
        # 取"场景类型标注 或 字面出现在标题"的最优者换入末位。
        _SCENARIO_TYPES = {"application_scenario", "research_object"}
        _pre_pool = [c for c in _ranked_all if c not in cleaned]
        if cleaned and not any(str(c.get("type") or "") in _SCENARIO_TYPES for c in cleaned):
            _title_cf = (title or "").casefold()
            # 救援池补充：挖掘候选里字面命中标题的（LLM 未输出过的标题词也能救回，
            # 特征分作权重代理）
            if _title_cf:
                _have_kws = {c["keyword"].casefold() for c in cleaned} | \
                            {c["keyword"].casefold() for c in _pre_pool}
                for _c in cands[:40]:
                    _ph = str(_c.get("phrase") or "")
                    if (not _ph or _ph.casefold() in _have_kws or len(_ph) > 30
                            or _ph.casefold() not in _title_cf):
                        continue
                    _pre_pool.append({"keyword": _ph,
                                      "weight": round(float(_c.get("score") or 0), 3),
                                      "type": "application_scenario"})
            _rescue_pool = [c for c in _pre_pool
                            if float(c.get("weight") or 0) >= 0.4
                            and (str(c.get("type") or "") in _SCENARIO_TYPES
                                 or (_title_cf and c["keyword"].casefold() in _title_cf))]
            _rescue_pool.sort(key=lambda x: (str(x.get("type") or "") in _SCENARIO_TYPES,
                                             x["keyword"].casefold() in _title_cf,
                                             float(x.get("weight") or 0)), reverse=True)
            if _rescue_pool:
                _resc = _rescue_pool[0]
                _rk = _resc["keyword"].casefold()
                if not any(_rk != k2 and (_rk in k2 or k2 in _rk)
                           for k2 in (x["keyword"].casefold() for x in cleaned)):
                    if len(cleaned) >= 8:
                        cleaned = cleaned[:-1]
                    cleaned.append(_resc)
        if len(cleaned) > 8:
            cleaned = cleaned[:8]
        searchable = searchable_text.casefold()
        for rank, item in enumerate(cleaned, start=1):
            keyword = item["keyword"]
            start = searchable.find(keyword.casefold())
            weight = item.get("weight")
            _kw_hit = _norm_index.get(keyword.casefold()) if is_en else None
            # 规范化形式：① 整词=库内变体 → 直接填标准术语；② 短语内含变体成分 →
            # 逐成分展开（bridge SHM → bridge structural health monitoring）；
            # ③ 无命中 → 原样。归一促成（精确或成分）即标库来源
            _norm_out = keyword
            _norm_from_lib = bool(_kw_hit and _user_lib_cf
                                  and str(_kw_hit.get("canonical") or "").casefold() in _user_lib_cf)
            if _kw_hit:
                _norm_out = _kw_hit["canonical"]
            elif is_en:
                _parts = []
                _hit_any = False
                for _w in keyword.split():
                    _w_cf = _w.strip('()[]{}"\',.;:').casefold()
                    _h2 = _norm_index.get(_w_cf)
                    if _h2:
                        _parts.append(_h2["canonical"])
                        if _user_lib_cf and (_w_cf in _user_lib_cf
                                             or str(_h2.get("canonical") or "").casefold() in _user_lib_cf):
                            _hit_any = True
                    else:
                        _parts.append(_w)
                if _hit_any:
                    _norm_out = " ".join(_parts)
                    _norm_from_lib = True
            # 分类映射反查链：关键词字面 → casefold → 术语库归一出的标准术语。
            # 变体（SHM）本身不在映射表、但其标准术语（structural health monitoring）
            # 在表内时，用标准术语的映射——术语库归一与映射表覆盖两资源协同。
            # 优先级：表内字面 > 表内标准术语（确定性映射）> 内置检索对变体的猜测
            _cm = None
            if is_en:
                _cm = _en_clc_map.get(keyword) or _en_clc_map.get(keyword.casefold())
                if _kw_hit:
                    _canon = str(_kw_hit.get("canonical") or "")
                    _cm2 = _en_clc_map.get(_canon) or _en_clc_map.get(_canon.casefold())
                    if isinstance(_cm2, dict) and str(_cm2.get("mapping_engine") or "").startswith("user_resource"):
                        _cm = _cm2
            # 用户术语库命中（字面=库内 canonical/变体，或归一由库促成）：标 external
            # 来源，前端"术语资源"列显示"领域术语库 · 库名"——库注入/归一的可观测指纹
            _lib_kw = _norm_from_lib or (bool(_user_lib_cf) and keyword.casefold() in _user_lib_cf)
            keyword_rows.append({
                "keyword": keyword,
                "term": keyword,
                "normalized_term": _norm_out,
                "weight": weight,
                "score": weight,
                "confidence": weight,
                "rank": rank,
                "type": item.get("type"),
                "terminology_source": ({"type": "external", "library_name": _user_lib_name or "用户术语库"}
                                       if _lib_kw else None),
                "source": custom_dictionary.get("name") if item.get("custom_dictionary_hit") else "model",
                "custom_dictionary_hit": bool(item.get("custom_dictionary_hit")),
                "matched_dictionary_term_id": item.get("dictionary_term_id"),
                "weight_change": _number_or_default(item.get("weight_change"), 0),
                "classification_mapping": _cm,
                "source_position": {
                    "start": start if start >= 0 else None,
                    "end": start + len(keyword) if start >= 0 else None,
                },
            })

        result.success = True
        result.data = {
            "keywords": keyword_rows,
            "document": {"title": title or ""},
            "document_title": title or "",
            "dictionary_usage": {
                "dictionary_id": custom_dictionary.get("id"),
                "version_id": custom_dictionary.get("version_id"),
                "version": custom_dictionary.get("version"),
                "name": custom_dictionary.get("name"),
                # 审计留痕：实际装载的术语列表（文件解析/手填/已存词典三种来源）
                # 与来源标记（parsed_file=上传文件规则解析或 LLM 兜底抽取）
                "dictionary_name": custom_dictionary.get("dictionary_name"),
                "terms": [t.get("term") if isinstance(t, dict) else t for t in custom_terms][:50],
                "term_source": "parsed_file" if (
                    custom_dictionary.get("text_content") or custom_dictionary.get("storage_uri")
                ) else (
                    "saved_dictionary" if custom_dictionary.get("id") else "user_input"),
                "matched_term_count": len(matched_terms),
            } if custom_terms else None,
            "statistics": {
                "keyword_count": len(keyword_rows),
                # 词典命中数：custom_dictionary_hit=true 的关键词条数（页面顶部
                # 「用户词典命中」卡片数据源）
                "user_dict_hit_count": sum(1 for row in keyword_rows if row.get("custom_dictionary_hit")),
            },
        }
        result.evidence = [{"dropped": d} for d in dropped] if dropped else []
        result.confidence = cleaned[0].get("weight") if cleaned else None
        result.raw = json.dumps(
            {"keywords": keyword_rows, "dictionary_usage": result.data.get("dictionary_usage"), "n_candidates": len(cands),
             "n_dropped": len(dropped), "feature_weights": model.get("feature_weights")},
            ensure_ascii=False, default=str)
        return result

    @staticmethod
    def _term_context(term: str, searchable_text: str, width: int = 100) -> str:
        """提取 term 在全文中的上下文片段（前后 width 字符），供 CLC rerank 消歧。"""
        if not searchable_text or not term:
            return ""
        idx = searchable_text.casefold().find(term.casefold())
        if idx < 0:
            return ""
        start = max(0, idx - width)
        end = min(len(searchable_text), idx + len(term) + width)
        return searchable_text[start:end].replace("\n", " ").strip()

    def _llm_rerank_clc(self, term: str, context: str, candidates: list) -> tuple:
        """LLM rerank：term + 上下文 + 候选类目 → (chosen_idx, confidence)。

        chosen=-1 表示所有候选都不相关（宁缺毋滥）。confidence 是 LLM 自评把握。
        解决 bge-m3 跨语言 dense 检索单 term 无上下文导致的多义词误分
        （European wildcat→E军事、hybridization→U交通）：用上下文语境消歧。
        """
        if not candidates:
            return -1, 0.0
        sysp = (
            "你是科技文献分类专家。给定一个英文术语、其所在上下文片段、若干中图法（CLC）候选类目，"
            "判断该术语在此语境下最可能属于哪个类目。\n"
            "- 从候选中选最接近术语学科语义的一个，即使不完全贴切也选最接近的（覆盖优先，尽量给映射）\n"
            "- 只有当所有候选都与术语学科完全无关时才返回 chosen=-1\n"
            "- confidence 反映把握（0.0-1.0）：学科明确且贴切→高(>0.8)；勉强/最接近但不完全贴切→中(0.5-0.7)；"
            "很勉强→低(0.4-0.5)\n"
            "输出JSON：{\"chosen\":0,\"confidence\":0.85,\"reason\":\"...\"}  # chosen=候选序号(0-based)或-1"
        )
        listing = []
        for i, c in enumerate(candidates):
            path = " > ".join(c.get("path_names") or []) or c.get("classification_path") or ""
            listing.append(f"[{i}] {c.get('clc_code')} {c.get('clc_name')} | 路径: {path}")
        user = f"术语：{term}\n上下文：{context[:200]}\n候选类目：\n" + "\n".join(listing)
        try:
            out = self._glm.chat_json(sysp, user, timeout=60.0, max_tokens=300)
            data = out.get("data", out) if isinstance(out, dict) else {}
            chosen = int(data.get("chosen", -1))
            conf = float(data.get("confidence", 0.0) or 0)
            if chosen < -1 or chosen >= len(candidates):
                chosen = -1
            return chosen, conf
        except Exception as exc:  # noqa: BLE001
            logger.warning("CLC LLM rerank 失败 [%s]: %s", term, exc)
            return -1, 0.0

    def _llm_rerank_clc_batch(self, jobs: list) -> dict:
        """CLC rerank 批量化：一篇的全部术语候选合成一次 LLM 调用。"""
        if not jobs:
            return {}
        sysp = (
            "你是科技文献分类专家。下面有多条术语，每条带其上下文与若干中图法候选类目。"
            "对每条术语独立判断其在此语境下最可能属于的类目。\n"
            "- 从该条的候选中选最接近的一个（覆盖优先）\n"
            "- 只有当该条所有候选都与术语学科完全无关时才 chosen=-1\n"
            "- confidence 反映把握（0.0-1.0）\n"
            "只输出JSON：{\"items\":[{\"term\":\"原词\",\"chosen\":0,\"confidence\":0.85},...]}"
        )
        parts = []
        for ji, job in enumerate(jobs):
            cands = job.get("candidates") or []
            lines = []
            for i, c in enumerate(cands):
                path = " > ".join(c.get("path_names") or []) or ""
                lines.append(f"  [{i}] {c.get('clc_code')} {c.get('clc_name')}" + (f" | {path}" if path else ""))
            parts.append(f"({ji}) 术语：{job.get('term')}\n  上下文：{str(job.get('context') or '')[:150]}\n  候选:\n" + "\n".join(lines))
        user = "\n\n".join(parts)
        out_map = {}
        try:
            out = self._glm.chat_json(sysp, user, timeout=90.0, max_tokens=1800)
            data = out.get("data", out) if isinstance(out, dict) else {}
            items = data.get("items") or []
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        t = str(it.get("term") or "").strip()
                        try:
                            ch = int(it.get("chosen", -1))
                            cf = max(0.0, min(1.0, float(it.get("confidence", 0))))
                        except (TypeError, ValueError):
                            ch, cf = -1, 0.0
                        if t:
                            out_map[t] = (ch, cf)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CLC rerank 批量失败: %s", exc)
        return out_map

    def _llm_translate_term(self, term: str) -> str:
        """LLM 翻译英文术语→中文标准译名，用于中文 dense 检索补充召回音译专有名词。

        bge-m3 跨语言 dense 对音译专有名词（Nile tilapia↔罗非鱼）无力——靠知识
        非语义相似。LLM 翻译后用中文 dense（cross_lingual=False）能精确召回。
        """
        sysp = ("你是科技术语翻译专家。将给定英文科技术语翻译成最规范的中文标准译名。"
                "只输出JSON：{\"answer\":\"中文译名\"}")
        try:
            out = self._glm.chat_json(sysp, term, temperature=0.1, timeout=30.0, max_tokens=60)
            data = out.get("data", out) if isinstance(out, dict) else {}
            ans = data.get("answer") or data.get("translation") or data.get("result") or ""
            if isinstance(ans, list):
                ans = ans[0] if ans else ""
            return str(ans).strip()
        except Exception:  # noqa: BLE001
            return ""

    def _llm_scene_rewrite_term(self, term: str, context: str, document_title: str = "") -> str:
        """LLM 融合关键词+上下文+标题，重写为带应用场景的中文描述，供 CLC 检索锚定学科。

        孤立英文词跨语言 dense 召回易跑偏（recombination→生物基因重组实为半导体复合层；
        growth performance→泛生物生长实为水产养殖指标）。LLM 综合上下文生成「该词在本
        研究中的学科语境」中文句，用中文 dense（bge-large-zh）召回更精确贴切的 CLC 类目。
        """
        if not (context or document_title):
            return ""
        sysp = (
            "你是科技文献分类助手。给定英文关键词、其上下文片段、文献标题，生成一句简洁的中文应用场景描述，"
            "说明该关键词在本研究中的具体学科语境，用于中图法分类检索。\n"
            "- 融合关键词语义与应用场景（研究对象/领域/方法用途），体现学科归属\n"
            "- 例：'growth performance' 在罗非鱼研究中→'罗非鱼水产养殖的生长性能评估'；"
            "'recombination layer' 在钙钛矿太阳能电池中→'钙钛矿太阳能电池载流子复合层'\n"
            "- 必须带应用场景锚定学科，不能只重复关键词字面（不要只输出'生长性能'）\n"
            "- 不超过30字。只输出JSON：{\"scene\":\"中文描述\"}"
        )
        user = f"关键词：{term}\n文献标题：{document_title or '（无标题）'}\n上下文：{context[:200]}"
        try:
            out = self._glm.chat_json(sysp, user, temperature=0.2, timeout=30.0, max_tokens=80)
            data = out.get("data", out) if isinstance(out, dict) else {}
            s = data.get("scene") or data.get("description") or data.get("scene_desc") or ""
            return str(s).strip()
        except Exception:  # noqa: BLE001
            return ""

    def _llm_keyword_semantic_scores(self, terms: list, contexts: dict, document_title: str = "", abstract: str = "") -> dict:
        scores, _ = self._llm_keyword_scores_and_scenes(terms, contexts, document_title, abstract)
        return scores

    def _llm_keyword_scores_and_scenes(self, terms: list, contexts: dict, document_title: str = "", abstract: str = "") -> tuple:
        """轮次合并：评分+场景一次调用。"""
        if not terms:
            return {}, {}
        sysp = (
            "你是科技文献主题分析专家。给定文献标题、摘要、若干候选术语（每个带其原文上下文片段），"
            "对每个术语同时完成两项独立判定：\n"
            "1) prob：该术语是否本文献的核心主题术语的 0-1 概率。独立判定，不互相比较、不按输入顺序递减；"
            "泛化功能词即使频高也给低分；核心术语给高分，即便只出现一次。\n"
            "2) scene：该术语在此文献中的应用场景中文描述（用于中图法类目锚定学科）。"
            "必须带应用场景（如\"罗非鱼水产养殖指标\"），不能只重复关键词字面。\n"
            "只输出JSON：{\"items\":[{\"term\":\"原词\",\"prob\":0.0-1.0,\"scene\":\"中文场景描述\"},...]}"
        )
        listing = []
        for t in terms:
            ctx = (contexts.get(t) or "")[:150]
            listing.append(f"- {t} | 上下文：{ctx}")
        user = f"文献标题：{document_title or '（无标题）'}\n摘要：{(abstract or '')[:500]}\n候选术语列表：\n" + "\n".join(listing)
        scores: dict = {}
        scenes: dict = {}
        try:
            out = self._glm.chat_json(sysp, user, temperature=0.2, timeout=60.0, max_tokens=1800)
            data = out.get("data", out) if isinstance(out, dict) else {}
            items = data.get("items") or data.get("terms") or []
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        t = it.get("term") or it.get("keyword") or ""
                        if not t:
                            continue
                        p = it.get("prob") if it.get("prob") is not None else it.get("probability")
                        try:
                            scores[t] = max(0.0, min(1.0, float(p)))
                        except (TypeError, ValueError):
                            scores[t] = 0.5
                        sc = str(it.get("scene") or "").strip()
                        if sc:
                            scenes[t] = sc
        except Exception as exc:  # noqa: BLE001
            logger.warning("关键词评分+场景合并调用失败: %s", exc)
        return scores, scenes
        if not terms:
            return {}
        sysp = (
            "你是科技文献主题分析助手。给定文献标题、摘要、若干候选术语（每个带其原文上下文片段），"
            "对每个术语独立判定：该术语是否本文献的核心主题术语（研究对象/核心方法/关键指标/关键参数），"
            "返回 0-1 概率（1=确定是核心主题术语，0=确定不是）。\n"
            "- 每个术语独立判定，不要互相比较、不要按输入顺序递减\n"
            "- 泛化功能词（研究/方法/结果/分析/设计/性能）即使频高也给低分\n"
            "- 核心术语（研究对象、独有方法名、关键参数、特定技术）给高分，即便只出现一次\n"
            "- 输出JSON：{\"items\":[{\"term\":\"原词\",\"prob\":0.0-1.0},...]}  # 每个术语一项，顺序与输入一致"
        )
        listing = []
        for t in terms:
            ctx = (contexts.get(t) or "")[:150]
            listing.append(f"- {t} | 上下文：{ctx}")
        user = f"文献标题：{document_title or '（无标题）'}\n摘要：{(abstract or '')[:500]}\n候选术语列表：\n" + "\n".join(listing)
        try:
            out = self._glm.chat_json(sysp, user, temperature=0.2, timeout=60.0, max_tokens=1500)
            data = out.get("data", out) if isinstance(out, dict) else {}
            items = data.get("items") or data.get("terms") or []
            result = {}
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        t = it.get("term") or it.get("keyword") or ""
                        p = it.get("prob") if it.get("prob") is not None else it.get("probability")
                        if t:
                            try:
                                result[t] = max(0.0, min(1.0, float(p)))
                            except (TypeError, ValueError):
                                result[t] = 0.5
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("关键词语义判定批量失败: %s", exc)
            return {}

    def _llm_scene_rewrite_batch(self, terms: list, contexts: dict, document_title: str = "") -> dict:
        """批量场景重写：1 次 LLM 调用为多个关键词生成应用场景描述，替代逐词 N 次降时延。

        返回 {term: scene} 字典。批量失败则返回空字典（调用方逐词兜底）。
        解决多文件/多关键词时逐词场景重写 N 次串行 GLM 导致时延翻倍的问题。
        """
        if not terms:
            return {}
        sysp = (
            "你是科技文献分类助手。给定多个英文关键词、文献标题、每个关键词的上下文片段，"
            "为每个关键词生成一句简洁的中文应用场景描述（≤30字），说明其在本文中的具体学科语境，用于中图法分类检索。\n"
            "- 融合关键词语义与应用场景（研究对象/领域/方法用途），体现学科归属\n"
            "- 例：'growth performance' 在罗非鱼研究中→'罗非鱼水产养殖的生长性能评估'；"
            "'recombination layer' 在钙钛矿太阳能电池中→'钙钛矿太阳能电池载流子复合层'\n"
            "- 必须带应用场景锚定学科，不能只重复关键词字面\n"
            "- 输出JSON：{\"items\":[{\"term\":\"原词\",\"scene\":\"中文描述\"},...]}  # 每个关键词一项，顺序与输入一致"
        )
        listing = []
        for t in terms:
            ctx = (contexts.get(t) or "")[:150]
            listing.append(f"- {t} | 上下文：{ctx}")
        user = f"文献标题：{document_title or '（无标题）'}\n关键词列表：\n" + "\n".join(listing)
        try:
            out = self._glm.chat_json(sysp, user, temperature=0.2, timeout=60.0, max_tokens=1000)
            data = out.get("data", out) if isinstance(out, dict) else {}
            items = data.get("items") or data.get("scenes") or []
            result = {}
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        t = it.get("term") or it.get("keyword") or ""
                        sc = it.get("scene") or it.get("description") or ""
                        if t:
                            result[t] = str(sc).strip()
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("CLC 场景重写批量失败: %s", exc)
            return {}

    def _keyword_classification_mapping(self, term: str, context: str = "", document_title: str = "", scene: str = "") -> Dict[str, Any] | None:
        """英文关键词→中图法类目映射：LLM 场景重写中文 dense + 英文 dense + 译名 dense 三路召回 + LLM rerank。

        孤立 term 跨语言 dense 召回易跑偏（recombination→生物基因重组，实为半导体复合层；
        growth performance→泛生物生长，实为水产养殖指标）。LLM 融合上下文+标题重写为带
        应用场景的中文描述，中文 dense（cross_lingual=False bge-large-zh）精确锚定学科
        （罗非鱼水产养殖→S96）。英文 dense 兜底、译名 dense 救音译专有名词。合并候选
        LLM rerank 消歧，confidence 用 LLM 自评（<0.45 或都不相关则不返回）。
        """
        try:
            from infrastructure.rag.clc_retriever import clc_retriever

            # 1. 英文 term dense 召回（兜底，场景重写失败/跑偏时仍可用）
            candidates = clc_retriever.retrieve(term, "", [], k=8, cross_lingual=True)
            # 2. LLM 场景重写 → 中文 dense 召回（主路径，应用场景锚定学科）
            # scene 优先用调用方批量预生成的（_llm_scene_rewrite_batch），无则逐词兜底
            if not scene and (context or document_title):
                scene = self._llm_scene_rewrite_term(term, context, document_title)
            if scene:
                scene_cands = clc_retriever.retrieve(scene, "", [], k=8, cross_lingual=False)
                candidates = candidates + scene_cands
            if not candidates:
                return None
            top_score = _number_or_default(candidates[0].get("score"), 0.0)
            if top_score < 0.40:  # 三路召回都不沾边，LLM 也难救
                return None
            # 3. 译名中文 dense 补充召回音译专有名词（英文不沾边时）
            if top_score < 0.50:
                trans = self._llm_translate_term(term)
                if trans and trans != scene:
                    t_cands = clc_retriever.retrieve(trans, "", [], k=8, cross_lingual=False)
                    candidates = candidates + t_cands
            # 4. 去重 by clc_code（保留 score 最高），按 score 降序取前 6 供 LLM 选
            best = {}
            for c in candidates:
                code = c.get("clc_code")
                if not code:
                    continue
                s = _number_or_default(c.get("score"), 0.0)
                if code not in best or s > _number_or_default(best[code].get("score"), 0.0):
                    best[code] = c
            uniq = sorted(best.values(), key=lambda c: -_number_or_default(c.get("score"), 0.0))[:6]
            # 5. LLM rerank（带场景上下文消歧）
            rerank_ctx = context + (" [场景]" + scene if scene else "")
            chosen, conf = self._llm_rerank_clc(term, rerank_ctx, uniq)
            if chosen < 0 or conf < 0.45:
                return None
            c = uniq[chosen]
            dense_score = _number_or_default(c.get("score"), 0.0)
            return {
                "system": "CLC",
                "code": c.get("clc_code"),
                "label": c.get("clc_name"),
                "classification_path": c.get("path_names") or c.get("classification_path") or [],
                "confidence": round(min(1.0, conf), 4),
                "mapping_engine": "clc_retriever+llm_scene+rerank",
                "dense_score": round(dense_score, 4),
                "scene": scene or "",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("关键词 CLC 映射失败 [%s]: %s", term, exc)
            return None

    # ---- 关键词管线辅助 ---- #
    @staticmethod
    def _split_title_abstract(text: str):
        """text 可为 '标题。摘要' 或纯摘要；首个句号前视作标题。"""
        text = (text or "").strip()
        for sep in ["。", "．", ". ", "\n"]:
            if sep in text:
                head, rest = text.split(sep, 1)
                if 4 <= len(head) <= 60:
                    return head.strip(), rest.strip()
        return "", text

    @staticmethod
    def _strip_author_keywords(text: str) -> str:
        """剥离论文已列作者关键词段落，避免 LLM 原样复述而非基于内容自主生成。

        覆盖常见格式：'关键词：A；B；C' / 'Keywords: a; b; c'，含以分隔符开头的续行
        （续行强特征是以分号/顿号/逗号开头，正文段落不以此开头，故不误伤正文）。
        """
        if not text:
            return text
        import re as _re
        guide = r'(?:关\s*键\s*词|\bKey\s*words?)\s*[:：]'
        # 内容匹配到句号/换行止，避免吞掉关键词段后续的正文；续行须以分隔符开头
        seg = r'[^。.\n]*(?:[；;、，,][^。.\n]*)*[。.]?'
        content = seg + r'(?:\n[；;、，,]\s*' + seg + r')*'
        out = _re.sub(r'[ \t]*' + guide + r'\s*' + content + r'\n?', '', text, flags=_re.IGNORECASE)
        out = _re.sub(r'\n{3,}', '\n\n', out)
        return out or text

    @staticmethod
    def _extract_paper_title(full_text: str) -> str:
        """从 MinerU markdown 全文提取论文题目。

        MinerU 常把期刊名/网络首发标识（《xx》网络首发论文）、出版信息标成首个一级标题，
        真正题目在第二个一级标题。跳过期刊/出版信息行与章节标题词，取首个真正的题目行。
        """
        import re as _re
        if not full_text:
            return ""
        # 所有层级标题按文档序取（文档题目可能标成 ##，而 # 被表单名/刊头占用）
        headings = _re.findall(r'^#{1,6}\s+(.+?)\s*$', full_text, _re.MULTILINE)

        def _clean(h: str) -> str:
            # 去 markdown 转义星号/下划线与首尾 * 标记
            h = h.replace('\\*', '*').replace('\\_', '_').replace('\\#', '#')
            return h.strip(' *').strip()

        journal_pat = _re.compile(
            r'(?:《[^》]*》|网络首发|首发论文|Vol\.?\s*\d|No\.\s*\d|DOI|doi:|https?://|'
            r'arXiv|preprint|期刊|杂志|出版社|©|copyright|received|accepted|'
            r'ISSN|ISBN|Published|刊号|'
            r'Technical\s+report|Research\s+report|White\s+paper|Working\s+paper|Position\s+paper)', _re.IGNORECASE)
        section_pat = _re.compile(
            r'^(?:摘要|abstract|引言|前言|背景|方法|结论|总结|展望|相关工作|关键词|keywords|'
            r'参考文献|references?|致谢|acknowledg|附录|appendix|目录|contents|'
            r'\d+[、\.．\s]|[一二三四五六七八九十]+[、\.．])', _re.IGNORECASE)

        # 无 # 标题（pdfplumber 纯文本等）：从首部取题目行，跳过期刊页眉/作者/摘要。
        # 优先「摘要标记上方定位」：论文题目几乎总紧邻摘要上方，从摘要行向上回溯
        # 可跳过期刊中英文名/期号/栏目行（如 信息与电脑 / Information&Computer），
        # 并把被解析拆成多行的题目拼回一行（肾内科血净护理 / 实习教学中的应用研究）。
        if not headings:
            lines = [l.strip() for l in (full_text or "").split('\n')[:40]]

            def _title_like(line: str) -> bool:
                if len(line) < 8 or len(line) > 80:
                    return False
                if (journal_pat.search(line)
                        or _re.search(r'\d{4}|[（(]\d+[)）]|@|doi|摘\s*要|关键\s*词|'
                                      r'文献标志码|中图分类号|通信作者|E-?mail|Abstract', line, _re.IGNORECASE)
                        or _re.match(r'^\d', line)):
                    return False
                # 跳过作者行：多个逗号分隔的人名；  全角空格分隔的作者串也不是题目
                if line.count('，') >= 2 or line.count(',') >= 2 or ' ' in line or '∗' in line or '*' in line:
                    return False
                if _re.search(r'大学|学院|医院|研究所|公司|集团|Hospital|University|Institute', line) and len(line) < 30:
                    return False
                return True

            def _author_or_affil(line: str) -> bool:
                """作者/单位行（题目与摘要之间的障碍行）：回溯时跳过而非中断。"""
                return bool(line and (
                    _re.match(r'^\d', line)
                    or ' ' in line
                    or '∗' in line
                    or _re.search(r'大学|学院|医院|研究所|公司|集团|重点实验室|研究中心|'
                                  r'Hospital|University|Institute|Technology|Laboratory|Research|@|mail', line, _re.IGNORECASE)
                    or line.count('，') >= 2 or line.count(',') >= 2))

            def _polish(t: str) -> str:
                # 去「题目：」表单前缀；同行作者以连续 2+ 空格分隔 → 截断保留题目部分
                t = _re.sub(r'^题目\s*[:：]\s*', '', t.strip())
                if _re.search(r'[一-鿿]', t):
                    t = _re.split(r'\s{2,}', t)[0]
                return t[:120]

            # 1) 摘要标记上方回溯：跳过作者/单位行，取紧邻摘要上方的题目行块
            abstract_idx = next((i for i, l in enumerate(lines)
                                 if _re.match(r'^(摘\s*要|Abstract)\s*[:：]?', l, _re.IGNORECASE)), None)
            if abstract_idx is not None:
                block = []
                for j in range(abstract_idx - 1, max(-1, abstract_idx - 8), -1):
                    if not lines[j]:
                        continue
                    if _title_like(lines[j]):
                        # 拉丁行须像题目（≥4 词或含冒号）：裸人名（Xian Guo，2-3 词）
                        # 不是题目，直接断开，避免把作者名并进标题块
                        if not _re.search(r'[一-鿿]', lines[j]) \
                                and len(lines[j].split()) < 4 and ':' not in lines[j]:
                            break
                        block.insert(0, lines[j])
                        continue
                    if _author_or_affil(lines[j]):
                        continue  # 作者/单位行：跳过继续向上找题目
                    break
                if block:
                    merged = "".join(block) if _re.search(r'[一-鿿]', block[0]) else " ".join(block)
                    return _polish(merged)
            # 2) 兜底：首个题目行（原逻辑），纯拉丁行（期刊英文名）在有中文行时跳过
            has_cjk_candidate = any(_title_like(l) and _re.search(r'[一-鿿]', l) for l in lines)
            for idx, line in enumerate(lines):
                if not _title_like(line) or _author_or_affil(line):
                    continue
                if has_cjk_candidate and not _re.search(r'[一-鿿]', line):
                    continue  # 期刊英文名（Information&Computer 等）
                # 题目被拆行：下一行也题目样且过中文规则 → 中文直接拼接/英文空格拼接
                nxt = ""
                if idx + 1 < len(lines) and _title_like(lines[idx + 1]):
                    nxt_ok = _re.search(r'[一-鿿]', lines[idx + 1]) or not has_cjk_candidate
                    nxt = lines[idx + 1] if nxt_ok else ""
                if nxt and _re.search(r'[一-鿿]', line):
                    return _polish(line + nxt)
                return _polish(line)
            return ""

        candidates = []
        for h in headings:
            c = _clean(h)
            if not c or len(c) < 4:
                continue
            if journal_pat.search(c) or section_pat.match(c):
                continue
            # mineru 偶把作者/单位行标成标题（英文论文）：∗ 上标、单位词、邮箱 → 跳过
            if '∗' in c or '*' in c or '@' in c or (
                    not _re.search(r'[一-鿿]', c)
                    and _re.search(r'Technology|Laboratory|University|Institute|Hospital', c)
                    and len(c.split()) >= 4):
                continue
            candidates.append(c)
        if candidates:
            return candidates[0][:120]
        # 全被跳过：取最长一级标题兜底
        cleaned = [_clean(h) for h in headings if _clean(h)]
        return max(cleaned, key=len)[:120] if cleaned else ""

    @staticmethod
    def _load_keyword_model(fp):
        """加载训练产物（特征权重+few_shot+domain_terms），缺失则默认。"""
        import json as _json
        from pathlib import Path
        from config.settings import settings as _settings
        path = Path(_settings.RULES_DIR) / fp.rule_path
        model_path = path.parent / (path.stem + "_model.json")
        if model_path.exists():
            try:
                return _json.loads(model_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass
        return {"feature_weights": {"in_title": 1.0, "freq": 0.6, "position": 0.4, "length": 0.2},
                "few_shot": [], "domain_terms": []}

    @staticmethod
    def _render_keyword_user_prompt(title, abstract, candidates, few_shot, lang="", preserve_original_form=True, count_min=3, count_max=8, body_excerpt: str = "", library_terms=None) -> str:
        import json as _json
        is_en = lang == "en"
        parts = []
        if few_shot:
            parts.append("Examples:" if is_en else "【示例】")
            for ex in few_shot[:3]:
                parts.append(("Input: " if is_en else "输入：") + (ex.get("abstract", "")[:160]))
                kws = ex.get("keywords", [])
                parts.append(("Output: " if is_en else "输出关键词：") + ("; ".join(kws) if is_en else "、".join(kws)))
            parts.append("")
        if is_en:
            if preserve_original_form:
                note = ("Generate keywords yourself from the document topic; do NOT copy any "
                        "author-listed keyword list verbatim. "
                        "Pick the keywords MOST RELEVANT to the core content, 0-2 per type, aiming for type "
                        "coverage (avoid clustering in one type; skip a type if no strong candidate). "
                        f"Extract {count_min}-{count_max} keywords in total. "
                        "Use terms exactly as they appear in the document; do NOT generalize, rephrase, "
                        "or merge scattered wording into a standard term. Prefer concise base terms; "
                        "drop generic words — a single bare generic noun (e.g. \"damage\", \"model\", "
                        "\"analysis\", \"monitoring\", \"learning\") is NEVER a keyword by itself: use the "
                        "fuller domain-specific term from the document (e.g. \"damage identification\") "
                        "instead. Also surface key metrics, phenomena, or parameters "
                        "(phenomenon_metric type) that recur in the document—they are often the "
                        "study's defining criteria; do not omit them just because they are not in "
                        "the title. MUST also cover application-scenario / research-object domain "
                        "terms (disease, department, industry, equipment, business scenario — e.g. "
                        "the scenario words in the title); never let method/model/metric terms "
                        "crowd them out. Return JSON {data:[{keyword,weight,type}]}.")
            else:
                note = ("Generate keywords yourself from the document topic; do NOT copy any "
                        "author-listed keyword list verbatim. "
                        "Pick the keywords MOST RELEVANT to the core content, 0-2 per type, aiming for type "
                        "coverage (avoid clustering in one type; skip a type if no strong candidate). "
                        f"Extract {count_min}-{count_max} keywords in total. "
                        "Prefer phrases appearing in the document; for a recurring concept with scattered wording, "
                        "use the standard term. Prefer concise base terms; drop generic words. "
                        "Also surface key metrics, phenomena, or parameters (phenomenon_metric type) "
                        "that recur in the document—they are often the study's defining criteria; "
                        "do not omit them just because they are not in the title. "
                        "MUST also cover application-scenario / research-object domain terms "
                        "(disease, department, industry, equipment, business scenario — e.g. the "
                        "scenario words in the title); never let method/model/metric terms crowd "
                        "them out. Return JSON {data:[{keyword,weight,type}]}.")
            obj = {
                "title": title,
                "document": abstract,
                "keyword_types (classify each keyword into one; aim for coverage, 0-2 per type)": [
                    "research_object", "technical_method", "proposed_model", "application_scenario", "material_data", "phenomenon_metric", "theory_concept", "research_context", "research_problem"
                ],
                "candidate_phrases (high-recall noun phrases; pick from them or extract your own from the document)": candidates,
                "note": note,
            }
            if body_excerpt:
                obj["body_excerpt (opening of the full text)"] = body_excerpt
                obj["body_excerpt_rule"] = (
                    "Keywords must PRIMARILY come from the title and document (abstract) above. "
                    "Use body_excerpt ONLY to supplement a few SPECIFIC terms for the research "
                    "object, method, conclusion, or innovation that the abstract does not cover "
                    "(e.g. a named technique appearing only in the method section). Do NOT pick "
                    "generic high-frequency words from the body text.")
            if library_terms:
                obj["domain_terminology_hits"] = library_terms
                obj["domain_terminology_rule"] = (
                    "These terms come from the user's domain terminology library (standard terms "
                    "and registered variants such as abbreviations). When one of them is a core "
                    "topic of this document, output it VERBATIM as a STANDALONE keyword (exact "
                    "string, e.g. \"CNN\" not \"CNN autoencoder\") so it can be normalized to the "
                    "standard term; do not embed it inside a longer phrase.")
            parts.append("Extract keywords for the following document:\n" + _json.dumps(obj, ensure_ascii=False, indent=2))
        else:
            if preserve_original_form:
                desc = ("基于文献主题自行提炼关键词，不得直接照搬论文中作者已列的关键词组合，"
                        "应独立判断主题代表性；"
                        f"抽取 {count_min}-{count_max} 个最反映主题的关键词，按重要性降序给 0-1 weight。"
                        "必须使用标题/摘要中字面出现的原词，不得概括、改写或合并措辞分散的概念"
                        "（如摘要为'深度神经网络'时不得概括为'深度学习'）。"
                        "偏好简洁基础术语，避免'高比例/大规模/高效'等量化修饰语加在基础词上"
                        "（如选'分布式电源'而非'高比例分布式电源'）；"
                        "公认固定术语保持完整，不得拆分（如'新型城镇化''双有源桥变换器'）。"
                        "除研究对象/技术方法外，也留意本文反复出现的核心度量指标、物理现象、"
                        "关键参数（phenomenon_metric 类，如响应谱/频谱/应力/位移/精度等），"
                        "它们常是研究的关键判据，勿因不在标题就遗漏。"
                        "关键词必须覆盖文中的应用场景/研究对象领域词（疾病、科室、行业、装备、业务场景等，如标题中的场景词），不得全部集中在方法/模型/指标词——标题中的研究对象与场景词通常就是核心关键词。"
                        "为每个关键词标注 type（从下方 keyword_types 中选一类；本文新提出的模型/方法/算法标 proposed_model，区别于通用 technical_method），返回 JSON {data:[{keyword,weight,type}]}。")
            else:
                desc = ("基于文献主题自行提炼关键词，不得直接照搬论文中作者已列的关键词组合，"
                        "应独立判断主题代表性；"
                        f"抽取 {count_min}-{count_max} 个最反映主题的关键词，按重要性降序给 0-1 weight。"
                        "优先使用标题/摘要中出现的原词；对反复出现但措辞分散的核心概念，"
                        "可用规范学术术语概括（如摘要'深度神经网络'可概括为'深度学习'，"
                        "'社会网络方法'可概括为'社会网络分析'），但不得脱离原文主题生造。"
                        "偏好简洁基础术语，避免'高比例/大规模/高效'等量化修饰语加在基础词上"
                        "（如选'分布式电源'而非'高比例分布式电源'）；"
                        "公认固定术语保持完整，不得拆分（如'新型城镇化''双有源桥变换器'）。"
                        "除研究对象/技术方法外，也留意本文反复出现的核心度量指标、物理现象、"
                        "关键参数（phenomenon_metric 类，如响应谱/频谱/应力/位移/精度等），"
                        "它们常是研究的关键判据，勿因不在标题就遗漏。"
                        "关键词必须覆盖文中的应用场景/研究对象领域词（疾病、科室、行业、装备、业务场景等，如标题中的场景词），不得全部集中在方法/模型/指标词——标题中的研究对象与场景词通常就是核心关键词。"
                        "为每个关键词标注 type（从下方 keyword_types 中选一类；本文新提出的模型/方法/算法标 proposed_model，区别于通用 technical_method），返回 JSON {data:[{keyword,weight,type}]}。")
            obj = {
                "title": title, "abstract": abstract,
                "keyword_types（为每个关键词归一类，力求覆盖多类，每类 0-2 个）": [
                    "research_object", "technical_method", "proposed_model",
                    "application_scenario", "material_data", "phenomenon_metric",
                    "theory_concept", "research_context", "research_problem",
                ],
                "候选短语（仅供参考，可从中选，也可自行从原文摘取原词）": candidates,
                "说明": desc,
            }
            if body_excerpt:
                obj["正文节选（全文开头部分）"] = body_excerpt
                obj["正文节选使用规则"] = (
                    "关键词主要从标题和摘要中提取；正文节选仅用于补充摘要未覆盖的"
                    "研究对象/研究方法/主要结论/创新点的特有术语（如只在方法章节出现的"
                    "具体技术名），不得从正文选取高频泛化词。")
            parts.append("请为以下文献抽取关键词：\n" + _json.dumps(obj, ensure_ascii=False, indent=2))
        return "\n".join(parts)

    @staticmethod
    def _clean_keywords(raw_kw, stopwords, full_text="", lang=""):
        """后置清洗：字面原词校验 + 包含去重(保留简洁基础词) + 停用词 + 长度 + 排序。"""
        import re as _re
        is_en = lang == "en"
        _lex_en = _keyword_lexicon("en")
        _lex_zh = _keyword_lexicon("zh")
        seen = set()
        cleaned, dropped = [], []
        for item in raw_kw:
            kw = (item.get("keyword", "") if isinstance(item, dict) else str(item)).strip()
            w = item.get("weight", 0.5) if isinstance(item, dict) else 0.5
            t = item.get("type") if isinstance(item, dict) else None
            kw = _re.sub(r"^[\s、，,。.；;:：()（）\[\]]+|[\s、，,。.；;:：()（）\[\]]+$", "", kw)
            for op, cp in [("（", "）"), ("(", ")")]:
                if op in kw:
                    a, _, b = kw.partition(op)
                    b = b.replace(cp, "").strip()
                    a = a.strip()
                    kw = a if len(a) >= len(b) and a else (b or a)
                    break
            if not kw:
                continue
            # 软偏好：不强制字面（允许概念概括），但记录是否原文词供参考
            key = kw.lower()
            # 长度：英文按词数(1-8词)+字符(<=60)，中文按字符(2-24)——避免英文多词术语被中文尺度误删
            if is_en:
                wc = len(kw.split())
                if not (1 <= wc <= 8 and 2 <= len(kw) <= 60):
                    dropped.append({"keyword": kw, "reason": "长度越界(英文)"}); continue
                # 虚词/短碎片防线（词表外置 lexicon_en.json，热加载）：he/at/ti 类
                # 闭类词与 1~2 字母小写碎片不可能是主题词；全大写缩写白名单放行
                if key in _lex_en["block"]:
                    dropped.append({"keyword": kw, "reason": "英文虚词"}); _log_keyword_drop("en", kw, "英文虚词"); continue
                if len(kw) <= 2 and not kw.isupper():
                    dropped.append({"keyword": kw, "reason": "短碎片"}); _log_keyword_drop("en", kw, "短碎片"); continue
                # 2~3 字母全大写：仅公认缩写白名单放行（"MA" 类标题残片拦截）
                if kw.isupper() and len(kw) <= 3 and kw not in _lex_en["acronyms"]:
                    dropped.append({"keyword": kw, "reason": "短大写碎片"}); _log_keyword_drop("en", kw, "短大写碎片"); continue
                # 单词短 token 合法性（2026-09-09 "tion" 碎片案例）：单词形态且
                # ≤5 字母的关键词必须以独立词形态字面出现在原文——LLM 偶发产出的
                # 词缀碎片在原文中并不独立存在（多词概念仍走软偏好不强制字面）
                if len(kw.split()) == 1 and len(kw) <= 5 and full_text:
                    if not _re.search(rf"(?:^|[^A-Za-z]){_re.escape(kw)}(?:[^A-Za-z]|$)",
                                      full_text, _re.IGNORECASE):
                        dropped.append({"keyword": kw, "reason": "原文无此独立词"}); _log_keyword_drop("en", kw, "原文无此独立词"); continue
            else:
                if not (2 <= len(kw) <= 24):
                    dropped.append({"keyword": kw, "reason": "长度越界"}); continue
                # 中文虚词/自指词防线（词表外置 lexicon_zh.json，热加载）
                if kw in _lex_zh["block"]:
                    dropped.append({"keyword": kw, "reason": "中文虚词"}); _log_keyword_drop("zh", kw, "中文虚词"); continue
            if kw in stopwords or key in {s.lower() for s in stopwords}:
                dropped.append({"keyword": kw, "reason": "停用词"}); continue
            # 裸泛词让位（2026-09-15 用户定调：damage 这类无领域区分度的单词不该
            # 独立成关键词——标了等于没标还挤占名额）。让位制而非一刀切阻断：
            # 本批存在以该词为成分的更长完整术语（damage identification）时裸词
            # 让位；只有裸词时保留（避免误伤 bridge 类研究对象词）。组合词不受影响。
            if is_en and len(kw.split()) == 1 and key in _lex_en.get("generic", frozenset()):
                _as_part = any(key != o.lower() and key in o.lower().split()
                               for o in (str(x.get("keyword") if isinstance(x, dict) else x) for x in raw_kw))
                if _as_part:
                    dropped.append({"keyword": kw, "reason": "裸泛词让位"})
                    _log_keyword_drop("en", kw, "裸泛词让位"); continue
            if len(kw) <= 1:
                dropped.append({"keyword": kw, "reason": "单字"}); continue
            if key in seen:
                dropped.append({"keyword": kw, "reason": "重复"}); continue
            seen.add(key)
            cleaned.append({"keyword": kw, "weight": float(w) if w is not None else 0.5, "type": t})
        # 包含去重：若 A 是 B 的子串且都已选，丢掉较长的 B（保留简洁基础词）
        cleaned.sort(key=lambda x: x["weight"], reverse=True)
        final, kept_keys = [], set()
        for c in cleaned:
            kw = c["keyword"]
            # 若已保留的某个更短词是 kw 的子串，丢 kw
            if any(k != kw and k in kw for k in kept_keys):
                dropped.append({"keyword": kw, "reason": "被基础词包含"}); continue
            # 若 kw 是已保留某词的子串，用 kw 替换那个更长的
            to_remove = [k for k in kept_keys if kw != k and kw in k]
            for k in to_remove:
                kept_keys.discard(k)
                final = [x for x in final if x["keyword"] != k]
            kept_keys.add(kw)
            final.append(c)
        # 类型分槽与每类最优筛选推迟到融合后（_execute_keyword 内按两层置信度选每类前1），
        # 这里仅做基础子串去重并放行全部候选，让两层置信度有完整选择空间。
        final.sort(key=lambda x: x["weight"], reverse=True)
        if len(final) > 20:
            dropped.extend([{"keyword": c["keyword"], "reason": "候选超20"} for c in final[20:]])
            final = final[:20]
        return final, dropped

    def _execute_domain_classification(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """专业领域分类：用户指定领域(domain_code 01-32) → LLM 在该领域语境下选 CLC 细码 → resolve_code + 层级细化。

        领域由用户在 params.domain_code 指定（必选），LLM 不再判领域，只在指定领域语境下选 CLC。
        复用 ac_zh 的 resolve_code 防幻觉 + 二阶段层级细化。
        """

        result = SemanticResult(code=code, name=fp.name)
        title, abstract, keywords, full_text = self._parse_paper_input(request)
        if not (title or abstract or full_text):
            raise ValueError("专业领域分类需提供 标题/摘要（text 传 paper JSON）")

        # 用户指定领域（必选，params.domain_code = 01-32）
        _raw_dc = (request.params or {}).get("domain_code", "")
        # 兼容 int 传入：其它客户端可能传数字 9；str 化后与 domain_list 的 "09" 按整数等价匹配
        domain_code = (_raw_dc if isinstance(_raw_dc, str) else str(_raw_dc)).strip()
        domain_list = getattr(rule, "domain_list", []) or []
        valid_domain = None
        for d in domain_list:
            d_code = d.split()[0]
            if d_code == domain_code:
                valid_domain = d
                break
            # 容错前导零：前端传 "09" 可能被解析去零成 "9"，二者按整数等价匹配
            try:
                if int(d_code) == int(domain_code):
                    valid_domain = d
                    break
            except (ValueError, TypeError):
                pass
        if valid_domain is None:
            raise ValueError(f"ac_domain 需在 params.domain_code 指定领域(01-32)，got '{domain_code}'")
        domain_name = valid_domain.split(None, 1)[1] if len(valid_domain.split(None, 1)) > 1 else valid_domain

        # ── 用户上传资源消费（2026-09-15 需规落实）──
        # ① 领域分类规则 = 该专业领域的三级中图分类体系（答案空间替换）：
        #    分类号只落用户体系内，resolve_code/路径从用户体系取
        # ② 人工标注训练数据 = few-shot 样本对（文本+中文标签），校准标引风格
        _resolved = (request.params or {}).get("resolved_resources") or {}
        top_k = int((request.params or {}).get("top_k", 5))
        _rules_res = _resolved.get("domain_classification_rules") if isinstance(_resolved, dict) else None
        _train_res = _resolved.get("manually_labeled_training_data") if isinstance(_resolved, dict) else None
        _rules_entries = []
        _train_boost = {}
        _keywords_eff_train = keywords
        custom_retriever = None
        custom_candidates: list = []
        fewshot_text = ""
        if isinstance(_rules_res, dict):
            # 领域分类规则 → 用户作用域检索器（同 zh/en-classify 的小表路径）
            _rules_entries = self._load_rules_taxonomy(_rules_res)
            if _rules_entries:
                from infrastructure.rag.clc_retriever import CLCRetriever
                custom_retriever = self._build_scope_retriever_from_entries(_rules_entries)
                if custom_retriever is not None:
                    custom_candidates = custom_retriever.retrieve(
                        title, abstract, keywords, k=max(top_k, 12))
                    logger.info("领域分类规则作用域检索器生效：%d 个用户条目", len(_rules_entries))
        if isinstance(_train_res, dict):
            # 人工标注训练数据 → 一次解析，两处使用（few-shot + 相似度增强）
            _train_pairs = self._parse_training_pairs(_train_res)
            if _train_pairs:
                fewshot_text = "\n".join(
                    f"- 文本「{t[:120]}」→ 分类「{l}」" for t, l in _train_pairs[:5])
                logger.info("人工标注训练数据生效：%d 对", len(_train_pairs))
                # 相似度增强：输入文本与训练样本语义相似 → 标签类别并入检索
                _train_boost = self._compute_training_similarity(
                    _train_pairs, f"{title or ''} {abstract or ''}")
                if _train_boost:
                    _boost_terms = " ".join(_train_boost["matched_labels"])
                    _kw_str = " ".join(keywords) if isinstance(keywords, list) else str(keywords or "")
                    _keywords_eff_train = (_kw_str + " " + _boost_terms).strip()
                    logger.info("训练数据相似命中 %d 个，标签增强：%s",
                                _train_boost["match_count"], _boost_terms[:60])

        # LLM 在指定领域语境下选 CLC 细码（领域由用户指定，LLM 不判领域）；全文输入时附全文
        system_prompt = self._system_prompt(rule, request).replace("{domain}", valid_domain)
        user_prompt = self._render_classification_user_prompt(title, abstract, keywords, full_text)
        if custom_candidates:
            # 用户三级中图分类体系 → 候选限定 + few-shot 样本注入
            _lines = [f"[{i+1}] {c.get('clc_code')} {c.get('clc_name')}"
                      + (f" | 路径: {' > '.join(c.get('path_names') or [])}" if c.get("path_names") else "")
                      for i, c in enumerate(custom_candidates)]
            user_prompt += (
                "\n\n【重要】本次使用用户自定义领域分类体系（非内置中图法）。"
                "clc_code 必须且只能从下列候选分类号中选择，"
                "禁止使用任何不在候选中的分类号（包括你已知的中图法分类号）：\n"
                + "\n".join(_lines))
        if fewshot_text:
            user_prompt += "\n\n【人工标注样本（用户上传）】以下是已标注的训练样本，当输入文本与某样本内容相似时，优先采用该样本的分类号作为 clc_code 输出：\n" + fewshot_text
        if _train_boost:
            _pref = "\n".join(f"→ 优先考虑：{l}" for l in _train_boost.get("matched_labels") or [])
            user_prompt += "\n\n【训练数据匹配推荐】以下分类号来自与输入文本语义相似的标注样本（相似度≥0.45），应作为首选分类号：\n" + _pref
        data = self._glm.chat_json(system_prompt, user_prompt, timeout=120.0, max_tokens=1500)
        data = data.get("data", data) if isinstance(data, dict) else {}
        clc_code = (data.get("clc_code") or "").strip()
        reason = data.get("selection_reason", "")

        # 训练数据权威覆盖（2026-09-15）：最高相似度样本的分类号优先于 LLM 泛判
        # ——内置给 TU3（粗），训练标注说这类文本是 TU31（细）→ 用 TU31
        if _train_boost and _train_boost.get("matched_examples"):
            _top = max(_train_boost["matched_examples"], key=lambda x: x.get("similarity", 0))
            _top_code = str(_top.get("label") or "").split()[0] if _top.get("label") else ""
            _top_sim = float(_top.get("similarity") or 0)
            if _top_code and _top_sim >= 0.50:
                # 仅当训练码是 LLM 码的同系（LLM=TU3, 训练=TU31 → 细化）或不同（覆盖）时采用
                if not clc_code or clc_code == _top_code or _top_code.startswith(clc_code) or clc_code.startswith(_top_code):
                    if _top_code != clc_code:
                        reason = f"[训练数据覆盖 {_top_sim:.2f}→{_top_code}] " + reason
                    clc_code = _top_code
                    # 训练标签权威输出：直接用训练标签构建分类对象，不走内置 resolve
                    # ——内置索引可能没有训练标签的细码（如 TU31），resolve 会退到粗码
                    _top_label = str(_top.get("label") or "")
                    _top_name = _top_label.split(None, 1)[1] if len(_top_label.split(None, 1)) > 1 else _top_label
                    # 推断层级路径：TU31 → [TU, TU3, TU31]（字母=一级，+1数字=二级）
                    import re as _re_t
                    _m_t = _re_t.match(r'([A-Z]+)(\d*)', _top_code)
                    _letters = _m_t.group(1) if _m_t else _top_code
                    _digits = _m_t.group(2) if _m_t else ""
                    _l1 = _letters
                    _l2_code = _letters + _digits[:1] if _digits else _letters
                    # 二级名称：优先从用户规则查，查不到用码的前缀推导
                    _l2_name = ""
                    if _rules_entries:
                        _l2_entry = next((e for e in _rules_entries
                                          if e.get("clc_code") == _l2_code), None)
                        if _l2_entry:
                            _l2_name = str(_l2_entry.get("clc_name") or "")
                    if not _l2_name:
                        _l2_name = "相关子类"  # 兜底名称（不含码，避免 normalizer 拼接后重复）
                    clc_obj = {
                        "clc_code": _top_code, "clc_name": _top_name,
                        "classification_path": _top_label,
                        "path_codes": [_l1, _l2_code, _top_code],
                        "path_names": [domain_name, _l2_name, _top_name],
                        "confidence": round(min(0.85 + _top_sim * 0.10, 0.95), 3),
                    }
                    result.success = True
                    result.data = {
                        "document_title": title,
                        "domain_code": valid_domain.split()[0],
                        "domain_name": domain_name,
                        "clc_classification": clc_obj,
                        "rag_top_k_candidates": [],
                        "selection_reason": reason,
                        "alignment_check": {"domain_valid": True,
                                            "training_data_override": True},
                        **({"training_data_effect": _train_boost} if _train_boost else {}),
                    }
                    result.confidence = clc_obj.get("confidence")
                    result.raw = json.dumps(result.data, ensure_ascii=False)
                    return result

        # 仅在远端模型成功后加载体积较大的 CLC 检索索引。
        retriever = custom_retriever if custom_retriever is not None else \
            self._resolve_clc_retriever(code, request, cross_lingual=False)
        _retrieval_kw = _keywords_eff_train if _train_boost else keywords
        candidates = custom_candidates if custom_candidates else \
            retriever.retrieve(title, abstract, _retrieval_kw, k=top_k)

        # 第二层校验：resolve_code + 二阶段层级细化
        refine = (request.params or {}).get("refine", True)
        proposed_entry = retriever.resolve_code(clc_code)
        if proposed_entry is None:
            raise RuntimeError("GLM-5.2 返回的领域分类号无法在 CLC 知识库中验证")
        if refine and proposed_entry is not None:
            picked = self._refine_main_hierarchy(title, abstract, keywords, proposed_entry, retriever)
            if picked and picked != clc_code:
                reason = ("[细化 %s→%s] " % (clc_code, picked)) + reason
                clc_code = picked
        main_entry = retriever.resolve_code(clc_code)
        if main_entry is None:
            raise RuntimeError("GLM-5.2 返回的领域分类号无法在 CLC 知识库中验证")
        clc_obj = self._entry_to_obj(main_entry, candidates) if main_entry else None
        if clc_obj:
            # 置信度计算方法：以"CLC 库验证通过 + 层级细化通过 + 用户指定领域约束 + LLM 推理(selection_reason)"
            # 作为可靠分类基线 0.85；bge 检索命中(LLM 选择也被召回=交叉佐证)则加成，未命中不降级。
            # 不用 bge 原始相似度当主信号——医疗短摘要 bge 分常聚簇 0.46、区分度低且常漏召回 LLM 的正确
            # 选择，据此惩罚会使正确分类显示 0.466/0.7"很低"，与 zh-classify 的 LLM 自报 0.9+ 口径不一致。
            # 命中加成：rank 越靠前越高(rank0 +0.10) + bge 高分(>0.5)小幅加成，封顶 0.95。
            chosen_code = main_entry["clc_code"]
            match = next((c for c in candidates if c.get("clc_code") == chosen_code), None)
            if match is not None:
                rank = next((i for i, c in enumerate(candidates) if c.get("clc_code") == chosen_code),
                            len(candidates))
                bge = float(match.get("score") or 0.0)
                bge_bonus = max(0.0, bge - 0.5) * 1.0          # bge>0.5 才加成
                rank_bonus = max(0.0, 0.10 - rank * 0.02)        # rank0 +0.10, rank1 +0.08, rank2 +0.06…
                clc_obj["confidence"] = round(min(0.85 + rank_bonus + bge_bonus, 0.95), 3)
            else:
                # LLM 选择未命中 RAG 候选，但 CLC 库验证 + 层级细化 + 领域约束通过：仍给可靠基线 0.85
                clc_obj["confidence"] = 0.85

        out = {
            # 文献题目回传：前端 recordsOf 第一列取 document_title，缺失会落到 file_name/input_id
            "document_title": title,
            "domain_code": valid_domain.split()[0] if valid_domain else domain_code,
            "domain_name": domain_name,
            "clc_classification": clc_obj,
            "rag_top_k_candidates": [self._candidate_to_obj(c, with_rank=True) for c in candidates],
            "selection_reason": reason,
            "alignment_check": {"domain_valid": valid_domain is not None,
                                "clc_code_exists_in_rag": main_entry is not None,
                                "path_copied_from_rag": True},
            # 训练数据生效指纹（2026-09-15：测试人员需要可观察的独立效果）
            **({"training_data_effect": _train_boost} if _train_boost else {}),
        }
        result.success = True
        result.data = out
        result.confidence = clc_obj.get("confidence") if clc_obj else None
        result.raw = json.dumps(out, ensure_ascii=False)
        return result

    @staticmethod
    def _parse_json_sections(raw: str):
        """解析 JSON 结构文本 → (展平正文, [(start, end, 章节路径)])。

        兼容常见形态：list[{title, content}]、{sections|chapters:[...]}、嵌套
        sections/subsections/children。解析失败返回 None（回落自动识别路径）。
        章节路径供研究问题溯源精确定位（替代标题启发式重建）。
        """
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
        sections: list = []  # [(path, content)]

        def _content_of(it: dict):
            for key in ("content", "text", "body", "正文", "content_text", "full_text"):
                value = it.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            return ""

        def _title_of(it: dict) -> str:
            for key in ("title", "section", "chapter", "heading", "name", "章节", "标题"):
                value = it.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""

        def _walk(node, prefix: str):
            items = []
            if isinstance(node, list):
                items = node
            elif isinstance(node, dict):
                for key in ("sections", "chapters", "items", "data"):
                    if isinstance(node.get(key), list):
                        items = node[key]
                        break
                else:
                    items = [node]
            for it in items:
                if isinstance(it, str):
                    if it.strip():
                        sections.append((prefix or "正文", it))
                    continue
                if not isinstance(it, dict):
                    continue
                title = _title_of(it)
                path = f"{prefix} > {title}" if (prefix and title) else (title or prefix or "正文")
                content = _content_of(it)
                if content:
                    sections.append((path, content))
                for key in ("sections", "chapters", "subsections", "children"):
                    if isinstance(it.get(key), list):
                        _walk(it[key], path)

        _walk(data, "")
        if not sections:
            return None
        parts: list = []
        spans: list = []
        pos = 0
        for path, content in sections:
            parts.append(content)
            spans.append((pos, pos + len(content), path))
            pos += len(content) + 1  # 展平时以换行分隔
        return "\n".join(parts), spans

    def _execute_rq_identify(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """研究问题句识别：LLM 识别 RQ 句+短语 → 后置字面校验（防幻觉）。

        输入为摘要文本（text）。LLM 直接返回 verbatim 句子+短语，后置引擎强制：
        句子须为摘要字面子串、短语须为句子字面子串（drop 不符的）。中英双语按 lang 切 prompt。
        """
        result = SemanticResult(code=code, name=fp.name)
        abstract = (request.text or "").strip()
        # 需规输入项 text_format_requirement：纯文本 / 章节结构文本 / JSON 结构文本 / 自动识别。
        # 显式声明时按声明处理（见下方 full_text 与溯源分支）；JSON 结构文本解析
        # 章节映射，问题溯源用精确章节路径替代标题启发式重建。
        _format_req = str((request.params or {}).get("text_format_requirement") or "").strip()
        _json_spans: list = []
        if abstract[:1] in "{[" and _format_req in ("", "自动识别", "JSON 结构文本"):
            _parsed = self._parse_json_sections(abstract)
            if _parsed:
                abstract, _json_spans = _parsed
        # 全文输入支持：文件路径或 mineru markdown 全文 → 截断 8000 字直送 LLM
        # （LLM 优先版：从全文找研究问题，不只看摘要）；字面校验对同一截断文本
        full_text = None
        if abstract and os.path.exists(abstract) and abstract.lower().endswith(('.pdf', '.md')):
            from infrastructure.document_parser.mineru_reader import process_to_text
            doc = process_to_text(abstract)
            full_text = doc.get("full_text", "") or ""
        if not full_text and self._looks_like_full_document(abstract):
            full_text = abstract
        if full_text:
            abstract = full_text[:8000]
        elif not abstract:
            # 兼容 paper JSON 输入
            _, abstract, _, _ = self._parse_paper_input(request)

        # mineru 回退函数（情况1 取文空 + 情况2 LLM判0 共用）：原始PDF mineru全量重抽
        def _rq_mineru_refallback(_src_path):
            from pathlib import Path as _Path
            from infrastructure.document_parser.upload_reader import extract_bytes as _eb
            from infrastructure.document_parser.mineru_api_client import _count_pages as _cp
            from infrastructure.document_parser.concurrency_pool import get_page_budget_pool as _gpp
            _content = _Path(_src_path).read_bytes()
            _pages = _cp(_content)
            _pool = _gpp()
            _pool.acquire(_pages)
            try:
                _mtxt = _eb(_content, _Path(_src_path).name, light=False) or ""
            finally:
                _pool.release(_pages)
            if not _mtxt:
                return None, None
            _ft = _mtxt if self._looks_like_full_document(_mtxt) else None
            return (_ft or _mtxt)[:8000], _ft

        # 情况1：PyMuPDF 取文为空 → 回退 mineru 重抽（pymupdf没取到内容为空也回退）
        _src = (request.params or {}).get("_source_pdf_path")
        if not abstract and _src and os.path.exists(_src):
            logger.info("rq-detect light 取文为空,回退 mineru 重抽: %s", _src)
            _ab, _ft = _rq_mineru_refallback(_src)
            if _ab:
                abstract, full_text = _ab, _ft
        if not abstract:
            raise ValueError("研究问题识别需提供 text 字段（摘要文本）；mineru 重抽仍空")

        # 显式声明「章节结构文本」：强制按结构化全文处理（标题层级路径溯源启用），
        # 不依赖 _looks_like_full_document 启发式是否命中
        if _format_req == "章节结构文本" and abstract:
            full_text = abstract
        # JSON 结构文本：展平文本直送 LLM；溯源优先用章节 spans，full_text 仅供
        # 兜底（spans 未命中时归「全文」而非「摘要」）
        if _json_spans:
            full_text = abstract
        lang = (request.params or {}).get("lang", getattr(rule, "lang", "") or "zh")
        system_prompt = self._system_prompt(rule, request, lang)
        is_en = lang == "en"
        obj = {"abstract": abstract,
               "说明": ("Identify research-question sentences; for each give: sentence (verbatim substring of abstract), "
                        "phrase (verbatim substring of sentence), implication (one-sentence plain paraphrase of the implied "
                        "research question, NOT verbatim), expression_type ('explicit' for direct problem/gap cues or "
                        "'implicit' for object/goal statements), question_type ('mechanism' for investigating mechanism/relationship, 'objective' for improving/solving/achieving a goal, 'method' for building/proposing a method to solve a problem, 'validation' for verifying/evaluating effectiveness), normalized_question (standard self-contained RQ statement,"
                        "paraphrase OK), research_object (core object/subject, noun phrase, verbatim preferred), constraints "
                        "(array of boundary conditions/scenarios, empty if none), role ('main' for the overarching RQ or 'sub' "
                        "for a refinement of it), parent_index (0-based index of the parent main in data; only for sub). "
                        "Order: main first, then its subs. Return JSON "
                        "{data:[{sentence,phrase,implication,expression_type,question_type,normalized_question,research_object,constraints,role,parent_index}]}.") if is_en
               else ("识别研究问题句；每条给：sentence(摘要字面子串)、phrase(句子字面子串)、"
                     "implication(一句话释义隐含研究问题，允许概括非字面)、expression_type(explicit=显式问题/缺口句，"
                     "implicit=隐式目标/对象句)、question_type(mechanism=机理型探究影响机制关系,objective=目标型为提高解决实现,method=方法型构建提出方法解决问题非方法步骤句,validation=验证型验证有效性评估效果)、normalized_question(规范化研究问题表述，主谓宾完整可独立理解，允许改写)、"
                     "research_object(研究对象，核心对象/主体名词短语，原文原词优先，无则空串)、"
                     "constraints(约束条件/限定场景数组，无则空数组)、role(main=统摄全篇的主研究问题，sub=主问题的子问题/细化方面)、"
                     "parent_index(子问题填其父main在data中的0基索引，main不填)。顺序：先main后其sub。"
                     "返回 JSON {data:[{sentence,phrase,implication,expression_type,question_type,normalized_question,research_object,constraints,role,parent_index}]}。")}
        user_prompt = ("Identify research questions in this abstract:\n" if is_en
                       else "请识别以下摘要的研究问题句：\n") + json.dumps(obj, ensure_ascii=False, indent=2)
        def _llm_extract_once():
            """单次 GLM 调用 + 后置字面校验，返回 (cleaned, dropped)。"""
            data = self._glm.chat_json(system_prompt, user_prompt, timeout=120.0, max_tokens=2500)
            raw = data.get("data", data) if isinstance(data, dict) else []
            if not isinstance(raw, list):
                raise RuntimeError("GLM-5.2 未返回有效研究问题列表")

            # 后置字面校验（sentence/phrase 须字面；implication 允许概括，不校验）
            cleaned, dropped = [], []
            seen_sent = set()
            for item in raw[:6]:
                if not isinstance(item, dict):
                    continue
                sent = (item.get("sentence") or "").strip()
                phrase = (item.get("phrase") or "").strip()
                implication = (item.get("implication") or "").strip()
                expr_raw = str(item.get("expression_type") or item.get("type") or "").strip().lower()
                expression_type = "explicit" if expr_raw.startswith("exp") else ("implicit" if expr_raw.startswith("imp") else "")
                if not sent:
                    continue
                start = self._ws_substr_find(abstract, sent)
                if start < 0:
                    dropped.append({"sentence": sent[:40], "reason": "非摘要原文(空白不敏感匹配失败)"}); continue
                if phrase and phrase not in sent:
                    dropped.append({"phrase": phrase[:40], "reason": "非句子原文"}); phrase = ""
                if sent in seen_sent:
                    continue
                seen_sent.add(sent)
                phrase_start = sent.find(phrase) if phrase else -1
                abstract_label = "Abstract" if is_en else "摘要"
                llm_section = (item.get("source_section") or "").strip()
                if _json_spans:
                    # JSON 结构文本：句子在展平正文中的位置 → 精确章节路径
                    heading_sec = next(
                        (path for s, e, path in _json_spans if s <= start < e), "")
                elif full_text and start is not None and start >= 0 and _format_req != "纯文本":
                    # 章节结构文本/自动识别：标题层级启发式重建；
                    # 纯文本声明则跳过（无结构可溯源）
                    heading_sec = self._rq_detect_section(full_text, start, abstract_label)
                else:
                    heading_sec = ""
                if heading_sec:
                    # 结构化文档：优先用真实标题层级路径（如“（一）立项依据 / 1．研究背景与动机”）
                    source_sections = [heading_sec]
                elif llm_section and _format_req != "纯文本":
                    # 无明确标题（如整篇无 Abstract/引言 字样）：用 LLM 按段落语义判定的章节。
                    # 纯文本声明时跳过（用户声明无结构，LLM 从可见文字猜章节不可靠）
                    source_sections = [llm_section]
                elif full_text:
                    source_sections = ["全文"]
                else:
                    source_sections = [abstract_label]
                try:
                    conf_val = float(item.get("confidence"))
                    conf_val = max(0.0, min(1.0, conf_val))
                    conf_val = round(conf_val, 2)
                except (TypeError, ValueError):
                    conf_val = None
                # 问题类型（LLM 产出，规范化为英文枚举）
                qt_raw = str(item.get("question_type") or "").strip().lower()
                if qt_raw.startswith("mec"): question_type = "mechanism"
                elif qt_raw.startswith("obj"): question_type = "objective"
                elif qt_raw.startswith("met"): question_type = "method"
                elif qt_raw.startswith("val"): question_type = "validation"
                else: question_type = ""
                # 结构化分解字段（LLM 产出，允许概括非字面，不做字面校验）
                normalized_q = (item.get("normalized_question") or "").strip()
                research_obj = (item.get("research_object") or "").strip()
                _cons = item.get("constraints")
                if isinstance(_cons, str):
                    constraints_list = [c.strip() for c in _cons.split("；;，,") if c.strip()] if _cons.strip() else []
                elif isinstance(_cons, list):
                    constraints_list = [str(c).strip() for c in _cons if str(c).strip()]
                else:
                    constraints_list = []
                role_raw = str(item.get("role") or "").strip().lower()
                role = "sub" if role_raw.startswith("sub") else ("main" if role_raw.startswith("main") else "")
                parent_idx = item.get("parent_index")
                try:
                    parent_idx = int(parent_idx) if parent_idx is not None else None
                except (TypeError, ValueError):
                    parent_idx = None
                cleaned.append({
                    "sentence": sent,
                    "phrase": phrase,
                    "implication": implication,
                    "expression_type": expression_type,
                    "question_type": question_type,
                    "source_sections": source_sections,
                    "sentence_index": len(cleaned),
                    "start": start if start >= 0 else None,
                    "end": start + len(sent) if start >= 0 else None,
                    "phrase_start": (start + phrase_start) if start >= 0 and phrase_start >= 0 else None,
                    "phrase_end": (start + phrase_start + len(phrase)) if start >= 0 and phrase_start >= 0 else None,
                    "normalized_question": normalized_q,
                    "research_object": research_obj,
                    "constraints": constraints_list,
                    "role": role,
                    "parent_index": parent_idx,
                    "confidence": conf_val,
                })
            return cleaned, dropped

        # LLM 非确定性：结果为空(cleaned=0)则重试,最多 3 次,取首个非空。
        # 覆盖两种 0：GLM 漏抽(raw=[]) 与 返了句被字面校验丢光；救回摇摆篇
        # （如英文 ML 论文有时抽"we explore…"有时漏抽），稳定空篇(摘要本无可识别 RQ)3 次后接受空。
        cleaned, dropped = [], []
        for _attempt in range(3):
            cleaned, dropped = _llm_extract_once()
            if cleaned:
                break
            if _attempt < 2:
                logger.info("rq-detect 结果为空,重试第 %d/3 次", _attempt + 2)
        # 情况2：PyMuPDF 取到内容但 LLM 没判出研究问题句 → 回退 mineru 重抽重判
        # （light 可能漏引言/RQ 段，mineru 全文能补；批量并发靠 /files group + PageBudgetPool）
        if not cleaned:
            _src = (request.params or {}).get("_source_pdf_path")
            if _src and os.path.exists(_src) and len(abstract) < 6000:
                # 文本较短才重抽(疑似局部抽取);已是全文时重抽仅白耗一遍 mineru 解析
                logger.info("rq-detect LLM 判 0,文本较短(%d字),回退 mineru 重抽重判: %s",
                            len(abstract), _src)
                _ab, _ft = _rq_mineru_refallback(_src)
                if _ab:
                    full_text, abstract = _ft, _ab
                    obj = {"abstract": abstract, "说明": obj["说明"]}
                    user_prompt = (("Identify research questions in this abstract:\n" if is_en
                                    else "请识别以下摘要的研究问题句：\n")
                                   + json.dumps(obj, ensure_ascii=False, indent=2))
                    for _attempt in range(3):
                        cleaned, dropped = _llm_extract_once()
                        if cleaned:
                            break
                        if _attempt < 2:
                            logger.info("rq-detect mineru 重抽后仍空,重试第 %d/3 次", _attempt + 2)
        # 仍空(摘要本无可识别 RQ)则 cleaned=[],交由后续去重/兜底逻辑接受空结果

        # 近重复去重 + 主问题兜底
        # ① 同句的截断/扩写版（子串且长度比≥0.5）保留更长句、去较短句
        #   （LLM 偶把同一句的整句与截断版分别当 main/sub，如 ch4 整句+其子串）
        drop_idx = set()
        for _a in range(len(cleaned)):
            if _a in drop_idx:
                continue
            _sa = cleaned[_a]["sentence"]
            for _b in range(_a + 1, len(cleaned)):
                if _b in drop_idx:
                    continue
                _sb = cleaned[_b]["sentence"]
                _lo, _hi = (_sa, _sb) if len(_sa) <= len(_sb) else (_sb, _sa)
                if _lo and _lo in _hi and len(_lo) >= len(_hi) * 0.5:
                    drop_idx.add(_a if len(_sa) <= len(_sb) else _b)
        if drop_idx:
            cleaned = [c for k, c in enumerate(cleaned) if k not in drop_idx]
        for _k, c in enumerate(cleaned):
            c["sentence_index"] = _k
        # ② 主问题兜底：若无任何 role=main（含单条却被标 sub 的孤儿，如 19.pdf），
        #   强制首条为 main、parent 清空，避免层级悬空
        if cleaned and not any(c.get("role") == "main" for c in cleaned):
            cleaned[0]["role"] = "main"
            cleaned[0]["parent_index"] = None

        result.success = True
        result.data = cleaned
        result.evidence = [{"dropped": d} for d in dropped] if dropped else []
        result.raw = json.dumps({"rq": cleaned, "n_dropped": len(dropped)}, ensure_ascii=False)
        return result

    @staticmethod
    def _parse_source_sections(content: str):
        """从 LLM 生成的 content 解析 '**来源章节：**X；Y；Z' 为 [X, Y, Z]。

        summary_prompt 规则#6 要求每类语步末尾标注来源章节；单调用模式下用此解析
        取得真实章节标题（取代笼统的"全文"）。解析失败返回 []。
        """
        import re as _re
        if not content:
            return []
        m = _re.search(r'\*\*来源章节[：:]\*\*\s*([^\n]+)', content) \
            or _re.search(r'来源章节[：:]\s*([^\n]+)', content)
        if not m:
            return []
        raw = _re.sub(r'\*+$', '', m.group(1)).strip()
        out = []
        for p in _re.split(r'[；;,，]', raw):
            p = p.strip().strip('*').strip()
            if p and p not in ('无', '全文') and p not in out:
                out.append(p)
        return out

    @staticmethod
    def _ws_substr_find(hay: str, needle: str) -> int:
        """空白不敏感子串查找：返回 needle 在 hay 中的起始字符偏移，找不到返 -1。
        PDF 抽取常在句中插入换行/多空格：英文词间换行（"called\\ngenerative"）、
        中文词内换行（"实现路径"→"实\\n现路径"，sort=True 与版面感知分栏读取都会拆）。
        LLM 返回干净句字面不匹配致整条 RQ 被丢（多栏/会议论文 + 分栏读取的文本因此
        整篇 0 RQ）。正则策略：
        - needle 中实际空白 → \\s+（保留词边界，防英文 "the cat" 误匹配 "thecat"）；
        - 相邻非空白字符间插 \\s*（容忍中文词内换行等任意位置任意空白）；
        要求非空白字面按序一致（防 LLM 改词仍能拦下，仅放松空白匹配）。
        """
        import re as _re
        if not needle:
            return -1
        tokens = []  # 'ws' 或 ('lit', escaped_char)
        for ch in needle:
            if ch.isspace():
                if tokens and tokens[-1] == "ws":
                    continue
                tokens.append("ws")
            else:
                tokens.append(("lit", _re.escape(ch)))
        if not tokens:
            return -1
        parts = []
        for i, tok in enumerate(tokens):
            if tok == "ws":
                parts.append(r"\s+")
            else:
                parts.append(tok[1])
                if i + 1 < len(tokens) and tokens[i + 1] != "ws":
                    parts.append(r"\s*")
        m = _re.search("".join(parts), hay)
        return m.start() if m else -1

    @staticmethod
    def _rq_detect_section(full_text: str, start: int, abstract_label: str = "摘要") -> str:
        """研究问题句溯源：返回字符偏移 start 处的完整章节路径（一级标题 / 二级 / 三级 / 叶子）。

        复用基金语步 _heading_aware_chunks 的层级推断规则，保证两处"来源章节"口径一致：
        - （一）/（二）… 或文档标题 → 一级；1．/2. → 二级；3.1/4.3 → 三级；(1)/第N步 → 叶子
        - 参考文献等结构性章节独立成一级
        单 # 的文档标题（非章节词）不计入路径，避免污染摘要区溯源。
        摘要区（start 在任何章节标题之前，但全文存在章节标题）返回 abstract_label，
        即便原文未写"摘要/Abstract"标题也由系统补上；全文无任何章节标题则返回空串。
        """
        import re as _re
        if not full_text or start is None or start < 0:
            return ""
        h1 = h2 = h3 = leaf = ""
        found = ""
        pos = 0

        def _path():
            parts = [p for p in [h1, h2, h3, leaf] if p]
            return " / ".join(parts)

        def _is_section_word(t):
            return bool(_re.match(r'^（[一二三四五六七八九十]+）', t)
                        or _re.match(r'^\d+[．.](?!\d)', t)
                        or _re.match(r'^\d+\.\d+', t)
                        or _re.match(r'^第[一二三四五六七八九十百千\d]+[章节部分条篇]', t)
                        or any(t == b or t.startswith(b) for b in SemanticApplicationService._NON_CONTENT_SECTIONS))

        for line in full_text.split('\n'):
            if pos > start:
                break
            s = line.strip()
            mh = _re.match(r'^(#{1,6})\s+(.+)', s)
            mch = _re.match(r'^（[一二三四五六七八九十]+）', s) if not mh else None
            if mh:
                hashes = len(mh.group(1))
                title = mh.group(2).strip()
                t = title.rstrip("：:.").strip()
                # 单 # 且非章节词 → 文档标题，跳过（不污染摘要区路径）
                if hashes == 1 and not _is_section_word(t):
                    pos += len(line) + 1
                    continue
            elif mch:
                title = s
                t = title.rstrip("：:.").strip()
            else:
                pos += len(line) + 1
                continue
            if any(t == b or t.startswith(b) for b in SemanticApplicationService._NON_CONTENT_SECTIONS):
                h1, h2, h3, leaf = title, "", "", ""
            elif _re.match(r'^（[一二三四五六七八九十]+）', t):
                h1, h2, h3, leaf = title, "", "", ""
            elif _re.match(r'^\d+[．.](?!\d)', t):
                h2, h3, leaf = title, "", ""
            elif _re.match(r'^\d+\.\d+', t):
                h3, leaf = title, ""
            else:
                leaf = title
            found = _path()
            pos += len(line) + 1
        if found:
            return found
        # found 为空：句子在首个章节标题之前，或全文无任何章节标题。
        # 不再自行补 abstract_label——交由 LLM 的 source_section 按段落语义判定
        # （摘要 vs 引言/背景），避免把陈述缺口/动机的引言段误标为"摘要"。
        return ""

    @staticmethod
    def _is_non_content_source(path: str) -> bool:
        """来源路径是否含结构性章节（参考文献/致谢/附录等）——这类章节与任何语步无关，应剔除。"""
        if not path:
            return False
        return any(b in path for b in SemanticApplicationService._NON_CONTENT_SECTIONS)

    @staticmethod
    def _strip_source_annotation(content: str) -> str:
        """去掉 content 里的来源标注 + markdown # 标题标记，只留纯语步内容。"""
        import re as _re
        if not content:
            return content
        # 去掉"**来源章节：**xxx"到行尾（含可能的换行）
        content = _re.sub(r'\n*\*\*来源章节[：:]\*\*[^\n]*', '', content)
        content = _re.sub(r'\n*来源章节[：:][^\n]*', '', content)
        # 去 markdown 标题标记（#### 立项时拟达成的成果 → 立项时拟达成的成果）
        content = _re.sub(r'^#{1,6}\s+', '', content, flags=_re.MULTILINE)
        # 去 【】标签（【立项时拟达成的成果】 → 立项时拟达成的成果）
        content = _re.sub(r'^【([^】]+)】\s*', r'\1：', content, flags=_re.MULTILINE)
        return content.rstrip()

    @staticmethod
    def _extract_project_name(full_text: str) -> str:
        """从基金报告封面提取项目名称（用于覆盖文件名兜底）。

        结题报告封面有"项目名称：X"字段（优先）；立项申请书常以报告题名代项目名，
        取首个标题行并剥离"研究报告正文/申请书正文（YYYY版）"等后缀。提取失败返回空串。
        """
        import re as _re
        if not full_text:
            return ""
        head = full_text[:4000]
        m = _re.search(r'项目名称\s*[：:]\s*([^\n\r]{2,80})', head)
        if m:
            return m.group(1).strip().rstrip('。.').strip()
        # 兜底：首个非空标题行，剥离 markdown # 与"…研究报告正文/申请书正文（年版）"后缀
        for line in head.split('\n'):
            s = line.strip()
            if not s:
                continue
            s = _re.sub(r'^#{1,6}\s+', '', s)
            if len(s) < 4:
                continue
            if any(b in s for b in ('参照以下提纲', '国家自然科学基金', '资助项目结题', '成果报告')):
                continue
            s = _re.sub(r'(研究报告|申请书)?正文（\d+版）?\s*$', '', s).strip()
            s = s.rstrip('。.').strip()
            if len(s) >= 4:
                return s[:80]
        return ""

    # 结构性章节：与具体语步内容无关，识别时独立成段、不作溯源来源
    _NON_CONTENT_SECTIONS = ("参考文献", "致谢", "附录", "目录", "声明", "后记")

    @staticmethod
    def _heading_aware_chunks(full_text: str, chunk_size: int):
        """按章节标题切段，按编号推断层级，构建完整章节路径用于溯源。

        MinerU 常把标题压平成 `##`，层级信息丢失；这里按标题**编号**推断逻辑层级：
        - `（一）/（二）...` 或 `#` 文档标题 → 一级
        - `1． / 4．`（单数字+句点，非 N.M）→ 二级
        - `3.1 / 4.3`（数字.数字）→ 三级
        - `(1) / 第一步` 等 → 叶子（挂在当前二/三级下）
        - `参考文献/致谢/附录/目录` → 一级（独立成段，不继承上文层级，避免污染溯源路径）
        每段路径如 "（二）研究内容： / 4．研究方案 / 4.3 面向约束..."。
        返回 [{"text": str, "headings": [完整路径...]}]。
        """
        import re as _re
        lines = full_text.split('\n')
        segments = []
        h1 = h2 = h3 = leaf = ""
        cur = []

        def _path():
            parts = [p for p in [h1, h2, h3, leaf] if p]
            return " / ".join(parts) if parts else "全文"

        def _flush():
            if cur:
                segments.append({"path": _path(), "content": "\n".join(cur).strip()})

        def _infer_level(title):
            t = title.strip().rstrip("：:.").strip()
            # 参考文献等结构性章节独立成一级，不继承上文 h2/h3 语境，避免污染溯源路径
            if any(t == b or t.startswith(b) for b in SemanticApplicationService._NON_CONTENT_SECTIONS):
                return 1
            if _re.match(r'^（[一二三四五六七八九十]+）', t):
                return 1
            if _re.match(r'^\d+[．.](?!\d)', t):  # "1．" "4." 但非 "1.1"
                return 2
            if _re.match(r'^\d+\.\d+', t):  # "3.1" "4.3"
                return 3
            return 4  # (1)/第N步/其他 → 叶子

        for line in lines:
            s = line.strip()
            mh = _re.match(r'^#{1,6}\s+(.+)', s)
            mch = _re.match(r'^（[一二三四五六七八九十]+）', s) if not mh else None
            if mh or mch:
                title = mh.group(1).strip() if mh else s
                _flush(); cur = []
                cur.append(line)  # 保留标题行在内容里，让 LLM 看到章节边界
                lvl = _infer_level(title)
                if lvl == 1:
                    h1 = title; h2 = h3 = leaf = ""
                elif lvl == 2:
                    h2 = title; h3 = leaf = ""
                elif lvl == 3:
                    h3 = title; leaf = ""
                else:
                    leaf = title
            else:
                cur.append(line)
        _flush()

        # 聚合成 ≤chunk_size 的块，每块收集其包含段落的完整章节路径
        chunks = []; cur_text = []; cur_headings = []; cur_len = 0
        for seg in segments:
            seg_text = seg["content"]
            if not seg_text:
                continue
            if len(seg_text) > chunk_size:
                if cur_text:
                    chunks.append({"text": "\n".join(cur_text), "headings": list(dict.fromkeys(cur_headings))})
                    cur_text = []; cur_headings = []; cur_len = 0
                # 单段超阈值：按字数切分（不再整段成一块），带 overlap 窗口
                # 防 GLM 处理超长段时漏识别（如（二）研究内容 15859 字整段送
                # GLM 只识别研究目标，漏技术方案/预期成果）。overlap 800 字保证
                # 跨子块边界语步连续；reduce 阶段按 content 去重避免重复输出
                _sub_head = [seg["path"]] if seg["path"] and seg["path"] != "全文" else []
                _start = 0
                while _start < len(seg_text):
                    _end = min(_start + chunk_size, len(seg_text))
                    chunks.append({"text": seg_text[_start:_end], "headings": list(_sub_head)})
                    if _end >= len(seg_text):
                        break
                    _start = _end - 800  # overlap 回退 800 字
                continue
            if cur_len + len(seg_text) > chunk_size and cur_text:
                chunks.append({"text": "\n".join(cur_text), "headings": list(dict.fromkeys(cur_headings))})
                cur_text = []; cur_headings = []; cur_len = 0
            cur_text.append(seg_text)
            if seg["path"] and seg["path"] != "全文":
                cur_headings.append(seg["path"])
            cur_len += len(seg_text)
        if cur_text:
            chunks.append({"text": "\n".join(cur_text), "headings": list(dict.fromkeys(cur_headings))})
        for c in chunks:
            if not c["headings"]:
                c["headings"] = ["全文"]
        return chunks

    # 来源章节相关性二次筛选提示词（按下标判定，避免 LLM 改写/缩短来源标题）
    _SOURCE_FILTER_PROMPT = (
        "你是基金报告溯源审核专家。下面给出每个语步的内容及其候选来源章节（candidate_sources 字符串数组，有顺序）。\n"
        "请判断每个候选来源与该语步内容的相关性，返回判定为\"相关\"的候选在数组中的**下标**（0-based 整数）。\n"
        "判定\"相关\"= 该语步内容确实出自该章节、且该章节主题与该语步类别相符；\n"
        "判定\"不相关\"包括：仅背景提及、相邻章节误带入、参考文献/致谢/附录/目录/声明/后记等结构性章节，\n"
        "以及父章节与其子章节同为候选、且子章节已充分说明该语步内容时，父章节判为\"不相关\"（只留更具体的子，避免父子重复列来源）；\n"
        "以及**章节主题与语步类别不符的串语步来源**——例如：\n"
        " 「研究目标完成情况」「按计划执行情况」章节讲目标/进度完成，不得作为「应用价值」「技术实施方案」的来源；\n"
        " 「研究内容/研究方案/具体研究对象或方法的研究子节」章节讲技术内容，不得作为「研究目标」「预期成果」的来源；\n"
        " 「期刊论文」「人才培养」章节讲成果产出，不得作为「研究目标」「技术实施方案」的来源；\n"
        " 「研究意义」讲价值意义，不得作为「研究目标」「技术实施方案」的来源。\n"
        "⚠️ 不要改写来源标题，只返回下标数组；若全部不相关返回空数组 relevant_indices:[]。\n"
        "只输出JSON：{\"data\":{\"moves\":[{\"move_type\":\"立项依据\",\"relevant_indices\":[0,1]},...]}}"
    )

    # 来源章节汇总整理提示词：清理 LaTeX 拘留、归并同章节不同写法、按文档先后顺序排列。
    # 只整理格式（不改语义、不增删来源、不改语步归属）——区别于 _SOURCE_FILTER（按下标筛相关性）。
    _SUMMARIZE_SOURCES_PROMPT = (
        "你是基金报告溯源编辑。下面给出每个语步的来源章节（原始，可能含 LaTeX 公式拘留、"
        "同一章节多种写法、顺序混乱），以及全文章节先后顺序参考。\n"
        "请整理每个语步的来源章节，**只整理格式不改语义**：\n"
        "1. 清理 LaTeX 公式：$\\mathrm{Ti}_{3}\\mathrm{Al}$ → Ti3Al（化学式下标直接写数字，去 $、\\mathrm、{} 等标记，"
        "保留中文与章节编号），其他 LaTeX 命令同理转人读形式或去除；\n"
        "2. 归并同一章节的不同写法（如「中文摘要：」与「中文摘要（对项目的背景…）」合并为一条「中文摘要」）；\n"
        "3. 按全文章节先后顺序排列（参照给定的章节顺序参考，无参考则按编号自然顺序）；\n"
        "4. 修正并保留每条来源的完整层级路径（父章节 > 子章节，用 \" > \" 分隔）。路径层级须符合原文章节结构——修正切块阶段可能误串的层级：带编号子项（如「2.缺陷簇对TiAl」「1. Ti3Al相…」）是其上级（如「（三）缺陷簇」）的子节、不是独立二级标题，不应断开父子关系；「一、」「二、」「三、」是同一上级下的平级子节、互不为父子。参照全文章节顺序参考重建正确父子层级。单层章节即章节本身；\n"
        "5. ⚠️ 严禁增删来源、严禁改语步归属、严禁臆造新章节。\n"
        "只输出JSON：{\"data\":{\"moves\":[{\"move_type\":\"立项依据\",\"source_sections\":[\"1. 研究背景 > 1.1 ...\", ...]},...]}}"
    )

    @staticmethod
    def _format_sources_local(out_moves: list, all_headings: list) -> None:
        """代码版来源章节整理（2026-09-09 提速 + 层级截断 + 图注过滤）。

        LaTeX 清理 + 同章节去重归并 + 按全文章节序排序 + 层级截断（最多三级，
        去掉"第N步"/"(N)"叶子级）+ 图表注解过滤（"图N"/"表N"不作为来源）。
        """
        import re as _re

        # 图表注解模式：图3.6 / 表1 / Figure 1 / Table 2 等（不作为来源章节）
        _fig_pat = _re.compile(r'^(图|表|Figure|Fig\.?|Table)\s*\d+', _re.IGNORECASE)
        # 叶子级标题模式：第N步 / 第N章 / (N) / （N）等（截断保留上级）
        _leaf_pat = _re.compile(
            r'^第[一二三四五六七八九十\d]+[步步章阶段]'
            r'|^\(?\d+\)'
            r'|^（[一二三四五六七八九十]+）'
            r'|^Step\s+\d+', _re.IGNORECASE)

        def _clean_heading(h: str) -> str:
            h = _re.sub(r'\$[^$]+\$', '', h)
            h = _re.sub(r'\\mathrm\{([^}]*)\}', r'\1', h)
            h = _re.sub(r'\\[a-zA-Z]+', '', h)
            h = _re.sub(r'\{|\}', '', h)
            h = _re.sub(r'\s+', ' ', h)
            h = _re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', h)
            h = h.strip().rstrip('：:').strip()
            return h

        def _trim_and_filter(h: str) -> str:
            """截断到三级 + 移除路径中的图表注解部分。

            "父章节 / 图3.6xxx" → "父章节"（图注部分删除，保留上级）
            "图3.6xxx" → ""（纯图注，整条丢弃）
            "（二）内容 / 4.1 构建 / (1) 表征 / 第一步：编码" → "（二）内容 / 4.1 构建 / (1) 表征"
            """
            parts = [p.strip() for p in h.split(" / ") if p.strip()]
            # 移除图表注解部分
            parts = [p for p in parts if not _fig_pat.match(p)]
            if not parts:
                return ""
            # 截断到最多三级
            if len(parts) > 3:
                parts = parts[:3]
            return " / ".join(parts)

        def _norm_key(h: str) -> str:
            h = _clean_heading(h)
            h = _re.sub(r'[（）()：:、，,。。\s\d\.\-–—/\\]+', '', h)
            return h.casefold()

        # 全文章节顺序索引（用截断后的 key）
        heading_order = {}
        for i, h in enumerate(all_headings):
            cleaned = _trim_and_filter(_clean_heading(h))
            k = _norm_key(cleaned)
            if k and k not in heading_order:
                heading_order[k] = i

        for m in out_moves:
            sources = m.get("source_sections") or []
            if not sources:
                continue
            # 1. 清理 LaTeX + 过滤图表注解
            cleaned = [r for r in (_trim_and_filter(_clean_heading(s)) for s in sources) if r]
            # 2. 去重归并（截断后可能有新重复，如四级去掉后与三级相同）
            seen = {}
            for s in cleaned:
                if len(s) < 3:
                    continue
                k = _norm_key(s)
                if k not in seen:
                    seen[k] = s
            # 3. 按全文章节序排序
            result = sorted(seen.values(), key=lambda s: heading_order.get(_norm_key(s), 9999))
            m["source_sections"] = result[:8]
            m["sources"] = m["source_sections"]

    def _summarize_sources_via_llm(self, out_moves: list, all_headings: list) -> None:
        """LLM 汇总整理各语步来源章节：清理 LaTeX 公式拘留、归并同一章节不同写法、
        按全文章节先后顺序排列、保留完整层级路径。只整理格式，不增删来源、不改语步归属。"""
        payload = [
            {"move_type": m["move_type"], "source_sections": m.get("source_sections") or []}
            for m in out_moves if (m.get("source_sections"))
        ]
        if not payload:
            return
        doc_order = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(all_headings)) if all_headings else "（无全文章节清单）"
        user_msg = (
            "以下是基金报告各语步的来源章节（原始，可能含 LaTeX 公式拘留、同一章节多种写法、顺序混乱）。\n\n"
            f"【全文章节先后顺序参考】\n{doc_order}\n\n"
            "【各语步来源章节】\n"
            + "\n".join(f"《{p['move_type']}》：" + " | ".join(p['source_sections']) for p in payload)
            + "\n\n请按系统提示的规则整理每个语步的来源章节。"
        )
        d = self._glm.chat_json(
            self._SUMMARIZE_SOURCES_PROMPT, user_msg,
            timeout=90.0, max_tokens=2500, temperature=0.0)
        d = d.get("data", d) if isinstance(d, dict) else {}
        for fm in (d.get("moves") or []):
            if not isinstance(fm, dict):
                continue
            mt = (fm.get("move_type") or "").strip()
            secs = [s.strip() for s in (fm.get("source_sections") or []) if s and str(s).strip()]
            if not secs:
                continue
            m = next((x for x in out_moves if x["move_type"] == mt), None)
            if m:
                m["source_sections"] = secs
                m["sources"] = secs

    def _filter_sources_by_relevance(self, out_moves: list) -> None:
        """让 LLM 对每个语步的候选来源章节做相关性二次筛选（按下标），就地更新 out_moves 的 sources。

        LLM 只返回相关候选的下标，代码据此保留**原始字符串**——这样 LLM 无法改写/缩短来源标题
        （之前的实现让 LLM 返回 sources 字符串，会把"（二）研究内容：/3．研究目标"缩短成"（二）研究内容："）。
        若某语步全部候选被判不相关，保留原全部来源（避免误清空丢失溯源）。
        """
        candidates = [
            {"move_type": m["move_type"], "content": (m.get("content") or "")[:300],
             "candidate_sources": m.get("sources") or []}
            for m in out_moves if (m.get("sources"))
        ]
        if not candidates:
            return
        d = self._glm.chat_json(
            self._SOURCE_FILTER_PROMPT,
            "请对以下每个语步的候选来源章节按下标做相关性筛选：\n" + json.dumps(candidates, ensure_ascii=False),
            timeout=60.0, max_tokens=1500, temperature=0.0)
        d = d.get("data", d) if isinstance(d, dict) else {}
        judgments = {}
        for item in (d.get("moves") or []):
            if isinstance(item, dict) and item.get("move_type"):
                raw_idxs = item.get("relevant_indices") or []
                idxs = []
                for i in raw_idxs:
                    try:
                        idxs.append(int(i))
                    except (TypeError, ValueError):
                        continue
                judgments[item["move_type"].strip()] = idxs
        for m in out_moves:
            key = m["move_type"]
            if key in judgments:
                srcs = m.get("sources") or []
                idxs = judgments[key]
                kept = [srcs[i] for i in idxs if 0 <= i < len(srcs)]
                if kept:
                    m["sources"] = kept
                    m["source_sections"] = kept

    def _relocate_deliverables_to_expected(self, out_moves: list, full_text: str) -> None:
        """预期成果来源兜底：若 LLM 已给预期成果内容但未给来源，从全文补"预期研究成果"章节标题。

        不再从全文兜底注入产出性句子、也不再从其他语步迁移——结题报告的"成果部分/发表论文情况/
        人才培养情况/研究成果目录"等是项目实际完成的**已有成果**，按句注入/迁移会把它们冒充成
        预期成果（用户要求：预期成果≠已有成果；无计划产出则留空，空值可接受）。预期成果的内容完全
        交给分块 LLM 按章节绑定（chunk 已见章节语境，能区分"预期研究成果"=计划产出 vs "成果部分"=已有成果）。
        """
        expected = next((m for m in out_moves if m["move_type"] == "预期成果"), None)
        if expected is None:
            return
        # 仅当预期成果已有内容但缺来源时，补"预期研究成果/预期成果"章节标题；空内容不补来源（保持空）
        if (expected.get("content") or "").strip() and not (expected.get("sources") or []):
            src = self._find_expected_outcome_section(full_text)
            if src:
                expected["sources"] = [src]
                expected["source_sections"] = [src]

    def _find_expected_outcome_section(self, full_text: str) -> str:
        """从全文定位"预期研究成果/预期成果"章节标题，返回标题原文（用于补全预期成果来源）。"""
        if not full_text:
            return ""
        for line in full_text.split('\n'):
            s = line.strip()
            m = re.match(r'^#{1,6}\s+(.+)', s)
            title = (m.group(1).strip() if m else s).strip()
            if re.search(r'预期(研究)?成果', title):
                return title
        return ""

    def _find_research_goal_section(self, full_text: str) -> str:
        """从全文定位"研究目标"章节标题（用于补全研究目标来源）。

        基于 NSFC 标准提纲：结题报告有"（2）研究目标完成情况"；立项申请书有"3. 研究目标"。
        优先匹配"研究目标完成情况"，其次"研究目标"（排除含"完成/情况"的变体，避免误中正文散见）。
        """
        if not full_text:
            return ""
        cand = []
        for line in full_text.split('\n'):
            s = line.strip()
            m = re.match(r'^#{1,6}\s+(.+)', s)
            title = (m.group(1).strip() if m else s).strip()
            if not title or len(title) > 40:
                continue
            if re.search(r'研究目标完成情况', title):
                return title
            if re.search(r'研究目标', title) and not re.search(r'完成|情况', title):
                cand.append(title)
        return cand[0] if cand else ""

    # 研究目标来源"白名单"关键词：只保留标题含这些词的来源（NSFC 标准提纲章节名，
    # 非某篇文献特有）。研究内容/研究方案/产出/价值等章节主题与"研究目标"不符，一律剔除。
    _GOAL_KEEP_KEYWORDS = ("目标", "关键科学问题", "关键问题", "摘要", "立项依据", "立项背景", "项目背景")

    def _ensure_research_goal_source(self, out_moves: list, full_text: str) -> None:
        """研究目标来源兜底：只保留"目标/关键问题/摘要/立项依据"类来源，并补精确叶子。

        块级 GLM 对该块未返回 source_section 时 B1 留空，致精确叶子缺失（只剩笼统的"中文摘要"）；
        且研究目标常被串入研究内容/研究方案/产出/价值章节。此处用白名单剔除不符来源，
        并从全文补"研究目标完成情况/研究目标"标准章节，使来源既精确又正确。
        """
        goal = next((m for m in out_moves if m["move_type"] == "研究目标"), None)
        if goal is None:
            return
        srcs = goal.get("sources") or []
        # 白名单：只留标题含"目标/关键(科学)问题/摘要/立项依据"等目标类词的来源
        kept = [s for s in srcs if any(k in s for k in self._GOAL_KEEP_KEYWORDS)]
        # 若无"研究目标/目标完成"精确叶子，从全文补上
        if not any(re.search(r'研究目标|目标完成', s) for s in kept):
            src = self._find_research_goal_section(full_text)
            if src and src not in kept:
                kept = kept + [src]
        # 过滤后仍有来源（含补的）才更新；否则保留原来源避免误清空
        if kept and kept != srcs:
            goal["sources"] = kept
            goal["source_sections"] = kept

    @staticmethod
    def _strip_no_evidence_filler(content: str) -> str:
        """剔除预期成果里 GLM 凑数的"原文未提供…/结题时的完成证据：原文未提供…"占位文字。

        原 prompt 曾强制第二段"完成证据"，立项申请书无结题数据时 GLM 会凑"原文未提供"——
        代码层硬守卫，无论 GLM 是否听话都根除这类占位/补白。
        """
        import re as _re
        if not content:
            return content
        # 去掉"结题时的完成证据：原文未提供…"整句（到行尾/句号）
        content = _re.sub(r'\n*结题时的完成证据[：:][^\n。]*[。]?', '', content)
        # 去掉孤立的"原文未提供…完成情况…"占位句
        content = _re.sub(r'\n*原文未提供[^\n。]*[。]?', '', content)
        return content.strip()

    def _execute_fund_move(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """基金项目语步识别：全文直送 LLM（自适应长度），不按 ## 章节切分。

        LLM 优先版：从全文角度处理，不解析章节结构。
        - 短全文（≤ FULL_TEXT_THRESHOLD 字）→ 单次 LLM 调用，summary_prompt + 全文
          直接出归纳后的五类语步（真·全文直送）。
        - 长全文（> 阈值）→ 按字数切块 map-reduce：每块（CHUNK_SIZE 字）system_prompt
          提取片段 → 过滤低置信度 → summary_prompt 汇总归纳。切块按固定字数，非章节语义。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        FULL_TEXT_THRESHOLD = 15000  # 字数阈值：以下单次直送，以上切块（切块来源为结构化章节标题，更可靠）
        CHUNK_SIZE = 10000           # 长文档切块大小（字）（2026-09-09 试 20000 反而更慢：块少但单次 LLM 更慢，净效果负，已回退）


        result = SemanticResult(code=code, name=fp.name)
        full_text = (request.text or "").strip()
        if not full_text:
            raise ValueError("基金项目语步识别需提供 text 字段（全文）")

        # 文件接口传入临时路径；PDF、DOCX、TXT 都要先解析，不能把路径
        # 字符串误当成基金正文交给模型。
        if os.path.exists(full_text):
            from pathlib import Path as _Path
            from infrastructure.document_parser.upload_reader import extract_bytes
            from config.settings import settings
            path = _Path(full_text)
            full_text = extract_bytes(path.read_bytes(), path.name, light=settings.should_use_light("fund-move")).strip()
        if not full_text:
            raise ValueError("基金项目语步识别需提供 text 字段（全文）")

        move_types = ["立项依据", "研究目标", "技术实施方案", "预期成果", "应用价值"]

        # 基金类文本预检（测试缺陷:普通科技摘要被虚构出基金语步）:
        # 基金申请书/申报书/任务书/结题报告必有申报结构词且篇幅较长;
        # 普通科技摘要/论文不满足,五类语步全部为空,不进 LLM 强行解读。
        _fund_kw = ("立项依据", "申请书", "申报书", "任务书", "结题", "验收", "考核指标",
                    "技术路线", "预期成果", "申请经费", "资助经费", "可行性分析", "依托单位",
                    "项目摘要", "研究基础", "年度研究计划",
                    # 五类语步词也作结构信号：短文本测试/在线试用常直接写含这些词的
                    # 简短申报式段落，此前长文+多词门槛会把它们全部拒掉（全空输出）
                    "建设目标", "研究内容", "研究目标", "应用价值", "实施方案")
        _kw_hits = sum(1 for _k in _fund_kw if _k in full_text)
        # 短文本(≥80字)有 3 个结构词即认定基金类（覆盖在线测试/短申报书摘要场景）；
        # 长文本维持原门槛
        _is_fund_text = (len(full_text) >= 1500 and _kw_hits >= 2) or _kw_hits >= 4 \
                        or (len(full_text) >= 80 and _kw_hits >= 3)
        if not _is_fund_text:
            _empty_moves = [{"move_type": _mt, "content": "", "sources": [], "source_sections": [],
                             "n_fragments": 0, "confidence": None} for _mt in move_types]
            result.success = True
            result.data = {
                "moves": _empty_moves,
                "confidence": None,
                "document": {},
                "document_type_check": "非基金类文本：输入不是基金申请书/项目申报书/任务书/结题报告等基金类文本，未识别到基金语步",
            }
            result.evidence = []
            result.confidence = None
            result.raw = json.dumps({"moves": _empty_moves, "n_chars": len(full_text),
                                     "mode": "not_fund_text", "n_units": 0}, ensure_ascii=False)
            logger.info("基金语步预检:非基金类文本(%d 字,%d 个申报结构词命中),跳过识别", len(full_text), _kw_hits)
            return result
        summary_prompt = rule.raw.get("summary_prompt", rule.system_prompt)
        system_prompt = self._system_prompt(rule, request)
        aggregated = {mt: [] for mt in move_types}
        all_headings = []  # 全文章节清单（文档顺序去重），供来源汇总按先后排序参考
        n_units = 1  # 单调用=1，切块=块数
        mode = "single_call"

        if len(full_text) <= FULL_TEXT_THRESHOLD:
            # —— 短全文：单次直送 LLM，直接出归纳后的五类语步 ——
            logger.info("基金语步识别（全文单调用）：%d 字", len(full_text))
            d = self._glm.chat_json(
                summary_prompt,
                "以下是基金报告全文，请直接从中识别并归纳五类语步：\n" + full_text,
                timeout=150.0, max_tokens=2500, temperature=0.0)
            d = d.get("data", d) if isinstance(d, dict) else {}
            final_moves = d.get("moves", [])
            # 单调用：LLM 按新 summary_prompt 在 source_sections 字段返回真实章节标题；
            # content 不含来源标注（_strip_source_annotation 兜底清理）
            for mt in move_types:
                for fm in final_moves:
                    if fm.get("move_type", "").strip() == mt:
                        raw = fm.get("content", "").strip()
                        if raw:
                            secs = [s.strip() for s in (fm.get("source_sections") or []) if s and s.strip()]
                            secs = [s for s in secs if s not in ('全文', '无') and not self._is_non_content_source(s)]
                            if not secs:
                                secs = self._parse_source_sections(raw)  # 兜底：从 content 解析
                                secs = [s for s in secs if not self._is_non_content_source(s)]
                            c = self._strip_source_annotation(raw)
                            aggregated[mt].append({
                                "content": c, "source": "；".join(secs) if secs else "全文",
                                "headings": secs if secs else ["全文"], "confidence": 1.0})
                        break
        else:
            # —— 长全文：按章节标题切块 map-reduce（来源=真实 ##/### 章节标题）——
            chunks = self._heading_aware_chunks(full_text, CHUNK_SIZE)
            n_units = len(chunks)
            mode = "chunked_map_reduce"
            logger.info("基金语步识别（章节切块 map-reduce）：%d 字 → %d 块", len(full_text), n_units)

            def process_chunk(idx, chunk):
                headings = chunk["headings"]
                src_label = "；".join(headings)
                if len(chunk["text"]) < 20:
                    return {"idx": idx, "moves": [], "headings": headings}
                # 跳过纯结构性章节块（参考文献/致谢/附录——与任何语步无关，不发 LLM 省调用）
                _content_heads = [h for h in headings if h != "全文" and not self._is_non_content_source(h)]
                if headings and not _content_heads:
                    return {"idx": idx, "moves": [], "headings": headings}
                # 把本块包含的章节路径列给 LLM，要求每语步按章节分段输出 fragments，
                # 每片段 section 从中选最具体叶子——使返回的叶子能与块内路径 endswith 匹配、
                # 来源可溯源且不错指。片段级绑定取代旧"语步级笼统 source_section"，从源头解决串语步/错指。
                heading_hint = "\n".join(f"- {h}" for h in headings if h and h != "全文") or "（未识别到章节标题）"
                d = self._glm.chat_json(
                    system_prompt,
                    f"以下是基金报告「{src_label}」部分的内容，请识别其中包含的五类语步。\n"
                    f"本段包含以下章节（完整路径，自上而下）：\n{heading_hint}\n"
                    f"⚠️ 每个语步按章节分段输出 fragments，每片段的 section 从上面列出的路径里选**最具体的那条叶子**"
                    f"（语步内容实际出自哪节就标哪节），同一章连续句子合一、跨节分多片段；"
                    f"严禁臆造、严禁用块首笼统路径、严禁串语步（来源章节主题须与语步类别相符）。\n\n"
                    f"内容：\n{chunk['text']}",
                    timeout=90.0, max_tokens=2500, temperature=0.0)
                d = d.get("data", d) if isinstance(d, dict) else {}
                return {"idx": idx, "moves": d.get("moves", []), "headings": headings}

            chunk_results = []
            from config.settings import settings as _settings
            with ThreadPoolExecutor(max_workers=max(1, _settings.GLM_MAX_CONCURRENCY)) as executor:
                futures = {executor.submit(process_chunk, i, c): i for i, c in enumerate(chunks)}
                for future in as_completed(futures):
                    chunk_results.append(future.result())
            chunk_results.sort(key=lambda x: x["idx"])

            # 收集全文章节清单（按块序=文档顺序，去重），供来源汇总时按先后排序参考
            _seen_h = set()
            for cr in chunk_results:
                for h in cr["headings"]:
                    if h and h not in _seen_h:
                        _seen_h.add(h)
                        all_headings.append(h)

            # 过滤低置信度 + 按语步聚合（片段级绑定：每 fragment 取其 section 对应的块内完整路径）
            for cr in chunk_results:
                for move in cr["moves"]:
                    mt = move.get("move_type", "").strip()
                    conf = float(move.get("confidence", 0) or 0)
                    if conf < 0.8 or mt not in move_types:
                        continue
                    # 候选来源剔除结构性章节（参考文献/致谢/附录等与语步无关）
                    cand_heads = [h for h in cr["headings"] if not self._is_non_content_source(h)]
                    if not cand_heads:
                        cand_heads = list(cr["headings"])
                    frags = move.get("fragments")
                    if not frags:
                        # 兜底：LLM 未按 fragments schema 输出而给了语步级 content 时，
                        # 把整段 content 当一个片段，section 用旧 source_section 字段（若有），
                        # 避免该语步聚合为空导致"未完整返回五类"。
                        raw_c = (move.get("content") or "").strip()
                        if raw_c:
                            frags = [{"text": raw_c, "section": (move.get("source_section") or "").strip()}]
                    for frag in (frags or []):
                        text = (frag.get("text") or "").strip() if isinstance(frag, dict) else ""
                        if not text:
                            continue
                        ss = (frag.get("section") or "").strip() if isinstance(frag, dict) else ""
                        heads = []
                        if ss:
                            # LLM 给叶子标题：优先映射到块内以它结尾的完整路径（带层级），
                            # 其次保留 LLM 给的叶子原文（至少准确），不乱指块首路径
                            matched = [h for h in cand_heads if h.rstrip().endswith(ss) or ss in h]
                            heads = matched[:1] if matched else [ss]
                        # ss 为空时不再兜底取块首路径——语步内容常在块内更深的叶子，
                        # 兜底块首会错指到内容不在的章节；留空由输出阶段聚合丢弃，避免错误溯源
                        aggregated[mt].append({"content": text, "source": heads[0] if heads else "",
                                               "headings": heads, "confidence": conf})

            # LLM 汇总归纳（各块片段 → 去重整合 → 最终五类）
            _empty_moves = [mt for mt, v in aggregated.items() if not v]
            if _empty_moves:
                logger.warning("基金语步聚合为空的语步：%s（分块 LLM 未给该语步 fragments），将由 summary 兜底", _empty_moves)
            fragments_str = ""
            for mt in move_types:
                if aggregated[mt]:
                    _seen = set()
                    sources = []
                    for a in aggregated[mt]:
                        if a["source"] not in _seen:
                            _seen.add(a["source"])
                            sources.append(f"{a['source']}(conf={a['confidence']:.1f})")
                    # content 去重（单段切分 overlap 会使同一片段在相邻子块都提取，
                    # 留第一个=前块 source 归属正确，避免 reduce 重复输出）
                    _seen_c = set()
                    contents = []
                    for a in aggregated[mt]:
                        _c = a["content"][:200]
                        if _c not in _seen_c:
                            _seen_c.add(_c)
                            contents.append(_c)
                    fragments_str += f"\n【{mt}】来源：{', '.join(sources)}\n" + "\n".join(contents) + "\n"
                else:
                    fragments_str += f"\n【{mt}】无内容\n"
            d = self._glm.chat_json(
                summary_prompt,
                "各片段提取的语步片段：\n" + fragments_str,
                timeout=120.0, max_tokens=2500, temperature=0.0)
            d = d.get("data", d) if isinstance(d, dict) else {}
            final_moves = d.get("moves", [])

        # 组装输出
        out_moves = []
        for mt in move_types:
            final_content = ""
            for fm in final_moves:
                if fm.get("move_type", "").strip() == mt:
                    final_content = self._strip_source_annotation(fm.get("content", "").strip())
                    break
            seen = set()
            sources = []
            for a in aggregated[mt]:
                for h in a.get("headings") or [a.get("source", "")]:
                    # 剔除结构性章节（参考文献/致谢/附录等与任何语步无关）
                    if h and h not in seen and not self._is_non_content_source(h):
                        seen.add(h)
                        sources.append(h)
            out_moves.append({
                "move_type": mt,
                "content": final_content or (aggregated[mt][0]["content"] if aggregated[mt] else ""),
                "sources": sources,
                "source_sections": sources,
                "n_fragments": len(aggregated[mt]),
                "confidence": max((a["confidence"] for a in aggregated[mt]), default=None),
            })

        # 允许个别语步为空（如结题报告无"预期成果/计划产出"——已有成果不冒充预期成果）；
        # 仅记日志，不报错，让前端按空值正常展示。
        _empty_moves = [m["move_type"] for m in out_moves if not (m.get("content") or "").strip()]
        if _empty_moves:
            logger.warning("基金语步以下语步无内容（可空，不报错）：%s", _empty_moves)

        # 来源判定：chunk 路径已在分块阶段片段级绑定（每 fragment 标所在章节叶子），聚合即去重，
        # 不再做事后重选——信任分块绑定，避免汇总后让模型对照全清单重选时串语步/错指。
        # 单调用路径 LLM 一次对照全文给 source_sections，走轻量相关性二次筛兜底。
        if mode == "single_call":
            self._filter_sources_by_relevance(out_moves)

        # 后处理纠偏：论文/专利/人才培养等产出性表述常被误分到研究目标/技术方案，
        # 且 fragments 截断会丢失末尾产出条目。这里直接从全文提取产出性句子补入"预期成果"，
        # 并把误分到其他语步的产出性句子迁移过来（用户硬性要求：预期成果必须含论文/专利/培养博硕士）
        self._relocate_deliverables_to_expected(out_moves, full_text)

        # 预期成果硬守卫：剔除 GLM 凑数的"原文未提供/结题时的完成证据"占位文字
        # （无论 GLM 是否遵守按阶段输出的 prompt 指令，代码层保证不残留补白）
        expected = next((m for m in out_moves if m["move_type"] == "预期成果"), None)
        if expected and expected.get("content"):
            expected["content"] = self._strip_no_evidence_filler(expected["content"])
        # 研究目标来源兜底：剔除不符的标准章节来源 + 补"研究目标完成情况/研究目标"精确叶子
        self._ensure_research_goal_source(out_moves, full_text)

        # 来源汇总整理：LLM 清理 LaTeX 拘留、归并同章节不同写法、按全文章节先后顺序排列，
        # 只整理格式不增删来源——前端正则清不干净 LaTeX/混合编号，交 LLM 汇总更稳更规范。
        # 来源整理（2026-09-09 提速：代码版替代 LLM 调用，省一轮串行 3~5s/篇）
        self._format_sources_local(out_moves, all_headings)

        result.success = True
        # 整体置信度 = 有内容语步的置信度均值。原「片段总数/(块数×5)」是片段覆盖率而非
        # 置信度，片段多于块数×5 时会 >1（实测 recommend.pdf 达 2.15）。各语步 confidence
        # 已由上方取该语步片段的最大置信度（LLM 给，0-1）；空语步（算法判定缺失，有确信）
        # 不计入均值，避免缺失判定拉低整体。
        _per_move_confs = [m["confidence"] for m in out_moves if m.get("confidence") is not None]
        overall_confidence = round(sum(_per_move_confs) / len(_per_move_confs), 3) if _per_move_confs else None
        # 从封面提取项目名称，覆盖文件名兜底：result.data.document.title 由 normalizer
        # 的 setdefault 采纳（不覆盖已有值），让弹窗题名列显示真实项目名而非文件名。
        project_name = self._extract_project_name(full_text)
        result.data = {
            "moves": out_moves,
            "confidence": overall_confidence,
            "document": {"title": project_name} if project_name else {},
            # 全文作为内部定位源传给 normalizer（弹窗"原文片段高亮"用全文匹配语步
            # 片段；文件模式 document.abstract 只有摘要，语步片段多来自全文正文）。
            # 该键不在弹窗白名单，public_viz_result 出口自动滤除，不进公开响应。
            "source_full_text": full_text[:20000],
        }
        result.evidence = [{"source": a["source"], "move_type": mt, "confidence": a["confidence"]}
                           for mt in move_types for a in aggregated[mt]]
        result.confidence = overall_confidence
        result.raw = json.dumps({
            "moves": out_moves,
            "n_chars": len(full_text),
            "mode": mode,
            "n_units": n_units,
        }, ensure_ascii=False)
        return result

    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_user_payload(input_type: InputType, request: SemanticRequest) -> Dict[str, Any]:
        """依据 input_type 校验并构造传入大模型的负载。"""
        if input_type == InputType.MULTI_TEXT:
            if not request.texts:
                raise ValueError(f"功能点要求多篇文本输入，请提供 texts 字段")
            MultiTextInput(texts=request.texts, metas=None).validate()
            return {"texts": request.texts, "meta": request.meta}
        else:
            if not request.text:
                raise ValueError(f"功能点要求单篇文本输入，请提供 text 字段")
            TextInput(text=request.text, meta=request.meta).validate()
            return {"text": request.text, "meta": request.meta}

    @staticmethod
    def _render_user_prompt(payload: Dict[str, Any], params: Dict[str, Any]) -> str:
        """渲染 user prompt：输入文本 + 运行参数。"""
        obj = {"input": payload}
        if params:
            obj["params"] = params
        return "请处理以下输入并按规则库要求输出 JSON：\n" + json.dumps(
            obj, ensure_ascii=False, indent=2
        )

    def _parse_papers_concurrent(self, texts: list, dual_view: bool = False,
                                 max_workers: int = 5, term_mode: bool = False,
                                 focus: bool = False, focused: bool = False) -> list:
        """并发解析多篇文献 → papers 列表（顺序与 texts 对齐）。

        每篇处理：JSON 文本→dict；PDF/MD 文件→MinerU 全文（瓶颈，并发加速）；
        纯文本→{"ch_abstract": t}。

        MinerU 走 GPU 子进程，并发过高会 OOM，故硬上限 8、默认 4。

        dual_view/term_mode/focus/focused 仅为兼容旧调用签名保留，不再触发旧 TopicFusion
        或旧 LLM 双视图抽取。深度聚类由 deep_clustering_service 独立处理。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _extract_year(text):
            """从全文前部提取发表年份（Published/©/收稿等上下文优先，无则取前部首个合理年份）。"""
            if not isinstance(text, str) or not text:
                return None
            head = text[:2000]
            m = re.search(r'(?:published|received|accepted|online|©|copyright)[^\d]{0,15}(20[0-2]\d)', head, re.I)
            if m:
                return int(m.group(1))
            m = re.search(r'(?:出版|发表|收稿|录用)[：:\s]*(20[0-2]\d)', head)
            if m:
                return int(m.group(1))
            m = re.search(r'\b20[0-2]\d\b', head[:600])
            return int(m.group(0)) if m else None

        def _one(t):
            t = (t or "").strip()
            if t and t[0] == "{":
                try:
                    return json.loads(t)
                except json.JSONDecodeError:
                    return {"ch_abstract": t}
            if t and os.path.exists(t) and t.lower().endswith((".pdf", ".md")):
                try:
                    from infrastructure.document_parser.mineru_reader import process_to_text
                    doc = process_to_text(t)
                    full = doc.get("full_text") or ""
                    if not isinstance(full, str):
                        full = ""
                    title = doc.get("title") or ""
                    return {
                        "ch_name": title,
                        "ch_abstract": full,
                        "keywords": [],
                        "publication_year": _extract_year(full),
                    }
                except Exception:  # noqa: BLE001
                    return {"ch_abstract": t}
            return {"ch_abstract": t}

        n = len(texts)
        if n <= 1:
            return [_one(t) for t in texts]
        # 实测 RTX 3090(24G)：单 MinerU 峰值~3.3G，6 路并发峰值 91%(22.5G/24.6G)，
        # 第 7 路 OOM。故硬上限 6；默认 5 留余量应对更大/更密 PDF。
        max_workers = max(1, min(int(max_workers or 5), 6, n))
        logger.info("并发解析 %d 篇文献，max_workers=%d（MinerU+LLM）", n, max_workers)
        papers = [None] * n
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_one, t): i for i, t in enumerate(texts)}
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    papers[i] = fut.result()
                except Exception:  # noqa: BLE001
                    papers[i] = {"ch_abstract": texts[i]}
                done += 1
                logger.info("已解析 %d/%d 篇", done, n)
        return papers

    def _execute_clustering(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """新的双路线深度聚类入口；不再使用 TopicFusion 主题库映射。"""
        from application.service.deep_clustering_service import execute_deep_clustering

        return execute_deep_clustering(code, request, fp, self._glm)

    def _execute_labeling(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """甲方契约入口：只接收深度聚类输出的类簇短语集合。"""
        from application.service.cluster_labeling_service import execute_cluster_labeling

        result = execute_cluster_labeling(code, request, fp, self._glm)

        # 后处理:用生成的最终标签更新聚类沉淀的文献集名称(标签 · 时间)
        try:
            labels = (result.data or {}).get("labels") or []
            if labels:
                from infrastructure.database.resource_repository import DatabaseResourceRepository
                from infrastructure.database.connection import Database
                db = Database()
                db.initialize()
                repo = DatabaseResourceRepository(db)
                collections = repo.list_collections("default", limit=200) if hasattr(repo, "list_collections") else []
                for coll in collections:
                    desc = str(coll.get("description") or "")
                    name = str(coll.get("name") or "")
                    # 匹配文献集(描述含深度聚类字样)
                    if "深度聚类" not in desc:
                        continue
                    # 从名称中提取时间部分(·后面)
                    time_part = name.split("·")[-1].strip() if "·" in name else ""
                    # 找到该文献集对应的标签(按簇ID或名称匹配)
                    for lb in labels:
                        lb_name = str(lb.get("label") or "").strip()
                        if not lb_name:
                            continue
                        # 尝试按簇ID匹配
                        cid = str(lb.get("cluster_id") or "")
                        if cid and cid in desc:
                            new_name = f"{lb_name} · {time_part}" if time_part else lb_name
                            if new_name != name:
                                repo.update_collection_name(str(coll.get("id")), new_name)
                                break
        except Exception as exc:
            import logging; logging.getLogger(__name__).warning("标签生成后更新文献集名失败: %s", exc)

        return result

    def _execute_structured_review(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """按需规顺序执行：研究问题抽取 → 问题聚类 → 方法匹配 → 综述。"""
        from application.service.structured_review_service import execute_structured_review

        return execute_structured_review(code, request, fp, self._glm)

    # ==================== 引用句识别 ==================== #

    # 引用标记正则（确定引用句）
    _CITATION_PATTERNS = [
        __import__('re').compile(r'\[\s*[1-9]\d*(?:\s*[-–,，]\s*[1-9]\d*)*\s*\]'),  # [1] [1,2] [1-3] [3-5] 容忍空格，排除0避免误匹配归一化区间[0,1]
        __import__('re').compile(r'<sup>\s*\[?\d+\]?\s*</sup>'),     # <sup>[1]</sup> <sup>1</sup>
        __import__('re').compile(r'<sub>\s*\[?\d+\]?\s*</sub>'),     # <sub>[1]</sub>
        __import__('re').compile(r'\([^)]*\b(?:19|20)\d{2}\b[^)]*\)'),              # (Smith, 2020) 要求19xx/20xx真年份，避免误匹配表格数字(8,1460)
        __import__('re').compile(r'[\w一-鿿]+等?[（(]\s*\d{4}\s*[）)]'),   # Smith等(2020) 张三等（2020） 支持全角括号
        __import__('re').compile(r'\w+\s+et\s+al\.?.*?\d{4}'),         # Smith et al. 2020
        __import__('re').compile(r'文献\[\s*[\d,\-\s]+\s*\]'),        # 文献[1]
        __import__('re').compile(r'文献\[\s*[A-Z]\d+\s*\]'),           # 文献[A1]
        __import__('re').compile(r'\w+\s*等人?\s*于\s*\d{4}\s*年'),   # Vaswani等人于2017年提出 / Vaswani 等人于 2017 年（容忍空格，不限定“提出”）
    ]
    # 线索词（不确定，需LLM判定）
    _CITATION_CUES = __import__('re').compile(
        r'所述|报道|提出|发现|研究表明|先前研究|已有研究|根据.*?研究|参考.*?文献|引用|借鉴|沿用|基于.*?工作')

    @staticmethod
    def _clean_citation_latex(text: str) -> str:
        """清理 MinerU 残缺的 LaTeX：配对 $...$/$$...$$ 保留给前端 KaTeX 渲染，
        外部孤立的 \\command（希腊字母/符号）转 unicode，去掉孤立 $。
        避免 "\\alpha$-Fe" 这类残缺 LaTeX 在引用句里裸露成符号。"""
        import re as _re
        greek = {'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε',
                 'varepsilon': 'ε', 'zeta': 'ζ', 'eta': 'η', 'theta': 'θ', 'vartheta': 'ϑ',
                 'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ', 'nu': 'ν', 'xi': 'ξ',
                 'pi': 'π', 'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'upsilon': 'υ', 'phi': 'φ',
                 'varphi': 'ϕ', 'chi': 'χ', 'psi': 'ψ', 'omega': 'ω', 'Gamma': 'Γ', 'Delta': 'Δ',
                 'Theta': 'Θ', 'Lambda': 'Λ', 'Xi': 'Ξ', 'Pi': 'Π', 'Sigma': 'Σ', 'Phi': 'Φ',
                 'Psi': 'Ψ', 'Omega': 'Ω'}
        sym = {'prime': "'", 'circ': '∘', 'approx': '≈', 'times': '×', 'leq': '≤', 'le': '≤',
               'geq': '≥', 'ge': '≥', 'sim': '∼', 'simeq': '≃', 'rightarrow': '→', 'to': '→',
               'Rightarrow': '⇒', 'leftarrow': '←', 'Leftarrow': '⇐', 'cdots': '⋯', 'ldots': '…',
               'dots': '…', 'pm': '±', 'mp': '∓', 'infty': '∞', 'partial': '∂', 'nabla': '∇',
               'cdot': '·', 'div': '÷', 'neq': '≠', 'ne': '≠', 'propto': '∝', 'degree': '°'}

        def _conv(m):
            name = m.group(1)
            return greek.get(name) or sym.get(name) or m.group(0)

        # $^{[1-3]}$ / $^{1,2}$ / $^{3}$ 是 LaTeX 上标引用（mineru 输出），转 [1-3]/[1,2]/[3] 供pattern匹配
        text = _re.sub(r'\$\^\{(\[[^\]]+\])\}\$', r'\1', text)
        text = _re.sub(r'\$\^\{([1-9]\d*(?:\s*[-–,，]\s*[1-9]\d*)*)\}\$', r'[\1]', text)
        out = []
        for i, part in enumerate(_re.split(r'(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)', text)):
            if i % 2 == 1:
                out.append(part)  # 配对的 $...$ 保留，前端 KaTeX 渲染
            else:
                part = _re.sub(r'\\([a-zA-Z]+)', _conv, part)
                part = part.replace('\\$', '$').replace('$', '')  # 去掉孤立 $
                out.append(part)
        return ''.join(out)

    def _execute_citation_recognition(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """引用句识别：规则抽取→LLM判不确定句→批量LLM判情感/意图→后置校验。

        支持 cr_sentiment（情感）和 cr_intent（意图），通过 code 区分。
        输入：text（文献全文，文本/PDF/MD）。
        """
        import re as _re
        result = SemanticResult(code=code, name=fp.name)
        # 模型边界守卫（2026-09-08，契约：GLM 不可用时必须失败，禁止本地编造结果）：
        # 引用句提取的并发分块为瞬时 API 错误设计了逐块 try/except，None 客户端的
        # AttributeError 会被吞成"0 块命中"→ 空结果 success=True —— 无模型却产出
        # "无引用句"业务结论。此处显式拦截，fail closed。
        if self._glm is None:
            raise RuntimeError("GLM 客户端未初始化，引用句识别不可用（须连接大模型判定，禁止本地编造结果）")
        text = (request.text or "").strip()
        if not text:
            raise ValueError("引用句识别需提供 text 字段（文献全文）")

        # PDF/MD 文件路径 → DocumentParser 提取全文
        if text.endswith(('.pdf', '.md')) and os.path.exists(text):
            from infrastructure.document_parser.mineru_reader import process_to_text
            doc = process_to_text(text)
            text = doc.get('full_text', '')

        if not text:
            raise ValueError("未能从输入获取文献全文")

        # ① 文本模式优先处理用户明确提交的“引用句+前后文”；文件模式
        # 没有该结构时再从全文自动抽取。这样批量文本不会把不同文献的
        # 引用句串在一起，也不会忽略在线测试中用户填写的上下文。
        provided_contexts = (request.params or {}).get("citation_sentence_and_context") or []
        if isinstance(provided_contexts, dict):
            provided_contexts = [provided_contexts]
        certain = []
        for row in provided_contexts if isinstance(provided_contexts, list) else []:
            if not isinstance(row, dict):
                continue
            sentence = str(row.get("citation_sentence") or row.get("sentence") or "").strip()
            if not sentence:
                continue
            # 句内多引用拆分后同一原句会提交多条记录：优先采用调用方指定的
            # citation_marker，否则每条都取句中第一个标记（[1][2][3] 全标成 [1]）
            marker = str(row.get("citation_marker") or "").strip()
            if not marker:
                marker = next((match.group() for pattern in self._CITATION_PATTERNS if (match := pattern.search(sentence))), "")
            # 局部子片段：该条引用在句内对应的语义片段，意图/情感判定优先采用
            sub_span = str(row.get("citation_sub_span") or row.get("local_sub_span") or row.get("sub_span") or "").strip()
            certain.append({
                "sentence": sentence,
                "citation_marker": marker,
                "sub_span": sub_span,
                "context_before": str(row.get("previous_context") or row.get("context_before") or ""),
                "context_after": str(row.get("next_context") or row.get("context_after") or ""),
            })
        uncertain = []
        if not certain:
            certain, uncertain = self._extract_citations(text, rule)
        logger.info("引用句抽取：确定%d 不确定%d", len(certain), len(uncertain))

        # ② 正则召回的候选(certain+uncertain)一次性批量送 LLM 判定是否正文引用句。
        # 替代原 confirm+filter+is_body 正则兜底：LLM 语义排除参考文献条目/作者署名/
        # 图标题/无标记总结句，不再需要 is_body 正则补丁。
        candidates = list(certain) + list(uncertain)
        if candidates:
            citations = self._llm_judge_citations(candidates)
            # uncertain 经 LLM 确认后，用引用模式从句中补 citation_marker（原 uncertain marker 为空）
            for _c in citations:
                if not _c.get("citation_marker"):
                    for _p in self._CITATION_PATTERNS:
                        _m = _p.search(_c.get("sentence", ""))
                        if _m:
                            _c["citation_marker"] = _m.group()
                            break
            logger.info("LLM判定引用句：%d/%d", len(citations), len(candidates))
        else:
            citations = []

        if not citations:
            # 规则未命中不等于可以跳过模型。正则覆盖不到的引用格式（作者-年份、
            # 罕见标记等）由 GLM 从全文分块提取引用句——不再只探前 3000 字符
            # （长论文的引用句常集中在 3000 字之后，实测会被整篇漏掉）。
            citations = self._llm_extract_citations_fallback(text)

        if not citations:
            result.success = True
            result.data = []
            result.raw = json.dumps({"n_citations": 0}, ensure_ascii=False)
            return result

        # ②c 被引文献元数据配对（按引用标记号匹配请求的 citation_metadata）：
        # 题名/年份作为意图判定的辅助信号（2026-09-15 用户定调——如老文献多为
        # 背景铺垫、题名含方法名多为方法引入）；未提供时为空，不影响判定
        _cited_meta_by_marker: dict = {}
        _meta_rows = (request.params or {}).get("citation_metadata") or []
        if isinstance(_meta_rows, dict):
            _meta_rows = [_meta_rows]
        for _m in _meta_rows if isinstance(_meta_rows, list) else []:
            if not isinstance(_m, dict):
                continue
            _mk = str(_m.get("citation_marker") or _m.get("marker") or "").strip()
            _nums = set()
            for _part in _re.split(r"[,，]", _mk.strip().lstrip("[［").rstrip("]］")):
                _mm2 = _re.fullmatch(r"(\d+)\s*[-–~]\s*(\d+)", _part.strip())
                if _mm2:
                    _nums.update(range(int(_mm2.group(1)), int(_mm2.group(2)) + 1))
                elif _part.strip().isdigit():
                    _nums.add(int(_part.strip()))
            _desc = "，".join(str(x) for x in (
                _m.get("title") or _m.get("work_name") or "",
                _m.get("publication_year") or _m.get("year") or "") if str(x).strip())
            if _desc:
                for _n in _nums:
                    _cited_meta_by_marker[_n] = _desc
        for _c in citations:
            _mk = str(_c.get("citation_marker") or "")
            _mm3 = _re.search(r"\d+", _mk)
            _c["_cited_meta"] = _cited_meta_by_marker.get(int(_mm3.group()), "") if _mm3 else ""

        # ③ 批量 LLM 判属性（情感/意图）
        is_sentiment = (code == "cr_sentiment")
        # 用户上传的预处理训练集（citation-intent 的 preprocessed_training_set 资源）：
        # 双机制（2026-09-15 用户定调，同 domain-classify 训练数据）——few-shot 口径
        # 校准（注入判定提示词）+ 语义相似度覆盖（>0.70 直接采用样本 intent，低于
        # 阈值保持内置 LLM 判定。2026-09-15 用户定调 0.70：上传资源的价值是高把握
        # 时的辅助——相似度不够高时覆盖反而拉低置信度，不如内置）。仅意图工具；情感无此资源
        training_pairs: list = []
        if not is_sentiment:
            training_pairs = self._load_citation_training_pairs(request)
        labeled = self._llm_label_citations(citations, is_sentiment, rule, request,
                                            fewshot=training_pairs)

        # ③b 训练集相似度候选：待判引用句与训练样本算 bge-m3 余弦相似度，
        # top1 >0.70 记为候选（_training）——是否覆盖推迟到引擎+冲突审核后，
        # 按"内置最终置信度 <0.95 才动用训练集"决策（2026-09-15 用户定调：
        # 上传资源 = 标引规范定制权——内置非绝对自信（<0.95，口径两可）时
        # 跟随用户标注口径；内置 ≥0.95 的铁案不干预。实测内置分布 0.8-1.0
        # 且 LLM 逐轮在 ±0.05 波动，0.95 刻度 = 铁案线，保证案例稳定可演示）
        if training_pairs:
            try:
                from infrastructure.rag.m3_encoder import m3_encoder as _m3c
                import numpy as _np3
                _sv = _np3.asarray(_m3c.encode([p["text"] for p in training_pairs]), dtype="float32")
                _sv = _sv / (_np3.linalg.norm(_sv, axis=1, keepdims=True) + 1e-9)
                _rows = [str(c.get("sub_span") or c.get("sentence") or "") for c in labeled]
                _qv = _np3.asarray(_m3c.encode(_rows), dtype="float32")
                _qv = _qv / (_np3.linalg.norm(_qv, axis=1, keepdims=True) + 1e-9)
                _sims = _qv @ _sv.T
                for _ri, item in enumerate(labeled):
                    _best = int(_np3.argmax(_sims[_ri]))
                    _sim = float(_sims[_ri][_best])
                    if _sim > 0.70:
                        item["_training"] = {
                            "intent": training_pairs[_best]["intent"],
                            "conf": round(min(0.98, _sim), 3),
                            "sample": training_pairs[_best]["text"],
                            "sim": round(_sim, 3),
                        }
                logger.info("训练集相似度覆盖：%d/%d 条",
                            sum(1 for c in labeled if c.get("_training")), len(labeled))
            except Exception:  # noqa: BLE001 - 相似度计算失败不影响内置路径
                logger.warning("训练集相似度覆盖失败（保持内置判定）", exc_info=True)

        # ④ 后置规则引擎校验调分（动态权重+冲突检测）
        from training.citation_profile import set_citation_profile_by_code
        from training.citation_rule_engine import verify_and_adjust_citations
        from training.rule_lib import RuleLib
        from pathlib import Path as _Path
        from config.settings import settings as _settings

        set_citation_profile_by_code(code)
        from training.citation_profile import get_citation_profile
        rule_lib_path = _Path(_settings.RULES_DIR) / fp.rule_path
        rule_lib = RuleLib.load(rule_lib_path)
        engine_result = verify_and_adjust_citations(labeled, rule_lib)

        # ④b 冲突二次审核（GLM裁定，并发执行：多冲突时串行逐条曾占 ~17s，
        # ThreadPoolExecutor 5 路并发后与单次审核同量级；strict=True 的
        # 失败语义不变——ex.map 迭代时异常照常抛出）
        conflicts = engine_result["conflicts"]
        if conflicts:
            from training.conflict_review import review as conflict_review
            from concurrent.futures import ThreadPoolExecutor
            p = get_citation_profile()
            lf = "sentiment" if is_sentiment else "intent"

            def _review_one(ci: int):
                item = engine_result["adjusted"][ci]
                return ci, conflict_review(
                    sentence=item.get("sentence", ""),
                    llm_label=item.get(lf, ""),
                    rule_suggestion=item.get("rule_suggestion", ""),
                    evidence=item.get("evidence", []),
                    client=self._glm,
                    strict=True,
                    review_system=p.review_system,
                    valid_labels=p.labels,
                )

            from config.settings import settings as _settings
            with ThreadPoolExecutor(max_workers=max(1, _settings.GLM_MAX_CONCURRENCY)) as _ex:
                for ci, review_result in _ex.map(_review_one, conflicts):
                    item = engine_result["adjusted"][ci]
                    item[lf] = review_result["final_label"]
                    item["confidence"] = max(item.get("confidence", 0.5), 0.7)
                    item["reviewed"] = True

        labeled = engine_result["adjusted"]
        # 覆盖决策（引擎/冲突审核之后，基于内置最终置信度）：内置 <0.95（口径
        # 两可、非铁案）且训练集候选 sim>0.70 → 跟随用户标注口径（conf=相似度）；
        # 内置 ≥0.95 绝对自信不干预（宁缺勿错）
        for item in labeled:
            _td = item.pop("_training", None)
            if _td and float(item.get("confidence") or 0) < 0.95:
                item["intent"] = _td["intent"]
                item["confidence"] = _td["conf"]
                item["training_data_effect"] = {
                    "matched_sample": _td["sample"],
                    "similarity": _td["sim"],
                    "mechanism": "训练集口径覆盖（内置置信<0.95 且相似度>0.7）",
                }

        # ⑤ 后置校验 + 组装
        valid_labels = ({"支持", "中立", "有局限性"} if is_sentiment
                        else {"用于背景介绍", "用于引入研究方法", "用于结果比较"})
        label_field = "sentiment" if is_sentiment else "intent"

        # 同句同标签合并（2026-09-10 用户三轮定稿）：句内多引用按编号拆分出的
        # 多条记录（"[2-3]"→[2]+[3]，或 "…特征[3]，进而…量化[4]。" 的前后
        # 独立标记）——同句即同情感，一律合并为一行，句子只出现一次，标记
        # 聚合展示。组编号恰好覆盖句中全部标记时用句中原始形态（"[2-3]"；
        # 否则聚合组内标记（"[3]","[4]"）。同句不同标签保留多条（意图工具
        # 同句 [1]背景/[2]结果比较 是真实差异）。
        _mk_group_re = _re.compile(r"[\[［]\s*\d+(?:\s*[-–,，]\s*\d+)*\s*[\]］]")

        def _nums_of(mk: str) -> set:
            out_n = set()
            for part in _re.split(r"[,，]", mk.strip().lstrip("[［").rstrip("]］")):
                part = part.strip()
                m = _re.fullmatch(r"(\d+)\s*[-–~]\s*(\d+)", part)
                if m:
                    out_n.update(range(int(m.group(1)), int(m.group(2)) + 1))
                elif part.isdigit():
                    out_n.add(int(part))
            return out_n

        _groups: dict = {}
        _order: list = []
        for item in labeled:
            sent = item.get("sentence", "").strip()
            if not sent:
                continue
            label = item.get(label_field, "").strip()
            if label not in valid_labels:
                raise RuntimeError(f"GLM-5.2 返回非法引文标签: {label!r}")
            key = (sent, label)
            if key not in _groups:
                _groups[key] = []
                _order.append(key)
            _groups[key].append(item)

        out = []
        for (sent, label) in _order:
            items = _groups[(sent, label)]
            marker = str(items[0].get("citation_marker") or "").strip()
            group_markers = []
            for it in items:
                for mk in [str(it.get("citation_marker") or "").strip()] + list(it.get("citation_markers") or []):
                    if mk and mk not in group_markers:
                        group_markers.append(mk)
            # 组编号覆盖句中全部标记 → 用句中原始标记形态（"[2-3]"）
            _sent_mks = _mk_group_re.findall(sent)
            if _sent_mks:
                _group_nums = set().union(*[_nums_of(m) for m in group_markers]) if group_markers else set()
                _sent_nums = set().union(*[_nums_of(m) for m in _sent_mks])
                if _group_nums == _sent_nums:
                    group_markers = _sent_mks
                    marker = _sent_mks[0]
            # 未走恢复路径时收敛展开形态：编号被更大标记覆盖的丢弃
            # （组内同时出现 "[18-21]" 与其展开 "[18]"/"[19]" 时只留前者）
            _kept = []
            for _i, _mk in enumerate(group_markers):
                _n = _nums_of(_mk)
                if _n and any(
                    _j != _i and (_n < _nums_of(_o) or (_n == _nums_of(_o) and _j < _i))
                    for _j, _o in enumerate(group_markers)
                ):
                    continue
                _kept.append(_mk)
            if _kept:
                group_markers = _kept
                if marker not in group_markers:
                    marker = group_markers[0]
            # 找回上下文：优先按引用标记匹配（同句多条各自对齐），退回句子匹配
            ctx = next((c for c in citations
                        if marker and c.get("citation_marker") == marker
                        and (c["sentence"][:50] in sent or sent[:50] in c["sentence"])), None)
            if ctx is None:
                ctx = next((c for c in citations if c["sentence"][:50] in sent or sent[:50] in c["sentence"]), {})
            start = text.find(sent)
            row = {
                "citation_id": f"CIT{len(out) + 1}",
                "sentence": sent,
                "citation_marker": marker or ctx.get("citation_marker", ""),
                "citation_markers": group_markers or ctx.get("citation_markers") or ([marker] if marker else []),
                "context_before": ctx.get("context_before", ""),
                "context_after": ctx.get("context_after", ""),
                "source_position": {
                    "start": start if start >= 0 else None,
                    "end": start + len(sent) if start >= 0 else None,
                },
                label_field: label.removeprefix("用于"),
                "confidence": max(min(1.0, float(it.get("confidence", 0.5) or 0.5))
                                  for it in items),
            }
            # 该条引用对应的局部子片段（句内多引用拆分时存在，供核对与下游定位；
            # 合并组取首个非空——同标签组的子片段语义一致）
            sub_span = ""
            for it in items:
                _ss = str(it.get("sub_span") or "").strip()
                if _ss:
                    sub_span = _ss
                    break
            if not sub_span:
                sub_span = str(ctx.get("sub_span") or "").strip()
            if sub_span:
                row["sub_span"] = sub_span
            # 训练集覆盖指纹透出（组内首个命中条目）：matched_sample + similarity
            _td = next((it.get("training_data_effect") for it in items
                        if it.get("training_data_effect")), None)
            if _td:
                row["training_data_effect"] = _td
            out.append(row)

        result.success = True
        result.data = out
        result.confidence = sum(x["confidence"] for x in out) / max(len(out), 1)
        result.raw = json.dumps({
            "n_citations": len(out), "label_type": label_field,
            "certain": len(certain), "uncertain_confirmed": len(citations) - len(certain),
        }, ensure_ascii=False)
        return result

    def _extract_citations(self, text: str, rule=None) -> tuple:
        """规则抽取引用句（全文分句，排除参考文献章节+图片路径）。返回 (确定引用句列表, 不确定句列表)。"""
        import re as _re

        raw = rule.raw if rule else {}
        cite_patterns_raw = raw.get("citation_patterns", [])
        if cite_patterns_raw:
            patterns = [_re.compile(p) for p in cite_patterns_raw]
        else:
            patterns = self._CITATION_PATTERNS
        cues_str = raw.get("citation_cues", "")
        cues_re = _re.compile(cues_str) if cues_str else self._CITATION_CUES
        exclude_strs = raw.get("exclude_patterns", [])
        exclude_res = [_re.compile(p, _re.IGNORECASE) for p in exclude_strs]
        addr_strs = raw.get("exclude_address_patterns", [])
        addr_res = [_re.compile(p, _re.IGNORECASE) for p in addr_strs]

        # 截掉参考文献章节及之后内容。标题须独占一行（行首+换行结尾），
        # 区分正文提及（如“详见参考文献[5]”，非行首不匹配）。冒号兼容全角：/半角:，
        # 因 PyMuPDF 文本常见“参考文献：\n”“References:\n” 等变体，原 \s*\n 会漏截。
        ref_re = _re.compile(r'(?:^|\n)\s*#{0,3}\s*(参考文献|References|REFERENCES|致谢|Acknowledg|附录|Appendix)[：:．.\s]*(?:\n|$)')
        ref_match = ref_re.search(text)
        if ref_match:
            text = text[:ref_match.start()]

        # 全角引用标记归一化：中文期刊 PDF 常用全角方括号 ［1］/［1-2］/［1，2］，
        # 抽取正则与 citation_marker 提取只认半角 [n]（实测 LSTM.pdf 34 处全角标记
        # 全部漏抽）。仅归一化内容为数字/连字符/逗号的全角括号，不影响文字性括号。
        text = _re.sub(r'［\s*([0-9\-–,，\s]+?)\s*］',
                       lambda m: '[' + m.group(1).replace('，', ',') + ']', text)
        # 清理 MinerU 残缺 LaTeX（孤立 \command 转 unicode、去孤立 $），避免引用句裸露符号
        text = self._clean_citation_latex(text)
        # 删 mineru 图片 vlm 描述标签 <summary>natural_image</summary>（连同内容），
        # 否则下面去 HTML 标签后剩 'natural_image' 等噪声混入分句污染前后文。
        text = _re.sub(r'(?m)^\s*<summary>.*?</summary>\s*$', '', text)
        # 删 HTML 表格块（<table>...</table>，可能跨行），否则去标签后单元格文本混入分句。
        text = _re.sub(r'<table>.*?</table>', '', text, flags=_re.DOTALL)
        # 清理HTML标签
        text = _re.sub(r'<sup>([^<]*)</sup>', lambda m: ('['+m.group(1)+']') if _re.match(r'^[0-9,\-–，\s]+$', m.group(1)) and _re.search(r'\d', m.group(1)) else m.group(1), text)
        text = _re.sub(r'<sub>([^<]*)</sub>', lambda m: ('['+m.group(1)+']') if _re.match(r'^[0-9,\-–，\s]+$', m.group(1)) and _re.search(r'\d', m.group(1)) else m.group(1), text)
        text = _re.sub(r'<[^>]+>', '', text)
        # 删除 markdown 表格行、图/表标题行、章节标题行（mineru 输出，非正文，不当引用句/前后文）
        text = '\n'.join(line for line in text.split('\n')
                        if not line.strip().startswith('|')
                        and not _re.match(r'^\s*(图|表|Fig\.?|Figure|Table)\s*\d', line)
                        and not _re.match(r'^\s*#{1,6}\s', line)
                        # 论文首页元数据行（非正文）。中文/英文摘要区各一套，兼容两种格式：
                        #   ① [收稿日期]2026 / [作者简介]xxx（方括号包裹，可能无冒号）
                        #   ② 收稿日期：2026 / Keywords: / 网络首发： / \*基金 / ISSN / URL（无方括号）
                        # 不清会与正文引用句合并（无句号分隔），judge 看到句首元数据误剔正文引用。
                        and not _re.match(r'^\s*\[(收稿日期|网络首发日期?|引用格式|题目|作者|作者简介|关键词|中图分类号|文献标识码|基金(?:项目)?|作者单位|单位地址|文章编号|出版确认|网络首发|CLC|DOI|doi)\]', line)
                        and not _re.match(r'^\s*(收稿日期|网络首发日期?|引用格式|题目|作者|作者简介|关键词|中图分类号|文献标识码|基金(?:项目)?|作者单位|单位地址|文章编号|出版确认|网络首发|CLC|DOI|doi|Keywords?|Abstract)\s*[:：]', line)
                        and not _re.match(r'^\s*\\?\*.*基金', line)
                        and not _re.match(r'^\s*(ISSN|CN\s\d|https?://|www\.)', line)
                        # 英文作者单位行（英文摘要区）："3. College of Civil Engineering, ... China)"
                        # 不含引用标记但与正文引用句相邻（无句号分隔），合并后 judge 误剔正文引用。
                        and not _re.match(r'^\s*\(?\d+\.\s+.*China[；;)]?\s*$', line)
                        # 作者署名行（中文/英文摘要区）："卓祖汀[1,2],杨帆[1,2]..." / "Zhuo Zuting[1,2]..."
                        # / "LIU Tingting[1,2], LÜ Dagang[3]..." 含多个 [n] 但非引用句。删英文单位后与
                        # 正文引用句相邻合并（无句号），judge 看句首署名误剔整句→[1][2]漏(mechanical/
                        # ResNet 均如此)。判据：整行由 名字[编号组] 以逗号/分号连接、末尾无 prose 动词
                        # （正文 Johnson[4],Smith[7] proposed… 提出 等动词破坏组结构不匹配，故不误删）。
                        # 名字块支持中文(2-4字)与英文(含变音 Ü/é)，旧版仅英文[a-z]漏 LÜ/中文署名。
                        and not _re.match(r'^(?:[一-鿿]{2,4}|[A-ZÀ-Þ][\wÀ-ÿ]*(?:\s+[A-ZÀ-Þ][\wÀ-ÿ]*)*)\s*\[\d[^]]*\]\s*(?:[,，;；]\s*(?:[一-鿿]{2,4}|[A-ZÀ-Þ][\wÀ-ÿ]*(?:\s+[A-ZÀ-Þ][\wÀ-ÿ]*)*)\s*\[\d[^]]*\]\s*)+\s*[,。.;；]?$', line)
                        # mineru 图片行（非正文）：图片 markdown ![](images/..)/[](images/..)、
                        # vlm 图片描述 alt（含 no text/symbols）、图片尺寸标注（d 320px×320px）。
                        # 整行过滤，删后引用句前文自动落到上一正文句；若前后全是这类噪声则置空，
                        # 满足"前后文只有图片/表格/标题时返回空"。
                        and not _re.match(r'^\s*!?\[.*\]\(images/.*\)\s*$', line)
                        and not _re.search(r'\(no (?:visible )?text or symbols\)', line)
                        and not _re.match(r'^\s*[a-z]\s+[\$]?\d+\s*px\s*(?:×|x|\\times)\s*\$?\d+\s*px', line))

        # 保护 "et al." 的句号
        text = text.replace('et al.', 'et al§')
        text = text.replace('et al．', 'et al§')
        for abbr in ['Fig.', 'Eq.', 'No.', 'Vol.', 'pp.', 'cf.', 'i.e.', 'e.g.']:
            text = text.replace(abbr, abbr.replace('.', '§'))

        # 全文分句
        sentences = _re.split(r'(?<=[。！？])\s*|(?<=[.!?])(?!\d)\s*', text)
        sentences = [s.replace('§', '.').strip() for s in sentences if s.strip() and len(s.strip()) > 5]

        certain, uncertain = [], []
        for i, sent in enumerate(sentences):
            # 前文：上一句；若是章节标题（markdown # 或 数字编号短标题）则置空（用户要求前文不要标题）
            _prev = sentences[i - 1] if i > 0 else ""
            if _prev and (_re.match(r'^\s*#{1,6}\s', _prev) or (_re.match(r'^\s*\d+(?:\.\d+)*\.?\s+\S{2,40}$', _prev) and len(_prev) < 30) or _re.match(r'^\s*(图|表|Figure|Table|Fig\.?)\s*\d', _prev)):
                _prev = ""
            # 后文：下一句；若是图/表/章节标题则置空（用户要求前后文不要图表标题）
            _next = sentences[i + 1] if i + 1 < len(sentences) else ""
            if _next and (_re.match(r'^\s*#{1,6}\s', _next) or _re.match(r'^\s*(图|表|Figure|Table|Fig\.?)\s*\d', _next)):
                _next = ""
            # 排除非引用句
            if any(er.search(sent) for er in exclude_res):
                continue
            if any(ar.search(sent) for ar in addr_res) and not _re.search(r'\[\s*\d+\s*\]', sent):
                continue
            # 排除图片路径行（mineru输出的(images/xxx)会被(年份)模式误匹配）
            if _re.search(r'\(images/', sent) and not _re.search(r'\[\s*\d+\s*\]', sent):
                continue
            # 排除纯引用符号堆叠句：句末/词后上标汇总被抽成只含 [n] 标记的独立句（无实质
            # 正文），不当引用句——否则 [6][7][8-10] 等会与正文引用句重复出现。
            _body = _re.sub(r'\[\s*[1-9]\d*(?:\s*[-–,，]\s*[1-9]\d*)*\s*\]', ' ', sent)
            _body = _re.sub(r'[\s,，。.；;:：、（）()\[\]]+', '', _body).strip()
            if not (_re.search(r'[一-鿿]', _body) or _re.search(r'[A-Za-z]{2,}', _body)):
                continue
            matched = False
            for p in patterns:
                m = p.search(sent)
                if m:
                    _all_raw = _re.findall(r'\[\s*[1-9]\d*(?:\s*[-–,，]\s*[1-9]\d*)*\s*\]', sent) or [m.group()]
                    _seen = set(); _all_mk = []
                    for _mk in _all_raw:
                        if _mk not in _seen:
                            _seen.add(_mk); _all_mk.append(_mk)
                    certain.append({
                        "sentence": sent,
                        "citation_marker": m.group(),
                        "citation_markers": _all_mk,
                        "context_before": _prev,
                        "context_after": _next,
                    })
                    matched = True
                    break
            if not matched and cues_re.search(sent) and _re.search(r'\[\s*\d|\(\s*(?:19|20)\d{2}|等人|et\s+al|文献\[', sent):
                # 要求含引用标记痕迹（[n]/年份/等人/et al/文献[），排除"上述研究表明""综上"等无标记纯总结句被误判为引用句
                uncertain.append({
                    "sentence": sent,
                    "citation_marker": "",
                    "context_before": _prev,
                    "context_after": _next,
                })
        return certain, uncertain

    def _llm_extract_citations_fallback(self, text: str) -> list:
        """正则零命中时的全文引用句提取兜底：GLM 分块扫描全文找出引用句。

        覆盖正则模式之外的引用格式（作者-年份、无标记转述、特殊符号标记等）。
        全文按 3000 字分块（引用句不跨块截断的粒度由 LLM 语句边界弥补），每块
        提取的句子按 citation 模式补 marker。返回结构同 _extract_citations 的确定项。
        """
        if not text.strip():
            return []
        sysp = ("你是学术引用句识别专家。从给定文本中找出所有引用他人研究成果的句子"
                "（含文献编号标记、作者+年份、或明确提及他人工作的转述）。"
                "逐字摘录原句，不得改写。只输出JSON："
                '{"data":{"results":[{"sentence":"引用句原文"}]}}，无引用句输出空数组。')
        chunks = [text[i:i + 3000] for i in range(0, len(text), 2800)][:12]  # 上限 12 块
        from concurrent.futures import ThreadPoolExecutor
        _chunk_errors: list = []
        def _extract_cite_chunk(chunk):
            try:
                return self._glm.chat_json(sysp, f"文本：\n{chunk}", timeout=60.0,
                                           max_tokens=2000, temperature=0.0)
            except Exception as exc:  # noqa: BLE001  瞬时错误容忍：其余块照常提取
                _chunk_errors.append(exc)
                return {}
        # 并发提取（2026-09-08）：原串行 12 块 × 2s = 24s 是引用工具主瓶颈；
        # 并发度 = GLM 配额（换更高配额 LLM 时随环境变量整体放大）
        from config.settings import settings as _st
        with ThreadPoolExecutor(max_workers=min(max(1, _st.GLM_MAX_CONCURRENCY), len(chunks))) as _pool:
            _raw_results = list(_pool.map(_extract_cite_chunk, chunks))
        # 全部块失败 = 模型不可达：fail closed（契约 2026-09-08：GLM 不可用时禁止
        # 把"提取不到"当成业务结论返回 success）。部分块失败仍降级容忍。
        if chunks and len(_chunk_errors) == len(chunks):
            raise RuntimeError(
                f"GLM 引用句分块提取全部失败（{len(chunks)} 块），模型不可达：{_chunk_errors[0]}")
        found: list = []
        for d in _raw_results:
            d = d.get("data", d) if isinstance(d, dict) else {}
            for r in (d.get("results") or []):
                if not isinstance(r, dict):
                    continue
                sent = str(r.get("sentence") or "").strip()
                if len(sent) < 8:
                    continue
                marker = ""
                for _p in self._CITATION_PATTERNS:
                    _m = _p.search(sent)
                    if _m:
                        marker = _m.group()
                        break
                if sent not in [f["sentence"] for f in found]:
                    found.append({"sentence": sent, "citation_marker": marker,
                                  "context_before": "", "context_after": ""})
        return found

    def _llm_confirm_citations(self, uncertain: list) -> list:
        """LLM 判定不确定句是否引用句（分批，每批10句）。返回确认的引用句。"""
        if not uncertain:
            return []
        sysp = ("你是学术引用句识别专家。判断给定句子是否包含引用他人研究成果的表述（引用句）。"
                "引用句是指引用、提及或参考他人工作的句子。"
                "只输出JSON：{\"data\":{\"results\":[{\"sentence\":\"句子\",\"is_citation\":true}]}}")
        confirmed = []
        batch_size = 10
        for start in range(0, len(uncertain), batch_size):
            batch = uncertain[start:start + batch_size]
            sent_list = "\n".join([f"[{i}] {u['sentence'][:120]}" for i, u in enumerate(batch)])
            try:
                d = self._glm.chat_json(sysp, f"判断以下句子是否引用句：\n{sent_list}",
                                        timeout=60.0, max_tokens=500, temperature=0.0)
                d = d.get("data", d) if isinstance(d, dict) else {}
                results = d.get("results", [])
                for r in results:
                    if r.get("is_citation"):
                        sent = r.get("sentence", "")
                        for u in batch:
                            if u["sentence"][:50] in sent or sent[:50] in u["sentence"]:
                                confirmed.append(u)
                                break
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("引用句 GLM-5.2 确认失败") from exc
        return confirmed

    def _llm_judge_citations(self, candidates: list) -> list:
        """LLM 批量判定每个候选是否正文引用句，替代 confirm+filter+is_body 正则兜底。

        正则召回按引用标记匹配会混入参考文献条目/作者署名/图标题/无标记总结句，
        一次性批量送 LLM 综合判定只留正文引用句，去掉 is_body 正则补丁。
        LLM 异常或漏判时倾向保留避免误杀真引用句。批次间并发执行。
        """
        if not candidates:
            return []
        if len(candidates) <= 1:
            return list(candidates)
        sysp = ("你是学术引用句识别专家。判断每个条目是否为正文中引用他人工作的引用句。\n"
                "正文引用句 is_citation=true：正文中完整陈述句，引用标记 [n]/[n,m]/[n-m] 或"
                " (作者,年份)/X等(2020)/et al. 嵌入句中，含 提出/表明/发现/采用/基于/利用/运用/"
                "showed/demonstrated/proposed/found 等动词提及他人研究成果。\n"
                "非引用句 is_citation=false，满足任一即 false：\n"
                "  - 参考文献条目：以 [n] 或数字编号开头，含 作者+题名+期刊/出版社+年卷期页码 等著录格式，无完整主谓；\n"
                "  - 作者署名：姓名+[n] 列表如 张三[1,2] 李四[3]，无陈述内容；\n"
                "  - 图/表标题：以 图N/Fig N/Table N 开头；\n"
                "  - 章节标题：以 # 或纯数字编号短标题开头；\n"
                "  - 元数据：以 关键词/中图分类号/文献标识码/收稿日期/基金项目/作者简介/摘要/Abstract 开头；\n"
                "  - 无引用标记的纯总结句：上述研究表明/综上/由此可见 等，无 [n]/年份/等人/et al。\n"
                "只输出 JSON：data 为数组，每元素含 index(0起的输入编号) 和 is_citation(true=正文引用句/false=非引用句)，"
                "每条都要判定，index 必须与输入编号对应。")
        batch_size = 10
        batches = [candidates[i:i + batch_size] for i in range(0, len(candidates), batch_size)]
        # 批量并发判定：走通用 _glm_chat_batch 自动并发，无需手写 ThreadPoolExecutor。
        prompts = ['判断以下条目是否正文引用句，按 index 输出判定：\n' +
                   '\n'.join([f'[{i}] ' + c['sentence'][:250] for i, c in enumerate(batch)])
                   for batch in batches]
        batch_ds = self._glm_chat_batch(sysp, prompts, temperature=0.0,
                                        timeout=90.0, max_tokens=1500)
        drop_ids = set()
        for batch, d in zip(batches, batch_ds):
            drop_idx = set()
            if d is not None:
                try:
                    d = d.get('data', d) if isinstance(d, dict) else d
                    results = d if isinstance(d, list) else (d.get('results', []) if isinstance(d, dict) else [])
                    for r in results:
                        if not isinstance(r, dict) or bool(r.get('is_citation')):
                            continue
                        idx = r.get('index')
                        if isinstance(idx, int) and 0 <= idx < len(batch):
                            drop_idx.add(idx)
                        elif isinstance(idx, str) and idx.strip().isdigit():
                            i2 = int(idx.strip())
                            if 0 <= i2 < len(batch):
                                drop_idx.add(i2)
                except Exception:  # noqa: BLE001
                    pass
                logger.info('LLM判定引用句：本批%d 剔除非引用句%d', len(batch), len(drop_idx))
            for i in drop_idx:
                drop_ids.add(id(batch[i]))
        kept = [c for c in candidates if id(c) not in drop_ids]
        logger.info("LLM判定引用句：保留%d/%d(剔除非引用句%d)",
                    len(kept), len(candidates), len(candidates) - len(kept))
        return kept

    def _load_citation_training_pairs(self, request) -> list:
        """citation-intent 预处理训练集资源 → few-shot 样本对。

        样本形态（2026-09-15 用户定调）= 题目 + 文本 + 分类结果三件套：
        document_title + document_text（含引用句）+ intent（reference_entries
        字段在但可空，仅甲方契约要求）。citation_sentence 为兼容字段，未提供时
        由 normalize 层从 document_text 提取。相似度覆盖匹配用 citation_sentence，
        few-shot 渲染带题目与文本。文件损坏/无资源返回空列表（内置路径）。
        """
        try:
            _res = ((request.params or {}).get("resolved_resources") or {}).get("preprocessed_training_set")
            _uri = str((_res or {}).get("storage_uri") or "")
            if not _uri:
                return []
            from pathlib import Path as _P
            _path = _P(_uri.removeprefix("project://")) if _uri.startswith("project://") else _P(_uri)
            if not _path.is_file():
                return []
            from infrastructure.resources.normalize import normalized_rows_for as _rows_for
            _rows = _rows_for(_path)
            if _rows is None:
                from infrastructure.resources.normalize import _normalize_citation_training_rows
                import json as _json3
                _doc = _json3.loads(_path.read_text(encoding="utf-8"))
                _raw = _doc if isinstance(_doc, list) else (
                    next((v for v in _doc.values() if isinstance(v, list)), [])
                    if isinstance(_doc, dict) else [])
                _rows = _normalize_citation_training_rows(_raw)
            pairs = []
            for _r in _rows:
                if not isinstance(_r, dict):
                    continue
                _sent = str(_r.get("citation_sentence") or "").strip()
                _intent = str(_r.get("intent") or "").strip()
                if not _sent or not _intent:
                    continue
                pairs.append({
                    "text": _sent,                     # 相似度匹配面（引用句）
                    "intent": _intent,                 # 分类结果
                    "title": str(_r.get("document_title") or _r.get("title") or "").strip(),
                    "doc": str(_r.get("document_text") or _r.get("text") or "").strip(),
                })
            return pairs
        except Exception:  # noqa: BLE001 - 训练集损坏不影响内置路径
            logger.warning("引用意图训练集解析失败（保持内置路径）", exc_info=True)
            return []

    def _llm_label_citations(self, citations: list, is_sentiment: bool, rule, request,
                             fewshot: list = None) -> list:
        """批量 LLM 判引用句的情感/意图。全部走 _glm_chat_batch 自动并发，
        无手写 ThreadPoolExecutor：每批一次 chat_json 并发，返回不全则直接逐句并发补全
        （取代旧的串行重试3次——补全并发更快，且只在 GLM 偶发返回不全时才触发）。

        句内多引用拆分后同一原句存在多条记录：意图判定文本优先用该条的局部子片段
        sub_span（无则整句），保证不同文献引用各自判定不混淆；返回条目 = 输入引用句
        条目 + LLM 标签/置信度（保留 citation_marker/sub_span/上下文，供后置规则
        引擎与结果组装按条对齐）。"""
        label_field = 'sentiment' if is_sentiment else 'intent'
        sysp = self._system_prompt(rule, request)
        if fewshot:
            # 训练集 few-shot 口径校准：样本 = 题目+文本+分类结果三件套，
            # 标引风格影响判定（如"借鉴方法"偏背景还是方法引入，按用户口径走）；
            # 最终标签仍由语义判定+相似度覆盖决定
            _samples = "\n".join(
                (f"题目：{p.get('title') or '（无题目）'}\n"
                 f"文本：{(p.get('doc') or p['text'])[:120]}\n"
                 f"意图：{p['intent']}")
                for p in fewshot[:10])
            sysp += ("\n\n人工标注样本（用户标引口径，判定风格向其对齐）：\n" + _samples)
        batch_size = 10
        batches = [citations[i:i + batch_size] for i in range(0, len(citations), batch_size)]
        _fallback_label = '中立' if is_sentiment else '用于背景介绍'

        def _judge_text(c):
            return str(c.get('sub_span') or c.get('sentence') or '')

        def _merge(c, r):
            r = r if isinstance(r, dict) else {}
            item = dict(c)
            item[label_field] = str(r.get(label_field) or '').strip() or _fallback_label
            conf = r.get('confidence')
            item['confidence'] = conf if conf is not None else 0.5
            return item

        # 第一步：所有批次第一次 chat_json 并发。输出按 index 对齐（不复述原句，
        # 输出 token 从 ~100字/条 降到 ~20token/条，实测整批耗时近乎减半）。
        # 被引文献元数据（_cited_meta：题名,年份）随行附带作辅助信号
        prompts = ['引用句列表：\n' +
                   '\n'.join([f'[{i}] ' + _judge_text(c)[:250] +
                              (f'（被引文献：{c.get("_cited_meta")}）' if c.get("_cited_meta") else '')
                              for i, c in enumerate(batch)]) +
                   '\n按 index 输出每条的判定，不要复述原句。'
                   for batch in batches]
        batch_ds = self._glm_chat_batch(sysp, prompts, temperature=0.0,
                                        timeout=90.0, max_tokens=1500)
        all_results = []
        _pending = []  # 未被覆盖的引用句条目，统一并发补全
        for batch, d in zip(batches, batch_ds):
            results = []
            if d is not None:
                d = d.get('data', d) if isinstance(d, dict) else d
                results = d if isinstance(d, list) else (d.get('results', []) if isinstance(d, dict) else [])
            covered = {}
            for r in results:
                if not isinstance(r, dict):
                    continue
                # index 对齐优先（prompt 已要求输出 index）；LLM 偶发漏 index 或
                # 仍回显原句时，退回句子子串匹配兜底
                _idx = r.get('index')
                if isinstance(_idx, int) and 0 <= _idx < len(batch) and _idx not in covered:
                    covered[_idx] = r
                    continue
                if isinstance(_idx, str) and _idx.strip().isdigit():
                    _i2 = int(_idx.strip())
                    if 0 <= _i2 < len(batch) and _i2 not in covered:
                        covered[_i2] = r
                        continue
                _rs = str(r.get('sentence', ''))[:60]
                for i, c in enumerate(batch):
                    if i in covered:
                        continue
                    _cs = _judge_text(c)[:60]
                    if _rs and (_rs in _judge_text(c) or _cs in _rs or _cs in str(r.get('sentence', ''))):
                        covered[i] = r
                        break
            for i, c in enumerate(batch):
                if i in covered:
                    all_results.append(_merge(c, covered[i]))
                else:
                    _pending.append(c)

        # 第二步：所有未覆盖句子逐句并发补全。
        if _pending:
            _prompts = ['引用句列表：\n[0] ' + _judge_text(c)[:250] +
                        '\n按 index 输出判定，不要复述原句。' for c in _pending]
            _comp_ds = self._glm_chat_batch(sysp, _prompts, temperature=0.0,
                                            timeout=60.0, max_tokens=500)
            for c, _d2 in zip(_pending, _comp_ds):
                if _d2 is None:
                    all_results.append(_merge(c, None))
                    continue
                _d2 = _d2.get('data', _d2) if isinstance(_d2, dict) else _d2
                _r2 = _d2 if isinstance(_d2, list) else (_d2.get('results', []) if isinstance(_d2, dict) else [])
                all_results.append(_merge(c, _r2[0] if _r2 else None))

        # 第三步：兜底 normalize（空/非法标签）。GLM 偶发返回空/非法（数量够不触发补全，
        # 直通后置校验会 raise 致整篇失败）。空或非法 → 兜底为 fallback 标签并降置信，
        # 记日志便于追踪质量问题；不 raise，保证任务不因个别句子整体失败。
        valid = {'支持', '中立', '有局限性'} if is_sentiment else {'用于背景介绍', '用于引入研究方法', '用于结果比较'}
        _fixed = 0
        for _r in all_results:
            if not isinstance(_r, dict):
                continue
            _v = (_r.get(label_field) or '').strip()
            if _v not in valid:
                _r[label_field] = _fallback_label
                try:
                    _r['confidence'] = min(float(_r.get('confidence', 0.5) or 0.5), 0.5)
                except (TypeError, ValueError):
                    _r['confidence'] = 0.5
                _fixed += 1
        if _fixed:
            logger.warning('引文标签兜底：%d条空/非法标签→%s', _fixed, _fallback_label)
        return all_results

    def _glm_chat_batch(self, system_prompt, user_prompts, *, temperature=None,
                        timeout=None, max_tokens=None, max_workers=None):
        """批量并发 GLM chat_json。多次 GLM 调用统一走此方法自动并发，
        无需每处手写 ThreadPoolExecutor。

        user_prompts: list[str] -> list[result]（与输入顺序一一对应）。
        单个调用异常返回 None（调用方自行过滤/兜底），不因一句失败拖垮整批。
        len<=1 串行不建池；默认 max_workers=GLM_MAX_CONCURRENCY（换更高配额
        LLM 时调环境变量即可整体放大；瞬时超限由 glm_client 429/1214 退避兜底）。
        """
        from config.settings import settings as _settings
        max_workers = max(1, int(max_workers or _settings.GLM_MAX_CONCURRENCY))
        if not user_prompts:
            return []
        if len(user_prompts) == 1:
            try:
                return [self._glm.chat_json(system_prompt, user_prompts[0],
                                            temperature=temperature, timeout=timeout,
                                            max_tokens=max_tokens)]
            except Exception:  # noqa: BLE001
                return [None]
        from concurrent.futures import ThreadPoolExecutor

        def _one(_p):
            try:
                return self._glm.chat_json(system_prompt, _p, temperature=temperature,
                                           timeout=timeout, max_tokens=max_tokens)
            except Exception:  # noqa: BLE001
                return None

        with ThreadPoolExecutor(max_workers=min(max_workers, len(user_prompts))) as _ex:
            return list(_ex.map(_one, user_prompts))

    def _verify_citation_labels(self, labeled: list, is_sentiment: bool, rule) -> list:
        """后置规则引擎：读 yaml 的 pattern_rules，对 LLM 输出做校验+调分。

        - boost：句子匹配规则的 necessary 且不含 exclude → 增强该标签置信度
        - override：句子匹配规则但 LLM 标了别的标签 → 按 weight 决定是否改标签
        """
        import re as _re
        label_field = "sentiment" if is_sentiment else "intent"
        rules = rule.raw.get("pattern_rules", [])
        if not rules:
            return labeled

        for item in labeled:
            sent = item.get("sentence", "")
            current_label = item.get(label_field, "")
            current_conf = float(item.get("confidence", 0.5) or 0.5)

            for r in rules:
                necessary = r.get("necessary", [])
                exclude = r.get("exclude", [])
                rule_label = r.get("label", "")
                action = r.get("action", "boost")
                weight = float(r.get("weight", 0.3))

                # 检查 necessary（须含任一）
                if not any(_re.search(pat, sent) for pat in necessary):
                    continue
                # 检查 exclude（含则不触发）
                if any(_re.search(pat, sent) for pat in exclude):
                    continue

                if action == "boost" and rule_label == current_label:
                    # 增强：LLM 标对了，加置信度
                    item["confidence"] = min(1.0, current_conf + weight)
                elif action == "override" and rule_label == current_label:
                    # 冲突调分：LLM 标了这个标签但规则认为应该改
                    override_to = r.get("override_to", "")
                    if override_to and current_conf < 0.8:
                        # LLM 置信度不高 → 按规则改
                        item[label_field] = override_to
                        item["confidence"] = max(0.5, current_conf - weight + 0.3)

        return labeled

    # ==================== 概念定义识别 ==================== #

    _DOMAIN_LABEL_NAMES = {
        "01": "数学与计算科学", "02": "力学与工程力学", "03": "物理学与应用物理", "04": "化学与化学科学",
        "05": "天文学与空间科学", "06": "地球科学与地质资源", "07": "测绘遥感与地理信息", "08": "气象海洋科学",
        "09": "生物科学与生物技术", "10": "医学与卫生健康", "11": "药学与毒理学", "12": "农业科学与农业工程",
        "13": "林业畜牧兽医与水产", "14": "材料科学与材料工程", "15": "矿业与矿物加工", "16": "石油与天然气工程",
        "17": "冶金与金属加工", "18": "机械工程与智能制造", "19": "仪器仪表与计量检测", "20": "能源与动力工程",
        "21": "核科学与核工程", "22": "电气工程与电力系统", "23": "电子通信与半导体", "24": "自动化与控制工程",
        "25": "人工智能与计算机技术", "26": "化学工程与过程工业", "27": "轻工食品与纺织", "28": "建筑与土木工程",
        "29": "水利与水电工程", "30": "交通运输工程", "31": "航空航天工程", "32": "环境与安全工程",
    }

    def _execute_concept_definition(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """概念定义识别：极速版取全文→清洗→按句号分块→批量 LLM 抽取定义句
        (sentence+concept+pattern 一步到位)→合并去重。light 漏抽/LLM 判 0 →
        _source_pdf_path 回退 mineru 重抽重判（参考 rq-detect）。

        LLM 主导抽取（替代旧正则 markers 主导）：覆盖非经典句式("X指Y")，concept
        不空，不误召回公式说明/分类描述。去掉后置规则引擎（markers 关键词打分对
        非 markers 句式压低 confidence，LLM 已判+提 concept，规则多余）。
        """
        result = SemanticResult(code=code, name=fp.name)
        params = request.params or {}
        _src_path = params.get("_source_pdf_path")
        # 需规输入项 domain_label / output_format_requirement:
        # - domain_label【辅助影响】注入提示词作为领域语境(概念判定优先该领域术语),并随结果返回
        # - output_format_requirement【直接影响输出结构】JSON(默认)/CSV(附 csv_content)/
        #   数据库写入结构(附 database_records,DB 就绪字段命名)
        domain_label = str(params.get("domain_label") or "").strip()
        domain_name = self._DOMAIN_LABEL_NAMES.get(domain_label, "")
        if not domain_name and domain_label and domain_label != "自动识别":
            domain_name = domain_label  # 兼容直接传领域名称
        output_format = str(params.get("output_format_requirement") or "JSON").strip() or "JSON"
        text = (request.text or "").strip()

        # 兼容直接传 PDF/MD 路径
        if text.endswith((".pdf", ".md")) and os.path.exists(text):
            from infrastructure.document_parser.mineru_reader import process_to_text
            try:
                text = process_to_text(text).get("full_text", "") or ""
            except Exception:  # noqa: BLE001
                pass

        def _extract_defs(full_text: str) -> list:
            cleaned = self._clean_definition_text(full_text)
            if not cleaned.strip():
                return []
            chunks = self._definition_chunks(cleaned)
            if not chunks:
                return []
            domain_hint = ("\n文献所属领域：" + domain_name + "。概念判定优先考虑该领域的专业术语与表达习惯。"
                           if domain_name else "")
            sysp = (
                "你是科技文献概念定义识别专家。从给定文本中抽取概念定义句。"
                f"{domain_hint}\n"
                "定义句：解释某个概念/术语是什么的句子——X是指Y / X指Y / X是一种Y / "
                "X定义为Y（含 界定为/规定为/…的定义是/量化为/操作化为，如\"噪声水平定义为所添加"
                "噪声标准差与原始信号标准差的比值\"这类操作性定义）/ X即Y（亦即/即是/即为/意指 同此）"
                "/ X称为Y（统称为/称之为/命名为/定名为/叫作/又称/亦称/也称 同此）/ X指的是Y / "
                "X属于Y的类别 / 编号定义标签（\"定义1：…\"\"定义 2.1：…\"数学论文形式）/ "
                "数学条件式定义（若…则称满足…的X为Y）。\n"
                "非定义句（不抽）：描述重要性/作用/意义（X是...的关键/重要环节/前提/核心）；"
                "描述方法步骤/流程/操作（将X按...聚类 / 基于...进行）；陈述结果/发现（X是最好的 / "
                "结果表明）；公式符号说明（式中：l0为初始学习率 / γ为衰减系数）；比较/引述/数据描述；"
                "方法步骤中的术语缩写展开——括号只是中英/缩写对照，不是在解释概念是什么"
                "（使用R语言limma包识别差异表达基因（Differentially expressed genes，DEGs）/"
                "计算曲线下面积（Area Under Curve，AUC）/ 从TRRUST数据库下载转录因子"
                "（Transcription factors，TFs）-mRNA关系对）；章节标题（1.8 基因集富集分析"
                "（Gene set enrichment analysis，GSEA））；结果句（主成分分析（PCA）结果表明...）。\n"
                "只抽真正的概念定义句，宁缺毋滥，没有就返回空列表。\n"
                "每条输出：sentence（定义句原文，不含章节标题/换行符）、concept（被定义的概念词，"
                "简洁名词性术语）、pattern（定义句式，如 是一种/是指/即/指/称为）、confidence（0-1）。\n"
                "只输出JSON："
                '{"results":[{"sentence":"","concept":"","pattern":"","confidence":0.9}]}'
            )
            prompts = ["文本片段（第%d块）：\n%s" % (i + 1, c) for i, c in enumerate(chunks)]
            batch_ds = self._glm_chat_batch(
                sysp, prompts, temperature=0.0, timeout=90.0, max_tokens=2000, max_workers=5)
            # 契约（2026-09-10 用户拍板）：调用失败 ≠ 无定义句——任一块 GLM 调用
            # 失败直接报错，禁止把 None 静默当 0 条返回；空列表只表示"真没有"
            # （曾出现瞬时失败被吞、有定义句的论文返回 0 条且无法区分的案例）
            _failed = sum(1 for d in batch_ds if d is None)
            if _failed:
                raise RuntimeError(
                    f"GLM 调用失败（{_failed}/{len(batch_ds)} 块），概念定义识别中止，请重试")
            defs = []
            for d in batch_ds:
                if d is None:
                    continue
                d = d.get("data", d) if isinstance(d, dict) else d
                rs = d if isinstance(d, list) else (d.get("results", []) if isinstance(d, dict) else [])
                for r in rs:
                    if not isinstance(r, dict):
                        continue
                    sent = (r.get("sentence") or "").replace("\n", " ").strip()
                    concept = (r.get("concept") or "").strip()
                    if not sent or not concept or len(concept) > 50:
                        continue
                    try:
                        conf = min(1.0, float(r.get("confidence", 0.7) or 0.7))
                    except (TypeError, ValueError):
                        conf = 0.7
                    # 置信度地板（2026-09-10 用户拍板"不合适就别要"）：LLM 对
                    # 方法步骤缩写展开/章节标题类会自觉打 0.4~0.6，真定义句
                    # 0.85+——<0.7 直接丢弃，宁缺毋滥
                    if conf < 0.7:
                        continue
                    defs.append({
                        "sentence": sent, "concept": concept,
                        "pattern": (r.get("pattern") or "").strip(),
                        "confidence": conf,
                    })
            return defs

        # 情况1：light 取文空 → 回退 mineru 重抽
        if not text and _src_path and os.path.exists(_src_path):
            logger.info("concept-definition light 取文空,回退 mineru 重抽: %s", _src_path)
            text = self._mineru_full_refallback(_src_path) or ""
        if not text:
            raise ValueError("概念定义识别需提供 text 字段（文献全文）")

        defs = _extract_defs(text)

        # 情况2：LLM 判 0 → 回退 mineru 重抽重判（light 可能漏段，mineru 全文补）。
        # 仅当现有文本较短(疑似 PyMuPDF 局部抽取)才重抽——双栏/扫描 PDF 的首遍
        # 解析本就已回退 mineru 全文，重抽得到相同文本只白耗一遍解析(约70s/篇)。
        if not defs and _src_path and os.path.exists(_src_path):
            if len(text) < 6000:
                logger.info("concept-definition LLM 判 0,文本较短(%d字),回退 mineru 重抽重判: %s",
                            len(text), _src_path)
                _mtxt = self._mineru_full_refallback(_src_path) or ""
                if _mtxt and _mtxt != text:
                    text = _mtxt
                    defs = _extract_defs(text)
            else:
                logger.info("concept-definition LLM 判 0,文本已是全文(%d字),不重抽", len(text))

        # LLM 清洗定义句：抽取的 sent 可能粘定义结束后的非定义尾巴（如"其表达式
        # 如式(1)所示"/"有助于模型..."），清洗只留定义核心，再组装定位
        def _clean_sents(defs_list):
            if not defs_list:
                return defs_list
            sysp = (
                "你是文本清洗专家。输入一条从论文抽取的概念定义句，可能含定义结束后的"
                "非定义补充内容。输出纯净的定义句——只保留 X是指Y / X指Y / X是一种Y 定义本身，"
                "去掉定义完整结束后的非定义尾巴：公式引用（其表达式如式N所示、见式N）、"
                "图表引用（如图N、见表N）、作用意义（有助于、从而、可以、能够 开头的描述）、"
                "举例（例如、比如）、结果陈述。\n"
                "保留：定义句本身的限定与补充（如 其中Z表示、也就是、即 开头的补充）"
                "是定义组成部分勿删。整句若已是纯净定义无尾巴，原样返回。\n"
                "只输出JSON："
                '{"results":[{"cleaned":"纯净定义句"}]}')
            prompts = ["定义句：%s" % d["sentence"] for d in defs_list]
            batch = self._glm_chat_batch(
                sysp, prompts, temperature=0.0, timeout=60.0, max_tokens=500, max_workers=5)
            for d, c in zip(defs_list, batch):
                if c is None:
                    continue
                c = c.get("data", c) if isinstance(c, dict) else c
                rs = c if isinstance(c, list) else (c.get("results", []) if isinstance(c, dict) else [])
                if rs and isinstance(rs[0], dict):
                    cl = (rs[0].get("cleaned") or "").strip()
                    if cl:
                        d["sentence"] = cl
            return defs_list

        defs = _clean_sents(defs)

        # 合并去重 + 组装（source_position 容错跨行 \n：LLM 抽的 sent 已去 \n，原文
        # 可能跨行含 \n，用去 \n 后匹配 + 映射回原文位置，确保字符位置有值）
        import re as _re2

        def _flat_to_orig(flat_idx: int) -> int:
            """去 \\n 后的第 flat_idx 个字符在原文 text 中的位置"""
            count = 0
            for i, ch in enumerate(text):
                if ch == "\n" or ch == "\r":
                    continue
                if count == flat_idx:
                    return i
                count += 1
            return len(text)

        out, seen = [], set()
        # 规范化折叠匹配（第三级兜底）：清洗 LLM 在裁剪边界常改标点/空格
        # （原文"…状态，"→清洗"…状态。"；"G1 和 G2"→"G1和G2"），精确 find 与
        # 去 \n find 都落空 → 位置返回 null。两侧同口径剥掉空白/数字/标点后
        # 匹配，经索引映射回原文真实位置（旧实现只剥 sent 不剥 text，必然失配）
        _strip_cls = r"[\s\d,，。.；;:：、（）()\[\]+\-*/=<>「」『』\"'‘’“”·…～~]"
        _norm_chars: list = []
        _norm_map: list = []
        for _i, _ch in enumerate(text):
            if not _re2.match(_strip_cls, _ch):
                _norm_chars.append(_ch)
                _norm_map.append(_i)
        _text_norm = "".join(_norm_chars)

        def _locate_norm(s: str):
            _s_norm = _re2.sub(_strip_cls, "", s)
            if len(_s_norm) < 6:
                return None
            _fi = _text_norm.find(_s_norm)
            if _fi < 0:  # 尾部仍异（截断长度差）：前半匹配兜底
                _fi = _text_norm.find(_s_norm[:max(10, len(_s_norm) // 2)])
            if _fi < 0:
                return None
            _end_fi = min(_fi + len(_s_norm) - 1, len(_norm_map) - 1)
            return _norm_map[_fi], _norm_map[_end_fi] + 1

        for item in defs:
            sent = item["sentence"]
            if sent in seen:
                continue
            seen.add(sent)
            start = text.find(sent)
            end = start + len(sent) if start >= 0 else None
            if start < 0:
                # 原文跨 \n，去 \n 后匹配再映射回原文位置
                flat = _re2.sub(r"[\n\r]", "", text)
                fs = flat.find(sent)
                if fs >= 0:
                    start = _flat_to_orig(fs)
                    end = _flat_to_orig(fs + len(sent) - 1) + 1
            if start < 0:
                _loc = _locate_norm(sent)
                if _loc:
                    start, end = _loc
            out.append({
                "sentence": sent,
                "concept": item["concept"],
                "definition": sent,
                "normalized_concept": item["concept"] or None,
                "pattern": item.get("pattern", ""),
                "context_before": "",
                "context_after": "",
                "source_position": {
                    "start": start if start >= 0 else None,
                    "end": end,
                },
                "confidence": item["confidence"],
            })

        # 需规参数回传与输出格式化:domain_label 随结果返回;output_format_requirement
        # 决定附加输出结构(CSV 文本 / 数据库写入结构记录)。out 原为定义条目列表,
        # 带需规参数时包装为 {definitions: [...], ...附加字段} 的 dict。
        fmt = output_format.upper()
        need_extra = bool(domain_label) and (domain_label != "自动识别")
        if need_extra or (fmt.startswith("CSV") or "数据库" in output_format or "DATABASE" in fmt):
            packed: Dict[str, Any] = {"definitions": out}
            if need_extra:
                packed["domain_label"] = domain_label
                packed["domain_name"] = domain_name or ""
                for item in out:
                    if isinstance(item, dict):
                        item.setdefault("domain_label", domain_label)
            if fmt.startswith("CSV") and out:
                import io as _io
                import csv as _csv
                buf = _io.StringIO()
                writer = _csv.writer(buf)
                writer.writerow(["concept", "definition_sentence", "pattern", "confidence"])
                for item in out:
                    writer.writerow([item.get("concept"), item.get("sentence"),
                                     item.get("pattern"), item.get("confidence")])
                packed["csv_content"] = buf.getvalue()
                packed["output_format"] = "csv"
            elif ("数据库" in output_format or "DATABASE" in fmt) and out:
                packed["database_records"] = [{
                    "concept_id": f"cdef_{index:04d}",
                    "concept": item.get("concept"),
                    "definition_sentence": item.get("sentence"),
                    "definition_pattern": item.get("pattern"),
                    "confidence": item.get("confidence"),
                    "domain_label": domain_label or None,
                } for index, item in enumerate(out, start=1)]
                packed["output_format"] = "database"
            out = packed
        result.success = True
        result.data = out
        defs_for_conf = out.get("definitions") if isinstance(out, dict) else out
        result.confidence = sum(x["confidence"] for x in defs_for_conf or []) / max(len(defs_for_conf or []), 1)
        result.raw = json.dumps({"n_definitions": len(defs_for_conf or []),
                                 "domain_label": domain_label, "output_format": output_format}, ensure_ascii=False)
        return result

    def _clean_definition_text(self, text: str) -> str:
        """清洗全文：去期刊网络首发说明段/章节标题/图表/元数据/图片行（供 LLM 抽取定义句）。

        复用 citation _extract_citations 行级过滤经验。PyMuPDF 章节标题无 ## 前缀
        （如"1 建模原理""1.3 运力..."），用数字编号短行正则删（独占行、无标点、<30字）。
        """
        import re as _re
        # 截参考文献及之后
        ref_re = _re.compile(r"(?:^|\n)\s*#{0,3}\s*(参考文献|References|REFERENCES|致谢|Acknowledg|附录|Appendix)[：:．.\s]*(?:\n|$)")
        m = ref_re.search(text)
        if m:
            text = text[:m.start()]
        # 删期刊网络首发说明段（录用定稿/排版定稿/整期汇编定稿等期刊模板术语，非论文概念；
        # 从"网络首发:"到"视为正式出版"整段删，避免 LLM 抽出期刊术语当定义句）
        text = _re.sub(r"网络首发[:：].*?视为正式出版[。.]?\s*", "", text, flags=_re.DOTALL)
        # 删 HTML 表格/图片描述标签
        text = _re.sub(r"<table>.*?</table>", "", text, flags=_re.DOTALL)
        text = _re.sub(r"(?m)^\s*<summary>.*?</summary>\s*$", "", text)
        text = _re.sub(r"<[^>]+>", "", text)
        # 行级过滤：章节标题/图表标题/元数据/图片 markdown
        keep = []
        for line in text.split("\n"):
            s = line.strip()
            if not s:
                continue
            if s.startswith("|"):
                continue
            if _re.match(r"^\s*(图|表|Fig\.?|Figure|Table)\s*\d", line):
                continue
            if _re.match(r"^\s*#{1,6}\s", line):
                continue
            # PyMuPDF 数字编号章节标题（无 ##）："1 建模原理" "1.3 运力..." 独占短行
            # （无标点、<30字；正文短句常含逗号/句号不误删）
            if (_re.match(r"^\s*\d+(?:\.\d+)*[\.．]?\s+\S{2,40}$", line)
                    and len(s) < 30 and not _re.search(r"[。！？，；,;]", s)):
                continue
            if _re.match(r"^\s*\[(收稿日期|网络首发日期?|引用格式|题目|作者|作者简介|关键词|中图分类号|文献标识码|基金(?:项目)?|作者单位|单位地址|文章编号|出版确认|网络首发|CLC|DOI|doi)\]", line):
                continue
            if _re.match(r"^\s*(收稿日期|网络首发日期?|引用格式|题目|作者|作者简介|关键词|中图分类号|文献标识码|基金(?:项目)?|作者单位|单位地址|文章编号|出版确认|网络首发|CLC|DOI|doi|Keywords?|Abstract)\s*[:：]", line):
                continue
            if _re.match(r"^\s*(ISSN|CN\s\d|https?://|www\.)", line):
                continue
            if _re.match(r"^\s*!?\[.*\]\(images/.*\)\s*$", line):
                continue
            keep.append(line)
        return "\n".join(keep)

    def _definition_chunks(self, text: str, chunk_size: int = 5000) -> list:
        r"""按句末边界切分（中英双语），聚合成 ≤chunk_size 的块（供 LLM 批量抽取定义句）。

        英文修复（2026-09-08）：原先只按 。！？ 切分，英文全文无中文句号 → 整篇
        坍缩成 1 个超大块（失去分块并行，超长文有截断风险）。现补 .!? 边界；
        `(?!\d)` 防 3.5 小数误切，英文句末要求后跟空白（PDF 常见粘连 "word.Next"
        无法凭空恢复边界）。句子重组保留原文空白（capture 组拼回）：LLM 抽取句
        后续用 text.find 在原文定位，丢空白会断链。
        """
        import re as _re
        pieces = _re.split(r"(?<=[。！？])(\s*)|(?<=[.!?])(?!\d)(\s+)", text)
        chunks, cur = [], ""
        # pieces 形如 [句, 空白, 句, 空白, ..., 句?]；交替分支未参与的捕获组返回
        # None，统一兜底成 ""。句与其后空白原样拼回。
        i = 0
        while i < len(pieces):
            sent = pieces[i] or ""
            sep = (pieces[i + 1] or "") if i + 1 < len(pieces) else ""
            i += 2
            if not sent and not sep:
                continue
            if len(cur) + len(sent) > chunk_size and cur:
                chunks.append(cur)
                cur = sent.lstrip()
            else:
                cur += sent + sep
        if cur:
            chunks.append(cur)
        return chunks

    def _mineru_full_refallback(self, src_path: str) -> str:
        """light 漏抽时回退 mineru 全文重抽（不截断，供概念定义全文抽取）。

        参考 rq-detect _rq_mineru_refallback，但不截 8000（概念定义需全文）。
        """
        from pathlib import Path as _Path
        from infrastructure.document_parser.upload_reader import extract_bytes as _eb
        from infrastructure.document_parser.mineru_api_client import _count_pages as _cp
        from infrastructure.document_parser.concurrency_pool import get_page_budget_pool as _gpp
        _content = _Path(src_path).read_bytes()
        _pages = _cp(_content) if src_path.lower().endswith(".pdf") else 1
        _pool = _gpp()
        _pool.acquire(_pages)
        try:
            return _eb(_content, _Path(src_path).name, light=False) or ""
        finally:
            _pool.release(_pages)

    # ---- 科研实体识别：用户上传资源（领域示例语料 / 标准词表）加载与归一 ---- #
    @staticmethod
    def _read_uploaded_resource_json(descriptor) -> list:
        """读用户上传资源并取【归一化行】（与全站资源消费同一口径）。

        优先走 infrastructure.resources.normalize 的注册表（规则层/LLM 容错层
        归一化的标准结构——磁盘原文件可能是中文 key 或 LLM 重构前形态）；
        注册表未命中再回退直接解析磁盘文件。失败返回 []（不影响主流程）。
        """
        try:
            uri = str((descriptor or {}).get("storage_uri") or "")
            if not uri:
                return []
            from config.settings import settings as _settings
            from infrastructure.resources.normalize import (
                normalized_rows_for, resource_path,
            )
            path = resource_path(uri, _settings.PROJECT_ROOT)
            if path is not None:
                rows = normalized_rows_for(path)
                if rows:
                    return rows
                import json as _json3
                if path.suffix.lower() == ".json" and path.is_file():
                    data = _json3.loads(path.read_text(encoding="utf-8"))
                    return data if isinstance(data, list) else []
            return []
        except Exception:  # noqa: BLE001
            logger.warning("科研实体识别资源文件解析失败", exc_info=True)
            return []

    _DOMAIN_TYPE_SYSTEMS_CACHE: tuple = (None, None)  # (mtime_ns, {领域: types})

    @classmethod
    def _builtin_domain_type_system(cls, domain: str) -> list:
        """内置领域类型体系（rules/ner/domain_type_systems.json，热加载）。

        领域下拉的 11 个大类各有专属类型集（医学→药物/疾病/疗法…，计算机→算法/
        模型/数据集…）。返回该领域的 types 列表；未命中返回空（走默认 13 类）。
        """
        import json as _jsonD
        from pathlib import Path as _PD
        path = _PD(__file__).resolve().parents[2] / "rules" / "ner" / "domain_type_systems.json"
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            return []
        cached_mtime, cached = cls._DOMAIN_TYPE_SYSTEMS_CACHE
        if cached_mtime == mtime and cached is not None:
            systems = cached
        else:
            try:
                systems = _jsonD.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return []
            cls._DOMAIN_TYPE_SYSTEMS_CACHE = (mtime, systems)
        return systems.get(str(domain or "").strip()) or []

    def _load_custom_ontology(self, descriptor) -> dict:
        """domain-ner 用户本体 → {domain, types:[{code,name,description,examples}]}。

        本体为配置型资源（原样透传无行结构）：优先读 types/类型 数组；无则全树
        扫描含 code+name 的节点（宽容）。解析失败返回空 dict（保持内置类型体系）。
        """
        try:
            uri = str((descriptor or {}).get("storage_uri") or "")
            if not uri:
                return {}
            from config.settings import settings as _settings
            from infrastructure.resources.normalize import resource_path
            path = resource_path(uri, _settings.PROJECT_ROOT)
            if path is None:
                return {}
            doc = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except Exception:  # noqa: BLE001 - 本体不可解析时走内置类型体系
            return {}
        types: list = []

        def _collect(node):
            if isinstance(node, dict):
                code = str(node.get("code") or node.get("type_code") or "").strip()
                name = str(node.get("name") or node.get("label") or node.get("类型名") or "").strip()
                if code and name and len(types) < 50:
                    types.append({
                        "code": code, "name": name,
                        "description": str(node.get("description") or node.get("描述") or "").strip(),
                        "examples": [str(x) for x in (node.get("examples") or node.get("示例") or [])][:6],
                    })
                for v in node.values():
                    _collect(v)
            elif isinstance(node, list):
                for v in node:
                    _collect(v)

        if isinstance(doc, dict):
            _collect(doc.get("types") or doc.get("类型") or doc)
        elif isinstance(doc, list):
            _collect(doc)
        return {"domain": (str(doc.get("domain") or doc.get("领域") or "").strip()
                           if isinstance(doc, dict) else ""),
                "types": types}

    @classmethod
    def _custom_ontology_types(cls, descriptor) -> set:
        """用户本体的类型集合（并入 domain-ner 防串域白名单）。

        本体为配置型资源（原样透传，无固定行结构），从其 JSON 任意层级
        收集全大写类型标识（如 BRIDGE_COMPONENT / LOAD_TYPE）：命中
        ^[A-Z][A-Z_0-9]{2,}$ 的字符串、或"类型体系"/"types"数组元素。
        上限 50 个防滥用；解析失败返回空集（不影响内置白名单）。
        """
        try:
            uri = str((descriptor or {}).get("storage_uri") or "")
            if not uri:
                return set()
            from config.settings import settings as _settings
            from infrastructure.resources.normalize import resource_path
            path = resource_path(uri, _settings.PROJECT_ROOT)
            if path is None:
                return set()
            doc = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
        except Exception:  # noqa: BLE001 - 本体不可解析时走内置白名单
            return set()
        found: set = set()
        import re as _reO
        _cap = _reO.compile(r"^[A-Z][A-Z_0-9]{2,}$")
        def _walk(node):
            if len(found) >= 50:
                return
            if isinstance(node, dict):
                for key, value in node.items():
                    if str(key) in ("类型体系", "types", "type_system", "categories",
                                    "entity_types") and isinstance(value, list):
                        for item in value:
                            _t = str(item or "").strip().upper()
                            if _t:
                                found.add(_t)
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)
            elif isinstance(node, str):
                _t = node.strip()
                if _cap.match(_t):
                    found.add(_t)
        _walk(doc)
        return found

    def _load_ner_fewshot(self, descriptor) -> str:
        """领域示例语料 → few-shot 文本。条目 {"text": 示例, "entities": [{"text","type"}]}。"""
        rows = [r for r in self._read_uploaded_resource_json(descriptor) if isinstance(r, dict)]
        lines = []
        for row in rows[:3]:
            text = str(row.get("text") or "").strip()
            ents = [e for e in (row.get("entities") or []) if isinstance(e, dict)
                    and e.get("text") and e.get("type")]
            if not text or not ents:
                continue
            lines.append("示例文本：%s\n识别结果：%s" % (
                text[:200], "；".join("%s(%s)" % (e["text"], e["type"]) for e in ents[:8])))
        return "\n\n".join(lines)

    def _load_ner_standard_index(self, descriptor) -> dict:
        """标准词表 → {变体casefold: {zh,en,type}}。兼容扁平列表与 doc_id 包壳两种形态。"""
        raw = self._read_uploaded_resource_json(descriptor)
        clusters = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            # doc_id 包壳形态：{"doc_id":.., "entities":[簇...]} → 下钻一层
            if "entities" in row and "canonical" not in row:
                clusters.extend(e for e in (row.get("entities") or []) if isinstance(e, dict))
            else:
                clusters.append(row)
        index = {}
        for c in clusters:
            # 兼容两种形态：用户原始格式 canonical/type 与基础设施归一化格式 text/label
            canon = str(c.get("canonical") or c.get("text") or "").strip()
            if not canon:
                continue
            info = {"zh": canon, "en": str(c.get("canonical_en") or c.get("en") or "").strip(),
                    "type": str(c.get("type") or c.get("label") or "").strip()}
            for v in [canon] + [str(x) for x in (c.get("variants") or [])]:
                v = v.strip()
                if v:
                    index.setdefault(v.casefold(), info)
        return index

    @staticmethod
    def _apply_ner_standard_mapping(entities: list, index: dict) -> None:
        """确定性查表归一：实体文本(精确/包含)命中词表变体 → 回填 standard_names 等字段。"""
        for e in entities:
            if not isinstance(e, dict):
                continue
            txt = str(e.get("text") or "").strip()
            cf = txt.casefold()
            hit = index.get(cf)
            if hit is None:  # 精确未命中 → 包含式：变体完整出现在实体文本中（或反之）
                for variant, info in index.items():
                    if (variant and (variant in cf or cf in variant)
                            and min(len(variant), len(cf)) >= 2):
                        hit = info
                        break
            if hit:
                e["standard_names"] = {"zh": hit["zh"], "en": hit["en"] or "—"}
                e["mapping_status"] = "已映射"
                e["mapping_confidence"] = 1.0
                e["mapping_source"] = "用户标准词表"
            else:
                e["standard_names"] = None
                e["mapping_status"] = "未映射"
                e["mapping_confidence"] = 0.0
                e["mapping_source"] = "用户标准词表"

    _LOC_LEXICON_CACHE: tuple = (None, None)  # (mtime_ns, lexicon)

    @classmethod
    def _location_lexicon(cls) -> list:
        """地名词表热加载（rules/ner/lexicon_locations.json，mtime_ns 缓存）。
        词表随后期数据扩充改文件即生效，无需重启。"""
        import json as _json
        from pathlib import Path as _P
        p = _P(__file__).resolve().parents[2] / "rules" / "ner" / "lexicon_locations.json"
        try:
            mt = p.stat().st_mtime_ns
        except OSError:
            return []
        if cls._LOC_LEXICON_CACHE[0] == mt:
            return cls._LOC_LEXICON_CACHE[1] or []
        try:
            data = _json.loads(p.read_text(encoding="utf-8"))
            terms = sorted([t for t in (data.get("zh") or []) + (data.get("en") or [])
                            if isinstance(t, str) and len(t) >= 2], key=len, reverse=True)
        except Exception:  # noqa: BLE001
            terms = []
        cls._LOC_LEXICON_CACHE = (mt, terms)
        return terms

    def _boost_locations_from_lexicon(self, entities: list, eff_text: str) -> list:
        """地名词表后验补抽：词表词在文本中出现且未被任何现有实体覆盖、后面
        不紧跟机构后缀（"中国+人民银行"类复合专名不拆）时补一条 LOCATION。
        每个词只补首个有效出现，避免同词刷屏。"""
        import re as _re
        terms = self._location_lexicon()
        if not terms:
            return entities
        # 现有实体覆盖区间（任意类型——org/person 内部不重复抽地名）
        spans = []
        for e in entities:
            if not isinstance(e, dict):
                continue
            try:
                s, t = int(e.get("start", -1)), int(e.get("end", -1))
            except (TypeError, ValueError):
                continue
            if 0 <= s < t <= len(eff_text):
                spans.append((s, t))
        # 已有 LOCATION 实体的归一文本集（词被包含则不重复补）
        import unicodedata as _ud
        def _n(x):
            return _re.sub(r"\s+", "", _ud.normalize("NFKC", str(x)).casefold())
        have_loc = {_n(e.get("text")) for e in entities
                    if isinstance(e, dict) and e.get("type") == "LOCATION"}
        # 复合专名守卫：词后紧接的机构后缀（中国+人民银行 / 中国+科学院…）
        suffix_guard = _re.compile(
            r"^(人民银行|银行|科学院|学术期刊|期刊|大学|学院|公司|医院|集团|石化|石油|"
            r"移动|联通|电信|电网|地震台网|台网|地质|航天|烟草|船舶|航空|铁道|建筑|"
            r"电建|核电|中铁|中车|中冶|邮政|出版|教育|海油|船舶|广电|人寿|保险|证券|基金)")
        added = []
        for term in terms:
            nt = _n(term)
            if any(_lex_contains(nt, h) or _lex_contains(h, nt) for h in have_loc if h):
                continue
            for m in _re.finditer(_re.escape(term), eff_text):
                s, t = m.span()
                if any(s < be and t > bs for bs, be in spans):
                    continue  # 出现在现有实体内部
                if term == "中国" and suffix_guard.match(eff_text[t:t + 4]):
                    continue  # 复合专名前缀（中国人民银行等）不拆
                added.append({"text": term, "type": "LOCATION",
                              "start": s, "end": t, "confidence": 0.9})
                break
        return entities + added

    _VARIANT_CACHE: tuple = (None, None)  # (mtime_ns, {norm_variant: group})

    @classmethod
    def _variant_index(cls) -> dict:
        """变体归一词表热加载（rules/ner/lexicon_variants.json）→ {norm(变体): group}。"""
        import json as _json
        from pathlib import Path as _P
        p = _P(__file__).resolve().parents[2] / "rules" / "ner" / "lexicon_variants.json"
        try:
            mt = p.stat().st_mtime_ns
        except OSError:
            return {}
        if cls._VARIANT_CACHE[0] == mt:
            return cls._VARIANT_CACHE[1] or {}
        try:
            data = _json.loads(p.read_text(encoding="utf-8"))
            idx = {}
            for grp in data.get("groups") or []:
                if not isinstance(grp, dict):
                    continue
                for v in [grp.get("canonical")] + list(grp.get("variants") or []):
                    if isinstance(v, str) and v.strip():
                        idx[_norm_surface(v)] = grp
        except Exception:  # noqa: BLE001
            idx = {}
        cls._VARIANT_CACHE = (mt, idx)
        return idx

    def _merge_ner_variants(self, entities: list) -> list:
        """实体去重 + 变体识别（2026-09-11 用户定稿语义）：
        **原文输出不变**——text 保持文献里的表面形式（"3-（1-甲基吡咯烷-2-基）
        吡啶"照原样输出）；变体词表只做"认知识别"：
        ① 同归一文本+同类型去重（保留首个位置）；
        ② 同变体组（类型一致）的多条归并为一条——保留首次出现的原文形式，
        其余表面形式进 variants；附 normalized_name（组 canonical，如"尼古丁"）
        与 canonical_en 供辨识——下次见到变体知道是什么，但不替换原文。"""
        idx = self._variant_index()
        out, seen_key = [], {}
        for e in entities:
            if not isinstance(e, dict) or not e.get("text"):
                continue
            original = str(e["text"])
            n = _norm_surface(original)
            grp = idx.get(n)
            if grp and grp.get("type") == e.get("type"):
                # 原文不改写；只加标识字段。归并键用组 canonical（同组变体
                # 尼古丁/Nicotine/学名 → 一条实体，variants 收齐全部形式）。
                # 词表命中是确定性查表：映射置信 0.95、source=variant_lexicon
                # ——覆盖 LLM 同轮生成的推测值（0.5/llm_inline）
                e = dict(e)
                e["normalized_name"] = grp["canonical"]
                e["mapping_status"] = "已映射"
                e["mapping_confidence"] = 0.95
                e["mapping_source"] = "variant_lexicon"
                if grp.get("canonical_en"):
                    e["canonical_en"] = grp["canonical_en"]
                    e.setdefault("standard_names", {})
                    if not e["standard_names"].get("en"):
                        e["standard_names"]["en"] = grp["canonical_en"]
                    if not e["standard_names"].get("zh"):
                        e["standard_names"]["zh"] = grp["canonical"]
                n = _norm_surface(grp["canonical"])
            key = (n, e.get("type"))
            if key in seen_key:
                first = seen_key[key]
                vs = set(first.get("variants") or [])
                vs.add(original)
                first["variants"] = sorted(vs)
                continue
            seen_key[key] = e
            out.append(e)
        return out

    _RESEARCH_LEX_CACHE: dict = {}  # {rel_path: (mtime_ns, terms)}
    _NER_INFLIGHT: int = 0  # 当前活跃 NER 执行数（分块自适应：>1 时退回单次调用）
    _NER_INFLIGHT_LOCK = threading.Lock()

    @classmethod
    def _terms_lexicon(cls, rel: str) -> list:
        """terms 型词表热加载（{"terms": [...]}，mtime_ns 缓存）。"""
        import json as _json
        from pathlib import Path as _P
        p = _P(__file__).resolve().parents[2] / rel
        try:
            mt = p.stat().st_mtime_ns
        except OSError:
            return []
        cached = cls._RESEARCH_LEX_CACHE.get(rel)
        if cached and cached[0] == mt:
            return cached[1] or []
        try:
            terms = sorted([t for t in (_json.loads(p.read_text(encoding='utf-8')).get('terms') or [])
                            if isinstance(t, str) and len(t) >= 2], key=len, reverse=True)
        except Exception:  # noqa: BLE001
            terms = []
        cls._RESEARCH_LEX_CACHE[rel] = (mt, terms)
        return terms

    def _boost_research_from_lexicons(self, entities: list, text: str) -> list:
        """科研 NER 词表后验补抽（2026-09-10，与通用 NER 地名词表同模式）：
        INSTRUMENT（GPU/风洞——LLM 对 prompt 示例执行不稳）与 METHOD（具体
        算法名——英文长文 >10k 截断段 LLM 看不到）两词表全文扫描补抽；
        词泛指词（机器学习/深度学习）按规则排除不入表。每词只补首个有效出现，
        已被现有实体（任意类型）覆盖或归一包含的不重复补。"""
        import re as _re
        spans = []
        for e in entities:
            if not isinstance(e, dict):
                continue
            try:
                s, t = int(e.get('start', -1)), int(e.get('end', -1))
            except (TypeError, ValueError):
                continue
            if 0 <= s < t <= len(text):
                spans.append((s, t))
        have = {_norm_surface(e.get('text')) for e in entities
                if isinstance(e, dict) and e.get('text')}
        for rel, typ in (('rules/ner/lexicon_instruments.json', 'INSTRUMENT'),
                         ('rules/ner/lexicon_methods.json', 'METHOD')):
            for term in self._terms_lexicon(rel):
                nt = _norm_surface(term)
                if any(_lex_contains(nt, h) or _lex_contains(h, nt) for h in have if h):
                    continue
                for m in _re.finditer(_re.escape(term), text):
                    s, t = m.span()
                    if any(s < be and t > bs for bs, be in spans):
                        continue
                    ent = {'text': term, 'type': typ, 'start': s, 'end': t,
                           'confidence': 0.9}
                    entities = entities + [ent]
                    spans.append((s, t))
                    have.add(nt)
                    break
        return entities

    def _execute_ner(self, code: str, request: SemanticRequest, fp, rule) -> SemanticResult:
        """命名实体/关系识别：全文直送 LLM（支持文件路径，超长截断）。

        LLM 优先版：text 可为实体文本片段、文件路径（.pdf/.md→MinerU全文）、或 mineru markdown 全文。
        全文超过 NER_TEXT_LIMIT 字时截取前段（命名实体多集中在标题/摘要/引言/作者机构/方法节）；
        start/end 字符位置相对实际送入 LLM 的（截断后）文本。ner_relation 无位置字段，不受影响。
        """
        NER_TEXT_LIMIT = 10000  # 超长全文截断阈值（字）

        result = SemanticResult(code=code, name=fp.name)
        text = (request.text or "").strip()
        if not text:
            raise ValueError("命名实体识别需提供 text 字段")
        # 文件路径 → 读全文（.pdf 走 MinerU，.md 直接读）
        if os.path.exists(text) and text.lower().endswith(('.pdf', '.md')):
            from infrastructure.document_parser.mineru_reader import process_to_text
            try:
                doc = process_to_text(text)
                text = doc.get("full_text", "") or ""
            except Exception:  # noqa: BLE001
                pass
        if not text:
            raise ValueError("命名实体识别需提供 text 字段")

        # 参考文献章节截断（2026-09-10 用户反馈）：参考文献条目里的作者/
        # 机构是著录信息不是正文实体（BOPPS.pdf 一次抽出 20+ 参考文献作者
        # 人名），通用/科研/领域 NER 均只面向正文。标题独占行判定与引用
        # 引擎 ref_re 同款。
        _ref_m = re.search(
            r'(?:^|\n)\s*#{0,3}\s*(参考文献|References|REFERENCES)\s*[：:．.\s]*(?:\n|$)', text)
        if _ref_m:
            text = text[:_ref_m.start()]

        truncated = len(text) > NER_TEXT_LIMIT
        eff_text = text[:NER_TEXT_LIMIT] if truncated else text

        system_prompt = self._system_prompt(rule, request)
        # 用户上传资源接线（2026-09-05 分层设计）：
        # ① multi_domain_scientific_corpus=领域示例语料 → few-shot 注入 prompt（识别增强，类型体系不变）
        # ② manually_labeled_data=标准词表 → 变体→标准词归一索引（识别后映射，见下方 _apply_standard_mapping）
        # ③ general_domain_annotated_corpus=通用标注语料 → 同①机制 few-shot（general-ner
        #    专属槽，2026-09-15 接线：此前为死槽——上传后无消费端）
        # ④ domain-ner 专属（2026-09-16 接线）：ontology_classification_system=用户本体
        #    → 类型体系整体注入提示词（答案空间替换，见下方白名单同步）；domain_labeled
        #    _training_data=领域标注训练数据 → 同①机制 few-shot（此前均为死槽）
        _res = (request.params or {}).get("resolved_resources") or {}
        _fewshot = self._load_ner_fewshot(
            _res.get("multi_domain_scientific_corpus") or _res.get("general_domain_annotated_corpus")
            or _res.get("domain_labeled_training_data"))
        _std_index = self._load_ner_standard_index(_res.get("manually_labeled_data"))
        _ontology = (self._load_custom_ontology(_res.get("ontology_classification_system"))
                     if code == 'ner_domain' else {})
        # 领域引导（2026-09-16 用户定调：领域是请求参数，本体只需给 types）：
        # 请求参数 domain（前端领域下拉）优先；未选时回落本体可选的 domain 字段；
        # 两者都无则不注入（内置领域自动判定）。无论是否上传本体都注入领域引导
        _domain_label = ""
        if code == 'ner_domain':
            _domain_label = str((request.params or {}).get("domain") or "").strip()
            if _domain_label in ("", "auto", "自动识别", "请选择专业领域"):
                _domain_label = str(_ontology.get("domain") or "").strip()
        # 内置领域类型体系回落（2026-09-16 用户定调：用户传本体→用户体系；
        # 未传本体+选了领域→该领域内置专属体系；都没有→默认 13 类自动判定）
        _builtin_types: list = []
        if code == 'ner_domain' and not _ontology.get("types") and _domain_label:
            _builtin_types = self._builtin_domain_type_system(_domain_label)
        if _ontology.get("types") or _builtin_types:
            _lines = []
            for _t in (_ontology["types"] if _ontology.get("types") else _builtin_types):
                _ex = "、".join(_t["examples"][:4])
                _lines.append(f"- {_t['code']}（{_t['name']}）：{_t['description']}"
                              + (f"，如 {_ex}" if _ex else ""))
            system_prompt += (
                ("\n\n【用户上传本体类型体系" if _ontology.get("types")
                 else "\n\n【领域类型体系（内置）")
                + "（重要：忽略前述默认类型体系，实体只能属于下列类型，"
                "type 字段用英文 code 输出；不属于任何类型的词一律不要输出为实体）】"
                + (f"\n领域：{_domain_label}" if _domain_label else "")
                + "\n" + "\n".join(_lines))
        elif _domain_label:
            # 未上传本体但请求参数指定了领域：仅注入领域引导（类型仍用内置体系，
            # 实体 domain 标签按该领域标注）
            system_prompt += f"\n\n本次识别面向【{_domain_label}】领域，实体领域标签统一标注为该领域。"
        if _fewshot:
            system_prompt += "\n\n【领域示例（用户上传语料，few-shot 校准实体边界与类型风格）】\n" + _fewshot
        if code in ('ner_research', 'ner_domain'):
            system_prompt += (
                "\n\n【标准词输出（与识别同轮完成）】对识别出的每个实体同时给出：\n"
                "- std_zh：学术规范的中文标准词\n"
                "- std_en：学术规范的英文标准词\n"
                "在原有识别 JSON 的每个实体对象中追加 \"std_zh\", \"std_en\" 两个字段。"
            )
        user_payload = {"text": eff_text, "meta": request.meta}
        # 长文对半分块并发（2026-09-10 响应提速，ResNet 篇 10k 单次 65s → ~30s）：
        # 按句边界切两块各自送 LLM 并行，第二块实体位置加偏移后合并；分块后
        # 单块更短，GLM 生成也更快。位置校验循环按 eff_text 全文复核兜底。
        # 自适应（2026-09-10 批量优化）：仅当自己是当前唯一活跃 NER 执行时才
        # 分块——批量 6 篇若都分块，在途请求 6×2=12 路挤满 GLM 配额反而墙钟
        # 翻倍（科研批量 72s 实测）；批量时各篇退回单次调用，配额留给篇间并发。
        _chunk_ok = False
        with self.__class__._NER_INFLIGHT_LOCK:
            _chunk_ok = self.__class__._NER_INFLIGHT <= 1
            self.__class__._NER_INFLIGHT += 1
        try:
            if _chunk_ok and len(eff_text) > 6000:
                import re as _reC
                _cut = eff_text.rfind("。", 0, len(eff_text) // 2)
                if _cut < 3000:
                    _cut = eff_text.rfind(". ", 0, len(eff_text) // 2)
                if _cut < 3000:
                    _cut = len(eff_text) // 2
                _chunks = [(eff_text[:_cut + 1], 0), (eff_text[_cut + 1:], _cut + 1)]
                _prompts = [self._render_user_prompt({"text": c, "meta": request.meta}, request.params)
                            for c, _ in _chunks]
                _batch = self._glm_chat_batch(system_prompt, _prompts, timeout=120.0,
                                              max_tokens=3000, max_workers=2)
                out = []
                for (_c, _off), _d in zip(_chunks, _batch):
                    if _d is None:
                        continue
                    _rows = _d.get("data", _d) if isinstance(_d, dict) else _d
                    for _e in (_rows if isinstance(_rows, list) else []):
                        if isinstance(_e, dict) and _off:
                            try:
                                _e["start"] = int(_e.get("start", -1)) + _off
                                _e["end"] = int(_e.get("end", -1)) + _off
                            except (TypeError, ValueError):
                                pass
                        out.append(_e)
                data = {"data": out}  # 下游 evidence/raw 组装沿用 data 变量
            else:
                user_prompt = self._render_user_prompt(user_payload, request.params)
                data = self._glm.chat_json(system_prompt, user_prompt, timeout=120.0, max_tokens=3000)
                out = data.get("data", data) if isinstance(data, dict) else data
        finally:
            with self.__class__._NER_INFLIGHT_LOCK:
                self.__class__._NER_INFLIGHT -= 1

        if code in ('ner_research', 'ner_domain') and isinstance(out, list):
            for _ent in out:
                if not isinstance(_ent, dict):
                    continue
                _szh = str(_ent.pop("std_zh", "") or "").strip()
                _sen = str(_ent.pop("std_en", "") or "").strip()
                if _szh or _sen:
                    _ent.setdefault("standard_names", {"zh": _szh, "en": _sen})
                    # 同轮生成的标准词只暂存（不标状态/置信度）——下方批量标准化
                    # 路径接管：独立调用会自报置信度（2026-09-16 用户定调透传原始
                    # 值，原 0.75 地板导致全 0.75 太整齐），状态/来源在那里统一标注

        # 位置校验 + 去重（防 GLM 幻觉位置/重复实体）：长文本多实体时 GLM 可能
        # 退化——重复堆同一实体并编造递增 start/end（实测 48 个"氧化膜"）、末尾
        # JSON 截断残缺（无 type/start/confidence）。校验 eff_text[start:end]==text，
        # 不符则重新 find 定位、找不到则丢弃（幻觉）；同 text+type+domain 去重留首个。
        # 在 context 截取前做，确保 context 用真实位置。
        if isinstance(out, list) and eff_text:
            import re as _reV
            _seen = set()
            _deduped = []
            for _ent in out:
                if not isinstance(_ent, dict):
                    continue
                _txt = (_ent.get("text") or "").strip()
                # 英文粘连修复（2026-09-10 用户反馈）：PDF 关键词行常出现单词粘连
                # （TransformerModel）；CamelCase 边界确定性拆分，全小写粘连
                # （operationmanagementoptimization）由 prompt 指令让 LLM 补空格。
                # 拆分后折叠匹配仍能定位（find 忽略空白差异）。
                if len(_txt) >= 8 and " " not in _txt and _txt.isascii() and _txt.isalpha() \
                        and any(c.isupper() for c in _txt[1:]):
                    _txt = _reV.sub(r"(?<=[a-z])(?=[A-Z])", " ", _txt)
                    _ent["text"] = _txt
                _typ = (_ent.get("type") or "").strip()
                _dom = (_ent.get("domain") or "").strip()
                if not _txt or not _typ:
                    continue  # 丢弃残缺实体（无 text/type，末尾截断残渣）
                _key = (_txt, _typ, _dom)
                if _key in _seen:
                    continue  # 去重
                try:
                    _st = int(_ent.get("start", -1)); _en = int(_ent.get("end", -1))
                except (TypeError, ValueError):
                    _st, _en = -1, -1
                _ok = (0 <= _st < _en <= len(eff_text)
                       and eff_text[_st:_en].strip() == _txt)
                _idx = _st if _ok else -1  # 位置有效沿用原位置；无效则重新定位
                if not _ok:
                    _idx = eff_text.find(_txt)
                    if _idx < 0 and len(_txt) >= 4:
                        # 容错：去空白后匹配命中，回原文近似定位（前缀 find）
                        _ft = _reV.sub(r"\s+", "", _txt)
                        _flat = _reV.sub(r"\s+", "", eff_text)
                        _fi = _flat.find(_ft)
                        if _fi >= 0:
                            _probe = _txt[:6] if len(_txt) >= 6 else _txt[:4]
                            _idx = eff_text.find(_probe)
                if _idx < 0:
                    continue  # 文本不在原文 → 幻觉实体，丢弃
                _ent["start"] = _idx
                _ent["end"] = _idx + len(_txt)
                _seen.add(_key)
                _deduped.append(_ent)
            out = _deduped

        # 地名词表后验补抽（2026-09-10，仅通用 NER）：LLM 对正文裸国家名/省市        # 召回不稳（74 篇评测 ~45 条真实漏检全是"中国/四川/Tokyo"类行政区划词，
        # prompt 已加指引仍执行不全）。词表（rules/ner/lexicon_locations.json，
        # mtime 热加载）命中且不在复合专名内部（前有任一实体覆盖、后不接机构
        # 后缀如"中国+人民银行"）时确定性补一条 LOCATION，与关键词工具的
        # 场景词保座同模式；词表随后期数据滚动扩充。
        # 扫描全文而非 eff_text：eff_text 是全文前缀，位置坐标系一致；长文
        # （>10k 截断）后半段的城市（时序行为篇 39k 字）LLM 看不到但词表能补。
        if code == 'ner_general' and isinstance(out, list) and text:
            try:
                out = self._boost_locations_from_lexicon(out, text)
            except Exception:  # noqa: BLE001  词表缺失/损坏不影响主路径
                pass
            try:
                out = self._merge_ner_variants(out)
            except Exception:  # noqa: BLE001
                pass
            # 指代性/泛指词硬排除（2026-09-10 用户反馈"我国"误判地名；LLM 对
            # prompt 排除项执行不稳，词表级黑名单确定性兜底，对 booster/LLM
            # 两来源生效）
            _generic_loc = {'我国', '本国', '国内', '境外', '国外', '海外', '全国',
                            '全省', '全市', '本地', '我市', '我省', '我国境内'}
            out = [e for e in out
                   if not (isinstance(e, dict) and e.get('type') == 'LOCATION'
                           and str(e.get('text', '')).strip() in _generic_loc)]
        # 科研 NER 词表补抽（INSTRUMENT/METHOD，与通用 NER 地名词表同模式）
        if code == 'ner_research' and isinstance(out, list) and text:
            try:
                out = self._boost_research_from_lexicons(out, text)
            except Exception:  # noqa: BLE001
                pass
            # 设施名改判 INSTRUMENT（2026-09-10 用户定稿：系统/平台=仪器设备）：
            # "XX数据中心/共享中心/管理与服务系统"是托管数据的载体非数据集合，
            # 不算 DATASET；LLM 对 prompt 改判执行不稳，词尾确定性兜底。
            import re as _reF
            for _e in out:
                if isinstance(_e, dict) and _e.get('type') == 'DATASET' \
                        and _reF.search(r'(管理系统|服务系统|系统|数据中心|共享中心|平台)$',
                                        str(_e.get('text') or '').strip()):
                    _e['type'] = 'INSTRUMENT'
        # 专业领域 NER 防串域（2026-09-11 用户反馈：ResNet 计算机视觉论文全被
        # 硬塞成 化工/MATERIAL）：AI/CS 方法名（网络/算法/优化器/损失函数/插值/
        # 退火/均衡化词尾）不是任何领域的专业实体——LLM 对"空数组合法"执行
        # 不稳，词尾确定性丢弃；科研方法归 research-ner 的 METHOD。
        if code == 'ner_domain' and isinstance(out, list):
            import re as _reD
            _method_tail = _reD.compile(
                r'(网络|算法|优化器|损失函数|学习率|插值|退火|均衡化|模型|架构|'
                r'Network|network|[A-Za-z]\d{1,2}$|classifier|Encoder|Decoder)$')
            out = [e for e in out
                   if not (isinstance(e, dict)
                           and e.get('type') in ('MATERIAL', 'COMPOUND', 'REACTION', 'DRUG')
                           and _method_tail.search(str(e.get('text') or '').strip()))]
            # ① 类型体系泄漏丢弃（2026-09-11 地震动篇案例）：专业 NER 只允许三领域
            # 类型，LLM 偶发输出 METHOD/科研 等科研 NER 类型（K-means/主成分分析）——
            # 科研方法归 research-ner，此处整类丢弃。
            # 2026-09-12 修复：用户上传 ontology_classification_system 时白名单扩展为
            # 内置∪本体声明类型——此前硬编码白名单把自定义类型（BRIDGE_COMPONENT等）
            # 整类丢弃，"换本体=换类型体系"实际失效
            _domain_types = {'DRUG', 'DISEASE', 'TREATMENT', 'COMPOUND', 'REACTION',
                             'MATERIAL', 'THEORY', 'PHENOMENON', 'LAW', 'SYMPTOM',
                             'EQUIPMENT', 'TECHNIQUE', 'OTHER'}
            _onto_extra = self._custom_ontology_types(_res.get("ontology_classification_system"))
            if _onto_extra:
                # 用户本体 = 答案空间替换（2026-09-16 用户定调）：类型体系整体换成
                # 用户的（而非并入内置）——内置类型（如 DRUG）在用户体系下不是合法
                # 答案，应被过滤；提示词已同步注入用户类型定义
                _domain_types = _onto_extra
            elif _builtin_types:
                # 内置领域类型体系（2026-09-16）：选了领域未传本体 → 该领域专属
                # 类型集为合法答案（如 计算机→ALGORITHM/MODEL/DATASET…）
                _domain_types = {str(t.get("code") or "").strip().upper()
                                 for t in _builtin_types if t.get("code")}
            else:
                # 只传训练数据未传本体（2026-09-16 修复）：训练示例教 LLM 输出的
                # 自定义类型 code（如 DRUG_CLASS）不在内置 13 类白名单——曾整批被
                # 过滤为 0 条。示例类型并入白名单（∪ 内置，软扩展非替换）
                _train_types = set()
                for _r in self._read_uploaded_resource_json(_res.get("domain_labeled_training_data")):
                    if not isinstance(_r, dict):
                        continue
                    for _e in (_r.get("entities") or []):
                        if isinstance(_e, dict) and _e.get("type"):
                            _t = str(_e["type"]).strip().upper()
                            if _t:
                                _train_types.add(_t)
                if _train_types:
                    _domain_types |= _train_types
            out = [e for e in out
                   if not (isinstance(e, dict)
                           and str(e.get('type') or '') not in _domain_types)]
            # ② PHENOMENON 泛化丢弃（地震动篇 30+ 条判滥）：数据集/参数/方法/
            # 试验/分类标签词尾不是物理现象
            _not_phenomenon = _reD.compile(
                r'(记录集|数据集|语料库|参数|指标|震级|马赫数|分析方法|分析法|设计|试验|'
                r'类别|类场地|分析|准则|映射|反应谱|序列)$|^(PGA|PGV|PGA|PGD|SI|[A-Z]{2,5})$')
            out = [e for e in out
                   if not (isinstance(e, dict)
                           and e.get('type') == 'PHENOMENON'
                           and _not_phenomenon.search(str(e.get('text') or '').strip()))]
            # ③ 变体归一（2026-09-11 用户需求：化学学名↔通用名）：分子对接句的
            # "3-（1-甲基吡咯烷-2-基）吡啶"（尼古丁 IUPAC 学名）应归并为通用名
            # 尼古丁并保留学名进 variants——与通用 NER 共用 lexicon_variants.json
            # （组 type 须与实体 type 一致才合并），改词表即生效
            try:
                out = self._merge_ner_variants(out)
            except Exception:  # noqa: BLE001
                pass

        # 填充语境片段：用实体 start/end 在送入 LLM 的文本中截取所在句子，供前端
        # "语境片段"/"关联上下文"列展示（GLM output_schema 未含 context 字段）
        if isinstance(out, list) and eff_text:
            import re as _re
            for _ent in out:
                if not isinstance(_ent, dict) or _ent.get("context"):
                    continue
                try:
                    _st = int(_ent.get("start", -1))
                    _en = int(_ent.get("end", -1))
                except (TypeError, ValueError):
                    continue
                if _st < 0 or _st >= len(eff_text):
                    continue
                _en = min(_en if _en > _st else _st + 1, len(eff_text))
                # 前边界：st 前最近的句末标点/换行之后
                _start = 0
                for _m in _re.finditer(r"[。！？\.!\?\n]", eff_text[:_st]):
                    _start = _m.end()
                # 后边界：en 后最近的句末标点/换行
                _m2 = _re.search(r"[。！？\.!\?\n]", eff_text[_en:])
                _end = _en + (_m2.start() if _m2 else len(eff_text) - _en)
                _ctx = eff_text[_start:_end].strip().replace("\n", " ")
                if _ctx:
                    _ent["context"] = _ctx
                # 短语境扩展（2026-09-11 用户反馈"没有完整上下文"）：署名区/作者
                # 简介的实体常独占短行（ctx 仅实体本身），按行截取无信息量——
                # 前后各扩一行（连续署名/单位/简介行本是一个语义块），直到
                # ≥40 字或无法再扩
                _guard = 0
                while len(_ctx) < 40 and _guard < 5:
                    _guard += 1
                    _ns = _start
                    _prev_nl = eff_text.rfind("\n", 0, max(_start - 1, 0))
                    if _prev_nl > 0:
                        _pp = eff_text.rfind("\n", 0, _prev_nl)
                        _ns = _pp + 1 if _pp >= 0 else 0
                    _ne = _end
                    _next_nl = eff_text.find("\n", _end + 1) if _end + 1 < len(eff_text) else -1
                    if _next_nl < 0 and _end < len(eff_text):
                        _ne = len(eff_text)
                    elif _next_nl >= 0:
                        _nn = eff_text.find("\n", _next_nl + 1)
                        _ne = _nn if _nn >= 0 else len(eff_text)
                    if _ns >= _start and _ne <= _end:
                        break
                    _nc = eff_text[_ns:_ne].strip().replace("\n", " ")
                    if _nc == _ctx or not _nc:
                        break
                    _start, _end, _ctx = _ns, _ne, _nc
                if _ctx:
                    _ent["context"] = _ctx

        # LLM 清洗语境片段（并发）：截取的 context 可能跨句/含期刊元数据/换行残留，
        # 清洗只留含实体的核心语境（参考 concept-definition _clean_sents 并发模式）
        if isinstance(out, list):
            _to_clean = [(i, _e) for i, _e in enumerate(out)
                        if isinstance(_e, dict) and _e.get("context")]
            if _to_clean:
                _csysp = (
                    "你是文本清洗专家。输入一个命名实体及其当前语境片段（可能跨句、含换行/"
                    "期刊元数据残留如网络首发日期/引用格式/收稿日期/作者简介），输出干净的"
                    "语境片段——保留含该实体的核心句子（实体前后必要上下文，1-2 句），去掉："
                    "换行符、期刊元数据、与实体无关的相邻句、重复内容。若语境已是干净单句则"
                    "原样返回。\n只输出JSON："
                    '{"results":[{"cleaned":"干净语境片段"}]}')
                _cprompts = ["实体：%s（%s）\n语境：%s" % (
                    _e.get("text", ""), _e.get("type", ""), _e["context"])
                    for _, _e in _to_clean]
                _cbatch = self._glm_chat_batch(
                    _csysp, _cprompts, temperature=0.0, timeout=60.0,
                    max_tokens=500, max_workers=5)
                for (_i, _e), _c in zip(_to_clean, _cbatch):
                    if _c is None:
                        continue
                    _c = _c.get("data", _c) if isinstance(_c, dict) else _c
                    _rs = _c if isinstance(_c, list) else (
                        _c.get("results", []) if isinstance(_c, dict) else [])
                    if _rs and isinstance(_rs[0], dict):
                        _cl = (_rs[0].get("cleaned") or "").strip()
                        if _cl:
                            out[_i]["context"] = _cl

        # 科研/专业领域实体识别：LLM 为每个实体生成中英文标准词 + 映射置信度
        # （默认内置映射，不查用户词表/本体；用户选择内置方式即用 LLM 直接归一）。
        # 回填 standard_names/mapping_status/mapping_confidence，经
        # result_normalizer._entities 的 **item 透传至 *_mappings，供前端主表
        # "映射标准词"/"知识库ID"列与映射标签页展示。domain 额外标
        # standard_kb_id='内置知识库'（前端主表知识库ID列显示内置知识库+已映射）。
        # 用户标准词表优先（2026-09-05）：确定性查表归一可核查，查不到诚实标未映射；
        # 仅未上传词表时才走下方 LLM 生成标准词的兜底路径
        if code == 'ner_research' and _std_index and isinstance(out, list):
            self._apply_ner_standard_mapping(out, _std_index)
        # 查表未命中的实体仍走 LLM 生成标准词（确定性优先，LLM 兜底管覆盖）
        if code == 'ner_research' and _std_index and isinstance(out, list):
            _unmapped = [e for e in out if isinstance(e, dict)
                         and e.get('mapping_status') == '未映射'
                         and e.get('mapping_source') != 'llm_inline']
            if _unmapped:
                _ents_llm = _unmapped  # 仅内置资源时 LLM 兜底；用户上传词表则严格查表
                # 复用下方 LLM 生成逻辑，对未映射实体生成标准词并覆盖"未映射"状态
                _msysp = (
                    "你是科研术语标准化专家。输入一个从论文识别出的科研实体（可能是方法/"
                    "数据集/仪器/理论/主题）及其类型与语境，输出该实体的标准术语名：\n"
                    "- zh：学术规范的中文标准词\n- en：学术规范的英文标准词\n"
                    "- confidence：0-1\n只输出JSON："
                    '{"results":[{"zh":"中文标准词","en":"英文标准词","confidence":0.0}]}')
                _mprompts = ["实体：%s\n类型：%s\n语境：%s" % (
                    e.get("text", ""), e.get("type", ""), e.get("context", "")) for e in _ents_llm]
                _mbatch = self._glm_chat_batch(
                    _msysp, _mprompts, temperature=0.0, timeout=60.0, max_tokens=300, max_workers=5)
                for e, c in zip(_ents_llm, _mbatch):
                    if c is None:
                        continue
                    c = c.get("data", c) if isinstance(c, dict) else c
                    rs = c if isinstance(c, list) else (c.get("results", []) if isinstance(c, dict) else [])
                    if rs and isinstance(rs[0], dict):
                        zh = (rs[0].get("zh") or "").strip()
                        en = (rs[0].get("en") or "").strip()
                        try:
                            _mc = float(rs[0].get("confidence", 0.8))
                        except (TypeError, ValueError):
                            _mc = 0.8
                        if zh or en:
                            e["standard_names"] = {"zh": zh, "en": en}
                            e["mapping_status"] = "已映射"
                            # 置信度透传 LLM 自报原始值（2026-09-16 用户定调：原 0.75
                            # 地板导致全 0.75 太整齐）——与用户词表查表的 1.0 区分仍清晰
                            e["mapping_confidence"] = round(min(1.0, _mc), 3)
                            e.pop("mapping_source", None)  # LLM 生成的非用户词表
        if code in ('ner_research', 'ner_domain') and isinstance(out, list) and out \
                and not (code == 'ner_research' and _std_index):
            _ents = [e for e in out if isinstance(e, dict) and e.get('mapping_source') != 'llm_inline']
            if _ents:
                if code == 'ner_domain':
                    _msysp = (
                        "你是专业领域术语标准化专家。输入一个从专业领域文献识别出的实体"
                        "（医学/化工/物理等领域，类型如药物DRUG/疾病DISEASE/疗法TREATMENT/"
                        "化合物COMPOUND/反应REACTION/材料MATERIAL/理论THEORY/现象PHENOMENON/"
                        "规律LAW）及其领域、类型与语境，输出该实体的标准术语名：\n"
                        "- zh：学术规范的中文标准词（实体已是规范中文术语则原样给出；若为英文"
                        "缩写或非规范表达，给出规范中文译名）\n"
                        "- en：学术规范的英文标准词（实体为中文则给出规范英文术语；英文缩写则"
                        "给出全称）\n"
                        "- confidence：0-1，反映标准词与该实体的匹配确定性\n只输出JSON："
                        '{"results":[{"zh":"中文标准词","en":"英文标准词","confidence":0.0}]}')
                    _mprompts = ["实体：%s\n领域：%s\n类型：%s\n语境：%s" % (
                        e.get("text", ""), e.get("domain", ""),
                        e.get("type", ""), e.get("context", "")) for e in _ents]
                else:
                    _msysp = (
                        "你是科研术语标准化专家。输入一个从论文识别出的科研实体（可能是方法/"
                        "数据集/仪器/理论/主题）及其类型与语境，输出该实体的标准术语名：\n"
                        "- zh：学术规范的中文标准词（实体已是规范中文术语则原样给出；若为英文"
                        "缩写或非规范表达，给出规范中文译名）\n"
                        "- en：学术规范的英文标准词（实体为中文则给出规范英文术语；英文缩写则"
                        "给出全称）\n"
                        "- confidence：0-1，反映标准词与该实体的匹配确定性（实体明确即该标准词"
                        "则高，模糊/多义则低）\n只输出JSON："
                        '{"results":[{"zh":"中文标准词","en":"英文标准词","confidence":0.0}]}')
                    _mprompts = ["实体：%s\n类型：%s\n语境：%s" % (
                        e.get("text", ""), e.get("type", ""), e.get("context", ""))
                        for e in _ents]
                _mbatch = self._glm_chat_batch(
                    _msysp, _mprompts, temperature=0.0, timeout=60.0,
                    max_tokens=300, max_workers=5)
                for e, c in zip(_ents, _mbatch):
                    if c is None:
                        continue
                    c = c.get("data", c) if isinstance(c, dict) else c
                    rs = c if isinstance(c, list) else (
                        c.get("results", []) if isinstance(c, dict) else [])
                    if rs and isinstance(rs[0], dict):
                        zh = (rs[0].get("zh") or "").strip()
                        en = (rs[0].get("en") or "").strip()
                        try:
                            mc = float(rs[0].get("confidence", 0.0))
                        except (TypeError, ValueError):
                            mc = 0.0
                        if zh or en:
                            e["standard_names"] = {"zh": zh, "en": en}
                            e["mapping_status"] = "已映射"
                            # 置信度透传 LLM 自报原始值（2026-09-16 用户定调，同上）
                            e["mapping_confidence"] = round(min(1.0, mc), 3)
                # LLM 未给出标准词的实体标"未映射"（前端默认 fallback '已映射'
                # 会误显，故显式标注）；domain 知识库标识按资源来源：用户上传本体
                # 时类型体系就是用户的（标"用户本体体系"），否则内置（2026-09-16
                # 用户定调——传本体后仍标"内置知识库"有误导）
                for e in _ents:
                    if not e.get("standard_names"):
                        e["mapping_status"] = "未映射"
                    if code == 'ner_domain':
                        e["standard_kb_id"] = "用户本体体系" if _onto_extra else "内置知识库"

        result.success = True
        result.data = out
        result.evidence = data.get("evidence", []) if isinstance(data, dict) else []
        result.confidence = data.get("confidence") if isinstance(data, dict) else None
        result.raw = json.dumps({
            "n_chars_input": len(text),
            "truncated": truncated,
            "limit": NER_TEXT_LIMIT if truncated else None,
            "n_out": len(out) if isinstance(out, list) else 0,
        }, ensure_ascii=False)
        return result

    def _extract_definitions(self, text: str, rule=None) -> tuple:
        """规则抽取定义句（全文分句，排除参考文献章节）。高置信标志词→确定，线索词→不确定。"""
        import re as _re
        raw = rule.raw if rule else {}
        markers = raw.get("definition_markers", [])
        cues_str = raw.get("definition_cues", "")
        cues_re = _re.compile(cues_str) if cues_str else _re.compile("")
        exclude_strs = raw.get("exclude_patterns", [])
        exclude_res = [_re.compile(p, _re.IGNORECASE) for p in exclude_strs]

        # 截掉参考文献章节
        ref_re = _re.compile(r'\n#{0,3}\s*(参考文献|References|REFERENCES|致谢|Acknowledg|附录|Appendix)\s*\n')
        ref_match = ref_re.search(text)
        if ref_match:
            text = text[:ref_match.start()]

        text = _re.sub(r'<[^>]+>', '', text)
        for abbr in ['et al.', 'Fig.', 'Eq.', 'No.', 'e.g.', 'i.e.']:
            text = text.replace(abbr, abbr.replace('.', '§'))
        sentences = _re.split(r'(?<=[。！？])\s*|(?<=[.!?])(?!\d)\s*', text)
        sentences = [s.replace('§', '.').strip() for s in sentences if s.strip() and len(s.strip()) > 5]

        certain, uncertain = [], []
        for i, sent in enumerate(sentences):
            if any(er.search(sent) for er in exclude_res):
                continue
            matched_marker = None
            for marker in markers:
                if marker in sent:
                    matched_marker = marker
                    break
            if matched_marker:
                certain.append({
                    "sentence": sent,
                    "pattern": matched_marker,
                    "context_before": sentences[i - 1] if i > 0 else "",
                    "context_after": sentences[i + 1] if i + 1 < len(sentences) else "",
                })
            elif cues_re.search(sent):
                uncertain.append({
                    "sentence": sent,
                    "pattern": "",
                    "context_before": sentences[i - 1] if i > 0 else "",
                    "context_after": sentences[i + 1] if i + 1 < len(sentences) else "",
                })
        return certain, uncertain

    def _llm_confirm_definitions(self, uncertain: list) -> list:
        """LLM判定不确定句是否定义句（分批，每批10句）。宽松判定标准。"""
        if not uncertain:
            return []
        sysp = ("你是科技文献概念定义识别专家。判断给定句子是否为概念定义句。\n"
                "定义句的判定标准：\n"
                "- 句子在解释某个概念/术语\"是什么\"——算定义句\n"
                "- \"X是Y的Z之一\"\"X是Y的Z\"\"X是Y\"——只要X是名词性术语、句子在解释X的本质或类别，算定义句\n"
                "- 不要要求必须有\"是指\"\"被称为\"等标志词才算定义\n\n"
                "不是定义句的情况：\n"
                "- 描述重要性/作用/意义的（如\"X是...的重要环节\"\"X是...的关键步骤\"\"X是...的核心\"）→ 不是定义\n"
                "- 描述功能的（如\"X是...的工具\"但只是说X能干什么，不是定义X是什么）→ 不是定义\n"
                "- 陈述事实/结果的（如\"X是第一\"\"X是最好的\"）→ 不是定义\n"
                "- 关键区分：\"X是Y的一种方法\"（定义X的类别）是定义句；\"X是Y的重要环节\"（描述X的作用）不是定义句\n\n"
                "只输出JSON：{\"data\":{\"results\":[{\"sentence\":\"句子\",\"is_definition\":true,\"reason\":\"理由\"}]}}")
        confirmed = []
        batch_size = 10
        for start in range(0, len(uncertain), batch_size):
            batch = uncertain[start:start + batch_size]
            sent_list = "\n".join([f"[{i}] {u['sentence'][:120]}" for i, u in enumerate(batch)])
            try:
                d = self._glm.chat_json(sysp, f"判断以下句子是否定义句：\n{sent_list}",
                                        timeout=60.0, max_tokens=500, temperature=0.0)
                d = d.get("data", d) if isinstance(d, dict) else {}
                results = d.get("results", [])
                for r in results:
                    if r.get("is_definition"):
                        sent = r.get("sentence", "")
                        for u in batch:
                            if u["sentence"][:50] in sent or sent[:50] in u["sentence"]:
                                confirmed.append(u)
                                break
            except Exception:  # noqa: BLE001
                pass
        return confirmed

    def _llm_extract_concepts(self, definitions: list, rule, request) -> list:
        """LLM批量提取概念词（分批，每批10句）。"""
        sysp = self._system_prompt(rule, request)
        all_results = []
        batch_size = 10
        for start in range(0, len(definitions), batch_size):
            batch = definitions[start:start + batch_size]
            sent_list = "\n".join([f"[{i}] {d['sentence'][:150]}" for i, d in enumerate(batch)])
            try:
                d = self._glm.chat_json(sysp, f"定义句列表：\n{sent_list}",
                                        timeout=90.0, max_tokens=1000, temperature=0.0)
                d = d.get("data", d) if isinstance(d, dict) else {}
                results = d.get("results", [])
                if not results and isinstance(d, list):
                    results = d
                if len(results) < len(batch):
                    matched_idx = set()
                    for r in results:
                        rs = r.get("sentence", "")[:30]
                        for j, df in enumerate(batch):
                            if j not in matched_idx and (rs in df["sentence"] or df["sentence"][:30] in rs):
                                matched_idx.add(j)
                                break
                    for j, df in enumerate(batch):
                        if j not in matched_idx:
                            results.append({"sentence": df["sentence"], "concept": "", "confidence": 0.3})
                all_results.extend(results if results else batch)
            except Exception:  # noqa: BLE001
                all_results.extend(batch)
        return all_results if all_results else definitions
