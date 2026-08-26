"""GLM 大模型客户端。

采用 OpenAI 兼容协议调用智谱 GLM-5.2。所有功能点统一通过本客户端
访问大模型，模型名、密钥、温度等由 config/settings 统一管理。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import httpx
import openai
from openai import OpenAI

from config.settings import settings

logger = logging.getLogger(__name__)


class GLMClient:
    """GLM 大模型客户端封装。"""

    def __init__(self) -> None:
        # 未配置密钥时也允许构造（服务可启动、前端/数据库可联调）；
        # 真正依赖模型的功能在 chat() 中由 llm_configured 守卫返回明确错误。
        api_key = settings.GLM_API_KEY or "not-configured"
        self._client = OpenAI(
            api_key=api_key,
            base_url=settings.GLM_BASE_URL,
            timeout=httpx.Timeout(60.0, connect=settings.GLM_CONNECT_TIMEOUT_SECONDS),
            max_retries=0,  # 不重试：个别摘要会让 GLM 长时挂起，重试只加倍等待
        )
        self.model = settings.GLM_MODEL
        self.temperature = settings.GLM_TEMPERATURE

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: Optional[float] = None,
        response_json: bool = True,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """调用对话接口，返回模型文本内容。

        Args:
            system_prompt: 系统提示词（含规则库内容）。
            user_prompt:   用户输入（含待处理文本）。
            temperature:   采样温度，默认使用全局配置。
            response_json: 是否强制 JSON 输出。
            timeout:       单次请求超时（秒），默认用客户端配置。
            max_tokens:    输出最大 token 数（防 runaway 生成导致挂起）。
        Returns:
            模型返回的文本内容。
        """
        if not settings.llm_configured:
            raise RuntimeError(
                "当前功能需要大模型，但尚未配置 GLM_API_KEY；请在 config/.env 中配置后重试。"
            )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}
        if timeout is not None:
            # Keep the task-specific read timeout while failing fast when the
            # configured GLM endpoint itself cannot be reached.
            kwargs["timeout"] = httpx.Timeout(
                timeout,
                connect=min(settings.GLM_CONNECT_TIMEOUT_SECONDS, timeout),
            )
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        # GLM-5.2 是推理模型，reasoning_tokens 会让响应极慢甚至 max_tokens 截断致空内容。
        # 分类/抽取等结构化任务无需推理，关闭后直接出 JSON，快且稳。
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        logger.info("GLM 调用 model=%s, json=%s", self.model, response_json)
        # 429 限流时温和退避重试（并发场景偶发限流，重试可消化避免单篇失败拖累整体）
        import time as _time
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content or ""
                return content
            except openai.RateLimitError as exc:
                last_exc = exc
                if attempt < 2:
                    wait = 1.0 * (attempt + 1)  # 1s, 2s
                    logger.warning("GLM 限流(429)，%ds 后重试 %d/2", wait, attempt + 1)
                    _time.sleep(wait)
                    continue
                raise RuntimeError(
                    f"[限流429] GLM接口限流，请降低 GLM_MAX_CONCURRENCY(当前{settings.GLM_MAX_CONCURRENCY})或稍后重试"
                ) from exc
            except openai.APITimeoutError as exc:
                raise RuntimeError("[超时] GLM接口请求超时，可能模型繁忙或 timeout 过小") from exc
            except openai.APIConnectionError as exc:
                raise RuntimeError(
                    f"[网络] GLM接口连接失败，请检查网络或 GLM_BASE_URL({settings.GLM_BASE_URL})"
                ) from exc
            except openai.BadRequestError as exc:
                raise RuntimeError(f"[请求错误400] GLM拒绝请求：{exc}") from exc
            except openai.InternalServerError as exc:
                raise RuntimeError(f"[服务端5xx] GLM服务内部错误：{exc}") from exc
            except openai.APIStatusError as exc:
                raise RuntimeError(f"[接口错误{exc.status_code}] GLM返回异常：{exc}") from exc
            except openai.APIError as exc:
                raise RuntimeError(f"[GLM错误] {exc}") from exc
        raise RuntimeError(f"[GLM错误] 调用失败：{last_exc}") from last_exc

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """调用对话接口并解析为 JSON 字典；解析失败抛 ValueError。

        - GLM 偶发返回空 content（200 响应但内容为空），检测到空内容自动重试最多 2 次。
        - GLM 偶发因 max_tokens 截断返回非合法 JSON：先尝试 _repair_json 修复（补全
          未闭合的字符串/括号），仍失败则增大 max_tokens 重试一次。
        """
        import time as _time
        raw = ""
        for attempt in range(3):
            raw = self.chat(system_prompt, user_prompt, temperature=temperature,
                            response_json=True, timeout=timeout, max_tokens=max_tokens)
            if raw and raw.strip():
                break
            logger.warning("GLM 返回空内容，重试 %d/2", attempt + 1)
            _time.sleep(1.0 * (attempt + 1))
        # 1. 直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # 2. 修复截断的 JSON
        try:
            repaired = self._repair_json(raw)
            logger.warning("GLM JSON 疑似截断，已补全修复后解析成功")
            return repaired
        except json.JSONDecodeError:
            pass
        # 3. 修复失败 → 增大 max_tokens 重试一次
        retry_tokens = (max_tokens * 2) if max_tokens else 2000
        logger.warning("GLM JSON 解析失败，增大 max_tokens=%d 重试一次", retry_tokens)
        raw2 = self.chat(system_prompt, user_prompt, temperature=temperature,
                         response_json=True, timeout=timeout, max_tokens=retry_tokens)
        if raw2 and raw2.strip():
            try:
                return json.loads(raw2)
            except json.JSONDecodeError:
                try:
                    return self._repair_json(raw2)
                except json.JSONDecodeError:
                    pass
        logger.error("GLM 返回非合法 JSON：%s", raw[:500])
        raise ValueError("大模型返回无法解析为 JSON（已尝试修复与重试）")

    @staticmethod
    def _repair_json(raw: str) -> Dict[str, Any]:
        """修复被 max_tokens 截断的 JSON：闭合未配对的字符串与括号。

        扫描时跳过字符串内部的括号，末尾按需补 " / ] / }。仅对结构层截断有效。
        """
        s = raw.strip()
        opens: list[str] = []
        in_str = False
        escape = False
        for ch in s:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch in "{[":
                opens.append(ch)
            elif ch == "}" and opens and opens[-1] == "{":
                opens.pop()
            elif ch == "]" and opens and opens[-1] == "[":
                opens.pop()
        suffix = ""
        if in_str:
            suffix += '"'
        for ch in reversed(opens):
            suffix += "]" if ch == "[" else "}"
        if not suffix:
            raise json.JSONDecodeError("无需补全但仍非法", s, 0)
        return json.loads(s + suffix)


# 单例
glm_client = GLMClient()
