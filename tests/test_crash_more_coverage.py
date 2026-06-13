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
    """Web 工具测试，使用 mock httpx 客户端避免真实网络请求。"""

    @pytest.mark.asyncio
    async def test_web_search_network_error(self):
        """网络错误应返回失败结果，不崩溃。"""
        from tools import web_tools

        tool = web_tools.WebSearchTool()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network down"))
        mock_client.is_closed = False
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(query="test query")
        assert result.success is True  # 双后端都失败 → 无搜索结果
        assert "无搜索结果" in result.output

    @pytest.mark.asyncio
    async def test_web_search_bing_results(self):
        """Bing 返回搜索结果应正确解析。"""
        from tools import web_tools

        tool = web_tools.WebSearchTool()
        bing_html = """
        <li class="b_algo">
            <h2><a href="https://example.com/article">Python Async Guide</a></h2>
            <div class="b_caption"><p>A comprehensive guide to async programming.</p></div>
        </li>
        <li class="b_algo">
            <h2><a href="https://realpython.com/async">Real Python Async Tutorial</a></h2>
            <div class="b_caption"><p>Learn asyncio from scratch.</p></div>
        </li>
        """

        mock_bing = MagicMock()
        mock_bing.status_code = 200
        mock_bing.text = bing_html

        mock_wiki = MagicMock()
        mock_wiki.status_code = 200
        mock_wiki.json.return_value = {"query": {"search": []}}

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(side_effect=[mock_bing, mock_wiki])
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(query="python async")

        assert result.success is True
        assert "Python Async Guide" in result.output
        assert "example.com/article" in result.output
        assert "comprehensive guide" in result.output

    @pytest.mark.asyncio
    async def test_web_search_wikipedia_only(self):
        """Bing 返回空但 Wikipedia 有结果。"""
        from tools import web_tools

        tool = web_tools.WebSearchTool()
        mock_bing = MagicMock()
        mock_bing.status_code = 200
        mock_bing.text = "<html><body>No results here</body></html>"

        mock_wiki = MagicMock()
        mock_wiki.status_code = 200
        mock_wiki.json.return_value = {
            "query": {
                "search": [
                    {"title": "Asyncio", "snippet": "asyncio is a Python module"},
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(side_effect=[mock_bing, mock_wiki])
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(query="asyncio")

        assert result.success is True
        assert "Asyncio" in result.output
        assert "Wikipedia" in result.output

    @pytest.mark.asyncio
    async def test_web_search_empty_results(self):
        """两个后端都返回空结果。"""
        from tools import web_tools

        tool = web_tools.WebSearchTool()
        mock_bing = MagicMock()
        mock_bing.status_code = 200
        mock_bing.text = "<html><body></body></html>"

        mock_wiki = MagicMock()
        mock_wiki.status_code = 200
        mock_wiki.json.return_value = {"query": {"search": []}}

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(side_effect=[mock_bing, mock_wiki])
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(query="obscure query")

        assert result.success is True
        assert "无搜索结果" in result.output

    @pytest.mark.asyncio
    async def test_web_search_bing_500_error(self):
        """Bing 返回 500 → 应优雅降级到 Wikipedia。"""
        from tools import web_tools

        tool = web_tools.WebSearchTool()
        mock_bing = MagicMock()
        mock_bing.status_code = 500
        mock_bing.text = "Internal Server Error"

        mock_wiki = MagicMock()
        mock_wiki.status_code = 200
        mock_wiki.json.return_value = {
            "query": {"search": [{"title": "Test", "snippet": "test snippet"}]}
        }

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(side_effect=[mock_bing, mock_wiki])
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(query="test")

        assert result.success is True
        assert "Test" in result.output

    @pytest.mark.asyncio
    async def test_web_fetch_network_error(self):
        """获取 URL 失败应返回错误。"""
        from tools import web_tools

        tool = web_tools.WebFetchTool()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(url="http://nonexistent.invalid")
        assert result.success is False
        assert "获取失败" in result.error

    @pytest.mark.asyncio
    async def test_web_fetch_invalid_url(self):
        """无效 URL 应返回错误。"""
        from tools.web_tools import WebFetchTool

        tool = WebFetchTool()
        result = await tool.execute(url="not-a-url")
        assert result.success is False
        assert "无效的 URL" in result.error

    @pytest.mark.asyncio
    async def test_web_fetch_html_content(self):
        """获取 HTML 页面应去除标签，保留正文。"""
        from tools import web_tools

        tool = web_tools.WebFetchTool()
        html = (
            "<html><head><style>body{color:red}</style></head>"
            "<body><script>alert(1)</script>"
            "<nav>Menu</nav><p>Hello World</p>"
            "<footer>Copyright</footer></body></html>"
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(url="http://example.com")

        assert result.success is True
        assert "Hello World" in result.output
        assert "<p>" not in result.output
        assert "alert" not in result.output
        assert "Copyright" not in result.output  # footer 被去除
        assert "color:red" not in result.output  # style 被去除

    @pytest.mark.asyncio
    async def test_web_fetch_plain_text(self):
        """纯文本内容应直接返回。"""
        from tools import web_tools

        tool = web_tools.WebFetchTool()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Hello, this is plain text."
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(url="https://raw.githubusercontent.com/test")

        assert result.success is True
        assert "plain text" in result.output

    @pytest.mark.asyncio
    async def test_web_fetch_json_content(self):
        """JSON 内容应直接返回。"""
        from tools import web_tools

        tool = web_tools.WebFetchTool()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"key": "value", "items": [1, 2, 3]}'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(url="https://api.example.com/data")

        assert result.success is True
        assert "value" in result.output
        assert "items" in result.output

    @pytest.mark.asyncio
    async def test_web_fetch_large_content_truncated(self):
        """大页面应被截断。"""
        from tools import web_tools

        tool = web_tools.WebFetchTool()
        large_html = f"<html><body><p>{'x' * 20000}</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = large_html
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = AsyncMock(return_value=mock_resp)
        with patch.object(web_tools, "_client", mock_client):
            result = await tool.execute(url="http://example.com/large", max_length=500)

        assert result.success is True
        assert len(result.output) <= 600  # 500 + 截断提示
        assert "截断" in result.output

    def test_web_search_tool_schema(self):
        from tools.web_tools import WebSearchTool

        tool = WebSearchTool()
        assert tool.name == "web_search"
        assert "query" in tool.parameters_schema["properties"]
        assert "max_results" in tool.parameters_schema["properties"]

    def test_web_fetch_tool_schema(self):
        from tools.web_tools import WebFetchTool

        tool = WebFetchTool()
        assert tool.name == "web_fetch"
        assert "url" in tool.parameters_schema["properties"]
        assert "max_length" in tool.parameters_schema["properties"]

    def test_extract_text_strips_noise_tags(self):
        """HTML 提取函数应去除 script/style/nav/footer。"""
        from tools.web_tools import extract_text_from_html

        html = """
        <html><body>
        <script>var x = 1;</script>
        <style>.cls { color: red; }</style>
        <nav><ul><li>Home</li><li>About</li></ul></nav>
        <main>
            <h1>Title</h1>
            <p>Important content here.</p>
        </main>
        <footer>(c) 2024</footer>
        </body></html>
        """
        text = extract_text_from_html(html)
        assert "Title" in text
        assert "Important content" in text
        assert "var x" not in text
        assert "color: red" not in text
        assert "Home" not in text
        assert "(c) 2024" not in text

    def test_parse_bing_real_html(self):
        """解析真实 Bing HTML 结构（含 CSS link 注入）。"""
        from tools.web_tools import _parse_bing

        html = """
        <li class="b_algo">
            <link rel="stylesheet" href="https://r.bing.com/rs/abc.css"/>
            <div class="b_tpcn"><a class="tilk" href="https://example.com">domain</a></div>
            <h2><a href="https://example.com/guide">Python Guide</a></h2>
            <div class="b_caption"><p class="b_lineclamp2">A great guide.</p></div>
        </li>
        <li class="b_algo">
            <h2><a href="https://test.com/page">Another Result</a></h2>
            <div class="b_caption"><p>Some snippet text.</p></div>
        </li>
        """
        results = _parse_bing(html, max_results=5)
        assert len(results) == 2
        assert results[0]["title"] == "Python Guide"
        assert results[0]["url"] == "https://example.com/guide"
        assert "great guide" in results[0]["snippet"]
        assert results[1]["title"] == "Another Result"
        assert results[1]["url"] == "https://test.com/page"

    def test_parse_bing_skips_internal_links(self):
        """Bing 内部链接应被跳过。"""
        from tools.web_tools import _parse_bing

        html = """
        <li class="b_algo">
            <h2><a href="https://www.bing.com/internal">Internal</a></h2>
            <div class="b_caption"><p>skip me</p></div>
        </li>
        <li class="b_algo">
            <h2><a href="https://real.com/page">Real Result</a></h2>
            <div class="b_caption"><p>keep me</p></div>
        </li>
        """
        results = _parse_bing(html, max_results=5)
        assert len(results) == 1
        assert results[0]["url"] == "https://real.com/page"


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
