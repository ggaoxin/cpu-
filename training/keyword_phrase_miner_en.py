"""确定性英文关键词候选挖掘器（nltk POS，可插拔候选源）。

用 nltk 词性标注抽取名词短语候选（NN/NNS/JJ+NN 等），并计算特征：
  freq（在文中的频次）、position（首次出现位置，越早越高）、length。
面向全文/摘要/任意英文文本（参数名 abstract 历史遗留，实际可传全文/摘要）。
候选与 LLM 抽取结果合并后由后置引擎打分排序。
"""
from __future__ import annotations

import re
from typing import Dict, List
from config.settings import settings

# 名词短语允许的 POS：名词、形容词、过去分词（作修饰）、数词
TERM_POS = {"NN", "NNS", "NNP", "NNPS", "JJ", "VBN", "CD"}

# 短语首尾需剥离的句法功能词/句首谓语动词。只删首尾、不动中间，
# 避免把 "case study" 这类中间含功能词的合法术语误伤。
_STRIP_WORDS = {
    # 冠词/限定词
    "a", "an", "the", "this", "these", "that", "those", "such", "any", "some",
    "all", "both", "each", "every", "either", "neither", "another", "other",
    # 介词
    "of", "for", "to", "in", "on", "with", "without", "by", "from", "as", "via",
    "through", "into", "onto", "upon", "over", "under", "between", "among",
    "during", "before", "after", "than", "across", "along", "around", "behind",
    "beyond", "within", "against", "toward", "towards",
    # 连词
    "and", "or", "but", "nor", "so", "yet", "while", "whereas", "although",
    "though", "because", "since", "until", "whether", "if", "unless",
    # 代词/疑问词
    "which", "who", "whom", "whose", "what", "where", "when", "how", "why",
    "we", "our", "us", "they", "them", "their", "its", "it", "his", "her",
    # 系动词/助动词
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does", "did",
    "have", "has", "had", "will", "would", "can", "could", "may", "might",
    "shall", "should", "must",
    # 分词/副词粘连
    "using", "used", "based", "according", "respectively", "herein", "thereof",
    "also", "not", "only", "very", "more", "most", "less", "least",
    "however", "therefore", "thus", "hence", "moreover", "furthermore",
    "additionally", "finally", "well", "here", "there", "now", "then",
    # 科技摘要高频句首谓语动词（nltk 偶把谓语误标进短语，首尾出现时剥离）
    "proposes", "proposed", "propose", "presents", "presented", "present",
    "shows", "shown", "show", "demonstrates", "demonstrated", "demonstrate",
    "reports", "reported", "report", "describes", "described", "describe",
    "evaluates", "evaluated", "evaluate", "investigates", "investigated",
    "investigate", "studies", "studied", "study", "aims", "aimed",
    "achieves", "achieved", "achieve", "obtains", "obtained", "obtain",
    "found", "find", "reveals", "revealed", "reveal", "includes", "included",
    "include", "involves", "involved", "involve", "consists", "consisted",
    "consist", "comprises", "comprised", "comprise", "contains", "contained",
    "contain", "suggests", "suggested", "suggest", "provides", "provided",
    "provide", "offers", "offered", "offer", "develops", "developed", "develop",
    "designs", "designed", "design", "introduces", "introduced", "introduce",
    "applies", "applied", "apply", "employs", "employed", "employ",
    "utilizes", "utilized", "utilize", "adopts", "adopted", "adopt",
    "exhibits", "exhibited", "exhibit", "yields", "yielded", "yield",
}

_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


def mine_candidates(abstract: str, max_len: int = 6) -> List[Dict]:
    """从英文文本挖名词短语候选，返回 [{phrase, freq, position, length}]。

    对 POS 短语做首尾功能词剥离与 /- 复合术语合并，避免核心术语被
    句法粘连（如 "tandem solar cells as"）或拆碎（如 perovskite / TOPCon）。
    """
    from nltk import pos_tag, word_tokenize
    abstract = (abstract or "").strip()
    if not abstract:
        return []
    try:
        tokens = word_tokenize(abstract)
        tokens = _merge_compound_tokens(tokens)
        tagged = pos_tag(tokens)
    except Exception:  # noqa: BLE001
        return _regex_fallback(abstract)

    candidates: Dict[str, Dict] = {}
    i = 0
    n = len(tagged)
    while i < n:
        if tagged[i][1] in TERM_POS and _is_word(tagged[i][0]):
            j = i
            buf = []
            while j < n and tagged[j][1] in TERM_POS and _is_word(tagged[j][0]):
                buf.append(tagged[j][0])
                j += 1
            phrase = _strip_phrase(" ".join(buf))
            # 过滤纯数字/单 token 过短
            if phrase and 1 <= len(phrase.split()) <= max_len and re.search(r"[A-Za-z]", phrase):
                _add(candidates, phrase, abstract)
            i = j if j > i else i + 1
        else:
            i += 1
    return sorted(candidates.values(), key=lambda c: (-c["freq"], c["position"]))


def _merge_compound_tokens(tokens: List[str]) -> List[str]:
    """合并被 / 或 - 拆开的复合术语 token（保留分隔符）。

    word_tokenize 会把 "perovskite/TOPCon" 切成 ["perovskite","/","TOPCon"]、
    "TiO2-Si" 切成 ["TiO2","-","Si"]，导致复合术语被 POS 断点拆碎。这里把
    形如 word sep word [sep word ...] 的相邻片段重新合并成单个 token，
    使 pos_tag 能把整个复合术语当整体标注。
    """
    merged: List[str] = []
    k = 0
    n = len(tokens)
    while k < n:
        tok = tokens[k]
        if (k + 2 < n and _WORD_RE.match(tok)
                and tokens[k + 1] in ("/", "-")
                and _WORD_RE.match(tokens[k + 2])):
            parts = [tok]
            k += 1  # 指向首个 sep
            while k + 1 < n and tokens[k] in ("/", "-") and _WORD_RE.match(tokens[k + 1]):
                parts.append(tokens[k])       # sep
                parts.append(tokens[k + 1])   # next word
                k += 2
            merged.append("".join(parts))
        else:
            merged.append(tok)
            k += 1
    return merged


def _strip_phrase(phrase: str) -> str:
    """剥离短语首尾的句法功能词/谓语动词，只动首尾不动中间。"""
    words = phrase.split()
    if not words:
        return ""
    changed = True
    while changed and len(words) > 1:
        changed = False
        if words[0].lower() in _STRIP_WORDS:
            words.pop(0)
            changed = True
        if words and words[-1].lower() in _STRIP_WORDS:
            words.pop()
            changed = True
    # 单 token 若是纯功能词/谓语则丢弃
    if len(words) == 1 and words[0].lower() in _STRIP_WORDS:
        return ""
    return " ".join(words)


def _is_word(w: str) -> bool:
    return bool(w) and not all(ch in ".,;:!?()[]\"'`/-" for ch in w)


def _add(store: Dict, phrase: str, text: str):
    key = phrase.lower()
    if key in store:
        return
    store[key] = {
        "phrase": phrase,
        "freq": text.lower().count(key),
        "position": text.lower().find(key) / max(len(text), 1),
        "length": len(phrase.split()),
    }


def _regex_fallback(text: str) -> List[Dict]:
    """nltk 不可用时的兜底：抽 n-gram 短语并剥离首尾功能词。"""
    store: Dict[str, Dict] = {}
    for m in re.finditer(r"[A-Za-z][A-Za-z\-]+(?: [A-Za-z\-]+){0,3}", text):
        phrase = _strip_phrase(m.group(0).strip())
        if phrase and 2 <= len(phrase) <= 50 and re.search(r"[A-Za-z]", phrase):
            _add(store, phrase, text)
    return sorted(store.values(), key=lambda c: (-c["freq"], c["position"]))


def score_candidates(cands: List[Dict], weights: Dict[str, float]) -> List[Dict]:
    if not cands:
        return cands
    max_freq = max(c["freq"] for c in cands) or 1
    w = weights or {"freq": 0.6, "position": 0.5, "length": 0.3}
    for c in cands:
        c["score"] = (
            w.get("freq", 0) * (c["freq"] / max_freq)
            + w.get("position", 0) * (1.0 - c["position"])
            + w.get("length", 0) * (1.0 / max(c["length"], 1))
        )
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands


if __name__ == "__main__":
    import json
    papers = json.load(open(str(settings.DATA_DIR / "en_keyword_50.json"), encoding="utf-8"))
    for p in papers[:5]:
        kw = p["keywords"] if isinstance(p["keywords"], list) else json.loads(p["keywords"])
        gold = [k.get("en_name", "") for k in kw if k.get("en_name")]
        cands = mine_candidates(p["en_abstract"])
        cand_phrases = [c["phrase"] for c in cands]
        hit = [g for g in gold if any(g.lower() == c.lower() or g.lower() in c.lower() or c.lower() in g.lower() for c in cand_phrases)]
        print(f"\n== {p['en_abstract'][:60]}")
        print(f"  gold({len(gold)}): {gold}")
        print(f"  候选数:{len(cands)} 命中:{len(hit)}/{len(gold)} top8:{cand_phrases[:8]}")
