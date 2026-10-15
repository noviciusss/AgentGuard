# Distribution and installation profiles

AgentGuard currently supports two mutually exclusive installation profiles.
Both profiles use the same `agentguard` entry-point group, so installing both
profiles into one environment can create duplicate plugin entry points.

## Profile A: bundled CLI

Install the root `agentguard` distribution. This is the recommended profile for
the complete CLI and includes the core, official adapters, and official Phase 5
plugins in one wheel.

```console
uv pip install agentguard
agentguard plugins list
agentguard scan .
```

Do not additionally install the standalone AgentGuard plugin wheels into this
environment.

## Profile B: core plus selected plugins

Install `agentguard-core` and only the plugins needed by the environment:

```console
uv pip install agentguard-core agentguard-langgraph agentguard-graph
agentguard plugins list
```

The standalone plugin packages depend on `agentguard-core`, not the bundled
`agentguard` distribution. This profile is intended for minimal deployments,
plugin development, and independent package testing.

## Package ownership

| Distribution | Owns | Entry-point contributions |
|---|---|---|
| `agentguard` | Bundled compatibility CLI, core, official plugins | `langgraph`, `graph`, `owasp`, `llm_triage`, `trace` |
| `agentguard-core` | Framework-neutral engine and contracts | None |
| `agentguard-langgraph` | LangGraph adapter | `langgraph` |
| `agentguard-graph` | Mermaid graph command | `graph` |
| `agentguard-owasp` | OWASP/CWE finding modifier | `owasp` |
| `agentguard-llm-triage` | Opt-in triage command | `llm_triage` |
| `agentguard-trace` | Local trace command | `trace` |

The root bundle and standalone plugin wheels are both built from this
repository, but they are not intended to be installed together. Before PyPI
publication, CI must build and test both profiles in isolated environments.

## Release requirements

- Every distribution has a matching versioning policy.
- Standalone plugin dependencies resolve to `agentguard-core`.
- A clean bundled installation discovers all bundled commands without load
  errors.
- A clean core-plus-selected-plugins installation discovers only its selected
  contributions.
- Installing a profile never reads credentials or makes network calls during
  static analysis.
- Wheel contents and entry points are inspected before publishing.
