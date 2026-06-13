# About Totoro Coding Agent

Totoro Coding Agent is a general-purpose, tool-using coding assistant built from scratch in Python. It combines an agentic reasoning loop with a registry of file, shell, Git, web, and project-analysis tools, and supports multiple LLM backends through a clean provider abstraction.

## What it does

- Reads, writes, and edits files in your project
- Runs shell commands with configurable timeouts and safety guards
- Searches code, fetches web pages, and inspects Git state
- Streams results to a Rich-powered terminal REPL
- Persists sessions and compresses context to stay within token limits

## Why it exists

Most coding agents are wrappers around existing frameworks or closed products. Totoro is intentionally small, explicit, and hackable: every component — the loop, tools, providers, sandbox, and context manager — is plain Python you can read and modify.

## Backends

- Totoro (LongCat API-compatible)
- OpenAI-compatible APIs
- Anthropic-compatible APIs

## Status

Phase 1 is complete and usable. Phase 2 adds lint/test/Git workflow tools, Phase 3 adds the HTTP API, and Phase 4 adds planning and memory.

## Links

- README: [README.md](README.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- Repository: https://github.com/leether/totoro-agent

## License

MIT License — see [LICENSE](LICENSE) for details.
