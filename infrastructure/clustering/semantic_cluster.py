"""深度聚类算法2：纯语义聚类 + 关键词重叠挖 top-1 标签。

与算法1（topicfusion_v8 主题映射表分类）平行，完全不依赖主题库：
LLM 抽技术路线文本 → bge-m3 编码 → KMeans+轮廓系数选 k → 每簇 jieba 挖跨文献
重叠关键词 → top-1 作簇标签。簇从数据里长出来，无覆盖缺口问题；真向量聚类使
轮廓系数等质量指标合法有效。

可干净删除：本模块 + semantic_service._execute_clustering_v2 + 前端算法下拉，
算法1 一行不动。
"""
from __future__ import annotations

import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score

from infrastructure.clustering.topicfusion_v8.incremental import _keywords
from infrastructure.rag.m3_encoder import m3_encoder

# 停用词（复用 _name_cluster 的，补常见虚词/泛词）
_ZH_STOP = {"基于", "研究", "分析", "方法", "模型", "系统", "技术", "本文", "提出",
            "采用", "使用", "通过", "实现", "针对", "用于", "利用", "结合", "以及",
            "并且", "同时", "从而", "进而", "能够", "可以", "一个", "这种", "该",
            "其", "此", "为", "在", "对", "与", "及", "和", "等", "了", "的", "是",
            # 泛词/虚词（作簇标签无信息量，IDF 之外再显式滤掉）
            "进行", "问题", "框架", "实验", "结果", "效果", "性能", "方案", "过程",
            "工作", "任务", "数据", "表现", "提升", "优化", "思路", "目标", "验证",
            "评估", "表明", "发现", "提供", "建立", "设计", "构建", "训练", "测试",
            "比较", "综合", "相关", "不同", "重要", "有效", "高效", "新型", "上述",
            "其中", "此外", "然而", "因此", "由于", "随着", "现有", "现有方法",
            "本文提出", "本文方法"}
_EN_STOP = {"using", "based", "study", "method", "model", "analysis", "the", "a",
            "an", "for", "with", "and", "of", "to", "in", "on", "via", "by",
            "this", "paper", "we", "our", "is", "are", "as", "at", "from"}
# jieba 词性白名单：名词类 + 动名词 + 动词方法词 + 英文
_POS_KEEP = {"n", "nr", "ns", "nt", "nz", "vn", "v", "eng", "l"}


def _extract_terms(text: str) -> list[str]:
    """jieba 分词，抽术语（含相邻二元组捕获被切散的复合术语如"强化学习"）。

    jieba 常把"强化学习"切成"强化"+"学习"，故额外拼相邻中文词成 bigram，
    靠跨文献文档频率（DF）让真复合术语浮现、噪声 bigram 自然被滤掉。
    """
    if not text:
        return []
    try:
        import jieba.posseg as pseg
    except Exception:  # noqa: BLE001
        return _regex_terms(text)
    tokens: list[tuple[str, str]] = []
    for w, flag in pseg.cut(str(text)):
        w = w.strip()
        if w:
            tokens.append((w, flag))
    terms: list[str] = []
    # 一元词
    for w, flag in tokens:
        if re.search(r"[一-鿿]", w):
            if len(w) >= 2 and w not in _ZH_STOP and flag in _POS_KEEP:
                terms.append(w)
        elif re.fullmatch(r"[A-Za-z][A-Za-z-]{2,}", w):
            wl = w.lower()
            if wl not in _EN_STOP:
                terms.append(wl)
    # 相邻二元组（捕获强化学习/对比学习/表示学习等被切散的复合术语）
    for i in range(len(tokens) - 1):
        a, fa = tokens[i]
        b, fb = tokens[i + 1]
        if (re.search(r"[一-鿿]", a) and re.search(r"[一-鿿]", b)
                and len(a) >= 2 and len(b) >= 2
                and a not in _ZH_STOP and b not in _ZH_STOP
                and (fa in _POS_KEEP or fb in _POS_KEEP)):
            bi = a + b
            if 3 <= len(bi) <= 6 and bi not in _ZH_STOP:
                terms.append(bi)
    return terms


def _regex_terms(text: str) -> list[str]:
    """jieba 不可用时的兜底：正则抽中文 2-6 字片段 + 英文词。"""
    out: list[str] = []
    for m in re.findall(r"[一-鿿]{2,6}", str(text)):
        if m not in _ZH_STOP:
            out.append(m)
    for m in re.findall(r"\b[A-Za-z][A-Za-z-]{2,}\b", str(text)):
        wl = m.lower()
        if wl not in _EN_STOP:
            out.append(wl)
    return out


def _label_cluster(doc_terms: list[dict[str, int]], member_indices: list[int],
                   global_df: Counter, n: int) -> tuple[str | None, list[str]]:
    """挖簇内跨文献重叠关键词，IDF 加权排序，返回 (top1_label, evidence_top5)。

    纯簇内 DF 排序会让"进行/问题"这种每篇都出现的泛词排第一（DF 最高）。
    改用 count×IDF：全局 DF 高的 ubiquitous 词 IDF 低→自然下沉，让簇内特异性
    词（如"强化学习""实体检索"虽只出现在部分篇里）浮现到 top-1。
    """
    import math
    counter: Counter[str] = Counter()
    df_hits: dict[str, set] = {}
    for idx in member_indices:
        for term, w in doc_terms[idx].items():
            counter[term] += w
            df_hits.setdefault(term, set()).add(idx)

    def _idf(t: str) -> float:
        return math.log((n + 1) / (global_df.get(t, 1) + 1)) + 1.0

    # 子串降权：短词若是同簇另一候选词的真子串（"对比"⊂"对比学习"），×0.5 降权，
    # 让 jieba 切散后被碎片掩盖的复合术语浮到 top-1。
    terms_set = set(counter.keys())
    def _substr_weight(t: str) -> float:
        return 0.5 if any(t != s and t in s for s in terms_set) else 1.0

    # 排序键：(count×IDF×子串权重, 簇内DF, 词长)
    ranked = sorted(counter.items(),
                    key=lambda x: (x[1] * _idf(x[0]) * _substr_weight(x[0]),
                                   len(df_hits.get(x[0], ())),
                                   len(x[0])), reverse=True)
    evidence = [t for t, _ in ranked[:5]]
    top1 = evidence[0] if evidence else None
    return top1, evidence


def _choose_k_v2(matrix, n: int, random_state: int) -> int:
    """算法2 专用 k 选择：比算法1 的 _choose_k 更宽松。

    算法1 的 _choose_k 用 n//4 封顶 + 每簇≥3，为 12 篇只留 k∈{2,3}，过粗。
    此处放宽到 max_k=n//2（上限8），允许小样本语义聚类分出 4-6 簇。
    不改 incremental._choose_k（算法1 共享，保持原行为）。

    不平衡惩罚：单例簇（outlier 被 KMeans 孤立）会虚高 silhouette，按最小簇大小
    降权——min_size<2 加 0.05 惩罚，避免退化成 11+1 之类的结构。
    k 惩罚 0.006（原 0.012 过重，12 篇只敢分 2-3 簇，把异类并一起；调低让算法
    敢分 4-6 簇，提升同质性）。
    """
    if n < 2:
        return 1
    if n < 4:
        return 2
    maximum = min(8, n // 2)
    candidates = [k for k in range(2, maximum + 1) if n >= 2 * k]
    if not candidates:
        return 2
    best_k, best_score = 2, -1.0
    for k in candidates:
        labels = KMeans(n_clusters=k, n_init=20, random_state=random_state).fit_predict(matrix)
        min_size = int(np.bincount(labels).min())
        try:
            sil = float(silhouette_score(matrix, labels, metric="cosine"))
        except Exception:  # noqa: BLE001
            continue
        penalty = 0.006 * (k - 2) + (0.05 if min_size < 2 else 0.0)
        score = sil - penalty
        if score > best_score:
            best_k, best_score = k, score
    return best_k


def _pca_projection(M: np.ndarray, clusters: list[dict], doc_ids: list[str]) -> list[dict]:
    """PCA 2D 降维 → 归一化到 [0,100]，每篇带 document_id/cluster_id。"""
    n = M.shape[0]
    if n < 1:
        return []
    try:
        comps = PCA(n_components=min(2, max(1, n)), random_state=42).fit_transform(M)
    except Exception:  # noqa: BLE001
        comps = np.zeros((n, 2))
    xs = comps[:, 0] if comps.shape[1] > 0 else np.zeros(n)
    ys = comps[:, 1] if comps.shape[1] > 1 else np.zeros(n)

    def _norm01(v):
        v = np.asarray(v, dtype=float)
        if v.size == 0:
            return v
        lo, hi = float(v.min()), float(v.max())
        if hi - lo < 1e-9:
            return np.full_like(v, 50.0)
        return (v - lo) / (hi - lo) * 100

    nx, ny = _norm01(xs), _norm01(ys)
    cid_by_idx = {}
    for cl in clusters:
        for i in cl["doc_indices"]:
            cid_by_idx[i] = cl["cluster_id"]
    return [
        {"document_id": doc_ids[i], "cluster_id": cid_by_idx.get(i, ""),
         "x": round(float(nx[i]), 2), "y": round(float(ny[i]), 2)}
        for i in range(n)
    ]


_LLM_CLUSTER_SYSP = (
    "你是科技文献聚类专家。以下是按序号编号的若干篇文献各自的研究主题描述。请按【具体研究主题】将它们聚成若干簇。\n\n"
    "要求：\n"
    "- 按每篇文献的核心研究对象/问题聚类：研究同一具体对象/问题的归同簇\n"
    "- 同一主题的不同方法/角度/数据仍归同簇（不要按方法变体拆分）\n"
    "- 不同具体主题必须分到不同簇（如 区域经济格局≠城市土地利用≠农业粮食≠旅游客流；"
    "电力设备≠故障诊断≠稳定控制；配电网规划≠配电网故障保护）\n"
    "- 簇数由实际主题数决定，不要凑数合并、也不要按方法拆碎\n"
    "- 每簇给一个 3-8 字的具体中文标签\n"
    "- 每篇必须归且仅归一个簇\n"
    "- 只看本文核心主题，不要被 related work 提及的他人工作干扰\n"
    "只输出JSON：{\"clusters\":[{\"label\":\"中文标签\",\"indices\":[0,3,5]}]}\n"
    "indices 是文献在下方列表中的【0-based序号】；每个序号必须且仅出现一次。"
)


def llm_cluster(df: pd.DataFrame, axis: str, glm_client, *, random_state: int = 42) -> dict:
    """LLM 直接聚类：汇总每篇技术路线 → LLM 输出分组。

    小批量（N≤50）主路径，质量远高于 bge+KMeans（12篇实测 ARI 0.573 vs 0.086）。
    LLM 能理解"本文核心方法 vs related work 提及"，不被流行词污染。

    非向量聚类 → silhouette/CH/DB 无意义（返回 None）。但用 bge 编码做 PCA 投影
    仅供可视化（点按 LLM 簇着色），聚类本身完全由 LLM 决定。
    返回与 semantic_cluster 同结构：{clusters, doc_axis_info, silhouette, k, projection}
    """
    text_col = "technical_route_text" if axis == "technical" else "application_scenario_text"
    doc_ids = [str(d) for d in df["document_id"].tolist()] if "document_id" in df else [f"D{i+1}" for i in range(len(df))]
    n = len(doc_ids)
    if n == 0:
        return {"clusters": [], "doc_axis_info": [], "silhouette": None,
                "calinski_harabasz": None, "davies_bouldin": None, "k": 0, "projection": []}

    docs = []
    for i, (_, row) in enumerate(df.iterrows()):
        route = str(row.get(text_col, "") or "").strip()
        docs.append({"document_id": doc_ids[i],
                     "title": str(row.get("title", "") or ""),
                     "route": route or str(row.get("title", "") or "文献")})

    # LLM 聚类（位置序号交互，避免 id 幻觉）
    listing = "\n".join(
        f"[{i}] 标题：{d['title']}\n    技术路线：{d['route']}" for i, d in enumerate(docs))
    try:
        out = glm_client.chat_json(_LLM_CLUSTER_SYSP, f"文献列表（共{n}篇）：\n{listing}",
                                   temperature=0.3, timeout=90.0, max_tokens=2000)
    except Exception:  # noqa: BLE001
        out = {"clusters": []}
    label_at: list[str] = ["未分类"] * n
    for cl in out.get("clusters", []):
        label = (cl.get("label") or "").strip() or "未分类"
        for idx in cl.get("indices", []):
            try:
                pos = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= pos < n:
                label_at[pos] = label

    # 组装 clusters（按 LLM 标签分组）
    label_to_members: dict[str, list[int]] = {}
    for i in range(n):
        label_to_members.setdefault(label_at[i], []).append(i)
    clusters: list[dict] = []
    seen: set[str] = set()
    for lbl, members in label_to_members.items():
        cid = lbl or "未分类"
        if cid in seen:
            cid = f"{cid}#{len(clusters)+1}"
        seen.add(cid)
        clusters.append({"cluster_id": cid, "topic_name": lbl or cid,
                         "doc_indices": members, "representative_terms": [lbl] if lbl else [],
                         "size": len(members)})

    # 每篇 axis info（score=1.0 表示 LLM 明确归簇，无相似度数值）
    doc_axis_info: list[dict] = [{} for _ in range(n)]
    for cl in clusters:
        for i in cl["doc_indices"]:
            doc_axis_info[i] = {"topic_id": cl["cluster_id"],
                                "topic_name": cl["topic_name"], "score": 1.0}

    # bge 编码做 PCA 投影（仅可视化，聚类不依赖向量）
    projection = []
    try:
        texts = [d["route"] for d in docs]
        M = m3_encoder.encode(texts)
        projection = _pca_projection(M, clusters, doc_ids)
    except Exception:  # noqa: BLE001
        pass

    return {"clusters": clusters, "doc_axis_info": doc_axis_info,
            "silhouette": None, "calinski_harabasz": None, "davies_bouldin": None,
            "k": len(clusters), "projection": projection}


# ------------------------------------------------------------------ 大批量分层
def _llm_cluster_docs(docs: list[dict], glm_client, temp: float = 0.3) -> dict:
    """单桶 LLM 聚类：docs=[{document_id,title,route}] → {document_id: label}。

    llm_cluster 与 llm_cluster_large 共用的桶内聚类核。返回每篇的簇标签。
    用【位置序号】与 LLM 交互（listing 用 [0][1]...，LLM 回传 indices），
    按 indices 映射回 document_id——避免 LLM 照抄 prompt 示例的 id 格式导致全不匹配。
    """
    n = len(docs)
    listing = "\n".join(
        f"[{i}] 标题：{d['title']}\n    技术路线：{d['route']}" for i, d in enumerate(docs))
    try:
        out = glm_client.chat_json(_LLM_CLUSTER_SYSP, f"文献列表（共{n}篇）：\n{listing}",
                                   temperature=temp, timeout=90.0, max_tokens=2000)
    except Exception:  # noqa: BLE001
        return {}
    mapping: dict[str, str] = {}
    for cl in out.get("clusters", []):
        label = (cl.get("label") or "").strip() or "未分类"
        for idx in cl.get("indices", []):
            try:
                pos = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= pos < n:
                mapping[str(docs[pos]["document_id"])] = label
    return mapping


def _merge_clusters(intermediate: list[dict], M: np.ndarray, *,
                    threshold: float = 0.80, glm_client=None) -> list[dict]:
    """合并跨桶中间簇 → 最终簇 [{label, doc_indices}]。

    用【average-linkage 层次聚类】在 bge 簇心上做：距离=1-余弦，
    distance_threshold=1-threshold。average linkage 抗链式合并
    （single-linkage 的并查集会把 A~B~C 传递成一个大簇，实测 98 簇→4 簇）。
    不再用"同名强制合并"——LLM 桶内标签可能泛化（如多个 EE 子方向都叫"电力系统
    分析"），按标签硬并会误合。LLM 仅给合并后的组规范命名，不参与合并决策。
    """
    if not intermediate:
        return []
    cents = np.array([M[c["doc_indices"]].mean(axis=0) for c in intermediate])
    K = len(intermediate)
    if K == 1:
        return [{"label": intermediate[0]["label"] or "未分类",
                 "doc_indices": list(intermediate[0]["doc_indices"])}]
    # 余弦距离矩阵
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import AgglomerativeClustering
    cos = cosine_similarity(cents)
    dist = np.clip(1.0 - cos, 0.0, 2.0)
    np.fill_diagonal(dist, 0.0)
    agg = AgglomerativeClustering(
        n_clusters=None, metric="precomputed", linkage="average",
        distance_threshold=1.0 - threshold)
    merge_labels = agg.fit_predict(dist)

    comp: dict[int, list[int]] = {}
    for i in range(K):
        comp.setdefault(int(merge_labels[i]), []).append(i)

    groups: list[dict] = []
    for cids in comp.values():
        doc_indices: list[int] = []
        for cid in cids:
            doc_indices.extend(intermediate[cid]["doc_indices"])
        labels = [intermediate[cid]["label"] for cid in cids if intermediate[cid]["label"]]
        label = Counter(labels).most_common(1)[0][0] if labels else "未分类"
        groups.append({"label": label, "doc_indices": doc_indices,
                       "_cids": cids})

    # 可选：LLM 规范命名（不改分组，仅给每组一个更好的标签）
    if glm_client is not None and groups:
        listing = "\n".join(
            f"[{i}] 现标签:{g['label']} 篇数:{len(g['doc_indices'])} "
            f"代表路线:{intermediate[g['_cids'][0]]['rep_route'][:90]}"
            for i, g in enumerate(groups))
        try:
            out = glm_client.chat_json(
                "你是科技文献聚类命名专家。下面是已分好的若干簇（分组不可改），"
                "请给每簇一个 3-8 字规范中文标签，反映该簇核心主题。\n"
                "只输出JSON：{\"names\":[\"标签0\",\"标签1\",...]}",
                f"簇列表：\n{listing}", temperature=0.1, timeout=90.0, max_tokens=1500)
            names = out.get("names", [])
            if isinstance(names, list) and len(names) == len(groups):
                for g, nm in zip(groups, names):
                    nm = (nm or "").strip()
                    if nm:
                        g["label"] = nm
        except Exception:  # noqa: BLE001
            pass
    for g in groups:
        g.pop("_cids", None)
    return groups


_LLM_SPLIT_SYSP = (
    "你是科技文献主题分析专家。下面是【已判定为同一大类】的若干文献研究主题描述，"
    "但其中可能混入了不同的具体研究主题。请阅读每篇，按【具体研究对象/问题】精分：\n"
    "- 只有研究【同一具体对象/问题】的才归一组（如 区域经济空间格局 ≠ 城市土地利用 ≠ 农业粮食 ≠ 旅游客流）\n"
    "- 同一主题的不同方法/角度仍归一组\n"
    "- 宁可多分，不要把不同具体主题糊一起\n"
    "输出JSON：{\"groups\":[{\"indices\":[0,3,5],\"label\":\"3-8字标签\"},...]}\n"
    "indices 是输入列表的0-based序号；每个输入必须归且仅归一组。"
)

_JUNK_LABELS = {"未分类", "无", "", "其它", "其他", "其他主题"}


def _llm_split_group(doc_indices: list[int], routes: list[str], glm_client,
                     target: int) -> list[dict]:
    """对一个大粗簇（doc_indices）用 LLM 按实际内容精分为子簇。

    返回 [{label, doc_indices}]。LLM 读每篇 route 按具体研究主题分组；
    漏分的文档由调用方兜底（bge 重分）。
    """
    listing = "\n".join(f"[{i}] {routes[di][:160]}" for i, di in enumerate(doc_indices))
    hint = (f"共{len(doc_indices)}篇。请精分为【约{target}组（{max(2, target-1)}~{target+2}组）】，"
            f"按具体研究主题归类。同一主题合并为一组（不要每2-3篇就拆一组）。")
    try:
        out = glm_client.chat_json(_LLM_SPLIT_SYSP, f"{hint}\n{listing}",
                                   temperature=0.1, timeout=120.0, max_tokens=2500)
        result, covered = [], set()
        for g in out.get("groups", []):
            idxs = [int(x) for x in g.get("indices", []) if isinstance(x, (int, float))]
            real = [doc_indices[x] for x in idxs
                    if 0 <= x < len(doc_indices) and doc_indices[x] not in covered]
            for r in real:
                covered.add(r)
            if real:
                result.append({"label": (g.get("label") or "").strip() or "未分类",
                               "doc_indices": real})
        miss = [di for di in doc_indices if di not in covered]
        if miss:
            result.append({"label": "未分类", "doc_indices": miss})
        return result
    except Exception:  # noqa: BLE001
        return [{"label": "未分类", "doc_indices": list(doc_indices)}]


def llm_cluster_large(df: pd.DataFrame, axis: str, glm_client, *,
                      bucket_size: int = 40, random_state: int = 42,
                      merge_threshold: float = 0.78, split_min: int = 12) -> dict:
    """大批量 LLM 分层聚类（N>50）：分桶 → 桶内 LLM 微聚类 → bge 粗合并 → LLM 精分。

    小批量 llm_cluster 把全部 route 喂一次 LLM，N>50 时上下文/注意力都撑不住。
    本函数四段管线：
      1. bge 编码 → KMeans 切 B 桶（仅负载均衡）
      2. 每桶独立 LLM 微聚类（≤40 篇/桶）→ 中间簇
      3. bge 簇心 average-linkage 粗合并（th=merge_threshold）—— 把同主题跨桶碎片合拢，
         但同域不同主题仍会糊在一起（社科摘要词汇高度重叠）
      4. 对大粗簇（>split_min 篇）用 LLM 读实际 route 精分回细主题；小粗簇保留；
         漏分/未分类文档按 bge 重分到最近实簇

    bge 负责分桶/粗合并/重分/可视化，LLM 负责桶内微聚类与大簇精分。返回结构与 llm_cluster 一致。
    """
    text_col = "technical_route_text" if axis == "technical" else "application_scenario_text"
    doc_ids = [str(d) for d in df["document_id"].tolist()] if "document_id" in df else [f"D{i+1}" for i in range(len(df))]
    n = len(doc_ids)
    if n == 0:
        return {"clusters": [], "doc_axis_info": [], "silhouette": None,
                "calinski_harabasz": None, "davies_bouldin": None, "k": 0, "projection": []}
    if n <= 50:
        return llm_cluster(df, axis, glm_client, random_state=random_state)

    routes = []
    for _, row in df.iterrows():
        r = str(row.get(text_col, "") or "").strip()
        routes.append(r or str(row.get("title", "") or "文献"))

    # 1. bge 编码
    M = m3_encoder.encode(routes)

    # 2. KMeans 分桶（仅切分，不要求语义精确）
    B = max(2, -(-n // bucket_size))  # ceil
    B = min(B, n)
    bucket_labels = KMeans(n_clusters=B, n_init=10, random_state=random_state).fit_predict(M)

    # 3. 每桶 LLM 微聚类
    intermediate: list[dict] = []
    for b in range(B):
        idxs = [i for i in range(n) if bucket_labels[i] == b]
        if not idxs:
            continue
        docs = [{"document_id": doc_ids[i], "title": "", "route": routes[i]} for i in idxs]
        mapping = _llm_cluster_docs(docs, glm_client, temp=0.3)
        lbl_to_idxs: dict[str, list[int]] = {}
        for i in idxs:
            lbl = mapping.get(doc_ids[i], "未分类")
            lbl_to_idxs.setdefault(lbl, []).append(i)
        for lbl, gidxs in lbl_to_idxs.items():
            intermediate.append({"label": lbl, "doc_indices": gidxs,
                                 "rep_route": routes[gidxs[0]]})

    # 4. bge 粗合并（average-linkage，不命名）
    coarse = _merge_clusters(intermediate, M, threshold=merge_threshold, glm_client=None)

    # 5. 大粗簇 LLM 精分；小粗簇保留
    final_groups: list[dict] = []
    big_tasks = []
    for g in coarse:
        if len(g["doc_indices"]) > split_min:
            big_tasks.append(g["doc_indices"])
        else:
            final_groups.append({"label": g["label"], "doc_indices": list(g["doc_indices"])})
    if big_tasks:
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(_llm_split_group, t, routes, glm_client,
                              max(1, round(len(t) / 22))): t for t in big_tasks}
            for fut in as_completed(futs):
                final_groups.extend(fut.result())

    # 6. 漏分/未分类文档 → bge 重分到最近实簇
    covered = set(i for g in final_groups for i in g["doc_indices"])
    junk_docs = [i for i in range(n) if i not in covered] + [
        i for g in final_groups if g["label"].strip() in _JUNK_LABELS for i in g["doc_indices"]]
    real = [g for g in final_groups if g["label"].strip() not in _JUNK_LABELS]
    if junk_docs and real:
        cents = []
        for g in real:
            v = M[g["doc_indices"]].mean(axis=0)
            cents.append(v / (np.linalg.norm(v) + 1e-9))
        cents = np.array(cents)
        for i in junk_docs:
            v = M[i]; v = v / (np.linalg.norm(v) + 1e-9)
            real[int(np.argmax(cents @ v))]["doc_indices"].append(i)
        final_groups = real
    elif not real:
        final_groups = [{"label": "未分类", "doc_indices": list(range(n))}]

    # 7. 组装最终 clusters（与 llm_cluster 同结构）
    clusters: list[dict] = []
    seen: set[str] = set()
    for g in final_groups:
        members = g["doc_indices"]
        if not members:
            continue
        lbl = g["label"] or "未分类"
        cid = lbl
        if cid in seen:
            cid = f"{lbl}#{len(clusters)+1}"
        seen.add(cid)
        clusters.append({"cluster_id": cid, "topic_name": lbl,
                         "doc_indices": members, "representative_terms": [lbl] if lbl else [],
                         "size": len(members)})

    doc_axis_info: list[dict] = [{} for _ in range(n)]
    for cl in clusters:
        for i in cl["doc_indices"]:
            doc_axis_info[i] = {"topic_id": cl["cluster_id"],
                                "topic_name": cl["topic_name"], "score": 1.0}

    projection = _pca_projection(M, clusters, doc_ids)
    return {"clusters": clusters, "doc_axis_info": doc_axis_info,
            "silhouette": None, "calinski_harabasz": None, "davies_bouldin": None,
            "k": len(clusters), "projection": projection,
            "_meta": {"buckets": B, "intermediate_clusters": len(intermediate),
                      "coarse_clusters": len(coarse)}}


def semantic_cluster(df: pd.DataFrame, axis: str, *, random_state: int = 42) -> dict:
    """对 df 在指定轴做纯语义聚类。

    axis: "technical" | "application"
    返回 {clusters, doc_axis_info, silhouette, k, projection}
    """
    text_col = "technical_route_text" if axis == "technical" else "application_scenario_text"
    doc_ids = [str(d) for d in df["document_id"].tolist()] if "document_id" in df else [f"D{i+1}" for i in range(len(df))]
    texts = []
    for _, row in df.iterrows():
        t = str(row.get(text_col, "") or "").strip()
        texts.append(t if t else str(row.get("title", "") or "文献"))
    n = len(texts)
    if n == 0:
        return {"clusters": [], "doc_axis_info": [], "silhouette": None, "k": 0, "projection": []}

    M = m3_encoder.encode(texts)  # (n,1024) L2 归一化
    k = _choose_k_v2(M, n, random_state)
    if k < 2:
        labels = np.zeros(n, dtype=int)
    else:
        labels = KMeans(n_clusters=k, n_init=20, random_state=random_state).fit_predict(M)

    sil = None
    ch = None
    db = None
    if k >= 2 and n >= 3 and len(set(labels.tolist())) >= 2:
        try:
            sil = round(float(silhouette_score(M, labels, metric="cosine")), 3)
        except Exception:  # noqa: BLE001
            sil = None
        # CH 指数(簇间/簇内方差比,越大越好)、DB 指数(越小越好)
        # 用 M 的前 50 主成分算(原 1024 维时 CH/DB 量纲失真,降维后更稳)
        try:
            from sklearn.decomposition import PCA as _PCA
            Mp = _PCA(n_components=min(50, n - 1), random_state=random_state).fit_transform(M) if n > 2 else M
            ch = round(float(calinski_harabasz_score(Mp, labels)), 2)
            db = round(float(davies_bouldin_score(Mp, labels)), 3)
        except Exception:  # noqa: BLE001
            pass

    # 预抽每篇术语（term→权重），供 _label_cluster 复用 + 算全局 DF（IDF 压泛词）
    doc_terms: list[dict[str, int]] = []
    for idx in range(n):
        row = df.iloc[idx]
        dt: dict[str, int] = {}
        for term in _keywords(row.get("keywords", [])):
            term = re.sub(r"\s+", " ", term).strip()
            if len(term) >= 2 and term not in _ZH_STOP:
                dt[term] = max(dt.get(term, 0), 3)
        for term in _extract_terms(str(row.get(text_col, ""))):
            dt[term] = max(dt.get(term, 0), 1)
        title = str(row.get("title", ""))
        # 仅取中文标题词（英文标题词在中文标签策略下是噪声，且会被正则截断成碎片）
        for term in re.findall(r"[一-鿿]{2,12}", title):
            if term in _ZH_STOP:
                continue
            dt[term] = max(dt.get(term, 0), 1)
        doc_terms.append(dt)
    global_df: Counter = Counter()
    for dt in doc_terms:
        for t in dt:
            global_df[t] += 1

    # 每簇：centroid + doc-centroid 相似度 + top-1 标签
    clusters: list[dict] = []
    seen: set[str] = set()
    for c in range(int(labels.max()) + 1):
        members = [i for i in range(n) if int(labels[i]) == c]
        if not members:
            continue
        centroid = M[members].mean(axis=0)
        cnorm = centroid / (np.linalg.norm(centroid) + 1e-9)
        sims = {i: float(M[i] @ cnorm) for i in members}  # M 已归一化 → 内积=cosine
        top1, evidence = _label_cluster(doc_terms, members, global_df, n)
        cid = top1 if top1 else f"簇{c+1}"
        if cid in seen:  # top-1 词碰撞 → 加序号保证唯一（colorMap 不合并）
            cid = f"{cid}#{c+1}"
        seen.add(cid)
        clusters.append({
            "cluster_id": cid,
            "topic_name": top1 or cid,
            "doc_indices": members,
            "representative_terms": evidence,
            "size": len(members),
            "_sims": sims,
        })

    # 每篇 axis info（供 normalizer 组 documents + feature_statistics）
    doc_axis_info: list[dict] = [{} for _ in range(n)]
    for cl in clusters:
        for i in cl["doc_indices"]:
            doc_axis_info[i] = {
                "topic_id": cl["cluster_id"],
                "topic_name": cl["topic_name"],
                "score": round(cl["_sims"][i], 4),
            }
    for cl in clusters:
        cl.pop("_sims", None)

    projection = _pca_projection(M, clusters, doc_ids)
    return {
        "clusters": clusters,
        "doc_axis_info": doc_axis_info,
        "silhouette": sil,
        "calinski_harabasz": ch,
        "davies_bouldin": db,
        "k": len(clusters),
        "projection": projection,
    }
