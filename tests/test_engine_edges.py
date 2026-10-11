"""Behavioral edge cases for file discovery and the scan pipeline."""

import ast
from pathlib import Path

import pytest

from agentguard.engine.discovery import discover_python_files
from agentguard.engine.parser import ParsedModule, ParseError, parse_file, parse_source
from agentguard.engine.runner import run_scan
from agentguard.engine.suppression import parse_suppressions
from agentguard.findings import Confidence, Finding, Location, Severity


def test_discovery_distinguishes_anchored_and_recursive_patterns(
    tmp_path: Path,
) -> None:
    (tmp_path / ".gitignore").write_text(
        "/root_only.py\npkg/*.py\n**/generated.py\n", encoding="utf-8"
    )
    package = tmp_path / "pkg"
    nested = package / "nested"
    nested.mkdir(parents=True)
    for relative in (
        "root_only.py",
        "generated.py",
        "pkg/direct.py",
        "pkg/nested/root_only.py",
        "pkg/nested/generated.py",
    ):
        (tmp_path / relative).write_text("pass\n", encoding="utf-8")

    assert discover_python_files([tmp_path]) == [nested / "root_only.py"]


def test_nested_ignore_can_reinclude_files_but_not_ignored_parents(
    tmp_path: Path,
) -> None:
    (tmp_path / ".gitignore").write_text("*.py\nblocked/\n", encoding="utf-8")
    package = tmp_path / "pkg"
    package.mkdir()
    (package / ".gitignore").write_text("!keep.py\n", encoding="utf-8")
    keep = package / "keep.py"
    keep.write_text("pass\n", encoding="utf-8")
    (package / "skip.py").write_text("pass\n", encoding="utf-8")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / ".gitignore").write_text("!keep.py\n", encoding="utf-8")
    (blocked / "keep.py").write_text("pass\n", encoding="utf-8")

    assert discover_python_files([tmp_path, keep]) == [keep]
    assert discover_python_files([blocked / "keep.py"], root=tmp_path) == []


def test_discovery_rejects_missing_and_outside_root_paths(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_python_files([tmp_path / "missing.py"])
    subdirectory = tmp_path / "subdirectory"
    subdirectory.mkdir()
    with pytest.raises(ValueError, match="outside root"):
        discover_python_files([tmp_path], root=subdirectory)


def test_parser_honors_python_encoding_cookie_without_executing(tmp_path: Path) -> None:
    path = tmp_path / "encoded.py"
    path.write_bytes(b"# coding: latin-1\nmessage = 'caf\xe9'\nraise RuntimeError()\n")

    parsed = parse_file(path)

    assert "caf\u00e9" in parsed.source
    assert isinstance(parsed.tree.body[-1], ast.Raise)


def test_parser_converts_encoding_and_null_byte_errors(tmp_path: Path) -> None:
    path = tmp_path / "invalid.py"
    path.write_bytes(b"\xff")
    with pytest.raises(ParseError, match="encoding"):
        parse_file(path)
    with pytest.raises(ParseError):
        parse_source("value = '\x00'", path)


def test_suppression_text_in_strings_is_not_a_directive() -> None:
    source = (
        'prompt = """\n'
        "# agentguard: ignore-file[AG003]\n"
        '"""\n'
        'value = "# agentguard: ignore"\n'
    )
    suppressions = parse_suppressions(source)

    assert not suppressions.is_suppressed("AG003", 99)
    assert not suppressions.is_suppressed("AG003", 4)


@pytest.mark.parametrize(
    "directive",
    ["ignore[]", "ignore[AG003", "ignore[INVALID]", "ignored", "ignore-file[AG003]"],
)
def test_malformed_or_late_file_directives_do_not_suppress(directive: str) -> None:
    source = "\n" * 10 + f"call()  # agentguard: {directive}\n"

    assert not parse_suppressions(source).is_suppressed("AG003", 11)


def test_file_suppression_last_valid_line_and_multiple_rule_ids() -> None:
    source = "\n" * 9 + "# agentguard:\tignore-file[ AG001, AG003 ] reason: tested\n"
    suppressions = parse_suppressions(source)

    assert suppressions.is_suppressed("AG001", 99)
    assert suppressions.is_suppressed("AG003", 99)
    assert not suppressions.is_suppressed("AG002", 99)


def _report_call(parsed: ParsedModule) -> list[Finding]:
    return [
        Finding(
            rule_id="AG003",
            severity=Severity.WARNING,
            confidence=Confidence.HIGH,
            message="Call lacks a timeout",
            why="A connection could hang",
            suggestion="Set a timeout",
            loc=Location(Path(parsed.path.name), 1, 0, 1, 6),
        )
    ]


def test_parallel_scan_matches_sequential_results(tmp_path: Path) -> None:
    (tmp_path / "b.py").write_text("call()\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("call()\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("if:\n", encoding="utf-8")
    (tmp_path / "suppressed.py").write_text(
        "call()  # agentguard: ignore[AG003]\n", encoding="utf-8"
    )

    sequential = run_scan([tmp_path], _report_call)
    parallel = run_scan([tmp_path], _report_call, jobs=2)

    assert parallel == sequential
    assert [finding.loc.file for finding in parallel.findings] == [
        Path("a.py"),
        Path("b.py"),
    ]
    assert [error.path.name for error in parallel.parse_errors] == ["bad.py"]


def test_runner_rejects_invalid_job_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="jobs"):
        run_scan([tmp_path], jobs=0)
