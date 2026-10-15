"""Tests for Phase 5 finding metadata tagging."""

from pathlib import Path

from agentguard.findings import Confidence, Finding, Location, Severity
from agentguard.ir.models import AgentSystem
from agentguard_owasp import OWASP_VERSION, Plugin


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
    assert dict(tagged.metadata)["owasp_version"] == OWASP_VERSION


def test_owasp_plugin_adds_cost_rule_metadata_and_overwrites_reserved_keys() -> None:
    finding = Finding(
        rule_id="AG005",
        severity=Severity.WARNING,
        confidence=Confidence.MEDIUM,
        message="missing budget",
        why="cost can grow",
        suggestion="set max_tokens",
        loc=Location(Path("agent.py"), 1, 0, 1, 1),
        tags=("custom",),
        metadata=(("cwe", "old"), ("owner", "team")),
    )

    tagged = Plugin().modify_findings([finding], AgentSystem([]))[0]

    assert tagged.tags == (
        "CWE-400",
        "LLM10:Unbounded Consumption",
        "custom",
    )
    assert dict(tagged.metadata) == {
        "cwe": "CWE-400",
        "owasp": "LLM10:Unbounded Consumption",
        "owasp_version": OWASP_VERSION,
        "owner": "team",
    }
