"""Human-readable text reporter."""

from collections.abc import Iterable

from agentguard.findings import Finding, sort_findings
from agentguard.reporters.base import Reporter


class TextReporter(Reporter):
    """Render one finding with why and fix guidance."""

    def render(self, findings: Iterable[Finding]) -> str:
        """Return findings in stable source order."""
        lines: list[str] = []
        for finding in sort_findings(list(findings)):
            location = finding.loc
            lines.append(
                f"{location.file.as_posix()}:{location.line}:{location.col}  "
                f"{finding.rule_id}  {finding.severity.value}  "
                f"[{finding.confidence.value}]  {finding.message}"
            )
            lines.append(f"  why: {finding.why}")
            lines.append(f"  fix: {finding.suggestion}")
        return "\n".join(lines)
