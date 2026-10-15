# Phase 3 benchmark

This report records the Phase 3 acceptance corpus run. Repositories were
shallow or filtered clones made on 2026-10-12. The scanner ran with the
default configuration and `--format json --fail-on never`; no repository was
imported or executed.

## Corpus results

| Repository | Python files | Lines | Findings | Rule distribution | Result |
|---|---:|---:|---:|---|---|
| `langchain-ai/langgraph` | 468 | 197,863 | 38 | AG003: 13, AG004: 5, AG007: 13, AG010: 5, AG020: 1, AG023: 1 | completed without crash |
| `langchain-ai/langgraph-supervisor-py` | 8 | 1,616 | 0 | — | completed without crash |
| `langchain-ai/langgraph-swarm-py` | 11 | 978 | 2 | AG003: 1, AG010: 1 | completed without crash |
| `crewAIInc/crewAI-examples` | 116 | 5,489 | 16 | AG003: 14, AG010: 2 | completed without crash |
| `microsoft/autogen` (`python/samples`) | 62 | 5,506 | 3 | AG011: 3 | completed without crash |

The scan results are intentionally not committed as generated JSON artifacts.
The commands and counts above are the reproducible acceptance record.

## Manual spot checks

- LangGraph model constructors and conditional routes produced findings at
  source locations containing the corresponding constructor or graph call.
- LangGraph cycle findings occurred in example graphs with explicit cycles and
  no visible `recursion_limit`.
- CrewAI examples reported concrete `requests` calls without timeouts and
  model aliases such as `gpt-4o`; these are valid candidates for review.
- AutoGen findings occurred on message collections appended in repeated loops.
- The supervisor repository produced no findings and completed without a
  parser or adapter failure.

These are manual plausibility checks, not a statistically measured precision
study. Phase 3's implementation remains conservative where names or framework
metadata cannot be resolved.

## Performance note

The largest corpus scan completed successfully in the local acceptance run.

## R1 performance and corpus gate

The repository now includes repeatable local tools:

```console
uv run --locked python benchmarks/scan_10k.py --repeats 3 --budget-seconds 5
uv run --locked python benchmarks/corpus_gate.py examples --output corpus.json
```

The 10,000-line benchmark generates one deterministic Python module and runs a
fresh `python -m agentguard scan` subprocess for each timing sample. Fixture
generation and the outer `uv` startup are excluded; Python CLI startup, parsing,
IR construction, rules, plugin modifiers, and JSON reporting are included.

Verified locally on Python 3.13.5 under WSL:

| Workload | Samples (seconds) | Median | Budget | Result |
|---|---|---:|---:|---|
| 10,000 lines, 1 file, `--jobs 1` | 3.443, 4.090, 3.774 | 3.774 | 5.000 | passed |

The generated fixture produced zero findings and zero parse errors. This meets
the SPEC performance target for the measured environment. It is not a claim
about Windows-mounted filesystem performance, other Python versions, or large
multi-file repositories.

The local examples corpus gate also passed:

| Corpus | Python files | Lines | Findings | Parse errors | Result |
|---|---:|---:|---:|---:|---|
| `examples/` | 3 | 97 | 12 | 0 | completed without crash |

Rule distribution for that run was AG001: 2, AG002: 3, AG003: 3, AG005: 1,
AG006: 2, and AG010: 1. The corpus tool only analyzes paths supplied by the
user; it does not clone repositories or make network calls.

The R1 refresh also scanned fresh shallow public clones using the default
`exclude_tests = true` configuration:

| Repository | Python files | Lines | Findings | Parse errors | Elapsed seconds | Result |
|---|---:|---:|---:|---:|---:|---|
| `langchain-ai/langgraph` | 261 | 85,672 | 38 | 0 | 4.946 | completed without crash |
| `langchain-ai/langgraph-supervisor-py` | 4 | 835 | 0 | 0 | 0.082 | completed without crash |
| `langchain-ai/langgraph-swarm-py` | 8 | 710 | 2 | 0 | 0.073 | completed without crash |
| `crewAIInc/crewAI-examples` | 116 | 5,489 | 16 | 0 | 0.345 | completed without crash |
| `microsoft/autogen` (`python/samples`) | 59 | 5,313 | 3 | 0 | 0.364 | completed without crash |

Rule distributions were identical to the prior recorded run for the five
repositories: LangGraph AG003: 13, AG004: 5, AG007: 13, AG010: 5, AG020: 1,
AG023: 1; supervisor none; swarm AG003: 1 and AG010: 1; CrewAI AG003: 14 and
AG010: 2; AutoGen AG011: 3. Manual spot checks of the fresh LangGraph results
found timeout/model findings in expected example and graph files, cycle and
conditional-route findings in graph examples, and one prompt-flow finding in
the prebuilt agent code. These are plausibility checks, not a measured
precision study.
