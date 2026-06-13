"""AgentEngine — 核心 Agent 引擎，编排 agentic loop。

流程：User Input → Context Manager → LLM → Tool Call → 工具执行 → 结果回注 → 循环直到完成。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator

from agent.context import ContextManager, Session
from providers.base import ChatProvider, ChatResponse, StreamEvent, ToolCall, ToolCallDefinition
from tools.base import ToolResult
from tools.registry import ToolRegistry


DEFAULT_SYSTEM_PROMPT = """\
You are Totoro Coding Agent, an expert software engineer and coding assistant.

## Capabilities
- Read, write, and edit files in the project
- Execute shell commands (with safety guardrails)
- Search files and code using grep/regex
- Search the web for documentation and solutions
- Analyze project structure and dependencies
- Run git operations (status, diff, log)

## Rules
1. Always read a file before editing it
2. Make minimal, focused changes — don't rewrite entire files unless asked
3. Use the edit_file tool for precise changes, write_file for new files
4. Search for existing code patterns before adding new ones
5. Run tests after code changes when possible
6. If you encounter an error, try to fix it autonomously
7. Prefer idiomatic patterns for the language you're working with
8. Comment your code in the same language as the project

## Safety
- Do not delete files or directories unless explicitly asked
- Do not execute destructive commands (rm -rf, sudo, etc.)
- Stop and ask if you're unsure about a destructive action
- Keep changes focused and reversible
"""


@dataclass
class AgentResponse:
    """Agent 最终响应。"""
    session_id: str
    message: str
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    iterations: int = 0
    finished: bool = True


@dataclass
class AgentConfig:
    """Agent 配置。"""
    max_iterations: int = 50
    max_tokens: int = 4096
    temperature: float = 0.1
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    tool_preset: str = "full"  # "core" | "full" | "readonly"
    session_dir: str = ".workbuddy/sessions"


class AgentEngine:
    """核心 Agent 引擎。编排 LLM + 工具的 agentic loop。"""

    def __init__(
        self,
        provider: ChatProvider,
        tool_registry: ToolRegistry,
        context_manager: ContextManager,
        config: AgentConfig | None = None,
    ):
        self._provider = provider
        self._tools = tool_registry
        self._context = context_manager
        self._config = config or AgentConfig()

        # 设置 system prompt
        self._context.system_prompt = self._config.system_prompt

    @classmethod
    def create(
        cls,
        provider: ChatProvider,
        config: AgentConfig | None = None,
        tool_preset: str = "full",
        project_path: str = "",
    ) -> AgentEngine:
        """便捷工厂方法：自动组装 ToolRegistry + ContextManager。"""
        from tools.file_tools import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool, SearchFileTool
        from tools.bash_tool import BashTool

        registry = ToolRegistry()
        registry.load_preset(tool_preset)

        ctx = ContextManager(
            system_prompt=cls._build_system_prompt(DEFAULT_SYSTEM_PROMPT, project_path),
            max_tokens=100_000,
        )

        engine = cls(
            provider=provider,
            tool_registry=registry,
            context_manager=ctx,
            config=config,
        )
        return engine

    @staticmethod
    def _build_system_prompt(base: str, project_path: str) -> str:
        prompt = base
        if project_path:
            prompt += f"\n\n## Working Directory\n{project_path}"
        return prompt

    # ============ 非流式运行 ============

    async def run(
        self,
        user_message: str,
        session: Session | None = None,
    ) -> AgentResponse:
        """
        核心执行循环。

        1. 注入 user_message
        2. agentic loop:
           a. 调用 LLM → 获取 response
           b. 有 tool_calls → 执行工具 → 结果回注 → 继续
           c. 只有 text → 完成
        3. 返回最终结果
        """
        if session is None:
            session = Session(id=f"session_{uuid.uuid4().hex[:12]}")

        session.messages.append({"role": "user", "content": user_message})
        session_messages = session.messages

        tool_defs = [
            ToolCallDefinition(
                name=t["name"],
                description=t["description"],
                parameters_schema=t["parameters_schema"],
            )
            for t in self._tools.tool_definitions()
        ]

        iterations = 0
        total_tool_calls: list[dict] = []

        while iterations < self._config.max_iterations:
            iterations += 1

            # 检查 Token 预算
            messages = self._context.build_messages(session_messages)

            # 调用 LLM
            llm_response = await self._provider.chat(
                messages=messages,
                tools=tool_defs,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )

            # 如果是 text only → 任务完成
            if llm_response.text and not llm_response.tool_calls:
                session.messages.append({
                    "role": "assistant",
                    "content": llm_response.text,
                })
                usage_dict = {
                    "input_tokens": llm_response.usage.input_tokens,
                    "output_tokens": llm_response.usage.output_tokens,
                }

                return AgentResponse(
                    session_id=session.id,
                    message=llm_response.text,
                    tool_calls=total_tool_calls,
                    usage=usage_dict,
                    iterations=iterations,
                    finished=True,
                )

            # 有 tool_calls → 执行工具
            if llm_response.tool_calls:
                # 将 assistant 消息加入历史
                assistant_msg = {
                    "role": "assistant",
                    "content": llm_response.text or "",
                }
                session.messages.append(assistant_msg)

                for tool_call in llm_response.tool_calls:
                    # 将 tool_call 加入历史
                    session.messages.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                            },
                        }],
                    })

                    # 执行工具
                    result = await self._execute_tool(tool_call)

                    total_tool_calls.append({
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "success": result.success,
                        "output_preview": result.output[:200],
                    })

                    # 将工具结果注入历史
                    session.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.to_message(),
                    })

                    # 保存 tool_call 到 assistant message
                    assistant_msg["tool_calls"] = [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                        },
                    }]

                    # 压缩检查
                    session.messages = self._context.compress_history(session.messages)

            # 只有 text 没有 tool_calls → 也完成
            if not llm_response.tool_calls and llm_response.text:
                session.messages.append({
                    "role": "assistant",
                    "content": llm_response.text,
                })
                return AgentResponse(
                    session_id=session.id,
                    message=llm_response.text,
                    tool_calls=total_tool_calls,
                    usage={"input_tokens": llm_response.usage.input_tokens, "output_tokens": llm_response.usage.output_tokens},
                    iterations=iterations,
                    finished=True,
                )

        # 达到最大迭代次数
        return AgentResponse(
            session_id=session.id,
            message="达到最大迭代次数，任务未完全完成。",
            tool_calls=total_tool_calls,
            iterations=iterations,
            finished=False,
        )

    # ============ 流式运行 ============

    async def run_stream(
        self,
        user_message: str,
        session: Session | None = None,
    ) -> AsyncIterator[dict]:
        """流式版的 run，yield 每个事件。"""
        if session is None:
            session = Session(id=f"session_{uuid.uuid4().hex[:12]}")

        session.messages.append({"role": "user", "content": user_message})

        tool_defs = [
            ToolCallDefinition(
                name=t["name"],
                description=t["description"],
                parameters_schema=t["parameters_schema"],
            )
            for t in self._tools.tool_definitions()
        ]

        iterations = 0
        final_text_parts: list[str] = []

        while iterations < self._config.max_iterations:
            iterations += 1
            messages = self._context.build_messages(session.messages)

            # 收集当前迭代的所有 tool_calls
            pending_tool_calls: list[ToolCall] = []
            current_text = ""

            async for event in self._provider.stream_chat(
                messages=messages,
                tools=tool_defs,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            ):
                if event.type == "text_delta":
                    current_text += event.content
                    yield {"type": "text_delta", "content": event.content}

                elif event.type == "tool_call_start":
                    pending_tool_calls.append(ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name=event.tool_name,
                        arguments=event.tool_arguments,
                    ))
                    yield {"type": "tool_call_start", "tool": event.tool_name, "arguments": event.tool_arguments}

                elif event.type == "done":
                    yield {"type": "done", "usage": event.usage}

            if current_text:
                final_text_parts.append(current_text)
                session.messages.append({"role": "assistant", "content": current_text})

            if not pending_tool_calls:
                # 无 tool_calls → 完成
                break

            # 执行所有 tool calls
            for tool_call in pending_tool_calls:
                result = await self._execute_tool(tool_call)
                yield {
                    "type": "tool_result",
                    "tool": tool_call.name,
                    "success": result.success,
                    "output": result.output[:500],
                }

                session.messages.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                        },
                    }],
                })
                session.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.to_message(),
                })

            session.messages = self._context.compress_history(session.messages)

        final_text = "".join(final_text_parts)
        yield {
            "type": "final",
            "message": final_text,
            "iterations": iterations,
            "session_id": session.id,
        }

    # ============ 工具执行 ============

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行单个工具调用。"""
        tool = self._tools.get(tool_call.name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"未知工具: {tool_call.name}",
            )

        try:
            result = await tool.execute(**tool_call.arguments)
            return result
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"工具执行异常: {e}",
            )
