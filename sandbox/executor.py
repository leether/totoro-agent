"""CommandExecutor Protocol — 沙箱执行器接口。

当前默认使用 SubprocessExecutor (tools/bash_tool.py)。
未来可替换为 DockerExecutor 实现容器级隔离。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol


@dataclass
class SandboxConfig:
    """沙箱配置。"""
    max_execution_time: int = 30       # 单次命令超时（秒）
    max_output_size: int = 10_000     # 输出截断长度
    allowed_paths: list[str] = None    # 可写路径白名单（None = 不限制）
    blocked_commands: list[str] = None  # 命令黑名单

    def __post_init__(self):
        if self.allowed_paths is None:
            self.allowed_paths = []
        if self.blocked_commands is None:
            self.blocked_commands = []


class CommandExecutor(Protocol):
    """命令执行器协议。"""

    async def execute(self, command: str) -> tuple[int, str, str]:
        """
        执行命令，返回 (returncode, stdout, stderr)。
        超时和输出截断由实现保证。
        """
        ...


class SubprocessExecutor:
    """基于 subprocess 的命令执行器（默认实现）。"""

    def __init__(self, config: SandboxConfig | None = None):
        self._config = config or SandboxConfig()

    async def execute(self, command: str) -> tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._config.max_execution_time,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return 1, "", f"命令执行超时（超过 {self._config.max_execution_time}s）"

        max_out = self._config.max_output_size
        stdout = stdout_b.decode("utf-8", errors="replace")[:max_out] if stdout_b else ""
        stderr = stderr_b.decode("utf-8", errors="replace")[:max_out] if stderr_b else ""

        return proc.returncode or 0, stdout, stderr
