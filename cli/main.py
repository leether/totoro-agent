"""Totoro Agent — 统一 CLI 入口。

用法:
    totoro                     # 启动 REPL（默认）
    totoro repl                # 启动 REPL
    totoro chat "你好"         # 单轮对话
    totoro chat "你好" --stream # 流式单轮对话
    totoro status              # 显示配置状态
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_repl(args: list[str]) -> None:
    """启动交互式 REPL。"""
    from cli.repl import main as repl_main

    sys.argv = ["totoro-repl"] + args
    repl_main()


def cmd_chat(args: list[str]) -> None:
    """单轮对话模式。"""
    import argparse

    parser = argparse.ArgumentParser(prog="totoro chat")
    parser.add_argument("message", help="要发送的消息")
    parser.add_argument("--stream", "-s", action="store_true", help="流式输出")
    parser.add_argument("--system", default=None, help="系统提示词")
    parsed = parser.parse_args(args)

    asyncio.run(_chat_impl(parsed.message, parsed.stream, parsed.system))


async def _chat_impl(message: str, stream: bool, system: str | None) -> None:
    """异步实现单轮对话。"""
    from config import AgentSettings
    from providers.anthropic_provider import AnthropicProvider
    from providers.openai_provider import OpenAIProvider
    from providers.totoro_provider import TotoroProvider

    settings = AgentSettings()
    provider_name = settings.resolve_provider()

    provider: object
    if provider_name == "totoro":
        provider = TotoroProvider(
            api_key=settings.totoro.api_key,
            base_url=settings.totoro.base_url,
            model=settings.totoro.model,
        )
    elif provider_name == "openai":
        provider = OpenAIProvider(
            api_key=settings.openai.api_key,
            base_url=settings.openai.base_url,
            model=settings.openai.model,
        )
    elif provider_name == "anthropic":
        provider = AnthropicProvider(
            api_key=settings.anthropic.api_key,
            model=settings.anthropic.model,
        )
    else:
        print(f"❌ 未知 provider: {provider_name}")
        sys.exit(1)

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    if stream:
        stream_chat = provider.stream_chat
        async for event in stream_chat(messages):
            if event.type == "text_delta":
                print(event.content, end="", flush=True)
        print()
    else:
        chat = provider.chat
        response = await chat(messages)
        print(response.text)


def cmd_status() -> None:
    """显示当前配置状态。"""
    from config import AgentSettings

    settings = AgentSettings()
    provider = settings.resolve_provider()
    model = _get_model(settings)

    match provider:
        case "totoro":
            key_set = bool(settings.totoro.api_key)
        case "openai":
            key_set = bool(settings.openai.api_key)
        case "anthropic":
            key_set = bool(settings.anthropic.api_key)
        case _:
            key_set = False

    key_status = "✅ 已设置" if key_set else "❌ 未设置"

    print("🐾 Totoro Agent 配置")
    print(f"  Provider:    {provider}")
    print(f"  Model:       {model}")
    print(f"  Tool preset: {settings.tool_preset}")
    print(f"  Max iter:    {settings.max_iterations}")
    print(f"  Max tokens:  {settings.max_tokens}")
    print(f"  Temperature: {settings.temperature}")
    print(f"  Session dir: {settings.session_dir}")
    print(f"  API Key:     {key_status}")


def _get_model(settings: object) -> str:
    provider = settings.resolve_provider()  # type: ignore[attr-defined]
    match provider:
        case "totoro":
            return settings.totoro.model  # type: ignore[attr-defined, no-any-return]
        case "openai":
            return settings.openai.model  # type: ignore[attr-defined, no-any-return]
        case "anthropic":
            return settings.anthropic.model  # type: ignore[attr-defined, no-any-return]
        case _:
            return "(default)"


def main() -> None:
    """统一 CLI 入口。"""
    if len(sys.argv) < 2:
        cmd_repl([])
        return

    subcommand = sys.argv[1]
    rest = sys.argv[2:]

    match subcommand:
        case "repl" | "r":
            cmd_repl(rest)
        case "chat" | "c":
            cmd_chat(rest)
        case "status" | "s":
            cmd_status()
        case "help" | "-h" | "--help":
            print(__doc__)
        case _:
            cmd_chat(sys.argv[1:])


if __name__ == "__main__":
    main()
