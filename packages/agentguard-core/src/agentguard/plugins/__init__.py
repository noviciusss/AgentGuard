"""Plugin contracts and discovery support for AgentGuard."""

from agentguard.plugins.manager import PluginInfo, PluginManager
from agentguard.plugins.spec import hookimpl, hookspec

__all__ = ["PluginInfo", "PluginManager", "hookimpl", "hookspec"]
