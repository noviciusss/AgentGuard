# AgentGuard: Build Spec (from scratch)

Static analysis CLI and plugin platform for AI agentic codebases (LangGraph, CrewAI, AutoGen, plain-Python agents).
It finds the bugs that make agents burn money, loop forever, leak data, or take destructive actions, **before** they run.

Mental model: `ruff` + `bandit` + `semgrep`, but the rules understand agent graphs, tool calls, retries, and LLM calls.

**The repo starts empty. Nothing exists yet.** Build everything in the phase order below. `AGENTS.md` defines how you work; this file defines what to build.

---

## 0. Ground rules

1. Phases are sequential and each is independently shippable. Finish, verify, commit, and stop at the end of each *step* (steps are listed per phase).
2. Rules operate on a **normalized Agent IR**, never on raw framework syntax. Framework-specific code lives only in adapters.
3. No network calls in core. LLM-powered features are optional plugins, off by default.
4. Python 3.10+, fully typed, `mypy --strict` clean, `ruff` clean.
5. Deterministic output: same input gives same output, findings sorted by (file, line, col, rule_id), stable fingerprints.
6. Every rule ships with fixtures, tests, and docs. No exceptions.
7. Low false positives beat high coverage. A noisy linter gets uninstalled. When unsure, lower the confidence rather than dropping the finding or raising severity.

---

## 1. Tech stack (decided)

| Concern | Choice | Why |
|---|---|---|
| Env / deps | `uv` | Fast, reproducible |
| Build backend | `hatchling` | Simple, supports src layout |
| CLI | `typer` + `rich` | Subcommands, good help, readable output |
| Parsing | stdlib `ast` | Fast; sufficient for analysis |
| Autofix (later) | `libcst` | Preserves formatting |
| Plugins (Phase 2) | `pluggy` + entry points | Same mechanism as pytest |
| Config models | `pydantic` v2 | Validated, typed |
| Tests | `pytest`, `hypothesis`, snapshot tests | |
| Lint/format | `ruff` | |
| Types | `mypy --strict` | |
| Parallelism | `concurrent.futures.ProcessPoolExecutor` per file | Files are independent |

Do not add dependencies beyond this table without asking.

---

## 2. Repository layout (single package for now)

Start as ONE package. Split into a monorepo of plugin packages only in Phase 2, after the plugin boundary is proven.

```
agentguard/
  AGENTS.md
  SPEC.md
  STATUS.md
  README.md
  LICENSE                      # MIT
  Makefile
  pyproject.toml
  .gitignore
  .github/workflows/ci.yml
  src/agentguard/
    __init__.py                # __version__
    __main__.py                # python -m agentguard
    cli/
      __init__.py              # typer app
      scan.py
      rules.py                 # `rules` + `explain`
    config.py                  # pydantic config + loading
    engine/
      discovery.py             # find .py files, honor excludes + .gitignore
      parser.py                # file -> ast.Module (+ source lines)
      runner.py                # orchestrates scan, parallel per file
      suppression.py           # inline ignore comments
      fingerprint.py
    ir/
      __init__.py
      models.py                # dataclasses (section 4)
      builder.py               # AST -> IR via adapters
      calls.py                 # known-call tables (LLM/HTTP/retry libs)
    adapters/
      base.py                  # FrameworkAdapter ABC
      generic.py               # plain Python: loops, retries, LLM/HTTP calls
      langgraph.py
    rules/
      base.py                  # Rule ABC, RuleContext, registry
      ag001_unbounded_retries.py
      ag002_shared_mutable_fanout.py
      ag003_missing_timeout.py
    reporters/
      base.py
      text.py
      json_reporter.py
    findings.py                # Finding, Severity, Confidence, Fix
  docs/
    rules/AG001.md AG002.md AG003.md
    architecture.md
  tests/
    conftest.py
    test_ir_*.py
    test_rules_fixtures.py     # parametrized fixture runner
    test_cli.py
    test_reporters.py
    fixtures/
      ag001/{bad_*.py,good_*.py,edge_*.py}
      ag002/...
      ag003/...
```

---

## 3. Phase plan

### Phase 0: Bootstrap
**Step 0.1** Create the scaffold: `pyproject.toml` (hatchling, src layout, console script `agentguard`, ruff + mypy + pytest config), `Makefile` (targets: `install`, `check`, `test`, `lint`, `fmt`, `types`), `.gitignore`, `README.md` stub, `LICENSE`, `STATUS.md`, CI workflow running `make check` on push/PR (Python 3.10, 3.11, 3.12).
**Step 0.2** `agentguard --version` works; a trivial test passes; `make check` is green.
**Done when:** fresh clone + `uv sync` + `make check` passes.

### Phase 1: Core engine, IR, three rules
**Step 1.1** `findings.py` and `ir/models.py` (section 4, section 5). Unit tests for dataclasses and fingerprints.
**Step 1.2** Discovery + parser + runner + suppression comments. Unit tests.
**Step 1.3** Rule base class + registry + fixture-driven test runner (section 9).
**Step 1.4** Generic adapter: detects loops, retry decorators/constructs, LLM/HTTP calls from `ir/calls.py`.
**Step 1.5** LangGraph adapter: `StateGraph` construction, `add_node`, `add_edge`, `add_conditional_edges`, `Send`, `compile(...)`, state schema with `Annotated` reducers.
**Step 1.6** Rule AG003 (section 6.3). Easiest, proves the pipeline end to end.
**Step 1.7** Rule AG001 (section 6.1).
**Step 1.8** Rule AG002 (section 6.2).
**Step 1.9** Reporters (text via `rich`, JSON) + CLI commands `scan`, `rules`, `explain` + config loading.
**Step 1.10** Docs for each rule, README with install + usage + example output.
**Done when:** `agentguard scan examples/` works on the bundled example agents, all fixtures pass, `make check` green, `mypy --strict` clean, runs on 3 real public LangGraph repos without crashing (list the repos in `STATUS.md` and the finding counts).

### Phase 2: Plugin system
- `pluggy` hookspecs and entry-point discovery (group `agentguard`).
- Move rules and adapters to be registered through the same hooks as third-party ones.
- Split into packages: `agentguard-core`, `agentguard-langgraph` (monorepo under `packages/`).
- CLI: `plugins list|info`, `plugins new NAME` (scaffolds a plugin package), `doctor`.
- Baseline support, `--select/--ignore`, severity overrides.
- **Done when:** a toy plugin installed from a separate folder adds a rule and appears in `agentguard rules`.

Hook specs:
```python
class AgentGuardSpec:
    @hookspec
    def register_rules(self) -> list[type[Rule]]: ...
    @hookspec
    def register_adapters(self) -> list[type[FrameworkAdapter]]: ...
    @hookspec
    def register_reporters(self) -> list[type[Reporter]]: ...
    @hookspec
    def register_commands(self, app: typer.Typer) -> None: ...
    @hookspec
    def modify_findings(self, findings: list[Finding], system: AgentSystem) -> list[Finding]: ...
```

### Phase 3: Rule expansion
- Add AG004 to AG011 and AG020 to AG023 (section 7). CrewAI and AutoGen adapters.
- Intra-function taint tracking for `DataSource`.
- Benchmarks doc: false-positive rate measured on 5 real repos.

### Phase 4: Reporters, CI, autofix
- SARIF 2.1.0 reporter, GitHub Action, pre-commit hook.
- `libcst` autofix for safe rules (add `timeout=`, add `recursion_limit`, pin model). `--fix-dry-run` prints a unified diff.

### Phase 5: Intelligence (optional plugins)
- `agentguard graph` (mermaid output).
- `agentguard-owasp`: tags findings with OWASP LLM Top 10 and CWE ids.
- `agentguard-llm-triage`: sends finding + snippet to an LLM to rate true/false positive and suggest a fix. Opt-in, provider-agnostic.
- `agentguard-trace`: ingest LangSmith/OpenTelemetry traces and flag loops/cost spikes seen in real runs.
- Inter-procedural taint.

### Phase 6: Platform (only if 1-5 are solid)
FastAPI + Postgres backend storing scan history from CI, Next.js dashboard (trends, per-repo risk), GitHub App for PR scans, README badge.

---

## 4. Findings model

```python
class Severity(str, Enum): ERROR="error"; WARNING="warning"; INFO="info"
class Confidence(str, Enum): HIGH="high"; MEDIUM="medium"; LOW="low"

@dataclass(frozen=True)
class Location:
    file: Path          # stored relative to scan root
    line: int           # 1-based
    col: int            # 0-based
    end_line: int
    end_col: int

@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    confidence: Confidence
    message: str                  # one sentence: what is wrong
    why: str                      # one sentence: why it matters
    suggestion: str               # one sentence: how to fix
    loc: Location
    related: tuple[Location, ...] = ()
    fingerprint: str = ""         # sha256(rule_id + relpath + normalized snippet)[:16]; independent of line numbers
    fix: Fix | None = None        # Phase 4
```

Text output example:
```
src/agent/nodes.py:42:8  AG003  warning  [high]  LLM call has no timeout
  why: a hung provider connection blocks the agent indefinitely
  fix: pass timeout=30 or configure the client with a default timeout
```

---

## 5. Agent IR

Rules never inspect `ast` nodes directly (they may read `ast` nodes referenced from the IR for locations/snippets). Adapters build the IR; rules consume it.

```python
class Capability(str, Enum):
    SHELL; FS_READ; FS_WRITE; FS_DELETE; NETWORK; SQL; EVAL; EMAIL; PAYMENT

class DataSource(str, Enum):
    LITERAL; USER_INPUT; TOOL_OUTPUT; LLM_OUTPUT; ENV; FILE; UNKNOWN

@dataclass
class CallSite:               # any call of interest
    loc: Location
    kind: Literal["llm", "http", "tool", "subprocess", "other"]
    qualified_name: str       # best-effort resolved, e.g. "requests.post", "openai.OpenAI.chat.completions.create"
    kwargs: dict[str, KwargInfo]   # names present; literal values captured when resolvable
    has_timeout: bool | None  # None = could not determine
    enclosing_function: str | None
    in_loop: bool

@dataclass
class Loop:
    loc: Location
    kind: Literal["while", "for", "retry_decorator", "retry_call", "recursion", "graph_cycle"]
    has_bound: bool | None    # None = could not determine
    bound_value: int | None
    bounded_by: str | None    # "range(N)", "attempt counter", "stop_after_attempt(N)", "recursion_limit", ...
    has_backoff: bool | None
    calls_inside: list[CallSite]
    catches_exceptions: bool

@dataclass
class StateKey:
    name: str
    has_reducer: bool         # LangGraph Annotated[T, reducer]
    mutable_type: bool        # list/dict/set annotations

@dataclass
class AgentNode:
    name: str
    framework: str
    loc: Location
    function_ref: str | None
    reads_state: set[str]
    writes_state: set[str]
    call_sites: list[CallSite]
    tools: list[ToolDef]

@dataclass
class ToolDef:
    name: str
    loc: Location
    capabilities: set[Capability]
    requires_approval: bool
    is_idempotent: bool | None

@dataclass
class Edge:
    source: str
    target: str | None        # None for unresolved conditional targets
    conditional: bool
    loc: Location

@dataclass
class FanOut:
    source: str               # node or Send call site
    branches: list[str]
    loc: Location
    mechanism: Literal["multiple_edges", "send_api", "thread_pool", "asyncio_gather", "crewai_async"]

@dataclass
class AgentGraph:
    name: str
    framework: str
    nodes: dict[str, AgentNode]
    edges: list[Edge]
    entry: str | None
    terminals: set[str]
    state_keys: dict[str, StateKey]
    recursion_limit: int | None
    fan_outs: list[FanOut]
    loc: Location

@dataclass
class ModuleFacts:            # per-file, produced by adapters
    path: Path
    call_sites: list[CallSite]
    loops: list[Loop]
    graphs: list[AgentGraph]
    module_mutables: dict[str, Location]   # module-level list/dict/set bindings
    imports: dict[str, str]                # alias -> qualified module

@dataclass
class AgentSystem:            # whole scan
    modules: list[ModuleFacts]
```

**Name resolution:** the builder resolves imports and aliases (`import requests as r`, `from openai import OpenAI`) so `r.get` resolves to `requests.get`. Track simple assignments like `client = OpenAI()` so `client.chat.completions.create` resolves to the OpenAI client family. If resolution fails, set the `qualified_name` to a best guess and the rule must lower confidence. Never crash on unresolvable code.

**Unknown is not false:** use `None` for "could not determine". Rules must handle `None` explicitly (usually: skip, or report LOW confidence).

---

## 6. Phase 1 rules (detailed)

### 6.1 AG001 unbounded-retries
**What:** retry/loop constructs around fallible calls (LLM, HTTP, tool) with no maximum attempts or time budget.
**Why:** a persistent failure (rate limit, outage, bad request) turns into an infinite loop that burns tokens and money, or hammers a failing service.

Detect:
1. `while True:` / `while 1:` / `while <non-counter condition>:` containing a `CallSite` of kind llm/http/tool inside a `try/except` (or whose result is checked and retried), with no `break`/`return`/`raise` reachable that is governed by a counter or deadline. Counter heuristic: a variable incremented in the loop and compared in a condition that exits the loop.
2. `tenacity`: `@retry` / `Retrying(...)` / `AsyncRetrying(...)` without a `stop=` argument, or with `stop=` that is not `stop_after_attempt`/`stop_after_delay`/combination thereof. `@retry` with `wait=` only is still unbounded.
3. `backoff` library: `@backoff.on_exception(...)` without `max_tries` or `max_time`.
4. Recursion retry: a function that calls itself from an `except` handler or after a failure check, with no depth/attempt parameter that changes between calls.
5. LangChain/OpenAI-style `max_retries=` values above 10 (WARNING, MEDIUM confidence); `max_retries=None` handled per library docs if verifiable.

Do NOT flag:
- `for _ in range(N)` retry loops, or loops with a counter bounded by a literal or config constant.
- `while True` event loops that contain no LLM/HTTP/tool call (e.g. a queue consumer with blocking `get()`), unless a fallible call is inside a try/except retry shape.
- Loops with a deadline check (`time.monotonic() < deadline`) as the condition.

Severity: ERROR when LLM call inside an unbounded loop (HIGH confidence); WARNING for HTTP/tool calls; WARNING + MEDIUM when bound could not be determined (`has_bound is None`).

Fix suggestion: add `stop_after_attempt(N)` / counter, plus exponential backoff with jitter and a max delay.

### 6.2 AG002 shared-mutable-fanout
**What:** parallel branches that read and write the same mutable state without safe merging.
**Why:** race conditions and lost updates; behavior varies run to run, which is nearly impossible to debug in agents.

Detect:
1. **LangGraph state keys:** two or more nodes that run in parallel (fan-out via multiple edges from one node, or `Send`) and write the same state key where the key has no reducer (`Annotated[list, operator.add]` or custom). Parallel writers to a key without a reducer cause `InvalidUpdateError` or lost writes. HIGH confidence when both writers resolved; MEDIUM when one branch is unresolved.
2. **Module-level mutables:** a module-level `list`/`dict`/`set` (or `defaultdict`, `deque`, etc.) that is mutated (`append`, `update`, item assignment, `+=`) inside a function that is submitted to `ThreadPoolExecutor.submit/map`, `asyncio.gather`, `asyncio.create_task`, `threading.Thread(target=...)`, or used as a LangGraph node in a parallel branch, with no lock (`threading.Lock`, `asyncio.Lock`) held around the mutation.
3. Mutable default arguments (`def node(state, cache={})`) on functions used as nodes/tasks (WARNING, HIGH).
4. Shared mutable object passed to multiple tasks (same variable in several `submit`/`gather` argument lists, then mutated).

Do NOT flag: reads only; mutation under `with lock:`; thread-local storage; keys with reducers; per-call local mutables.

Severity: ERROR for unreduced parallel LangGraph state-key writes; WARNING for module-level mutables.

### 6.3 AG003 missing-timeout
**What:** network calls (HTTP clients, LLM SDK clients, tool HTTP calls) with no explicit timeout.
**Why:** a hung connection blocks the whole agent indefinitely (or for a very long default), freezing runs and pinning workers.

Maintain a data table in `ir/calls.py` of known calls, with how each library handles timeouts. **Verify each library's defaults against its installed version before encoding them**; do not trust this table blindly. Starting points (confirm):

| Library / call | Timeout behavior to check |
|---|---|
| `requests.get/post/put/delete/request`, `Session.*` | no default timeout: flag when `timeout=` absent (ERROR if inside a loop or LLM-adjacent, else WARNING) |
| `urllib.request.urlopen` | flag if `timeout` absent |
| `httpx.get/post/...`, `httpx.Client/AsyncClient` | has a default; flag only `timeout=None` explicitly (WARNING) |
| `aiohttp.ClientSession` | has a long default total; flag when no `timeout=` is configured anywhere (INFO/LOW) |
| OpenAI SDK client / `chat.completions.create` / `responses.create` | long default; flag when no timeout on client constructor and none per call (WARNING) |
| Anthropic SDK client / `messages.create` | same approach |
| LangChain chat models (`ChatOpenAI`, `ChatAnthropic`, ...) | flag constructors without `timeout`/`request_timeout`/`default_request_timeout` (WARNING, MEDIUM) |
| `subprocess.run` of network tools | out of scope |

Resolve client-level timeouts: if `client = OpenAI(timeout=30)` and `client.chat.completions.create(...)` is called without per-call timeout, the call **has** a timeout (`has_timeout=True`). Track simple assignments within the module.

Do NOT flag: calls where `timeout` is passed via `**kwargs` (set `has_timeout=None`, report nothing or LOW confidence at most); test files if `exclude_tests` config is on (default on).

Fix suggestion: add `timeout=<seconds>`; for agents, also add an overall run deadline.

---

## 7. Later rule catalog (Phase 3+)

Reliability and cost: **AG004** unbounded-agent-loop (cycle without `recursion_limit`/max iterations/terminal edge; CrewAI `max_iter`, AutoGen `max_round`), **AG005** no-cost-budget (no `max_tokens` on an LLM call inside a loop), **AG006** unreachable-graph-node, **AG007** conditional-edge-unmapped-key, **AG008** exception-swallowed-in-tool, **AG009** non-idempotent-tool-with-retry, **AG010** unpinned-model-alias, **AG011** unbounded-state-growth (message list appended every loop, never trimmed).

Security: **AG020** prompt-injection-sink (tool output or user input flows into system prompt of an agent with dangerous tools), **AG021** dangerous-tool-no-approval (shell/delete/payment/email tool without a human-in-the-loop gate), **AG022** llm-output-to-sink (LLM output reaches `eval`/`exec`/`subprocess`/raw SQL/file path), **AG023** hardcoded-secret, **AG024** secret-in-prompt, **AG025** ssrf-via-tool, **AG026** path-traversal-via-tool, **AG027** overbroad-tool-scope.

Hygiene: **AG030** no-tracing, **AG031** no-tests-for-agent, **AG032** duplicated-prompt.

Each added rule follows the same recipe as section 6: spec paragraph (what/why/detect/do-not-flag/severity/fix), fixtures, docs page.

---

## 8. CLI

```
agentguard scan [PATHS...]          # default path: .
    --format text|json              # sarif/markdown added Phase 4
    --output FILE
    --select AG001,AG00*   --ignore AG003
    --min-severity info|warning|error
    --min-confidence low|medium|high
    --fail-on error|warning|never   # default: error
    --jobs N
    --no-cache                      # cache added when needed; flag exists from start (no-op)
agentguard rules                    # list rules: id, name, severity, one-line description
agentguard explain AG001            # render docs/rules/AG001.md in terminal
agentguard --version
```
Later: `init`, `baseline create`, `plugins ...`, `doctor`, `graph`, `watch`.

Exit codes: `0` clean (or below `--fail-on`), `1` findings at/above `--fail-on`, `2` usage/config error, `3` internal error. A file that fails to parse produces a warning on stderr and is skipped; it never crashes the scan.

Inline suppression:
```python
llm.invoke(p)  # agentguard: ignore[AG003] reason: internal gateway enforces deadline
```
Bare `# agentguard: ignore` suppresses all rules on that line. File-level: `# agentguard: ignore-file[AG003]` in the first 10 lines.

Config (`pyproject.toml` `[tool.agentguard]` or `agentguard.toml`):
```toml
[tool.agentguard]
select = ["AG*"]
ignore = []
exclude = ["tests/", ".venv/", "build/"]
exclude_tests = true
min_severity = "info"
min_confidence = "low"
fail_on = "error"

[tool.agentguard.severity]      # per-rule overrides
AG003 = "error"
```
Precedence: CLI flags > config file > defaults. Invalid config exits with code 2 and a clear message.

---

## 9. Testing strategy

- **Fixture-driven rule tests.** `tests/test_rules_fixtures.py` parametrizes over `tests/fixtures/<rule>/*.py`. Mark expected findings with a comment on the exact line: `# expect: AG003`. `bad_*` files must produce exactly the marked findings; `good_*` files produce none; `edge_*` files are tricky cases with their own markers. Fail on both missing and unexpected findings.
- **Minimum fixtures per rule:** 5 bad, 5 good, 3 edge, covering plain Python and LangGraph shapes, aliased imports, and client-level timeouts for AG003.
- **IR unit tests:** snippets in, IR out. Include `hypothesis` tests asserting the builder never crashes on arbitrary valid Python and that parse errors are handled.
- **Reporter snapshot tests** for text and JSON.
- **CLI tests** via `typer.testing.CliRunner`: exit codes, `--select/--ignore`, `--fail-on`, bad config, unparseable file.
- **Corpus test (Phase 1 exit criterion):** run on 3 real public LangGraph repos; assert no crashes. Record finding counts and a manual false-positive spot check in `STATUS.md`.
- **Self-scan:** CI runs `agentguard scan src/` on its own code.
- **Performance budget:** 10k LOC in under 5 seconds cold.
- Verify LangGraph/library APIs against the **installed version's source** when writing adapters. Do not rely on memory.

---

## 10. Bundled examples (`examples/`)

Create small realistic agents used for demos and smoke tests, each containing deliberate issues: `examples/langgraph_support_bot/` (retry loop, unreduced parallel state key, LLM call without timeout), `examples/plain_python_agent/` (while-True retry, thread pool with shared dict), `examples/clean_agent/` (everything correct, must produce zero findings). `agentguard scan examples/` is the README demo.

---

## 11. Quality bar and non-goals

**Quality bar:** every finding states what, why, and how to fix; every rule documented; confidence reflects uncertainty honestly; no crashes on weird code; fast.

**Non-goals for v1:** runtime instrumentation, non-Python languages, LLM dependency in core, auto-applying fixes without an explicit flag.

## 12. v1.0 definition of done

- [ ] Phase 1 complete and verified on real repos
- [ ] Plugin system with docs and `plugins new` template
- [ ] 15+ documented rules across reliability and security
- [ ] LangGraph, CrewAI, AutoGen adapters
- [ ] SARIF + GitHub Action working on a real repo
- [ ] Autofix for 3+ rules
- [ ] Published to PyPI
- [ ] `docs/benchmarks.md` with measured false-positive rates
- [ ] README with a 30-second demo GIF
