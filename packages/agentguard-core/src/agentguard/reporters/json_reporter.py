"""Deterministic JSON reporter."""

import json
from collections.abc import Iterable
from typing import ClassVar

from agentguard.findings import Finding, sort_findings
from agentguard.reporters.base import Reporter


class JsonReporter(Reporter):
    """Render findings as a stable JSON array."""

    format_name: ClassVar[str] = "json"

    def render(self, findings: Iterable[Finding]) -> str:
        """Return a pretty-printed JSON array with stable key ordering."""
        payload = [_serialize(finding) for finding in sort_findings(list(findings))]
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _serialize(finding: Finding) -> dict[str, object]:
    location = finding.loc
    payload: dict[str, object] = {
        "confidence": finding.confidence.value,
        "fingerprint": finding.fingerprint,
        "location": {
            "col": location.col,
            "end_col": location.end_col,
            "end_line": location.end_line,
            "file": location.file.as_posix(),
            "line": location.line,
        },
        "message": finding.message,
        "related": [
            {
                "col": related.col,
                "end_col": related.end_col,
                "end_line": related.end_line,
                "file": related.file.as_posix(),
                "line": related.line,
            }
            for related in finding.related
        ],
        "rule_id": finding.rule_id,
        "severity": finding.severity.value,
        "suggestion": finding.suggestion,
        "why": finding.why,
    }
    if finding.tags:
        payload["tags"] = list(finding.tags)
    if finding.metadata:
        payload["metadata"] = dict(finding.metadata)
    return payload
