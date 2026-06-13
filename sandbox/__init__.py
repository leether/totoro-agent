"""沙箱模块 — 安全执行边界。

当前实现：tools/bash_tool.py 内嵌黑名单 + 超时 + 输出截断。
扩展点：CommandExecutor Protocol → 后续可替换为 DockerExecutor。
"""

from sandbox.executor import CommandExecutor, SandboxConfig, SubprocessExecutor

__all__ = ["CommandExecutor", "SandboxConfig", "SubprocessExecutor"]
