"""The built-in Phase 1 rule registry."""

from agentguard.plugins.manager import PluginManager
from agentguard.rules.registry import RuleRegistry


def builtin_registry() -> RuleRegistry:
    """Create a fresh registry containing all built-in rules."""
    return RuleRegistry(PluginManager.default(discover=False).rules())
