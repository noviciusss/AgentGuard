# AgentGuard status

## Current position

- Phase: 1 — Core engine, IR, three rules
- Step: 1.3 — Rule base, registry, and fixture runner
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

## Completed in Step 1.2

- Sorted and deduplicated Python-file discovery with explicit excludes and
  nested `.gitignore` files; ignored directories are pruned
- AST parsing with source preservation, Python encoding-cookie support, and
  structured parse diagnostics without executing source
- Token-based inline and first-ten-line file suppressions; directive-looking
  strings and malformed directives do not suppress findings
- Sequential and process-pool scan orchestration with an injected analysis
  callback, deterministic findings, and non-fatal parse diagnostics
- Edge-case tests for ignore precedence, path errors, encodings, suppressions,
  and equivalent sequential/parallel results

## Completed in Step 1.3

- Typed `Rule` and `RuleContext` contracts that consume normalized Agent IR
- Rule descriptors with stable IDs, names, descriptions, and default severity
- Duplicate/invalid rule registration checks
- Deterministic rule selection with `AG00*`-style include and ignore patterns
- Registry execution with finding validation, fingerprint finalization, and
  global source-order sorting
- Exact-line fixture marker parser and assertion helper for `# expect: AGxxx`
  comments, ready for the first real rule fixtures

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

## Verified in Step 1.2

- `make check` on Python 3.13.5: 24 tests passed, no warnings
- Ruff lint and format checks passed for all 17 Python files
- `mypy --strict`: no issues in 17 source files

## Verified in Step 1.3

- `make check` on Python 3.13.5: 31 tests passed, no warnings
- Ruff lint and format checks passed for all 24 Python files
- `mypy --strict`: no issues in 24 source files
- `feature/phase-1-models` pushed to `origin`

## Next

The next unit is Phase 1, Step 1.4: generic adapter and known-call tables for
plain Python loops, retries, LLM calls, HTTP calls, and name resolution.
Framework analysis and `agentguard scan` are not implemented yet. CLI
rendering of parse diagnostics belongs to Step 1.9.

## Known issues

- `uv` is installed at `$HOME/.local/bin/uv`; shells must include that path or
  start a new terminal before invoking it directly.
- A parallel direct `uv run` verification briefly created an ignored project
  `.venv`; the documented Makefile environment remains the supported path.
- Checks have run locally on Python 3.13.5; the GitHub CI matrix has not run
  for these local commits yet.
- Discovery reads `.gitignore` files within the scan root. User-global Git
  excludes and `.git/info/exclude` are not read.
