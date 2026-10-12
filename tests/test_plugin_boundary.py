"""Acceptance tests for the external-plugin boundary."""

from importlib.metadata import EntryPoint

from agentguard.findings import Finding
from agentguard.plugins import PluginManager, hookimpl
from agentguard.rules.base import Rule, RuleContext


class ExternalRule(Rule):
    """Rule supplied by a plugin outside the built-in registry."""

    rule_id = "AG998"
    name = "external-rule"
    description = "A rule from a separately discovered plugin."

    def check(self, context: RuleContext) -> list[Finding]:
        return []


class ExternalPlugin:
    @hookimpl
    def register_rules(self) -> list[type[Rule]]:
        return [ExternalRule]


def test_separately_discovered_plugin_contributes_a_rule() -> None:
    manager = PluginManager.default(discover=False)
    manager.discover(
        [
            EntryPoint(
                name="external-plugin",
                value="tests.test_plugin_boundary:ExternalPlugin",
                group="agentguard",
            )
        ]
    )

    assert "AG998" in {rule.rule_id for rule in manager.rules()}
    assert manager.load_errors() == ()
