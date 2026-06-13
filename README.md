# 🐾 Totoro Coding Agent

<div align="center">

**AI-powered coding assistant with tool use, Rich REPL, and multi-provider support.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[English](#english) | [中文](#中文)

</div>

---

## English

A **general-purpose Coding Agent** built from scratch — not a wrapper around an existing framework. It features a full agentic loop with 10+ built-in tools, multi-provider LLM support (Totoro / OpenAI / Anthropic), a Rich-powered terminal UI, and a cleanly architected codebase ready for extension.

### ✨ Features

| Feature | Description |
|---------|-------------|
| **Agentic Loop** | Autonomous reasoning → tool calling → result injection → iterate until done |
| **10+ Built-in Tools** | File read/write/edit, Bash execution, Git, Web search/fetch, project analysis |
| **Multi-Provider** | Switch between LongCat, OpenAI (GPT-4o), and Anthropic (Claude) at runtime |
| **Rich REPL** | Beautiful terminal UI with syntax highlighting, panels, and colored output |
| **Session Management** | Persistent sessions with message history and context compression |
| **Safety Sandbox** | Command timeout, output truncation, and Protocol-based extensible isolation |
| **Zero SDK Dependencies** | Pure `httpx`-based HTTP clients — no pydantic_core or vendor SDK lock-in |

### 🚀 Quick Start

```bash
# Clone
git clone https://github.com/leether/totoro-agent.git && cd totoro-agent

# Install dependencies
pip install -e ".[repl]"

# Configure API Key
echo 'TOTORO_API_KEY=your_key_here' > .env

# Launch REPL
python -m cli.repl .
```

### 📁 Project Structure

```
totoro-agent/
├── agent/          # Core Agent engine (agentic loop, context, sessions)
├── providers/      # LLM backends (Totoro / OpenAI / Anthropic)
├── tools/          # Built-in tools (file, bash, git, web, project)
├── sandbox/        # Safety sandbox (Protocol-based isolation)
├── cli/            # Rich REPL terminal interface
├── api/            # HTTP API layer (FastAPI, planned)
└── evals/          # Evaluation test suite
```

### 🔧 Usage as Library

```python
from providers.totoro_provider import TotoroProvider
from agent.engine import AgentEngine, AgentConfig

provider = TotoroProvider(api_key="your_key")
engine = AgentEngine.create(provider=provider, tool_preset="full")

# Non-streaming
response = await engine.run("Write a hello world function")
print(response.message)

# Streaming
async for event in engine.run_stream("Analyze this codebase"):
    if event["type"] == "text_delta":
        print(event["text"], end="")
```

### 📖 Architecture

See [docs/architecture.md](docs/architecture.md) for full design document including data flow, API design, security strategy, and implementation roadmap.

### 🛠️ Roadmap

- [x] Phase 1: Core engine + file tools + Rich REPL
- [ ] Phase 2: Lint/Test tools + Git workflow tools
- [ ] Phase 3: FastAPI HTTP API + SSE streaming
- [ ] Phase 4: Planner + multi-session memory + code review mode

---

## 中文

一个**从零构建的通用 Coding Agent** —— 不是现有框架的包装。具备完整 agentic 循环、10+ 内置工具、多 Provider 大模型支持（Totoro / OpenAI / Anthropic）、Rich 美化终端 UI，以及易于扩展的整洁架构。

### ✨ 特性

| 特性 | 说明 |
|------|------|
| **Agentic 循环** | 自主推理 → 工具调用 → 结果回注 → 循环直到完成 |
| **10+ 内置工具** | 文件读写、Bash 执行、Git、网络搜索/抓取、项目分析 |
| **多 Provider** | 运行时在 LongCat、OpenAI (GPT-4o)、Anthropic (Claude) 之间切换 |
| **Rich REPL** | 语法高亮、Panel 面板、彩色输出的美观终端界面 |
| **会话管理** | 持久化会话，支持消息历史和上下文压缩 |
| **安全沙箱** | 命令超时、输出截断、Protocol 可扩展隔离层 |
| **零 SDK 依赖** | 纯 `httpx` HTTP 实现 —— 无 pydantic_core，无厂商 SDK 锁定 |

### 🚀 快速开始

```bash
# 克隆
git clone https://github.com/leether/totoro-agent.git && cd totoro-agent

# 安装依赖
pip install -e ".[repl]"

# 配置 API Key
echo 'TOTORO_API_KEY=你的密钥' > .env

# 启动 REPL
python -m cli.repl .
```

### 📁 项目结构

```
totoro-agent/
├── agent/          # 核心 Agent 引擎（agentic 循环、上下文、会话）
├── providers/      # LLM 后端（Totoro / OpenAI / Anthropic）
├── tools/          # 内置工具（文件、Shell、Git、网络、项目分析）
├── sandbox/        # 安全沙箱（Protocol 隔离层）
├── cli/            # Rich 美化终端交互界面
├── api/            # HTTP API 层（FastAPI，开发中）
└── evals/          # 评测测试套件
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
        print(event["text"], end="")
```

### 📖 架构设计

完整的设计文档（数据流、API 设计、安全策略、实施路线图）见 [docs/architecture.md](docs/architecture.md)。

### 🛠️ 开发路线

- [x] Phase 1: 核心引擎 + 文件工具 + Rich REPL
- [ ] Phase 2: Lint/Test 工具 + Git 工作流工具
- [ ] Phase 3: FastAPI HTTP API + SSE 流式
- [ ] Phase 4: Planner + 跨会话记忆 + 代码审查模式

---

<div align="center">

**[MIT License](LICENSE)** · Built with ❤️ by [leether](https://github.com/leether)

</div>
