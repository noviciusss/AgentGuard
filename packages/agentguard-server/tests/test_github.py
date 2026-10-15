"""Tests for GitHub webhook authentication and pull-request normalization."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping

import pytest

from agentguard_server.github import (
    GitHubWebhookConfig,
    InMemoryDeliveryReplayStore,
    InvalidSignatureError,
    MalformedPayloadError,
    ReplayDetectedError,
    UnsupportedEventError,
    make_idempotency_key,
    parse_pull_request_event,
    process_pull_request_webhook,
    verify_github_signature,
    verify_signature,
)

SECRET = "test-webhook-secret"
CONFIG = GitHubWebhookConfig(webhook_secret=SECRET)


def _payload(
    *,
    action: str = "opened",
    repository: str = "acme/agent",
    number: int = 42,
    head_sha: str = "ABC123",
) -> bytes:
    return json.dumps(
        {
            "action": action,
            "number": 99,
            "repository": {"full_name": repository},
            "pull_request": {
                "number": number,
                "head": {"sha": head_sha},
            },
        },
        separators=(",", ":"),
    ).encode()


def _signature(payload: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _headers(
    payload: bytes,
    *,
    event_name: str = "pull_request",
    delivery_id: str = "delivery-1",
) -> Mapping[str, str]:
    return {
        "X-Hub-Signature-256": _signature(payload),
        "X-GitHub-Event": event_name,
        "X-GitHub-Delivery": delivery_id,
    }


def test_valid_signature_uses_raw_payload_and_configuration_secret() -> None:
    payload = b'{"action":"opened"}'
    signature = _signature(payload)

    assert verify_signature(payload, signature, SECRET)
    assert verify_github_signature(payload, signature, CONFIG)


@pytest.mark.parametrize(
    "signature",
    [
        "sha256=" + "0" * 64,
        "sha1=" + "0" * 40,
        "sha256=not-hex",
        "",
    ],
)
def test_invalid_signatures_are_rejected(signature: str) -> None:
    payload = b'{"action":"opened"}'

    assert not verify_signature(payload, signature, SECRET)


def test_configuration_requires_a_secret() -> None:
    with pytest.raises(ValueError, match="webhook_secret"):
        GitHubWebhookConfig(webhook_secret="")

    with pytest.raises(ValueError, match="missing GitHub webhook secret"):
        GitHubWebhookConfig.from_mapping({})


def test_signed_delivery_is_claimed_once_and_replay_is_rejected() -> None:
    payload = _payload()
    headers = _headers(payload)
    store = InMemoryDeliveryReplayStore()

    first = process_pull_request_webhook(payload, headers, CONFIG, store)

    assert first.delivery_id == "delivery-1"
    with pytest.raises(ReplayDetectedError, match="already been processed"):
        process_pull_request_webhook(payload, headers, CONFIG, store)


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
def test_supported_pull_request_actions_are_normalized(action: str) -> None:
    payload = _payload(action=action)

    event = parse_pull_request_event(payload, "pull_request", "delivery-1")

    assert event.action == action
    assert event.repository == "acme/agent"
    assert event.pull_request_number == 42
    assert event.head_sha == "ABC123"
    assert event.idempotency_key.startswith("github-pr-")


def test_unsupported_event_and_action_are_rejected() -> None:
    payload = _payload()

    with pytest.raises(UnsupportedEventError, match="unsupported GitHub event"):
        parse_pull_request_event(payload, "push")
    with pytest.raises(UnsupportedEventError, match="unsupported pull-request action"):
        parse_pull_request_event(_payload(action="closed"), "pull_request")


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        b'{"action":"opened"}',
        b'{"action":"opened","repository":{},"pull_request":{}}',
        b'{"action":"opened","repository":{"full_name":"acme/agent"},'
        b'"pull_request":{"number":0,"head":{"sha":"abc"}}}',
    ],
)
def test_malformed_payloads_are_rejected(payload: bytes) -> None:
    with pytest.raises(MalformedPayloadError):
        parse_pull_request_event(payload, "pull_request")


def test_process_rejects_invalid_signature_before_payload_processing() -> None:
    payload = _payload()
    headers = dict(_headers(payload))
    headers["X-Hub-Signature-256"] = "sha256=" + "0" * 64

    with pytest.raises(InvalidSignatureError):
        process_pull_request_webhook(
            payload, headers, CONFIG, InMemoryDeliveryReplayStore()
        )


def test_idempotency_keys_are_deterministic_and_normalized() -> None:
    first = make_idempotency_key("Acme/Agent", 42, "ABC123", "opened")
    second = make_idempotency_key("acme/agent", 42, "abc123", "opened")
    different_action = make_idempotency_key("acme/agent", 42, "abc123", "reopened")

    assert first == second
    assert first != different_action
    assert len(first) == len("github-pr-") + 64
