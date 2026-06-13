"""测试 agent/engine.py — AgentEngine。"""
import pytest

from agent.context import ContextManager, Session
from agent.engine import AgentConfig, AgentEngine, AgentResponse
from providers.base import ChatResponse, ToolCall, TokenUsage
from tests.conftest import MockProvider
from tools.registry import ToolRegistry


class TestAgentConfig:
    def test_defaults(self):
        config = AgentConfig()
        assert config.max_iterations == 50
        assert config.max_tokens == 4096
        assert config.temperature == 0.1
        assert config.tool_preset == "full"

    def test_custom(self):
        config = AgentConfig(max_iterations=10, temperature=0.5)
        assert config.max_iterations == 10
        assert config.temperature == 0.5


class TestAgentEngine:
    @pytest.mark.asyncio
    async def test_run_text_only(self, mock_provider):
        """纯文本响应，无 tool_calls → 直接返回。"""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=ToolRegistry(),
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=5),
        )
        session = Session(id="test_run")
        result = await engine.run("Hello", session)

        assert isinstance(result, AgentResponse)
        assert result.message == "Hello from mock!"
        assert result.finished is True
        assert result.iterations == 1
        assert result.session_id == "test_run"

    @pytest.mark.asyncio
    async def test_run_with_tool_call(self, mock_provider_with_tool_call):
        """有 tool_calls → 执行工具 → 再次调用 LLM → 返回最终文本。"""
        registry = ToolRegistry()
        registry.load_preset("core")

        engine = AgentEngine(
            provider=mock_provider_with_tool_call,
            tool_registry=registry,
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=5),
        )
        session = Session(id="test_tool")
        result = await engine.run("Read a file", session)

        assert result.finished is True
        assert result.message == "The file contains a hello world function."
        assert result.iterations == 2  # 第一次带 tool_call，第二次纯文本
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["tool"] == "read_file"

    @pytest.mark.asyncio
    async def test_run_stream(self, mock_provider):
        """流式运行应 yield 正确的事件序列。"""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=ToolRegistry(),
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=5),
        )
        session = Session(id="test_stream")

        events = []
        async for event in engine.run_stream("Hello", session):
            events.append(event)

        # 应有 text_delta 和 final 事件
        types = [e["type"] for e in events]
        assert "text_delta" in types
        assert "final" in types

        # final 事件包含完整消息
        final = [e for e in events if e["type"] == "final"][0]
        assert final["message"] == "Hello from mock!"

    @pytest.mark.asyncio
    async def test_max_iterations(self, mock_provider):
        """达到最大迭代次数应停止。"""
        # 每次返回带 tool_call 的响应，迫使循环继续
        tool_call = ToolCall(id="call_x", name="read_file", arguments={"path": "/x"})
        resp = ChatResponse(
            text="thinking...",
            tool_calls=[tool_call],
            usage=TokenUsage(),
        )
        provider = MockProvider(responses=[resp] * 10)  # 永远返回 tool_call

        registry = ToolRegistry()
        registry.load_preset("core")

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=3),
        )
        session = Session(id="test_max_iter")
        result = await engine.run("loop test", session)

        assert result.finished is False
        assert result.iterations == 3

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """调用不存在的工具应返回错误 ToolResult。"""
        tool_call = ToolCall(id="call_bad", name="nonexistent_tool", arguments={})
        resp = ChatResponse(
            text="",
            tool_calls=[tool_call],
            usage=TokenUsage(),
        )
        final_resp = ChatResponse(text="Done", usage=TokenUsage())
        provider = MockProvider(responses=[resp, final_resp])

        engine = AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),  # 空注册表
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=5),
        )
        session = Session(id="test_unknown_tool")
        result = await engine.run("test", session)

        assert result.finished is True
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["success"] is False

    def test_create_factory(self, mock_provider):
        """AgentEngine.create() 工厂方法应正确组装。"""
        engine = AgentEngine.create(
            provider=mock_provider,
            tool_preset="readonly",
            project_path="/test/project",
        )
        assert engine._provider is mock_provider
        assert len(engine._tools) == 3  # readonly: read_file, list_dir, search_file

    @pytest.mark.asyncio
    async def test_session_messages_updated(self, mock_provider):
        """运行后 session.messages 应包含 user 和 assistant 消息。"""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=ToolRegistry(),
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=5),
        )
        session = Session(id="test_msgs")
        await engine.run("Hello", session)

        assert len(session.messages) == 2  # user + assistant
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"
