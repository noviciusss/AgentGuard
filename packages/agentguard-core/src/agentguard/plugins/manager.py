"""Deterministic registration and execution of AgentGuard plugins."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import TypeVar, cast

import pluggy
from typer import Typer

from agentguard.adapters.base import FrameworkAdapter
from agentguard.findings import Finding
from agentguard.ir.models import AgentSystem
from agentguard.plugins.spec import PROJECT_NAME, AgentGuardSpec
from agentguard.reporters.base import Reporter
from agentguard.rules.base import Rule


@dataclass(frozen=True)
class PluginInfo:
    """Stable metadata for one registered plugin object."""

    name: str
    version: str
    module: str


class PluginManager:
    """Register plugins and collect their typed contributions."""

    def __init__(self) -> None:
        self._manager = pluggy.PluginManager(PROJECT_NAME)
        self._manager.add_hookspecs(AgentGuardSpec)
        self._plugins: dict[str, PluginInfo] = {}
        self._objects: dict[str, object] = {}
        self._load_errors: list[str] = []

    @classmethod
    def default(cls, *, discover: bool = True) -> PluginManager:
        """Create a manager with built-ins and optionally installed plugins."""
        from agentguard.plugins.builtin import BuiltinPlugin

        manager = cls()
        manager.register(BuiltinPlugin(), version="0.1.0")
        if discover:
            manager.discover()
        return manager

    def register(
        self,
        plugin: object,
        *,
        name: str | None = None,
        version: str = "unknown",
    ) -> PluginInfo:
        """Register one plugin and return its normalized metadata."""
        plugin_name = name or _plugin_name(plugin)
        if plugin_name in self._plugins:
            raise ValueError(f"duplicate plugin name: {plugin_name}")
        self._manager.register(plugin, name=plugin_name)
        info = PluginInfo(plugin_name, version, plugin.__class__.__module__)
        self._plugins[plugin_name] = info
        self._objects[plugin_name] = plugin
        return info

    def plugins(self) -> tuple[PluginInfo, ...]:
        """Return registered plugin metadata in stable name order."""
        return tuple(self._plugins[name] for name in sorted(self._plugins))

    def info(self, name: str) -> PluginInfo:
        """Return one plugin's metadata by name."""
        return self._plugins[name]

    def contributions(self, name: str) -> dict[str, tuple[str, ...]]:
        """Return the named plugin's declared contribution class names."""
        plugin = self._objects[name]
        contributions: dict[str, tuple[str, ...]] = {}
        for hook_name in ("register_rules", "register_adapters", "register_reporters"):
            contribution = getattr(plugin, hook_name, None)
            if callable(contribution):
                values = contribution()
                contributions[hook_name] = tuple(
                    sorted(value.__name__ for value in values)
                )
        if callable(getattr(plugin, "register_commands", None)):
            contributions["register_commands"] = ()
        return contributions

    def load_errors(self) -> tuple[str, ...]:
        """Return non-fatal errors encountered while loading entry points."""
        return tuple(self._load_errors)

    def discover(self, candidates: Iterable[EntryPoint] | None = None) -> None:
        """Load plugins from the ``agentguard`` entry-point group."""
        selected = (
            tuple(candidates)
            if candidates is not None
            else tuple(entry_points(group=PROJECT_NAME))
        )
        for entry_point in sorted(selected, key=lambda item: item.name):
            try:
                loaded = entry_point.load()
                plugin = loaded() if isinstance(loaded, type) else loaded
                version = (
                    entry_point.dist.version
                    if entry_point.dist is not None
                    else "unknown"
                )
                self.register(plugin, name=entry_point.name, version=version)
            except (ImportError, AttributeError, TypeError, ValueError) as error:
                self._load_errors.append(f"{entry_point.name}: {error}")

    def rules(self) -> tuple[type[Rule], ...]:
        """Collect and sort all registered rule classes."""
        rules = _flatten(self._manager.hook.register_rules())
        return tuple(sorted(rules, key=lambda rule: rule.rule_id))

    def adapters(self) -> tuple[type[FrameworkAdapter], ...]:
        """Collect and sort all registered adapter classes."""
        adapters = _flatten(self._manager.hook.register_adapters())
        return tuple(
            sorted(adapters, key=lambda adapter: (adapter.priority, adapter.name))
        )

    def reporters(self) -> tuple[type[Reporter], ...]:
        """Collect and sort all registered reporter classes."""
        reporters = _flatten(self._manager.hook.register_reporters())
        return tuple(sorted(reporters, key=lambda reporter: reporter.__name__))

    def apply_finding_modifiers(
        self, findings: list[Finding], system: AgentSystem
    ) -> list[Finding]:
        """Apply finding hooks in registered plugin-name order."""
        result = list(findings)
        for name in sorted(self._objects):
            plugin = self._objects[name]
            modifier = getattr(plugin, "modify_findings", None)
            if callable(modifier):
                result = _call_modifier(modifier, result, system)
        return result

    def register_commands(self, app: Typer) -> None:
        """Let installed plugins add commands to a Typer application."""
        for name in sorted(self._objects):
            command_hook = getattr(self._objects[name], "register_commands", None)
            if callable(command_hook):
                command_hook(app)


def _plugin_name(plugin: object) -> str:
    name = getattr(plugin, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return plugin.__class__.__name__


T = TypeVar("T")


def _flatten(values: list[list[T]]) -> list[T]:
    return [value for contribution in values for value in contribution]


def _call_modifier(
    modifier: object, findings: list[Finding], system: AgentSystem
) -> list[Finding]:
    callable_modifier = cast(Callable[[list[Finding], AgentSystem], object], modifier)
    result = callable_modifier(findings, system)
    if not isinstance(result, list) or not all(
        isinstance(finding, Finding) for finding in result
    ):
        raise TypeError("modify_findings must return list[Finding]")
    return result
