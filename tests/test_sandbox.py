"""测试 sandbox/executor.py — CommandExecutor。"""

import pytest

from sandbox.executor import SandboxConfig, SubprocessExecutor


class TestSandboxConfig:
    def test_defaults(self):
        cfg = SandboxConfig()
        assert cfg.max_execution_time == 30
        assert cfg.max_output_size == 10_000
        assert cfg.allowed_paths == []
        assert cfg.blocked_commands == []

    def test_custom(self):
        cfg = SandboxConfig(max_execution_time=60, max_output_size=5000)
        assert cfg.max_execution_time == 60
        assert cfg.max_output_size == 5000


class TestSubprocessExecutor:
    @pytest.mark.asyncio
    async def test_execute_echo(self):
        executor = SubprocessExecutor()
        rc, stdout, _stderr = await executor.execute("echo hello")
        assert rc == 0
        assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_execute_failure(self):
        executor = SubprocessExecutor()
        rc, _stdout, _stderr = await executor.execute("false")
        assert rc != 0

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        executor = SubprocessExecutor(config=SandboxConfig(max_execution_time=1))
        rc, _stdout, stderr = await executor.execute("sleep 10")
        assert rc == 1
        assert "超时" in stderr

    @pytest.mark.asyncio
    async def test_output_truncation(self):
        executor = SubprocessExecutor(config=SandboxConfig(max_output_size=10))
        _rc, stdout, _stderr = await executor.execute("echo 'a' * 100")
        assert len(stdout) <= 10

    def test_is_protocol(self):
        """SubprocessExecutor 应实现 CommandExecutor 协议。"""
        executor = SubprocessExecutor()
        assert hasattr(executor, "execute")
        assert callable(executor.execute)
