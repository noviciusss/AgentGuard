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

## Optional intelligence plugins

Phase 5 functionality remains opt-in and keeps the core scanner offline:

- `agentguard-graph` renders normalized graph edges as Mermaid text.
- `agentguard-owasp` adds deterministic OWASP LLM Top 10 and CWE metadata to
  matching findings.
- `agentguard-llm-triage` uses a user-supplied provider and optional local
  cache; it is advisory and never changes finding severity.
- `agentguard-trace` reads local JSON span exports and reports repeated failed
  spans without contacting a tracing service.

The generic adapter also records a same-file function call graph and resolves
return-source summaries through local calls. Summaries are computed to a fixed
point, so definition order and bounded recursive call graphs do not affect
termination. Dynamic dispatch, cross-module calls, and argument-sensitive
interprocedural flow remain unknown rather than being treated as tainted.
