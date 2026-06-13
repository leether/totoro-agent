"""测试 tools/registry.py — ToolRegistry。"""
import pytest
from tools.base import BaseTool, ToolResult
from tools.registry import ToolRegistry


class _ToolA(BaseTool):
    @property
    def name(self): return "tool_a"
    @property
    def description(self): return "Tool A"
    @property
    def parameters_schema(self): return {"type": "object", "properties": {}}
    async def execute(self, **kw): return ToolResult(success=True, output="a")


class _ToolB(BaseTool):
    @property
    def name(self): return "tool_b"
    @property
    def description(self): return "Tool B"
    @property
    def parameters_schema(self): return {"type": "object", "properties": {}}
    async def execute(self, **kw): return ToolResult(success=True, output="b")


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = _ToolA()
        reg.register(tool)
        assert reg.get("tool_a") is tool

    def test_get_missing_returns_none(self):
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_list_tools(self):
        reg = ToolRegistry()
        a, b = _ToolA(), _ToolB()
        reg.register(a)
        reg.register(b)
        tools = reg.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "tool_a"
        assert tools[1].name == "tool_b"

    def test_tool_names(self):
        reg = ToolRegistry()
        reg.register(_ToolA())
        reg.register(_ToolB())
        assert reg.tool_names() == ["tool_a", "tool_b"]

    def test_tool_definitions(self):
        reg = ToolRegistry()
        reg.register(_ToolA())
        defs = reg.tool_definitions()
        assert len(defs) == 1
        assert defs[0]["name"] == "tool_a"
        assert "description" in defs[0]
        assert "parameters_schema" in defs[0]

    def test_len(self):
        reg = ToolRegistry()
        assert len(reg) == 0
        reg.register(_ToolA())
        assert len(reg) == 1

    def test_contains(self):
        reg = ToolRegistry()
        reg.register(_ToolA())
        assert "tool_a" in reg
        assert "tool_b" not in reg

    def test_clear(self):
        reg = ToolRegistry()
        reg.register(_ToolA())
        reg.register(_ToolB())
        reg.clear()
        assert len(reg) == 0

    def test_repr(self):
        reg = ToolRegistry()
        reg.register(_ToolA())
        assert "tool_a" in repr(reg)

    def test_load_preset_core(self):
        reg = ToolRegistry()
        reg.load_preset("core")
        names = reg.tool_names()
        assert "read_file" in names
        assert "write_file" in names
        assert "edit_file" in names
        assert "list_dir" in names
        assert "search_file" in names
        assert "bash" in names

    def test_load_preset_readonly(self):
        reg = ToolRegistry()
        reg.load_preset("readonly")
        names = reg.tool_names()
        assert "read_file" in names
        assert "list_dir" in names
        assert "search_file" in names
        assert "write_file" not in names
        assert "bash" not in names

    def test_load_preset_full(self):
        reg = ToolRegistry()
        reg.load_preset("full")
        names = reg.tool_names()
        assert "read_file" in names
        assert "write_file" in names
        assert "bash" in names
        assert "web_search" in names
        assert "web_fetch" in names
        assert "git_status" in names
        assert "project_summary" in names
