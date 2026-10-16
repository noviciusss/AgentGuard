"""FastAPI application factory for AgentGuard Server."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from agentguard_server.api import router, v1_router
from agentguard_server.audit import InMemoryAuditSink, SqlAlchemyAuditSink
from agentguard_server.config import ServerSettings
from agentguard_server.db import (
    SessionFactory,
    create_database_engine,
    create_session_factory,
)
from agentguard_server.github import InMemoryDeliveryReplayStore
from agentguard_server.platform_api import router as platform_router
from agentguard_server.security import (
    ANONYMOUS,
    RateLimiter,
    TokenAuthenticator,
    request_id,
)


class RequestSafetyMiddleware(BaseHTTPMiddleware):
    """Apply request IDs, payload limits, and a process-local rate limit."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process one request without logging request bodies or credentials."""
        settings = request.app.state.settings
        incoming_length = request.headers.get("content-length")
        try:
            content_length = (
                int(incoming_length) if incoming_length is not None else None
            )
        except ValueError:
            content_length = None
        if content_length is not None and content_length > settings.max_payload_bytes:
            identifier = request_id(request.headers.get("x-request-id"))
            return Response(
                content='{"detail":"request payload is too large"}',
                status_code=413,
                media_type="application/json",
                headers={"X-Request-ID": identifier},
            )
        identifier = request_id(request.headers.get("x-request-id"))
        request.state.request_id = identifier
        client_host = request.client.host if request.client else "unknown"
        limiter = request.app.state.rate_limiter
        if not limiter.allow(client_host):
            return Response(
                content='{"detail":"rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60", "X-Request-ID": identifier},
            )
        response = await call_next(request)
        response.headers["X-Request-ID"] = identifier
        request.app.state.audit.record(
            request.method,
            identifier,
            getattr(request.state, "principal", request.app.state.anonymous),
            response.status_code,
            {"path": request.url.path},
        )
        return response


def create_app(
    settings: ServerSettings | None = None,
    *,
    engine: Engine | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> FastAPI:
    """Create a configured FastAPI application.

    ``engine`` and ``session_factory`` are injectable so tests and migration
    tools can use an isolated database without changing environment variables.
    """
    resolved_settings = settings or ServerSettings.from_env()
    resolved_engine = engine or create_database_engine(resolved_settings)
    resolved_factory: SessionFactory = session_factory or create_session_factory(
        resolved_engine
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        resolved_engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.engine = resolved_engine
    app.state.session_factory = resolved_factory
    app.state.anonymous = ANONYMOUS
    app.state.authenticator = (
        TokenAuthenticator.from_raw(resolved_settings.api_tokens)
        if resolved_settings.api_tokens
        else None
    )
    app.state.rate_limiter = RateLimiter(limit=resolved_settings.rate_limit)
    app.state.audit = SqlAlchemyAuditSink(resolved_factory, InMemoryAuditSink())
    app.state.github_replay_store = InMemoryDeliveryReplayStore()
    if resolved_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                origin.strip()
                for origin in resolved_settings.cors_origins.split(",")
                if origin.strip()
            ],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    app.add_middleware(RequestSafetyMiddleware)
    app.include_router(router)
    app.include_router(v1_router)
    app.include_router(platform_router)
    return app
