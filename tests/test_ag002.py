"""Fixture-driven tests for AG002."""

from pathlib import Path

import pytest

from agentguard.adapters.generic import GenericAdapter
from agentguard.engine.parser import parse_file
from agentguard.ir.models import AgentSystem
from agentguard.rules.ag002_shared_mutable_fanout import SharedMutableFanoutRule
from agentguard.rules.base import RuleContext
from agentguard_langgraph.adapter import LangGraphAdapter
from tests.fixture_support import assert_fixture_findings

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ag002"


@pytest.mark.parametrize("path", sorted(FIXTURE_ROOT.glob("*.py")))
def test_ag002_fixtures(path: Path) -> None:
    parsed = parse_file(path)
    adapter = LangGraphAdapter() if "langgraph" in parsed.source else GenericAdapter()
    facts = adapter.build(parsed)
    findings = SharedMutableFanoutRule().run(
        RuleContext(AgentSystem([facts]), sources={path: parsed.source})
    )

    assert_fixture_findings(path, findings)
