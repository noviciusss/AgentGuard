"""Build whole-scan Agent IR through registered framework adapters."""

from __future__ import annotations

from collections.abc import Iterable

from agentguard.adapters.base import FrameworkAdapter
from agentguard.engine.parser import ParsedModule
from agentguard.ir.models import AgentSystem, ModuleFacts


class IRBuilder:
    """Select the first matching adapter and build normalized module facts."""

    def __init__(self, adapters: Iterable[FrameworkAdapter] = ()) -> None:
        configured = tuple(adapters)
        from agentguard.plugins.manager import PluginManager

        registered = PluginManager.default(discover=False).adapters()
        names = {adapter.name for adapter in configured}
        fallback = tuple(
            adapter()
            for adapter in registered
            if adapter.name == "generic" and adapter.name not in names
        )
        self.adapters = (*configured, *fallback)

    def build_module(self, module: ParsedModule) -> ModuleFacts:
        """Build one module using the first adapter that recognizes it."""
        for adapter in self.adapters:
            if adapter.can_handle(module):
                return adapter.build(module)
        raise ValueError(f"no adapter recognized {module.path}")

    def build_system(self, modules: Iterable[ParsedModule]) -> AgentSystem:
        """Build deterministic whole-scan facts from parsed modules."""
        facts = [self.build_module(module) for module in modules]
        return AgentSystem(sorted(facts, key=lambda item: item.path.as_posix()))
