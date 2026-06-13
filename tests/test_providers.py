"""测试 providers/ — Provider 注册表和协议。"""
import pytest
from providers.base import (
    ChatProvider,
    ChatResponse,
    StreamEvent,
    ToolCall,
    ToolCallDefinition,
    TokenUsage,
)
from providers.registry import ProviderRegistry
from unittest.mock import MagicMock


class TestTokenUsage:
    def test_defaults(self):
        u = TokenUsage()
        assert u.input_tokens == 0
        assert u.output_tokens == 0
        assert u.total_tokens == 0

    def test_custom(self):
        u = TokenUsage(input_tokens=100, output_tokens=50)
        assert u.input_tokens == 100
        assert u.output_tokens == 50


class TestToolCallDefinition:
    def test_to_anthropic_dict(self):
        t = ToolCallDefinition(
            name="read_file",
            description="Read a file.",
            parameters_schema={"type": "object"},
        )
        d = t.to_anthropic_dict()
        assert d["name"] == "read_file"
        assert d["input_schema"] == {"type": "object"}

    def test_to_openai_dict(self):
        t = ToolCallDefinition(
            name="read_file",
            description="Read a file.",
            parameters_schema={"type": "object"},
        )
        d = t.to_openai_dict()
        assert d["type"] == "function"
        assert d["function"]["name"] == "read_file"


class TestChatResponse:
    def test_text_only(self):
        r = ChatResponse(text="hello", usage=TokenUsage())
        assert r.text == "hello"
        assert r.tool_calls == []

    def test_with_tool_calls(self):
        tc = ToolCall(id="c1", name="bash", arguments={"command": "ls"})
        r = ChatResponse(text="Let me check.", tool_calls=[tc], usage=TokenUsage())
        assert len(r.tool_calls) == 1
        assert r.tool_calls[0].name == "bash"


class TestStreamEvent:
    def test_text_delta(self):
        e = StreamEvent(type="text_delta", content="hello")
        assert e.type == "text_delta"
        assert e.content == "hello"

    def test_tool_call_start(self):
        e = StreamEvent(type="tool_call_start", tool_name="bash", tool_arguments={"command": "ls"})
        assert e.tool_name == "bash"

    def test_done_with_usage(self):
        e = StreamEvent(type="done", usage=TokenUsage(input_tokens=10, output_tokens=5))
        assert e.usage.input_tokens == 10


class TestProviderRegistry:
    def test_register_and_get(self):
        provider = MagicMock(spec=ChatProvider)
        ProviderRegistry.register("test_backend", provider)
        assert ProviderRegistry.get("test_backend") is provider

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="not registered"):
            ProviderRegistry.get("nonexistent")

    def test_list_providers(self):
        provider = MagicMock(spec=ChatProvider)
        ProviderRegistry.register("list_test", provider)
        providers = ProviderRegistry.list_providers()
        assert "list_test" in providers

    def test_clear(self):
        ProviderRegistry.clear()
        assert ProviderRegistry.list_providers() == []


# ─── 测试每个 Provider 的实例化 ────────────────────────────


class TestProviderInstantiation:
    """测试各 Provider 能正确实例化（不调用真实 API）。"""

    def test_totoro_provider(self):
        from providers.totoro_provider import TotoroProvider
        p = TotoroProvider(api_key="test_key")
        assert p._api_key == "test_key"
        assert "longcat.chat" in p._base_url

    def test_totoro_provider_default_url(self):
        from providers.totoro_provider import TotoroProvider
        p = TotoroProvider(api_key="k")
        assert p._base_url == "https://api.longcat.chat/anthropic/v1/messages"

    def test_openai_provider(self):
        from providers.openai_provider import OpenAIProvider
        p = OpenAIProvider(api_key="test_key")
        assert p._api_key == "test_key"
        assert "openai.com" in p._base_url

    def test_anthropic_provider(self):
        from providers.anthropic_provider import AnthropicProvider
        p = AnthropicProvider(api_key="test_key")
        assert p._api_key == "test_key"


