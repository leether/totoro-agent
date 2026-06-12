"""项目分析工具 — 理解项目结构、依赖、入口文件。"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from tools.base import BaseTool, ToolResult


class ProjectSummaryTool(BaseTool):
    """分析项目结构：目录树 + 入口文件 + 依赖清单。"""

    @property
    def name(self) -> str:
        return "project_summary"

    @property
    def description(self) -> str:
        return "分析指定项目的结构：目录树、入口文件、重要配置文件内容。帮助快速理解代码库。"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "项目路径（绝对路径）。",
                },
            },
            "required": ["path"],
        }

    async def execute(self, *, path: str) -> ToolResult:
        proj = Path(path)
        if not proj.exists() or not proj.is_dir():
            return ToolResult(success=False, output="", error=f"目录不存在: {path}")

        sections = []

        # 1. 目录树（深度 3）
        sections.append("## 目录树")
        lines: list[str] = [str(proj)]

        def _walk(p: Path, level: int, prefix: str = ""):
            if level > 3:
                return
            entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name))
            # 限制每目录最多 20 个条目
            entries = entries[:20]
            for i, entry in enumerate(entries):
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{entry.name}")
                if entry.is_dir() and level < 3:
                    ext = "    " if is_last else "│   "
                    _walk(entry, level + 1, prefix + ext)

        _walk(proj, 1)
        sections.append("\n".join(lines[:200]))  # 最多 200 行

        # 2. 入口文件检测
        sections.append("\n## 入口文件")
        entry_patterns = ["main.py", "app.py", "index.js", "index.ts", "manage.py", "setup.py", "pyproject.toml"]
        found_entries: list[str] = []
        for pat in entry_patterns:
            fp = proj / pat
            if fp.exists():
                found_entries.append(pat)
        sections.append(", ".join(found_entries) if found_entries else "未检测到常见入口文件")

        # 3. 依赖清单
        sections.append("\n## 依赖清单")
        req_file = proj / "requirements.txt"
        if req_file.exists():
            sections.append(f"### requirements.txt\n{req_file.read_text()[:500]}")

        pyproject = proj / "pyproject.toml"
        if pyproject.exists():
            sections.append(f"### pyproject.toml\n{pyproject.read_text()[:500]}")

        pkg_json = proj / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text())
                deps = pkg.get("dependencies", {})
                dev_deps = pkg.get("devDependencies", {})
                dep_lines = [f"- {k}: {v}" for k, v in {**deps, **dev_deps}.items()]
                sections.append(f"### package.json\n" + "\n".join(dep_lines[:30]))
            except Exception:
                pass

        # 4. Python 文件统计
        py_files = list(proj.rglob("*.py"))
        js_files = list(proj.rglob("*.js"))
        ts_files = list(proj.rglob("*.ts"))
        sections.append(f"\n## 文件统计")
        sections.append(f"Python: {len(py_files)}  |  JavaScript: {len(js_files)}  |  TypeScript: {len(ts_files)}")

        output = "\n".join(sections)
        return ToolResult(
            success=True,
            output=output,
            metadata={
                "path": str(proj),
                "python_files": len(py_files),
                "js_files": len(js_files),
                "ts_files": len(ts_files),
            },
        )
