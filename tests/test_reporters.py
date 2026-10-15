"""Reporter output tests."""

from dataclasses import replace
from pathlib import Path

from agentguard.findings import Confidence, Finding, Location, Severity
from agentguard.reporters import JsonReporter, SarifReporter, TextReporter


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


def test_sarif_reporter_snapshot() -> None:
    assert (
        SarifReporter().render([finding()])
        == """{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "runs": [
    {
      "results": [
        {
          "level": "warning",
          "locations": [
            {
              "message": {
                "text": "request has no timeout"
              },
              "physicalLocation": {
                "artifactLocation": {
                  "uri": "agent.py"
                },
                "region": {
                  "endColumn": 26,
                  "endLine": 4,
                  "startColumn": 9,
                  "startLine": 4
                }
              }
            }
          ],
          "message": {
            "text": "request has no timeout"
          },
          "properties": {
            "confidence": "high",
            "suggestion": "pass timeout=30",
            "why": "the connection can hang"
          },
          "ruleId": "AG003"
        }
      ],
      "tool": {
        "driver": {
          "informationUri": "https://github.com/agentguard/agentguard",
          "name": "AgentGuard",
          "rules": [
            {
              "id": "AG003",
              "shortDescription": {
                "text": "AG003"
              }
            }
          ],
          "version": "0.1.0"
        }
      }
    }
  ],
  "version": "2.1.0"
}
"""
    )


def test_sarif_omits_empty_fingerprint() -> None:
    rendered = SarifReporter().render([finding()])

    assert '"fingerprints"' not in rendered


def test_reporters_preserve_finding_metadata() -> None:
    tagged = replace(finding(), tags=("CWE-400",), metadata=(("owasp", "LLM10"),))

    text = TextReporter().render([tagged])
    json_output = JsonReporter().render([tagged])
    sarif = SarifReporter().render([tagged])

    assert "tags: CWE-400" in text
    assert "metadata: owasp=LLM10" in text
    assert '"metadata": {' in json_output
    assert '"owasp": "LLM10"' in json_output
    assert '"metadata": {' in sarif
    assert '"owasp": "LLM10"' in sarif
