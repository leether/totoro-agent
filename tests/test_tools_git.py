"""测试 tools/git_tool.py — Git 工具。"""
import subprocess

import pytest

from tools.git_tool import GitDiffTool, GitLogTool, GitStatusTool


@pytest.fixture
def git_repo(tmp_dir):
    """初始化一个 git 仓库并做一次提交。"""
    subprocess.run(["git", "init"], cwd=str(tmp_dir), capture_output=True)  # noqa: S607
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_dir), capture_output=True)  # noqa: S607
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_dir), capture_output=True)  # noqa: S607
    (tmp_dir / "file.txt").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_dir), capture_output=True)  # noqa: S607
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_dir), capture_output=True)  # noqa: S607
    return tmp_dir


class TestGitStatusTool:
    @pytest.mark.asyncio
    async def test_clean_workdir(self, git_repo):
        tool = GitStatusTool()
        result = await tool.execute(path=str(git_repo))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_dirty_workdir(self, git_repo):
        (git_repo / "new.txt").write_text("new file\n")
        tool = GitStatusTool()
        result = await tool.execute(path=str(git_repo))
        assert result.success is True
        assert "new.txt" in result.output

    def test_schema(self):
        tool = GitStatusTool()
        assert tool.name == "git_status"


class TestGitDiffTool:
    @pytest.mark.asyncio
    async def test_no_diff(self, git_repo):
        tool = GitDiffTool()
        result = await tool.execute(path=str(git_repo))
        assert result.success is True

    def test_schema(self):
        tool = GitDiffTool()
        assert tool.name == "git_diff"


class TestGitLogTool:
    @pytest.mark.asyncio
    async def test_log(self, git_repo):
        tool = GitLogTool()
        result = await tool.execute(path=str(git_repo))
        assert result.success is True
        assert "initial commit" in result.output

    @pytest.mark.asyncio
    async def test_log_limit(self, git_repo):
        tool = GitLogTool()
        result = await tool.execute(path=str(git_repo), limit=1)
        assert result.success is True

    def test_schema(self):
        tool = GitLogTool()
        assert tool.name == "git_log"
