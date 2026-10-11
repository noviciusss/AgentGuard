"""Tests for the marker-based rule fixture runner."""

from pathlib import Path

import pytest

from agentguard.findings import Confidence, Finding, Location, Severity
from tests.fixture_support import (
    assert_fixture_findings,
    fixture_paths,
    read_expectations,
)


def test_expectation_parser_keeps_exact_lines(tmp_path: Path) -> None:
    fixture = tmp_path / "bad_example.py"
    fixture.write_text(
        "first()  # expect: AG001\nsecond()  # expect: AG002, AG003\nclean()\n",
        encoding="utf-8",
    )

    assert read_expectations(fixture).findings == (
        (1, "AG001"),
        (2, "AG002"),
        (2, "AG003"),
    )


def test_fixture_runner_requires_exact_rule_and_line_matches(tmp_path: Path) -> None:
    fixture = tmp_path / "bad_example.py"
    fixture.write_text("first()  # expect: AG001\n", encoding="utf-8")
    expected = Finding(
        rule_id="AG001",
        severity=Severity.WARNING,
        confidence=Confidence.HIGH,
        message="message",
        why="why",
        suggestion="suggestion",
        loc=Location(fixture, 1, 0, 1, 5),
    )

    assert_fixture_findings(fixture, [expected])
    with pytest.raises(AssertionError):
        assert_fixture_findings(
            fixture,
            [
                Finding(
                    rule_id="AG001",
                    severity=Severity.WARNING,
                    confidence=Confidence.HIGH,
                    message="message",
                    why="why",
                    suggestion="suggestion",
                    loc=Location(fixture, 2, 0, 2, 5),
                )
            ],
        )


def test_fixture_paths_are_sorted_and_rule_scoped(tmp_path: Path) -> None:
    directory = tmp_path / "ag001"
    directory.mkdir()
    for name in ("edge_case.py", "bad_case.py", "good_case.py"):
        (directory / name).write_text("pass\n", encoding="utf-8")

    assert [path.name for path in fixture_paths(tmp_path, "AG001")] == [
        "bad_case.py",
        "edge_case.py",
        "good_case.py",
    ]
