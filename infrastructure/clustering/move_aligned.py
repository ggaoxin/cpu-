"""v3 语步对齐双轴聚类引擎（替换原混合向量+锚点体系，2026-09-06 定稿）。

设计（需求评审定稿）：
  文献 → 语步提取（全文切块并发：研究方法句 / 研究背景+研究目的句）
  → 技术路线轴 = 按方法分组（综述粒度：簇内文献可用同类方法合并成一篇综述）
  → 应用场景轴 = 按场景分组（背景+目的+题名；簇内文献围绕同一问题）
  → LLM 综述粒度分组（≤20 直接；>20 分批分组后跨批合并），失败退向量聚类

验证记录（scripts/ 下实验）：
  合成集双轴 ARI=1.0（YOLO×5 应用各异聚齐 / 场景×5 方法各异聚齐）
  papers20 英文集：双轴分组语义正确，簇可直接产出聚焦综述
  ch_papers 中文集：无主题群时正确不硬聚
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

CHUNK_SIZE = 6000
CHUNK_OVERLAP = 200
MAX_WORKERS = 6
BATCH_SIZE = 20

MOVE_KEYS = ("研究方法", "研究背景", "研究目的", "研究结果")

EXTRACT_SYSTEM = (
    "你是科技文献语步提取专家。从给定文献片段中逐字摘录四类句子（保留原文，中英文均按原语言）：\n"
    "- 研究方法：采用的数据、模型、算法、实验手段、技术路线\n"
    "- 研究背景：领域现状、问题由来、前人工作不足\n"
    "- 研究目的：本文要解决什么问题、达成什么目标\n"
    "- 研究结果：实验发现、性能表现、主要结论与研究进展\n"
    "只摘录句子原文，不得改写；片段中没有的类别输出空数组。只输出JSON："
    '{"研究方法":["句子",...],"研究背景":["句子",...],"研究目的":["句子",...],"研究结果":["句子",...]}'
)

AXIS_PROMPTS = {
    "technical": {
        "criterion": "所用的具体技术方法（方法、模型、算法层面）",
        "example": "如'扩散模型图像生成''图神经网络检测''WGCNA基因筛选'",
    },
    "application": {
        "criterion": "所研究的应用场景/研究对象（问题与领域层面）",
        "example": "如'社交媒体机器人检测''糖尿病诊疗''混凝土结构耐久'",
    },
}

GROUP_SYSTEM_TEMPLATE = (
    "你是科技文献聚类专家。下面是每篇文献的题名与{which}描述片段，把文献按{criterion}分组。\n"
    "判断标准（综述粒度）：同一簇的文献必须能直接合并为一篇聚焦的主题综述"
    "（{example}）。研究同一主题但方法/表述不同的文献必须聚在一起；"
    "讲不同事情的文献绝不能混入同簇，宁可各自单列。孤立文献可单列。\n"
    '只输出JSON：{{"groups":[{{"name":"簇名（10字内）","docs":[文献编号,...],"keywords":["关键词1","关键词2","关键词3"]}}]}}'
    "\nkeywords 要求：3-5 个该簇文献的专业术语（至少 2 个），优先级：① 论文命名的方法/模型名"
    "（如 TTSR、Self-Harmony、Memex、FLB）；② 核心技术术语（如 reinforcement learning、"
    "pseudo-label method）；③ 研究对象。逐字摘录原文，不得翻译、缩写、概括或造新词；"
    "禁止用描述性句子片段（如 'Student and a Teacher at test time' 是机制描述不是术语，"
    "应改为方法名 TTSR）。"
    "簇名 = 该簇最核心的技术术语（方法名或技术名，不是句子片段）。"
    "簇名禁止占位词（'簇1''孤立文献1''未分组''其他'）——单列簇也必须用该文献的"
    "核心方法名或场景名命名（如 'TTSR''基准评测'）。"
    "每个 keyword 完整保留原文（含空格），不截断。"
)


def chunk_text(text: str, size: int = CHUNK_SIZE) -> List[str]:
    text = (text or "").strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, step, i = [], size - CHUNK_OVERLAP, 0
    while i < len(text):
        chunks.append(text[i:i + size])
        i += step
    return chunks


def _clean_text(value: Any) -> str:
    """LLM/PDF 文本清洗：去 HTML 实体（GLM 偶发把撇号转义成 &#39; 等）。"""
    import html
    return html.unescape(str(value or "")).strip()


def _extract_chunk(glm, chunk: str) -> Dict[str, List[str]]:
    try:
        raw = glm.chat_json(EXTRACT_SYSTEM, f"文献片段：\n{chunk}",
                            temperature=0.0, timeout=120.0, max_tokens=3000)
    except Exception:  # noqa: BLE001
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    return {k: [_clean_text(v) for v in (raw.get(k) or []) if _clean_text(v)]
            for k in MOVE_KEYS} if isinstance(raw, dict) else {}


def _display_title(paper: Dict[str, Any]) -> str:
    """题名：优先真实题名；文件名式（DOC001/1.pdf）无语义时从全文首行提取。"""
    title = str(paper.get("title") or "").strip()
    if title and not re.fullmatch(r"(DOC\d+|\d+|[\w-]+\.pdf?)", title, re.IGNORECASE):
        return title[:50]
    full_text = str(paper.get("full_text") or "")
    for ln in full_text.split("\n")[:8]:
        ln = ln.strip().lstrip("# ").strip()
        if 8 <= len(ln) <= 80 and not ln.startswith(("Abstract", "摘要", "http", "DOI", "{")):
            return ln[:50]
    return title or str(paper.get("document_id") or "")


MOVE_EXTRACT_TEXT_LIMIT = 10000  # 语步提取文本上限：有摘要从摘要起，无摘要从正文起，一律前 10k（不假设文档类型）

def extract_moves(paper: Dict[str, Any], glm) -> Dict[str, List[str]]:
    """单篇语步提取：优先全文前段（切块并发），退回题名+摘要。

    全文截断到 20k 字（2026-09-08）：聚类只需研究方法/背景/目的句——它们集中在
    摘要和引言/方法节；全文 100k 字×6 篇 = 116 次 GLM 块调用是 97s 的根因，
    截断后 3-4 块/篇 ≈ 25 次调用，信息不丢（摘要本身已含核心语步句）。
    返回 {研究方法: [...], 研究背景: [...], 研究目的: [...]}（去重截断）。
    """
    full_text = str(paper.get("full_text") or "").strip()
    abstract = str(paper.get("abstract") or "").strip()
    title = str(paper.get("title") or "").strip()
    source = full_text if len(full_text) > len(abstract) else " ".join(x for x in (title, abstract) if x)
    if len(source) > MOVE_EXTRACT_TEXT_LIMIT:
        source = source[:MOVE_EXTRACT_TEXT_LIMIT]
    chunks = chunk_text(source)
    if not chunks:
        return {k: [] for k in MOVE_KEYS}
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(chunks))) as pool:
        parts = list(pool.map(lambda c: _extract_chunk(glm, c), chunks))
    merged = {k: [] for k in MOVE_KEYS}
    for part in parts:
        for k in MOVE_KEYS:
            merged[k].extend(part.get(k) or [])
    for k in MOVE_KEYS:
        merged[k] = list(dict.fromkeys(merged[k]))[:15]
    # 场景信号保底：背景/目的全空时用题名（题目直接写明场景——实测修复场景轴 ARI 0.669→1.0）
    if not any(merged[k] for k in ("研究背景", "研究目的")) and title:
        merged["研究背景"] = [title]
    return merged


def extract_moves_batch(papers: List[Dict[str, Any]], glm) -> List[Dict[str, List[str]]]:
    """逐篇语步提取（并发 6，10k 截断）。

    2024-09-08：截断到前 10k 字（有摘要从摘要起、无摘要从正文起，不假设文档类型）
    ——每篇 2 块，6 篇 12 次 GLM 并发 6 路 ≈ 15s。批量提取实测 LLM 无法可靠
    分文档返回（143s 回归），回退到逐篇并发。
    """
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(6, len(papers))) as pool:
        return list(pool.map(lambda p: extract_moves(p, glm), papers))

def _doc_index_map(papers: List[Dict[str, Any]]) -> Dict[str, int]:
    """LLM 返回 docs 编号时的容错映射：数字串(1-based)、document_id(DOC001)、大写 ID 都认。

    GLM 偶发把 "docs":[1,2] 写成 ["DOC001","DOC002"]——int() 直接失败会把整组
    文献静默丢光（分组退化为全兜底占位名），这里统一先查映射再退数字解析。"""
    m: Dict[str, int] = {}
    for i, p in enumerate(papers):
        did = str(p.get("document_id") or "").strip()
        if did:
            m[did] = i
            m[did.upper()] = i
        m.setdefault(str(i + 1), i)
    return m


def _parse_doc_ref(x: Any, papers_len: int, index_map: Dict[str, int]) -> Optional[int]:
    """解析 LLM 输出里的文献引用（编号/ID 字符串/带数字后缀）→ 0-based 下标。"""
    s = str(x).strip().strip("[]()").strip()
    if s in index_map:
        idx = index_map[s]
    else:
        try:
            idx = int(s) - 1
        except (TypeError, ValueError):
            tail = re.search(r"(\d+)\s*$", s)
            if not tail:
                return None
            idx = int(tail.group(1)) - 1
    return idx if 0 <= idx < papers_len else None


def _group_once(glm, papers: List[Dict[str, Any]], moves: List[Dict[str, List[str]]], axis: str,
                target_k: int | None = None) -> List[Dict[str, Any]]:
    """一次 LLM 分组（≤BATCH_SIZE 篇）。target_k 非空时提示 LLM 目标簇数（软约束）。
    返回 [{name, indices}]；校验失败返回 []。"""
    which = "研究方法" if axis == "technical" else "研究背景+研究目的"
    spec = AXIS_PROMPTS[axis]
    lines = []
    for i, (paper, mv) in enumerate(zip(papers, moves)):
        title = str(paper.get("title") or "")[:40]
        if axis == "technical":
            sents = mv["研究方法"][:3]
        else:
            sents = (mv["研究背景"] + mv["研究目的"])[:3]
        lines.append(f"[{i + 1}]「{title}」{'；'.join(s[:120] for s in sents[:2])}")
    system = GROUP_SYSTEM_TEMPLATE.format(which=which, criterion=spec["criterion"], example=spec["example"])
    if target_k:
        system += f"\n用户要求类簇数量约为 {target_k} 个（允许±1 浮动），请按此粒度分组。"""
    try:
        raw = glm.chat_json(system, "\n".join(lines), temperature=0.0, timeout=180.0, max_tokens=3000)
    except Exception:  # noqa: BLE001
        return []
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    groups: List[Dict[str, Any]] = []
    seen = set()
    index_map = _doc_index_map(papers)
    for g in ((raw or {}).get("groups") if isinstance(raw, dict) else []) or []:
        if not isinstance(g, dict):
            continue
        name = _clean_text(g.get("name"))[:40]
        indices = []
        for x in (g.get("docs") or []):
            idx = _parse_doc_ref(x, len(papers), index_map)
            if idx is not None and idx not in seen and name:
                seen.add(idx)
                indices.append(idx)
        keywords = [_clean_text(k)[:60] for k in (g.get("keywords") or []) if _clean_text(k)][:5]
        if indices:
            groups.append({"name": name, "indices": indices, "keywords": keywords})
    if len(seen) != len(papers) or not groups:
        return []
    return groups


def _merge_batches(glm, batch_groups: List[List[Dict[str, Any]]], batch_size: int) -> List[Dict[str, Any]]:
    """跨批合并：把各批的簇（带全局索引）按簇名语义合并（一次 LLM）。"""
    flat = []
    for bi, groups in enumerate(batch_groups):
        for g in groups:
            flat.append({
                "name": g["name"],
                "indices": [i + bi * batch_size for i in g["indices"]],
            })
    if len(batch_groups) <= 1:
        return flat
    lines = [f"簇「{g['name']}」: {len(g['indices'])}篇 {g['indices'][:8]}..." for g in flat]
    system = (
        "下面是对多批文献分别聚类得到的簇（docs 为全局文献编号）。请把研究同一主题"
        "的簇合并（合并后 docs 取并集，簇名保留最贴切的）；不同主题的簇保持独立。"
        '只输出JSON：{"merged":[{"name":"簇名","docs":[全局编号,...]},...]}，'
        "必须覆盖全部文献编号、不重叠。"
    )
    try:
        raw = glm.chat_json(system, "\n".join(lines), temperature=0.0, timeout=180.0, max_tokens=3000)
    except Exception:  # noqa: BLE001
        return flat
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    merged, seen = [], set()
    kw_by_name = {g["name"]: g.get("keywords") or [] for g in flat}
    for g in ((raw or {}).get("merged") if isinstance(raw, dict) else []) or []:
        if not isinstance(g, dict):
            continue
        name = _clean_text(g.get("name"))[:40]
        indices = []
        for x in (g.get("docs") or []):
            # 此处 docs 是 0-based 全局编号（flat 构造时 i + bi*batch_size）
            try:
                idx = int(str(x).strip())
            except (TypeError, ValueError):
                tail = re.search(r"(\d+)\s*$", str(x))
                idx = int(tail.group(1)) if tail else None
            if idx is not None and idx >= 0 and idx not in seen:
                seen.add(idx)
                indices.append(idx)
        raw_kws = [k for k in (g.get("keywords") or kw_by_name.get(name, [])) if _clean_text(k)]
        if indices and name:
            merged.append({"name": name, "indices": sorted(indices), "keywords": raw_kws})
    total = sum(len(g["indices"]) for g in flat)
    return merged if merged and len(seen) == total else flat




ANCHOR_ASSIGN_SYSTEM = (
    "你是科技文献归类专家。下面是用户提供的类目档案（每个类目名 + 该类目训练样本"
    "的{which}代表句）和待聚类文献的{which}描述。把每篇文献归入最贴切的一个类目"
    "（只填类目编号数字）；与所有类目都不贴切的文献填 0（后续自由分组）。"
    '只输出JSON：{{"assign":[{{"id":文献编号,"cat":类目序号}},...]}}，每篇一条。'
)


def build_anchor_profiles(anchor_docs: List[Dict[str, Any]], glm) -> Dict[str, Dict[str, List[str]]]:
    """用户训练样本 → 类目档案：每类目的语步代表句。

    anchor_docs: [{title/abstract/text, category|label}]（已归一化的资源行）。
    对每篇样本提取语步句，按类目聚合：{类目名: {methods:[...], scenes:[...]}}。
    """
    profiles: Dict[str, Dict[str, List[str]]] = {}
    papers = []
    labels = []
    for d in anchor_docs:
        # 类目名优先语义名（category/technical_cluster_name），编号 ID 兜底：
        # 官方资源包结构 technical_cluster_id=USER-CAT-A + technical_cluster_name=
        # 数据聚类方法——用 ID 当类目名会让 LLM 只能靠方法句猜语义
        cat = _clean_text(d.get("category") or d.get("category_id") or d.get("label")
                          or d.get("technical_cluster_name") or d.get("application_cluster_name")
                          or d.get("cluster_name") or d.get("technical_cluster_id"))
        if not cat:
            continue
        papers.append({
            "title": _clean_text(d.get("title") or d.get("ch_name")),
            "abstract": _clean_text(d.get("abstract") or d.get("ch_abstract") or d.get("text")),
            "full_text": _clean_text(d.get("text") or d.get("full_text")),
        })
        labels.append(cat)
    if not papers:
        return profiles
    moves = extract_moves_batch(papers, glm)
    for cat, mv, paper in zip(labels, moves, papers):
        prof = profiles.setdefault(cat, {"methods": [], "scenes": [], "titles": []})
        prof["methods"].extend(mv["研究方法"][:6])
        prof["scenes"].extend((mv["研究背景"] + mv["研究目的"])[:6])
        if str(paper.get("title") or "").strip():
            prof["titles"].append(str(paper["title"]).strip()[:40])
    return profiles


def _assign_to_anchor_categories(glm, papers, moves, profiles, axis) -> List[str]:
    """LLM 把每篇文献归入用户类目或 0（不贴切）。返回每篇的类目名（""=未归入）。"""
    which = "研究方法" if axis == "technical" else "研究背景+研究目的"
    cats = list(profiles.keys())
    lines = []
    for ci, (cat, prof) in enumerate(profiles.items(), start=1):
        rep = prof["methods"][:2] if axis == "technical" else prof["scenes"][:2]
        sample = " / ".join(dict.fromkeys(prof.get("titles") or []))
        head = f"类目{ci}「{cat}」" + (f"（样本：{sample[:80]}）" if sample else "")
        lines.append(f"{head}: {'；'.join(s[:120] for s in rep[:2])}")
    doc_lines = []
    for i, (paper, mv) in enumerate(zip(papers, moves)):
        title = _display_title(paper)
        sents = mv["研究方法"][:2] if axis == "technical" else (mv["研究背景"] + mv["研究目的"])[:2]
        doc_lines.append(f"[{i + 1}]「{title}」{'；'.join(s[:60] for s in sents[:2])}")
    try:
        raw = glm.chat_json(
            ANCHOR_ASSIGN_SYSTEM.format(which=which),
            "类目档案：\n" + "\n".join(lines) + "\n\n待归类文献：\n" + "\n".join(doc_lines),
            temperature=0.0, timeout=180.0, max_tokens=3000)
    except Exception:  # noqa: BLE001
        return ["" for _ in papers]
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        raw = raw["data"]
    label_of = {}
    index_map = _doc_index_map(papers)
    for item in ((raw or {}).get("assign") if isinstance(raw, dict) else []) or []:
        if isinstance(item, dict) and item.get("id") is not None:
            try:
                ci = int(item.get("cat"))
            except (TypeError, ValueError):
                continue
            # id 可能是 1-based 数字也可能是 "DOC001" 式 document_id（GLM 格式漂移）
            idx = _parse_doc_ref(item["id"], len(papers), index_map)
            if idx is not None:
                label_of[idx] = cats[ci - 1] if 1 <= ci <= len(cats) else ""
    return [label_of.get(i, "") for i in range(len(papers))]


def anchor_guided_groups(papers, moves, anchor_docs, axis, glm) -> List[Dict[str, Any]]:
    """锚点引导分组：用户类目为种子，未归入的文献自由分组。

    返回 [{name, indices}]（与 _group_once 同构）；档案为空返回 []（走自由分组）。
    """
    profiles = build_anchor_profiles(anchor_docs, glm)
    if not profiles:
        import logging
        logging.getLogger(__name__).info("锚点引导回落自由分组：类目档案为空（语步提取未产出，LLM 波动）")
        return []
    labels = _assign_to_anchor_categories(glm, papers, moves, profiles, axis)
    groups: List[Dict[str, Any]] = []
    assigned = [i for i, x in enumerate(labels) if x]
    for cat in profiles:
        indices = [i for i in assigned if labels[i] == cat]
        if indices:
            groups.append({"name": cat, "indices": indices, "keywords": [cat]})
    leftovers = [i for i, x in enumerate(labels) if not x]
    if leftovers:
        sub_papers = [papers[i] for i in leftovers]
        sub_moves = [moves[i] for i in leftovers]
        free = (_group_once(glm, sub_papers, sub_moves, axis) if len(leftovers) > 1
                else ([{"name": str(sub_papers[0].get("title") or "其他")[:12], "indices": [0]}] if leftovers else []))
        for g in free:
            # keywords 必须透传：_group_once 的提示词已按「方法名>术语>对象」优先级
            # 摘录原文；丢弃后会落到 _terms_acronym 正则兜底，混入句首词/作者名
            groups.append({"name": g["name"],
                           "indices": [leftovers[j] for j in g["indices"]],
                           "keywords": g.get("keywords") or []})
    covered = sum(len(g["indices"]) for g in groups)
    if covered != len(papers):
        import logging
        logging.getLogger(__name__).info(
            "锚点引导回落自由分组：覆盖不全（%d/%d，LLM 分配波动）", covered, len(papers))
        return []
    return groups


def _vector_fallback(papers, moves, axis, encoder, fixed_k=None) -> List[Dict[str, Any]]:
    """LLM 分组失败兜底：提取句向量 + 层次聚类（fixed_k 或自动 k）。"""
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    def doc_vec(i):
        if axis == "technical":
            sents = moves[i]["研究方法"] or [str(papers[i].get("title") or "")]
        else:
            sents = (moves[i]["研究背景"] + moves[i]["研究目的"]) or [str(papers[i].get("title") or "")]
        v = np.asarray(encoder.encode(sents)).mean(axis=0)
        return v / max(float(np.linalg.norm(v)), 1e-9)

    matrix = np.asarray([doc_vec(i) for i in range(len(papers))])
    if fixed_k:
        best = AgglomerativeClustering(n_clusters=min(fixed_k, len(matrix) - 1), metric="cosine", linkage="average").fit_predict(matrix)
    else:
        best, best_score = None, -2
        for k in range(2, min(9, len(matrix))):
            labels = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(matrix)
            score = silhouette_score(matrix, labels, metric="cosine")
            if score > best_score:
                best_score, best = score, labels
    groups: List[Dict[str, Any]] = []
    for lab in sorted(set(best)):
        groups.append({"name": f"簇{lab + 1}", "indices": [i for i, x in enumerate(best) if x == lab]})
    return groups


_STOPWORDS = frozenset(
    "the and this that with for from are was were been be have has had we our us you your they their "
    "it its in on of to as by at or is not can will may using used use based which who whom what when "
    "where how also than then more most other such into over between both each some any all only very "
    "propose propose proposed proposes method model models approach approaches paper study research "
    "result results experiment experiments show shows showed demonstrate demonstrates introduction"
    .split()
)


_TERM_SUFFIXES = (
    "网络", "模型", "方法", "算法", "检测", "预测", "识别", "分析", "学习", "聚类", "分类",
    "仿真", "框架", "系统", "技术", "策略", "机制", "理论", "调控", "建模", "优化", "筛选",
    "治疗", "诊断", "监测", "评估", "综述", "推断", "编码", "表示", "检索", "推理", "生成",
)


def _extract_axis_keywords(sentences: List[str], axis: str) -> List[str]:
    """从轴语步句提取专业关键词：缩写/大写术语/后缀名词/带限定复合词。

    - 英文缩写（TTSR/GNN/BERT/LSTM/YOLO）：全大写 2-6 字母
    - 英文专有技术词：首字母大写且非句首常见词
    - 中文后缀名词："图注意力网络""卷积神经网络""强化学习" 等 X+后缀 模式
    - 中文前缀限定："基于X的Y" 取 Y、"采用X" 取 X
    """
    import re
    seen = set()
    out = []
    for s in sentences:
        # 英文缩写（全大写 2-6 字母，非 XX/OK 类）
        for m in re.findall(r"\b[A-Z]{2,6}\b", s):
            if m not in ("II", "III", "IV", "OK", "NO", "YES", "AND", "THE", "FOR", "NOT", "BUT", "ALL", "NEW", "USE", "CAN"):
                if m not in seen:
                    seen.add(m); out.append(m)
        # 小写连字符复合技术术语（test-time scaling / pseudo-label method）：
        # 连字符复合词几乎必为专业术语，可作类簇短语的高质量补齐来源；
        # 尾缀虚词（on/in/of 等）不是术语一部分，剥掉
        for m in re.findall(r"\b[a-z]{2,}(?:-[a-z]{2,})+(?:\s+[a-z]{2,})?\b", s):
            words = m.split()
            while len(words) > 1 and words[-1] in (
                    "on", "in", "of", "for", "and", "the", "with", "to", "by", "from", "at", "as"):
                words.pop()
            m = " ".join(words)
            if len(m) >= 8 and m not in seen:
                seen.add(m); out.append(m)
        # 首字母大写的英文技术词（非句首常见词）— 取相邻大写词组成复合词；
        # 连字符/撇号不拆词（Self-Harmony、Humanity's Last Exam 保持完整，
        # 拆开会产出 'Self' 这类碎片）
        for m in re.findall(r"\b([A-Z][a-z]{2,}(?:['’-][A-Za-z]+)*(?:\s+[A-Z][a-z]{2,}(?:['’-][A-Za-z]+)*){0,2})\b", s):
            first = m.split()[0]
            if first.lower() in _STOPWORDS:
                continue
            if m not in seen:
                seen.add(m); out.append(m)
        # 中文后缀名词：X(2-4字)+技术后缀（短匹配优先，避免截到句子碎片）
        for suf in _TERM_SUFFIXES:
            for m in re.findall(r"([一-鿿]{2,4})" + suf, s):
                term = m + suf
                # 排除虚词/通用词开头的伪术语
                if any(w in term[:2] for w in ("研究", "本文", "该方", "我们", "为了", "通过", "采用", "基于", "利用", "结合", "进行")):
                    continue
                if term not in seen:
                    seen.add(term); out.append(term)
    # 后缀词排序：优先短词（"注意力网络" 优于 "意力网络学习"），同长取先出现
    zh_terms = [t for t in out if re.search(r"[一-鿿]", t)]
    en_terms = [t for t in out if not re.search(r"[一-鿿]", t)]
    zh_terms.sort(key=len)
    # 互相包含的取短的（"强化学习" 包含 "学习"→都保留但排前短的）
    return (en_terms[:3] + zh_terms[:4])[:6]


def _terms_acronym(moves_list, indices, axis) -> List[str]:
    """LLM 关键词缺失时的保守兜底：仅取英文缩写/专有词（TTSR/GNN/BERT 类）。

    中文正则后缀提取产出"表示进行检测"类碎片（无分词器无法根治），弃用；
    中文兜底直接用簇名（分组时 LLM 命名的语义簇名即主题词）。
    """
    import re
    seen = set()
    out = []
    for i in indices:
        mv = moves_list[i]
        sents = mv["研究方法"] if axis == "technical" else (mv["研究背景"] + mv["研究目的"])
        for s in sents:
            for m in re.findall(r"\b[A-Z]{2,6}\b", s):
                if m not in ("II", "III", "IV", "OK", "NO", "AND", "THE", "FOR", "NOT", "BUT"):
                    if m not in seen:
                        seen.add(m); out.append(m)
            for m in re.finditer(r"\b([A-Z][a-z]{2,}(?:['’-][A-Za-z]+)*(?:\s+[A-Z][a-z]{2,}(?:['’-][A-Za-z]+)*){0,2})\b", s):
                # 句首大写词（"Finally, ..." "Critically, ..."）只是普通词被大写，
                # 无术语含义：前面是句读/开头/换行的大写词一律排除
                prev = s[:m.start()].rstrip()
                if not prev or prev[-1] in ".!?:\"'“”…)】":
                    continue
                # "Johnson et al." 是作者引用不是术语
                if re.match(r"\s+et\s+al", s[m.end():]):
                    continue
                word = m.group(1)
                if word.split()[0].lower() not in _STOPWORDS and word not in seen:
                    seen.add(word); out.append(word)
    return out[:4]


def _pad_cluster_terms(base: Any, moves_list: List[Dict[str, Any]], indices: List[int],
                       axis: str, name: str, min_terms: int = 2) -> List[str]:
    """类簇短语不足 min_terms 时，从簇内文献语步句提取**高质量**术语补齐。

    用户要求（2026-09-06）：每簇类簇短语最少 2 个；但绝不拿低质碎片充数
    （如连字符拆开的 'Self'、句首词、作者名）——补不齐就动态返回现有数量。
    补齐来源仅限：英文缩写（TTSR/RL）、带连字符/撇号的完整方法名
    （Self-Harmony、Humanity's Last Exam）、多词专有术语、中文术语。
    """
    def _quality(t: str) -> bool:
        if re.fullmatch(r"(簇|孤立文献|文献|未分组|其他|单列)\s*\d*", t):
            return False                      # 占位词不配当类簇短语
        if re.search(r"[一-鿿]", t):
            return True                       # 中文术语
        if re.fullmatch(r"[A-Z][A-Z0-9-]{1,6}", t):
            return True                       # 缩写 RL / TTSR / BERT
        if "-" in t or "’" in t or "'" in t:
            return True                       # Self-Harmony / Humanity's Last Exam
        return len(t.split()) >= 2            # 多词专有术语

    terms: List[str] = []
    seen = set()
    for t in list(base or [])[:5]:
        t = _clean_text(t)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            terms.append(t)
    if len(terms) >= min_terms:
        return terms
    sents: List[str] = []
    for i in indices:
        mv = moves_list[i]
        sents.extend(mv["研究方法"] if axis == "technical" else (mv["研究背景"] + mv["研究目的"]))
    for t in _extract_axis_keywords(sents, axis) + _terms_acronym(moves_list, indices, axis):
        if t.lower() in seen or not _quality(t):
            continue
        seen.add(t.lower())
        terms.append(t)
        if len(terms) >= min_terms:
            break
    return terms


def run_move_aligned_clustering(papers, *, selected_axis, glm_client, encoder=None,
                                anchor_docs=None, cluster_count=None) -> Dict[str, Any]:
    """主入口：语步提取 → 双轴分组 → 输出轴 payload（与旧管线同构）。

    anchor_docs（用户上传训练样本，可选）非空时走锚点引导分组：样本内部先提取
    语步 → 类目档案 → 目标文献按档案归类（未归入的自由分组）；为空时纯 v3
    自由分组（综述粒度）。返回 {"axis", "clusters", "doc_axis_info", "moves",
    "quality", "projection"}；clusters 含 cluster_id/topic_name/size/doc_indices/
    representative_terms/members（members 供 phrase_sets/标签生成）。
    """
    n = len(papers)
    moves = extract_moves_batch(papers, glm_client)
    # 题名不做解析（2026-09-06 用户定调）：文件模式 title=文件名（1.pdf），
    # 文本模式 title=用户手动填写的题名——直接使用，不从全文/摘要提取
    # （提取会把作者名/邮箱/摘要头当题目，反而引入干扰）

    groups: List[Dict[str, Any]] = []
    method = ""
    if anchor_docs:
        # 锚点引导：用户类目为种子，语步级归类（方法对方法 / 场景对场景）
        groups = anchor_guided_groups(papers, moves, anchor_docs, selected_axis, glm_client)
        method = "llm_anchor_guided_grouping" if groups else ""
    if not groups:
        # 自由分组：≤BATCH_SIZE 一次；>BATCH_SIZE 分批 + 跨批合并
        if n <= BATCH_SIZE:
            groups = _group_once(glm_client, papers, moves, selected_axis, target_k=cluster_count)
        else:
            batches = [papers[i:i + BATCH_SIZE] for i in range(0, n, BATCH_SIZE)]
            moves_batches = [moves[i:i + BATCH_SIZE] for i in range(0, n, BATCH_SIZE)]
            with ThreadPoolExecutor(max_workers=3) as pool:
                batch_groups = list(pool.map(
                    lambda args: _group_once(glm_client, args[0], args[1], selected_axis),
                    zip(batches, moves_batches)))
            groups = _merge_batches(glm_client, batch_groups, BATCH_SIZE) if all(batch_groups) else []
        method = "llm_move_aligned_grouping"
    if not groups and encoder is not None:
        groups = _vector_fallback(papers, moves, selected_axis, encoder, fixed_k=cluster_count)
        method = "move_vector_fallback"
    if not groups:
        raise ValueError("语步对齐聚类失败：LLM 分组与向量兜底均未产出有效结果")

    groups.sort(key=lambda g: (-len(g["indices"]), min(g["indices"])))
    clusters, doc_axis_info = [], []
    for counter, g in enumerate(groups, start=1):
        cluster_id = f"C{counter:02d}"
        clusters.append({
            "cluster_id": cluster_id,
            "topic_id": cluster_id,
            "topic_name": g["name"],
            "size": len(g["indices"]),
            "doc_indices": sorted(g["indices"]),
            "representative_terms": _pad_cluster_terms(
                g.get("keywords"), moves, g["indices"], selected_axis, g["name"]),
            "members": [
                {"document_id": str(papers[i].get("document_id") or f"DOC{i + 1}"),
                 "title": str(papers[i].get("title") or "")}
                for i in sorted(g["indices"])
            ],
        })
        for i in g["indices"]:
            doc_axis_info.append({
                "index": i,
                "topic_id": cluster_id,
                "topic_name": g["name"],
            })
    doc_axis_info = sorted(doc_axis_info, key=lambda x: x["index"])

    # 投影：轴提取句向量 PCA（散点可视化；encoder 缺失时跳过）
    projection = []
    if encoder is not None:
        import numpy as np
        try:
            from sklearn.decomposition import PCA
            vecs = []
            for i, mv in enumerate(moves):
                sents = (mv["研究方法"] or mv["研究背景"] or [str(papers[i].get("title") or "x")])
                v = np.asarray(encoder.encode(sents[:6])).mean(axis=0)
                vecs.append(v / max(float(np.linalg.norm(v)), 1e-9))
            coords = PCA(n_components=2, random_state=42).fit_transform(np.asarray(vecs))
            scaled = []
            for col in range(2):
                values = coords[:, col]
                span = float(values.max() - values.min())
                scaled.append(np.full(len(values), 50.0) if span < 1e-12
                              else 5.0 + (values - values.min()) / span * 90.0)
            for i in range(n):
                projection.append({
                    "document_id": str(papers[i].get("document_id") or f"DOC{i + 1}"),
                    "title": str(papers[i].get("title") or ""),
                    "cluster_id": next(c["cluster_id"] for c in clusters if i in c["doc_indices"]),
                    "x": round(float(scaled[0][i]), 3),
                    "y": round(float(scaled[1][i]), 3),
                })
        except Exception:  # noqa: BLE001 - 投影失败不阻塞聚类结果
            projection = []

    # 质量指标口径与弹窗/响应示例一致（2026-09-06）：轮廓系数等旧向量指标
    # 已从弹窗移除，不再输出；保留簇数 + 簇内平均相似度（≥2 篇簇的均值）+ 算法
    multi = [c["feature_statistics"]["intra_cluster_similarity"]
             for c in clusters if c["size"] >= 2
             and isinstance(c.get("feature_statistics", {}).get("intra_cluster_similarity"), (int, float))]
    quality = {
        "cluster_count": len(clusters),
        "intra_cluster_similarity": round(sum(multi) / len(multi), 3) if multi else None,
        "algorithm_requested": "move_aligned",
        "algorithm_used": method,
    }
    return {
        "axis": selected_axis,
        "clusters": clusters,
        "doc_axis_info": doc_axis_info,
        "moves": moves,
        "quality": quality,
        "projection": projection,
    }
