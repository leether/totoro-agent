"""Git 工具 — git status / diff / log。"""
from __future__ import annotations

from typing import Any

import asyncio

from tools.base import BaseTool, ToolResult


async def _run_git(args: str, cwd: str = ".") -> tuple[int, str, str]:
    """执行 git 命令，返回 (returncode, stdout, stderr)。"""
    cmd = f"git {args}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=15)
        return (
            proc.returncode or 0,
            stdout_b.decode("utf-8", errors="replace").strip(),
            stderr_b.decode("utf-8", errors="replace").strip(),
        )
    except TimeoutError:
        return 1, "", "命令超时"
    except Exception as e:
        return 1, "", str(e)


class GitStatusTool(BaseTool):
    """查看 Git 工作状态。"""

    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "查看当前 Git 仓库的工作状态（已修改、已暂存、未跟踪的文件）。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Git 仓库路径（默认当前目录）。",
                },
            },
        }

    async def execute(self, *, path: str = ".") -> ToolResult:  # type: ignore[override]
        rc, out, err = await _run_git("status --short", cwd=path)
        if rc != 0:
            return ToolResult(success=False, output="", error=err)
        return ToolResult(success=True, output=out or "(工作区干净)")


class GitDiffTool(BaseTool):
    """查看代码变更。"""

    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return "查看工作区的代码变更（diff）。可指定文件路径查看特定文件的变更。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "仓库路径或特定文件路径。",
                },
                "file": {
                    "type": "string",
                    "description": "特定文件路径（可选）。",
                },
            },
        }

    async def execute(self, *, path: str = ".", file: str = "") -> ToolResult:  # type: ignore[override]
        args = "diff HEAD"
        if file:
            args += f" -- {file}"
        rc, out, err = await _run_git(args, cwd=path)
        if rc != 0:
            return ToolResult(success=False, output="", error=err)
        return ToolResult(success=True, output=out or "(无变更)")


class GitLogTool(BaseTool):
    """查看提交历史。"""

    @property
    def name(self) -> str:
        return "git_log"

    @property
    def description(self) -> str:
        return "查看 Git 提交历史。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "仓库路径。",
                },
                "limit": {
                    "type": "integer",
                    "description": "显示的提交数量（默认 10）。",
                },
            },
        }

    async def execute(self, *, path: str = ".", limit: int = 10) -> ToolResult:  # type: ignore[override]
        args = f"log --oneline -{limit}"
        rc, out, err = await _run_git(args, cwd=path)
        if rc != 0:
            return ToolResult(success=False, output="", error=err)
        return ToolResult(success=True, output=out or "(无提交记录)")
