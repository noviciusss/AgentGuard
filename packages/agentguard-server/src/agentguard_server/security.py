"""Authentication, request safety, and privacy helpers for the server."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from time import monotonic
from typing import cast

from fastapi import HTTPException, Request, status


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated service identity and its repository scope."""

    subject: str
    repositories: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset({"read", "write"})
    authenticated: bool = True

    def can_access(self, repository_name: str) -> bool:
        """Return whether this principal may access a repository."""
        return not self.repositories or repository_name in self.repositories

    def allows(self, scope: str) -> bool:
        """Return whether the principal has a named API scope."""
        return scope in self.scopes


ANONYMOUS = Principal(subject="anonymous", authenticated=False)


def _parse_tokens(raw: str) -> dict[str, Principal]:
    """Parse ``token=subject;scope1,scope2;repo1,repo2`` entries.

    The raw token value is retained only as a hash key and is never returned in
    errors or logs. Empty scope/repository sections are valid.
    """
    parsed: dict[str, Principal] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        token, separator, descriptor = entry.partition("=")
        if not separator or not token or not descriptor:
            raise ValueError("AGENTGUARD_API_TOKENS entries must use token=descriptor")
        parts = descriptor.split(";", 2)
        subject = parts[0].strip()
        if not subject:
            raise ValueError("API token subjects must not be empty")
        scopes = (
            frozenset(item.strip() for item in parts[1].split("|") if item.strip())
            if len(parts) > 1
            else frozenset({"read", "write"})
        )
        repositories = (
            frozenset(item.strip() for item in parts[2].split("|") if item.strip())
            if len(parts) > 2
            else frozenset()
        )
        parsed[token] = Principal(subject, repositories, scopes)
    return parsed


class TokenAuthenticator:
    """Constant-time bearer-token authenticator backed by environment config."""

    def __init__(self, tokens: Mapping[str, Principal]) -> None:
        self._tokens = tuple(tokens.items())

    @classmethod
    def from_raw(cls, raw: str) -> TokenAuthenticator:
        return cls(_parse_tokens(raw))

    def authenticate(self, authorization: str | None) -> Principal:
        """Authenticate a bearer header or raise a generic HTTP error."""
        if authorization is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="authentication required",
            )
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="authentication required",
            )
        for configured, principal in self._tokens:
            if secrets.compare_digest(configured, token):
                return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="access denied"
        )


def principal_for_request(request: Request) -> Principal:
    """Resolve the configured principal for a request."""
    authenticator = cast(
        TokenAuthenticator | None, getattr(request.app.state, "authenticator", None)
    )
    required = bool(getattr(request.app.state.settings, "auth_required", False))
    authorization = request.headers.get("authorization")
    if authenticator is None:
        if required:
            raise HTTPException(status_code=401, detail="authentication required")
        request.state.principal = ANONYMOUS
        return ANONYMOUS
    if authorization is None and not required:
        request.state.principal = ANONYMOUS
        return ANONYMOUS
    principal = authenticator.authenticate(authorization)
    request.state.principal = principal
    return principal


def require_scope(principal: Principal, scope: str) -> None:
    """Reject an authenticated principal without a required scope."""
    if not principal.authenticated or not principal.allows(scope):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="access denied"
        )


def require_authenticated_scope(request: Request, scope: str) -> Principal:
    """Resolve a principal and enforce a scope for authenticated deployments."""
    principal = principal_for_request(request)
    if principal.authenticated:
        require_scope(principal, scope)
    return principal


def require_read_access(request: Request) -> Principal:
    """FastAPI dependency for repository and scan reads."""
    return require_authenticated_scope(request, "read")


def require_write_access(request: Request) -> Principal:
    """FastAPI dependency for ingestion and mutation endpoints."""
    return require_authenticated_scope(request, "write")


def request_id(value: str | None) -> str:
    """Accept a safe incoming request ID or create a UUID-based one."""
    if (
        value is not None
        and 0 < len(value) <= 128
        and all(character.isalnum() or character in "-_." for character in value)
    ):
        return value
    return str(uuid.uuid4())


def redact(value: object) -> object:
    """Return a recursively redacted structure suitable for audit details."""
    sensitive = {"authorization", "token", "secret", "password", "api_key", "cookie"}
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if str(key).lower() in sensitive else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


@dataclass(slots=True)
class RateLimiter:
    """Small process-local fixed-window limiter for deployment safety defaults."""

    limit: int = 120
    window_seconds: float = 60.0
    _windows: dict[str, tuple[float, int]] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        now = monotonic()
        started, count = self._windows.get(key, (now, 0))
        if now - started >= self.window_seconds:
            started, count = now, 0
        if count >= self.limit:
            self._windows[key] = (started, count)
            return False
        self._windows[key] = (started, count + 1)
        return True


def token_fingerprint(token: str) -> str:
    """Return a non-secret identifier for audit/debug correlation."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


RequestAudit = Callable[[str, str, str, int, Principal], None]
