"""共享 fixtures — 为所有测试提供公共 mock 和临时目录。"""

import tempfile
from pathlib import Path

import pytest

from agent.context import ContextManager, Session
from providers.base import (
    ChatProvider,
    ChatResponse,
    StreamEvent,
    TokenUsage,
    ToolCall,
)
from tools.registry import ToolRegistry

# ─── 临时目录 ─────────────────────────────────────────────


@pytest.fixture
def tmp_dir():
    """创建临时目录，测试结束后自动清理。"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_project(tmp_dir):
    """创建一个示例项目目录结构。"""
    (tmp_dir / "main.py").write_text("def main():\n    print('hello')\n")
    (tmp_dir / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_dir / "README.md").write_text("# Sample Project\n")
    (tmp_dir / "subdir").mkdir()
    (tmp_dir / "subdir" / "helper.py").write_text("class Helper:\n    pass\n")
    return tmp_dir


# ─── Mock Provider ─────────────────────────────────────────


class MockProvider(ChatProvider):
    """测试用 mock provider，不调用真实 API。"""

    def __init__(self, responses=None):
        """
        responses: list[ChatResponse | str]
        按顺序返回响应。如果元素是 str，自动包装为纯文本 ChatResponse。
        """
        self._responses = []
        for r in responses or []:
            if isinstance(r, str):
                self._responses.append(ChatResponse(text=r, usage=TokenUsage()))
            else:
                self._responses.append(r)
        self._call_count = 0
        self.chat_calls = []  # 记录每次 chat() 的参数
        self.stream_calls = []  # 记录每次 stream_chat() 的参数

    async def chat(self, messages, tools=None, max_tokens=4096, temperature=0.1):
        self.chat_calls.append(
            {
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]

    async def stream_chat(self, messages, tools=None, max_tokens=4096, temperature=0.1):
        self.stream_calls.append(
            {
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        resp = self._responses[idx]
        # 模拟流式事件
        if resp.text:
            yield StreamEvent(type="text_delta", content=resp.text)
        for tc in resp.tool_calls:
            yield StreamEvent(
                type="tool_call_start",
                tool_name=tc.name,
                tool_arguments=tc.arguments,
            )
        yield StreamEvent(type="done", usage=resp.usage)


@pytest.fixture
def mock_provider():
    """返回一个默认的 MockProvider（纯文本响应，无 tool_calls）。"""
    return MockProvider(responses=["Hello from mock!"])


@pytest.fixture
def mock_provider_with_tool_call():
    """返回一个会调用工具的 MockProvider。"""
    tool_call = ToolCall(
        id="call_abc123",
        name="read_file",
        arguments={"path": "/test/file.py"},
    )
    response_with_tool = ChatResponse(
        text="Let me read that file.",
        tool_calls=[tool_call],
        usage=TokenUsage(input_tokens=50, output_tokens=20),
    )
    response_final = ChatResponse(
        text="The file contains a hello world function.",
        usage=TokenUsage(input_tokens=100, output_tokens=30),
    )
    return MockProvider(responses=[response_with_tool, response_final])


# ─── Tool Registry ─────────────────────────────────────────


@pytest.fixture
def empty_registry():
    """空的工具注册表。"""
    return ToolRegistry()


@pytest.fixture
def core_registry():
    """加载 core 预设的工具注册表。"""
    reg = ToolRegistry()
    reg.load_preset("core")
    return reg


@pytest.fixture
def full_registry():
    """加载 full 预设的工具注册表。"""
    reg = ToolRegistry()
    reg.load_preset("full")
    return reg


@pytest.fixture
def readonly_registry():
    """加载 readonly 预设的工具注册表。"""
    reg = ToolRegistry()
    reg.load_preset("readonly")
    return reg


# ─── Context & Session ─────────────────────────────────────


@pytest.fixture
def context_manager():
    """默认 ContextManager。"""
    return ContextManager(max_tokens=100_000)


@pytest.fixture
def session():
    """默认 Session。"""
    return Session(id="test_session_001")


# ─── Config ────────────────────────────────────────────────


@pytest.fixture
def mock_env(monkeypatch):
    """设置测试环境变量。"""
    monkeypatch.setenv("TOTORO_API_KEY", "test_key_totoro")
    monkeypatch.setenv("OPENAI_API_KEY", "test_key_openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key_anthropic")
    monkeypatch.setenv("AGENT_PROVIDER", "totoro")
