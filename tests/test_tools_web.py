"""测试 tools/web_tools.py — 网络工具。"""
import pytest

from tools.web_tools import WebFetchTool, WebSearchTool


class TestWebSearchTool:
    @pytest.mark.asyncio
    async def test_search_returns_result(self):
        tool = WebSearchTool()
        result = await tool.execute(query="Python programming language")
        # 网络搜索可能成功也可能失败（取决于网络），但不应崩溃
        assert isinstance(result.success, bool)
        assert isinstance(result.output, str)

    @pytest.mark.asyncio
    async def test_search_preserves_query_in_metadata(self):
        tool = WebSearchTool()
        result = await tool.execute(query="test query")
        assert result.metadata.get("query") == "test query"

    def test_schema(self):
        tool = WebSearchTool()
        assert tool.name == "web_search"
        assert "query" in tool.parameters_schema["required"]


class TestWebFetchTool:
    @pytest.mark.asyncio
    async def test_fetch_invalid_url(self):
        tool = WebFetchTool()
        result = await tool.execute(url="http://nonexistent.invalid.url.test")
        # 应该失败但不崩溃
        assert result.success is False
        assert result.error is not None

    def test_schema(self):
        tool = WebFetchTool()
        assert tool.name == "web_fetch"
        assert "url" in tool.parameters_schema["required"]
