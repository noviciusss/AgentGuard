# AgentGuard architecture

AgentGuard is a static analysis pipeline for Python agent code. It separates
framework parsing from analysis so rules can reason about one stable model
instead of depending on LangGraph, SDK, or application syntax.

## Scan pipeline

1. **Discovery** finds Python files under the requested paths. Explicit
   excludes, nested `.gitignore` files, and the default test exclusion are
   applied before parsing.
2. **Parsing** reads source with Python's encoding rules and builds an AST.
   A syntax or encoding failure becomes a diagnostic on stderr; it does not
   abort the scan.
3. **Adapters** translate parsed modules into the Agent IR. The generic adapter
   handles ordinary Python. The LangGraph adapter recognizes `StateGraph`,
   nodes, edges, `Send`, and reducer annotations. Adapters never emit
   findings.
4. **Rules** consume only `AgentSystem` and its normalized facts. The registry
   selects rules by stable IDs, validates their output, assigns fingerprints,
   and sorts findings.
5. **Filtering** applies configuration thresholds, severity overrides, rule
   selection, and inline/file suppressions.
6. **Reporters** render the already-analyzed findings as text or JSON. They do
   not inspect source or repeat analysis.

## Agent IR

The IR contains module facts, call sites, retry/loop facts, agent graphs, state
keys, fan-outs, and source locations. Unknown values are represented as
`None`; rules lower confidence or skip a finding rather than treating unknown
information as proof that a property is absent.

Locations use paths relative to the scan root. Findings are sorted by file,
line, column, and rule ID. Fingerprints use the rule ID, relative path, and a
normalized source snippet, so moving a finding to another line does not change
its identity.

## Extension boundary

Phase 1 ships built-in adapters and rules through the same typed interfaces
that the Phase 2 plugin manager will expose. The engine depends on the adapter,
IR, rule, and reporter contracts; rules do not import framework adapters and
reporters do not re-analyze source.

## Safety properties

- Source is parsed but never imported or executed.
- Core analysis makes no network calls.
- Unresolved names and dynamic keyword arguments are handled conservatively.
- Parallel parsing preserves deterministic ordering before rules run.
- Suppressions are explicit and can include a reason for code review.

## Phase 5 intelligence plugins

Phase 5 capabilities keep the scanner offline. Graph and trace analysis are
explicit CLI commands; LLM triage is additionally opt-in through a user-owned
provider. The bundled distributions are discovered through the same plugin
boundary as separately installed plugins.

- `agentguard graph` renders normalized graph nodes, entry/terminal markers,
  static and conditional edges, unresolved targets, and fan-outs as Mermaid.
  Labels are escaped and IDs are generated independently of user names.
- `agentguard-owasp` adds deterministic OWASP LLM Top 10 (2025) and CWE tags
  to applicable findings. JSON and SARIF preserve machine metadata; text output
  shows tags and metadata when present.
- `agentguard-llm-triage` reads a JSON finding report and a bounded,
  string/comment-redacted local source snippet. It validates provider results,
  supports request-bound private caches, and never changes finding severity.
- `agentguard-trace` reads flat, LangSmith-like, or nested OTLP JSON exports.
  It reports repeated operations within one trace (`TRACE001`) and explicit
  cost outliers (`TRACE002`) without inferring provider prices.

The generic adapter records a same-file function call graph and performs
argument-sensitive return and sink propagation through direct module-level
functions. Summaries use a fixed point so definition order and recursive call
graphs terminate. Imported/cross-module calls, class or nested-function
dispatch, and other dynamic callables remain unknown rather than being treated
as tainted.
