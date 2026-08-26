"""确定性中文分句器。

按标点 。！？；及换行切分，处理引号内句号、省略号、编号(1)(2)等边界情况。
分句结果用于：① 把摘要切成句子单元；② 句子↔语步段对齐做评测。
"""
from __future__ import annotations

import re
from typing import List

# 句末标点（中文+英文）
_SENT_END = "。！？!?；;…\n"
# 不切分的“句内”括号/引号配对（简化处理）
_QUOTE_PAIRS = [("“", "”"), ("‘", "’"), ("(", ")"), ("（", "）"), ("《", "》")]

# 连续句末标点合并（如 。。。 或 ！？）
_MULTI_END = re.compile(r"[。！？!?；;…\n]+")


def segment(text: str) -> List[str]:
    """把文本切分为句子列表（保留原文，不修改字符）。

    规则：
    - 遇句末标点切分；
    - 标点前的编号标记如 (1)/(2)/① 不单独成句（已并入前句或后句，靠句末标点切分自然处理）；
    - 连续句末标点合并为一次切分；
    - 空白句丢弃。
    """
    if not text or not text.strip():
        return []

    sentences: List[str] = []
    buf: List[str] = []
    i = 0
    n = len(text)
    quote_depth = 0
    while i < n:
        ch = text[i]
        buf.append(ch)

        # 简单引号深度跟踪：遇到引号/括号开闭
        for op, cl in _QUOTE_PAIRS:
            if ch == op:
                quote_depth += 1
            elif ch == cl:
                quote_depth = max(0, quote_depth - 1)

        # 句末标点：且不在引号内部时切分
        if ch in _SENT_END and quote_depth == 0:
            # 合并连续句末标点
            j = i + 1
            while j < n and text[j] in _SENT_END:
                buf.append(text[j])
                # 引号跟踪同样作用于这些标点
                for op, cl in _QUOTE_PAIRS:
                    if text[j] == op:
                        quote_depth += 1
                    elif text[j] == cl:
                        quote_depth = max(0, quote_depth - 1)
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


def assign_sentences_to_spans(sentences: List[str], spans: dict) -> List[str]:
    """把每个句子归到所属语步段。

    优先用“包含”判定（句子是某 span 的子串 → 归该 span，因 spans 划分原文，
    至多一个 span 包含它）；若句子跨越 span 边界，回退到最长公共子串重叠最大者。

    spans: {"研究背景": "...", ...}（允许空串）
    返回：与 sentences 等长的 move 标签列表；无任何重叠时记为 ""。
    """
    labels: List[str] = []
    for sent in sentences:
        sent_clean = sent.strip()
        # 1) 包含判定
        contained_in = [m for m, sp in spans.items() if sp and sent_clean and sent_clean in sp]
        if len(contained_in) == 1:
            labels.append(contained_in[0])
            continue
        if len(contained_in) > 1:
            # 同时被多段包含（短句），取最长 span 者更可靠
            labels.append(max(contained_in, key=lambda m: len(spans[m])))
            continue
        # 2) 回退：最长公共子串重叠
        best_move = ""
        best_overlap = 0
        for move, span in spans.items():
            if not span:
                continue
            ov = _char_overlap(sent_clean, span)
            if ov > best_overlap:
                best_overlap = ov
                best_move = move
        labels.append(best_move)
    return labels


def _char_overlap(a: str, b: str) -> int:
    """两字符串的最长公共子串长度（近似重叠度，够用于归属判定）。"""
    if not a or not b:
        return 0
    la, lb = len(a), len(b)
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    # dp 滚动数组求最长公共子串
    prev = [0] * (lb + 1)
    best = 0
    for i in range(1, la + 1):
        cur = [0] * (lb + 1)
        ai = a[i - 1]
        for j in range(1, lb + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


if __name__ == "__main__":
    t = "第一句。第二句！第三句？"
    print(segment(t))
