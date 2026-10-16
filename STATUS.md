# AgentGuard status

## Current position

- Phase: 6 — Platform
- Step: 6.7 — release and final validation
- Status: Phase 6 implementation slice complete; release evidence reconciliation
  is complete locally and external CI/production review remain before publication

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

## Completed in Phase 3

- Extended the Agent IR with graph cycles, unreachable nodes, iteration limits,
  model/token metadata, approval gates, exception facts, state-growth facts,
  taint flows, and secret facts
- Added conservative CrewAI and AutoGen adapters with `max_iter` and
  `max_round` normalization
- Added intra-function taint tracking for user input, tool output, LLM output,
  environment values, execution sinks, prompt sinks, and likely credentials
- Added AG004–AG011 and AG020–AG023 with documentation and fixture coverage
- Added 36 Phase 3 fixture tests covering bad, good, and edge cases
- Added Phase 3 integration tests for graph, cost, taint, tool, and secret paths
- Updated README for the expanded adapters, plugin system, and rule catalog

## Verified in Phase 3 implementation

- `make check` on Python 3.13.5: 277 tests passed, no warnings
- Ruff lint and format checks passed for all 280 Python files
- `mypy --strict`: no issues in 81 source files
- `agentguard rules` lists all 15 Phase 1–3 rules
- `agentguard plugins list` discovers built-ins and the LangGraph plugin
- Core and LangGraph package wheels build successfully
- A separately built and installed external scaffold plugin appears in
  `agentguard rules` as AG900 and in `agentguard plugins info`

## Completed in Phase 4, Step 4.1

- Added deterministic SARIF 2.1.0 reporting with rule metadata, locations,
  severity, confidence, suggestions, related locations, and fingerprints
- Registered SARIF through the plugin reporter boundary
- Added `agentguard scan --format sarif`
- Added SARIF snapshot coverage, empty-fingerprint behavior, and CLI coverage

## Verified in Phase 4, Step 4.1

- `make check` on Python 3.13.5: 280 tests passed, no warnings
- Ruff lint and format checks passed for all 281 Python files
- `mypy --strict`: no issues in 82 source files

## Completed in Phase 4, Step 4.2

- Added the reusable composite GitHub Action at
  `.github/actions/agentguard/action.yml`
- Added configurable scan path, SARIF output, rule selection, ignore patterns,
  failure threshold, and Python version inputs
- Added CI documentation with SARIF upload permissions and workflow example
- Added validation tests for the action metadata and CI documentation

## Verified in Phase 4, Step 4.2

- `make check` on Python 3.13.5: 282 tests passed, no warnings
- Ruff lint and format checks passed for all 281 Python files
- `mypy --strict`: no issues in 82 source files

## Completed in Phase 4, Step 4.3

- Added `.pre-commit-hooks.yaml` with a Python-file AgentGuard hook
- Added staged-file usage and rule-argument documentation to `docs/ci.md`
- Added validation tests for hook metadata and documentation examples

## Verified in Phase 4, Step 4.3

- `make check` on Python 3.13.5: 284 tests passed, no warnings
- Ruff lint and format checks passed for all 282 Python files
- `mypy --strict`: no issues in 83 source files

## Completed in Phase 4, Step 4.4

- Added the approved `libcst` dependency to the core and compatibility package
  metadata and lockfile
- Added a typed `FixEngine` with formatting-preserving LibCST transforms
- Added deterministic unified diff generation
- Added explicit apply behavior while keeping preview mode side-effect free
- Added parse-error, transformation-error, no-op, formatting-preservation, and
  explicit-write tests

## Verified in Phase 4, Step 4.4

- `make check` on Python 3.13.5: 288 tests passed, no warnings
- Ruff lint and format checks passed for all 282 Python files
- `mypy --strict`: no issues in 83 source files

## Completed in Phase 4, Step 4.5

- Added AG003 LibCST timeout autofix for supported known-call findings
- Added `--fix-dry-run`, `--fix`, and `--fix-timeout` scan options
- Kept dry-run preview side-effect free and limited writes to explicit `--fix`
- Added CLI and direct-transform tests for requests timeout insertion and
  deterministic diff output

## Verified in Phase 4, Step 4.5

- `make check` on Python 3.13.5: 291 tests passed, no warnings
- Ruff lint and format checks passed for all 286 Python files
- `mypy --strict`: no issues in 87 source files

## Completed in Phase 4, Step 4.6

- Added AG004 LibCST recursion-limit autofix for supported LangGraph builders
- Preserved existing compile arguments and skipped already-bounded graphs
- Routed AG004 through the shared dry-run/apply fix pipeline
- Added direct transformer and CLI dry-run coverage

## Verified in Phase 4, Step 4.6

- `make check` on Python 3.13.5: 293 tests passed, no warnings
- Ruff lint and format checks passed for all 287 Python files
- `mypy --strict`: no issues in 88 source files

## Completed in Phase 4, Step 4.7

- Added configurable `[tool.agentguard.fix.model]` mappings
- Added AG010 literal-only model pinning through LibCST
- Skipped dynamic values and aliases without an explicit mapping
- Integrated AG010 with the shared dry-run/apply pipeline
- Added configuration, direct-transform, and dynamic-value tests

## Verified in Phase 4, Step 4.7

- `make check` on Python 3.13.5: 296 tests passed, no warnings
- Ruff lint and format checks passed for all 288 Python files
- `mypy --strict`: no issues in 89 source files

## Completed in the approved Phase 5 taint unit

- Added a deterministic same-file function call graph to generic module facts,
  including recursive local calls.
- Added return-source summaries for direct user input, environment, tool, and
  LLM sources plus local function-call dependencies.
- Resolve summaries to a fixed point so definition order and multi-hop local
  calls propagate taint without executing application code.
- Kept clean literal-return chains untainted and recursive summaries
  terminating conservatively.
- Documented the optional plugin boundary and current interprocedural limits
  in `docs/architecture.md`.

## Verified in the approved Phase 5 taint unit

- Focused taint, plugin, and regression tests pass.
- Argument-sensitive helper sinks, return forwarding, keyword/default binding,
  scope isolation, clean overwrites, recursion, aliases, and unknown-call
  boundaries are covered.

## Completed in Phase 5

- Completed `agentguard graph` Mermaid rendering from normalized IR, including
  deterministic module/graph ordering, isolated nodes, entry and terminal
  markers, static/conditional edges, unresolved targets, fan-outs, escaped
  labels, output files, and CLI diagnostics.
- Completed the offline OWASP/CWE modifier with deterministic tags, metadata,
  catalog version, applicable cost/state mappings, reporter serialization, and
  plugin introspection.
- Completed opt-in provider-neutral LLM triage with bounded redacted snippets,
  source-root containment, validated provider results, request-bound private
  caching, atomic writes, and controlled input/provider error codes.
- Completed local trace ingestion for flat, LangSmith-like, and nested OTLP
  JSON exports with normalized IDs/timestamps/attributes/status/model/cost,
  trace-local repetition findings, explicit cost-spike findings, deterministic
  output, and malformed-input handling.
- Completed same-file argument-sensitive inter-procedural taint propagation
  through direct module-level functions with fixed-point recursion handling.

## Verified in Phase 5

- `uv sync --locked --all-extras`
- `make check` on Python 3.13.5: **356 tests passed**, no warnings
- Ruff lint and format checks passed; 301 files formatted
- `mypy --strict`: no issues found in 102 checked source files
- Focused Phase 5 suite: 51 tests passed
- `agentguard plugins list` discovers all six plugin contributions with stable
  declared names; OWASP modifier appears in `plugins info`.
- `agentguard graph examples/langgraph_support_bot` emits deterministic Mermaid
  with START and END markers.
- Bundled example scan emits OWASP/CWE metadata in JSON output.
- Triage help, trace CLI, graph CLI, output-file handling, malformed-input
  behavior, and plugin discovery are covered by tests and smoke checks.

## Phase 4 acceptance note

Phase 4 is functionally complete: SARIF, GitHub Action, pre-commit metadata,
LibCST dry-run/apply infrastructure, and AG003/AG004/AG010 safe fixes are
implemented and verified. A final package-build record is included above; the
next implementation work begins Phase 5 optional plugins.

## Completed in Phase 4 acceptance

- Added `docs/autofix.md` with safe preview/apply behavior and model mappings
- Linked CI and autofix documentation from the README
- Verified SARIF output, bundled-example dry-run fixes, clean-agent behavior,
  version commands, locked installation, and package builds

## Verified in Phase 4 acceptance

- `uv sync --locked --all-extras`
- `uv run --locked agentguard --version`
- `uv run --locked python -m agentguard --version`
- `agentguard scan examples/ --format sarif --fail-on never`
- `agentguard scan examples/ --fix-dry-run --fail-on never`
- `agentguard scan examples/clean_agent --fix-dry-run --fail-on never`
- Core and LangGraph package wheels build successfully
- `make check` on Python 3.13.5: 297 tests passed, no warnings
- Ruff lint and format checks passed for all 288 Python files
- `mypy --strict`: no issues in 89 source files

## Phase 3 acceptance corpus

- `langchain-ai/langgraph`: 38 findings
- `langchain-ai/langgraph-supervisor-py`: 0 findings
- `langchain-ai/langgraph-swarm-py`: 2 findings
- `crewAIInc/crewAI-examples`: 16 findings
- `microsoft/autogen` `python/samples`: 3 findings
- All five scans completed without crashes; rule distributions and manual
  plausibility checks are recorded in `docs/benchmarks.md`
- 156 Phase 3 fixture cases pass: five bad, five good, and three edge fixtures
  for each AG004–AG011 and AG020–AG023 rule

## Next

Phase 6 is the final phase defined by `SPEC.md`. The implementation slice and
local release evidence are complete. Remaining work is external release
closure: GitHub Actions matrix evidence, production worker/authentication
choices, browser smoke tests if desired, and publishing/deployment setup.
The detailed register is in `docs/ROADMAP_AND_ISSUES.md`.

## Completed in R0 — release/package alignment

- Defined two mutually exclusive installation profiles: the recommended root
  `agentguard` bundle and `agentguard-core` plus selected standalone plugins.
- Changed standalone Phase 5 plugin dependencies from `agentguard` to
  `agentguard-core`.
- Documented package ownership and mixed-install restrictions in
  `docs/distribution.md`.
- Added metadata/profile tests covering root entry points, standalone core
  dependencies, and the distribution contract.

## Verified in R0

- `tests/test_packaging.py`: 3 passed
- Root bundle and all six standalone package distributions built successfully
  as wheels and source distributions in `/tmp/omnirush/phase6-r0-*`.
- `make check` after the metadata changes: **356 tests passed**, no warnings.

## Completed in R1 — performance and corpus gate

- Added `benchmarks/scan_10k.py` for a deterministic exactly-10,000-line
  workload measured through fresh `python -m agentguard scan` subprocesses.
- Added `benchmarks/corpus_gate.py` for deterministic local corpus summaries
  without cloning or network access.
- Added benchmark and corpus helper tests.
- Recorded the measured results in `docs/benchmarks.md`.

## Verified in R1

- 10,000-line benchmark, three samples: 3.443s, 4.090s, and 3.774s;
  median 3.774s against the 5.000s budget.
- Generated benchmark fixture: one file, zero findings, zero parse errors.
- Local `examples/` corpus: 3 Python files, 97 lines, 12 findings, zero parse
  errors, completed without a crash.
- `tests/test_benchmarks.py`: 3 passed.
- Fresh public corpus refresh completed for LangGraph, LangGraph supervisor,
  LangGraph swarm, CrewAI examples, and AutoGen samples; all five completed
  without parse errors or crashes. Counts and manual plausibility checks are in
  `docs/benchmarks.md`.

## Completed in Phase 6 platform slice

- Added standalone `agentguard-server` workspace packaging with FastAPI,
  SQLAlchemy 2, psycopg 3, and Alembic.
- Added PostgreSQL migrations through `0004_audit_records` for repositories,
  branches, commits, scans, findings, baselines, plugin/configuration versions,
  webhook delivery claims, badge visibility, and sanitized audit records.
- Added idempotent JSON and SARIF scan ingestion, deterministic pagination,
  repository-scoped reads, aggregate repository detail, and health/readiness
  endpoints while keeping the core CLI independent of the server.
- Added bearer-token authentication, repository/scope authorization,
  request IDs, payload limits, process-local rate limiting, redacted audit
  sinks, and explicit scan-retention helpers.
- Added signed GitHub pull-request webhook parsing for opened, synchronize, and
  reopened events, durable delivery replay claims, and queued commit-pinned
  scans.
- Added privacy-safe aggregate risk badges with repository opt-in visibility,
  ETags, cache headers, missing/stale/private/unavailable states, and no source
  snippets in public output.
- Added the separate Next.js dashboard with typed API mapping, repository and
  scan detail pages, risk trends, baseline/PR placeholders, and loading,
  forbidden, unavailable, error, and empty states.
- Added Dockerfile, Docker Compose PostgreSQL runtime, `.env.example`, Node
  lockfile checks, and the dashboard CI typecheck job.

## Verified in Phase 6 platform slice

- `make check`: Ruff clean, strict mypy clean across 118 source files, and 361
  root tests passed.
- Server package checks: strict mypy clean across 24 source/test files and 56
  PostgreSQL-backed tests passed with 0 skipped and 0 failed.
- SQLite migration smoke: Alembic upgraded a clean database through
  `0004_audit_records`.
- `npm test`: dashboard TypeScript check passed.
- Next.js production build passed on Next 14.2.35 with Node 20, matching the
  repository `.nvmrc`; the WSL host's Node 22 build workers can hang during
  static page generation.
- Root and server source/wheel distributions built successfully in
  `/tmp/omnirush/agentguard-build-root` and `/tmp/omnirush/agentguard-build-server`.
- The owner-reported Docker Compose smoke run built the server image, waited for
  PostgreSQL health, applied all four migrations, and returned HTTP 200 from
  `/healthz` and `/readyz`. The live API docs were available at `/docs`.
- GitHub CI now runs both `npm test` and `npm run build` for the dashboard job.

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
- Phase 3 corpus verification used filtered clones in
  `/tmp/omnirush/phase3-corpus`; those external temporary files are not part
  of the repository.
- The R1 benchmark measures a fresh Python CLI subprocess but excludes outer
  `uv` startup and fixture generation; other filesystems and Python versions
  still require CI validation.
- Phase 5 plugins are bundled in the current root distribution for this
  workspace; standalone package metadata is also retained for plugin boundary
  builds. Installing both forms may expose duplicate entry points in external
  environments and should be normalized before publishing packages.
- Trace loop detection is a deterministic repeated-operation heuristic, not
  full graph-cycle reconstruction. Cost findings require explicit reported
  costs and never infer provider pricing from token counts.
- Triage providers are synchronous and responsible for their own SDK/network
  timeout. Redaction covers Python string literals and comments, not all
  possible secrets in identifiers or code structure.
- Docker is not available to the current Linux shell, although the owner has
  reported a successful Docker Compose validation from the host environment.
  Reproduce it with `docker compose up --build` where Docker is available.
- GitHub webhook handling verifies and queues scans; a production deployment
  still needs a worker that executes the analyzer and publishes GitHub Check
  Runs/SARIF annotations.
- Authentication currently provides environment-managed service tokens and
  repository scopes. A production identity provider, token rotation, and
  shared rate-limit storage remain deployment responsibilities.
