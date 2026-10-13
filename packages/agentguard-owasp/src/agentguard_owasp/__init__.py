"""Offline OWASP/CWE finding tagging plugin."""

from __future__ import annotations

from dataclasses import replace

from agentguard.findings import Finding
from agentguard.ir.models import AgentSystem
from agentguard.plugins import hookimpl

TAGS: dict[str, tuple[str, str]] = {
    "AG020": ("LLM01:Prompt Injection", "CWE-693"),
    "AG021": ("LLM06:Excessive Agency", "CWE-862"),
    "AG022": ("LLM05:Improper Output Handling", "CWE-95"),
    "AG023": ("LLM02:Sensitive Information Disclosure", "CWE-798"),
    "AG001": ("LLM10:Unbounded Consumption", "CWE-400"),
    "AG004": ("LLM10:Unbounded Consumption", "CWE-835"),
}


class Plugin:
    """Attach versioned OWASP and CWE tags without network access."""

    name = "agentguard-owasp"

    @hookimpl
    def modify_findings(
        self, findings: list[Finding], system: AgentSystem
    ) -> list[Finding]:
        del system
        tagged: list[Finding] = []
        for finding in findings:
            mapping = TAGS.get(finding.rule_id)
            if mapping is None:
                tagged.append(finding)
                continue
            owasp, cwe = mapping
            tags = tuple(sorted({*finding.tags, owasp, cwe}))
            metadata = tuple(
                sorted({*finding.metadata, ("owasp", owasp), ("cwe", cwe)})
            )
            tagged.append(replace(finding, tags=tags, metadata=metadata))
        return tagged
