"""Fixture-driven tests for AG001."""

from pathlib import Path

import pytest

from agentguard.adapters.generic import GenericAdapter
from agentguard.engine.parser import parse_file
from agentguard.ir.models import AgentSystem
from agentguard.rules.ag001_unbounded_retries import UnboundedRetriesRule
from agentguard.rules.base import RuleContext
from tests.fixture_support import assert_fixture_findings

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ag001"


@pytest.mark.parametrize("path", sorted(FIXTURE_ROOT.glob("*.py")))
def test_ag001_fixtures(path: Path) -> None:
    parsed = parse_file(path)
    facts = GenericAdapter().build(parsed)
    findings = UnboundedRetriesRule().run(
        RuleContext(AgentSystem([facts]), sources={path: parsed.source})
    )

    assert_fixture_findings(path, findings)
