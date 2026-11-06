"""后置规则引擎（运行时 + 训练共用，确定性、零 GLM 调用）。

LLM 输出 5 段划分后，本引擎做：
1. 确定性校验：标签合法、原文逐字未改、无遗漏/重复句子、语步顺序异常
2. 逐句 pattern 规则匹配 → 收集证据 → 对 5 语步分数做有限调整（受等级上限约束）
3. 冲突检测：规则建议 ≠ LLM 判定 且超过阈值 → 标记待二次审核

设计原则（rule.pdf 第11/15条）：
- 规则不直接覆盖 LLM，只调分数或触发复核
- 改标签需 ≥2 个独立证据维度共识
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from training.profile import get_profile
from training.rule_lib import Rule, RuleLib

# LLM 判定的基础分（代表 LLM 的选择，规则在其上做有限调整）
LLM_BASE_SCORE = 0.70
# 冲突触发：非 LLM 标签的备选 move 获得共识支持且加分超过此值 → 触发二次审核
# （规则不与 LLM 比拼绝对分数高低，而是看是否有共识证据反对 LLM 判定）
CONFLICT_MIN_SUPPORT = 0.12
# 共识要求：至少 N 个独立证据维度支持才视为强建议
CONSENSUS_MIN_DIMS = 2


def match_condition(cond: Dict[str, Any], sentence: str, feats: Dict[str, str],
                    ctx: Dict[str, Any]) -> bool:
    """判定单个条件是否满足。"""
    kind = cond.get("kind", "")
    if kind == "keyword":
        if "any_of" in cond:
            return any(w in sentence for w in (cond["any_of"] or []))
        if "all_of" in cond:
            return all(w in sentence for w in (cond["all_of"] or []))
        return False
    if kind == "regex":
        return re.search(cond.get("pattern", ""), sentence) is not None
    if kind == "feature":
        dim = cond.get("dim", "")
        val = feats.get(dim, "unknown")
        if "in" in cond:
            return val in (cond["in"] or [])
        if "not_in" in cond:
            return val not in (cond["not_in"] or [])
        return False
    if kind == "position":
        if "after_move" in cond:
            return ctx["seen_moves"].get(cond["after_move"], False)
        if "before_move" in cond:
            return not ctx["seen_moves"].get(cond["before_move"], False)
        if "rel_min" in cond or "rel_max" in cond:
            rel = ctx["rel_pos"]
            lo = cond.get("rel_min", 0.0)
            hi = cond.get("rel_max", 1.0)
            return lo <= rel <= hi
        return False
    return False


def rule_fires(rule: Rule, sentence: str, feats: Dict[str, str], ctx: Dict[str, Any]) -> bool:
    """规则命中：所有必要条件满足 且 无排除条件命中。"""
    if not all(match_condition(c, sentence, feats, ctx) for c in rule.necessary_conditions):
        return False
    if any(match_condition(c, sentence, feats, ctx) for c in rule.exclusion_conditions):
        return False
    return True


def matched_sources(rule: Rule, sentence: str, feats: Dict[str, str], ctx: Dict[str, Any]) -> set:
    """返回该规则命中的必要条件所提供的"证据来源"集合。

    用于共识判定（rule.pdf 第15条：改标签需≥2独立证据维度）：
    - feature 条件贡献其 dim（如 research_actor）
    - keyword/regex/position 条件贡献其 kind
    不同来源视为独立证据维度。
    """
    sources: set = set()
    for c in rule.necessary_conditions:
        if not match_condition(c, sentence, feats, ctx):
            continue
        if c.get("kind") == "feature":
            sources.add(c.get("dim", "feature"))
        else:
            sources.add(c.get("kind", ""))
    return sources


_SUMMARY_TAIL_RE = re.compile(
    r"(能力|性能|效果|精度|鲁棒性|抗扰|泛化)(能力)?(得到|获得)?(显著|明显|大幅|有效)?(提升|改善|提高|增强)"
)

# ── 分句级片段口径校准（2026-11-06，20 篇实测 LLM 判断层浮动收敛）──────────
# 与 result_normalizer._split_clauses 同口径的小句切分（层间不互相 import：
# training 不依赖 application，正则保持手工同步）。半角逗号按"后非数字"切
# （"实验表明,该方法"这类中文摘要的半角逗号无后随空白也要切；仅千分位
# "3,400" 不切）
_CLAUSE_BOUNDARY_RE = re.compile(r"[。！？；，：]|[,](?!\d)|[!?;:](?=\s)|\.(?=[\s\"'”’\)\]]|$)")

# 总结性收尾小句（比 _SUMMARY_TAIL_RE 宽：另覆盖"为…提供/具有…价值/验证了…
# 潜力/实现…匹配"等收尾形态——实测轨道交通"实现运力资源对突发需求的精准动态
# 匹配"、WGCNA"为DN的精准诊疗提供了新思路"等被判进结果尾部）
_FRAG_SUMMARY_RE = re.compile(
    r"为[^，。；]{0,28}(?:提供|奠定|支撑|参考|依据|途径|思路|基础|借鉴|保障)"
    r"|具有(?:较[好大]|重要|一定|很高?)?的?[^，。；]{0,12}(?:价值|意义|潜力|前景)"
    r"|验证了?[^，。；]{0,30}(?:能力|潜力|有效性|可行性)"
    r"|(?:能力|性能|效率|水平|鲁棒性|泛化[化性]?|抗扰[动性]?)(?:得到|获得)?(?:显著|明显|大幅|有效)?(?:提升|改善|提高|增强)"
    r"|(?:显著|有效)提升(?:了)?(?:模型|系统|框架)?的?(?:科学性|可解释性|稳定性|可靠性)"
    r"|实现了?[^，。；]{0,24}(?:匹配|协同|统一|一体化|均衡|闭环|落地|应用)"
)
# 目的段中的步骤小句（"首先，在模型中设计了…模块"——宣言归目的、步骤归方法）
_FRAG_STEP_RE = re.compile(r"^(?:首先|其次|再次|然后|接着|最后|进一步|同时)[，,]")
_FRAG_METHOD_VERB_RE = re.compile(r"设计|引入|构建|采用|建立|搭建|开发|研制|训练|提出|结合|利用|部署|融合|优化")
# 背景尾部宣言小句（"针对该问题，提出了一种…模型"——痛点归背景、宣言归目的；
# re.S：PDF 抽取文本小句内常带换行，`.` 需跨行匹配）
_FRAG_DECL_RE = re.compile(
    r"^(?:针对(?:该|这些|上述)?(?:问题|困境|挑战|不足|缺陷|需求)|为此|鉴于此|因此|基于此)[，,]"
    r".{0,80}?(?:提出|构建|设计|建立|开发|研制|形成)", re.S
)
# 第三方主语词（背景里描述他人工作时出现——宣言改判必须排除，防止把
# "针对该问题，Smith 等提出了 X"误搬进目的）
_FRAG_THIRD_PARTY_RE = re.compile(r"已有|传统|现有|先前|早期|近年|文献|学者|他人|et al")
# 宣言动词 + 成果名词（"提出了一种…模型/构建了…框架"——本文首次宣言形态）
_FRAG_DECL_VERB_RE = re.compile(
    r"(?:提出|构建|设计|建立|开发|研制|形成)了?[^，。；]{0,40}(?:模型|方法|框架|策略|系统|方案|机制|体系)")


def _split_span_clauses(text: str) -> List[str]:
    """按句读标点把 span 文本切成小句串（含边界标点），供片段级口径校准。"""
    if not text:
        return []
    out: List[str] = []
    start = 0
    for m in _CLAUSE_BOUNDARY_RE.finditer(text):
        end = m.end()
        while end < len(text) and text[end] in "”’\"')]}":
            end += 1
        seg = text[start:end]
        if seg.strip():
            out.append(seg)
        start = end
    if start < len(text) and text[start:].strip():
        out.append(text[start:])
    return out


def relocate_fragment_tails(spans: Dict[str, str], abstract: str) -> tuple:
    """分句级语步片段的确定性口径校准（与 relocate_summary_tail_sentences 同一
    需求评审口径的片段粒度版）。

    背景：片段保留路径（LLM spans ≥ 重组非空时优先）会跳过句级的
    relocate_summary_tail_sentences 等校准，实测 20 篇出现三类 LLM 判断层浮动：
    ① 结果段末总结性小句未拆出（"实现…精准动态匹配""为…提供了新思路"留在
       结果尾部、结论空置）；
    ② 背景尾部吞并宣言句（"针对该问题，提出了一种…模型"留在背景、目的错拿
       方法步骤）；
    ③ 目的段含"首先，设计了…模块"类步骤小句。
    三条规则（高置信确定性模式 + 空语步守卫，改判记录进 deterministic_issues）：
    A 结果尾部连续 ≤2 个无数字总结性小句 → 研究结论（仅结论为空时）；
    B 背景尾部宣言小句 → 研究目的（仅目的为空且无第三方主语时）；
    C 目的中步骤小句 → 研究方法（按原文顺序归并）。
    返回 (调整后 spans, 改判说明列表)；非中文摘要 profile（无此三语步）原样返回。
    """
    p = get_profile()
    need = ("研究背景", "研究目的", "研究方法", "研究结果", "研究结论")
    if not all(m in p.moves for m in need):
        return spans, []
    notes: List[str] = []
    flat = re.sub(r"\s+", "", abstract)

    def _pos(clause: str) -> int:
        return flat.find(re.sub(r"\s+", "", clause))

    def _merge_by_doc_order(dst: List[str], moved: List[str]) -> List[str]:
        # 搬迁小句按原文位置插入目标段（位置取不到的排尾部），保持各段 text
        # 是原文小句的按序拼接（跨段非连续时由归一化层多段拼接兜底定位）
        allc = dst + moved
        allc.sort(key=lambda c: _pos(c) if _pos(c) >= 0 else 10 ** 9)
        return allc

    # C: 目的段中的步骤小句 → 研究方法。步骤标记"首先，"后的逗号即切分点，
    # 标记小句与方法动词分属相邻小句——标记小句（≤4 字纯标记）与其后小句
    # 合并成一个判定单元，命中则两小句一并搬迁（按索引处理，避免同名小句
    # 误删）
    purpose_cl = _split_span_clauses(spans.get("研究目的") or "")
    step_idx = set()
    for i, c in enumerate(purpose_cl):
        cs = c.strip()
        if not _FRAG_STEP_RE.match(cs):
            continue
        if _FRAG_METHOD_VERB_RE.search(cs):
            step_idx.add(i)
        elif (len(re.sub(r"[，,。\s]", "", cs)) <= 4 and i + 1 < len(purpose_cl)
              and _FRAG_METHOD_VERB_RE.search(purpose_cl[i + 1])):
            step_idx.update((i, i + 1))
    if step_idx and (spans.get("研究方法") or "").strip():
        moved = [c for i, c in enumerate(purpose_cl) if i in step_idx]
        spans["研究目的"] = "".join(c for i, c in enumerate(purpose_cl) if i not in step_idx)
        spans["研究方法"] = "".join(_merge_by_doc_order(
            _split_span_clauses(spans["研究方法"]), moved))
        notes.append(f"目的段 {len(moved)} 个步骤小句按口径改判研究方法")

    # B: 背景尾部宣言小句 → 研究目的（目的为空时）。"针对该问题，提出了X模型"
    # 会被逗号切成"针对该问题，"+"提出了…模型。"两小句——尾部小句命中宣言
    # 模式、其前是 ≤8 字的 针对/为此/鉴于此 类标记小句时，两小句一并搬迁
    bg_cl = _split_span_clauses(spans.get("研究背景") or "")
    if bg_cl and not (spans.get("研究目的") or "").strip():
        tail = bg_cl[-1].strip()
        decl_hit = bool(_FRAG_DECL_VERB_RE.search(tail)) and not _FRAG_THIRD_PARTY_RE.search(tail)
        take = 1
        if decl_hit and len(bg_cl) >= 2:
            prev = bg_cl[-2].strip()
            if (len(re.sub(r"[，,。\s]", "", prev)) <= 8
                    and re.match(r"^(?:针对|为此|鉴于此|因此|基于此)", prev)
                    and not _FRAG_THIRD_PARTY_RE.search(prev)):
                take = 2
        if decl_hit:
            moved_bg = bg_cl[-take:]
            spans["研究背景"] = "".join(bg_cl[:-take])
            spans["研究目的"] = "".join(moved_bg)
            notes.append("背景段尾部宣言小句按口径改判研究目的")

    # A: 结果尾部总结性小句 → 研究结论（结论为空时）。守卫：候选小句不得以
    # 结果引导词开头（"实验表明/结果表明"类是结果本体）、不含数字（带数据的是
    # 结果不是结论）。结果段单小句且整句是总结形态时允许整段搬迁（[斜拉索]
    # 实测：结果段仅"验证了…潜力。"一句，结论空置）
    res_cl = _split_span_clauses(spans.get("研究结果") or "")
    if res_cl and not (spans.get("研究结论") or "").strip():
        _result_lead_re = re.compile(r"^(?:实验|相关)?(?:表明|显示|发现|结果|测试|分析)")
        moved: List[str] = []
        for c in reversed(res_cl[-2:]):
            cs = c.strip()
            core_len = len(re.sub(r"[，。；、,.;:\s]", "", cs))
            if (core_len >= 6 and not re.search(r"\d", c)
                    and not _result_lead_re.match(cs)
                    and _FRAG_SUMMARY_RE.search(cs)):
                moved.insert(0, c)
        if moved:
            spans["研究结果"] = "".join(c for c in res_cl if c not in moved)
            spans["研究结论"] = "".join(moved)
            notes.append(f"结果段末 {len(moved)} 个总结性小句按口径改判研究结论")

    return spans, notes


def relocate_summary_tail_sentences(sentences: List[str], final_labels: List[str]) -> int:
    """确定性口径校准：结果段末尾连续的总结性句子改判研究结论（需求评审口径）。

    "结果表明：数据A%；即使引入误差，数据B%，系统能力得到显著提升。"这类复合句
    分号被分句器切开后，尾子句（数据+总结性评价）的落点是总体性评价——按口径归
    研究结论。LLM 与冲突审核对该落点判定不稳定，此处按确定规则校准：
    仅从句子序列末尾向前扫描"研究结果"标签的连续块，命中总结性模式的句子改判
    "研究结论"（中间命中的结果句不动，避免误伤）；英文 profile 无此二语步则跳过。
    返回改判句数。
    """
    p = get_profile()
    if "研究结论" not in p.moves or "研究结果" not in p.moves:
        return 0
    changed = 0
    for i in range(len(sentences) - 1, -1, -1):
        if final_labels[i] == "研究结果":
            if _SUMMARY_TAIL_RE.search(sentences[i]):
                final_labels[i] = "研究结论"
                changed += 1
            else:
                break  # 尾部连续结果块结束（纯数据句是边界）
        elif final_labels[i] == "研究结论":
            continue  # 已是结论的尾句跳过，继续向前找结果句块
        else:
            break
    return changed


def _deterministic_checks(abstract: str, sentences: List[str], spans: Dict[str, str]) -> List[str]:
    """确定性校验，返回发现的问题清单（可自动修正的在此处修正并记录）。"""
    p = get_profile()
    moves = p.moves
    issues: List[str] = []
    # 1. 标签合法
    bad = [k for k in spans if k not in moves]
    if bad:
        issues.append(f"非法语步键: {bad}")
    # 2. 原文逐字未改（span 应为 abstract 子串，忽略空白）
    abs_norm = re.sub(r"\s+", "", abstract)
    for m, sp in spans.items():
        if sp and re.sub(r"\s+", "", sp) not in abs_norm:
            issues.append(f"{m} 段非原文逐字摘录（可能被改写）")
    # 3. 遗漏句子：所有句应被某段覆盖
    covered = [False] * len(sentences)
    for i, s in enumerate(sentences):
        s_norm = s.strip()
        for sp in spans.values():
            if sp and s_norm and s_norm in sp:
                covered[i] = True
                break
    missing = [sentences[i] for i, c in enumerate(covered) if not c]
    if missing:
        issues.append(f"遗漏句子({len(missing)}句): {missing[:2]}")
    # 4. 重复句子：一句出现在多段
    for i, s in enumerate(sentences):
        s_norm = s.strip()
        cnt = sum(1 for sp in spans.values() if sp and s_norm and s_norm in sp)
        if cnt > 1:
            issues.append(f"句子重复出现在多段: {s_norm[:20]}")
    # 5. 语步顺序：结论不应在结果之前出现（moves[-1]=结论, moves[-2]=结果）
    order_idx: Dict[str, int] = {}
    for i, s in enumerate(sentences):
        s_norm = s.strip()
        for m, sp in spans.items():
            if sp and s_norm and s_norm in sp and m not in order_idx:
                order_idx[m] = i
    conc, res = moves[-1], moves[-2]
    if conc in order_idx and res in order_idx and order_idx[conc] < order_idx[res]:
        issues.append(f"语步顺序异常：{conc}出现在{res}之前")
    return issues


def verify_and_adjust(
    abstract: str,
    llm_output: Dict[str, str],
    rule_lib: RuleLib,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """主入口：校验 + 调分 + 冲突检测。

    返回:
      final_spans: 确定性修正后的 spans（不含规则覆盖；规则覆盖经冲突审核后由调用方回填）
      sentences: 逐句分析 [{text, llm_label, rule_suggestion, scores, evidence, conflict, consensus, adjustments}]
      conflicts: 待二次审核的句子索引列表
      deterministic_issues: 确定性校验发现的问题
    """
    p = get_profile()
    moves = p.moves
    spans = {m: (llm_output.get(m) or "") for m in moves}
    sentences = p.seg.segment(abstract)
    n = len(sentences)
    llm_labels = p.seg.assign_sentences_to_spans(sentences, spans)
    feats_list = p.features.extract_for_sentences(sentences)
    rules = rule_lib.engine_rules(domain)

    seen_moves: Dict[str, bool] = {}
    sent_analysis: List[Dict[str, Any]] = []
    conflicts: List[int] = []

    for i, (sent, feats, llm_lab) in enumerate(zip(sentences, feats_list, llm_labels)):
        rel_pos = (i / n) if n else 0.0
        ctx = {"seen_moves": seen_moves, "rel_pos": rel_pos, "idx": i, "n": n}

        # 初始分数：LLM 判定给基础分
        scores: Dict[str, float] = {m: 0.0 for m in moves}
        if llm_lab in scores:
            scores[llm_lab] = LLM_BASE_SCORE

        evidence: List[Dict[str, Any]] = []
        support_sources: Dict[str, set] = {m: set() for m in moves}
        penalize_sources: Dict[str, set] = {m: set() for m in moves}
        adjustments: List[Dict[str, Any]] = []

        for rule in rules:
            if not rule_fires(rule, sent, feats, ctx):
                continue
            tm = rule.target_move
            w = rule.effective_weight
            src = matched_sources(rule, sent, feats, ctx)
            if rule.action == "+score" and tm in scores:
                scores[tm] += w
                support_sources[tm].update(src)
                adjustments.append({"rule": rule.id, "action": "+score", "move": tm, "delta": round(w, 3)})
            elif rule.action == "-score" and tm in scores:
                scores[tm] -= w
                penalize_sources[tm].update(src)
                adjustments.append({"rule": rule.id, "action": "-score", "move": tm, "delta": round(-w, 3)})
            elif rule.action == "review":
                adjustments.append({"rule": rule.id, "action": "review", "move": tm})
            evidence.append({"rule": rule.id, "target": tm, "sources": sorted(src),
                             "level": rule.level, "description": rule.description})

        rule_suggestion = max(scores, key=scores.get)
        rule_score = scores[rule_suggestion]
        # 备选 move = 除 LLM 标签外得分最高的 move
        alt_candidates = {m: v for m, v in scores.items() if m != llm_lab}
        alt_move = max(alt_candidates, key=alt_candidates.get) if alt_candidates else rule_suggestion
        alt_support = alt_candidates.get(alt_move, 0.0)
        alt_consensus = len(support_sources.get(alt_move, set())) >= CONSENSUS_MIN_DIMS
        # 规则对 LLM 标签的净惩罚（-score 之和）及其共识
        llm_penalty = sum(-a["delta"] for a in adjustments
                          if a.get("action") == "-score" and a.get("move") == llm_lab)
        llm_pen_consensus = len(penalize_sources.get(llm_lab, set())) >= CONSENSUS_MIN_DIMS
        # 冲突 = 有共识证据支持别的 move，或共识证据惩罚 LLM 的 move
        conflict = (alt_consensus and alt_move != llm_lab and alt_support >= CONFLICT_MIN_SUPPORT) \
            or (llm_pen_consensus and llm_penalty >= CONFLICT_MIN_SUPPORT)
        consensus = alt_consensus or llm_pen_consensus
        # 冲突时，规则建议指向共识支持的备选 move（供二次审核参考）
        if conflict:
            rule_suggestion = alt_move

        sent_analysis.append({
            "text": sent,
            "llm_label": llm_lab,
            "rule_suggestion": rule_suggestion,
            "scores": {m: round(v, 3) for m, v in scores.items()},
            "evidence": evidence,
            "adjustments": adjustments,
            "consensus": consensus,
            "conflict": conflict,
        })
        if conflict:
            conflicts.append(i)

        if llm_lab:
            seen_moves[llm_lab] = True

    issues = _deterministic_checks(abstract, sentences, spans)

    return {
        "final_spans": spans,            # 确定性修正后（暂未做规则覆盖）
        "sentences": sent_analysis,
        "conflicts": conflicts,
        "deterministic_issues": issues,
    }


def reassemble_spans(abstract: str, sentence_labels: List[str]) -> Dict[str, str]:
    """按逐句标签重新拼装 spans（冲突审核回填后用）。保持句子原序。"""
    p = get_profile()
    sentences = p.seg.segment(abstract)
    buckets: Dict[str, List[str]] = {m: [] for m in p.moves}
    for s, lab in zip(sentences, sentence_labels):
        if lab in buckets:
            buckets[lab].append(s)
    return {m: "".join(buckets[m]) for m in p.moves}


if __name__ == "__main__":
    from pathlib import Path
    lib = RuleLib.load(Path("rules/move_recognition/mr_zh_abstract.yaml"))
    abstract = ("已有研究表明，图神经网络能够处理非欧氏数据。"
                "针对泛化能力不足的问题，本文提出一种多尺度网络。"
                "实验结果显示，该模型使F1值提高了3.2%。"
                "据此，本文建议在更多任务中验证该方法。")
    llm_out = {"研究背景": "已有研究表明，图神经网络能够处理非欧氏数据。",
               "研究目的": "针对泛化能力不足的问题，",
               "研究方法": "本文提出一种多尺度网络。",
               "研究结果": "实验结果显示，该模型使F1值提高了3.2%。",
               "研究结论": "据此，本文建议在更多任务中验证该方法。"}
    res = verify_and_adjust(abstract, llm_out, lib)
    print("确定性问题:", res["deterministic_issues"])
    print("冲突句:", res["conflicts"])
    for sa in res["sentences"]:
        flag = " ⚠冲突" if sa["conflict"] else ""
        print(f"  [{sa['llm_label']}→{sa['rule_suggestion']}{flag}] {sa['text'][:30]}")
        if sa["adjustments"]:
            print("      调整:", sa["adjustments"])
