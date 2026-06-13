"""Anthropic Provider — 基于 httpx 的纯 Python 实现，无 pydantic_core 依赖。

直接使用 Anthropic 原生 /v1/messages API，通过 httpx 发送请求。
"""
from __future__ import annotations

from typing import Any

import json
import os
from typing import TYPE_CHECKING

import httpx

from providers.base import (
    ChatResponse,
    StreamEvent,
    TokenUsage,
    ToolCall,
    ToolCallDefinition,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class AnthropicProvider:
    """Anthropic 原生 API 支持者（Claude 系列），基于 httpx 实现。"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "claude-sonnet-4-20250514",
        timeout: int = 120,
    ):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        base = base_url or os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        self._base_url = base.rstrip("/") + "/v1/messages"
        self._model = model
        self._timeout = timeout

    def _headers(self) -> dict[str, Any]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _serialize_tools(self, tools: list[ToolCallDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters_schema,
            }
            for t in tools
        ]

    def _parse_response(self, data: dict[str, Any]) -> ChatResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in data.get("content", []):
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                text_parts.append(block["text"])
            elif btype == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    arguments=block.get("input", {}),
                ))

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

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> ChatResponse:
        system_content = None
        chat_messages = messages[:]
        if messages and messages[0].get("role") == "system":
            system_content = messages[0]["content"]
            chat_messages = messages[1:]

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
            "temperature": temperature,
        }
        if system_content:
            payload["system"] = system_content
        if tools:
            payload["tools"] = self._serialize_tools(tools)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._base_url,
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return self._parse_response(data)

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamEvent]:
        system_content = None
        chat_messages = messages[:]
        if messages and messages[0].get("role") == "system":
            system_content = messages[0]["content"]
            chat_messages = messages[1:]

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
            "temperature": temperature,
            "stream": True,
        }
        if system_content:
            payload["system"] = system_content
        if tools:
            payload["tools"] = self._serialize_tools(tools)

        async with httpx.AsyncClient(timeout=self._timeout) as client, client.stream(
            "POST",
            self._base_url,
            headers={**self._headers(), "accept": "text/event-stream"},
            json=payload,
        ) as resp:
                resp.raise_for_status()

                current_tool_name = ""
                current_tool_args_buffer = ""
                collecting_tool = False

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data: "):
                        continue

                    raw = line[6:]
                    if raw == "[DONE]":
                        yield StreamEvent(type="done")
                        continue

                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("type")

                    if etype == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            block.get("id", "")
                            current_tool_name = block.get("name", "")
                            current_tool_args_buffer = ""
                            collecting_tool = True

                    elif etype == "content_block_delta":
                        delta = event.get("delta", {})
                        dtype = delta.get("type")
                        if dtype == "text_delta" and delta.get("text"):
                            yield StreamEvent(type="text_delta", content=delta["text"])
                        elif dtype == "input_json_delta" and collecting_tool:
                            current_tool_args_buffer += delta.get("partial_json", "")

                    elif etype == "content_block_stop":
                        if collecting_tool and current_tool_name:
                            try:
                                args = json.loads(current_tool_args_buffer) if current_tool_args_buffer else {}
                            except json.JSONDecodeError:
                                args = {}
                            yield StreamEvent(
                                type="tool_call_start",
                                tool_name=current_tool_name,
                                tool_arguments=args,
                            )
                            current_tool_name = ""
                            collecting_tool = False

                    elif etype == "message_delta":
                        usage = event.get("usage", {})
                        yield StreamEvent(
                            type="done",
                            usage=TokenUsage(
                                input_tokens=usage.get("input_tokens", 0),
                                output_tokens=usage.get("output_tokens", 0),
                            ),
                        )

    def __repr__(self) -> str:
        return f"AnthropicProvider(model={self._model})"
