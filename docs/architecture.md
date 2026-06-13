# Totoro Coding Agent — 架构设计文档

> 版本：v1.0 | 日期：2026-06-12 | 状态：设计稿

---

## 1. 设计目标

构建一个**通用 Coding Agent 平台**，支持：

| 目标 | 描述 |
|------|------|
| 自主编码 | Agent 可自主读文件、编写/修改代码、执行命令、运行测试，遇到阻断才向用户确认 |
| 双栈支持 | 优先支持 Python + JavaScript/TypeScript，设计可扩展以支持更多语言 |
| 多 Provider | 运行时可在 LongCat / OpenAI / Claude / 本地模型间切换 |
| 平台级能力 | 提供 CLI + REPL + HTTP API 三种交互方式，支持多租户会话 |
| 安全沙箱 | 文件/命令/网络操作有边界，不裸奔 |

---

## 2. 系统架构总览

```
                        ┌─────────────────────┐
                        │     Client Layer     │
                        │  CLI / REPL / HTTP   │
                        └─────────┬───────────┘
                                  │
                        ┌─────────▼───────────┐
                        │   API Gateway        │
                        │  (FastAPI / uvicorn)  │
                        │  - 会话管理            │
                        │  - 流式 SSE           │
                        │  - 认证中间件          │
                        └─────────┬───────────┘
                                  │
┌─────────────────────────────────▼─────────────────────────────────────┐
│                        Agent Engine                                   │
│                                                                       │
│  ┌───────────┐    ┌─────────────┐    ┌──────────────┐                │
│  │  Planner  │───▶│  ToolCaller  │───▶│  Validator   │                │
│  │ (意图分解) │    │  (工具调度)   │    │ (结果校验)    │                │
│  └───────────┘    └──────┬──────┘    └──────┬───────┘                │
│         ▲                 │                  │                        │
│         │            ┌────▼────┐             │                        │
│         │            │Sandbox  │             │                        │
│         │            │(安全执行) │             │                        │
│         │            └─────────┘             │                        │
│         │                                    ▼                        │
│         │         ┌────────────────────────────────┐                  │
│         └─────────│        Context Manager          │                  │
│                   │  Token 计数 / 消息压缩 / 持久化   │                  │
│                   └────────────────────────────────┘                  │
│                                  │                                    │
│  ┌───────────────────────────────▼──────────────────────────────┐     │
│  │                    Memory System                              │     │
│  │   Working Memory (会话内)  +  Long-term Memory (跨会话)       │     │
│  └──────────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────────┘
                                  │
                        ┌─────────▼───────────┐
                        │   Provider Layer     │
                        │  (多 LLM 适配)       │
                        │   LongCat / OpenAI   │
                        │   Anthropic / Local   │
                        └─────────────────────┘
```

---

## 3. 目录结构

```
totoro-agent/
├── agent/                          # 核心 Agent 引擎
│   ├── __init__.py
│   ├── engine.py                   # AgentEngine — 主入口，编排整个流程
│   ├── planner.py                  # Planner — 任务分解、意图识别、多步规划
│   ├── caller.py                   # ToolCaller — 工具调用调度器
│   ├── validator.py                # Validator — 结果校验、安全检查
│   ├── context.py                  # ContextManager — 消息历史、Token 管理、压缩
│   └── memory.py                   # Memory — 短期记忆 + 跨会话长期记忆
│
├── tools/                          # 工具系统
│   ├── __init__.py
│   ├── registry.py                 # ToolRegistry — 装饰器注册、JSON Schema 生成
│   ├── base.py                     # BaseTool — 工具协议（name, description, parameters, execute）
│   ├── file_tools.py               # ReadFile, WriteFile, EditFile, SearchFile, ListDir
│   ├── bash_tool.py                # Bash — Shell 命令执行（沙箱内）
│   ├── web_tools.py                # WebSearch, HttpFetch
│   ├── git_tool.py                 # GitStatus, GitDiff, GitLog, GitCommit
│   ├── lint_tool.py                # LintCheck — Pylint / ESLint / Ruff
│   ├── test_tool.py                # TestRun — pytest / jest / vitest
│   └── project_tool.py             # ProjectSummary — 项目结构理解、依赖分析
│
├── providers/                      # LLM 提供者抽象
│   ├── __init__.py
│   ├── base.py                     # ChatProvider 协议（Protocol 类）
│   ├── longcat_provider.py         # LongCat（Anthropic 兼容）
│   ├── openai_provider.py          # OpenAI 兼容（GPT-4 / GPT-4o）
│   ├── anthropic_provider.py       # Anthropic 原生（Claude）
│   └── registry.py               # ProviderRegistry — 运行时切换
│
├── sandbox/                        # 安全沙箱
│   ├── __init__.py
│   ├── executor.py                 # CommandExecutor — 超时、资源限制、输出截断
│   ├── filesystem.py               # FileSystemGuard — 读写白名单、路径校验
│   └── network.py                  # NetworkGuard — 网络访问控制
│
├── api/                            # HTTP API 层
│   ├── __init__.py
│   ├── app.py                      # FastAPI 应用
│   ├── routes/
│   │   ├── chat.py                 # POST /chat, GET /chat/stream (SSE)
│   │   ├── sessions.py             # CRUD /sessions
│   │   └── projects.py             # /projects — 项目管理
│   ├── schemas.py                  # Pydantic 请求/响应模型
│   └── middleware.py               # 认证、限流、日志
│
├── cli/                            # 命令行交互
│   ├── __init__.py
│   ├── repl.py                     # 交互式 REPL（prompt_toolkit）
│   └── commands.py                 # CLI 子命令（serve / chat / eval）
│
├── config.py                       # 全局配置（.env / YAML 加载）
├── constants.py                    # 常量（默认值、限制）
│
├── evals/                          # 评测套件（已有，扩展）
│   ├── conftest.py
│   ├── test_basic.py
│   ├── test_latency.py
│   ├── test_consistency.py
│   ├── test_streaming.py
│   ├── test_error_handling.py
│   ├── test_summary.py
│   └── test_tools.py               # 新增：工具调用评测
│
├── docs/
│   └── architecture.md             # 本文档
│
├── longcat_agent.py                # 向后兼容入口（保留）
├── longcat_agent_openai.py         # 向后兼容入口（保留）
├── pyproject.toml
└── README.md
```

---

## 4. 核心模块详细设计

### 4.1 Agent Engine（`agent/engine.py`）

这是整个系统的心脏。

```python
class AgentEngine:
    """编排 Agent 的完整执行流程。"""

    def __init__(
        self,
        provider: ChatProvider,
        tool_registry: ToolRegistry,
        context_manager: ContextManager,
        sandbox: SandboxConfig,
        max_iterations: int = 50,
    ): ...

    async def run(self, user_message: str, session: Session) -> AgentResponse:
        """
        主执行循环：
        1. 将 user_message 注入 context
        2. 调用 Planner 获取执行计划
        3. 进入 agentic loop:
           a. 调用 LLM 获取 response（含 tool_calls）
           b. 如果有 tool_calls → 执行工具 → 将结果追加到 context → 继续
           c. 如果只有 text → 任务完成，退出循环
        4. 返回最终结果
        """
        ...

    async def run_stream(self, user_message: str, session: Session) -> AsyncIterator[Event]:
        """流式版本，每个步骤 yield 事件（text_delta / tool_call / tool_result）"""
        ...
```

**Agentic Loop 核心逻辑**：

```
User Input
    │
    ▼
┌──────────────────┐
│  Context Manager  │ ◀── 注入 system prompt + 历史 + 工具定义
│  build messages   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   LLM Provider    │ ◀── 调用模型，返回 text + tool_calls
│   chat()         │
└────────┬─────────┘
         │
    ┌────▼────┐
    │有 tool  │──── Yes ──▶ ToolCaller.execute() ──▶ 结果追加到 context ──┐
    │_calls?  │                                                           │
    └────┬────┘                                                           │
         │ No                                                              │
         ▼                                                                 │
    ┌─────────┐                                                            │
    │ Validator │ ◀── 校验最终输出（代码可编译？测试通过？）                  │
    └────┬────┘                                                            │
         │                                                                 │
         ▼                                                                 │
    Final Response                                                        │
         ▲                                                                 │
         └─────────────────────────────────────────────────────────────────┘
```

### 4.2 Planner（`agent/planner.py`）

Planner 负责理解用户意图并分解为可执行步骤。

```python
class Planner:
    """将用户意图转化为结构化的执行计划。"""

    async def plan(self, user_message: str, context: PlanContext) -> ExecutionPlan:
        """
        - 简单任务（如"写个函数"）→ 单步计划
        - 复杂任务（如"重构这个模块"）→ 多步计划：
          1. 分析现有代码结构
          2. 识别需要修改的文件
          3. 逐个修改
          4. 运行测试验证
        """
        ...

@dataclass
class ExecutionPlan:
    steps: list[PlanStep]
    estimated_tools: list[str]  # 预计用到的工具
    risk_level: RiskLevel       # low / medium / high
```

### 4.3 Tool System（`tools/`）

#### 工具协议

```python
class BaseTool(ABC):
    """所有工具的基类。"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def parameters_schema(self) -> dict: ...  # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult: ...

@dataclass
class ToolResult:
    success: bool
    output: str               # 工具输出文本
    error: str | None = None  # 错误信息
    metadata: dict = field(default_factory=dict)  # 额外信息（如文件路径、行号）
```

#### 工具注册表

```python
class ToolRegistry:
    """工具注册中心。"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None: ...

    def get(self, name: str) -> BaseTool | None: ...

    def list_tools(self) -> list[ToolDefinition]:
        """返回所有工具的 JSON Schema 列表，注入 LLM system prompt。"""

    def load_preset(self, preset: str) -> None:
        """
        加载预设工具集：
        - "core": 文件读写 + Bash + Web
        - "full": core + Git + Lint + Test + Project
        - "readonly": 只读工具（文件读取 + 搜索）
        """
```

#### 内置工具清单

| 工具 | 功能 | 风险等级 |
|------|------|----------|
| `read_file` | 读取文件内容，支持行号范围 | 低 |
| `write_file` | 写入/创建文件 | 高 |
| `edit_file` | 精确编辑文件（搜索替换） | 高 |
| `list_dir` | 列出目录结构 | 低 |
| `search_file` | 文件内容搜索（grep） | 低 |
| `bash` | 执行 Shell 命令 | 高 |
| `web_search` | 网络搜索 | 低 |
| `web_fetch` | 获取 URL 内容 | 低 |
| `git_status` | 查看 Git 状态 | 低 |
| `git_diff` | 查看代码变更 | 低 |
| `git_log` | 查看提交历史 | 低 |
| `git_commit` | 提交代码 | 高 |
| `lint_check` | 运行代码检查 | 中 |
| `test_run` | 运行测试 | 中 |
| `project_summary` | 分析项目结构 | 低 |

### 4.4 Context Manager（`agent/context.py`）

```python
class ContextManager:
    """管理对话上下文，控制 Token 预算。"""

    def __init__(self, max_tokens: int = 100_000, compression_threshold: float = 0.8):
        self.max_tokens = max_tokens
        self.compression_threshold = compression_threshold

    def build_messages(
        self,
        system_prompt: str,
        history: list[Message],
        tool_definitions: list[dict],
        project_context: ProjectContext | None = None,
    ) -> list[dict]:
        """
        组装完整消息列表：
        1. System prompt（含工具定义、项目上下文、安全规则）
        2. 历史消息（可能经过压缩）
        3. 当前用户消息
        """
        ...

    def maybe_compress(self, messages: list[dict]) -> list[dict]:
        """
        当 Token 数超过阈值的 80% 时，压缩历史消息：
        - 保留最近 N 轮
        - 对更早的消息做摘要
        """
        ...

    def estimate_tokens(self, messages: list[dict]) -> int:
        """快速估算 Token 数（tiktoken 或启发式）。"""
        ...
```

**System Prompt 设计**：

```
You are LongCat Coding Agent, an expert software engineer.

## Capabilities
- Read, write, and edit files
- Execute shell commands
- Search the web for information
- Run tests and linting tools

## Rules
1. Always read a file before editing it
2. Make minimal, focused changes
3. Run tests after code changes
4. If you encounter an error, try to fix it autonomously
5. Stop and ask the user if you're unsure about a destructive action
6. Prefer the most idiomatic patterns for the language

## Project Context
{project_context}

## Available Tools
{tool_definitions}
```

### 4.5 Provider Layer（`providers/`）

```python
class ChatProvider(Protocol):
    """LLM 提供者协议。所有 provider 必须实现此接口。"""

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> ChatResponse: ...

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamEvent]: ...

@dataclass
class ChatResponse:
    text: str
    tool_calls: list[ToolCall]
    usage: TokenUsage
    finish_reason: str  # "stop" | "tool_calls" | "length"

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
```

**Provider 注册表**：

```python
class ProviderRegistry:
    _providers: dict[str, ChatProvider] = {}

    @classmethod
    def register(cls, name: str, provider: ChatProvider): ...

    @classmethod
    def get(cls, name: str) -> ChatProvider: ...

    @classmethod
    def list_providers(cls) -> list[str]: ...
```

### 4.6 Sandbox（`sandbox/`）

```python
@dataclass
class SandboxConfig:
    """沙箱配置。"""
    allowed_paths: list[str]       # 可写路径白名单
    blocked_commands: list[str]    # 禁止的命令（rm -rf, sudo, etc.）
    max_execution_time: int = 30    # 单次命令超时（秒）
    max_output_size: int = 10_000  # 输出截断长度
    network_allowed: bool = False  # 是否允许网络访问

class CommandExecutor:
    """安全的命令执行器。"""

    async def execute(self, command: str, config: SandboxConfig) -> CommandResult:
        1. 命令黑名单检查
        2. 路径白名单验证
        3. subprocess 异步执行（带超时）
        4. 输出截断
        5. 返回结果
```

### 4.7 Memory System（`agent/memory.py`）

```python
class MemoryManager:
    """管理短期和长期记忆。"""

    # 短期记忆：当前会话内的上下文
    working_memory: WorkingMemory

    # 长期记忆：跨会话持久化（存储在项目 .workbuddy/memory/ 下）
    long_term_memory: LongTermMemory

    async def save_session(self, session: Session): ...
    async def load_session(self, session_id: str) -> Session: ...
    async def index_project(self, project_path: str): ...
```

---

## 5. 数据流示例

### 5.1 用户说："帮我在 main.py 里加一个 hello world 的 Python 函数"

```
1. User → AgentEngine.run("帮我在 main.py 里加一个 hello world 的 Python 函数")
2. AgentEngine → ContextManager.build_messages()
   → [System(tools + rules), User(message)]
3. AgentEngine → Provider.chat(messages, tools)
   → LLM 返回: tool_calls=[ReadFile("main.py")]
4. AgentEngine → ToolCaller.execute("read_file", path="main.py")
   → ToolResult(success=True, output="...文件内容...")
5. 结果追加到 context → 再次调用 LLM
   → LLM 返回: tool_calls=[EditFile("main.py", search="...", replace="...")]
6. AgentEngine → ToolCaller.execute("edit_file", ...)
   → ToolResult(success=True, output="File updated")
7. 结果追加到 context → 再次调用 LLM
   → LLM 返回: text="已在 main.py 中添加 hello_world() 函数", tool_calls=[]
8. AgentEngine → Validator.validate(response)
   → 检查代码语法是否正确
9. AgentEngine → 返回最终响应给用户
```

### 5.2 流式 API 事件流

```jsonl
{"type": "text_delta", "content": "我来帮你..."}
{"type": "tool_call_start", "tool": "read_file", "arguments": {"path": "main.py"}}
{"type": "tool_call_end", "tool": "read_file", "result": "..."}
{"type": "text_delta", "content": "现在添加函数..."}
{"type": "tool_call_start", "tool": "edit_file", "arguments": {...}}
{"type": "tool_call_end", "tool": "edit_file", "result": "File updated"}
{"type": "text_delta", "content": "已完成！"}
{"type": "done", "usage": {"input": 1234, "output": 567}}
```

---

## 6. API 设计

### 6.1 REST API

```
POST   /api/v1/chat              # 非流式对话
GET    /api/v1/chat/stream       # SSE 流式对话
POST   /api/v1/sessions          # 创建会话
GET    /api/v1/sessions/:id      # 获取会话详情
DELETE /api/v1/sessions/:id      # 删除会话
GET    /api/v1/sessions/:id/messages  # 获取消息历史
POST   /api/v1/projects          # 注册项目
GET    /api/v1/projects/:id      # 获取项目信息
```

### 6.2 请求/响应格式

```json
// POST /api/v1/chat
{
  "message": "帮我写一个 hello world 函数",
  "session_id": "optional-session-id",
  "provider": "longcat",           // 可选，默认从配置读取
  "tools": ["read_file", "write_file", "bash"],  // 可选，默认全量
  "project_path": "/path/to/project"  // 可选
}

// Response
{
  "session_id": "sess_abc123",
  "message": "已在 main.py 中添加 hello_world() 函数",
  "tool_calls": [
    {"tool": "read_file", "arguments": {"path": "main.py"}, "result": "..."},
    {"tool": "edit_file", "arguments": {...}, "result": "File updated"}
  ],
  "usage": {"input_tokens": 1234, "output_tokens": 567},
  "duration_ms": 3200
}
```

---

## 7. 安全策略

| 层面 | 策略 |
|------|------|
| **文件访问** | 路径白名单，默认只允许项目目录内读写 |
| **命令执行** | 黑名单（rm -rf / sudo / curl | sh），超时 30s，输出截断 |
| **网络** | 默认关闭，需要显式开启 |
| **Token 限制** | 单次请求 max_tokens 上限，防止无限生成 |
| **迭代上限** | 单次任务最多 50 次 tool call，防止死循环 |
| **敏感信息** | 日志中脱敏 API Key、Token |

---

## 8. 配置系统

```yaml
# config.yaml
provider:
  default: longcat
  longcat:
    api_key: ${LONGCAT_API_KEY}
    base_url: https://api.longcat.chat/anthropic
    model: LongCat-2.0-Preview
  openai:
    api_key: ${OPENAI_API_KEY}
    model: gpt-4o

agent:
  max_iterations: 50
  max_tokens: 100000
  default_tools: full  # core / full / readonly

sandbox:
  allowed_paths:
    - ~/workspace
  blocked_commands:
    - "rm -rf"
    - "sudo"
    - "curl | sh"
  max_execution_time: 30
  network_allowed: false

api:
  host: 0.0.0.0
  port: 8000
  auth_token: ${API_AUTH_TOKEN}
```

---

## 9. 实施路线图

### Phase 1：核心引擎（1-2 周）
- [ ] Provider 抽象层（base + longcat + openai）
- [ ] Tool 协议 + 注册表
- [ ] 文件工具（read / write / edit / list / search）
- [ ] Bash 工具（沙箱执行）
- [ ] AgentEngine 主循环（agentic loop）
- [ ] ContextManager（基础版）

### Phase 2：工具扩展（1 周）
- [ ] Git 工具
- [ ] Lint 工具
- [ ] Test 工具
- [ ] Web 工具
- [ ] Project 分析工具

### Phase 3：平台层（1-2 周）
- [ ] FastAPI 应用 + 路由
- [ ] SSE 流式接口
- [ ] 会话管理
- [ ] REPL（交互式命令行）

### Phase 4：增强（持续迭代）
- [ ] Planner（多步规划）
- [ ] Memory（跨会话记忆）
- [ ] 代码审查模式
- [ ] 多语言支持扩展
- [ ] 评测套件扩展

---

## 10. 技术选型决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 语言 | Python 3.11+ | 与现有代码一致，async/await 原生支持 |
| HTTP 框架 | FastAPI | 原生 async，自动 OpenAPI 文档，SSE 支持好 |
| REPL | prompt_toolkit | 成熟的 Python 交互式终端库 |
| 配置 | pydantic-settings | 类型安全，.env 原生支持 |
| 沙箱 | subprocess + 路径校验 | 简单够用，后续可升级 Docker |
| Token 计算 | tiktoken | OpenAI 官方，快速准确 |
| 测试 | pytest + pytest-asyncio | 与现有 evals 一致 |

---

## 11. 开放问题（五公理裁决结果）

### 11.1 沙箱隔离级别 — ✅ 裁决完毕

**结论**：subprocess + 路径校验 + 命令黑名单，Docker 留 Protocol 扩展点

| 公理 | 判定 |
|------|------|
| A1 | 定义 `CommandExecutor` Protocol 接口，Docker 是可替换实现 |
| A2 | 零额外依赖，调试简单；Docker 引入冷启动 + 镜像管理的 surprise |
| A3 | subprocess <50ms 反馈 vs Docker 1-3s 冷启动，反射 loop 必须快 |
| A4 | 沙箱逻辑不绑定 Docker，切换成本为零 |
| A5（最高优先级） | ~50 行代码 vs Docker 维护 10x 复杂度 |

→ 实现 `sandbox/executor.py`，Protocol + subprocess，Docker executor 留作 `DockerExecutor` 后续实现

### 11.2 多租户隔离 — ✅ 裁决完毕

**结论**：Day 1 有 Session 模型 + 每会话独立 workspace，认证留 L2 扩展

| 公理 | 判定 |
|------|------|
| A1 | Session 数据模型 = 天然隔离边界，API 层不需改动 |
| A2 | 不实现认证 = 零 uncertainty，单用户场景够用 |
| A3 | Session 让 `ContextManager.load(session_id)` 有稳定上下文边界 |
| A4 | Session 是 plain dataclass，不绑定任何认证机制（JWT/OAuth/SSO 自由叠加） |
| A5（最高优先级） | ~20 行代码 vs 认证系统 10x 复杂度 |

→ 实现 `Session` dataclass，暂不加认证中间件

### 11.3 代码索引 — ✅ 裁决完毕

**结论**：用 `rg` (ripgrep) 替代 AST/embedding 索引，索引作为 L2 skill Phase 4 引入

| 公理 | 判定 |
|------|------|
| A1 | CodeIndex 是 ToolRegistry 的注册 tool，不引入额外抽象 |
| A2 | rg <50ms 零维护 vs embedding pipeline 五步 uncertainty 链 |
| A3 | list_dir + grep 两步完成 project perceive，embedding 需 query→retrieve→rerank 三步 |
| A4 | grep POSIX 100 年兼容，AST parser 锁语言版本，向量库锁模型版本 |
| A5（最高优先级） | 0 行额外代码 vs ~2000 行 embedding 系统 |

→ `project_summary` 用 `os.walk` + 入口文件读取即可

### 11.4 并发策略 — ✅ 裁决完毕

**结论**：asyncio 原生并发，不引入 broker/queue，记录为 L3 配置项

| 公理 | 判定 |
|------|------|
| A1 | asyncio task = 天然并发边界，不需 task queue/orchestrator |
| A2 | `asyncio.gather()` 零依赖 vs Celery+Redis 额外基础设施 surprise |
| A3 | 每个 Agent instance 是独立 async task，self-contained loop |
| A4 | asyncio 不绑定外部 broker，水平扩展只需 `uvicorn --workers N` |
| A5（最高优先级） | `aiofiles` 一行 pip install vs Redis+Celery ~500 行配置 |

→ 所有 IO 操作 async 化，单 worker uvicorn，不做过早优化

### 统一判定模式

四个决策共同主线：**A5（热力学箭头）** 优先级最高 — 最小 negentropy 换取最大演进自由度。每个选择都保留升级路径（Protocol 接口、L2 skill、配置项），不提前 lock-in。
