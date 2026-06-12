"""ChatProvider 协议 — 所有 LLM 后端必须实现此接口。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class TokenUsage:
    """Token 用量统计。"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ToolCallDefinition:
    """工具调用定义（发送给 LLM 的 tool/function 描述）。"""
    name: str
    description: str
    parameters_schema: dict  # JSON Schema

    def to_anthropic_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters_schema,
        }

    def to_openai_dict(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


@dataclass
class ToolCall:
    """模型返回的一次工具调用。"""
    id: str
    name: str
    arguments: dict


@dataclass
class ChatResponse:
    """非流式聊天响应。"""
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = "stop"  # "stop" | "tool_calls" | "length"


@dataclass
class StreamEvent:
    """流式响应事件。"""
    type: str  # "text_delta" | "tool_call_start" | "tool_call_end" | "done"
    content: str = ""
    tool_name: str = ""
    tool_arguments: dict = field(default_factory=dict)
    tool_result: str = ""
    usage: TokenUsage | None = None


class ChatProvider(Protocol):
    """LLM 提供者协议。所有后端（LongCat / OpenAI / Anthropic / 本地）必须实现。"""

    async def chat(
        self,
        messages: list[dict],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> ChatResponse:
        """非流式聊天。"""
        ...

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamEvent]:
        """流式聊天，逐个 yield 事件。"""
        ...
