# AgentGuard

AgentGuard is a static analysis CLI for AI agent codebases. It finds reliability,
cost, and security bugs in agent graphs, tool calls, retries, and LLM calls
before an agent runs.

The project currently ships the Phase 1 core engine, normalized Agent IR,
generic, LangGraph, CrewAI, and AutoGen adapters, the Phase 2 plugin system,
and 15 documented reliability, cost, and security rules.

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

Install the locked environment and run the complete local check suite with:

```bash
uv sync --locked --all-extras
make check
```

`make install` also installs the locked dependencies, using the same
environment as the check targets. The Makefile exports both WSL settings;
export them in your shell as above when running `uv` directly. All check
targets include the development dependencies automatically.

Keep `uv.lock` in version control. For intentional dependency updates, run
`uv lock --upgrade`, review the lockfile changes, and run `make check`.

## Quick start

Check the installed version:

```bash
uv run --locked agentguard --version
uv run --locked python -m agentguard --version
```

Scan the bundled examples without failing the shell command on findings:

```bash
uv run --locked agentguard scan examples/ --fail-on never
```

The support bot and plain Python agent intentionally contain findings. The
clean agent should produce no findings:

```bash
uv run --locked agentguard scan examples/clean_agent --format json --fail-on never
```

List the built-in rules or read a rule's remediation guidance:

```bash
uv run --locked agentguard rules
uv run --locked agentguard explain AG003
uv run --locked agentguard plugins list
uv run --locked agentguard baseline create examples/ --output baseline.json
```

Useful scan options include:

```text
agentguard scan [PATHS...] --format text|json
    --select AG001,AG00* --ignore AG003
    --min-severity info|warning|error
    --min-confidence low|medium|high
    --fail-on error|warning|never
    --jobs N --output FILE --no-cache
```

The scanner parses source without importing or executing it. A syntax error is
reported as a warning and the remaining files continue to scan. Findings are
deterministically sorted and can be suppressed inline:

```python
requests.get(url)  # agentguard: ignore[AG003] reason: gateway adds timeout
```

See [the architecture guide](docs/architecture.md) and the individual pages in
[`docs/rules/`](docs/rules/) for the IR pipeline and rule-specific guidance.
See [the CI guide](docs/ci.md) for GitHub and pre-commit integration, and
[the autofix guide](docs/autofix.md) for safe dry-run and apply behavior.

## License

AgentGuard is released under the MIT license. See [LICENSE](LICENSE).
