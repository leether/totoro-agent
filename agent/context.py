"""ContextManager — 消息历史、Token 管理、压缩、会话持久化。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tools.registry import ToolRegistry


@dataclass
class Session:
    """会话模型 — 隔离不同用户的 Agent 上下文。"""

    id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        return cls(
            id=data["id"],
            messages=data.get("messages", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
        )

    def save(self, directory: str) -> Path:
        """将会话持久化到磁盘。"""
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{self.id}.json"
        file_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return file_path

    @classmethod
    def load(cls, session_id: str, directory: str) -> Session | None:
        """从磁盘恢复会话。"""
        file_path = Path(directory) / f"{session_id}.json"
        if not file_path.exists():
            return None
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)


class ContextManager:
    """对话上下文管理器。控制 Token 预算，管理消息历史。"""

    def __init__(
        self,
        system_prompt: str = "",
        max_tokens: int = 100_000,
        compression_threshold: float = 0.8,
    ):
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._compression_threshold = compression_threshold

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self._system_prompt = value

    def build_messages(
        self,
        history: list[dict[str, Any]],
        tool_registry: ToolRegistry | None = None,
        project_context: str = "",
    ) -> list[dict[str, Any]]:
        """
        组装完整消息列表注入 LLM。

        结构：
        1. system prompt（含工具定义 + 项目上下文）
        2. 历史消息（可能经过压缩）
        """
        messages: list[dict[str, Any]] = []

        # System prompt
        system_content = self._system_prompt
        if project_context:
            system_content += f"\n\n## Project Context\n{project_context}"

        # 注入工具定义到 system prompt（Anthropic 方式）
        if tool_registry:
            tool_defs = tool_registry.tool_definitions()
            if tool_defs:
                import json

                system_content += f"\n\n## Available Tools\n```json\n{json.dumps(tool_defs, ensure_ascii=False, indent=2)}\n```"

        messages.append({"role": "system", "content": system_content})

        # 历史消息
        messages.extend(history)

        return messages

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        快速估算 Token 数。
        使用启发式：1 token ≈ 4 字符（英文）或 ≈ 1.5 字符（中文）。
        """
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        total_chars += len(block["text"])

        # 粗略估算：混合内容约 1 token = 3 字符
        return total_chars // 3

    def maybe_compress(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """超过 Token 阈值时压缩历史。"""
        token_count = self.estimate_tokens(messages)
        threshold = int(self._max_tokens * self._compression_threshold)

        if token_count <= threshold:
            return messages

        # 保留 system + 最近 6 轮 + 将更早的消息折叠为摘要
        if len(messages) <= 8:
            return messages

        system_msg = messages[0] if messages[0].get("role") == "system" else None
        recent = messages[-6:]
        older = messages[1:-6] if system_msg else messages[:-6]

        # 生成摘要
        summary_text = self._summarize(older)
        summary_msg = {
            "role": "user",
            "content": f"[历史对话摘要]\n{summary_text}",
        }

        compressed = []
        if system_msg:
            compressed.append(system_msg)
        compressed.append(summary_msg)
        compressed.extend(recent)

        return compressed

    def _summarize(self, messages: list[dict[str, Any]]) -> str:
        """生成消息摘要（轻量版 — 截取每段前 100 字符）。"""
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                preview = content[:100].replace("\n", " ")
                parts.append(f"[{role}] {preview}...")
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        preview = block["text"][:100].replace("\n", " ")
                        parts.append(f"[{role}] {preview}...")
                        break

        return "\n".join(parts[:20])  # 最多 20 条

    def compress_history(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """公开接口：压缩历史消息。"""
        return self.maybe_compress(messages)

    def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """公开接口：获取估算 token 数。"""
        return self.estimate_tokens(messages)

    @staticmethod
    def session_storage_path(base_dir: str = ".workbuddy/sessions") -> str:
        """获取会话存储路径。"""
        return str(Path(base_dir))
