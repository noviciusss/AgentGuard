# AgentGuard

AgentGuard is a static analysis CLI for AI agent codebases. It is designed to
find reliability, cost, and security bugs in agent graphs, tool calls, retries,
and LLM calls before an agent runs.

The project is currently in the Phase 0 bootstrap stage.

## Development setup

AgentGuard uses `uv` for environments and dependencies. WSL users should keep
the virtual environment outside a Windows-mounted project directory and use
copy mode for dependency links:

```bash
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/agentguard"
uv sync --all-extras
```

Run the complete local check suite with:

```bash
make check
```

The initial CLI supports a version check:

```bash
uv run agentguard --version
```

Scanning commands and the analysis engine will be added in later phases.

## License

AgentGuard is released under the MIT license. See [LICENSE](LICENSE).
