"""测试 tools/project_tool.py — 项目分析工具。"""
import pytest

from tools.project_tool import ProjectSummaryTool


class TestProjectSummaryTool:
    @pytest.mark.asyncio
    async def test_summary_basic(self, sample_project):
        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(sample_project))
        assert result.success is True
        assert "main.py" in result.output
        assert "utils.py" in result.output

    @pytest.mark.asyncio
    async def test_summary_contains_dir_tree(self, sample_project):
        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(sample_project))
        assert "目录树" in result.output

    @pytest.mark.asyncio
    async def test_summary_contains_file_stats(self, sample_project):
        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(sample_project))
        assert "Python: 3" in result.output  # main.py, utils.py, subdir/helper.py

    @pytest.mark.asyncio
    async def test_summary_nonexistent(self):
        tool = ProjectSummaryTool()
        result = await tool.execute(path="/nonexistent/dir")
        assert result.success is False
        assert result.error is not None and "不存在" in result.error

    @pytest.mark.asyncio
    async def test_summary_metadata(self, sample_project):
        tool = ProjectSummaryTool()
        result = await tool.execute(path=str(sample_project))
        assert result.metadata["python_files"] == 3

    def test_schema(self):
        tool = ProjectSummaryTool()
        assert tool.name == "project_summary"
        assert "path" in tool.parameters_schema["required"]
