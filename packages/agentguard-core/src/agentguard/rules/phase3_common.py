"""Shared helpers for the Phase 3 rule family."""

from __future__ import annotations

from agentguard.findings import Confidence, Finding, Location, Severity


def finding(
    rule_id: str,
    loc: Location,
    message: str,
    why: str,
    suggestion: str,
    *,
    severity: Severity = Severity.WARNING,
    confidence: Confidence = Confidence.HIGH,
    related: tuple[Location, ...] = (),
) -> Finding:
    """Construct a consistent Phase 3 finding."""
    return Finding(
        rule_id=rule_id,
        severity=severity,
        confidence=confidence,
        message=message,
        why=why,
        suggestion=suggestion,
        loc=loc,
        related=related,
    )


def dangerous_tool_name(name: str) -> bool:
    """Return whether a tool name suggests an irreversible capability."""
    lowered = name.lower()
    return any(
        word in lowered
        for word in {
            "shell",
            "exec",
            "delete",
            "remove",
            "write",
            "payment",
            "charge",
            "email",
            "send",
            "sql",
            "file",
        }
    )
