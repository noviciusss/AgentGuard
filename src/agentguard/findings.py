"""Finding and source-location models shared by the analysis pipeline."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    """How serious a finding is for the analyzed agent."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Confidence(str, Enum):
    """How confident AgentGuard is that a finding is valid."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Location:
    """A source range, with a path relative to the scan root."""

    file: Path
    line: int
    col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class Fix:
    """Placeholder for a future safe autofix operation."""


@dataclass(frozen=True)
class Finding:
    """A deterministic, user-facing result produced by an analysis rule."""

    rule_id: str
    severity: Severity
    confidence: Confidence
    message: str
    why: str
    suggestion: str
    loc: Location
    related: tuple[Location, ...] = ()
    fingerprint: str = ""
    fix: Fix | None = None


def finding_sort_key(finding: Finding) -> tuple[str, int, int, str]:
    """Return the stable ordering key required for reported findings."""
    return (
        finding.loc.file.as_posix(),
        finding.loc.line,
        finding.loc.col,
        finding.rule_id,
    )


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Return findings sorted by file, location, and rule identifier."""
    return sorted(findings, key=finding_sort_key)
