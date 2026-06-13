"""ChatProvider 协议 — 所有 LLM 后端必须实现此接口。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


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
    parameters_schema: dict[str, Any]  # JSON Schema

    def to_anthropic_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters_schema,
        }

    def to_openai_dict(self) -> dict[str, Any]:
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
    arguments: dict[str, Any]


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
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""
    usage: TokenUsage | None = None


class ChatProvider(Protocol):
    """LLM 提供者协议。所有后端（LongCat / OpenAI / Anthropic / 本地）必须实现。"""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> ChatResponse:
        """非流式聊天。"""
        ...

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[ToolCallDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamEvent]:
        """流式聊天，逐个 yield 事件。"""
        ...


# ──────────────────────────────────────────────
# 类型定义 + 运行时校验（弥补纯 httpx 无类型安全的问题）
# ──────────────────────────────────────────────


class Message(TypedDict):
    """单条消息。"""

    role: str  # "user" | "assistant" | "system"
    content: str


class ChatPayload(TypedDict):
    """发送给 Anthropic /v1/messages 的请求体。"""

    model: str
    max_tokens: int
    messages: list[Message]
    temperature: float


_VALID_ROLES = frozenset({"user", "assistant", "system"})


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """运行时校验请求体，返回错误列表（空列表 = 通过）。

    只校验关键字段，不做完整 schema 校验——目标是拦截最常见的拼写错误
    和类型错误，而非替代 pydantic 的完整能力。
    """
    errors: list[str] = []

    if not payload.get("model"):
        errors.append("model 不能为空")

    max_tokens = payload.get("max_tokens")
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        errors.append(f"max_tokens 必须是正整数，得到 {type(max_tokens).__name__}: {max_tokens!r}")

    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) == 0:
        errors.append("messages 必须是非空列表")
    else:
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                errors.append(f"messages[{i}] 必须是 dict")
                continue
            role = msg.get("role")
            if role not in _VALID_ROLES:
                errors.append(f"messages[{i}].role={role!r} 不在 {sorted(_VALID_ROLES)} 中")
            if not msg.get("content"):
                errors.append(f"messages[{i}].content 不能为空")

    temperature = payload.get("temperature")
    if temperature is not None and not (
        isinstance(temperature, float | int) and 0 <= temperature <= 2
    ):
        errors.append(f"temperature 应在 [0, 2] 范围内，得到 {temperature!r}")

    if errors:
        logger.warning("请求校验失败: %s", errors)

    return errors
