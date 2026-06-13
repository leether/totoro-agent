"""文件操作工具 — read / write / edit / list / search。"""
from __future__ import annotations

from typing import Any

import re
from pathlib import Path

from tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """读取文件内容，支持指定行号范围。"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取指定路径的文件内容。可指定 start_line 和 end_line 只读取部分内容。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径（绝对路径）。",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（1-based，可选）。",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（1-based，可选，包含该行）。",
                },
            },
            "required": ["path"],
        }

    async def execute(self, *, path: str, start_line: int = 0, end_line: int = 0) -> ToolResult:  # type: ignore[override]
        file_path = Path(path)

        if not file_path.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {path}")

        if not file_path.is_file():
            return ToolResult(success=False, output="", error=f"路径不是文件: {path}")

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            return ToolResult(success=False, output="", error=f"读取失败: {e}")

        total_lines = len(lines)

        if start_line > 0:
            s = max(0, start_line - 1)
            e_end = total_lines if end_line <= 0 else min(end_line, total_lines)
            lines = lines[s:e_end]

        content = "\n".join(lines)
        meta = {"path": str(file_path), "total_lines": total_lines, "returned_lines": len(lines)}
        return ToolResult(success=True, output=content, metadata=meta)


class WriteFileTool(BaseTool):
    """写入/创建文件。覆盖模式，适用于新建或全量重写文件。"""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "将内容写入指定路径的文件。如果文件已存在则覆盖，如果不存在则创建。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目标文件路径（绝对路径）。",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文件内容。",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, *, path: str, content: str) -> ToolResult:  # type: ignore[override]
        file_path = Path(path)

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"写入失败: {e}")

        return ToolResult(
            success=True,
            output=f"文件已写入: {path} ({len(content)} chars)",
            metadata={"path": str(path), "size": len(content)},
        )


class EditFileTool(BaseTool):
    """精确编辑文件 — 搜索并替换指定文本块。适用于局部修改。"""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "在文件中搜索 exact 文本并将其替换为新文本。"
            "search 文本必须在文件中完全匹配（包括空白字符），确保精准定位。"
            "适用于函数修改、配置更新、bug 修复等场景。"
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目标文件路径（绝对路径）。",
                },
                "search": {
                    "type": "string",
                    "description": "要搜索的精确文本（必须在文件中完全匹配）。",
                },
                "replace": {
                    "type": "string",
                    "description": "替换后的文本。",
                },
            },
            "required": ["path", "search", "replace"],
        }

    async def execute(self, *, path: str, search: str, replace: str) -> ToolResult:  # type: ignore[override]
        file_path = Path(path)

        if not file_path.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"读取失败: {e}")

        if search not in content:
            return ToolResult(
                success=False,
                output="",
                error=f"搜索文本在文件中未找到\n---search---\n{search}\n---end---",
            )

        new_content = content.replace(search, replace, 1)

        try:
            file_path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"写入失败: {e}")

        return ToolResult(
            success=True,
            output=f"文件已编辑: {path}",
            metadata={"path": str(path), "original_length": len(content), "new_length": len(new_content)},
        )


class ListDirTool(BaseTool):
    """列出目录结构，以树形格式返回。"""

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "列出指定目录的文件和子目录结构。支持 depth 控制递归深度。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径（绝对路径）。",
                },
                "depth": {
                    "type": "integer",
                    "description": "递归深度（默认 2，最大 5）。",
                },
            },
            "required": ["path"],
        }

    async def execute(self, *, path: str, depth: int = 2) -> ToolResult:  # type: ignore[override]
        dir_path = Path(path)

        if not dir_path.exists():
            return ToolResult(success=False, output="", error=f"目录不存在: {path}")
        if not dir_path.is_dir():
            return ToolResult(success=False, output="", error=f"路径不是目录: {path}")

        depth = min(max(1, depth), 5)
        lines: list[str] = []

        def _walk(p: Path, level: int, prefix: str = "") -> None:
            if level > depth:
                return
            entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name))
            for i, entry in enumerate(entries):
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{entry.name}")
                if entry.is_dir() and level < depth:
                    ext = "    " if is_last else "│   "
                    _walk(entry, level + 1, prefix + ext)

        lines.append(str(dir_path))
        _walk(dir_path, 1)

        return ToolResult(
            success=True,
            output="\n".join(lines),
            metadata={"path": str(dir_path), "depth": depth, "entries": len(lines) - 1},
        )


class SearchFileTool(BaseTool):
    """文件内容搜索（grep）。支持正则匹配，返回匹配行及上下文。"""

    @property
    def name(self) -> str:
        return "search_file"

    @property
    def description(self) -> str:
        return "在文件中搜索匹配指定模式的文本行（类似 grep）。支持正则表达式。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "搜索模式（正则表达式）。",
                },
                "path": {
                    "type": "string",
                    "description": "搜索路径（文件或目录的绝对路径）。",
                },
                "context": {
                    "type": "integer",
                    "description": "匹配行前后显示的上下文行数（默认 0）。",
                },
            },
            "required": ["pattern", "path"],
        }

    async def execute(self, *, pattern: str, path: str, context: int = 0) -> ToolResult:  # type: ignore[override]
        search_path = Path(path)

        if not search_path.exists():
            return ToolResult(success=False, output="", error=f"路径不存在: {path}")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"无效的正则表达式: {e}")

        results: list[str] = []

        if search_path.is_file():
            files = [search_path]
        else:
            files = [f for f in search_path.rglob("*") if f.is_file()]

        for fpath in files:
            try:
                lines = fpath.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, PermissionError):
                continue

            for i, line in enumerate(lines):
                if regex.search(line):
                    if context > 0:
                        start = max(0, i - context)
                        end = min(len(lines), i + context + 1)
                        ctx_lines = []
                        for j in range(start, end):
                            marker = ">>>" if j == i else "   "
                            ctx_lines.append(f"{marker} {j + 1}: {lines[j]}")
                        results.append(f"\n--- {fpath}:{i + 1} ---\n" + "\n".join(ctx_lines))
                    else:
                        results.append(f"{fpath}:{i + 1}: {line}")

        if not results:
            return ToolResult(success=True, output="无匹配结果", metadata={"matches": 0})

        output = "\n".join(results)
        return ToolResult(
            success=True,
            output=output,
            metadata={"matches": len(results), "files_searched": len(files)},
        )
