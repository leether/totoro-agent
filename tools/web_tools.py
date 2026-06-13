"""网络工具 — WebSearch / WebFetch。"""
from __future__ import annotations

import urllib.request
from tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    """网络搜索。使用 DuckDuckGo 即时回答 API（无需 API key）。"""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "在网络上搜索信息，获取实时答案。适合查找文档、解决方案、最新资讯等。"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词。",
                },
            },
            "required": ["query"],
        }

    async def execute(self, *, query: str) -> ToolResult:
        # 使用 DuckDuckGo 即时回答 API
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "totoro-agent/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                import json
                data = json.loads(resp.read().decode("utf-8"))

            parts = []
            if data.get("AbstractText"):
                parts.append(f"摘要: {data['AbstractText']}")
            if data.get("AbstractURL"):
                parts.append(f"来源: {data['AbstractURL']}")

            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    parts.append(f"- {topic['Text']}")

            output = "\n".join(parts) if parts else "无搜索结果"
            return ToolResult(success=True, output=output, metadata={"query": query})

        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {e}")


class WebFetchTool(BaseTool):
    """获取并提取 URL 内容。"""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "获取指定 URL 的页面内容。适合读取 API 文档、技术文章等。"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要获取的 URL。",
                },
            },
            "required": ["url"],
        }

    async def execute(self, *, url: str) -> ToolResult:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "totoro-agent/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="replace")

            # 简单去除 HTML 标签
            import re
            text = re.sub(r"<[^>]+>", "", content)
            text = re.sub(r"\s+", " ", text).strip()

            max_len = 8000
            if len(text) > max_len:
                text = text[:max_len] + f"\n... (截断，原始长度 {len(text)})"

            return ToolResult(success=True, output=text, metadata={"url": url})

        except Exception as e:
            return ToolResult(success=False, output="", error=f"获取失败: {e}")
