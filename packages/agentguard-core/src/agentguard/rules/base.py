"""Base classes and context objects for AgentGuard rules."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import ClassVar

from agentguard.engine.fingerprint import fingerprint
from agentguard.findings import Finding, Severity, sort_findings
from agentguard.ir.models import AgentSystem

RULE_ID_PATTERN = re.compile(r"AG[0-9]{3}\Z")


@dataclass(frozen=True)
class RuleContext:
    """Read-only inputs available to a rule during one scan.

    ``system`` is the normalized Agent IR. ``sources`` is optional source text
    keyed by the relative paths used in IR locations; rules never need to
    inspect AST nodes or framework-specific syntax.
    """

    system: AgentSystem
    root: Path = Path(".")
    sources: Mapping[Path, str] = field(default_factory=dict)

    def source_snippet(self, file: Path, line: int, end_line: int | None = None) -> str:
        """Return a source range, or an empty string when source is unavailable."""
        source = self.sources.get(file)
        if source is None:
            return ""
        lines = source.splitlines()
        start_index = max(line - 1, 0)
        end_index = max(end_line if end_line is not None else line, line)
        return "\n".join(lines[start_index:end_index])

    def finalize_finding(self, finding: Finding) -> Finding:
        """Add a stable fingerprint when source text is available."""
        if finding.fingerprint:
            return finding
        snippet = self.source_snippet(
            finding.loc.file,
            finding.loc.line,
            finding.loc.end_line,
        )
        if not snippet:
            return finding
        return replace(
            finding,
            fingerprint=fingerprint(finding.rule_id, finding.loc.file, snippet),
        )


@dataclass(frozen=True)
class RuleDescriptor:
    """Metadata displayed by rule listing and plugin discovery code."""

    rule_id: str
    name: str
    description: str
    default_severity: Severity


class Rule(ABC):
    """Abstract interface implemented by every AgentGuard analysis rule."""

    rule_id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    default_severity: ClassVar[Severity] = Severity.WARNING

    @classmethod
    def descriptor(cls) -> RuleDescriptor:
        """Return validated metadata for this rule class."""
        return RuleDescriptor(
            rule_id=cls.rule_id,
            name=cls.name,
            description=cls.description,
            default_severity=cls.default_severity,
        )

    @abstractmethod
    def check(self, context: RuleContext) -> Iterable[Finding]:
        """Analyze normalized IR and yield findings for this rule."""

    def run(self, context: RuleContext) -> list[Finding]:
        """Validate, fingerprint, and deterministically sort rule findings."""
        findings: list[Finding] = []
        for finding in self.check(context):
            if finding.rule_id != self.rule_id:
                raise ValueError(
                    f"rule {self.rule_id} emitted finding for {finding.rule_id}"
                )
            findings.append(context.finalize_finding(finding))
        return sort_findings(findings)
