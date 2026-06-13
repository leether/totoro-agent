"""Totoro Provider — 基于 httpx 的纯 Python 实现，无 pydantic_core 依赖。

LongCat API 兼容 Anthropic 的 /v1/messages 接口格式，直接 HTTP 调用。

设计决策记录（why not SDK）:
  - 绕开 anthropic SDK → pydantic → pydantic_core 的依赖链
  - 避免 macOS 上 pydantic_core 的 codesign 问题
  - 代价：无自动类型校验 / 无内置重试 / 无 SDK 级别封装
  - 缓解：TypedDict + validate_payload（类型）+ 内置重试（健壮性）
  - 切回 SDK 的时机：多模型支持 / 团队 >5人 / codesign 已修复
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

from providers.base import (
    ChatResponse,
    StreamEvent,
    TokenUsage,
    ToolCall,
    ToolCallDefinition,
    convert_openai_to_anthropic_messages,
    validate_payload,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# API 版本管理——升级时只改这一处
ANTHROPIC_API_VERSION = "2023-06-01"

# 客户端身份标识——让 LongCat 端能识别调用方（限流 / 统计 / 排查）
CLIENT_NAME = "Totoro-Agent"
CLIENT_VERSION = "0.1.0"


class TotoroProvider:
    """Totoro 提供者 — 兼容 Anthropic /v1/messages API。

    增强功能:
      - 复用 httpx.AsyncClient 连接池（避免每次请求新建 TCP 连接）
      - 指数退避重试（429 / 5xx 自动重试 3 次）
      - 请求体运行时校验（拦截参数拼写错误）
      - API 版本集中管理
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "LongCat-2.0-Preview",
        timeout: int = 120,
        max_retries: int = 3,
    ):
        self._api_key = api_key or os.environ.get("LONGCAT_API_KEY", "")
        base = base_url or os.environ.get("TOTORO_BASE_URL", "https://api.longcat.chat/anthropic")
        # 确保 base_url 以 / 结尾
        self._base_url = base.rstrip("/") + "/v1/messages"
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
        # 懒初始化的持久 HTTP 客户端——复用连接池
        self._client: httpx.AsyncClient | None = None

    # ---------- 内部 helpers ----------

    def _get_client(self) -> httpx.AsyncClient:
        """获取或创建持久化的 HTTP 客户端，复用连接池。"""
        if self._client is None or self._client.is_closed:
            transport = httpx.AsyncHTTPTransport(retries=2)
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10.0),
                transport=transport,
            )
        return self._client

    async def close(self) -> None:
        """关闭持久化客户端，释放连接池。"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _headers(self, stream: bool = False) -> dict[str, Any]:
        h = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "anthropic-version": ANTHROPIC_API_VERSION,
            # 客户端身份标识——让 API 端能识别调用方
            "User-Agent": f"{CLIENT_NAME}/{CLIENT_VERSION}",
            "x-client-name": CLIENT_NAME,
            "x-client-version": CLIENT_VERSION,
        }
        if stream:
            h["accept"] = "text/event-stream"
        else:
            h["accept"] = "application/json"
        return h

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolCallDefinition] | None,
        max_tokens: int,
        temperature: float,
        stream: bool = False,
    ) -> dict[str, Any]:
        """构建请求体并做运行时校验。"""
        system_content = None
        raw_messages = messages[:]
        if messages and messages[0].get("role") == "system":
            system_content = messages[0]["content"]
            raw_messages = messages[1:]

        # 关键：将 OpenAI 格式的 tool messages 转换为 Anthropic 格式
        chat_messages = convert_openai_to_anthropic_messages(raw_messages)

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
            "temperature": temperature,
        }
        if stream:
            payload["stream"] = True
        if system_content:
            payload["system"] = system_content
        if tools:
            payload["tools"] = self._serialize_tools(tools)

        # 运行时校验——拦截参数拼写错误
        errors = validate_payload(payload)
        if errors:
            raise ValueError(f"请求校验失败: {'; '.join(errors)}")

        return payload

    async def _request_with_retry(
        self,
        payload: dict[str, Any],
        *,
        stream: bool = False,
    ) -> httpx.Response:
        """带指数退避重试的 HTTP 请求。"""
        client = self._get_client()
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                if stream:
                    resp = await client.send(
                        client.build_request(
                            "POST",
                            self._base_url,
                            headers=self._headers(stream=True),
                            json=payload,
                        ),
                        stream=True,
                    )
                else:
                    resp = await client.post(
                        self._base_url,
                        headers=self._headers(stream=False),
                        json=payload,
                    )

                # 429 / 5xx 触发重试
                if resp.status_code in (429, 500, 502, 503):
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )

                resp.raise_for_status()
                return resp

            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as e:
                last_exc = e
                if attempt < self._max_retries:
                    wait = 2**attempt  # 1s, 2s, 4s
                    logger.warning(
                        "LLM 请求失败 (attempt %d/%d): %s — %ds 后重试",
                        attempt + 1,
                        self._max_retries + 1,
                        e,
                        wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("LLM 请求 %d 次重试后仍失败: %s", self._max_retries + 1, e)

        raise last_exc  # type: ignore[misc]

    async def check_api_health(self) -> bool:
        """检查 API 是否可达及版本是否过时。"""
        try:
            client = self._get_client()
            # 用 messages 端点的父路径做轻量探测
            base = self._base_url.rsplit("/", 1)[0]
            resp = await client.get(base, timeout=10)
            deprecated = resp.headers.get("x-deprecated-version")
            if deprecated:
                logger.warning("API 版本可能已过时 (x-deprecated-version: %s)", deprecated)
            return resp.status_code < 500
        except Exception as e:
            logger.warning("API 健康检查失败: %s", e)
            return False

    def _serialize_tools(self, tools: list[ToolCallDefinition]) -> list[dict[str, Any]]:
        """将 ToolCallDefinition 转为 Anthropic tool schema。"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters_schema,
            }
            for t in tools
        ]

    def _parse_response(self, data: dict[str, Any]) -> ChatResponse:
        """解析 Anthropic /v1/messages 响应。"""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in data.get("content", []):
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                text_parts.append(block["text"])
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        usage = data.get("usage", {})
        return ChatResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            ),
            finish_reason=data.get("stop_reason", "stop") or "stop",
        )

    def _parse_sse_event(self, line: str) -> dict[str, Any] | None:
        """解析单行 SSE 事件。"""
        if line.startswith("data: "):
            payload = line[6:]
            if payload == "[DONE]":
                return {"type": "message_stop"}
            try:
                return json.loads(payload)  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                return None
        return None

    # ---------- 非流式 ----------

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> ChatResponse:
        payload = self._build_payload(messages, tools, max_tokens, temperature)
        resp = await self._request_with_retry(payload, stream=False)
        data = resp.json()
        return self._parse_response(data)

    # ---------- 流式 ----------

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamEvent]:
        payload = self._build_payload(messages, tools, max_tokens, temperature, stream=True)

        # 流式请求只重试连接阶段，流建立后的中断不重试
        client = self._get_client()
        resp: httpx.Response | None = None
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                req = client.build_request(
                    "POST",
                    self._base_url,
                    headers=self._headers(stream=True),
                    json=payload,
                )
                resp = await client.send(req, stream=True)
                if resp.status_code in (429, 500, 502, 503):
                    await resp.aclose()
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=req, response=resp
                    )
                resp.raise_for_status()
                break
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as e:
                last_exc = e
                if attempt < self._max_retries:
                    wait = 2**attempt
                    logger.warning(
                        "流式请求连接失败 (attempt %d/%d): %s — %ds 后重试",
                        attempt + 1,
                        self._max_retries + 1,
                        e,
                        wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise

        if resp is None:
            raise last_exc  # type: ignore[misc]

        try:
            # 收集增量状态
            text_buffer = ""
            current_tool_name = ""
            current_tool_args_buffer = ""
            collecting_tool_args = False

            async for line in resp.aiter_lines():
                if not line:
                    continue

                event = self._parse_sse_event(line)
                if event is None:
                    continue

                etype = event.get("type")

                if etype == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "text":
                        pass  # 等 delta
                    elif block.get("type") == "tool_use":
                        block.get("id", "")
                        current_tool_name = block.get("name", "")
                        current_tool_args_buffer = ""
                        collecting_tool_args = True

                elif etype == "content_block_delta":
                    delta = event.get("delta", {})
                    dtype = delta.get("type")
                    if dtype == "text_delta" and delta.get("text"):
                        text_buffer += delta["text"]
                        yield StreamEvent(type="text_delta", content=delta["text"])
                    elif dtype == "input_json_delta" and collecting_tool_args:
                        current_tool_args_buffer += delta.get("partial_json", "")

                elif etype == "content_block_stop":
                    if current_tool_name:
                        try:
                            args = (
                                json.loads(current_tool_args_buffer)
                                if current_tool_args_buffer
                                else {}
                            )
                        except json.JSONDecodeError:
                            args = {}
                        yield StreamEvent(
                            type="tool_call_start",
                            tool_name=current_tool_name,
                            tool_arguments=args,
                        )
                        current_tool_name = ""
                        collecting_tool_args = False

                elif etype == "message_delta":
                    event.get("delta", {}).get("stop_reason")
                    usage = event.get("usage", {})
                    yield StreamEvent(
                        type="done",
                        usage=TokenUsage(
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                        ),
                    )

                elif etype == "message_stop":
                    yield StreamEvent(type="done")
        finally:
            await resp.aclose()

    # ---------- Provider 协议：让 Registry 能实例化 ----------

    def __repr__(self) -> str:
        return f"TotoroProvider(model={self._model})"
