"""CLI command tests."""

from pathlib import Path

from typer.testing import CliRunner

from agentguard.cli import app
from agentguard.cli.scan import analyze_project
from agentguard.config import AgentGuardConfig

runner = CliRunner()


def test_rules_command_lists_phase_one_rules() -> None:
    result = runner.invoke(app, ["rules"])

    assert result.exit_code == 0
    assert "AG001" in result.stdout
    assert "AG002" in result.stdout
    assert "AG003" in result.stdout


def test_explain_command_renders_rule_documentation() -> None:
    result = runner.invoke(app, ["explain", "ag001"])

    assert result.exit_code == 0
    assert result.stdout.startswith("# AG001: unbounded-retries")
    assert "How to fix" in result.stdout


def test_explain_unknown_rule_returns_usage_error() -> None:
    result = runner.invoke(app, ["explain", "AG999"])

    assert result.exit_code == 2
    assert "unknown rule: AG999" in result.stderr


def test_scan_json_and_fail_on_never(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    source.write_text(
        'import requests\nrequests.get("https://example.com")\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "scan",
            str(source),
            "--format",
            "json",
            "--fail-on",
            "never",
        ],
    )

    assert result.exit_code == 0
    assert '"rule_id": "AG003"' in result.stdout


def test_scan_sarif_output(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    source.write_text(
        'import requests\nrequests.get("https://example.com")\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["scan", str(source), "--format", "sarif", "--fail-on", "never"],
    )

    assert result.exit_code == 0
    assert '"version": "2.1.0"' in result.stdout
    assert '"ruleId": "AG003"' in result.stdout


def test_scan_fix_dry_run_prints_diff_without_writing(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    original = 'import requests\nrequests.get("https://example.com")\n'
    source.write_text(original, encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "scan",
            str(source),
            "--fix-dry-run",
            "--fix-timeout",
            "12",
            "--fail-on",
            "never",
        ],
    )

    assert result.exit_code == 0
    assert '+requests.get("https://example.com", timeout = 12)' in result.stdout
    assert source.read_text(encoding="utf-8") == original


def test_scan_fix_applies_supported_ag003_transform(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    source.write_text(
        'import requests\nrequests.get("https://example.com")\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["scan", str(source), "--fix", "--fail-on", "never"],
    )

    assert result.exit_code == 0
    assert "timeout = 30" in source.read_text(encoding="utf-8")


def test_scan_fix_dry_run_applies_supported_ag004_transform(tmp_path: Path) -> None:
    source = tmp_path / "graph.py"
    original = """from langgraph.graph import START, StateGraph

def node(state):
    return state

builder = StateGraph(dict)
builder.add_node("node", node)
builder.add_edge(START, "node")
builder.add_edge("node", "node")
graph = builder.compile()
graph.invoke({})
"""
    source.write_text(original, encoding="utf-8")

    result = runner.invoke(
        app,
        ["scan", str(source), "--fix-dry-run", "--fail-on", "never"],
    )

    assert result.exit_code == 0
    assert '"recursion_limit": 25' in result.stdout
    assert source.read_text(encoding="utf-8") == original


def test_scan_bad_config_returns_usage_error(tmp_path: Path) -> None:
    (tmp_path / "agentguard.toml").write_text(
        "unknown = true\n",
        encoding="utf-8",
    )
    source = tmp_path / "agent.py"
    source.write_text("pass\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(source)])

    assert result.exit_code == 2


def test_scan_text_fails_at_warning_threshold(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    source.write_text(
        'import requests\nrequests.get("https://example.com")\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["scan", str(source), "--fail-on", "warning"],
    )

    assert result.exit_code == 1
    assert "AG003" in result.stdout
    assert "request" in result.stdout


def test_scan_select_and_ignore_filter_findings(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    source.write_text(
        'import requests\nrequests.get("https://example.com")\n',
        encoding="utf-8",
    )

    selected = runner.invoke(
        app,
        ["scan", str(source), "--select", "AG001", "--fail-on", "warning"],
    )
    ignored = runner.invoke(
        app,
        ["scan", str(source), "--ignore", "AG003", "--fail-on", "warning"],
    )

    assert selected.exit_code == 0
    assert selected.stdout == ""
    assert ignored.exit_code == 0
    assert ignored.stdout == ""


def test_scan_skips_unparseable_files_with_a_warning(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.py"
    invalid.write_text("def broken(:\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(invalid)])

    assert result.exit_code == 0
    assert "warning: skipped" in result.stderr


def test_analyze_project_uses_multiple_workers_deterministically(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    source = 'import requests\nrequests.get("https://example.com")\n'
    first.write_text(source, encoding="utf-8")
    second.write_text(source, encoding="utf-8")

    sequential = analyze_project([tmp_path], AgentGuardConfig(jobs=1), root=tmp_path)
    parallel = analyze_project([tmp_path], AgentGuardConfig(jobs=2), root=tmp_path)

    assert parallel.findings == sequential.findings
    assert parallel.scanned_files == sequential.scanned_files
    assert parallel.parse_errors == sequential.parse_errors


def test_bundled_clean_example_has_no_findings() -> None:
    result = runner.invoke(
        app,
        ["scan", "examples/clean_agent", "--format", "json", "--fail-on", "never"],
    )

    assert result.exit_code == 0
    assert result.stdout == "[]\n"


def test_bundled_issue_examples_expose_phase_one_rules() -> None:
    result = runner.invoke(
        app,
        ["scan", "examples/", "--format", "json", "--fail-on", "never"],
    )

    assert result.exit_code == 0
    assert '"rule_id": "AG001"' in result.stdout
    assert '"rule_id": "AG002"' in result.stdout
    assert '"rule_id": "AG003"' in result.stdout


def test_baseline_create_and_scan_filter(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    source.write_text(
        'import requests\nrequests.get("https://example.com")\n',
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"

    created = runner.invoke(
        app,
        ["baseline", "create", str(source), "--output", str(baseline)],
    )
    scanned = runner.invoke(
        app,
        [
            "scan",
            str(source),
            "--baseline",
            str(baseline),
            "--format",
            "json",
            "--fail-on",
            "never",
        ],
    )

    assert created.exit_code == 0
    assert baseline.is_file()
    assert scanned.exit_code == 0
    assert scanned.stdout == "[]\n"
