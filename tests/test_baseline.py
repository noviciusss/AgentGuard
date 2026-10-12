"""Tests for stable finding baselines."""

from pathlib import Path

import pytest

from agentguard.baseline import (
    BaselineError,
    create_baseline,
    filter_baselined,
    load_baseline,
    save_baseline,
)
from agentguard.findings import Confidence, Finding, Location, Severity


def finding(fingerprint: str) -> Finding:
    return Finding(
        rule_id="AG001",
        severity=Severity.WARNING,
        confidence=Confidence.HIGH,
        message="message",
        why="why",
        suggestion="fix",
        loc=Location(Path("agent.py"), 1, 0, 1, 1),
        fingerprint=fingerprint,
    )


def test_baseline_round_trips_sorted_fingerprints(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    baseline = create_baseline([finding("b"), finding("a"), finding("")])

    save_baseline(path, baseline)

    assert load_baseline(path) == baseline
    assert '"findings": [\n    "a",\n    "b"' in path.read_text(encoding="utf-8")


def test_filter_baselined_keeps_new_findings() -> None:
    old = finding("old")
    new = finding("new")

    assert filter_baselined([old, new], create_baseline([old])) == [new]


def test_invalid_baseline_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"version": 2, "findings": []}', encoding="utf-8")

    with pytest.raises(BaselineError, match="unsupported baseline"):
        load_baseline(path)
