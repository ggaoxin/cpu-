"""用户上传资源的 LLM 辅助结构整理（上传时一次性转换，非请求热路径）。

触发条件：确定性归一化（normalize.py）解析出 0 条有效数据——包括 JSON 语法
损坏（尾逗号/单引号等，GLM 擅长修复）与结构/字段名不匹配。

护栏（与确定性层的关系）：
- 仅行型资源字段（ROW_FIELD_CONFIG）触发；配置型字段不送模型；
- 大小/条数上限（settings 可配），超限直接放弃，维持确定性报错；
- 模型输出必须重过 normalize_resource_document 确定性校验（≥1 条）才算成功，
  绝不盲信模型输出；失败时调用方沿用原报错文案（附加"已尝试大模型整理"）。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.resources.normalize import ROW_FIELD_CONFIG, normalize_resource_document

logger = logging.getLogger(__name__)


def _build_prompts(text: str, *, field: str) -> Tuple[str, str]:
    config = ROW_FIELD_CONFIG.get(field) or {}
    expect = config.get("expect") or "JSON 数组"
    system = (
        "你是数据结构转换器。把用户提供的 JSON 文件内容转换为标准结构，"
        "只输出转换后的 JSON（一个数组），不要输出任何解释、注释或代码块标记。\n"
        f"目标标准结构：{expect}\n"
        "规则：保留全部原始条目，不编造、不删减数据；字段名映射到标准字段名；"
        "外层包装对象要拆开取内部数组；无法对应到任何标准字段的额外字段原样保留。"
    )
    user = f"请转换以下 JSON 文件内容：\n{text}"
    return system, user


def _extract_json_payload(raw: str) -> Optional[Any]:
    """剥离 ```json 围栏/空白后解析；失败返回 None。"""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


def maybe_llm_normalize(
    text: str,
    *,
    field: str,
    max_bytes: int,
    max_rows: int,
) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """尝试用 GLM 把非标准 JSON 整理为标准行结构。

    返回 (rows, note)：
    - rows 非 None：整理成功（已过确定性校验），note='glm'
    - rows None + note：'disabled'/'oversize'/'overrows'/'parse_failed'/'empty'/'error'
    """
    if field not in ROW_FIELD_CONFIG:
        return None, "unsupported_field"
    encoded_len = len(text.encode("utf-8"))
    if encoded_len > max_bytes:
        return None, "oversize"
    # 条数上限：能解析出顶层数组时预判条数，避免把超大行集送进模型
    try:
        peek = json.loads(text)
        if isinstance(peek, list) and len(peek) > max_rows:
            return None, "overrows"
    except (json.JSONDecodeError, ValueError):
        pass  # 语法损坏的文件没有条数可判，靠 max_bytes 兜底
    try:
        from infrastructure.llm.glm_client import glm_client
        system, user = _build_prompts(text, field=field)
        raw = glm_client.chat(system, user, temperature=0.0, response_json=True, max_tokens=8192)
    except Exception as exc:  # noqa: BLE001 - 模型/网络异常回落确定性报错
        logger.warning("资源大模型整理调用失败（%s）：%s", field, exc)
        return None, "error"
    if not isinstance(raw, str) or not raw.strip():
        return None, "empty"
    parsed = _extract_json_payload(raw)
    if parsed is None:
        return None, "parse_failed"
    rows = normalize_resource_document(parsed, field=field)
    if not rows:
        return None, "invalid_after_llm"
    logger.info("资源大模型整理成功：%s → %d 条标准行", field, len(rows))
    return rows, "glm"
