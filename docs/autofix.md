# Autofix

AgentGuard never edits source during a normal scan. Safe source changes require
an explicit flag.

## Preview changes

```bash
agentguard scan examples/ --fix-dry-run --fail-on never
```

This prints deterministic unified diffs and leaves every file unchanged.

## Apply changes

```bash
agentguard scan src/ --fix --fail-on never
```

The current safe fixes are:

| Rule | Fix | Default |
|---|---|---|
| AG003 | Add `timeout=` to supported known calls | `30` seconds |
| AG004 | Add `recursion_limit` to supported LangGraph invocation config | `25` |
| AG010 | Replace a literal model alias using an explicit mapping | no implicit mapping |

AG010 mappings must be supplied in configuration. AgentGuard never guesses a
provider revision:

```toml
[tool.agentguard.fix.model]
"gpt-4" = "gpt-4-2024-08-06"
"latest" = "gpt-4o-2024-08-06"
```

Dynamic calls, unresolved framework shapes, existing keyword arguments, and
unsupported source forms are skipped. Fixes use LibCST so comments and source
formatting are preserved. A parse error prevents a file from being modified.

## CI guidance

Use `--fix-dry-run` in review or diagnostics. Applying fixes in CI should be an
explicit workflow step with the resulting diff reviewed before commit.
