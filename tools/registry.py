"""ToolRegistry — 工具注册中心，管理 JSON Schema 生成和工具实例查找。"""
from __future__ import annotations

from collections import OrderedDict

from tools.base import BaseTool


class ToolRegistry:
    """工具注册中心。支持按名称注册、查找、批量加载预设。"""

    def __init__(self):
        self._tools: OrderedDict[str, BaseTool] = OrderedDict()

    def register(self, tool: BaseTool) -> None:
        """注册一个工具实例。"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """按名称获取工具。"""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """列出所有已注册工具。"""
        return list(self._tools.values())

    def tool_definitions(self) -> list[dict]:
        """生成所有工具的 JSON Schema 列表（注入 LLM system prompt）。"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters_schema": tool.parameters_schema,
            }
            for tool in self._tools.values()
        ]

    def tool_names(self) -> list[str]:
        """列出所有工具名称。"""
        return list(self._tools.keys())

    def load_preset(self, preset: str, **kwargs) -> None:
        """
        加载预设工具集。

        preset:
          - "core":   文件读写 + 搜索 + Bash
          - "full":   core + Git + Lint + Test + Web + Project
          - "readonly": 文件读取 + 搜索（无写入）
        """
        from tools.file_tools import (
            ReadFileTool,
            WriteFileTool,
            EditFileTool,
            ListDirTool,
            SearchFileTool,
        )
        from tools.bash_tool import BashTool

        if preset == "readonly":
            self.register(ReadFileTool())
            self.register(SearchFileTool())
            self.register(ListDirTool())
            return

        # core tools
        self.register(ReadFileTool())
        self.register(WriteFileTool())
        self.register(EditFileTool())
        self.register(ListDirTool())
        self.register(SearchFileTool())
        self.register(BashTool(**kwargs))

        if preset == "full":
            from tools.web_tools import WebSearchTool, WebFetchTool
            from tools.git_tool import GitStatusTool
            from tools.project_tool import ProjectSummaryTool

            self.register(WebSearchTool())
            self.register(WebFetchTool())
            self.register(GitStatusTool())
            self.register(ProjectSummaryTool())
            # Lint / Test 工具依赖可选依赖，按需注册

    def clear(self) -> None:
        """清空所有注册的工具。"""
        self._tools.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        names = ", ".join(self._tools.keys())
        return f"ToolRegistry([{names}])"
