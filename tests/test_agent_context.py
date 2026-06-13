"""测试 agent/context.py — ContextManager 和 Session。"""

from unittest.mock import MagicMock

from agent.context import ContextManager, Session


class TestSession:
    def test_create(self):
        s = Session(id="test_001")
        assert s.id == "test_001"
        assert s.messages == []
        assert isinstance(s.created_at, float)

    def test_to_dict(self):
        s = Session(id="test_002", messages=[{"role": "user", "content": "hi"}])
        d = s.to_dict()
        assert d["id"] == "test_002"
        assert len(d["messages"]) == 1

    def test_from_dict(self):
        data = {
            "id": "test_003",
            "messages": [{"role": "user", "content": "hello"}],
            "created_at": 1000.0,
            "updated_at": 1001.0,
            "metadata": {"key": "val"},
        }
        s = Session.from_dict(data)
        assert s.id == "test_003"
        assert len(s.messages) == 1
        assert s.metadata["key"] == "val"

    def test_save_and_load(self, tmp_dir):
        s = Session(id="persist_test", messages=[{"role": "user", "content": "msg"}])
        path = s.save(str(tmp_dir))
        assert path.exists()

        loaded = Session.load("persist_test", str(tmp_dir))
        assert loaded is not None
        assert loaded.id == "persist_test"
        assert len(loaded.messages) == 1

    def test_load_nonexistent(self, tmp_dir):
        result = Session.load("nonexistent", str(tmp_dir))
        assert result is None


class TestContextManager:
    def test_build_messages_basic(self):
        ctx = ContextManager(system_prompt="You are a helper.")
        messages = ctx.build_messages(
            [
                {"role": "user", "content": "Hello"},
            ]
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "You are a helper." in messages[0]["content"]
        assert messages[1]["role"] == "user"

    def test_build_messages_with_project_context(self):
        ctx = ContextManager(system_prompt="Base prompt.")
        messages = ctx.build_messages(
            [{"role": "user", "content": "Hi"}],
            project_context="/home/user/project",
        )
        assert "/home/user/project" in messages[0]["content"]

    def test_build_messages_with_tools(self):
        ctx = ContextManager(system_prompt="Base.")
        registry = MagicMock()
        registry.tool_definitions.return_value = [
            {"name": "read_file", "description": "Read a file.", "parameters_schema": {}},
        ]
        messages = ctx.build_messages(
            [{"role": "user", "content": "Hi"}],
            tool_registry=registry,
        )
        assert "read_file" in messages[0]["content"]

    def test_estimate_tokens(self):
        ctx = ContextManager()
        messages = [
            {"role": "user", "content": "Hello world!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        tokens = ctx.estimate_tokens(messages)
        assert tokens > 0

    def test_maybe_compress_under_threshold(self):
        ctx = ContextManager(max_tokens=100_000)
        messages = [{"role": "user", "content": "short"}]
        result = ctx.maybe_compress(messages)
        assert result == messages  # 不需要压缩

    def test_compress_history(self):
        ctx = ContextManager(max_tokens=100)
        # 构造大量消息以触发压缩
        messages = [{"role": "user", "content": "x" * 50} for _ in range(20)]
        result = ctx.compress_history(messages)
        # 压缩后消息数应减少
        assert len(result) < len(messages)

    def test_count_tokens(self):
        ctx = ContextManager()
        messages = [{"role": "user", "content": "test"}]
        count = ctx.count_tokens(messages)
        assert count > 0

    def test_session_storage_path(self):
        path = ContextManager.session_storage_path()
        assert ".workbuddy/sessions" in path

    def test_system_prompt_setter(self):
        ctx = ContextManager(system_prompt="old")
        ctx.system_prompt = "new prompt"
        assert ctx.system_prompt == "new prompt"
