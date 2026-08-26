"""确定性中文关键词候选挖掘器（可插拔候选源，数据多了可加 PMI 模块）。

用 jieba 词性标注抽取"术语型"名词短语候选，并计算特征：
  in_title（是否在标题中出现）、freq（在摘要中的频次）、position（首次出现位置，越早越高）、length。
候选与 LLM 抽取结果合并后由后置引擎打分排序。

设计为无 LLM、可复现，便于在训练集上校准特征权重、在验证集测净收益。
"""
from __future__ import annotations

import re
from typing import Dict, List

import jieba
import jieba.posseg as pseg
from config.settings import settings

# 术语型词性：名词类 + 名动词 + 英文 + 其他专名
TERM_POS = {"n", "nr", "ns", "nt", "nz", "vn", "eng", "an", "nl", "ng"}
# 连接词性：允许出现在术语中间的（如"的"一般断开，但"配电网"等整体词 jieba 已切好）
_LINK = {"n", "nr", "ns", "nt", "nz", "vn", "eng", "an", "nl", "ng", "x"}

_PUNCT = "，。、；：！？（）()【】[]《》\"' \n\t,.:;!?—-"

# 垃圾过滤：PDF 抽取常混入图片标记(images/、text_image)、期刊/出版商信息
# (出版社、文摘编著、JOURNAL、学报……)、参考文献条目等，与主题无关却高频，挤占候选槽位。
# 用正则一次性剔除，让真正的术语上浮。
_JUNK_RE = re.compile(
    r"[/\\_]|出版社|文摘|编著|JOURNAL|学报|abstract|introduction|"
    r"images?|text_image|figure|fig\.?|table|http|关键词|references?|"
    r"copyright|rights|received|accepted|编辑部|学术期刊|学术研究|稿件|"
    r"书刊|cnki|定稿|电子杂志|网络连续型|纸质期刊|法定计量|统一规范语言|"
    r"新闻出|产学研|自然科学基金|杂志社|出版物"
)


def _is_junk(phrase: str) -> bool:
    """候选是否为垃圾（图片标记/出版商/参考文献/英文常见词）。"""
    if _JUNK_RE.search(phrase):
        return True
    # 英文候选：仅保留全大写缩写（LSTM/PEER/WGCNA 等技术缩写），
    # 其余英文词（on/in/motion/ground 及 PDF 无空格粘连成的 groundmotion/basedon/Journalof）
    # 在中文文献里是噪声，丢掉；英文术语由 en-keyword 工具处理，LLM 亦可从原文自行摘取。
    if phrase.isascii():
        if not (phrase.isupper() and 2 <= len(phrase) <= 8):
            return True
    return False


def mine_candidates(title: str, abstract: str, max_len: int = 12) -> List[Dict]:
    """从标题+正文挖名词短语候选，返回 [{phrase, in_title, freq, position, length}]。

    abstract 实参为全文正文（semantic_service 传入 mine_source），挖掘面向全文以提升
    低频但核心的术语召回（如 ch4 反应谱全文 23 次，仅看前 8000 字只见 2-4 次会被埋）。
    """
    title = title or ""
    text = (title + "。" + (abstract or ""))
    words = list(pseg.cut(text))
    # 抽取最大名词短语块
    candidates: Dict[str, Dict] = {}
    i = 0
    n = len(words)
    while i < n:
        w = words[i]
        if w.flag in TERM_POS and w.word.strip() and not _is_punct(w.word):
            # 向后扩展：连续术语词性（含单字名词）组成短语
            j = i
            buf = []
            while j < n and not _is_punct(words[j].word):
                fl = words[j].flag
                # 允许单字 v 进短语：jieba 把"谱/测/算"等技术性名词语素误标为动词(v)
                # （因"谱写"等动词用法），致"反应谱"在"加速度反应谱"处被切断——
                # 加速度(n)+反应(vn)+谱(v←误标) 只挖出"加速度反应"，反应谱丢失。
                # 真(多字)动词(进行/采用)不受影响，限制单字避免误并多字动词。
                ok = fl in _LINK or (fl == "v" and len(words[j].word) == 1)
                if not ok:
                    break
                buf.append(words[j].word)
                j += 1
            phrase = "".join(buf).strip()
            if phrase and 2 <= len(phrase) <= max_len and not _is_junk(phrase):
                _add(candidates, phrase, title, text)
            i = j if j > i else i + 1
        else:
            i += 1
    vals = list(candidates.values())
    # 子串去膨胀：text.count 是字符子串计数，"地震"会把"地震动/地震动记录"里的出现也计入，
    # 虚高频次霸榜挤掉真术语。规则——短候选 S 若被某更长候选 L 完全包含(字符子串)且
    # S.freq ≤ L.freq*1.5，则 S 多半只是 L 的碎片而非独立术语，丢弃。
    # 反应谱(freq23)被加速度反应谱(freq12)包含但 23 > 18 → 保留(它才是独立复现的核心)。
    fmap = {c["phrase"]: c["freq"] for c in vals}
    vals = [
        c for c in vals
        if not any(p != c["phrase"] and c["phrase"] in p and c["freq"] <= fmap[p] * 1.5
                   for p in fmap)
    ]
    return sorted(vals, key=lambda c: (-c["freq"], c["position"]))


def _is_punct(w: str) -> bool:
    return all(ch in _PUNCT for ch in w) if w else True


def _add(store: Dict, phrase: str, title: str, text: str):
    if phrase in store:
        return
    store[phrase] = {
        "phrase": phrase,
        "in_title": phrase in title,
        "freq": text.count(phrase),
        "position": text.find(phrase) / max(len(text), 1),
        "length": len(phrase),
    }


def score_candidates(cands: List[Dict], weights: Dict[str, float]) -> List[Dict]:
    """按特征权重打分：score = w_in_title*in_title + w_freq*norm(freq) + w_pos*(1-position) + w_len*len_pref。"""
    if not cands:
        return cands
    max_freq = max(c["freq"] for c in cands) or 1
    w = weights or {"in_title": 1.0, "freq": 0.5, "position": 0.5, "length": 0.2}
    for c in cands:
        c["score"] = (
            w.get("in_title", 0) * (1.0 if c["in_title"] else 0.0)
            + w.get("freq", 0) * (c["freq"] / max_freq)
            + w.get("position", 0) * (1.0 - c["position"])
            + w.get("length", 0) * min(c["length"] / 6.0, 1.0)
        )
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands


if __name__ == "__main__":
    import json
    papers = json.load(open(str(settings.DATA_DIR / "random_50_chinese_papers.json"), encoding="utf-8"))
    # 抽 5 篇看候选是否覆盖 author keyword
    for p in papers[:5]:
        gold = [k["ch_name"] for k in p["keywords"] if k["ch_name"]]
        cands = mine_candidates(p["ch_name"], p["ch_abstract"])
        cand_phrases = [c["phrase"] for c in cands]
        hit = [g for g in gold if any(g == c or g in c or c in g for c in cand_phrases)]
        print(f"\n== {p['ch_name'][:30]} ==")
        print(f"  gold({len(gold)}): {gold}")
        print(f"  候选数: {len(cands)}  命中gold: {hit}")
        print(f"  top8候选: {cand_phrases[:8]}")
