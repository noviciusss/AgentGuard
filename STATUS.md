# AgentGuard status

## Current position

- Phase: 1 — Core engine, IR, three rules
- Step: 1.1 — Findings and Agent IR models
- Status: Complete; all checks pass

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

## Completed in Step 1.1

- Severity, confidence, location, finding, and future-fix models
- Stable finding ordering by file, line, column, and rule identifier
- Line-number-independent SHA-256 finding fingerprints
- Normalized Agent IR enums and dataclasses for calls, loops, graphs, state,
  tools, fan-outs, module facts, and whole systems
- Unit tests for finding defaults, ordering, fingerprints, and IR relationships

## Verified in Step 0.2

- `uv sync --locked --all-extras`
- `make install`
- `make check`
- `uv run --locked agentguard --version`
- `uv run --locked python -m agentguard --version`

## Verified in Step 1.1

- `make check`
- 6 tests passed
- `ruff check` and format verification passed
- `mypy --strict` passed for 11 source files

## Next

The next unit is Phase 1, Step 1.2: discovery, parsing, scan orchestration, and
inline suppression comments.

## Known issues

- `uv` is installed at `$HOME/.local/bin/uv`; shells must include that path or
  start a new terminal before invoking it directly.
- A parallel direct `uv run` verification briefly created an ignored project
  `.venv`; the documented Makefile environment remains the supported path.
