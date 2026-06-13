"""CLI/REPL 层测试 — 覆盖交互层崩溃点。

之前 CLI/REPL 覆盖率仅 17%，交互层完全没有测试。
这组测试专门覆盖：
- _ask_user 输入处理（UnicodeDecodeError / 阻塞模式切换 / stdin 异常）
- slash commands（/q /reset /tools /session /unknown）
- _build_provider / _build_engine 工厂函数
- display 辅助函数（_guess_language / _display_tool_result 等）
- run_repl 主循环（模拟完整交互流程）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.repl import (
    _ask_user,
    _build_engine,
    _build_provider,
    _display_error,
    _display_footer,
    _display_provider,
    _display_thinking,
    _display_tool_header,
    _display_tool_result,
    _display_welcome,
    _get_model,
    _guess_language,
    run_repl,
)

# ============================================================================
# _ask_user 测试
# ============================================================================


class TestAskUser:
    """_ask_user 是 REPL 最核心的输入函数，之前完全没测。

    注意：_ask_user 内部调用 sys.stdin.fileno()（检查阻塞模式）+ Prompt.ask（读输入）。
    pytest 环境下 sys.stdin 是 pseudofile，没有 fileno()，需要 mock。
    """

    def _mock_stdin(self, monkeypatch):
        """给 _ask_user 提供一个可用的 mock stdin。"""
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        monkeypatch.setattr(sys, "stdin", mock_stdin)

    def test_normal_input(self, monkeypatch):
        """正常字符串输入应原样返回。"""
        self._mock_stdin(monkeypatch)
        monkeypatch.setattr("cli.repl.Prompt.ask", lambda _: "hello world")
        result = _ask_user("test prompt")
        assert result == "hello world"

    def test_unicode_input(self, monkeypatch):
        """中文/emoji 输入应正常工作。"""
        self._mock_stdin(monkeypatch)
        monkeypatch.setattr("cli.repl.Prompt.ask", lambda _: "你好 🌍")
        result = _ask_user("test")
        assert result == "你好 🌍"

    def test_empty_input(self, monkeypatch):
        """空输入返回空字符串。"""
        self._mock_stdin(monkeypatch)
        monkeypatch.setattr("cli.repl.Prompt.ask", lambda _: "")
        result = _ask_user("test")
        assert result == ""

    def test_unicode_decode_error_returns_empty(self, monkeypatch):
        """当终端产生非法 utf-8 字节时应返回空字符串，而不是崩溃。

        这是用户实际遇到的崩溃场景：输入 /session 后 UnicodeDecodeError。
        """
        self._mock_stdin(monkeypatch)

        def raise_unicode_decode_error(_):
            raise UnicodeDecodeError("utf-8", b"\xff\xfe", 0, 1, "invalid continuation byte")

        monkeypatch.setattr("cli.repl.Prompt.ask", raise_unicode_decode_error)
        result = _ask_user("test")
        assert result == ""

    def test_eof_error_propagates(self, monkeypatch):
        """EOFError 应正常传播（主循环捕获它来退出）。"""
        self._mock_stdin(monkeypatch)

        def raise_eof(_):
            raise EOFError

        monkeypatch.setattr("cli.repl.Prompt.ask", raise_eof)
        with pytest.raises(EOFError):
            _ask_user("test")

    def test_keyboard_interrupt_propagates(self, monkeypatch):
        """KeyboardInterrupt 应正常传播。"""
        self._mock_stdin(monkeypatch)

        def raise_ki(_):
            raise KeyboardInterrupt

        monkeypatch.setattr("cli.repl.Prompt.ask", raise_ki)
        with pytest.raises(KeyboardInterrupt):
            _ask_user("test")

    def test_blocking_mode_toggle(self, monkeypatch):
        """_ask_user 应临时把 stdin 设回阻塞模式。"""
        monkeypatch.setattr("cli.repl.Prompt.ask", lambda _: "ok")

        calls = []

        # 模拟非阻塞 stdin
        def fake_get_blocking(fd):
            calls.append(("get_blocking", fd))
            return False  # 非阻塞

        def fake_set_blocking(fd, blocking):
            calls.append(("set_blocking", fd, blocking))

        monkeypatch.setattr(os, "get_blocking", fake_get_blocking)
        monkeypatch.setattr(os, "set_blocking", fake_set_blocking)

        # 需要 stdin.fileno() 可用
        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        monkeypatch.setattr(sys, "stdin", mock_stdin)

        result = _ask_user("test")
        assert result == "ok"

        # 应该：检查是否非阻塞 -> 设为阻塞 -> 读取 -> 设回非阻塞
        blocking_sets = [c for c in calls if c[0] == "set_blocking"]
        assert len(blocking_sets) == 2
        assert blocking_sets[0] == ("set_blocking", 0, True)   # 设为阻塞
        assert blocking_sets[1] == ("set_blocking", 0, False)  # 恢复非阻塞

    def test_blocking_mode_already_blocking(self, monkeypatch):
        """stdin 已是阻塞模式时不应调用 set_blocking。"""
        monkeypatch.setattr("cli.repl.Prompt.ask", lambda _: "ok")

        set_calls = []

        def fake_get_blocking(fd):
            return True  # 已阻塞

        def fake_set_blocking(fd, blocking):
            set_calls.append(blocking)

        monkeypatch.setattr(os, "get_blocking", fake_get_blocking)
        monkeypatch.setattr(os, "set_blocking", fake_set_blocking)

        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        monkeypatch.setattr(sys, "stdin", mock_stdin)

        result = _ask_user("test")
        assert result == "ok"
        assert len(set_calls) == 0  # 不需要切换

    def test_blocking_mode_oserror_suppressed(self, monkeypatch):
        """get_blocking/set_blocking 抛 OSError 时应被忽略。"""
        monkeypatch.setattr("cli.repl.Prompt.ask", lambda _: "ok")

        def fake_get_blocking(fd):
            raise OSError("not a terminal")

        monkeypatch.setattr(os, "get_blocking", fake_get_blocking)

        mock_stdin = MagicMock()
        mock_stdin.fileno.return_value = 0
        monkeypatch.setattr(sys, "stdin", mock_stdin)

        # 不应崩溃
        result = _ask_user("test")
        assert result == "ok"


# ============================================================================
# _guess_language 测试
# ============================================================================


class TestGuessLanguage:
    """语言猜测逻辑覆盖。"""

    def test_python_tools(self):
        assert _guess_language("x = 1", "read_file") == "python"
        assert _guess_language("x = 1", "write_file") == "python"
        assert _guess_language("x = 1", "edit_file") == "python"

    def test_bash(self):
        assert _guess_language("ls -la", "bash") == "bash"

    def test_git_diff(self):
        assert _guess_language("diff --git a/x b/x", "git_diff") == "diff"
        assert _guess_language("just some log output", "git_log") == "text"

    def test_web(self):
        assert _guess_language("# Heading", "web_search") == "markdown"
        assert _guess_language("# Heading", "web_fetch") == "markdown"

    def test_unknown(self):
        assert _guess_language("anything", "unknown_tool") == "text"


# ============================================================================
# _display_provider 测试
# ============================================================================


class TestDisplayProvider:
    """_display_provider 名称映射。"""

    def test_known_providers(self):
        assert _display_provider("totoro") == "LongCat"
        assert _display_provider("openai") == "OpenAI"
        assert _display_provider("anthropic") == "Anthropic"

    def test_unknown_provider(self):
        assert _display_provider("unknown") == "unknown"


# ============================================================================
# _get_model 测试
# ============================================================================


class TestGetModel:
    """_get_model 根据配置返回模型名。"""

    def test_totoro_model(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "totoro"
        settings.totoro.model = "glm-4-plus"
        assert _get_model(settings) == "glm-4-plus"

    def test_openai_model(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "openai"
        settings.openai.model = "gpt-4"
        assert _get_model(settings) == "gpt-4"

    def test_anthropic_model(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "anthropic"
        settings.anthropic.model = "claude-3"
        assert _get_model(settings) == "claude-3"

    def test_unknown_model(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "unknown"
        assert _get_model(settings) == "(default)"


# ============================================================================
# _build_provider 测试
# ============================================================================


class TestBuildProvider:
    """_build_provider 工厂函数。"""

    def test_totoro_provider(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "totoro"
        settings.totoro.api_key = "test_key"
        settings.totoro.base_url = "https://test.example.com"
        settings.totoro.model = "glm-4-plus"
        provider = _build_provider(settings)
        assert provider is not None

    def test_openai_provider(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "openai"
        settings.openai.api_key = "test_key"
        settings.openai.base_url = "https://test.example.com"
        settings.openai.model = "gpt-4"
        provider = _build_provider(settings)
        assert provider is not None

    def test_anthropic_provider(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "anthropic"
        settings.anthropic.api_key = "test_key"
        settings.anthropic.model = "claude-3"
        provider = _build_provider(settings)
        assert provider is not None

    def test_unknown_provider_raises(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "invalid"
        with pytest.raises(ValueError, match="未知 provider"):
            _build_provider(settings)


# ============================================================================
# Display 函数测试（不崩溃即可）
# ============================================================================


class TestDisplayFunctions:
    """所有 display 函数应正常执行不崩溃。"""

    def test_display_welcome(self):
        settings = MagicMock()
        settings.resolve_provider.return_value = "totoro"
        settings.totoro.model = "glm-4-plus"
        settings.tool_preset = "core"
        _display_welcome(settings, "/test/path")

    def test_display_tool_header(self):
        _display_tool_header(1, "bash")

    def test_display_tool_result_python(self):
        _display_tool_result("read_file", "x = 1\ny = 2", "x = 1...")

    def test_display_tool_result_bash(self):
        _display_tool_result("bash", "echo hello", "echo h...")

    def test_display_tool_result_large(self):
        """超过 1500 字符的 Python 输出应截断。"""
        large_output = "x = 1\n" * 500
        large_preview = "x = 1..." * 10
        _display_tool_result("read_file", large_output, large_preview)

    def test_display_tool_result_empty(self):
        _display_tool_result("unknown_tool", "", "")

    def test_display_tool_result_list_dir(self):
        _display_tool_result("list_dir", "file1\nfile2\nfile3", "file1...")

    def test_display_footer(self):
        _display_footer(5)

    def test_display_error(self):
        _display_error("Something went wrong")

    def test_display_thinking(self):
        _display_thinking()


# ============================================================================
# run_repl 集成测试
# ============================================================================

def _make_mock_settings(tmp_path):
    """创建用于 REPL 测试的 mock settings。"""
    settings = MagicMock()
    settings.resolve_provider.return_value = "totoro"
    settings.totoro.api_key = "test_key"
    settings.totoro.base_url = "http://test"
    settings.totoro.model = "test-model"
    settings.tool_preset = "core"
    settings.max_iterations = 5
    settings.max_tokens = 4096
    settings.temperature = 0.7
    settings.session_dir = str(tmp_path / "test_session_repl")
    return settings


class TestRunReplSlashCommands:
    """模拟 REPL 主循环，测试 slash commands。

    需要同时 mock _ask_user（输入）和 _build_engine（避免创建真实 provider）。
    """

    @pytest.mark.asyncio
    async def test_quit_command(self, tmp_path):
        """输入 /q 应退出 REPL。"""
        inputs = iter(["/q"])
        mock_engine = MagicMock()
        mock_engine._tools.list_tools.return_value = []
        with (
            patch("cli.repl._ask_user", side_effect=lambda _: next(inputs)),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_exit_and_quit_variants(self, tmp_path):
        """测试所有退出命令。"""
        for cmd in ["/exit", "/quit", "/q"]:
            inputs = iter([cmd])
            mock_engine = MagicMock()
            mock_engine._tools.list_tools.return_value = []
            cmd_val = cmd
            with (
                patch("cli.repl._ask_user", side_effect=lambda _, iv=inputs: next(iv)),
                patch("cli.repl._build_engine", return_value=mock_engine),
            ):
                await run_repl(_make_mock_settings(tmp_path), ".")
            _ = cmd_val  # 避免未使用变量

    @pytest.mark.asyncio
    async def test_empty_input_skipped(self, tmp_path):
        """空输入应被跳过，不触发 Agent 执行。"""
        inputs = iter(["", "   ", "/q"])
        mock_engine = MagicMock()
        with (
            patch("cli.repl._ask_user", side_effect=lambda _: next(inputs)),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")
        # mock_engine.run_stream 不应被调用
        mock_engine.run_stream.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_command(self, tmp_path):
        """/reset 应重置会话。"""
        inputs = iter(["/reset", "/q"])
        mock_engine = MagicMock()
        with (
            patch("cli.repl._ask_user", side_effect=lambda _: next(inputs)),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_tools_command(self, tmp_path):
        """/tools 应展示工具列表。"""
        mock_tool = MagicMock()
        mock_tool.name = "bash"
        mock_tool.description = "Execute bash commands"

        inputs = iter(["/tools", "/q"])
        mock_engine = MagicMock()
        mock_engine._tools.list_tools.return_value = [mock_tool]
        with (
            patch("cli.repl._ask_user", side_effect=lambda _: next(inputs)),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_session_command(self, tmp_path):
        """/session 应展示会话信息——这是用户触发崩溃的命令。"""
        inputs = iter(["/session", "/q"])
        mock_engine = MagicMock()
        with (
            patch("cli.repl._ask_user", side_effect=lambda _: next(inputs)),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_unknown_slash_command(self, tmp_path):
        """未知 slash 命令应给出提示。"""
        inputs = iter(["/unknown", "/q"])
        mock_engine = MagicMock()
        with (
            patch("cli.repl._ask_user", side_effect=lambda _: next(inputs)),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_eof_exits_gracefully(self, tmp_path):
        """EOF 应优雅退出。"""
        def raise_eof(_):
            raise EOFError

        mock_engine = MagicMock()
        with (
            patch("cli.repl._ask_user", side_effect=raise_eof),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_exits_gracefully(self, tmp_path):
        """Ctrl+C 应优雅退出。"""
        def raise_ki(_):
            raise KeyboardInterrupt

        mock_engine = MagicMock()
        with (
            patch("cli.repl._ask_user", side_effect=raise_ki),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_os_error_exits_gracefully(self, tmp_path):
        """OSError（stdin 管道问题）应优雅退出。"""
        def raise_os_error(_):
            raise OSError("Bad file descriptor")

        mock_engine = MagicMock()
        with (
            patch("cli.repl._ask_user", side_effect=raise_os_error),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_agent_execution_with_stream(self, tmp_path):
        """普通输入应触发 Agent 执行。"""
        inputs = iter(["hello", "/q"])
        mock_engine = MagicMock()

        async def mock_run_stream(*args, **kwargs):
            yield {"type": "text_delta", "content": "Hello!"}
            yield {"type": "tool_call_start", "tool": "bash"}
            yield {"type": "tool_result", "success": True, "output": "ok", "output_preview": "ok", "tool": "bash"}
            yield {"type": "done"}
            yield {"type": "final", "iterations": 1}

        mock_engine.run_stream = mock_run_stream

        with (
            patch("cli.repl._ask_user", side_effect=lambda _: next(inputs)),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")

    @pytest.mark.asyncio
    async def test_agent_execution_error(self, tmp_path):
        """Agent 执行中的异常应被捕获，不崩溃 REPL。"""
        inputs = iter(["hello", "/q"])
        mock_engine = MagicMock()

        async def mock_run_stream(*args, **kwargs):
            raise RuntimeError("API error")
            yield  # never reached

        mock_engine.run_stream = mock_run_stream

        with (
            patch("cli.repl._ask_user", side_effect=lambda _: next(inputs)),
            patch("cli.repl._build_engine", return_value=mock_engine),
        ):
            await run_repl(_make_mock_settings(tmp_path), ".")


# ============================================================================
# _build_engine 测试
# ============================================================================


class TestBuildEngine:
    """_build_engine 工厂函数。"""

    def test_build_engine_totoro(self, tmp_path):
        settings = MagicMock()
        settings.resolve_provider.return_value = "totoro"
        settings.totoro.api_key = "test_key"
        settings.totoro.base_url = "https://test.example.com"
        settings.totoro.model = "glm-4-plus"
        settings.tool_preset = "core"
        settings.max_iterations = 10
        settings.max_tokens = 4096
        settings.temperature = 0.7
        settings.session_dir = str(tmp_path / "sessions")

        engine = _build_engine(settings, str(tmp_path))
        assert engine is not None


# ============================================================================
# cli/main.py 测试
# ============================================================================


class TestCliMain:
    """cli/main.py 入口测试。"""

    def test_main_no_args_calls_repl(self, monkeypatch):
        """无参数时 main() 应调用 cmd_repl。"""
        called = []
        monkeypatch.setattr("cli.main.cmd_repl", lambda args: called.append(args))
        monkeypatch.setattr(sys, "argv", ["totoro"])
        from cli.main import main

        main()
        assert called == [[]]

    def test_main_repl_subcommand(self, monkeypatch):
        """totoro repl 应调用 cmd_repl。"""
        called = []
        monkeypatch.setattr("cli.main.cmd_repl", lambda args: called.append(args))
        monkeypatch.setattr(sys, "argv", ["totoro", "repl"])
        from cli.main import main

        main()
        assert called == [[]]

    def test_main_r_alias(self, monkeypatch):
        """totoro r 应调用 cmd_repl。"""
        called = []
        monkeypatch.setattr("cli.main.cmd_repl", lambda args: called.append(args))
        monkeypatch.setattr(sys, "argv", ["totoro", "r", "/some/path"])
        from cli.main import main

        main()
        assert called == [["/some/path"]]

    def test_main_status_subcommand(self, monkeypatch):
        """totoro status 应调用 cmd_status。"""
        called = []
        monkeypatch.setattr("cli.main.cmd_status", lambda: called.append(True))
        monkeypatch.setattr(sys, "argv", ["totoro", "status"])
        from cli.main import main

        main()
        assert called == [True]

    def test_main_help_subcommand(self, monkeypatch, capsys):
        """totoro help 应打印文档。"""
        monkeypatch.setattr(sys, "argv", ["totoro", "help"])
        from cli.main import main

        main()
        captured = capsys.readouterr()
        assert "totoro" in captured.out.lower()

    def test_cmd_repl_calls_repl_main(self, monkeypatch):
        """cmd_repl 应调用 repl.main。"""
        repl_called = []

        def fake_repl_main():
            repl_called.append(True)

        monkeypatch.setattr("cli.repl.main", fake_repl_main)
        from cli.main import cmd_repl

        cmd_repl([])
        assert repl_called == [True]

    def test_cmd_repl_sets_argv(self, monkeypatch):
        """cmd_repl 应设置 sys.argv。"""
        captured_argv = []

        def fake_repl_main():
            captured_argv.append(list(sys.argv))

        monkeypatch.setattr("cli.repl.main", fake_repl_main)
        from cli.main import cmd_repl

        cmd_repl(["--provider", "openai"])
        assert captured_argv[0] == ["totoro-repl", "--provider", "openai"]
