# AgentGuard status

## Current position

- Phase: 2 — Plugin system
- Step: 2.5 — package boundaries and external plugin acceptance
- Status: Phase 2 complete; Phase 3 remains in progress

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

## Completed in Step 1.4

- Framework adapter interface and generic Python adapter
- Known call table for requests, urllib, httpx, aiohttp, OpenAI, Anthropic, and
  LangChain chat models
- Import-alias and simple client assignment resolution
- Literal keyword extraction and timeout-state inference, including client-level
  timeout propagation
- IR extraction for calls, bounded/unbounded loops, retry decorators, module
  mutables, generic function nodes, mutable defaults, and concurrency fan-outs
- Adapter tests covering aliases, client timeouts, retry bounds, loops, and
  shared mutable concurrency shapes

## Completed in Step 1.5

- LangGraph adapter based on the verified StateGraph API shape
- StateGraph construction and compiled graph detection
- Static and conditional edges, START/END entry and terminal handling
- Named and function-derived nodes with node state read/write facts
- Send-based and static-edge fan-out extraction
- TypedDict-style state schemas with `Annotated` reducer and mutable-type facts
- Adapter ordering and generic fallback through `IRBuilder`

## Completed in Step 1.6

- AG003 rule for HTTP, LLM, and tool calls with unresolved timeout state
- Severity escalation for calls inside loops and LLM-adjacent HTTP calls
- Medium confidence for LangChain timeout findings and low confidence for
  aiohttp's long-default behavior
- 5 bad, 5 good, and 3 edge fixtures covering aliases, client-level timeouts,
  dynamic kwargs, HTTP defaults, and LLM constructors

## Completed in Step 1.7

- AG001 detection for unbounded while loops, retry decorators, retry calls,
  retry recursion, and excessive `max_retries`
- Severity and confidence based on operation kind and bound certainty
- Bounded-loop and deadline exclusions
- 5 bad, 5 good, and 3 edge fixtures for tenacity, backoff, recursion,
  counters, deadlines, event loops, and retry limits

## Completed in Step 1.8

- AG002 detection for unreduced LangGraph state writes across static and Send
  fan-outs
- Generic thread-pool and asyncio fan-out mutation detection
- Mutable default argument detection for parallel tasks
- Lock-protected mutation and reducer-backed state exclusions
- 5 bad, 5 good, and 3 edge fixtures for graph branches, Send, locks, reads,
  local state, dynamic fan-outs, and custom reducers

## Completed in Step 1.9 configuration sub-unit

- Pydantic configuration model with validated severity, confidence, failure,
  exclusion, rule-selection, and worker settings
- `agentguard.toml` and `pyproject.toml` discovery with nearest-file and
  `agentguard.toml` precedence
- Explicit CLI override merging with validation and clear configuration errors
- Tests for defaults, precedence, malformed TOML, extra keys, and invalid jobs

## Completed in Step 1.9 CLI and reporter integration

- `scan`, `rules`, and `explain` command registration
- Text and deterministic JSON reporters with snapshot coverage
- Rule selection, ignore patterns, severity/confidence filters, output files,
  failure thresholds, and non-fatal parse diagnostics
- Multi-worker project parsing through `--jobs` while preserving whole-project
  IR analysis and deterministic result ordering
- CLI tests for filtering, exit codes, parse warnings, and sequential versus
  parallel results

## Completed in Step 1.10

- Rule documentation for AG001, AG002, and AG003 with examples, fixes, and
  suppression guidance
- Architecture documentation for discovery, parsing, adapters, IR, rules,
  reporters, and the Phase 2 extension boundary
- README installation, WSL setup, scan usage, suppression, and example output
- Bundled LangGraph, plain-Python, and clean agent examples
- CLI and scan smoke tests for rule documentation and bundled examples

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

## Verified in Step 1.4

- `make check` on Python 3.13.5: 34 tests passed, no warnings
- Ruff lint and format checks passed for all 29 Python files
- `mypy --strict`: no issues in 29 source files

## Verified in Step 1.5

- `make check` on Python 3.13.5: 36 tests passed, no warnings
- Ruff lint and format checks passed for all 32 Python files
- `mypy --strict`: no issues in 32 source files

## Verified in Step 1.6

- `make check` on Python 3.13.5: 50 tests passed, no warnings
- Ruff lint and format checks passed for all 47 Python files
- `mypy --strict`: no issues in 34 checked source files

## Verified in Step 1.7

- `make check` on Python 3.13.5: 63 tests passed, no warnings
- Ruff lint and format checks passed for all 62 Python files
- `mypy --strict`: no issues in 36 source files

## Verified in Step 1.8

- `make check` on Python 3.13.5: 77 tests passed, no warnings
- Ruff lint and format checks passed for all 78 Python files
- `mypy --strict`: no issues in 38 source files

## Verified in Step 1.9 configuration sub-unit

- `make check` on Python 3.13.5: 88 tests passed, no warnings
- Ruff lint and format checks passed for all 89 Python files
- `mypy --strict`: no issues in 49 source files

## Verified in Step 1.9 CLI and reporter integration

- `make check` on Python 3.13.5: 92 tests passed, no warnings
- Ruff lint and format checks passed for all 89 Python files
- `mypy --strict`: no issues in 49 source files

## Verified in Step 1.10

- `make check` on Python 3.13.5: 96 tests passed, no warnings
- Ruff lint and format checks passed for all 92 Python files
- `mypy --strict`: no issues in 49 source files
- `agentguard scan examples/ --format json --fail-on never` reports AG001,
  AG002, and AG003 from the deliberately unsafe examples
- `agentguard scan examples/clean_agent --format json --fail-on never` returns
  an empty finding list

## Phase 1 acceptance corpus

Scanned shallow clones of three public Python LangGraph repositories with
`agentguard scan ... --format json --fail-on never`. All scans completed without
crashing:

- `langchain-ai/langgraph`: 13 findings, all AG003 timeout findings
- `langchain-ai/langgraph-supervisor-py`: 0 findings
- `langchain-ai/langgraph-swarm-py`: 1 AG003 timeout finding

The manual spot check found the reported LangChain model constructors without
configured timeouts in the first and third repositories; these are expected
Phase 1 findings rather than parser or adapter crashes.

## Completed in Phase 2, Step 2.1

- Added the typed `pluggy` hook contract for rules, adapters, reporters,
  commands, and finding modifiers
- Added deterministic plugin registration and contribution collection
- Added plugin metadata, duplicate-name validation, and ordered finding
  modifier execution
- Added unit coverage for plugin registration, ordering, duplicate names, and
  finding modifiers

## Verified in Phase 2, Step 2.1

- `make check` on Python 3.13.5: 100 tests passed, no warnings
- Ruff lint and format checks passed for all 96 Python files
- `mypy --strict`: no issues in 53 source files

## Completed in Phase 2, Step 2.2

- Added `agentguard` entry-point discovery with deterministic ordering
- Added non-fatal plugin load diagnostics for malformed external plugins
- Routed built-in rules, adapters, and reporters through the plugin manager
- Added adapter priorities so framework-specific adapters run before the
  generic fallback
- Applied plugin finding modifiers in stable plugin-name order
- Updated rule listing, explanation, and scan orchestration to use plugin
  contributions
- Added entry-point and built-in registration tests

## Verified in Phase 2, Step 2.2

- `make check` on Python 3.13.5: 102 tests passed, no warnings
- Ruff lint and format checks passed for all 97 Python files
- `mypy --strict`: no issues in 54 source files

## Completed in Phase 2, Step 2.3

- Added `agentguard plugins list` and `plugins info`
- Added `agentguard plugins new NAME` package scaffolding with entry-point
  metadata, an example rule, and tests
- Added `agentguard plugins doctor` for configuration and plugin-load health
- Added CLI coverage for built-in inspection, invalid names, existing targets,
  generated files, and healthy diagnostics

## Verified in Phase 2, Step 2.3

- `make check` on Python 3.13.5: 107 tests passed, no warnings
- Ruff lint and format checks passed for all 99 Python files
- `mypy --strict`: no issues in 56 source files

## Completed in Phase 2, Step 2.4

- Added stable JSON baselines based on finding fingerprints
- Added `agentguard baseline create`
- Added `agentguard scan --baseline FILE`
- Added baseline validation and new-versus-existing finding filtering
- Added tests for deterministic baseline serialization, invalid files, and CLI
  baseline workflows

## Verified in Phase 2, Step 2.4

- `make check` on Python 3.13.5: 111 tests passed, no warnings
- Ruff lint and format checks passed for all 102 Python files
- `mypy --strict`: no issues in 59 source files

## Completed in Phase 2, Step 2.5

- Added `packages/agentguard-core` and `packages/agentguard-langgraph`
  distribution boundaries
- Added LangGraph entry-point package metadata and plugin wrapper
- Added an external-plugin acceptance test using a separately discovered
  entry-point contribution
- Verified both distribution boundaries build source and wheel artifacts
  outside the repository

## Phase 2 acceptance

- `make check` on Python 3.13.5: 112 tests passed, no warnings
- Ruff lint and format checks passed for all 105 Python files
- `mypy --strict`: no issues in 60 source files
- `agentguard plugins list`, `info`, `new`, and `doctor` are covered
- Baseline creation and filtering are covered
- A separately discovered external plugin contributes rule `AG998`
- `agentguard-core` and `agentguard-langgraph` both build successfully

## Next

The next unit is Phase 3, Step 3.1: extend the Agent IR for graph reachability,
cost metadata, tool safety, and intra-function dataflow facts.

## Known issues

- `uv` is installed at `$HOME/.local/bin/uv`; shells must include that path or
  start a new terminal before invoking it directly.
- A parallel direct `uv run` verification briefly created an ignored project
  `.venv`; the documented Makefile environment remains the supported path.
- Checks have run locally on Python 3.13.5; the GitHub CI matrix has not run
  for these local commits yet.
- Discovery reads `.gitignore` files within the scan root. User-global Git
  excludes and `.git/info/exclude` are not read.
- Generic adapter call defaults are conservative and intentionally avoid
  treating unresolved arbitrary `.invoke()` methods as LLM calls.
- Corpus verification used shallow clones in `/tmp/omnirush/langgraph-corpus`;
  those external temporary files are not part of the repository.
