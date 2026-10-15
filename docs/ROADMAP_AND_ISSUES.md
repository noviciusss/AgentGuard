# AgentGuard roadmap and issue register

This document is the planning and risk register for work after Phase 5. It is
based on `SPEC.md`, the verified implementation recorded in `STATUS.md`, and
the current repository/package layout.

## Current position

- **Phase 0 — Bootstrap:** complete.
- **Phase 1 — Core engine, IR, and initial rules:** complete and exercised on
  the recorded corpus.
- **Phase 2 — Plugin system:** complete, including external plugin discovery,
  scaffolding, baselines, and package boundaries.
- **Phase 3 — Rule expansion:** complete, including the 15 currently shipped
  rules and CrewAI/AutoGen adapters.
- **Phase 4 — Reporters, CI, and autofix:** complete, including SARIF, the
  reusable GitHub Action, pre-commit integration, and three safe autofixes.
- **Phase 5 — Intelligence:** complete locally. It includes graph rendering,
  OWASP/CWE tagging, opt-in LLM triage, local trace analysis, and same-file
  argument-sensitive inter-procedural taint.
- **Current next step:** Phase 6.1 server and PostgreSQL foundation. R0 and R1
  release gates are complete for the current repository model.

The latest verified local result is `make check` with 356 passing tests,
strict mypy clean across 102 checked source files, and clean Ruff checks. These
checks were run on Python 3.13. The complete CI matrix still needs an external
run.

## Approved Phase 6 direction

The owner approved the following platform direction:

- FastAPI backend.
- PostgreSQL persistence.
- A PostgreSQL driver and migration tool selected before implementation.
- A separate Next.js frontend after the backend contract is stable.
- GitHub App integration for pull-request scans.
- Public or repository-scoped risk badges, subject to privacy and authorization
  review.

Phase 6 must not make network services a requirement for the local CLI. Core
static analysis remains offline and deterministic.

## Roadmap

### Unit R0 — Release-readiness and repository alignment

**Goal:** make the completed Phase 5 work publishable and accurately described
before adding hosted platform complexity.

**Work:**

1. Reconcile `STATUS.md` current position and historical phase wording.
2. Review the stale v1 checklist in `SPEC.md` against actual implementation.
3. Separate and commit completed units with conventional commit messages.
4. Decide whether the root distribution is a compatibility bundle or whether
   every plugin is independently published.
5. Normalize package dependencies and entry-point ownership.
6. Build and install each distribution in isolation.
7. Verify the documented install paths from a clean environment.

**Expected files:**

```text
pyproject.toml
uv.lock
packages/*/pyproject.toml
.github/workflows/ci.yml
README.md
STATUS.md
SPEC.md
```

**Acceptance:** no duplicate plugin entry points in the supported install
model; clean wheel/source installs discover exactly the documented commands and
plugins; `make check` remains green.

**Risks:** changing package ownership can break the current editable workspace
or external-plugin acceptance test. Preserve a compatibility install path or
make the migration explicit in the release notes.

**Status:** complete for the current repository model. The root `agentguard`
bundle is the recommended complete CLI profile; `agentguard-core` plus selected
standalone plugins is the minimal profile. They are documented as mutually
exclusive, standalone plugin dependencies now target `agentguard-core`, and all
six current distributions build successfully. Isolated installation tests are
still required before publication.

### Unit R1 — Performance and corpus gate

**Goal:** turn the existing performance target and corpus notes into repeatable
evidence.

**Work:**

- Add a reproducible 10,000-line cold-start benchmark.
- Measure parsing, IR construction, rules, reporting, and process-based jobs
  separately where useful.
- Keep the SPEC target of under five seconds visible and measured.
- Re-run the five recorded public corpora.
- Record scan duration, file counts, parse diagnostics, finding counts by rule,
  and manual false-positive observations.
- Add a non-flaky CI smoke threshold rather than a brittle exact timing test.

**Expected files:**

```text
benchmarks/scan_10k.py
tests/test_benchmarks.py
docs/benchmarks.md
STATUS.md
```

**Acceptance:** the benchmark is reproducible locally, corpus scans do not
crash, and any missed performance target is recorded as an issue rather than
silently ignored.

The local benchmark and `examples/` corpus gate are implemented. The five
public repositories were refreshed in the R1 acceptance run; their counts and
manual spot checks are recorded in `docs/benchmarks.md`.

**Risks:** process startup and mounted Windows filesystems can distort timing.
Record environment details and compare like-for-like runs.

### Unit 6.1 — Server and persistence foundation

**Goal:** add a versioned API and durable scan-history storage without coupling
the core analyzer to the service.

**Proposed layout:**

```text
packages/agentguard-server/
  src/agentguard_server/
    app.py
    config.py
    db.py
    models.py
    migrations/
    api/
    services/
  tests/
```

**Work:**

- Create a FastAPI application factory.
- Add PostgreSQL connection/configuration handling.
- Add migrations and a schema version policy.
- Store repositories, branches, commits, scans, findings, baselines, and
  plugin/configuration versions.
- Make scan ingestion idempotent using repository/commit/scan identifiers.
- Add health and readiness endpoints.
- Add pagination and deterministic ordering to read endpoints.

**Dependencies requiring an implementation-time decision:**

- FastAPI and an ASGI server.
- A PostgreSQL driver, preferably one with a clear async/sync policy.
- A migration tool.
- An ORM or typed SQL layer.

The chosen set must be added to the plan before dependency changes and locked
in `uv.lock`. Do not add a database substitute merely to avoid running
PostgreSQL in tests; service behavior must be tested against PostgreSQL.

**Acceptance:** migrations apply to a clean database, API tests cover normal
and invalid requests, duplicate ingestion is safe, and the core package does
not import the server package.

### Unit 6.2 — CI scan ingestion API

**Goal:** receive scan results from CI safely and make them queryable.

**Work:**

- Accept JSON and SARIF uploads.
- Store repository identity, commit SHA, branch, pull request number, tool
  version, plugin versions, configuration, fingerprints, and timestamps.
- Enforce payload-size and field-size limits.
- Make retries idempotent.
- Reject malformed findings and invalid repository identifiers.
- Expose scan summaries and finding history with pagination and filters.

**Acceptance:** the same upload can be retried without duplicate findings;
different repositories cannot read each other's data; malformed uploads return
clear 4xx responses.

### Unit 6.3 — Authentication, authorization, and data protection

**Goal:** make stored scan data safe before exposing a dashboard or GitHub App.

**Work:**

- Define user, organization, repository, and service-token ownership.
- Add authentication and repository-level authorization.
- Add audit events for uploads, reads, deletes, and webhook actions.
- Define retention, deletion, export, and backup policies.
- Keep source snippets and triage output protected as sensitive data.
- Use environment-managed secrets only.
- Add rate limits and request correlation IDs.

**Acceptance:** authorization tests demonstrate tenant isolation; unauthenticated
and cross-repository reads fail; sensitive values are absent from logs and
error responses.

**Risk:** authentication is security-critical and should not be replaced with
temporary development behavior in a production path.

### Unit 6.4 — GitHub App and pull-request scans

**Goal:** run or receive scans for pull requests and report only actionable
changes.

**Work:**

- Implement GitHub App installation and repository selection.
- Verify webhook signatures and prevent replay processing.
- Handle pull-request opened, synchronized, and reopened events.
- Run scans against the correct commit.
- Compare against baselines and changed findings.
- Publish Check Run/SARIF annotations.
- Handle retries, cancellation, rate limits, and partial failures.

**Acceptance:** signed events create one idempotent scan; invalid signatures
are rejected; a pull request receives deterministic findings tied to its commit
and repository.

### Unit 6.5 — Dashboard

**Goal:** expose scan history and risk trends through a separate frontend.

**Proposed layout:**

```text
web/
  app/
  components/
  lib/
  tests/
```

**Work:**

- Repository list and repository detail pages.
- Scan history and trend charts.
- Finding details with rule, severity, confidence, source location, and
  remediation.
- Baseline comparison and pull-request context.
- Empty, loading, forbidden, unavailable, and error states.
- API client generated or typed from the backend contract.

**Acceptance:** browser smoke tests cover the primary repository and finding
flows; the frontend does not bypass backend authorization.

### Unit 6.6 — Badge and public reporting

**Goal:** provide a useful badge without leaking private repository data.

**Work:**

- Define badge levels and their calculation window.
- Add repository-scoped authorization or intentionally public tokens.
- Add cache headers and rate limits.
- Handle missing, stale, private, and unavailable data.
- Document the badge URL and privacy behavior.

**Acceptance:** private repositories never become readable through badge
endpoints; badge results are deterministic and cache-safe.

### Unit 6.7 — Release and distribution

**Goal:** publish reproducible packages and platform artifacts.

**Work:**

- Define versioning across core and plugin packages.
- Add trusted PyPI publishing.
- Build wheels and source distributions in CI.
- Add clean-install smoke tests.
- Generate release notes from verified changes.
- Document supported Python versions and optional plugin installation.
- Add a short demo or recording to the README if still desired.

**Acceptance:** a clean environment can install the documented package set,
run `agentguard --version`, discover plugins, and complete the smoke scan.

## Issue register

Severity uses **P0** for a release/security blocker, **P1** for a high-risk
correctness or operational issue, and **P2** for important follow-up work.

### P1 — Package and entry-point ownership needs publication verification

**Evidence:** the root distribution bundles Phase 5 plugins while standalone
plugin packages also define their own entry points.

**Impact:** installing both forms may produce duplicate-entry-point diagnostics
or confusing plugin ownership. The supported profiles now explicitly avoid
that combination.

**Action:** keep the two profiles mutually exclusive, add isolated-install
tests in CI, and reject or clearly warn about unsupported mixed installs in
release documentation.

**Target:** Unit R0 complete; CI publication verification remains open.

### P1 — Phase status and specification wording can drift

**Evidence:** historical phase sections, current-position text, and the v1
checklist were written at different times.

**Impact:** contributors may repeat completed work or assume unchecked work is
finished.

**Action:** maintain `STATUS.md` as the operational record and update SPEC
checklists only when the acceptance evidence exists.

**Target:** Unit R0.

### P1 — No dedicated performance gate exists

**Evidence:** the SPEC requires 10,000 lines under five seconds, while the
benchmark document records that a dedicated cold-start harness is not present.

**Impact:** regressions in IR construction or inter-procedural analysis can
ship unnoticed.

**Action:** implement the R1 benchmark and record environment-aware results.

**Target:** Unit R1.

### P1 — Phase 6 will introduce sensitive data storage

**Evidence:** scan findings, source locations, snippets, triage output, commit
metadata, and potentially repository identifiers will enter the platform.

**Impact:** an authorization, logging, backup, or retention mistake could leak
proprietary source or security findings.

**Action:** complete the security/data model before dashboard or GitHub App
work; add tenant-isolation, deletion, and log-redaction tests.

**Target:** Unit 6.3 before Units 6.4–6.6.

### P1 — GitHub webhook trust and replay protection are not implemented

**Evidence:** the GitHub App is still only a planned Phase 6 feature.

**Impact:** forged or replayed webhooks could trigger unauthorized scans or
write incorrect results.

**Action:** verify HMAC signatures, timestamps/delivery IDs, installation
permissions, and idempotency before processing events.

**Target:** Unit 6.4.

### P1 — Core/plugin distribution boundary needs clean-install proof

**Evidence:** the root bundle and standalone packages intentionally have
different profiles. Standalone Phase 5 plugin metadata now depends on
`agentguard-core`.

**Impact:** without clean-install tests, a future dependency or entry-point
change could reintroduce the wrong package resolution or duplicate discovery.

**Action:** define the supported dependency graph in CI and test it from clean
wheels for both profiles.

**Target:** R0 metadata alignment complete; clean-install CI remains open.

### P2 — Trace loop detection is heuristic

**Evidence:** `TRACE001` detects repeated operations within a trace, not a full
control-flow cycle.

**Impact:** repeated legitimate operations may be reported, while unusual cycle
patterns may be missed.

**Action:** keep confidence and identity in findings; add sequence/cycle
analysis only when real trace corpora demonstrate a need.

**Target:** monitor after release; do not overfit synthetic traces.

### P2 — Explicit cost is required for cost spikes

**Evidence:** trace analysis never infers provider prices from token counts.

**Impact:** many traces cannot produce cost findings without instrumentation
that records cost.

**Action:** document the input contract and optionally support a user-supplied
local pricing table in a later, separately scoped unit.

**Target:** post-Phase 6 telemetry feedback.

### P2 — Triage redaction is not a secret guarantee

**Evidence:** strings and comments are redacted, but identifiers, code shape,
finding messages, and provider output can still contain sensitive information.

**Impact:** a user can unintentionally transmit proprietary information to a
provider.

**Action:** keep triage explicitly opt-in, document the data boundary, add
provider trust warnings, and consider a configurable local redaction policy.

**Target:** before public triage release; no automatic remote provider in scan.

### P2 — Provider timeout is delegated

**Evidence:** triage providers are synchronous and own their SDK/network
timeout.

**Impact:** a badly behaved provider can block a CLI invocation.

**Action:** document the provider contract and consider a future subprocess
execution mode with a hard timeout. Do not add unsafe thread termination.

**Target:** later triage hardening unit.

### P2 — Same-file taint is intentionally incomplete

**Evidence:** cross-module calls, class methods, nested functions, and dynamic
dispatch remain unknown.

**Impact:** some real flows will be missed; aggressive inference would increase
false positives.

**Action:** preserve conservative behavior. Only add project-level symbol and
taint indexing after corpus evidence justifies the complexity.

**Target:** post-release analysis, not an unbounded Phase 6 prerequisite.

### P2 — Graph terminal representation is ambiguous in the IR

**Evidence:** `Edge.target is None` can represent an unresolved conditional
target or an edge to a terminal; terminal metadata is required to interpret it.

**Impact:** consumers that ignore `AgentGraph.terminals` can render incorrect
graphs.

**Action:** either split terminal and unresolved edge representations in a
future IR revision or document the invariant for all consumers.

**Target:** next IR revision, if a second graph consumer requires it.

### P2 — CI matrix evidence is incomplete locally

**Evidence:** local checks have run on Python 3.13; the repository CI matrix
has not completed for the current uncommitted Phase 5 state.

**Impact:** Python 3.10–3.12 compatibility regressions may remain hidden.

**Action:** run the actual GitHub matrix before release and preserve any
version-specific failures as tracked issues.

**Target:** Unit R0/release gate.

### P2 — The README demo GIF is not present

**Evidence:** the v1 definition of done lists a 30-second demo GIF, but no
verified artifact is recorded.

**Impact:** onboarding is less effective, though this does not affect analyzer
correctness.

**Action:** create a short redacted demo only after the CLI and package install
flow are stable.

**Target:** Unit 6.7 or explicitly remove the requirement from the v1 spec.

### P2 — Hosted platform scope is large for a solo maintainer

**Evidence:** Phase 6 combines API, PostgreSQL, authentication, frontend,
GitHub App, jobs, deployment, and public badges.

**Impact:** platform work can delay analyzer quality and create operational
burden.

**Action:** implement the backend contract and a narrow scan-history slice
first; defer dashboard, App, and badges until the service is secure and useful.

**Target:** roadmap sequencing decision.

## Required gates before public release

- [ ] `make check` passes on the supported Python matrix.
- [ ] Root and standalone package ownership is finalized.
- [ ] Clean-install plugin discovery is tested.
- [ ] The 10,000-line performance target is measured.
- [ ] Corpus scans and false-positive notes are current.
- [ ] No credentials or private payloads appear in fixtures, logs, caches, or
      documentation.
- [ ] Triage disclosure and provider trust warnings are visible.
- [ ] GitHub webhook verification is tested before enabling the App.
- [ ] PostgreSQL migrations and backup/retention policy are documented before
      storing user scans.
- [ ] Release artifacts are built from CI and verified in a clean environment.
- [ ] The README installation and demo path work from a fresh clone.

## Recommended execution order

1. Unit R0 — release/package alignment. **Complete.**
2. Unit R1 — benchmark and corpus gate. **Complete.**
3. Unit 6.1 — server and PostgreSQL foundation.
4. Unit 6.2 — CI ingestion and scan history.
5. Unit 6.3 — authentication, authorization, and data protection.
6. Unit 6.4 — GitHub App and pull-request scans.
7. Unit 6.5 — dashboard.
8. Unit 6.6 — badge/public reporting.
9. Unit 6.7 — release automation and final v1 documentation.

Each unit should have its own approval, focused tests, `make check`, status
update, and conventional commit. Do not start the next unit while the current
unit has failing checks or unresolved security decisions.
