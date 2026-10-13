"""Deterministic SARIF 2.1.0 reporter."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import ClassVar

from agentguard import __version__
from agentguard.findings import Finding, Location, Severity, sort_findings
from agentguard.reporters.base import Reporter


class SarifReporter(Reporter):
    """Render findings as a SARIF 2.1.0 log for code-scanning tools."""

    format_name: ClassVar[str] = "sarif"

    def render(self, findings: Iterable[Finding]) -> str:
        """Return a stable SARIF document containing the supplied findings."""
        ordered = sort_findings(list(findings))
        rules = _rules(ordered)
        results = [_result(finding, index) for index, finding in enumerate(ordered)]
        document = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "results": results,
                    "tool": {
                        "driver": {
                            "informationUri": "https://github.com/agentguard/agentguard",
                            "name": "AgentGuard",
                            "rules": rules,
                            "version": __version__,
                        }
                    },
                }
            ],
            "version": "2.1.0",
        }
        return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _rules(findings: list[Finding]) -> list[dict[str, object]]:
    return [
        {
            "id": rule_id,
            "shortDescription": {"text": rule_id},
        }
        for rule_id in sorted({finding.rule_id for finding in findings})
    ]


def _result(finding: Finding, index: int) -> dict[str, object]:
    properties: dict[str, object] = {
        "confidence": finding.confidence.value,
        "suggestion": finding.suggestion,
        "why": finding.why,
    }
    if finding.metadata:
        properties["metadata"] = dict(finding.metadata)
    if finding.tags:
        properties["tags"] = list(finding.tags)
    result: dict[str, object] = {
        "level": _level(finding.severity),
        "locations": [_location(finding)],
        "message": {"text": finding.message},
        "ruleId": finding.rule_id,
        "properties": properties,
    }
    if finding.fingerprint:
        result["fingerprints"] = {"agentguard/v1": finding.fingerprint}
    if finding.related:
        result["relatedLocations"] = [
            {"id": index, "physicalLocation": _physical_location(location)}
            for index, location in enumerate(finding.related)
        ]
    return result


def _location(finding: Finding) -> dict[str, object]:
    return {
        "physicalLocation": _physical_location(finding.loc),
        "message": {"text": finding.message},
    }


def _physical_location(location: Location) -> dict[str, object]:
    return {
        "artifactLocation": {"uri": location.file.as_posix()},
        "region": {
            "endColumn": location.end_col + 1,
            "endLine": location.end_line,
            "startColumn": location.col + 1,
            "startLine": location.line,
        },
    }


def _level(severity: Severity) -> str:
    return {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "note",
    }[severity]
