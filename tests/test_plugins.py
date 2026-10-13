"""Tests for the Phase 2 plugin contract and manager."""

from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from agentguard.adapters.base import FrameworkAdapter
from agentguard.engine.parser import ParsedModule
from agentguard.findings import Confidence, Finding, Location, Severity
from agentguard.ir.models import AgentSystem, ModuleFacts
from agentguard.plugins import PluginManager, hookimpl
from agentguard.rules.base import Rule, RuleContext


class ExampleRule(Rule):
    """Rule contributed by a test plugin."""

    rule_id = "AG900"
    name = "example-rule"
    description = "A test plugin rule."

    def check(self, context: RuleContext) -> list[Finding]:
        return []


class ExampleAdapter(FrameworkAdapter):
    """Adapter contributed by a test plugin."""

    name = "example"

    def can_handle(self, module: ParsedModule) -> bool:
        return False

    def build(self, module: ParsedModule) -> ModuleFacts:
        raise AssertionError("the test adapter must not build a module")


class ExamplePlugin:
    """A complete test plugin implementing contribution hooks."""

    name = "example-plugin"

    @hookimpl
    def register_rules(self) -> list[type[Rule]]:
        return [ExampleRule]

    @hookimpl
    def register_adapters(self) -> list[type[FrameworkAdapter]]:
        return [ExampleAdapter]

    @hookimpl
    def modify_findings(
        self, findings: list[Finding], system: AgentSystem
    ) -> list[Finding]:
        return [*findings]


class OtherPlugin:
    """A second plugin used to prove stable ordering."""

    name = "other-plugin"

    @hookimpl
    def register_rules(self) -> list[type[Rule]]:
        return []


class EntryPointPlugin:
    """Plugin loaded through importlib metadata in the discovery test."""

    @hookimpl
    def register_rules(self) -> list[type[Rule]]:
        return [ExampleRule]


def test_plugin_manager_collects_typed_contributions() -> None:
    manager = PluginManager()
    info = manager.register(ExamplePlugin(), version="1.2.3")

    assert info.name == "example-plugin"
    assert info.version == "1.2.3"
    assert manager.plugins() == (info,)
    assert manager.rules() == (ExampleRule,)
    assert manager.adapters() == (ExampleAdapter,)
    assert manager.reporters() == ()


def test_plugin_manager_orders_plugins_and_rules_deterministically() -> None:
    manager = PluginManager()
    manager.register(OtherPlugin())
    manager.register(ExamplePlugin())

    assert [plugin.name for plugin in manager.plugins()] == [
        "example-plugin",
        "other-plugin",
    ]
    assert manager.rules() == (ExampleRule,)


def test_duplicate_plugin_names_are_rejected() -> None:
    manager = PluginManager()
    manager.register(ExamplePlugin())

    with pytest.raises(ValueError, match="duplicate plugin name"):
        manager.register(ExamplePlugin())


def test_entry_point_plugins_are_loaded_and_bad_plugins_are_reported() -> None:
    manager = PluginManager()
    candidates = [
        EntryPoint(
            name="entry-point-plugin",
            value="tests.test_plugins:EntryPointPlugin",
            group="agentguard",
        ),
        EntryPoint(
            name="broken-plugin",
            value="tests.test_plugins:MissingPlugin",
            group="agentguard",
        ),
    ]

    manager.discover(candidates)

    assert [plugin.name for plugin in manager.plugins()] == ["entry-point-plugin"]
    assert manager.rules() == (ExampleRule,)
    assert manager.load_errors() == (
        "broken-plugin: module 'tests.test_plugins' has no attribute 'MissingPlugin'",
    )


def test_default_manager_registers_builtins_in_adapter_priority_order() -> None:
    manager = PluginManager.default(discover=False)

    assert [rule.rule_id for rule in manager.rules()] == [
        "AG001",
        "AG002",
        "AG003",
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
    ]
    assert [adapter.name for adapter in manager.adapters()] == [
        "crewai",
        "autogen",
        "generic",
    ]


def test_finding_modifiers_are_applied_in_plugin_order() -> None:
    class FirstPlugin:
        name = "a-first"

        @hookimpl
        def modify_findings(
            self, findings: list[Finding], system: AgentSystem
        ) -> list[Finding]:
            return [*findings, _finding("AG901")]

    class SecondPlugin:
        name = "b-second"

        @hookimpl
        def modify_findings(
            self, findings: list[Finding], system: AgentSystem
        ) -> list[Finding]:
            return [*findings, _finding("AG902")]

    manager = PluginManager()
    manager.register(SecondPlugin())
    manager.register(FirstPlugin())

    findings = manager.apply_finding_modifiers([], AgentSystem([]))

    assert [finding.rule_id for finding in findings] == ["AG901", "AG902"]


def _finding(rule_id: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=Severity.INFO,
        confidence=Confidence.HIGH,
        message="message",
        why="why",
        suggestion="suggestion",
        loc=Location(Path("agent.py"), 1, 0, 1, 1),
    )
