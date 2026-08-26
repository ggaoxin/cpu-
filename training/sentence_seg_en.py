"""英文确定性分句器（缩写保护）。

按 . ! ? 切分，但不切缩写中的点（e.g. / i.e. / et al. / Fig. / vs. / etc. / No. /
approx. / Mr. / Dr.）及数字小数点。assign_sentences_to_spans 与 _char_overlap 复用中文版（语言无关）。
"""
from __future__ import annotations

import re
from typing import List

from training.sentence_seg import assign_sentences_to_spans, _char_overlap  # noqa: F401

# 缩写白名单（点号前为这些词时不切）。小写匹配。
_ABBREV = {
    "e.g", "i.e", "et al", "fig", "figs", "tab", "tabs", "vs", "etc", "no",
    "approx", "mr", "mrs", "dr", "prof", "st", "mt", "jr", "sr", "ph.d",
    "al", "ref", "refs", "eq", "eqs", "sec", "vol", "pp", "p", "ch",
}
# 句末标点
_SENT_END = ".!?"

# 数字小数点（如 3.14）不切：仅 digit.digit 才算真小数
_NUM_DOT = re.compile(r"\d\.\d")


def segment(text: str) -> List[str]:
    """把英文文本切分为句子列表（保留原文，缩写中的点不切分）。"""
    if not text or not text.strip():
        return []
    sentences: List[str] = []
    buf: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        buf.append(ch)
        if ch in _SENT_END:
            # 判断这个点/!? 是否为真正句末
            is_end = True
            if ch == ".":
                # 向前看：buf 末尾的"词."是否为缩写
                tail = "".join(buf).rstrip()
                # 取点号前的最后一个 token（字母序列）
                m = re.search(r"([A-Za-z][A-Za-z\.]*)\.$", tail)
                if m:
                    word = m.group(1).lower().rstrip(".")
                    if word in _ABBREV:
                        is_end = False
                # 数字小数点不切（digit.digit）
                if is_end:
                    # 看 buf 末尾 + 后续字符是否构成 digit.digit
                    look = "".join(buf) + (text[i + 1] if i + 1 < n else "")
                    if _NUM_DOT.search(look[-4:]):
                        is_end = False
                # 单字母点（如 "A."）通常为缩写，不切
                if is_end and m and len(m.group(1)) == 1:
                    is_end = False
            # 向后看：点后接小写字母/逗号，多半不是句末
            if is_end and i + 1 < n:
                j = i + 1
                # 跳过空格
                while j < n and text[j] == " ":
                    j += 1
                if j < n and text[j].islower():
                    # 后接小写 → 大概率非句末（除非前词是强句末信号）。保守不切。
                    # 但 ! ? 总是句末，仅对 . 应用
                    if ch == ".":
                        is_end = False
            if is_end:
                # 合并连续句末标点
                j = i + 1
                while j < n and text[j] in _SENT_END:
                    buf.append(text[j])
                    j += 1
                sent = "".join(buf).strip()
                if sent:
                    sentences.append(sent)
                buf = []
                i = j
                continue
        i += 1
    tail = "".join(buf).strip()
    if tail:
        sentences.append(tail)
    return sentences


if __name__ == "__main__":
    t = ("Fundamental understanding remains challenging. In this study, we investigate "
         "CsCu2I3 by employing first principles calculations, e.g. self-consistent phonon. "
         "Our results show F1=0.362 Wm-1. Importantly, we find anomalous trend (see Fig. 1). "
         "Our study paves the way for designing materials.")
    for s in segment(t):
        print("•", s)
