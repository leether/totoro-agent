"""全局配置 — .env 加载 + dataclass 绑定。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


@dataclass
class TotoroConfig:
    """Totoro 后端配置。"""
    api_key: str = field(default_factory=lambda: os.environ.get("TOTORO_API_KEY", ""))
    base_url: str = "https://api.longcat.chat/anthropic"
    model: str = "LongCat-2.0-Preview"


@dataclass
class OpenAIConfig:
    """OpenAI 后端配置。"""
    api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"


@dataclass
class AnthropicConfig:
    """Anthropic 后端配置。"""
    api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    model: str = "claude-sonnet-4-20250514"


@dataclass
class AgentSettings:
    """Agent 完整配置。"""
    provider_name: str = field(default_factory=lambda: os.environ.get("AGENT_PROVIDER", "totoro"))
    max_iterations: int = 50
    max_tokens: int = 4096
    temperature: float = 0.1
    tool_preset: str = "full"
    session_dir: str = ".workbuddy/sessions"

    totoro: TotoroConfig = field(default_factory=TotoroConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = field(default_factory=AnthropicConfig)

    def resolve_provider(self) -> str:
        """根据配置决定使用哪个 provider。"""
        return self.provider_name
