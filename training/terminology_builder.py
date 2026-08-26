"""en-keyword 术语库归一化构建管道（离线一次性脚本）。

用大模型判定术语是否属同一内容/概念，把同义术语（缩写↔全称↔单复数↔同一实体
不同写法）聚簇，每簇选 canonical 规范形，写入 kw_en_model.json 的 domain_terms
字段，供 _execute_keyword 消费（归一匹配放宽 preserve_original_form + normalized_term
填 canonical）。

流程：
  1. 候选术语池：对每篇 en_abstract+en_name 调 mine_candidates + 收集 author keywords
  2. 规则预聚类：缩写-全称/词干/子串/括号学名/连字符变体 → 候选同义对（降 LLM 调用量）
  3. LLM 批量同义判定：SYSP_TERM_PAIR（默认 false 保守）+ batch + ThreadPoolExecutor
  4. 连通分量合并 → 簇；每簇选 canonical（作者关键词优先 > 最高频 > 偏好全称）
  5. 写 kw_en_model.json domain_terms（保留 feature_weights+few_shot 不动）

用法：
  python -m training.terminology_builder \
    --input rules/deep_clustering/input_1000_english_title_abstract_keywords.json \
    --output rules/keyword_recognition/kw_en_model.json \
    --min-freq 2 --min-source-count 2 --batch-size 20 --top-k 6
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from training.keyword_phrase_miner_en import mine_candidates  # noqa: E402

# 术语同义判定 prompt（默认 false 保守，只有确属同一具体概念/实体才 true）
SYSP_TERM_PAIR = (
    "你是科技文献术语归一化专家。下面是若干【术语对】，每对含两个英文术语及其在语料中的上下文片段。"
    "请判断每对的两个术语是否指代【同一具体概念/实体】（同义/同指），而非仅相关或上下位。\n"
    "- 同一概念 → same=true（如 'OMIEC' 与 'organic mixed ionic-electronic conductor' 缩写-全称→true；"
    "'wildcat' 与 'Felis silvestris' 同一物种→true；'haematology' 与 'hematology' 英美拼写→true；"
    "'conductor' 与 'conductors' 单复数→true）\n"
    "- 相关但不同概念 → same=false（如 'haematology' 与 'immunology' 相关但不同学科→false；"
    "'perovskite' 与 'solar cell' 上下位→false；'TCO' 与 'transparent conductive oxide' 同一→true，"
    "但 'TCO-free' 与 'TCO' 是不同概念→false；'titanium' 与 'titanium silicide' 上下位→false）\n"
    "- 默认 false，只有确属同一具体概念/实体才 true\n"
    "输出JSON：{\"pairs\":[{\"id\":0,\"same\":false,\"reason\":\"...\"}]}"
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)*")
# 缩写：全大写 2-8 字母，或首字母大写混合（如 OMIEC / TOPCon / TiSi）
_ABBREV_RE = re.compile(r"^(?:[A-Z]{2,8}|[A-Z][a-z]+[A-Z][A-Za-z]*)$")


def _norm_kw(k) -> str:
    """把 author keyword 归一为字符串（兼容 str / {en_name} / {name}）。"""
    if isinstance(k, dict):
        return str(k.get("en_name") or k.get("name") or "").strip()
    return str(k or "").strip()


def build_candidate_pool(papers: List[dict]) -> List[dict]:
    """从所有文献抽候选术语 + 收集 author keywords，返回候选池（去重+统计）。"""
    pool: Dict[str, dict] = {}  # phrase_cf -> {phrase, freq, sources:set, from_kw:bool, context:str}

    def _add(phrase: str, text: str, doc_id: str, from_kw: bool):
        phrase = phrase.strip()
        if not phrase or len(phrase) < 2:
            return
        cf = phrase.casefold()
        # 跳过纯数字/单字符
        if not re.search(r"[A-Za-z]{2,}", phrase):
            return
        hit = pool.get(cf)
        if hit is None:
            # 首次出现：截取上下文（首次出现位置±50字）
            pos = text.casefold().find(cf)
            ctx_start = max(0, pos - 50)
            ctx_end = min(len(text), pos + len(phrase) + 50)
            context = text[ctx_start:ctx_end].replace("\n", " ").strip() if pos >= 0 else ""
            hit = {"phrase": phrase, "freq": 0, "sources": set(), "from_kw": False, "context": context}
            pool[cf] = hit
        hit["freq"] += text.casefold().count(cf)
        hit["sources"].add(doc_id)
        if from_kw:
            hit["from_kw"] = True

    for p in papers:
        title = (p.get("en_name") or p.get("en_title") or p.get("title") or "").strip()
        abstract = (p.get("en_abstract") or p.get("abstract") or "").strip()
        doc_id = str(p.get("document_id") or p.get("id") or f"DOC_{papers.index(p)}")
        text = (title + " " + abstract).strip()
        if not text:
            continue
        # mine_candidates 抽名词短语
        for c in mine_candidates(text):
            _add(c["phrase"], text, doc_id, from_kw=False)
        # author keywords（标注 from_kw=True）
        kws = p.get("keywords") or []
        if isinstance(kws, str):
            try:
                kws = json.loads(kws)
            except Exception:
                kws = [kws]
        for k in kws:
            kw_str = _norm_kw(k)
            if kw_str:
                _add(kw_str, text, doc_id, from_kw=True)

    # 过滤低频噪声：freq<2 且非 author keyword
    cands = [v for v in pool.values() if v["freq"] >= 2 or v["from_kw"]]
    return cands


def _stem_map(cands: List[dict]) -> Dict[str, List[str]]:
    """词干归并：返回 stem -> [phrase_cf] 索引（同 stem 的候选可能同义）。"""
    try:
        from nltk.stem import PorterStemmer
        stemmer = PorterStemmer()
    except Exception:
        return {}
    smap: Dict[str, List[str]] = {}
    for c in cands:
        cf = c["phrase"].casefold()
        # 取首词词干（多词短语用首词代表，避免 conductor/conductivity 过聚）
        first = cf.split()[0] if " " in cf else cf
        stem = stemmer.stem(first)
        smap.setdefault(stem, []).append(cf)
    return smap


def _first_letters(phrase: str) -> str:
    """取多词短语每词首字母（如 Organic Mixed Ionic-Electronic Conductor → OMIEC）。"""
    words = re.findall(r"[A-Za-z]+", phrase)
    return "".join(w[0] for w in words if w)


def generate_candidate_pairs(cands: List[dict], top_k: int = 6) -> List[Tuple[str, str, str]]:
    """规则预聚类：生成候选同义对 [(phraseA_cf, phraseB_cf, reason), ...]。"""
    by_cf = {c["phrase"].casefold(): c for c in cands}
    cfs = list(by_cf.keys())
    pairs: Set[Tuple[str, str, str]] = set()
    # 每个候选最多配 top_k 对
    per_term_count: Dict[str, int] = {}

    def _try(a: str, b: str, reason: str):
        if a == b:
            return
        key = (a, b) if a < b else (b, a)
        if key in {(p[0], p[1]) for p in pairs}:
            return
        if per_term_count.get(a, 0) >= top_k or per_term_count.get(b, 0) >= top_k:
            return
        pairs.add((key[0], key[1], reason))
        per_term_count[a] = per_term_count.get(a, 0) + 1
        per_term_count[b] = per_term_count.get(b, 0) + 1

    # 1. 缩写-全称：缩写词的首字母应匹配某多词全称的首字母序列
    for c in cands:
        cf = c["phrase"].casefold()
        phrase = c["phrase"]
        is_abbrev = bool(_ABBREV_RE.match(phrase)) and len(phrase) <= 12
        if is_abbrev:
            letters = phrase.casefold()
            for other in cands:
                ocf = other["phrase"].casefold()
                if ocf == cf or " " not in other["phrase"]:
                    continue
                if _first_letters(other["phrase"]).casefold() == letters:
                    _try(cf, ocf, "abbreviation")
        # 括号学名拆分：Wildcat (Felis silvestris) → 拆括号内外
        m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", phrase)
        if m:
            inner = m.group(1).strip().casefold()
            outer = m.group(2).strip().casefold()
            if inner in by_cf and outer in by_cf:
                _try(inner, outer, "organism")

    # 2. 词干归并（同 stem 的候选配对，限 top_k）
    smap = _stem_map(cands)
    for stem, group in smap.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                _try(group[i], group[j], "stem")

    # 3. 子串包含（a 是 b 子串且长度比 >0.5）
    for a in cfs:
        for b in cfs:
            if a == b or len(a) >= len(b):
                continue
            if a in b and len(a) / len(b) > 0.5:
                _try(a, b, "substring")

    # 4. 连字符-空格变体（去 - 后相等）
    dehyph = {}
    for c in cands:
        cf = c["phrase"].casefold()
        key = re.sub(r"[-/]", " ", cf)
        key = re.sub(r"\s+", " ", key).strip()
        dehyph.setdefault(key, []).append(cf)
    for key, group in dehyph.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                _try(group[i], group[j], "hyphen")

    return list(pairs)


def llm_judge_pairs(pairs: List[Tuple[str, str, str]], by_cf: Dict[str, dict],
                    glm, batch: int = 20, max_workers: int = 4) -> Set[Tuple[str, str]]:
    """LLM 批量同义判定，返回 same=true 的对集合。"""
    if not pairs:
        return set()
    same_pairs: Set[Tuple[str, str]] = set()
    batches = [pairs[i:i + batch] for i in range(0, len(pairs), batch)]

    def ask(b):
        listing = []
        for k, (a, b_, reason) in enumerate(b):
            ca = by_cf.get(a, {})
            cb = by_cf.get(b_, {})
            ctx_a = (ca.get("context") or "")[:80]
            ctx_b = (cb.get("context") or "")[:80]
            listing.append(
                f"[{k}] 术语A「{ca.get('phrase', a)}」(上下文: {ctx_a})\n"
                f"    术语B「{cb.get('phrase', b_)}」(上下文: {ctx_b})"
            )
        prompt = f"共{len(b)}对：\n" + "\n".join(listing)
        try:
            out = glm.chat_json(SYSP_TERM_PAIR, prompt, temperature=0.1, timeout=90.0, max_tokens=1200)
            res = []
            items = out.get("pairs", [])
            if not items and "data" in out:
                items = out["data"].get("pairs", []) if isinstance(out["data"], dict) else out["data"]
            for item in items:
                k = int(item.get("id", -1))
                if 0 <= k < len(b) and bool(item.get("same", False)):
                    a, b_, _ = b[k]
                    res.append((a, b_) if a < b_ else (b_, a))
            return res
        except Exception as e:  # noqa: BLE001
            print(f"  batch失败: {e}", flush=True)
            return []

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(ask, b) for b in batches]
        for i, fut in enumerate(as_completed(futs), 1):
            for p in fut.result():
                same_pairs.add(p)
            if i % 5 == 0 or i == len(batches):
                print(f"    裁决 {i}/{len(batches)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"  LLM判同={len(same_pairs)}对 ({time.time()-t0:.0f}s)", flush=True)
    return same_pairs


def _find(x, parent):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def build_clusters(cands: List[dict], same_pairs: Set[Tuple[str, str]],
                   min_freq: int, min_source_count: int) -> List[dict]:
    """连通分量合并 → 簇；每簇选 canonical + 统计 + type 标注 + 过滤。"""
    by_cf = {c["phrase"].casefold(): c for c in cands}
    cfs = list(by_cf.keys())
    idx = {cf: i for i, cf in enumerate(cfs)}
    parent = list(range(len(cfs)))

    for a, b in same_pairs:
        if a in idx and b in idx:
            parent[_find(idx[a], parent)] = _find(idx[b], parent)

    comp: Dict[int, List[str]] = {}
    for i, cf in enumerate(cfs):
        comp.setdefault(_find(i, parent), []).append(cf)

    clusters = []
    for cids in comp.values():
        members = [by_cf[cf] for cf in cids]
        # 簇统计
        freq = sum(m["freq"] for m in members)
        sources = set()
        for m in members:
            sources |= m["sources"]
        source_count = len(sources)
        # 过滤低频/孤立簇（单成员且非 author kw 且低频）
        if freq < min_freq and source_count < min_source_count:
            continue
        if len(members) == 1 and not members[0]["from_kw"] and freq < min_freq:
            continue
        # canonical 选择：作者关键词优先 > 最高频 > 偏好完整全称
        kw_members = [m for m in members if m["from_kw"]]
        if kw_members:
            canon_m = sorted(kw_members, key=lambda m: (-m["freq"], -len(m["phrase"]), m["phrase"]))[0]
        else:
            canon_m = sorted(members, key=lambda m: (-m["freq"], -len(m["phrase"]), m["phrase"]))[0]
        canonical = canon_m["phrase"]
        variants = [m["phrase"] for m in members]
        # type 标注
        mtypes = set()
        for m in members:
            p = m["phrase"]
            if _ABBREV_RE.match(p) and len(p) <= 12:
                mtypes.add("abbreviation")
            if re.search(r"\(([^)]+)\)", p) or _first_letters(p).casefold() in [v.casefold() for v in variants]:
                mtypes.add("organism")
        if "abbreviation" in mtypes:
            ctype = "abbreviation"
        elif "organism" in mtypes:
            ctype = "organism"
        elif len(members) == 1:
            ctype = "concept"
        else:
            ctype = "variant"
        clusters.append({
            "canonical": canonical,
            "variants": variants,
            "type": ctype,
            "freq": freq,
            "source_count": source_count,
        })
    # 按 freq 降序
    clusters.sort(key=lambda c: -c["freq"])
    return clusters


def write_domain_terms(output_path: Path, clusters: List[dict]) -> None:
    """读现有 kw_en_model.json，保留 feature_weights+few_shot，替换 domain_terms。"""
    if output_path.exists():
        try:
            model = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception:
            model = {}
    else:
        model = {}
    model["domain_terms"] = clusters
    output_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="构建 en-keyword 术语库归一化 domain_terms")
    ap.add_argument("--input", required=True, help="批量 {摘要,关键词} JSON 文件")
    ap.add_argument("--output", default=str(PROJECT_ROOT / "rules" / "keyword_recognition" / "kw_en_model.json"),
                    help="输出 kw_en_model.json 路径")
    ap.add_argument("--min-freq", type=int, default=2, help="簇最低总频次")
    ap.add_argument("--min-source-count", type=int, default=2, help="簇最低涉及文献数")
    ap.add_argument("--batch-size", type=int, default=20, help="LLM 每批判定对数")
    ap.add_argument("--top-k", type=int, default=6, help="每个候选术语最多配候选对数")
    ap.add_argument("--max-workers", type=int, default=4, help="LLM 并发数")
    args = ap.parse_args()

    from infrastructure.llm.glm_client import glm_client

    papers = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(f"载入 {len(papers)} 篇文献", flush=True)

    # 1. 候选池
    cands = build_candidate_pool(papers)
    print(f"候选术语池 {len(cands)}（from_kw={sum(1 for c in cands if c['from_kw'])}）", flush=True)

    # 2. 规则预聚类
    pairs = generate_candidate_pairs(cands, top_k=args.top_k)
    print(f"规则预聚类候选对 {len(pairs)}", flush=True)

    # 3. LLM 同义判定
    by_cf = {c["phrase"].casefold(): c for c in cands}
    same_pairs = llm_judge_pairs(pairs, by_cf, glm_client, batch=args.batch_size, max_workers=args.max_workers)

    # 4. 连通分量 + canonical
    clusters = build_clusters(cands, same_pairs, args.min_freq, args.min_source_count)
    print(f"产出 {len(clusters)} 簇（abbreviation={sum(1 for c in clusters if c['type']=='abbreviation')}"
          f" organism={sum(1 for c in clusters if c['type']=='organism')}"
          f" concept={sum(1 for c in clusters if c['type']=='concept')}"
          f" variant={sum(1 for c in clusters if c['type']=='variant')}）", flush=True)

    # 5. 输出
    out = Path(args.output)
    write_domain_terms(out, clusters)
    print(f"写入 {out}（domain_terms={len(clusters)} 簇）", flush=True)
    # 打印 top10 供抽检
    print("\n=== top10 簇 ===", flush=True)
    for c in clusters[:10]:
        print(f"  [{c['type']}] canon={c['canonical']!r} variants={c['variants']} freq={c['freq']} src={c['source_count']}", flush=True)


if __name__ == "__main__":
    main()
