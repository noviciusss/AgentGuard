# AGENTS.md

Instructions for AI coding agents working on **AgentGuard**.
Read this file and `SPEC.md` at the start of every session. `SPEC.md` is the source of truth for architecture, rules, and phases. This file is the source of truth for how you work.

## Project

AgentGuard is a static analysis CLI and plugin platform for AI agentic codebases (LangGraph, CrewAI, AutoGen, plain Python agents). It detects reliability, cost, and security bugs before the agent runs.

- Language: Python 3.10+
- Owner: Samarth (solo developer, student). Treat the owner as technically capable; be direct and concise.
- **The repo starts empty.** No code exists yet. Build from Phase 0 of `SPEC.md`.
- Current phase: **check `STATUS.md`**. If it does not exist, create it and start at Phase 0, Step 0.1.

## Environment (WSL)

This project runs in WSL Ubuntu, possibly under `/mnt/d/...` (a Windows drive). Quirks to handle:

- Set `UV_LINK_MODE=copy` (hardlinks fail across filesystems). Put it in the Makefile and `README` setup notes.
- Keep the virtualenv off the Windows drive for speed: use `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/agentguard"`. Document this in the README and export it in the Makefile.
- Use LF line endings. Add a `.gitattributes` with `* text=auto eol=lf`.
- Do not use Windows paths in code or docs. Use `pathlib` and POSIX paths.
- If a tool is missing (`make`, `uv`, `git`), tell the owner the install command instead of working around it.

## Workflow (mandatory)

1. **Plan first, then wait.** For any task beyond a trivial fix, write a plan and stop. The plan lists: files to create or change, approach, tests to add, risks. Do **not** edit files until the owner replies with approval.
2. **One unit per task.** A unit is one rule, one adapter, one CLI command, or one refactor step. Do not bundle units.
3. **Build, verify, stop.** After implementing, run `make check` (below). Fix failures. Then stop and give a summary: what changed, what was tested, what remains, anything you are unsure about.
4. **Update `STATUS.md`** at the end of every unit: phase, what is done, what is next, known issues.
5. **Never expand scope.** Touch only files relevant to the task. If you notice unrelated problems, list them in the summary; do not fix them.

## Commands

Use `uv` for environments and dependencies.

```
uv sync --all-extras          # install everything
make check                    # lint + typecheck + tests (run before declaring done)
make test                     # pytest only
make lint                     # ruff check + ruff format --check
make fmt                      # ruff format + ruff check --fix
make types                    # mypy --strict
```

`make check` must pass with zero errors and zero warnings before any unit is considered done. If a command above does not exist yet, creating it is the first task of Phase 2.

## Tooling (decided)

| Purpose | Tool |
|---|---|
| Env / deps | `uv` |
| Build backend | `hatchling` |
| Tests | `pytest`, `hypothesis`, snapshot tests for reporters |
| Lint + format | `ruff` |
| Types | `mypy --strict` |
| CLI | `typer` + `rich` |
| Plugins | `pluggy` + entry points (group `agentguard`) |
| Config models | `pydantic` v2 |
| Autofix | `libcst` |

Do not add dependencies without asking. If a new dependency is justified, put it in the plan with the reason.

## Code standards

- Fully typed. No `Any` unless justified in a comment.
- Small functions, clear names, docstrings on public APIs.
- Findings are deterministic: same input gives same output, sorted, stable fingerprints.
- No network calls in core. LLM-related features live in optional plugins, off by default.
- No print statements in library code; use `rich` in CLI layer only.
- No broad `except Exception: pass`. Handle or re-raise with context.
- Prefer the standard library for simple tasks.

## Architecture rules

- Rules operate on the **Agent IR**, never on raw framework syntax. Framework-specific logic belongs in adapters.
- Rules are plugins implementing the `Rule` base class. Core ships built-in rules through the same mechanism third parties use.
- Adapters translate framework code into IR. They never emit findings.
- Reporters consume findings only. They never re-analyze code.
- Do not let the engine import from adapters or rules directly; go through the plugin manager.

## Testing rules

- Every rule needs fixtures under `tests/fixtures/<rule_id>/`: `bad_*.py` (must trigger), `good_*.py` (must not), and at least one edge case. Mark expected findings with `# expect: AGxxx` on the exact line.
- Every new reporter needs a snapshot test.
- Every IR builder change needs a unit test.
- **Never modify an existing test to make it pass.** If a test fails, fix the code. If you believe a test is wrong, say so in your summary and wait for approval.
- Never delete or skip tests to get green. Never use `# type: ignore` or `# noqa` without a one-line reason.

## Rule documentation

Each rule needs `docs/rules/<ID>.md` containing: what it detects, why it matters, bad example, good example, how to fix, how to suppress. `agentguard explain <ID>` reads this file.

## Git

- Work on a feature branch, never directly on `main`.
- Commit after each green unit with a conventional message (`feat(rules): add AG004 unbounded agent loop`).
- Do not commit generated files, caches, or secrets.
- Never force-push, rewrite history, or run destructive git commands without explicit approval.

## Safety

- Do not run `rm -rf`, delete directories, or modify files outside this repository without approval.
- Never print or commit secrets. Read credentials from environment variables only.
- Do not install global packages or modify system configuration.
- When fixture code needs to look dangerous (shell calls, eval), keep it inert: it is parsed, never executed.

## Verifying framework APIs

LangGraph, CrewAI, and AutoGen change fast. Do not rely on memory for their APIs. Check the installed version's source or current docs before writing an adapter, and pin the tested version in the plan. If you cannot verify something, say so rather than guessing.

## Summary format (end of every unit)

```
Done: <what was implemented>
Tested: <commands run and results>
Changed: <files>
Not done / next: <remaining work>
Concerns: <uncertainties, risks, things to review closely>
```

## What not to do

- Do not start a new phase without approval.
- Do not refactor code that is unrelated to the current task.
- Do not add features not in `SPEC.md`; suggest them in the summary instead.
- Do not report "done" with failing checks.
- Do not guess when requirements are ambiguous. Ask one specific question.
