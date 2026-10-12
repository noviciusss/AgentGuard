"""LangGraph adapter plugin distribution."""

from agentguard.plugins import hookimpl
from agentguard_langgraph.adapter import LangGraphAdapter


class Plugin:
    """Register the LangGraph adapter with AgentGuard."""

    name = "agentguard-langgraph"

    @hookimpl
    def register_adapters(self) -> list[type[LangGraphAdapter]]:
        return [LangGraphAdapter]
