"""Typed configuration loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field


def _read_bool(value: str, variable_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{variable_name} must be a boolean")


def _read_int(value: str, variable_name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{variable_name} must be an integer") from error


class ServerSettings(BaseModel):
    """Validated settings for the HTTP service and database engine."""

    model_config = ConfigDict(extra="forbid")

    app_name: str = Field(default="AgentGuard Server", min_length=1)
    environment: str = Field(default="development", min_length=1)
    debug: bool = False
    database_url: str = Field(
        default="postgresql+psycopg://agentguard:agentguard@localhost:5432/agentguard",
        min_length=1,
    )
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_echo: bool = False
    auth_required: bool = False
    api_tokens: str = ""
    max_payload_bytes: int = Field(default=2_000_000, ge=1_024)
    rate_limit: int = Field(default=120, ge=1)
    github_webhook_secret: str | None = None
    public_badges: bool = False
    cors_origins: str = ""

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ServerSettings:
        """Build settings from ``AGENTGUARD_*`` variables and safe defaults."""
        values = os.environ if environ is None else environ
        database_url = values.get("AGENTGUARD_DATABASE_URL") or values.get(
            "DATABASE_URL"
        )
        raw: dict[str, object] = {}
        if database_url is not None:
            raw["database_url"] = database_url
        mappings: tuple[tuple[str, str], ...] = (
            ("app_name", "AGENTGUARD_APP_NAME"),
            ("environment", "AGENTGUARD_ENVIRONMENT"),
            ("host", "AGENTGUARD_HOST"),
        )
        for field_name, variable_name in mappings:
            value = values.get(variable_name)
            if value is not None:
                raw[field_name] = value

        boolean_mappings: tuple[tuple[str, str], ...] = (
            ("debug", "AGENTGUARD_DEBUG"),
            ("db_echo", "AGENTGUARD_DB_ECHO"),
            ("auth_required", "AGENTGUARD_AUTH_REQUIRED"),
            ("public_badges", "AGENTGUARD_PUBLIC_BADGES"),
        )
        for field_name, variable_name in boolean_mappings:
            value = values.get(variable_name)
            if value is not None:
                raw[field_name] = _read_bool(value, variable_name)

        integer_mappings: tuple[tuple[str, str], ...] = (
            ("port", "AGENTGUARD_PORT"),
            ("db_pool_size", "AGENTGUARD_DB_POOL_SIZE"),
            ("db_max_overflow", "AGENTGUARD_DB_MAX_OVERFLOW"),
            ("max_payload_bytes", "AGENTGUARD_MAX_PAYLOAD_BYTES"),
            ("rate_limit", "AGENTGUARD_RATE_LIMIT"),
        )
        for field_name, variable_name in integer_mappings:
            value = values.get(variable_name)
            if value is not None:
                raw[field_name] = _read_int(value, variable_name)
        tokens = values.get("AGENTGUARD_API_TOKENS")
        if tokens is not None:
            raw["api_tokens"] = tokens
        webhook_secret = values.get("AGENTGUARD_GITHUB_WEBHOOK_SECRET")
        if webhook_secret is not None:
            raw["github_webhook_secret"] = webhook_secret
        cors_origins = values.get("AGENTGUARD_CORS_ORIGINS")
        if cors_origins is not None:
            raw["cors_origins"] = cors_origins
        return cls.model_validate(raw)
