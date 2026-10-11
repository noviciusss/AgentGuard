"""Framework adapters that translate source into Agent IR."""

from agentguard.adapters.base import FrameworkAdapter
from agentguard.adapters.generic import GenericAdapter

__all__ = ["FrameworkAdapter", "GenericAdapter"]
