# Contributing to Totoro Agent

感谢你对 Totoro Agent 的兴趣！以下是参与贡献的指南。

## 开发环境搭建

```bash
# 克隆仓库
git clone https://github.com/leether/totoro-agent.git
cd totoro-agent

# 安装所有开发依赖
uv sync

# 安装 pre-commit hooks
pre-commit install
```

## 开发工作流

### 1. 创建分支

```bash
git checkout -b feat/your-feature-name
# 或
git checkout -b fix/your-bug-fix
```

### 2. 编写代码

遵循项目现有的代码风格：

- **类型标注**：所有公开函数/方法必须有类型标注（`disallow_untyped_defs = true`）
- **文档字符串**：公开 API 使用 Google 风格 docstring
- **导入排序**：由 ruff (isort) 自动管理
- **行宽**：100 字符（ruff format 自动处理）

### 3. 本地检查

每次提交前确保通过以下检查：

```bash
# 运行所有检查（lint + format + typecheck + test）
make all

# 或单独运行
make lint        # ruff check
make format-check # ruff format --check
make typecheck   # mypy
make test        # pytest
```

### 4. 提交

Pre-commit hooks 会在提交时自动运行：
- `ruff check` — 代码质量检查
- `ruff format` — 代码格式化
- `mypy` — 类型检查
- `codespell` — 拼写检查
- `trailing-whitespace` / `end-of-file-fixer` — 文件清理

### 5. 推送 & PR

```bash
git push origin feat/your-feature-name
```

然后在 GitHub 上创建 Pull Request，CI 会自动运行完整检查。

## 测试

```bash
# 运行全部测试
make test

# 快速测试（跳过慢速/集成测试）
make test-fast

# 带覆盖率报告
make test-cov
```

新增功能时，请同时添加对应的单元测试。测试文件放在 `tests/` 目录下，命名遵循 `test_*.py` 规范。

## 项目结构

```
totoro-agent/
├── agent/          # 核心引擎（agentic loop, context, session）
├── providers/      # LLM 后端（Totoro, OpenAI, Anthropic）
├── tools/          # 内置工具（file, bash, git, web, project）
├── sandbox/        # 安全沙箱与隔离抽象
├── cli/            # Rich REPL 终端界面
├── api/            # HTTP API 层（FastAPI）
├── config.py       # 配置定义
├── docs/           # 架构文档
└── tests/          # 单元测试
```

## 代码规范

### 类型标注

```python
# ✅ 正确：完整类型标注
def execute(self, **kwargs: Any) -> ToolResult:
    ...

# ❌ 错误：缺少类型标注
def execute(self, **kwargs):
    ...
```

### 错误处理

```python
# ✅ 正确：具体异常 + 清晰消息
if not path.exists():
    raise FileNotFoundError(f"File not found: {path}")

# ❌ 错误：裸异常
raise Exception("error")
```

### 工具注册

新工具通过 `@register_tool` 装饰器注册：

```python
@register_tool(presets=["core", "full"])
class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Description of what this tool does"

    def execute(self, **kwargs: Any) -> ToolResult:
        ...
```

## Commit Message 规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
feat: add new web search tool
fix: resolve bash tool output truncation
docs: update architecture diagram
test: add tests for git tools
refactor: simplify provider registry
style: apply ruff format
```

## License

本项目采用 MIT License。提交贡献即表示你同意在 MIT License 下发布你的代码。
