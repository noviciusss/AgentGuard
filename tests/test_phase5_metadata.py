"""Tests for Phase 5 finding metadata tagging."""

from pathlib import Path

from agentguard.findings import Confidence, Finding, Location, Severity
from agentguard.ir.models import AgentSystem
from agentguard_owasp import Plugin


def test_owasp_plugin_tags_security_findings() -> None:
    finding = Finding(
        rule_id="AG020",
        severity=Severity.ERROR,
        confidence=Confidence.HIGH,
        message="prompt injection",
        why="unsafe",
        suggestion="separate data",
        loc=Location(Path("agent.py"), 1, 0, 1, 1),
    )

    tagged = Plugin().modify_findings([finding], AgentSystem([]))[0]

    assert "LLM01:Prompt Injection" in tagged.tags
    assert dict(tagged.metadata)["cwe"] == "CWE-693"
