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
The repository currently has no dedicated benchmark harness for isolating a
10,000-line cold-start timing sample; that measurement should be added before
using the performance budget as a release regression gate.
