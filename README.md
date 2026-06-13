# 🐾 Totoro Coding Agent

<div align="center">

**A general-purpose coding agent with tool use, Rich REPL, and multi-provider LLM support.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/leether/totoro-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/leether/totoro-agent/actions/workflows/ci.yml)

[English](#english) · [中文](#中文)

</div>

---

## English

Totoro is a **general-purpose Coding Agent** built from scratch. It runs an agentic loop (reason → call tools → observe → repeat), ships with 10+ built-in tools, supports multiple LLM backends, and exposes both a beautiful terminal UI and a clean library API.

### ✨ Features

| Feature | Description |
|---------|-------------|
| **Agentic Loop** | Autonomous planning, tool execution, and result integration |
| **10+ Built-in Tools** | File read/write/edit, Bash, Git, Web search/fetch, project analysis |
| **Multi-Provider** | Switch between LongCat, OpenAI-compatible, and Anthropic-compatible APIs at runtime |
| **Unified CLI** | Single `totoro` command for REPL, one-shot chat, and status checks |
| **Rich REPL** | Syntax highlighting, panels, and colored output in the terminal |
| **Session Management** | Persistent sessions with message history and context compression |
| **Safety Sandbox** | Command timeout, output truncation, and extensible isolation via Protocol |
| **Zero SDK Lock-in** | Pure `httpx`-based HTTP clients for LLM backends |

### 🚀 Quick Start

```bash
# Clone
git clone https://github.com/leether/totoro-agent.git && cd totoro-agent

# Install dependencies (recommended)
uv sync

# Or with pip
pip install -e .

# Configure API key
echo 'LONGCAT_API_KEY=your_key_here' > .env

# Launch REPL
totoro
```

### ⌨️ CLI Commands

```bash
totoro                              # Start interactive REPL (default)
totoro repl                         # Start REPL explicitly
totoro status                       # Show current configuration
totoro chat "Write a hello world"   # Single-turn chat
totoro chat "Explain this repo" --stream
```

### ⚙️ Configuration

Create a `.env` file in the project root:

```bash
# Default provider: totoro (LongCat)
LONGCAT_API_KEY=your_longcat_key

# Optional: switch provider
AGENT_PROVIDER=totoro        # or openai / anthropic

# Optional provider keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### 📁 Project Structure

```
totoro-agent/
├── agent/          # Core engine: agentic loop, context, sessions
├── providers/      # LLM backends: LongCat, OpenAI-compatible, Anthropic-compatible
├── tools/          # Built-in tools: file, bash, git, web, project
├── sandbox/        # Safety sandbox and isolation abstractions
├── cli/            # Rich REPL terminal interface and unified CLI entry
├── api/            # HTTP API layer (FastAPI, planned)
├── evals/          # Evaluation test suite
├── tests/          # Unit test suite
└── .github/        # CI, issue/PR templates, Dependabot config
```

### 🔧 Usage as Library

```python
from providers.totoro_provider import TotoroProvider
from agent.engine import AgentEngine

provider = TotoroProvider(api_key="your_key")
engine = AgentEngine.create(provider=provider, tool_preset="full")

# Non-streaming
response = await engine.run("Write a hello world function")
print(response.message)

# Streaming
async for event in engine.run_stream("Analyze this codebase"):
    if event["type"] == "text_delta":
        print(event["content"], end="")
```

### 🛠️ Development

```bash
# Install all dev dependencies and pre-commit hooks
uv sync
pre-commit install

# Run the full local CI pipeline
make all          # lint + format-check + typecheck + test
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

### 📖 Architecture

See [docs/architecture.md](docs/architecture.md) for the full design document, data flow, security strategy, and roadmap.

### 🛠️ Roadmap

- [x] Phase 1: Core engine + file tools + Rich REPL + unified CLI
- [ ] Phase 2: Lint/Test tools + Git workflow tools
- [ ] Phase 3: FastAPI HTTP API + SSE streaming
- [ ] Phase 4: Planner + multi-session memory + code review mode

---

## 中文

Totoro 是一个**从零构建的通用 Coding Agent**。它运行完整的 agentic 循环（推理 → 调用工具 → 观察 → 重复），内置 10 余种工具，支持多个 LLM 后端，同时提供美观的终端 UI 和简洁的库 API。

### ✨ 特性

| 特性 | 说明 |
|------|------|
| **Agentic 循环** | 自主规划、工具执行、结果回注 |
| **10+ 内置工具** | 文件读写编辑、Bash、Git、网络搜索/抓取、项目分析 |
| **多 Provider** | 运行时切换 LongCat / OpenAI 兼容 / Anthropic 兼容 后端 |
| **统一 CLI** | 一个 `totoro` 命令搞定 REPL、单轮对话、状态查看 |
| **Rich REPL** | 语法高亮、面板、彩色输出的终端界面 |
| **会话管理** | 持久化会话，支持消息历史和上下文压缩 |
| **安全沙箱** | 命令超时、输出截断、基于 Protocol 的可扩展隔离 |
| **无 SDK 锁定** | LLM 后端全部基于纯 `httpx` 实现 |

### 🚀 快速开始

```bash
# 克隆
git clone https://github.com/leether/totoro-agent.git && cd totoro-agent

# 安装依赖（推荐）
uv sync

# 或使用 pip
pip install -e .

# 配置 API 密钥
echo 'LONGCAT_API_KEY=你的密钥' > .env

# 启动 REPL
totoro
```

### ⌨️ CLI 命令

```bash
totoro                              # 启动交互式 REPL（默认）
totoro repl                         # 显式启动 REPL
totoro status                       # 显示当前配置
totoro chat "写一个 hello world"     # 单轮对话
totoro chat "解释这个仓库" --stream  # 流式单轮对话
```

### ⚙️ 配置

在项目根目录创建 `.env`：

```bash
# 默认 provider：totoro（LongCat）
LONGCAT_API_KEY=你的_longcat_密钥

# 可选：切换 provider
AGENT_PROVIDER=totoro        # 或 openai / anthropic

# 可选的其它 provider 密钥
OPENAI_API_KEY=你的_openai_密钥
ANTHROPIC_API_KEY=你的_anthropic_密钥
```

### 📁 项目结构

```
totoro-agent/
├── agent/          # 核心引擎：agentic 循环、上下文、会话
├── providers/      # LLM 后端：LongCat / OpenAI 兼容 / Anthropic 兼容
├── tools/          # 内置工具：文件、Shell、Git、网络、项目分析
├── sandbox/        # 安全沙箱与隔离抽象
├── cli/            # Rich 终端交互界面与统一 CLI 入口
├── api/            # HTTP API 层（FastAPI，开发中）
├── evals/          # 评测测试套件
├── tests/          # 单元测试套件
└── .github/        # CI、Issue/PR 模板、Dependabot 配置
```

### 🔧 作为库使用

```python
from providers.totoro_provider import TotoroProvider
from agent.engine import AgentEngine

provider = TotoroProvider(api_key="你的密钥")
engine = AgentEngine.create(provider=provider, tool_preset="full")

# 非流式
response = await engine.run("写一个 hello world 函数")
print(response.message)

# 流式
async for event in engine.run_stream("分析这个代码库"):
    if event["type"] == "text_delta":
        print(event["content"], end="")
```

### 🛠️ 开发

```bash
# 安装开发依赖和 pre-commit hooks
uv sync
pre-commit install

# 运行完整本地 CI 流水线
make all          # lint + format-check + typecheck + test
```

详细贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

### 📖 架构设计

完整的设计文档（数据流、API 设计、安全策略、开发路线图）见 [docs/architecture.md](docs/architecture.md)。

### 🛠️ 开发路线

- [x] Phase 1: 核心引擎 + 文件工具 + Rich REPL + 统一 CLI
- [ ] Phase 2: Lint/Test 工具 + Git 工作流工具
- [ ] Phase 3: FastAPI HTTP API + SSE 流式
- [ ] Phase 4: Planner + 跨会话记忆 + 代码审查模式

---

<div align="center">

**[MIT License](LICENSE)** · Built with ❤️ by [leether](https://github.com/leether)

</div>
