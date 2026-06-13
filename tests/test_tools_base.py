"""测试 tools/base.py — BaseTool 和 ToolResult。"""

from typing import Any

import pytest

from tools.base import BaseTool, ToolResult


class DummyTool(BaseTool):
    """测试用最小工具实现。"""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy tool for testing."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "A value."},
            },
            "required": ["value"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        value = kwargs.get("value", "")
        return ToolResult(success=True, output=f"got: {value}")


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, output="hello")
        assert r.success is True
        assert r.output == "hello"
        assert r.error is None

    def test_failure_result(self):
        r = ToolResult(success=False, output="", error="file not found")
        assert r.success is False
        assert r.error == "file not found"

    def test_to_message(self):
        r = ToolResult(success=True, output="result text")
        msg = r.to_message()
        assert msg == "result text"

    def test_to_message_with_error(self):
        r = ToolResult(success=False, output="partial", error="timeout")
        msg = r.to_message()
        assert "partial" in msg
        assert "timeout" in msg

    def test_metadata_default(self):
        r = ToolResult(success=True, output="x")
        assert r.metadata == {}

    def test_metadata_custom(self):
        r = ToolResult(success=True, output="x", metadata={"key": "val"})
        assert r.metadata["key"] == "val"


class TestBaseTool:
    @pytest.mark.asyncio
    async def test_dummy_tool_execute(self):
        tool = DummyTool()
        result = await tool.execute(value="test")
        assert result.success is True
        assert result.output == "got: test"

    def test_tool_properties(self):
        tool = DummyTool()
        assert tool.name == "dummy"
        assert "dummy" in tool.description
        assert tool.parameters_schema["type"] == "object"
        assert "value" in tool.parameters_schema["properties"]
