# AgentGuard status

## Current position

- Phase: 0 — Bootstrap
- Step: 0.2 — Verification
- Status: Complete; locked install and all checks pass

## Completed in Step 0.1

- Project metadata and Hatchling `src/` layout
- WSL-safe Makefile targets
- Ruff, mypy, and pytest configuration
- Minimal version-capable CLI package
- Bootstrap smoke test
- MIT license, README, ignore rules, and LF line-ending policy
- GitHub Actions workflow for Python 3.10, 3.11, and 3.12
- Committed `uv.lock` with locked development tooling
- Python 3.13 added to the CI matrix
- Bootstrap specification clarified for lockfiles, line endings, and verification

## Verified in Step 0.2

- `uv sync --locked --all-extras`
- `make install`
- `make check`
- `uv run --locked agentguard --version`
- `uv run --locked python -m agentguard --version`

## Next

Phase 0 is complete. The next approved unit is Phase 1, Step 1.1: findings and
Agent IR models with unit tests for dataclasses and fingerprints.

## Known issues

- `uv` is installed at `$HOME/.local/bin/uv`; shells must include that path or
  start a new terminal before invoking it directly.
- A parallel direct `uv run` verification briefly created an ignored project
  `.venv`; the documented Makefile environment remains the supported path.
