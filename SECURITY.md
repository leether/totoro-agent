# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do not** open a public issue on GitHub.
2. Contact the maintainer directly via the contact information in the README.

We will acknowledge your report within 7 days and work on a fix promptly.

## Security Best Practices

- Never commit API keys or secrets to the repository. Use `.env` files (which are in `.gitignore`).
- Keep dependencies up to date (`uv sync` regularly).
- Review tool execution outputs when running shell commands through the agent.
