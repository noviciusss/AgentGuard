"""Uvicorn entry point for the AgentGuard server."""

from __future__ import annotations

import uvicorn

from agentguard_server.app import create_app
from agentguard_server.config import ServerSettings

settings = ServerSettings.from_env()
app = create_app(settings)


def run() -> None:
    """Run the configured Uvicorn application."""
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="debug" if settings.debug else "info",
    )
