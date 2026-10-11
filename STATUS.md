# AgentGuard status

## Current position

- Phase: 0 — Bootstrap
- Step: 0.1 — Scaffold
- Status: Scaffold implemented; dependency lock and checks are blocked by missing local tools

## Completed in Step 0.1

- Project metadata and Hatchling `src/` layout
- WSL-safe Makefile targets
- Ruff, mypy, and pytest configuration
- Minimal version-capable CLI package
- Bootstrap smoke test
- MIT license, README, ignore rules, and LF line-ending policy
- GitHub Actions workflow for Python 3.10, 3.11, and 3.12

## Still required for Step 0.1 completion

- Install `uv` and `make` locally
- Generate and commit `uv.lock`
- Run `uv sync --all-extras`
- Run `make check` and fix any findings

## Next

After Step 0.1 is green and committed, proceed to Step 0.2 verification and
then stop for approval before starting Phase 1.

## Known issues

- `uv.lock` has not been generated because `uv` is not installed locally.
- `make check` has not run because `make` and the project development tools are
  not installed locally.
- Work is on `feature/phase-0-bootstrap`; no commit has been created because
  the unit is not green yet.
