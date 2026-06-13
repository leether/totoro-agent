"""OpenAI Provider — 基于 httpx 的纯 Python 实现，无 pydantic_core 依赖。"""
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


def _to_openai_tool(t: ToolCallDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters_schema,
        },
    }


class OpenAIProvider:
    """OpenAI 兼容提供者（GPT-4 / GPT-4o），基于直接 HTTP 调用。"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "gpt-4o",
        timeout: int = 120,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        base = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        self._base_url = base.rstrip("/") + "/v1/chat/completions"
        self._model = model
        self._timeout = timeout

    def _headers(self) -> dict[str, Any]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _parse_response(self, data: dict[str, Any]) -> ChatResponse:
        choices = data.get("choices", [])
        if not choices:
            return ChatResponse(text="", tool_calls=[], usage=TokenUsage(0, 0), finish_reason="stop")

        msg = choices[0].get("message", {})
        text = msg.get("content", "") or ""

        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls", []):
            func = tc.get("function", {})
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=func.get("name", ""),
                arguments=args,
            ))

        usage = data.get("usage", {})
        return ChatResponse(
            text=text,
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            finish_reason=choices[0].get("finish_reason", "stop") or "stop",
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [_to_openai_tool(t) for t in tools]
            payload["tool_choice"] = "auto"

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
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = [_to_openai_tool(t) for t in tools]
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=self._timeout) as client, client.stream(
            "POST",
            self._base_url,
            headers=self._headers(),
            json=payload,
        ) as resp:
            resp.raise_for_status()

            # 增量聚合 tool_calls
            tool_call_buffers: dict[int, dict[str, Any]] = {}

            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    payload_str = line[6:]
                    if payload_str == "[DONE]":
                        yield StreamEvent(type="done")
                        continue

                    try:
                        chunk = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})

                    # text content
                    if delta.get("content"):
                        yield StreamEvent(type="text_delta", content=delta["content"])

                    # tool_calls 增量
                    for tc_delta in delta.get("tool_calls", []):
                        idx = tc_delta.get("index", 0)
                        if idx not in tool_call_buffers:
                            tool_call_buffers[idx] = {
                                "id": tc_delta.get("id", ""),
                                "name": "",
                                "args_buffer": "",
                            }

                        buf = tool_call_buffers[idx]
                        func = tc_delta.get("function", {})
                        if func.get("name"):
                            buf["name"] = func["name"]
                        if func.get("arguments"):
                            buf["args_buffer"] += func["arguments"]

                        # yield tool_call_start 一次
                        if buf["name"] and not buf.get("emitted"):
                            try:
                                args = json.loads(buf["args_buffer"]) if buf["args_buffer"] else {}
                            except json.JSONDecodeError:
                                args = {}
                            yield StreamEvent(
                                type="tool_call_start",
                                tool_name=buf["name"],
                                tool_arguments=args,
                            )
                            buf["emitted"] = True

    def __repr__(self) -> str:
        return f"OpenAIProvider(model={self._model})"
