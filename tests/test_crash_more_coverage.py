"""更多覆盖率测试 — 覆盖 Git 工具、Project 工具、Web 工具、Provider 网络层。

专门针对 0% 覆盖率的代码路径设计，目标是把这些模块中隐藏的崩溃点逼出来。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ============================================================================
# Git 工具全覆盖
# ============================================================================


class TestGitToolsFull:
    """GitStatusTool / GitDiffTool / GitLogTool 全面测试。"""

    @pytest.mark.asyncio
    async def test_git_status_clean_repo(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=str(tmp_path), capture_output=True
        )

        from tools.git_tool import GitStatusTool

        tool = GitStatusTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "干净" in result.output

    @pytest.mark.asyncio
    async def test_git_status_with_changes(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "test.py").write_text("print('modified')")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "test.py").write_text("print('changed')")

        from tools.git_tool import GitStatusTool

        tool = GitStatusTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "test.py" in result.output

    @pytest.mark.asyncio
    async def test_git_diff_no_changes(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "file.py").write_text("x = 1")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)

        from tools.git_tool import GitDiffTool

        tool = GitDiffTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "无变更" in result.output

    @pytest.mark.asyncio
    async def test_git_diff_with_changes(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "file.py").write_text("x = 1")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "file.py").write_text("x = 2")

        from tools.git_tool import GitDiffTool

        tool = GitDiffTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "x = 2" in result.output

    @pytest.mark.asyncio
    async def test_git_diff_specific_file(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "a.py").write_text("a = 1")
        (tmp_path / "b.py").write_text("b = 1")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "a.py").write_text("a = 2")
        (tmp_path / "b.py").write_text("b = 2")

        from tools.git_tool import GitDiffTool

        tool = GitDiffTool()
        result = await tool.execute(path=str(tmp_path), file="a.py")
        assert result.success is True
        assert "a = 2" in result.output
        assert "b = 2" not in result.output

    @pytest.mark.asyncio
    async def test_git_diff_not_git_repo(self, tmp_path):
        from tools.git_tool import GitDiffTool

        tool = GitDiffTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_git_log_with_commits(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), capture_output=True)
        for i in range(3):
            (tmp_path / f"f{i}.py").write_text(f"# file {i}")
            subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"commit {i}"], cwd=str(tmp_path), capture_output=True
            )

        from tools.git_tool import GitLogTool

        tool = GitLogTool()
        result = await tool.execute(path=str(tmp_path), limit=2)
        assert result.success is True
        assert "commit" in result.output.lower()

    @pytest.mark.asyncio
    async def test_git_log_empty_repo(self, tmp_path):
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)

        from tools.git_tool import GitLogTool

        tool = GitLogTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is False  # no commits yet

    @pytest.mark.asyncio
    async def test_git_log_not_git_repo(self, tmp_path):
        from tools.git_tool import GitLogTool

        tool = GitLogTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_git_status_default_path(self):
        """默认路径 '.' 应使用当前工作目录。"""
        from tools.git_tool import GitStatusTool

        tool = GitStatusTool()
        # 在当前项目目录执行，应该能正常工作
        result = await tool.execute()
        # 当前目录是 git repo
        assert result.success is True


# ============================================================================
# Project 工具全覆盖
# ============================================================================


class TestProjectToolFull:
    """ProjectSummaryTool 全面测试。"""

    @pytest.mark.asyncio
    async def test_project_summary_basic(self, tmp_path):
        from tools.project_tool import ProjectSummaryTool

        (tmp_path / "main.py").write_text("def main(): pass")
        (tmp_path / "requirements.txt").write_text("httpx\npytest\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "目录树" in result.output
        assert "main.py" in result.output
        assert "httpx" in result.output

    @pytest.mark.asyncio
    async def test_project_summary_nonexistent(self):
        from tools.project_tool import ProjectSummaryTool

        tool = ProjectSummaryTool()
        result = await tool.execute(path="/nonexistent_project_xyz")
        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_project_summary_on_file(self, tmp_path):
        from tools.project_tool import ProjectSummaryTool

        f = tmp_path / "not_a_dir.txt"
        f.write_text("content")
        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(f))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_project_summary_empty_dir(self, tmp_path):
        from tools.project_tool import ProjectSummaryTool

        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "未检测到" in result.output

    @pytest.mark.asyncio
    async def test_project_summary_with_package_json(self, tmp_path):
        from tools.project_tool import ProjectSummaryTool

        (tmp_path / "package.json").write_text(
            json.dumps(
                {
                    "name": "test-pkg",
                    "dependencies": {"express": "^4.18"},
                    "devDependencies": {"jest": "^29"},
                }
            )
        )
        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert "express" in result.output
        assert "jest" in result.output

    @pytest.mark.asyncio
    async def test_project_summary_malformed_package_json(self, tmp_path):
        """package.json 格式错误不应崩溃。"""
        from tools.project_tool import ProjectSummaryTool

        (tmp_path / "package.json").write_text("{ broken json }")
        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True  # should not crash

    @pytest.mark.asyncio
    async def test_project_summary_file_stats(self, tmp_path):
        from tools.project_tool import ProjectSummaryTool

        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        (tmp_path / "c.js").write_text("c")
        (tmp_path / "d.ts").write_text("d")
        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True
        assert result.metadata["python_files"] == 2
        assert result.metadata["js_files"] == 1
        assert result.metadata["ts_files"] == 1


# ============================================================================
# Web 工具测试（Mock 网络层）
# ============================================================================


class TestWebToolsMocked:
    """Web 工具测试，使用 mock 避免真实网络请求。"""

    @pytest.mark.asyncio
    async def test_web_search_network_error(self):
        """网络错误应返回失败结果，不崩溃。"""
        from tools.web_tools import WebSearchTool

        tool = WebSearchTool()
        with patch("urllib.request.urlopen", side_effect=Exception("Network down")):
            result = await tool.execute(query="test query")
        assert result.success is False
        assert "搜索失败" in result.error

    @pytest.mark.asyncio
    async def test_web_fetch_network_error(self):
        """获取 URL 失败应返回错误。"""
        from tools.web_tools import WebFetchTool

        tool = WebFetchTool()
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            result = await tool.execute(url="http://nonexistent.invalid")
        assert result.success is False
        assert "获取失败" in result.error

    @pytest.mark.asyncio
    async def test_web_search_malformed_response(self):
        """畸形响应不应崩溃。"""
        from tools.web_tools import WebSearchTool

        tool = WebSearchTool()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json at all"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await tool.execute(query="test")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_web_search_empty_results(self):
        """搜索返回空结果。"""
        from tools.web_tools import WebSearchTool

        tool = WebSearchTool()
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "AbstractText": "",
                "AbstractURL": "",
                "RelatedTopics": [],
            }
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await tool.execute(query="obscure query")
        assert result.success is True
        assert "无搜索结果" in result.output

    @pytest.mark.asyncio
    async def test_web_search_with_results(self):
        """搜索返回有效结果。"""
        from tools.web_tools import WebSearchTool

        tool = WebSearchTool()
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "AbstractText": "Python is a programming language.",
                "AbstractURL": "https://python.org",
                "RelatedTopics": [
                    {"Text": "Python tutorial"},
                    {"Text": "Python docs"},
                ],
            }
        ).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await tool.execute(query="python")
        assert result.success is True
        assert "programming language" in result.output
        assert "Python tutorial" in result.output

    @pytest.mark.asyncio
    async def test_web_fetch_html_content(self):
        """获取 HTML 页面应去除标签。"""
        from tools.web_tools import WebFetchTool

        tool = WebFetchTool()
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html><body><p>Hello World</p></body></html>"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await tool.execute(url="http://example.com")
        assert result.success is True
        assert "Hello World" in result.output
        assert "<p>" not in result.output

    @pytest.mark.asyncio
    async def test_web_fetch_large_content_truncated(self):
        """大页面应被截断。"""
        from tools.web_tools import WebFetchTool

        tool = WebFetchTool()
        large_html = f"<p>{'x' * 20000}</p>"
        mock_resp = MagicMock()
        mock_resp.read.return_value = large_html.encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await tool.execute(url="http://example.com/large")
        assert result.success is True
        assert len(result.output) < 20000

    def test_web_search_tool_schema(self):
        from tools.web_tools import WebSearchTool

        tool = WebSearchTool()
        assert tool.name == "web_search"
        assert "query" in tool.parameters_schema["properties"]

    def test_web_fetch_tool_schema(self):
        from tools.web_tools import WebFetchTool

        tool = WebFetchTool()
        assert tool.name == "web_fetch"
        assert "url" in tool.parameters_schema["properties"]


# ============================================================================
# Totoro Provider — 流式 SSE 解析测试
# ============================================================================


class TestTotoroSSEParsing:
    """TotoroProvider 的 SSE 流式解析逻辑。"""

    def test_parse_sse_content_block_start_text(self):
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        event = provider._parse_sse_event(
            'data: {"type": "content_block_start", "content_block": {"type": "text"}}'
        )
        assert event is not None
        assert event["type"] == "content_block_start"

    def test_parse_sse_content_block_start_tool_use(self):
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        event = provider._parse_sse_event(
            'data: {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "tc1", "name": "bash"}}'
        )
        assert event is not None
        assert event["content_block"]["name"] == "bash"

    def test_parse_sse_content_block_delta_text(self):
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        event = provider._parse_sse_event(
            'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}}'
        )
        assert event is not None
        assert event["delta"]["text"] == "Hello"

    def test_parse_sse_content_block_delta_tool_json(self):
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        event = provider._parse_sse_event(
            'data: {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": "{\\"cmd\\""}}'
        )
        assert event is not None
        assert "partial_json" in event["delta"]

    def test_parse_sse_message_delta_with_usage(self):
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        event = provider._parse_sse_event(
            'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"input_tokens": 100, "output_tokens": 50}}'
        )
        assert event is not None
        assert event["usage"]["input_tokens"] == 100

    def test_parse_sse_empty_data(self):
        """data: 后面什么都没有。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        result = provider._parse_sse_event("data: ")
        assert result is None  # json.loads("") 会抛异常 → None

    @pytest.mark.asyncio
    async def test_stream_chat_mock_success(self):
        """Mock 一个成功的流式响应。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")

        # 构造 SSE 响应行
        sse_lines = [
            'data: {"type": "content_block_start", "content_block": {"type": "text"}}',
            'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello "}}',
            'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "World!"}}',
            'data: {"type": "content_block_stop"}',
            'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"input_tokens": 10, "output_tokens": 5}}',
            'data: {"type": "message_stop"}',
        ]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.aclose = AsyncMock()

        async def mock_aiter_lines():
            for line in sse_lines:
                yield line

        mock_response.aiter_lines = mock_aiter_lines

        mock_request = MagicMock()
        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=mock_request)
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        provider._client = mock_client

        events = []
        async for event in provider.stream_chat([{"role": "user", "content": "hi"}]):
            events.append(event)

        types = [e.type for e in events]
        assert "text_delta" in types
        assert "done" in types

        text_content = "".join(e.content for e in events if e.type == "text_delta")
        assert text_content == "Hello World!"

    @pytest.mark.asyncio
    async def test_stream_chat_mock_with_tool_use(self):
        """Mock 一个带 tool_use 的流式响应。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")

        sse_lines = [
            'data: {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "tc1", "name": "bash"}}',
            'data: {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": "{\\"command\\": \\"echo hi\\"}"}}',
            'data: {"type": "content_block_stop"}',
            'data: {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"input_tokens": 5, "output_tokens": 3}}',
            'data: {"type": "message_stop"}',
        ]

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.aclose = AsyncMock()

        async def mock_aiter_lines():
            for line in sse_lines:
                yield line

        mock_response.aiter_lines = mock_aiter_lines

        mock_request = MagicMock()
        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=mock_request)
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        provider._client = mock_client

        events = []
        async for event in provider.stream_chat([{"role": "user", "content": "run bash"}]):
            events.append(event)

        tool_events = [e for e in events if e.type == "tool_call_start"]
        assert len(tool_events) == 1
        assert tool_events[0].tool_name == "bash"
        assert tool_events[0].tool_arguments == {"command": "echo hi"}


# ============================================================================
# OpenAI Provider — 网络层 mock 测试
# ============================================================================


class TestOpenAIProviderNetwork:
    """OpenAIProvider 的 HTTP 调用测试。"""

    @pytest.mark.asyncio
    async def test_chat_mock_success(self):
        from providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await provider.chat([{"role": "user", "content": "hi"}])

        assert result.text == "Hello!"
        assert result.usage.total_tokens == 8

    @pytest.mark.asyncio
    async def test_chat_mock_with_tool_calls(self):
        from providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Running bash",
                        "tool_calls": [
                            {
                                "id": "tc1",
                                "function": {
                                    "name": "bash",
                                    "arguments": '{"command": "ls"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await provider.chat([{"role": "user", "content": "ls"}])

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "bash"
        assert result.tool_calls[0].arguments == {"command": "ls"}


# ============================================================================
# Anthropic Provider — 网络层 mock 测试
# ============================================================================


class TestAnthropicProviderNetwork:
    """AnthropicProvider 的 HTTP 调用测试。"""

    @pytest.mark.asyncio
    async def test_chat_mock_success(self):
        from providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Hello!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await provider.chat([{"role": "user", "content": "hi"}])

        assert result.text == "Hello!"
        assert result.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_chat_mock_with_system_and_tools(self):
        from providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "Using tool"},
                {"type": "tool_use", "id": "tc1", "name": "bash", "input": {"command": "ls"}},
            ],
            "usage": {"input_tokens": 20, "output_tokens": 10},
            "stop_reason": "tool_use",
        }

        tools = [
            __import__("providers.base", fromlist=["ToolCallDefinition"]).ToolCallDefinition(
                name="bash", description="Run bash", parameters_schema={"type": "object"}
            )
        ]

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await provider.chat(
                [{"role": "system", "content": "Be helpful."}, {"role": "user", "content": "ls"}],
                tools=tools,
            )

        assert "Using tool" in result.text
        assert len(result.tool_calls) == 1


# ============================================================================
# CLI 入口测试（基本 smoke test）
# ============================================================================


class TestCLIBasic:
    """CLI 模块的基本导入和结构测试。"""

    def test_import_cli_main(self):
        """CLI main 模块应可正常导入。"""
        import cli.main  # noqa: F401

    def test_import_cli_repl(self):
        """CLI repl 模块应可正常导入。"""
        import cli.repl  # noqa: F401

    def test_agent_settings_import(self):
        """config.AgentSettings 应可正常导入。"""
        from config import AgentSettings  # noqa: F401
