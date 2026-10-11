"""Tests for rule contracts and registry behavior."""

from pathlib import Path
from typing import ClassVar

import pytest

from agentguard.findings import Confidence, Finding, Location, Severity
from agentguard.ir.models import AgentSystem
from agentguard.rules import Rule, RuleContext, RuleRegistrationError, RuleRegistry


def finding(rule_id: str, line: int, file: Path = Path("agent.py")) -> Finding:
    """Create a concise test finding."""
    return Finding(
        rule_id=rule_id,
        severity=Severity.WARNING,
        confidence=Confidence.HIGH,
        message="test finding",
        why="test reason",
        suggestion="test fix",
        loc=Location(file, line, 0, line, 1),
    )


class FirstRule(Rule):
    """Test rule with a source-backed fingerprint."""

    rule_id: ClassVar[str] = "AG001"
    name: ClassVar[str] = "first-rule"
    description: ClassVar[str] = "First test rule."

    def check(self, context: RuleContext) -> list[Finding]:
        assert context.system.modules == []
        return [finding(self.rule_id, 2)]


class SecondRule(Rule):
    """Test rule used to verify selection and sorting."""

    rule_id: ClassVar[str] = "AG002"
    name: ClassVar[str] = "second-rule"
    description: ClassVar[str] = "Second test rule."

    def check(self, context: RuleContext) -> list[Finding]:
        return [finding(self.rule_id, 1)]


def context() -> RuleContext:
    """Build a minimal context for registry tests."""
    return RuleContext(
        AgentSystem([]),
        sources={Path("agent.py"): "first line\nsecond line\n"},
    )


def test_rule_run_validates_and_fingerprints_findings() -> None:
    results = FirstRule().run(context())

    assert len(results) == 1
    assert results[0].fingerprint
    assert results[0].rule_id == "AG001"


def test_registry_lists_selects_and_runs_rules_deterministically() -> None:
    registry = RuleRegistry([SecondRule, FirstRule])

    assert [descriptor.rule_id for descriptor in registry.descriptors()] == [
        "AG001",
        "AG002",
    ]
    assert registry.select(["AG00*"]) == (FirstRule, SecondRule)
    assert registry.select(ignored=["AG001"]) == (SecondRule,)
    assert [item.rule_id for item in registry.run(context())] == ["AG002", "AG001"]


def test_registry_rejects_invalid_and_duplicate_rules() -> None:
    class InvalidRule(Rule):
        rule_id: ClassVar[str] = "BAD"
        name: ClassVar[str] = "invalid"
        description: ClassVar[str] = "Invalid test rule."

        def check(self, context: RuleContext) -> list[Finding]:
            return []

    with pytest.raises(RuleRegistrationError, match="invalid rule ID"):
        RuleRegistry([InvalidRule])

    registry = RuleRegistry([FirstRule])
    with pytest.raises(RuleRegistrationError, match="duplicate"):
        registry.register(FirstRule)


def test_rule_rejects_findings_from_another_rule() -> None:
    class MismatchedRule(Rule):
        rule_id: ClassVar[str] = "AG003"
        name: ClassVar[str] = "mismatched"
        description: ClassVar[str] = "Mismatched test rule."

        def check(self, context: RuleContext) -> list[Finding]:
            return [finding("AG001", 1)]

    with pytest.raises(ValueError, match="emitted finding"):
        MismatchedRule().run(context())
