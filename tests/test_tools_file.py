"""测试 tools/file_tools.py — 文件操作工具。"""

import pytest

from tools.file_tools import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    SearchFileTool,
    WriteFileTool,
)


class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_dir):
        f = tmp_dir / "test.py"
        f.write_text("print('hello')\n")
        tool = ReadFileTool()
        result = await tool.execute(path=str(f))
        assert result.success is True
        assert "print('hello')" in result.output

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        tool = ReadFileTool()
        result = await tool.execute(path="/nonexistent/file.py")
        assert result.success is False
        assert result.error is not None  # PT018
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_read_directory(self, tmp_dir):
        tool = ReadFileTool()
        result = await tool.execute(path=str(tmp_dir))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_read_with_line_range(self, tmp_dir):
        f = tmp_dir / "lines.txt"
        f.write_text("line1\nline2\nline3\nline4\nline5\n")
        tool = ReadFileTool()
        result = await tool.execute(path=str(f), start_line=2, end_line=4)
        assert result.success is True
        assert "line2" in result.output
        assert "line4" in result.output
        assert "line5" not in result.output

    def test_schema(self):
        tool = ReadFileTool()
        assert tool.name == "read_file"
        assert "path" in tool.parameters_schema["properties"]
        assert "path" in tool.parameters_schema["required"]


class TestWriteFileTool:
    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_dir):
        f = tmp_dir / "new.py"
        tool = WriteFileTool()
        result = await tool.execute(path=str(f), content="x = 1\n")
        assert result.success is True
        assert f.read_text() == "x = 1\n"

    @pytest.mark.asyncio
    async def test_write_overwrite(self, tmp_dir):
        f = tmp_dir / "existing.py"
        f.write_text("old content\n")
        tool = WriteFileTool()
        result = await tool.execute(path=str(f), content="new content\n")
        assert result.success is True
        assert f.read_text() == "new content\n"

    def test_schema(self):
        tool = WriteFileTool()
        assert tool.name == "write_file"
        assert "path" in tool.parameters_schema["required"]
        assert "content" in tool.parameters_schema["required"]


class TestEditFileTool:
    @pytest.mark.asyncio
    async def test_edit_existing_text(self, tmp_dir):
        f = tmp_dir / "edit.py"
        f.write_text("def foo():\n    return 1\n")
        tool = EditFileTool()
        result = await tool.execute(
            path=str(f),
            search="return 1",
            replace="return 2",
        )
        assert result.success is True
        assert "return 2" in f.read_text()

    @pytest.mark.asyncio
    async def test_edit_not_found(self, tmp_dir):
        f = tmp_dir / "edit2.py"
        f.write_text("hello\n")
        tool = EditFileTool()
        result = await tool.execute(
            path=str(f),
            search="nonexistent",
            replace="replacement",
        )
        assert result.success is False
        assert result.error is not None  # PT018
        assert "未找到" in result.error

    @pytest.mark.asyncio
    async def test_edit_nonexistent_file(self):
        tool = EditFileTool()
        result = await tool.execute(
            path="/nonexistent/file.py",
            search="a",
            replace="b",
        )
        assert result.success is False

    def test_schema(self):
        tool = EditFileTool()
        assert tool.name == "edit_file"
        assert "search" in tool.parameters_schema["required"]
        assert "replace" in tool.parameters_schema["required"]


class TestListDirTool:
    @pytest.mark.asyncio
    async def test_list_directory(self, sample_project):
        tool = ListDirTool()
        result = await tool.execute(path=str(sample_project))
        assert result.success is True
        assert "main.py" in result.output
        assert "utils.py" in result.output

    @pytest.mark.asyncio
    async def test_list_nonexistent(self):
        tool = ListDirTool()
        result = await tool.execute(path="/nonexistent/dir")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_depth_limit(self, sample_project):
        tool = ListDirTool()
        result = await tool.execute(path=str(sample_project), depth=1)
        assert result.success is True
        # depth=1 不应包含 subdir 的内容
        assert "helper.py" not in result.output

    def test_schema(self):
        tool = ListDirTool()
        assert tool.name == "list_dir"
        assert "path" in tool.parameters_schema["properties"]


class TestSearchFileTool:
    @pytest.mark.asyncio
    async def test_search_found(self, sample_project):
        tool = SearchFileTool()
        result = await tool.execute(
            pattern="def main",
            path=str(sample_project),
        )
        assert result.success is True
        assert result.metadata["matches"] > 0
        assert "main.py" in result.output

    @pytest.mark.asyncio
    async def test_search_not_found(self, sample_project):
        tool = SearchFileTool()
        result = await tool.execute(
            pattern="nonexistent_pattern_xyz",
            path=str(sample_project),
        )
        assert result.success is True
        assert result.metadata["matches"] == 0

    @pytest.mark.asyncio
    async def test_search_with_context(self, tmp_dir):
        f = tmp_dir / "ctx.py"
        f.write_text("line1\nline2\ntarget\nline4\nline5\n")
        tool = SearchFileTool()
        result = await tool.execute(
            pattern="target",
            path=str(tmp_dir),
            context=1,
        )
        assert result.success is True
        assert "line2" in result.output
        assert "line4" in result.output

    def test_schema(self):
        tool = SearchFileTool()
        assert tool.name == "search_file"
        assert "pattern" in tool.parameters_schema["required"]
