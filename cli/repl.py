"""交互式 REPL — Rich 美化的 Coding Agent 终端界面。"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from providers.base import ChatProvider
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

from agent.context import Session
from agent.engine import AgentConfig, AgentEngine
from config import AgentSettings
from providers.anthropic_provider import AnthropicProvider
from providers.openai_provider import OpenAIProvider
from providers.totoro_provider import TotoroProvider
from tools.registry import ToolRegistry

# ─── 配色方案 ───────────────────────────────────────────
AGENT_COLOR = "cyan"        # Agent 名称 & 标题
USER_COLOR = "green"        # 用户输入
TOOL_COLOR = "yellow"       # 工具调用
SUCCESS_COLOR = "green"    # 成功标记
ERROR_COLOR = "red"        # 错误标记
CODE_THEME = "monokai"     # 代码高亮主题

_console = Console()


# ─── Tool display detection helpers ─────────────────────

def _guess_language(output: str, tool_name: str) -> str:
    """根据工具名和输出内容猜测语言用于语法高亮。"""
    if tool_name in ("read_file", "write_file", "edit_file"):
        return "python"
    if tool_name == "bash":
        return "bash"
    if tool_name in ("git_status", "git_diff", "git_log"):
        return "diff" if "diff" in output[:200] else "text"
    if tool_name in ("web_search", "web_fetch"):
        return "markdown"
    return "text"


def _display_tool_result(tool_name: str, output: str, output_preview: str) -> None:
    """根据工具类型选择合适的 Rich 渲染方式。"""
    lang = _guess_language(output, tool_name)

    if lang in ("python", "javascript", "typescript", "bash", "json"):
        display_text = output if len(output) <= 1500 else output_preview
        syntax = Syntax(display_text, lang, theme=CODE_THEME, line_numbers=(lang == "python"))
        _console.print(Panel(syntax, title=f"[bold {TOOL_COLOR}]{tool_name}[/]", border_style=TOOL_COLOR))
    elif tool_name == "list_dir":
        # 目录列表直接输出文本
        _console.print(Panel(output[:2000], title=f"[bold {TOOL_COLOR}]{tool_name}[/]", border_style=TOOL_COLOR))
    else:
        # 通用输出：截断 + panel
        display_text = output[:2000] if output else "(empty)"
        _console.print(Panel(display_text, title=f"[bold {TOOL_COLOR}]{tool_name}[/]", border_style=TOOL_COLOR))


def _display_welcome(settings: AgentSettings, project_path: str) -> None:
    """渲染欢迎面板。"""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("key", style="bold")
    table.add_column("value")
    table.add_row("Provider", f"[{AGENT_COLOR}]{settings.resolve_provider()}[/]")
    table.add_row("Project", f"[{AGENT_COLOR}]{project_path}[/]")
    table.add_row("Tools", f"[{AGENT_COLOR}]{settings.tool_preset}[/]")
    table.add_row("Model", f"[{AGENT_COLOR}]{_get_model(settings)}[/]")

    panel = Panel(
        table,
        title="[bold]  🐾 Totoro Coding Agent[/]",
        subtitle="[dim]/q 退出 | /reset 重置 | /tools 工具 | /session 会话[/]",
        border_style=AGENT_COLOR,
        padding=(1, 2),
    )
    _console.print(panel)


def _get_model(settings: AgentSettings) -> str:
    provider = settings.resolve_provider()
    match provider:
        case "totoro":
            return settings.totoro.model
        case "openai":
            return settings.openai.model
        case "anthropic":
            return settings.anthropic.model
        case _:
            return "(default)"


def _display_tool_header(count: int, tool_name: str) -> None:
    """渲染工具调用头。"""
    _console.print(
        f"\n[bold {TOOL_COLOR}]🔧 [{count}] {tool_name}[/] "
        f"[dim]executing...[/]",
        end="",
    )


def _display_footer(iterations: int) -> None:
    """渲染会话末尾统计。"""
    _console.print()
    stats = Table(show_header=False, box=None)
    stats.add_column("label", style="dim")
    stats.add_column("value")
    stats.add_row("迭代次数", str(iterations))
    panel = Panel(stats, border_style="dim", padding=(0, 1))
    _console.print(panel)


def _display_error(error: str) -> None:
    """渲染错误面板。"""
    _console.print(Panel(
        f"[bold {ERROR_COLOR}]{error}[/]",
        title=f"[bold {ERROR_COLOR}]❌ Error[/]",
        border_style=ERROR_COLOR,
    ))


def _display_thinking() -> None:
    """渲染思考中状态。"""
    _console.print(f"\n[bold {AGENT_COLOR}]← Agent[/] [dim]thinking ...[/]", end="")


# ─── Setup helpers ───────────────────────────────────────

def _build_provider(settings: AgentSettings) -> ChatProvider:
    """根据配置构建 provider。"""
    name = settings.resolve_provider()
    if name == "totoro":
        return TotoroProvider(  # type: ignore[return-value]
            api_key=settings.totoro.api_key,
            base_url=settings.totoro.base_url,
            model=settings.totoro.model,
        )
    elif name == "openai":
        return OpenAIProvider(  # type: ignore[return-value]
            api_key=settings.openai.api_key,
            base_url=settings.openai.base_url,
            model=settings.openai.model,
        )
    elif name == "anthropic":
        return AnthropicProvider(  # type: ignore[return-value]
            api_key=settings.anthropic.api_key,
            model=settings.anthropic.model,
        )
    else:
        raise ValueError(f"未知 provider: {name}")


def _build_engine(settings: AgentSettings, project_path: str = "") -> AgentEngine:
    """组装完整 AgentEngine。"""
    provider = _build_provider(settings)

    tool_registry = ToolRegistry()
    tool_registry.load_preset(settings.tool_preset)

    config = AgentConfig(
        max_iterations=settings.max_iterations,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        tool_preset=settings.tool_preset,
        session_dir=settings.session_dir,
    )

    return AgentEngine.create(
        provider=provider,
        config=config,
        tool_preset=settings.tool_preset,
        project_path=project_path,
    )


# ─── REPL main ───────────────────────────────────────────

def main() -> None:
    """CLI 入口: longcat-repl [project_path]."""
    import argparse
    parser = argparse.ArgumentParser(description="LongCat Coding Agent REPL")
    parser.add_argument("project_path", nargs="?", default=".", help="项目路径（默认当前目录）")
    parser.add_argument("--provider", "-p", default=None, help="Provider: longcat / openai / anthropic")
    parser.add_argument("--tools", "-t", default=None, choices=["core", "full", "readonly"], help="工具预设")
    args = parser.parse_args()

    settings = AgentSettings()
    if args.provider:
        settings.provider_name = args.provider
    if args.tools:
        settings.tool_preset = args.tools

    asyncio.run(run_repl(settings, args.project_path))


async def run_repl(settings: AgentSettings, project_path: str = ".") -> None:
    """启动交互式 REPL。"""
    project_path = str(Path(project_path).resolve())
    engine = _build_engine(settings, project_path)
    session = Session(id=f"repl_{uuid.uuid4().hex[:8]}")

    _display_welcome(settings, project_path)

    while True:
        try:
            user_input = await asyncio.to_thread(
                Prompt.ask, f"\n[bold {USER_COLOR}]❯ User[/]"
            )
            user_input = user_input.strip()
        except (EOFError, KeyboardInterrupt):
            _console.print("\n[dim]Bye![/]")
            break

        if not user_input:
            continue

        # ─── Slash commands ───
        if user_input in ("/q", "/quit", "/exit"):
            _console.print("[dim]Bye![/]")
            break

        if user_input == "/reset":
            session = Session(id=f"repl_{uuid.uuid4().hex[:8]}")
            _console.print("[dim]⟳ 会话已重置[/]")
            continue

        if user_input == "/tools":
            tools_table = Table(title="[bold]已注册工具[/]", border_style=AGENT_COLOR)
            tools_table.add_column("Name", style=TOOL_COLOR)
            tools_table.add_column("Description")
            for tool in engine._tools.list_tools():
                tools_table.add_row(tool.name, tool.description[:80])
            _console.print(tools_table)
            continue

        if user_input == "/session":
            info = Table(show_header=False, box=None)
            info.add_column("key", style="bold")
            info.add_column("value")
            info.add_row("Session ID", session.id)
            info.add_row("Messages", str(len(session.messages)))
            _console.print(Panel(info, title="[bold]会话信息[/]", border_style=AGENT_COLOR))
            continue

        if user_input.startswith("/"):
            _console.print(f"[dim]未知命令: {user_input}[/]")
            continue

        # ─── Agent execution ───
        _console.print()
        tool_call_count = 0
        _display_thinking()

        try:
            async for event in engine.run_stream(user_input, session):
                etype = event.get("type")

                if etype == "text_delta":
                    _console.print(event["content"], end="", style=AGENT_COLOR, highlight=False)

                elif etype == "tool_call_start":
                    tool_call_count += 1
                    tool_name = event.get("tool", "?")
                    _display_tool_header(tool_call_count, tool_name)

                elif etype == "tool_result":
                    success = event.get("success", False)
                    output = event.get("output", "")
                    output_preview = event.get("output_preview", "")

                    # 清除 "executing..." 行尾
                    _console.print("", end="")

                    tool_name = event.get("tool", "")
                    _display_tool_result(tool_name, output, output_preview)

                    status = "✓" if success else "✗"
                    status_color = SUCCESS_COLOR if success else ERROR_COLOR
                    _console.print(f"  [{status_color}]{status}[/]")

                elif etype == "done":
                    # Stream done event — may have usage info
                    pass

                elif etype == "final":
                    iterations = event.get("iterations", "?")
                    _display_footer(iterations)

        except Exception as e:
            _display_error(str(e))

    # Save session
    session_dir = Path(settings.session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    session.save(str(session_dir))
    _console.print(f"[dim]💾 会话已保存: {session.id}[/]")
