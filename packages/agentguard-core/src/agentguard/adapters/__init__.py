"""Framework adapters that translate source into Agent IR."""

from agentguard.adapters.autogen import AutoGenAdapter
from agentguard.adapters.base import FrameworkAdapter
from agentguard.adapters.crewai import CrewAIAdapter
from agentguard.adapters.generic import GenericAdapter

__all__ = [
    "AutoGenAdapter",
    "CrewAIAdapter",
    "FrameworkAdapter",
    "GenericAdapter",
]
