"""Validation tests for Phase 4 CI assets."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_github_action_declares_sarif_inputs_and_runner() -> None:
    action = (ROOT / ".github/actions/agentguard/action.yml").read_text(
        encoding="utf-8"
    )

    assert "name: AgentGuard scan" in action
    assert 'default: "agentguard.sarif"' in action
    assert "--format sarif" in action
    assert "uvx --python" in action
    assert "using: composite" in action


def test_ci_documentation_contains_upload_example() -> None:
    documentation = (ROOT / "docs/ci.md").read_text(encoding="utf-8")

    assert "github/codeql-action/upload-sarif@v3" in documentation
    assert "security-events: write" in documentation
    assert "agentguard scan . --format sarif" in documentation


def test_pre_commit_hook_scans_python_files() -> None:
    hook = (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")

    assert "id: agentguard" in hook
    assert "entry: agentguard scan --fail-on error" in hook
    assert "language: python" in hook
    assert "types: [python]" in hook
    assert "pass_filenames: true" in hook


def test_ci_documentation_contains_pre_commit_example() -> None:
    documentation = (ROOT / "docs/ci.md").read_text(encoding="utf-8")

    assert ".pre-commit-config.yaml" in documentation
    assert "agentguard scan --fail-on error" in documentation


def test_autofix_documentation_requires_explicit_flags_and_mapping() -> None:
    documentation = (ROOT / "docs/autofix.md").read_text(encoding="utf-8")

    assert "--fix-dry-run" in documentation
    assert "--fix" in documentation
    assert "[tool.agentguard.fix.model]" in documentation
    assert "never guesses" in documentation
