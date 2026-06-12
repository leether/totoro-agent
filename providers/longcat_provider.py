"""LongCat Provider — 基于 httpx 的纯 Python 实现，无 pydantic_core 依赖。

LongCat API 兼容 Anthropic 的 /v1/messages 接口格式，直接 HTTP 调用。
"""
from __future__ import annotations

import json
import os
from typing import AsyncIterator

import httpx

from providers.base import (
    ChatProvider,
    ChatResponse,
    StreamEvent,
    ToolCall,
    ToolCallDefinition,
    TokenUsage,
)


class LongCatProvider:
    """LongCat 提供者 — 兼容 Anthropic /v1/messages API。"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "LongCat-2.0-Preview",
        timeout: int = 120,
    ):
        self._api_key = api_key or os.environ.get("LONGCAT_API_KEY", "")
        base = base_url or os.environ.get("LONGCAT_BASE_URL", "https://api.longcat.chat/anthropic")
        # 确保 base_url 以 / 结尾
        self._base_url = base.rstrip("/") + "/v1/messages"
        self._model = model
        self._timeout = timeout

    # ---------- 内部 helpers ----------

    def _headers(self, stream: bool = False) -> dict:
        h = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if stream:
            h["accept"] = "text/event-stream"
        else:
            h["accept"] = "application/json"
        return h

    def _serialize_tools(self, tools: list[ToolCallDefinition]) -> list[dict]:
        """将 ToolCallDefinition 转为 Anthropic tool schema。"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters_schema,
            }
            for t in tools
        ]

    def _parse_response(self, data: dict) -> ChatResponse:
        """解析 Anthropic /v1/messages 响应。"""
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

    def _parse_sse_event(self, line: str) -> dict | None:
        """解析单行 SSE 事件。"""
        if line.startswith("data: "):
            payload = line[6:]
            if payload == "[DONE]":
                return {"type": "message_stop"}
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None
        return None

    # ---------- 非流式 ----------

    async def chat(
        self,
        messages: list[dict],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> ChatResponse:
        # 分离 system prompt
        system_content = None
        chat_messages = messages[:]
        if messages and messages[0].get("role") == "system":
            system_content = messages[0]["content"]
            chat_messages = messages[1:]

        payload: dict = {
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
                headers=self._headers(stream=False),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return self._parse_response(data)

    # ---------- 流式 ----------

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamEvent]:
        system_content = None
        chat_messages = messages[:]
        if messages and messages[0].get("role") == "system":
            system_content = messages[0]["content"]
            chat_messages = messages[1:]

        payload: dict = {
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

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                self._base_url,
                headers=self._headers(stream=True),
                json=payload,
            ) as resp:
                resp.raise_for_status()

                # 收集增量状态
                text_buffer = ""
                current_tool_name = ""
                current_tool_id = ""
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
                            current_tool_id = block.get("id", "")
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
                                args = json.loads(current_tool_args_buffer) if current_tool_args_buffer else {}
                            except json.JSONDecodeError:
                                args = {}
                            yield StreamEvent(
                                type="tool_call_start",
                                tool_name=current_tool_name,
                                tool_arguments=args,
                            )
                            current_tool_name = ""
                            current_tool_id = ""
                            collecting_tool_args = False

                    elif etype == "message_delta":
                        stop_reason = event.get("delta", {}).get("stop_reason")
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

    # ---------- Provider 协议：让 Registry 能实例化 ----------

    def __repr__(self) -> str:
        return f"LongCatProvider(model={self._model})"
