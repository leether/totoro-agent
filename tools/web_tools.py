"""网络工具 — WebSearch / WebFetch。

设计决策：
- 使用 httpx.AsyncClient（与 Provider 层保持一致），而非 urllib
- web_search: 双后端策略 — Bing HTML 主搜索 + Wikipedia API 知识补充
  （DuckDuckGo 已全面上 CAPTCHA，不再使用）
- web_fetch: 去除 <script>/<style>/<nav>/<footer> 等噪音标签，
  按 <article>/<main>/body 优先级提取正文，再做 HTML→text 清洗
- 两个工具均复用模块级连接池，支持超时 / 重定向 / 编码探测
"""

from __future__ import annotations

import re
from html import unescape
from typing import TYPE_CHECKING, Any

from tools.base import BaseTool, ToolResult

if TYPE_CHECKING:
    import httpx

# ─── 常量 ───────────────────────────────────────────────────────

_DEFAULT_TIMEOUT = 20.0
_CONNECT_TIMEOUT = 10.0
_MAX_CONTENT_LENGTH = 10000
_MAX_SEARCH_RESULTS = 8
_MAX_SUMMARY_LENGTH = 300

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ─── 共享 HTTP 客户端 ──────────────────────────────────────────

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """获取或创建模块级共享 httpx 客户端。"""
    global _client
    if _client is None or _client.is_closed:
        import httpx

        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(_DEFAULT_TIMEOUT, connect=_CONNECT_TIMEOUT),
            follow_redirects=True,
            headers={
                "User-Agent": _UA,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
    return _client


async def _close_client() -> None:
    """关闭模块级 httpx 客户端（测试 / 退出时调用）。"""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# ─── HTML 文本提取 ─────────────────────────────────────────────

# 噪音标签 — 整块删除（含内容）
_NOISE_TAGS = re.compile(
    r"<(script|style|noscript|nav|footer|header|aside|iframe|svg|form"
    r"|button|input|select|textarea|template|slot)[^>]*>.*?</\1\s*>",
    re.DOTALL | re.IGNORECASE,
)

# HTML 注释
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# 剩余所有标签
_ALL_TAGS = re.compile(r"<[^>]+>")

# 连续空白
_MULTI_WS = re.compile(r"[ \t]+")
_MULTI_NL = re.compile(r"\n{3,}")

# 块级标签 → 换行
_BLOCK_TAGS = re.compile(
    r"</?(p|div|br|h[1-6]|li|ul|ol|tr|td|th|table|section|article"
    r"|main|blockquote|pre|hr|dl|dt|dd)\b[^>]*>",
    re.IGNORECASE,
)


def extract_text_from_html(html: str) -> str:
    """从 HTML 中提取干净的文本。

    步骤:
        1. 删除 <script>/<style>/<nav>/<footer> 等噪音标签（含内容）
        2. 删除 HTML 注释
        3. 把 <br>, <p>, <div>, <li> 等块级标签替换为换行
        4. 去除所有剩余标签
        5. unescape HTML 实体
        6. 压缩连续空白
    """
    text = _NOISE_TAGS.sub("", html)
    text = _HTML_COMMENT.sub("", text)
    text = _BLOCK_TAGS.sub("\n", text)
    text = _ALL_TAGS.sub("", text)
    text = unescape(text)
    text = _MULTI_WS.sub(" ", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


def _truncate(text: str, max_len: int = _MAX_CONTENT_LENGTH) -> str:
    """截断文本到 max_len，并追加截断提示。"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n\n... (截断，原始长度 {len(text)} 字符)"


def _strip_tags(text: str) -> str:
    """快速去除 HTML 标签 + unescape。"""
    text = _ALL_TAGS.sub("", text)
    return unescape(text)


# ─── Bing 搜索结果解析 ─────────────────────────────────────────

# Bing 搜索结果摘要
_BING_SNIPPET = re.compile(
    r'<div[^>]*class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>',
    re.DOTALL | re.IGNORECASE,
)

# Bing 搜索结果链接 — 可能在 h2>a 或直接在 <a class="tilk"> 中
_BING_LINKS = re.compile(
    r'<a\s+[^>]*?href="(https?://[^"]+)"[^>]*?'
    r'(?:class="[^"]*(?:tilk|b_algo)[^"]*")?[^>]*>'
    r"(.*?)</a>",
    re.DOTALL | re.IGNORECASE,
)

# Bing 搜索结果区域内的链接（更精确：b_algo 内部的第一个链接）
_BING_RESULT_BLOCK = re.compile(
    r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)


def _parse_bing(html: str, max_results: int) -> list[dict[str, str]]:
    """解析 Bing 搜索结果 HTML。

    Bing b_algo 块结构:
        <li class="b_algo">
          <div class="b_tpcn"><a class="tilk" href="...">域名图标</a></div>
          <h2><a href="REAL_URL">真实标题</a></h2>
          <div class="b_caption"><p>摘要文本</p></div>
        </li>

    策略: 优先从 <h2><a> 提取标题链接，从 b_caption > p 提取摘要。
    """
    results: list[dict[str, str]] = []

    blocks = _BING_RESULT_BLOCK.findall(html)

    for block in blocks:
        # 去掉 <link>/<style> 标签（Bing 在结果块中注入 CSS）
        block = re.sub(r"<link[^>]*/?>|<style[^>]*>.*?</style>", "", block, flags=re.DOTALL)

        # 优先策略: <h2><a href=URL>标题</a></h2>
        h2_link = re.search(
            r"<h2[^>]*>\s*<a\s+[^>]*?href=\"(https?://[^\"]+)\"[^>]*>(.*?)</a>",
            block,
            re.DOTALL | re.IGNORECASE,
        )

        url = None
        title = None

        if h2_link:
            url = h2_link.group(1)
            title = _strip_tags(h2_link.group(2)).strip()
        else:
            # 回退: 找 <a class="tilk"> 之后的第一个链接
            tilk = re.search(
                r'class="tilk"[^>]*href="(https?://[^"]+)"',
                block,
                re.IGNORECASE,
            )
            if tilk:
                url = tilk.group(1)
                # 标题取 cite 标签中的文本或 aria-label
                cite = re.search(r"<cite[^>]*>(.*?)</cite>", block, re.DOTALL | re.IGNORECASE)
                if cite:
                    title = _strip_tags(cite.group(1)).strip()

        if not url or not title:
            continue

        # 清理 URL（去掉 Bing 追踪参数）
        url = url.split("&")[0] if "&" in url and "uddg" not in url else url
        # 跳过 Bing 内部链接
        if "bing.com" in url or "microsoft.com" in url:
            continue
        if len(title) < 3:
            continue

        # 提取摘要
        snippet_match = re.search(
            r'<div[^>]*class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        snippet = _strip_tags(snippet_match.group(1)).strip() if snippet_match else ""

        results.append(
            {
                "title": title[:200],
                "url": url,
                "snippet": snippet[:_MAX_SUMMARY_LENGTH],
            }
        )
        if len(results) >= max_results:
            break

    return results


# ─── Wikipedia 搜索 ────────────────────────────────────────────


def _parse_wikipedia(data: dict[str, Any], max_results: int) -> list[dict[str, str]]:
    """解析 Wikipedia API 搜索结果。"""
    results: list[dict[str, str]] = []
    for item in data.get("query", {}).get("search", [])[:max_results]:
        title = item.get("title", "")
        snippet = _strip_tags(item.get("snippet", ""))
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet[:_MAX_SUMMARY_LENGTH],
            }
        )
    return results


# ─── WebSearch ─────────────────────────────────────────────────


class WebSearchTool(BaseTool):
    """网络搜索。

    使用双后端策略：
    - Bing HTML 搜索（主）：覆盖通用查询，无需 API key
    - Wikipedia API（补充）：覆盖百科 / 知识类查询

    DuckDuckGo 已全面启用 CAPTCHA，不再使用。
    """

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "在网络上搜索信息，获取实时答案。适合查找文档、解决方案、最新资讯等。"
            " 返回搜索结果的标题、摘要和链接。"
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词。",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数（默认8）。",
                    "default": 8,
                },
            },
            "required": ["query"],
        }

    async def execute(self, *, query: str, max_results: int = _MAX_SEARCH_RESULTS) -> ToolResult:  # type: ignore[override]
        try:
            client = _get_client()

            # 主搜索: Bing HTML
            bing_results = await self._search_bing(client, query, max_results)

            # 补充: Wikipedia API（总是取几条百科结果）
            wiki_count = max(0, max_results - len(bing_results))
            wiki_results = await self._search_wikipedia(client, query, min(3, wiki_count))

            all_results = bing_results + wiki_results

            if not all_results:
                return ToolResult(
                    success=True,
                    output="无搜索结果",
                    metadata={"query": query, "result_count": 0},
                )

            # 格式化输出
            lines = []
            for i, item in enumerate(all_results[:max_results], 1):
                title = item["title"]
                snippet = item["snippet"]
                link = item["url"]
                source = item.get("source", "")
                prefix = f"[{i}]"
                if source:
                    prefix += f" ({source})"
                lines.append(f"{prefix} {title}")
                if snippet:
                    lines.append(f"    {snippet}")
                lines.append(f"    🔗 {link}")
                lines.append("")

            output = "\n".join(lines).strip()
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "query": query,
                    "result_count": len(all_results[:max_results]),
                    "sources": {
                        "bing": len(bing_results),
                        "wikipedia": len(wiki_results),
                    },
                },
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {e}")

    async def _search_bing(
        self, client: httpx.AsyncClient, query: str, max_results: int
    ) -> list[dict[str, str]]:
        """Bing HTML 搜索。"""
        try:
            resp = await client.get(
                "https://www.bing.com/search",
                params={"q": query, "count": max_results + 5},
                headers={"Accept": "text/html"},
            )
            if resp.status_code != 200:
                return []

            results = _parse_bing(resp.text, max_results)
            for r in results:
                r["source"] = "Bing"
            return results
        except Exception:
            return []

    async def _search_wikipedia(
        self, client: httpx.AsyncClient, query: str, max_results: int
    ) -> list[dict[str, str]]:
        """Wikipedia API 搜索。"""
        if max_results <= 0:
            return []
        try:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max_results,
                    "format": "json",
                },
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return []

            results = _parse_wikipedia(resp.json(), max_results)
            for r in results:
                r["source"] = "Wikipedia"
            return results
        except Exception:
            return []


# ─── WebFetch ──────────────────────────────────────────────────


class WebFetchTool(BaseTool):
    """获取并提取 URL 页面的正文内容。

    支持 HTML 页面（自动提取正文）和纯文本 / JSON / 代码（直接返回）。
    """

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "获取指定 URL 的页面内容，自动提取正文（去除导航、广告、脚本等）。"
            "适合读取 API 文档、技术文章、GitHub Raw 内容等。"
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要获取的 URL。",
                },
                "max_length": {
                    "type": "integer",
                    "description": "返回内容的最大字符数（默认10000）。",
                    "default": 10000,
                },
            },
            "required": ["url"],
        }

    async def execute(self, *, url: str, max_length: int = _MAX_CONTENT_LENGTH) -> ToolResult:  # type: ignore[override]
        if not url.startswith(("http://", "https://")):
            return ToolResult(success=False, output="", error=f"无效的 URL: {url}")

        try:
            client = _get_client()
            resp = await client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")

            # 纯文本 / JSON / Markdown / XML — 直接返回
            if any(
                ct in content_type
                for ct in ("text/plain", "application/json", "text/markdown", "application/xml")
            ):
                text = resp.text
            elif "html" in content_type or "<html" in resp.text[:500].lower():
                # HTML 页面 — 提取正文
                text = extract_text_from_html(resp.text)
            else:
                # 未知类型 — 尝试当 HTML 解析
                text = extract_text_from_html(resp.text)

            text = _truncate(text, max_length)

            if not text:
                return ToolResult(
                    success=True,
                    output="(页面内容为空或提取后无有效文本)",
                    metadata={"url": url, "content_type": content_type},
                )

            return ToolResult(
                success=True,
                output=text,
                metadata={
                    "url": url,
                    "content_type": content_type,
                    "status_code": resp.status_code,
                },
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=f"获取失败: {e}")
