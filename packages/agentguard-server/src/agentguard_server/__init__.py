"""AgentGuard's standalone scan-history server."""

from agentguard_server.app import create_app
from agentguard_server.config import ServerSettings

__all__ = ["ServerSettings", "create_app"]
__version__ = "0.1.0"
