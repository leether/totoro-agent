"""Bash 工具 — 在沙箱内执行 Shell 命令。"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.base import BaseTool, ToolResult

# 危险命令黑名单
_BLOCKED_PATTERNS = [
    "rm -rf",
    "rm -r /",
    "rm -rf /",
    "sudo ",
    "sudo\t",
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "mkfs",
    "dd if=",
    "dd of=",
    "chmod 777",
    "chown root",
    "shutdown -h",
    "shutdown -r",
    "reboot",
    "killall -9",
]

_BLOCKED_ERROR = "命令被安全策略禁止（黑名单匹配）"


def _is_blocked(command: str) -> bool:
    """检查命令是否匹配黑名单。"""
    cmd_lower = command.lower().strip()
    return any(pattern.lower() in cmd_lower for pattern in _BLOCKED_PATTERNS)


class BashTool(BaseTool):
    """在安全沙箱内执行 Shell 命令。"""

    def __init__(self, max_execution_time: int = 30, max_output_size: int = 10_000):
        self._max_time = max_execution_time
        self._max_output = max_output_size

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "在沙箱内执行 Shell 命令。支持文件操作、编译、运行脚本等。危险命令（rm -rf / sudo 等）会被拦截。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令。",
                },
            },
            "required": ["command"],
        }

    async def execute(self, *, command: str) -> ToolResult:  # type: ignore[override]
        if _is_blocked(command):
            return ToolResult(success=False, output="", error=_BLOCKED_ERROR)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._max_time,
            )
        except TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:  # noqa: S110 — best-effort cleanup
                pass
            return ToolResult(
                success=False,
                output="",
                error=f"命令执行超时（超过 {self._max_time}s）",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"执行异常: {e}")

        stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
        stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""

        # 截断输出
        if len(stdout) > self._max_output:
            stdout = stdout[: self._max_output] + f"\n... (截断，原始长度 {len(stdout)})"
        if len(stderr) > self._max_output:
            stderr = stderr[: self._max_output] + f"\n... (截断，原始长度 {len(stderr)})"

        returncode = proc.returncode or 0
        output = stdout
        if stderr:
            output += f"\n[stderr]\n{stderr}"

        return ToolResult(
            success=returncode == 0,
            output=output or "(无输出)",
            error=None if returncode == 0 else f"Exit code: {returncode}",
            metadata={"command": command, "returncode": returncode},
        )
