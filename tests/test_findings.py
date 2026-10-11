"""Unit tests for findings and deterministic fingerprints."""

import hashlib
from pathlib import Path

from agentguard.engine.fingerprint import fingerprint
from agentguard.findings import (
    Confidence,
    Finding,
    Location,
    Severity,
    sort_findings,
)


def location(file: str, line: int, col: int = 0) -> Location:
    """Build a concise test location."""
    return Location(Path(file), line, col, line, col + 1)


def make_finding(rule_id: str, file: str, line: int) -> Finding:
    """Build a concise test finding."""
    return Finding(
        rule_id=rule_id,
        severity=Severity.WARNING,
        confidence=Confidence.HIGH,
        message="message",
        why="why",
        suggestion="suggestion",
        loc=location(file, line),
    )


def test_finding_defaults_and_enum_values() -> None:
    finding = make_finding("AG003", "src/agent.py", 4)

    assert finding.related == ()
    assert finding.fingerprint == ""
    assert finding.fix is None
    assert Severity.ERROR.value == "error"
    assert Confidence.LOW.value == "low"


def test_findings_sort_by_file_location_then_rule() -> None:
    findings = [
        make_finding("AG003", "b.py", 2),
        make_finding("AG001", "a.py", 4),
        make_finding("AG001", "a.py", 2),
        make_finding("AG002", "a.py", 2),
    ]

    ordered = sort_findings(findings)

    assert [
        (item.loc.file.as_posix(), item.loc.line, item.rule_id) for item in ordered
    ] == [
        ("a.py", 2, "AG001"),
        ("a.py", 2, "AG002"),
        ("a.py", 4, "AG001"),
        ("b.py", 2, "AG003"),
    ]


def test_fingerprint_normalizes_whitespace_and_ignores_line_numbers() -> None:
    first = fingerprint("AG003", Path("src/agent.py"), "requests.get(url)")
    second = fingerprint("AG003", Path("src/agent.py"), " requests.get(url) \n ")

    assert first == second
    assert (
        first == hashlib.sha256(b"AG003src/agent.pyrequests.get(url)").hexdigest()[:16]
    )
    assert first != fingerprint("AG001", Path("src/agent.py"), "requests.get(url)")
    assert first != fingerprint("AG003", Path("other.py"), "requests.get(url)")
    assert first != fingerprint("AG003", Path("src/agent.py"), "requests.post(url)")
