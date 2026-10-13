# CI integration

## GitHub Action

AgentGuard provides a reusable composite action at
`.github/actions/agentguard/action.yml`. It runs a SARIF scan and writes the
report to `agentguard.sarif` by default.

```yaml
name: AgentGuard

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/agentguard
        with:
          path: .
          fail-on: error
          output: agentguard.sarif
      - name: Upload AgentGuard SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: agentguard.sarif
```

The upload step uses `if: always()` so a failed scan still uploads its
findings. The action supports `path`, `select`, `ignore`, `fail-on`, `output`,
and `python-version` inputs.

The action invokes the published AgentGuard package through `uvx`. For a
repository checkout or a pinned release, replace the command with the desired
package source and keep the version pinned in the workflow.

## Local SARIF generation

```bash
agentguard scan . --format sarif --output agentguard.sarif
```

SARIF output is deterministic and includes rule IDs, source locations, finding
severity, confidence, remediation guidance, related locations, and stable
fingerprints.

## Pre-commit

Add the repository hook to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/<owner>/agentguard
    rev: <version>
    hooks:
      - id: agentguard
```

The hook receives staged Python files and runs:

```text
agentguard scan --fail-on error <staged-python-files>
```

Use hook `args` to change the threshold or select rules, for example:

```yaml
      - id: agentguard
        args: [--fail-on, warning, --ignore, AG023]
```
