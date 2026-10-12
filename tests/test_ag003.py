"""Fixture-driven tests for AG003."""

from pathlib import Path

import pytest

from agentguard.adapters.generic import GenericAdapter
from agentguard.engine.parser import parse_file
from agentguard.findings import Severity
from agentguard.ir.models import AgentSystem
from agentguard.rules.ag003_missing_timeout import MissingTimeoutRule
from agentguard.rules.base import RuleContext
from tests.fixture_support import assert_fixture_findings

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ag003"


@pytest.mark.parametrize("path", sorted(FIXTURE_ROOT.glob("*.py")))
def test_ag003_fixtures(path: Path) -> None:
    parsed = parse_file(path)
    facts = GenericAdapter().build(parsed)
    context = RuleContext(
        AgentSystem([facts]),
        sources={path: parsed.source},
    )

    assert_fixture_findings(path, MissingTimeoutRule().run(context))


def test_ag003_escalates_calls_inside_loops() -> None:
    path = FIXTURE_ROOT / "bad_loop.py"
    parsed = parse_file(path)
    facts = GenericAdapter().build(parsed)
    findings = MissingTimeoutRule().run(
        RuleContext(AgentSystem([facts]), sources={path: parsed.source})
    )

    assert findings[0].severity == Severity.ERROR
