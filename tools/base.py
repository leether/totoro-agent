"""工具协议 — 所有 Agent 工具的基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """工具执行结果。"""
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> str:
        """转换为可注入 LLM 的 message 文本。"""
        if self.success:
            return self.output
        return f"Error: {self.error}\nOutput: {self.output}"


class BaseTool(ABC):
    """所有 Agent 工具的抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（唯一标识）。"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """功能描述（注入 LLM system prompt）。"""
        ...

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """参数 JSON Schema（默认空对象，子类可覆盖）。"""
        return {"type": "object", "properties": {}}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具。"""
        ...
