"""崩溃边界测试 — 专门针对 Coding Agent 实际使用中可能遇到的崩溃场景。

覆盖范围:
  1. Provider 层: 空响应 / 畸形 JSON / 网络错误 / SSE 解析异常
  2. Context 层: 空消息 / 巨大消息 / 压缩边界 / Session 持久化异常
  3. Engine 层: 空 tool_call / 多 tool_call 循环 / 工具参数类型错误
  4. 工具层: 不存在路径 / 权限问题 / 超大输出 / 正则炸弹 / 并发写入
  5. 配置层: 环境变量缺失 / 非法值
  6. validate_payload: 各种畸形 payload
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from agent.context import ContextManager, Session
from agent.engine import AgentConfig, AgentEngine
from providers.base import (
    ChatResponse,
    TokenUsage,
    ToolCall,
    ToolCallDefinition,
    validate_payload,
)
from tests.conftest import MockProvider
from tools.base import ToolResult
from tools.registry import ToolRegistry

# ============================================================================
# 1. Provider 层 — TotoroProvider 崩溃测试
# ============================================================================


class TestTotoroProviderCrash:
    """TotoroProvider 的各种畸形输入和异常场景。"""

    def test_parse_response_empty_content(self):
        """空 content 列表不应崩溃。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        resp = provider._parse_response({"content": []})
        assert resp.text == ""
        assert resp.tool_calls == []

    def test_parse_response_missing_content_key(self):
        """完全没有 content key 不应崩溃。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        resp = provider._parse_response({})
        assert resp.text == ""
        assert resp.tool_calls == []

    def test_parse_response_none_stop_reason(self):
        """stop_reason 为 None 时应回退为 'stop'。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        resp = provider._parse_response({"stop_reason": None})
        assert resp.finish_reason == "stop"

    def test_parse_response_tool_use_missing_input(self):
        """tool_use block 缺少 input 字段。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        resp = provider._parse_response(
            {
                "content": [
                    {"type": "tool_use", "id": "tc1", "name": "bash"},
                    # 缺少 input
                ]
            }
        )
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].arguments == {}

    def test_parse_response_unknown_block_type(self):
        """未知的 content block type 应被忽略，不崩溃。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        resp = provider._parse_response(
            {
                "content": [
                    {"type": "unknown_type", "data": "whatever"},
                    {"type": "text", "text": "hello"},
                ]
            }
        )
        assert resp.text == "hello"

    def test_parse_response_usage_missing(self):
        """完全缺少 usage 字段。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        resp = provider._parse_response({"content": [{"type": "text", "text": "ok"}]})
        assert resp.usage.input_tokens == 0
        assert resp.usage.output_tokens == 0

    def test_parse_sse_event_malformed_json(self):
        """畸形 JSON 的 data 行应返回 None，不崩溃。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        assert provider._parse_sse_event("data: {broken json") is None

    def test_parse_sse_event_non_data_line(self):
        """非 data: 开头的行应返回 None。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        assert provider._parse_sse_event("event: ping") is None
        assert provider._parse_sse_event("") is None

    def test_parse_sse_event_done(self):
        """[DONE] 标记应正确解析。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        result = provider._parse_sse_event("data: [DONE]")
        assert result == {"type": "message_stop"}

    def test_build_payload_empty_messages(self):
        """空 messages 列表应触发校验异常。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        with pytest.raises(ValueError, match="请求校验失败"):
            provider._build_payload([], None, 4096, 0.1)

    def test_build_payload_with_system_prompt(self):
        """system prompt 应被正确提取。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        payload = provider._build_payload(
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hi"},
            ],
            None,
            4096,
            0.1,
        )
        assert payload["system"] == "You are helpful."
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

    def test_headers_stream_flag(self):
        """stream 参数应改变 accept header。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        non_stream_headers = provider._headers(stream=False)
        stream_headers = provider._headers(stream=True)
        assert non_stream_headers["accept"] == "application/json"
        assert stream_headers["accept"] == "text/event-stream"

    def test_headers_contain_client_identity(self):
        """客户端身份头应存在。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        h = provider._headers()
        assert "User-Agent" in h
        assert "x-client-name" in h
        assert "x-client-version" in h

    def test_serialize_tools(self):
        """工具序列化应正确输出 Anthropic 格式。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        tools = [
            ToolCallDefinition(
                name="bash", description="Run bash", parameters_schema={"type": "object"}
            ),
        ]
        result = provider._serialize_tools(tools)
        assert result[0]["name"] == "bash"
        assert result[0]["input_schema"] == {"type": "object"}

    @pytest.mark.asyncio
    async def test_chat_with_mock_httpx_500_retry(self):
        """5xx 应触发重试，最终全部失败时抛异常。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test", max_retries=1)
        provider._timeout = 1

        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.request = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=mock_response.request, response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        provider._client = mock_client

        with pytest.raises((httpx.HTTPStatusError, Exception)):
            await provider.chat([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_chat_with_mock_httpx_success(self):
        """Mock 一个成功的 HTTP 响应。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Hello!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        provider._client = mock_client

        result = await provider.chat([{"role": "user", "content": "hi"}])
        assert result.text == "Hello!"
        assert result.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_close_client_idempotent(self):
        """close() 多次调用不应崩溃。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        await provider.close()  # 没创建过 client
        await provider.close()  # 再关一次

    def test_get_client_creates_once(self):
        """_get_client 应只创建一次客户端。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")
        c1 = provider._get_client()
        c2 = provider._get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_check_api_health_failure(self):
        """健康检查失败时应返回 False，不崩溃。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test", base_url="http://localhost:1")

        # 健康检查应该异常但不崩溃
        result = await provider.check_api_health()
        assert result is False


# ============================================================================
# 2. Provider 层 — OpenAIProvider 解析测试
# ============================================================================


class TestOpenAIProviderCrash:
    """OpenAIProvider 的畸形输入场景。"""

    def test_parse_empty_choices(self):
        """空 choices 不应崩溃。"""
        from providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="test")
        resp = provider._parse_response({})
        assert resp.text == ""
        assert resp.tool_calls == []

    def test_parse_malformed_tool_call_arguments(self):
        """畸形 tool_call arguments JSON 应回退为空 dict。"""
        from providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="test")
        resp = provider._parse_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": "thinking",
                            "tool_calls": [
                                {
                                    "id": "tc1",
                                    "function": {
                                        "name": "bash",
                                        "arguments": "{broken json}",
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            }
        )
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].arguments == {}

    def test_parse_none_content(self):
        """message.content 为 None 时不应崩溃。"""
        from providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="test")
        resp = provider._parse_response(
            {
                "choices": [
                    {
                        "message": {"content": None},
                        "finish_reason": "stop",
                    }
                ],
            }
        )
        assert resp.text == ""

    def test_parse_none_finish_reason(self):
        """finish_reason 为 None 时应回退为 'stop'。"""
        from providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="test")
        resp = provider._parse_response(
            {
                "choices": [
                    {
                        "message": {"content": "ok"},
                        "finish_reason": None,
                    }
                ],
            }
        )
        assert resp.finish_reason == "stop"


# ============================================================================
# 3. Provider 层 — AnthropicProvider 解析测试
# ============================================================================


class TestAnthropicProviderCrash:
    """AnthropicProvider 的畸形输入场景。"""

    def test_parse_empty_response(self):
        """空响应不应崩溃。"""
        from providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key="test")
        resp = provider._parse_response({})
        assert resp.text == ""

    def test_parse_tool_use_missing_fields(self):
        """tool_use block 缺少 name/id/input。"""
        from providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key="test")
        resp = provider._parse_response(
            {
                "content": [{"type": "tool_use"}],
            }
        )
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].id == ""
        assert resp.tool_calls[0].name == ""

    def test_headers_contain_api_key(self):
        """header 应包含 x-api-key。"""
        from providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key="my_secret")
        h = provider._headers()
        assert h["x-api-key"] == "my_secret"
        assert h["anthropic-version"] == "2023-06-01"


# ============================================================================
# 4. validate_payload — 全面的校验测试
# ============================================================================


class TestValidatePayloadCrash:
    """validate_payload 的各种畸形输入。"""

    def test_valid_payload(self):
        payload = {
            "model": "gpt-4",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.5,
        }
        assert validate_payload(payload) == []

    def test_empty_model(self):
        errors = validate_payload(
            {
                "model": "",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.5,
            }
        )
        assert any("model" in e for e in errors)

    def test_missing_model(self):
        errors = validate_payload(
            {
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.5,
            }
        )
        assert any("model" in e for e in errors)

    def test_max_tokens_zero(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 0,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        assert any("max_tokens" in e for e in errors)

    def test_max_tokens_negative(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": -10,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        assert any("max_tokens" in e for e in errors)

    def test_max_tokens_string(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": "100",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        assert any("max_tokens" in e for e in errors)

    def test_max_tokens_float(self):
        """浮点数不应被接受为 max_tokens。"""
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100.5,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        assert any("max_tokens" in e for e in errors)

    def test_empty_messages(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100,
                "messages": [],
            }
        )
        assert any("messages" in e for e in errors)

    def test_messages_not_list(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100,
                "messages": "not a list",
            }
        )
        assert any("messages" in e for e in errors)

    def test_message_not_dict(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100,
                "messages": ["not a dict"],
            }
        )
        assert any("messages[0]" in e for e in errors)

    def test_invalid_role(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100,
                "messages": [{"role": "developer", "content": "hi"}],
            }
        )
        assert any("role" in e for e in errors)

    def test_empty_content(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": ""}],
            }
        )
        assert any("content" in e for e in errors)

    def test_temperature_out_of_range_high(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 3.0,
            }
        )
        assert any("temperature" in e for e in errors)

    def test_temperature_negative(self):
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": -0.1,
            }
        )
        assert any("temperature" in e for e in errors)

    def test_temperature_none_ok(self):
        """temperature 为 None 应通过。"""
        errors = validate_payload(
            {
                "model": "gpt-4",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": None,
            }
        )
        assert errors == []

    def test_multiple_errors(self):
        """多个错误应同时报告。"""
        errors = validate_payload(
            {
                "model": "",
                "max_tokens": -1,
                "messages": [],
                "temperature": 99,
            }
        )
        assert len(errors) >= 4


# ============================================================================
# 5. Context 层 — Session 和 ContextManager 崩溃测试
# ============================================================================


class TestContextCrash:
    """ContextManager 和 Session 的边界场景。"""

    def test_session_from_dict_missing_id(self):
        """Session.from_dict 缺少 id 应抛 KeyError（设计如此）。"""
        with pytest.raises(KeyError):
            Session.from_dict({"messages": []})

    def test_session_from_dict_empty_data(self):
        """最小化数据（只有 id）。"""
        s = Session.from_dict({"id": "test"})
        assert s.id == "test"
        assert s.messages == []
        assert s.metadata == {}

    def test_session_save_to_unwritable_dir(self):
        """保存到不可写目录应抛异常。"""
        s = Session(id="test_perm")
        with pytest.raises((OSError, PermissionError)):
            s.save("/nonexistent_root_dir_xyz/sub")

    def test_session_load_nonexistent(self):
        """加载不存在的 session 应返回 None。"""
        result = Session.load("nonexistent_id", "/tmp/nonexistent_sessions_dir")
        assert result is None

    def test_session_save_and_load_roundtrip(self, tmp_path):
        """保存再加载应保持一致。"""
        s = Session(id="roundtrip_test", messages=[{"role": "user", "content": "hi"}])
        path = s.save(str(tmp_path))
        assert path.exists()

        loaded = Session.load("roundtrip_test", str(tmp_path))
        assert loaded is not None
        assert loaded.id == "roundtrip_test"
        assert loaded.messages == [{"role": "user", "content": "hi"}]

    def test_build_messages_empty_history(self):
        """空 history 应只返回 system prompt。"""
        ctx = ContextManager(system_prompt="You are helpful.", max_tokens=1000)
        msgs = ctx.build_messages([])
        assert len(msgs) == 1
        assert msgs[0]["role"] == "system"

    def test_estimate_tokens_empty(self):
        """空消息列表的 token 估算应为 0。"""
        ctx = ContextManager()
        assert ctx.estimate_tokens([]) == 0

    def test_estimate_tokens_with_none_content(self):
        """content 为 None 不应崩溃。"""
        ctx = ContextManager()
        assert ctx.estimate_tokens([{"role": "user", "content": None}]) == 0

    def test_estimate_tokens_with_int_content(self):
        """content 为非字符串类型不应崩溃。"""
        ctx = ContextManager()
        assert ctx.estimate_tokens([{"role": "user", "content": 12345}]) == 0

    def test_estimate_tokens_with_list_content(self):
        """content 为 list 类型（多模态消息）。"""
        ctx = ContextManager()
        tokens = ctx.estimate_tokens(
            [
                {"role": "user", "content": [{"type": "text", "text": "hello world"}]},
            ]
        )
        assert tokens > 0

    def test_maybe_compress_short_history(self):
        """短历史不应被压缩。"""
        ctx = ContextManager(max_tokens=100, compression_threshold=0.1)
        msgs = [{"role": "user", "content": "short"}]
        result = ctx.maybe_compress(msgs)
        assert result == msgs

    def test_maybe_compress_triggers(self):
        """超长历史应被压缩。"""
        ctx = ContextManager(max_tokens=10, compression_threshold=0.1)
        msgs = [{"role": "user", "content": f"Message number {i} " * 10} for i in range(20)]
        result = ctx.maybe_compress(msgs)
        assert len(result) < len(msgs)

    def test_maybe_compress_few_messages_above_threshold(self):
        """超过 token 阈值但消息太少（<=8条）不应压缩。"""
        ctx = ContextManager(max_tokens=10, compression_threshold=0.1)
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "x" * 100},
            {"role": "assistant", "content": "x" * 100},
        ]
        result = ctx.maybe_compress(msgs)
        assert result == msgs

    def test_summarize_with_empty_messages(self):
        """_summarize 空列表。"""
        ctx = ContextManager()
        result = ctx._summarize([])
        assert result == ""

    def test_summarize_with_non_string_content(self):
        """_summarize 非 str content 不应崩溃。"""
        ctx = ContextManager()
        result = ctx._summarize([{"role": "user", "content": None}])
        assert isinstance(result, str)

    def test_summarize_truncates_at_20(self):
        """_summarize 最多保留 20 条。"""
        ctx = ContextManager()
        msgs = [{"role": "user", "content": f"msg {i}"} for i in range(50)]
        result = ctx._summarize(msgs)
        lines = result.strip().split("\n")
        assert len(lines) <= 20

    def test_build_messages_with_project_context(self):
        """project_context 应被追加到 system prompt。"""
        ctx = ContextManager(system_prompt="Base prompt")
        msgs = ctx.build_messages([], project_context="/custom/project")
        assert "/custom/project" in msgs[0]["content"]

    def test_build_messages_with_tool_registry(self, core_registry):
        """tool_registry 的定义应被注入 system prompt。"""
        ctx = ContextManager(system_prompt="Base")
        msgs = ctx.build_messages([], tool_registry=core_registry)
        assert "Available Tools" in msgs[0]["content"]
        assert "read_file" in msgs[0]["content"]


# ============================================================================
# 6. Engine 层 — AgentEngine 崩溃测试
# ============================================================================


class TestEngineCrash:
    """AgentEngine 的异常和边界场景。"""

    @pytest.mark.asyncio
    async def test_run_empty_user_message(self, mock_provider):
        """空用户消息不应崩溃。"""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=ToolRegistry(),
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=3),
        )
        session = Session(id="test_empty_msg")
        result = await engine.run("", session)
        assert result.finished is True

    @pytest.mark.asyncio
    async def test_run_provider_raises_exception(self):
        """Provider 抛异常时，run 应传播异常（不吞掉）。"""

        class CrashProvider(MockProvider):
            async def chat(self, *args, **kwargs):
                raise RuntimeError("API exploded")

        provider = CrashProvider(responses=[])
        engine = AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=3),
        )
        with pytest.raises(RuntimeError, match="API exploded"):
            await engine.run("test", Session(id="crash_test"))

    @pytest.mark.asyncio
    async def test_run_tool_raises_exception(self):
        """工具执行抛异常时应被捕获，返回错误 ToolResult。"""

        class CrashingTool:
            @property
            def name(self):
                return "crash_tool"

            @property
            def description(self):
                return "A tool that crashes"

            @property
            def parameters_schema(self):
                return {"type": "object", "properties": {}}

            async def execute(self, **kwargs):
                raise RuntimeError("Tool internal error")

        registry = ToolRegistry()
        registry.register(CrashingTool())

        tool_call = ToolCall(id="tc1", name="crash_tool", arguments={})
        resp1 = ChatResponse(text="", tool_calls=[tool_call], usage=TokenUsage())
        resp2 = ChatResponse(text="Done after crash", usage=TokenUsage())
        provider = MockProvider(responses=[resp1, resp2])

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=5),
        )
        result = await engine.run("test", Session(id="crash_tool_test"))
        assert result.finished is True
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["success"] is False

    @pytest.mark.asyncio
    async def test_run_multiple_tool_calls_in_one_response(self):
        """一个 response 中包含多个 tool_calls。"""
        registry = ToolRegistry()
        registry.load_preset("readonly")

        tc1 = ToolCall(id="tc1", name="read_file", arguments={"path": "/tmp/nonexistent_a"})
        tc2 = ToolCall(id="tc2", name="read_file", arguments={"path": "/tmp/nonexistent_b"})
        resp1 = ChatResponse(text="", tool_calls=[tc1, tc2], usage=TokenUsage())
        resp2 = ChatResponse(text="Done", usage=TokenUsage())
        provider = MockProvider(responses=[resp1, resp2])

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=5),
        )
        result = await engine.run("test", Session(id="multi_tool"))
        assert result.finished is True
        assert len(result.tool_calls) == 2

    @pytest.mark.asyncio
    async def test_run_llm_returns_empty_response(self):
        """LLM 返回空 text 和空 tool_calls 时不应死循环。"""
        resp = ChatResponse(text="", tool_calls=[], usage=TokenUsage())
        provider = MockProvider(responses=[resp])

        engine = AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=3),
        )
        result = await engine.run("test", Session(id="empty_resp"))
        # 空 text + 空 tool_calls → 条件不满足，循环到 max_iterations
        assert result.iterations == 3
        assert result.finished is False

    @pytest.mark.asyncio
    async def test_run_stream_no_tool_calls(self, mock_provider):
        """流式模式下无 tool_calls 应正确结束。"""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=ToolRegistry(),
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=3),
        )
        events = []
        async for e in engine.run_stream("hi", Session(id="stream_test")):
            events.append(e)
        assert any(e["type"] == "final" for e in events)

    @pytest.mark.asyncio
    async def test_run_stream_with_tool_call(self):
        """流式模式下有 tool_call 应正确执行并继续。"""
        registry = ToolRegistry()
        registry.load_preset("readonly")

        tc = ToolCall(id="tc1", name="read_file", arguments={"path": "/tmp/x"})
        resp1 = ChatResponse(text="reading...", tool_calls=[tc], usage=TokenUsage())
        resp2 = ChatResponse(text="All done", usage=TokenUsage())
        provider = MockProvider(responses=[resp1, resp2])

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=5),
        )
        events = []
        async for e in engine.run_stream("read file", Session(id="stream_tool")):
            events.append(e)
        types = [e["type"] for e in events]
        assert "tool_call_start" in types
        assert "tool_result" in types
        assert "final" in types

    @pytest.mark.asyncio
    async def test_run_with_none_session(self, mock_provider):
        """session=None 应自动创建新 session。"""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=ToolRegistry(),
            context_manager=ContextManager(max_tokens=100_000),
            config=AgentConfig(max_iterations=3),
        )
        result = await engine.run("hello")
        assert result.session_id.startswith("session_")


# ============================================================================
# 7. 文件工具 — 崩溃边界测试
# ============================================================================


class TestFileToolsCrash:
    """文件操作工具的各种边界和异常场景。"""

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        from tools.file_tools import ReadFileTool

        tool = ReadFileTool()
        result = await tool.execute(path="/nonexistent/path/file.txt")
        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_read_directory_as_file(self, tmp_path):
        from tools.file_tools import ReadFileTool

        tool = ReadFileTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_read_file_with_invalid_encoding(self, tmp_path):
        """包含二进制数据的文件不应导致崩溃。"""
        from tools.file_tools import ReadFileTool

        binary_file = tmp_path / "binary.dat"
        binary_file.write_bytes(b"\x80\xff\xfe\x00binary")
        tool = ReadFileTool()
        result = await tool.execute(path=str(binary_file))
        # 应该抛异常被捕获
        assert result.success is False

    @pytest.mark.asyncio
    async def test_write_to_nonexistent_parent_dir(self, tmp_path):
        """写入不存在的嵌套父目录应自动创建。"""
        from tools.file_tools import WriteFileTool

        tool = WriteFileTool()
        nested = tmp_path / "a" / "b" / "c" / "file.txt"
        result = await tool.execute(path=str(nested), content="hello")
        assert result.success is True
        assert nested.exists()

    @pytest.mark.asyncio
    async def test_write_empty_content(self, tmp_path):
        """写入空内容。"""
        from tools.file_tools import WriteFileTool

        tool = WriteFileTool()
        f = tmp_path / "empty.txt"
        result = await tool.execute(path=str(f), content="")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_edit_file_search_not_found(self, tmp_path):
        """编辑文件时搜索文本不存在。"""
        from tools.file_tools import EditFileTool

        f = tmp_path / "test.txt"
        f.write_text("hello world")
        tool = EditFileTool()
        result = await tool.execute(path=str(f), search="nonexistent text", replace="new")
        assert result.success is False
        assert "未找到" in result.error

    @pytest.mark.asyncio
    async def test_edit_nonexistent_file(self):
        from tools.file_tools import EditFileTool

        tool = EditFileTool()
        result = await tool.execute(path="/nonexistent", search="a", replace="b")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_edit_file_multiple_occurrences(self, tmp_path):
        """只有第一处匹配被替换。"""
        from tools.file_tools import EditFileTool

        f = tmp_path / "multi.txt"
        f.write_text("aaa bbb aaa")
        tool = EditFileTool()
        result = await tool.execute(path=str(f), search="aaa", replace="ccc")
        assert result.success is True
        assert f.read_text() == "ccc bbb aaa"

    @pytest.mark.asyncio
    async def test_list_dir_nonexistent(self):
        from tools.file_tools import ListDirTool

        tool = ListDirTool()
        result = await tool.execute(path="/nonexistent_dir")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_dir_on_file(self, tmp_path):
        from tools.file_tools import ListDirTool

        f = tmp_path / "file.txt"
        f.write_text("data")
        tool = ListDirTool()
        result = await tool.execute(path=str(f))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_dir_depth_clamping(self, tmp_path):
        """depth 超出范围应被 clamp 到 [1,5]。"""
        from tools.file_tools import ListDirTool

        tool = ListDirTool()
        result = await tool.execute(path=str(tmp_path), depth=100)
        assert result.success is True
        assert result.metadata["depth"] == 5

    @pytest.mark.asyncio
    async def test_search_file_with_regex_bomb(self, tmp_path):
        """恶意正则（ catastrophic backtracking）不应永久卡住。"""
        from tools.file_tools import SearchFileTool

        f = tmp_path / "evil.txt"
        f.write_text("aaaaaaaaaaaaaaaaaaaaaa")
        tool = SearchFileTool()
        # 这个正则在某些引擎上会引发指数级回溯
        result = await tool.execute(pattern="(a+)+$", path=str(f))
        # 可能超时或正常返回，但不应崩溃
        assert isinstance(result.success, bool)

    @pytest.mark.asyncio
    async def test_search_file_invalid_regex(self, tmp_path):
        """非法正则表达式应返回错误。"""
        from tools.file_tools import SearchFileTool

        f = tmp_path / "test.txt"
        f.write_text("hello")
        tool = SearchFileTool()
        result = await tool.execute(pattern="[unclosed", path=str(f))
        assert result.success is False
        assert "正则" in result.error

    @pytest.mark.asyncio
    async def test_search_file_nonexistent_path(self):
        from tools.file_tools import SearchFileTool

        tool = SearchFileTool()
        result = await tool.execute(pattern="test", path="/nonexistent_search")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_search_file_empty_directory(self, tmp_path):
        from tools.file_tools import SearchFileTool

        tool = SearchFileTool()
        result = await tool.execute(pattern="anything", path=str(tmp_path))
        assert result.success is True
        assert "无匹配" in result.output

    @pytest.mark.asyncio
    async def test_search_file_with_context(self, tmp_path):
        """带上下文的搜索。"""
        from tools.file_tools import SearchFileTool

        f = tmp_path / "ctx.txt"
        f.write_text("line1\nMATCH\nline3\n")
        tool = SearchFileTool()
        result = await tool.execute(pattern="MATCH", path=str(f), context=1)
        assert result.success is True
        assert ">>>" in result.output

    @pytest.mark.asyncio
    async def test_read_file_with_line_range(self, tmp_path):
        """指定行号范围读取。"""
        from tools.file_tools import ReadFileTool

        f = tmp_path / "lines.txt"
        f.write_text("\n".join(f"line {i}" for i in range(1, 21)))
        tool = ReadFileTool()
        result = await tool.execute(path=str(f), start_line=5, end_line=10)
        assert result.success is True
        assert "line 5" in result.output
        assert "line 10" in result.output
        assert "line 11" not in result.output

    @pytest.mark.asyncio
    async def test_read_file_line_range_beyond_file(self, tmp_path):
        """行号超出文件总行数。"""
        from tools.file_tools import ReadFileTool

        f = tmp_path / "short.txt"
        f.write_text("only\n_two\nlines\n")
        tool = ReadFileTool()
        result = await tool.execute(path=str(f), start_line=1, end_line=1000)
        assert result.success is True


# ============================================================================
# 8. Bash 工具 — 安全和超时测试
# ============================================================================


class TestBashToolCrash:
    """BashTool 的安全拦截和异常场景。"""

    @pytest.mark.asyncio
    async def test_blocked_rm_rf(self):
        from tools.bash_tool import BashTool

        tool = BashTool()
        result = await tool.execute(command="rm -rf /")
        assert result.success is False
        assert "安全策略" in result.error

    @pytest.mark.asyncio
    async def test_blocked_sudo(self):
        from tools.bash_tool import BashTool

        tool = BashTool()
        result = await tool.execute(command="sudo rm -rf /")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_blocked_chmod_777(self):
        from tools.bash_tool import BashTool

        tool = BashTool()
        result = await tool.execute(command="chmod 777 /etc/passwd")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_blocked_case_insensitive(self):
        """黑名单匹配应不区分大小写。"""
        from tools.bash_tool import BashTool

        tool = BashTool()
        result = await tool.execute(command="RM -RF /")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_timeout(self):
        """超时命令应被终止。"""
        from tools.bash_tool import BashTool

        tool = BashTool(max_execution_time=1)
        result = await tool.execute(command="sleep 10")
        assert result.success is False
        assert "超时" in result.error

    @pytest.mark.asyncio
    async def test_command_success(self):
        from tools.bash_tool import BashTool

        tool = BashTool()
        result = await tool.execute(command="echo hello_world")
        assert result.success is True
        assert "hello_world" in result.output

    @pytest.mark.asyncio
    async def test_command_failure_exit_code(self):
        from tools.bash_tool import BashTool

        tool = BashTool()
        result = await tool.execute(command="exit 42")
        assert result.success is False
        assert "42" in result.error

    @pytest.mark.asyncio
    async def test_command_with_stderr(self):
        from tools.bash_tool import BashTool

        tool = BashTool()
        result = await tool.execute(command="echo err >&2")
        assert result.success is True
        assert "err" in result.output

    @pytest.mark.asyncio
    async def test_large_output_truncation(self):
        """超大输出应被截断。"""
        from tools.bash_tool import BashTool

        tool = BashTool(max_output_size=100)
        result = await tool.execute(command="seq 1 10000")
        assert result.success is True
        assert len(result.output) < 5000  # 被截断


# ============================================================================
# 9. Config 层 — 配置加载和实例化测试
# ============================================================================


class TestConfigCrash:
    """配置层的边界场景。"""

    def test_agent_settings_defaults(self, mock_env):
        from config import AgentSettings

        settings = AgentSettings()
        assert settings.provider_name == "totoro"
        assert settings.totoro.api_key == "test_key_totoro"

    def test_agent_settings_custom(self):
        from config import AgentSettings, TotoroConfig

        settings = AgentSettings(
            provider_name="openai",
            max_iterations=100,
            totoro=TotoroConfig(api_key="custom_key"),
        )
        assert settings.provider_name == "openai"
        assert settings.totoro.api_key == "custom_key"

    def test_resolve_provider(self, mock_env):
        from config import AgentSettings

        settings = AgentSettings()
        assert settings.resolve_provider() == "totoro"

    def test_env_file_loading(self, mock_env):
        """环境变量应正确注入到 config。"""
        from config import AnthropicConfig, OpenAIConfig

        assert OpenAIConfig().api_key == "test_key_openai"
        assert AnthropicConfig().api_key == "test_key_anthropic"

    def test_missing_env_var_defaults(self, monkeypatch):
        """环境变量缺失时应使用默认空字符串。"""
        monkeypatch.delenv("LONGCAT_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from config import TotoroConfig

        config = TotoroConfig()
        assert config.api_key == ""


# ============================================================================
# 10. Provider Registry — 边界测试
# ============================================================================


class TestProviderRegistryCrash:
    """ProviderRegistry 的边界场景。"""

    def test_register_none_succeeds_but_get_returns_none(self):
        """注册 None 不会抛异常（registry 只存引用），但 get 返回 None。"""
        from providers.registry import ProviderRegistry

        ProviderRegistry.register("null_provider", None)  # type: ignore[arg-type]
        assert ProviderRegistry.get("null_provider") is None

    def test_get_after_clear(self):
        from providers.registry import ProviderRegistry

        ProviderRegistry.clear()
        with pytest.raises(KeyError):
            ProviderRegistry.get("anything")


# ============================================================================
# 11. ToolRegistry — 边界测试
# ============================================================================


class TestToolRegistryCrash:
    """ToolRegistry 的边界场景。"""

    def test_get_nonexistent(self):
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_register_duplicate_overwrites(self):
        """注册同名工具应覆盖。"""
        from tools.file_tools import ReadFileTool

        reg = ToolRegistry()
        reg.register(ReadFileTool())
        reg.register(ReadFileTool())  # 重复注册
        assert len(reg) == 1

    def test_load_unknown_preset_loads_core(self):
        """未知 preset 应走 core/full 分支（不是 readonly）。"""
        reg = ToolRegistry()
        reg.load_preset("unknown_preset")
        assert len(reg) >= 5  # core tools

    def test_clear_empties_registry(self):
        reg = ToolRegistry()
        reg.load_preset("core")
        reg.clear()
        assert len(reg) == 0
        assert reg.list_tools() == []

    def test_contains(self):
        from tools.file_tools import ReadFileTool

        reg = ToolRegistry()
        reg.register(ReadFileTool())
        assert "read_file" in reg
        assert "nonexistent" not in reg


# ============================================================================
# 12. 沙箱执行器 — 边界测试
# ============================================================================


class TestSandboxCrash:
    """SubprocessExecutor 的异常场景。"""

    @pytest.mark.asyncio
    async def test_execute_simple(self):
        from sandbox.executor import SubprocessExecutor

        executor = SubprocessExecutor()
        code, stdout, stderr = await executor.execute("echo test")
        assert code == 0
        assert "test" in stdout

    @pytest.mark.asyncio
    async def test_execute_failure(self):
        from sandbox.executor import SubprocessExecutor

        executor = SubprocessExecutor()
        code, stdout, stderr = await executor.execute("exit 1")
        assert code == 1

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        from sandbox.executor import SandboxConfig, SubprocessExecutor

        config = SandboxConfig(max_execution_time=1)
        executor = SubprocessExecutor(config)
        code, stdout, stderr = await executor.execute("sleep 10")
        assert code == 1
        assert "超时" in stderr

    @pytest.mark.asyncio
    async def test_execute_with_stderr_output(self):
        from sandbox.executor import SubprocessExecutor

        executor = SubprocessExecutor()
        code, stdout, stderr = await executor.execute("echo err >&2")
        assert code == 0
        assert "err" in stderr

    @pytest.mark.asyncio
    async def test_output_truncation(self):
        from sandbox.executor import SandboxConfig, SubprocessExecutor

        config = SandboxConfig(max_output_size=50)
        executor = SubprocessExecutor(config)
        code, stdout, stderr = await executor.execute("seq 1 10000")
        assert len(stdout) <= 50

    def test_sandbox_config_defaults(self):
        from sandbox.executor import SandboxConfig

        config = SandboxConfig()
        assert config.max_execution_time == 30
        assert config.max_output_size == 10_000
        assert config.allowed_paths == []
        assert config.blocked_commands == []


# ============================================================================
# 13. Git 工具 — 基本测试
# ============================================================================


class TestGitToolCrash:
    """GitStatusTool 的边界场景。"""

    @pytest.mark.asyncio
    async def test_git_in_non_git_dir(self, tmp_path):
        """非 git 目录中执行 git 命令。"""
        from tools.git_tool import GitStatusTool

        tool = GitStatusTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is False  # not a git repo

    @pytest.mark.asyncio
    async def test_git_in_git_repo(self, tmp_path):
        """在 git 仓库中应正常工作。"""
        import subprocess

        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)

        from tools.git_tool import GitStatusTool

        tool = GitStatusTool()
        result = await tool.execute(path=str(tmp_path))
        assert result.success is True


# ============================================================================
# 14. 并发和竞态条件测试
# ============================================================================


class TestConcurrency:
    """并发场景下的稳定性测试。"""

    @pytest.mark.asyncio
    async def test_concurrent_file_writes_different_files(self, tmp_path):
        """并发写入不同文件不应互相干扰。"""
        from tools.file_tools import WriteFileTool

        tool = WriteFileTool()
        import asyncio

        tasks = [
            tool.execute(path=str(tmp_path / f"file_{i}.txt"), content=f"content {i}")
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        assert all(r.success for r in results)
        for i in range(10):
            assert (tmp_path / f"file_{i}.txt").read_text() == f"content {i}"

    @pytest.mark.asyncio
    async def test_concurrent_read_same_file(self, tmp_path):
        """并发读取同一文件。"""
        from tools.file_tools import ReadFileTool

        f = tmp_path / "shared.txt"
        f.write_text("shared content")
        tool = ReadFileTool()
        import asyncio

        tasks = [tool.execute(path=str(f)) for _ in range(20)]
        results = await asyncio.gather(*tasks)
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_bash_commands(self):
        """并发执行多个 bash 命令。"""
        from tools.bash_tool import BashTool

        tool = BashTool()
        import asyncio

        tasks = [tool.execute(command=f"echo task_{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_provider_client_reuse_across_calls(self):
        """Provider 的 httpx client 应在多次调用间复用。"""
        from providers.totoro_provider import TotoroProvider

        provider = TotoroProvider(api_key="test")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        provider._client = mock_client

        await provider.chat([{"role": "user", "content": "call1"}])
        await provider.chat([{"role": "user", "content": "call2"}])

        # 应复用同一个 client
        assert mock_client.post.call_count == 2


# ============================================================================
# 15. ToolResult 边界测试
# ============================================================================


class TestToolResultCrash:
    """ToolResult.to_message() 的边界场景。"""

    def test_success_with_empty_output(self):
        r = ToolResult(success=True, output="")
        assert r.to_message() == ""

    def test_failure_with_none_error(self):
        r = ToolResult(success=False, output="", error=None)
        msg = r.to_message()
        assert "Error:" in msg

    def test_failure_with_empty_output(self):
        r = ToolResult(success=False, output="", error="something broke")
        msg = r.to_message()
        assert "something broke" in msg

    def test_failure_with_both_output_and_error(self):
        r = ToolResult(success=False, output="partial data", error="crashed")
        msg = r.to_message()
        assert "partial data" in msg
        assert "crashed" in msg
