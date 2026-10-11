"""Shared fixture expectation parsing for rule tests."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from agentguard.findings import Finding

_EXPECTATION = re.compile(
    r"#\s*expect:\s*(?P<rules>AG[0-9]{3}(?:\s*,\s*AG[0-9]{3})*)\s*$"
)


@dataclass(frozen=True)
class FixtureExpectation:
    """Expected rule IDs attached to exact source lines."""

    path: Path
    findings: tuple[tuple[int, str], ...]


def read_expectations(path: Path) -> FixtureExpectation:
    """Read exact-line ``# expect: AGxxx`` markers from a fixture."""
    expected: list[tuple[int, str]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        marker = _EXPECTATION.search(line)
        if marker is not None:
            expected.extend(
                (line_number, rule.strip().upper())
                for rule in marker.group("rules").split(",")
            )
    return FixtureExpectation(path, tuple(expected))


def assert_fixture_findings(
    path: Path,
    findings: Iterable[Finding],
) -> None:
    """Assert findings exactly match the markers in one fixture."""
    expected = read_expectations(path).findings
    actual = tuple(
        sorted((finding.loc.line, finding.rule_id.upper()) for finding in findings)
    )
    assert actual == tuple(sorted(expected)), (
        f"{path}: expected {expected!r}, received {actual!r}"
    )


def fixture_paths(root: Path, rule_id: str) -> tuple[Path, ...]:
    """Return sorted fixtures for one rule ID."""
    directory = root / rule_id.lower()
    return tuple(sorted(directory.glob("*.py"), key=lambda path: path.name))
