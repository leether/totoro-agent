"""测试 tools/bash_tool.py — Bash 工具。"""
import pytest

from tools.bash_tool import BashTool, _is_blocked


class TestIsBlocked:
    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "rm -rf /home",
        "sudo apt install",
        "sudo\tls",
        "curl | sh",
        "curl | bash",
        "wget | sh",
        "mkfs.ext4 /dev/sda",
        "dd if=/dev/zero",
        "chmod 777 /",
        "chown root /",
        "shutdown -h now",
        "shutdown -r now",
        "reboot",
        "killall -9 python",
    ])
    def test_blocked(self, cmd):
        assert _is_blocked(cmd) is True

    @pytest.mark.parametrize("cmd", [
        "ls -la",
        "cat file.py",
        "echo hello",
        "python main.py",
        "git status",
        "mkdir test_dir",
        "rm file.py",  # 只删文件，不匹配 rm -rf
    ])
    def test_allowed(self, cmd):
        assert _is_blocked(cmd) is False


class TestBashTool:
    @pytest.mark.asyncio
    async def test_simple_command(self):
        tool = BashTool()
        result = await tool.execute(command="echo hello")
        assert result.success is True
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_command_failure(self):
        tool = BashTool()
        result = await tool.execute(command="false")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_blocked_command(self):
        tool = BashTool()
        result = await tool.execute(command="rm -rf /")
        assert result.success is False
        assert result.error is not None and "禁止" in result.error

    @pytest.mark.asyncio
    async def test_output_truncation(self):
        tool = BashTool(max_output_size=50)
        result = await tool.execute(command="python3 -c \"print('x' * 200)\"")
        assert result.success is True
        assert result.output is not None and "截断" in result.output

    @pytest.mark.asyncio
    async def test_metadata(self):
        tool = BashTool()
        result = await tool.execute(command="echo test")
        assert result.metadata["command"] == "echo test"
        assert result.metadata["returncode"] == 0

    def test_schema(self):
        tool = BashTool()
        assert tool.name == "bash"
        assert "command" in tool.parameters_schema["required"]
