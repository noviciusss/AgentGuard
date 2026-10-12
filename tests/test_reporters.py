"""Reporter output tests."""

from pathlib import Path

from agentguard.findings import Confidence, Finding, Location, Severity
from agentguard.reporters import JsonReporter, TextReporter


def finding() -> Finding:
    return Finding(
        rule_id="AG003",
        severity=Severity.WARNING,
        confidence=Confidence.HIGH,
        message="request has no timeout",
        why="the connection can hang",
        suggestion="pass timeout=30",
        loc=Location(Path("agent.py"), 4, 8, 4, 25),
    )


def test_text_reporter_snapshot() -> None:
    assert TextReporter().render([finding()]) == (
        "agent.py:4:8  AG003  warning  [high]  request has no timeout\n"
        "  why: the connection can hang\n"
        "  fix: pass timeout=30"
    )


def test_json_reporter_snapshot() -> None:
    assert (
        JsonReporter().render([finding()])
        == """[
  {
    "confidence": "high",
    "fingerprint": "",
    "location": {
      "col": 8,
      "end_col": 25,
      "end_line": 4,
      "file": "agent.py",
      "line": 4
    },
    "message": "request has no timeout",
    "related": [],
    "rule_id": "AG003",
    "severity": "warning",
    "suggestion": "pass timeout=30",
    "why": "the connection can hang"
  }
]
"""
    )
