"""The public pluggy hook contract for AgentGuard extensions."""

from __future__ import annotations

import pluggy
from typer import Typer

from agentguard.adapters.base import FrameworkAdapter
from agentguard.findings import Finding
from agentguard.ir.models import AgentSystem
from agentguard.reporters.base import Reporter
from agentguard.rules.base import Rule

PROJECT_NAME = "agentguard"
hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


class AgentGuardSpec:
    """Hooks implemented by built-in and third-party AgentGuard plugins."""

    @hookspec
    def register_rules(self) -> list[type[Rule]]:
        """Return rule classes provided by the plugin."""
        raise NotImplementedError

    @hookspec
    def register_adapters(self) -> list[type[FrameworkAdapter]]:
        """Return adapter classes provided by the plugin."""
        raise NotImplementedError

    @hookspec
    def register_reporters(self) -> list[type[Reporter]]:
        """Return reporter classes provided by the plugin."""
        raise NotImplementedError

    @hookspec
    def register_commands(self, app: Typer) -> None:
        """Add plugin-specific commands to the CLI application."""
        raise NotImplementedError

    @hookspec
    def modify_findings(
        self, findings: list[Finding], system: AgentSystem
    ) -> list[Finding]:
        """Return findings after applying a plugin transformation."""
        raise NotImplementedError
