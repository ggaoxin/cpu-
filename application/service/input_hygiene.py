"""展示字段输入卫生（2026-11-24 漏洞修复 V2 第 1 档）。

漏洞报告指出：全部写端点对 HTML 零过滤，XSS payload 原样入库并在 GET 回显。
前端渲染层虽有转义（escapeHtml/renderTextWithMath），但名称/标题类展示字段
在业务上本不应含 HTML 标签——在入库前直接拒绝，把"存储型注入面"从源头收敛，
同时保护下游（导出 CSV、共享下拉、LLM 管道）不被污染。

判定只匹配 HTML 元素形态（<img ...>、</svg>、<svg onload=...>），
普通文本的 "a < b"、"x < 100"（< 后不是字母/斜杠）不会误伤。
"""
from __future__ import annotations

import re

_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(?:\s[^<>]*)?/?>")


def contains_html_tag(value) -> bool:
    """字符串是否含 HTML 元素形态（用于入库前的拒绝判定）。"""
    return bool(_HTML_TAG_RE.search(str(value or "")))


def html_tag_error(label: str) -> str:
    """拒绝时的业务错误消息（42201 口径）。"""
    return f"{label} 不允许包含 HTML 标签（名称/标题等展示字段为纯文本）"


def strip_html_tags(value: str) -> str:
    """剥离 HTML 元素形态（用于无法走报错路径的展示字段，如上传文件名）。"""
    return _HTML_TAG_RE.sub("", str(value or ""))
