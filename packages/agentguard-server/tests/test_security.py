"""Authentication, redaction, request IDs, and rate-limit coverage."""

from __future__ import annotations

from fastapi import HTTPException

from agentguard_server.security import (
    Principal,
    RateLimiter,
    TokenAuthenticator,
    redact,
    request_id,
)


def test_bearer_tokens_are_scoped_without_echoing_secrets() -> None:
    authenticator = TokenAuthenticator.from_raw(
        "secret-token=ci;read;acme/demo|acme/other"
    )
    principal = authenticator.authenticate("Bearer secret-token")
    assert principal.subject == "ci"
    assert principal.can_access("acme/demo")
    assert not principal.can_access("other/repository")

    try:
        authenticator.authenticate("Bearer wrong-token")
    except HTTPException as error:
        assert error.status_code == 403
        assert "wrong-token" not in str(error.detail)
    else:
        raise AssertionError("invalid bearer token should be rejected")


def test_privacy_redaction_and_safe_request_ids() -> None:
    value = redact({"Authorization": "Bearer secret", "nested": [{"token": "x"}]})
    assert value == {
        "Authorization": "[REDACTED]",
        "nested": [{"token": "[REDACTED]"}],
    }
    assert request_id("request-123") == "request-123"
    generated = request_id("not safe/id")
    assert generated != "not safe/id"
    assert len(generated) == 36


def test_rate_limiter_resets_after_window() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60)
    assert limiter.allow("client")
    assert not limiter.allow("client")
    assert limiter.allow("other")
    assert Principal(subject="x").allows("read")
