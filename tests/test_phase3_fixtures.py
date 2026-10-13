"""Fixture-driven tests for the Phase 3 rule catalog."""

from pathlib import Path

import pytest

from agentguard.engine.parser import parse_file
from agentguard.ir.builder import IRBuilder
from agentguard.ir.models import AgentSystem
from agentguard.plugins.manager import PluginManager
from agentguard.rules.base import RuleContext
from tests.fixture_support import assert_fixture_findings

RULE_IDS = (
    "AG004",
    "AG005",
    "AG006",
    "AG007",
    "AG008",
    "AG009",
    "AG010",
    "AG011",
    "AG020",
    "AG021",
    "AG022",
    "AG023",
)


@pytest.mark.parametrize(
    ("rule_id", "path"),
    [
        (rule_id, path)
        for rule_id in RULE_IDS
        for path in sorted(
            (Path(__file__).parent / "fixtures" / rule_id.lower()).glob("*.py")
        )
    ],
)
def test_phase3_fixtures(rule_id: str, path: Path) -> None:
    manager = PluginManager.default()
    adapters = [adapter() for adapter in manager.adapters()]
    rule = next(rule for rule in manager.rules() if rule.rule_id == rule_id)
    parsed = parse_file(path)
    facts = IRBuilder(adapters).build_module(parsed)
    findings = rule().run(
        RuleContext(AgentSystem([facts]), sources={path: parsed.source})
    )

    assert_fixture_findings(path, findings)
