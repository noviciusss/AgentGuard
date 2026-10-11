"""Unit tests for discovery, parsing, suppression, and scan orchestration."""

from pathlib import Path

import pytest

from agentguard.engine.discovery import discover_python_files
from agentguard.engine.parser import ParsedModule, ParseError, parse_source
from agentguard.engine.runner import run_scan
from agentguard.engine.suppression import parse_suppressions
from agentguard.findings import Confidence, Finding, Location, Severity


def test_discovery_honors_gitignore_and_explicit_excludes(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("ignored.py\nignored_dir/\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "ignored.py").write_text("pass\n", encoding="utf-8")
    ignored_dir = tmp_path / "ignored_dir"
    ignored_dir.mkdir()
    (ignored_dir / "nested.py").write_text("pass\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("pass\n", encoding="utf-8")

    files = discover_python_files([tmp_path], excludes=["tests/"])

    assert files == [tmp_path / "app.py"]


def test_parser_preserves_source_and_reports_syntax_errors(tmp_path: Path) -> None:
    parsed = parse_source("value = 1\n", tmp_path / "agent.py")

    assert parsed.path == tmp_path / "agent.py"
    assert parsed.source_lines == ("value = 1",)
    assert parsed.lines == parsed.source_lines
    assert parsed.tree.body[0].__class__.__name__ == "Assign"

    with pytest.raises(ParseError) as error:
        parse_source("if:\n", tmp_path / "broken.py")
    assert error.value.path == tmp_path / "broken.py"
    assert error.value.line == 1


def test_suppressions_support_line_and_file_directives() -> None:
    suppressions = parse_suppressions(
        "# agentguard: ignore-file[AG003]\n"
        "requests.get(url)  # agentguard: ignore[AG001] reason: safe\n"
        "dangerous()  # agentguard: ignore\n"
    )

    assert suppressions.is_suppressed("AG003", 99)
    assert suppressions.is_suppressed("AG001", 2)
    assert suppressions.is_suppressed("AG999", 3)
    assert not suppressions.is_suppressed("AG001", 4)


def analyze_source(parsed: ParsedModule) -> list[Finding]:
    """Return a finding at the first source line for runner testing."""
    source_path = parsed.path
    return [
        Finding(
            rule_id="AG003",
            severity=Severity.WARNING,
            confidence=Confidence.HIGH,
            message="missing timeout",
            why="a connection may hang",
            suggestion="set a timeout",
            loc=Location(source_path, 1, 0, 1, 1),
        )
    ]


def test_runner_skips_parse_errors_and_applies_suppressions(tmp_path: Path) -> None:
    clean = tmp_path / "clean.py"
    clean.write_text("pass\n", encoding="utf-8")
    suppressed = tmp_path / "suppressed.py"
    suppressed.write_text("# agentguard: ignore-file[AG003]\npass\n", encoding="utf-8")
    broken = tmp_path / "broken.py"
    broken.write_text("if:\n", encoding="utf-8")

    result = run_scan([tmp_path], analyze_source, root=tmp_path)

    assert result.scanned_files == (broken, clean, suppressed)
    assert result.findings == (
        Finding(
            rule_id="AG003",
            severity=Severity.WARNING,
            confidence=Confidence.HIGH,
            message="missing timeout",
            why="a connection may hang",
            suggestion="set a timeout",
            loc=Location(clean, 1, 0, 1, 1),
        ),
    )
    assert len(result.parse_errors) == 1
    assert result.parse_errors[0].path == broken
