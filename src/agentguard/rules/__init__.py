"""Rule interfaces and deterministic rule registration."""

from agentguard.rules.base import Rule, RuleContext, RuleDescriptor
from agentguard.rules.registry import RuleRegistrationError, RuleRegistry

__all__ = [
    "Rule",
    "RuleContext",
    "RuleDescriptor",
    "RuleRegistry",
    "RuleRegistrationError",
]
