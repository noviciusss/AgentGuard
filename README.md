# AgentGuard

AgentGuard is a static analysis CLI for AI agent codebases. It is designed to
find reliability, cost, and security bugs in agent graphs, tool calls, retries,
and LLM calls before an agent runs.

The project is currently in the Phase 0 bootstrap stage.

## Development setup

AgentGuard requires Python 3.10+ and uses `uv` for environments and
dependencies. CI targets Python 3.10, 3.11, 3.12, and 3.13. The bootstrap uses
`uv` 0.13.0 and GNU Make.

If you just installed `uv` and the shell cannot find it, open a new terminal
or add its default install directory to your current shell's path:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

WSL users should keep the virtual environment outside a Windows-mounted
project directory and use copy mode for dependency links:

```bash
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/agentguard"
uv sync --locked --all-extras
```

Run the complete local check suite with:

```bash
make check
```

`make install` also installs the locked dependencies, using the same
environment as the check targets. The Makefile exports both WSL settings;
export them in your shell as above when running `uv` directly. All check
targets include the development dependencies automatically.

Keep `uv.lock` in version control. For intentional dependency updates, run
`uv lock --upgrade`, review the lockfile changes, and run `make check`.

The initial CLI supports a version check:

```bash
uv run --locked agentguard --version
uv run --locked python -m agentguard --version
```

Scanning commands and the analysis engine will be added in later phases.

## License

AgentGuard is released under the MIT license. See [LICENSE](LICENSE).
