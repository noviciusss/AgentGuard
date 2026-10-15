"""Pure helpers for authenticating and normalizing GitHub webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Literal, Protocol, cast

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentguard_server.models import WebhookDelivery

PullRequestAction = Literal["opened", "synchronize", "reopened"]
"""Pull-request actions that can start an AgentGuard scan."""

_SUPPORTED_ACTIONS: frozenset[str] = frozenset({"opened", "synchronize", "reopened"})
_SIGNATURE_PREFIX = "sha256="


class GitHubWebhookError(ValueError):
    """Base exception for invalid or unprocessable webhook requests."""


class InvalidSignatureError(GitHubWebhookError):
    """Raised when a webhook signature is absent or does not match."""


class ReplayDetectedError(GitHubWebhookError):
    """Raised when a previously claimed delivery is received again."""


class UnsupportedEventError(GitHubWebhookError):
    """Raised when GitHub sends an event or action this module does not handle."""


class MalformedPayloadError(GitHubWebhookError):
    """Raised when a signed webhook cannot be parsed as a pull-request event."""


@dataclass(frozen=True, slots=True)
class GitHubWebhookConfig:
    """Configuration required to verify GitHub webhook requests."""

    webhook_secret: str

    def __post_init__(self) -> None:
        if not self.webhook_secret:
            raise ValueError("webhook_secret must not be empty")

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, str],
        key: str = "AGENTGUARD_GITHUB_WEBHOOK_SECRET",
    ) -> GitHubWebhookConfig:
        """Build configuration from an application configuration mapping."""
        secret = values.get(key)
        if secret is None:
            raise ValueError(f"missing GitHub webhook secret configuration: {key}")
        return cls(webhook_secret=secret)


class DeliveryReplayStore(Protocol):
    """Atomic store used to claim a GitHub delivery exactly once."""

    def claim(self, delivery_id: str) -> bool:
        """Return ``True`` only for the first claim of ``delivery_id``."""


class InMemoryDeliveryReplayStore:
    """Thread-safe replay store for tests and single-process deployments."""

    def __init__(self) -> None:
        self._claimed: set[str] = set()
        self._lock = Lock()

    def claim(self, delivery_id: str) -> bool:
        """Atomically claim a delivery identifier."""
        if not delivery_id:
            raise ValueError("delivery_id must not be empty")
        with self._lock:
            if delivery_id in self._claimed:
                return False
            self._claimed.add(delivery_id)
            return True


class SqlAlchemyDeliveryReplayStore:
    """Database-backed atomic delivery claim for multi-worker deployments."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(self, delivery_id: str) -> bool:
        """Claim a delivery using the database primary-key constraint."""
        if not delivery_id:
            raise ValueError("delivery_id must not be empty")
        if self._session.get(WebhookDelivery, delivery_id) is not None:
            return False
        self._session.add(
            WebhookDelivery(
                delivery_id=delivery_id,
                event_name="pull_request",
                idempotency_key=delivery_id,
                payload_sha256="",
            )
        )
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            return False
        return True


@dataclass(frozen=True, slots=True)
class PullRequestEvent:
    """Normalized data needed to schedule a pull-request scan."""

    event_name: Literal["pull_request"]
    action: PullRequestAction
    delivery_id: str | None
    repository: str
    pull_request_number: int
    head_sha: str
    idempotency_key: str


def verify_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """Verify GitHub's ``X-Hub-Signature-256`` value for raw request bytes.

    The comparison is constant-time once the header has the expected shape.
    Invalid headers return ``False`` rather than raising so callers can map all
    authentication failures to the same response.
    """
    if not secret or not signature_header.startswith(_SIGNATURE_PREFIX):
        return False

    supplied = signature_header[len(_SIGNATURE_PREFIX) :]
    if len(supplied) != hashlib.sha256().digest_size * 2:
        return False
    try:
        bytes.fromhex(supplied)
    except ValueError:
        return False

    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied.lower())


def verify_github_signature(
    payload: bytes,
    signature_header: str,
    config: GitHubWebhookConfig,
) -> bool:
    """Verify a signature using the secret held by webhook configuration."""
    return verify_signature(payload, signature_header, config.webhook_secret)


def make_idempotency_key(
    repository: str,
    pull_request_number: int,
    head_sha: str,
    action: PullRequestAction,
) -> str:
    """Return a stable scan key for one repository/PR/commit/action tuple."""
    normalized_repository = repository.strip().lower()
    normalized_sha = head_sha.strip().lower()
    if not normalized_repository:
        raise ValueError("repository must not be empty")
    if pull_request_number < 1:
        raise ValueError("pull_request_number must be positive")
    if not normalized_sha:
        raise ValueError("head_sha must not be empty")
    if action not in _SUPPORTED_ACTIONS:
        raise ValueError(f"unsupported pull-request action: {action}")

    identity = json.dumps(
        {
            "action": action,
            "head_sha": normalized_sha,
            "pull_request": pull_request_number,
            "repository": normalized_repository,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"github-pr-{digest}"


def parse_pull_request_event(
    payload: bytes,
    event_name: str,
    delivery_id: str | None = None,
) -> PullRequestEvent:
    """Parse a supported GitHub pull-request webhook into typed event data."""
    if event_name != "pull_request":
        raise UnsupportedEventError(f"unsupported GitHub event: {event_name}")

    try:
        decoded: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MalformedPayloadError("webhook payload is not valid JSON") from error

    root = _as_mapping(decoded, "payload")
    action = _required_string(root, "action")
    if action not in _SUPPORTED_ACTIONS:
        raise UnsupportedEventError(f"unsupported pull-request action: {action}")
    supported_action = cast(PullRequestAction, action)

    repository_data = _required_mapping(root, "repository")
    repository = _required_string(repository_data, "full_name")
    pull_request_data = _required_mapping(root, "pull_request")
    pull_request_number = _required_positive_int(pull_request_data, "number")
    head_data = _required_mapping(pull_request_data, "head")
    head_sha = _required_string(head_data, "sha")

    return PullRequestEvent(
        event_name="pull_request",
        action=supported_action,
        delivery_id=delivery_id,
        repository=repository,
        pull_request_number=pull_request_number,
        head_sha=head_sha,
        idempotency_key=make_idempotency_key(
            repository, pull_request_number, head_sha, supported_action
        ),
    )


def process_pull_request_webhook(
    payload: bytes,
    headers: Mapping[str, str],
    config: GitHubWebhookConfig,
    replay_store: DeliveryReplayStore,
) -> PullRequestEvent:
    """Authenticate, replay-check, and parse a pull-request webhook.

    The delivery is claimed only after signature and payload validation. This
    keeps malformed requests from consuming a delivery identifier while still
    making a successfully parsed event safe to retry exactly once.
    """
    signature = _header(headers, "x-hub-signature-256")
    if signature is None or not verify_github_signature(payload, signature, config):
        raise InvalidSignatureError("invalid GitHub webhook signature")

    event_name = _header(headers, "x-github-event")
    delivery_id = _header(headers, "x-github-delivery")
    if event_name is None:
        raise MalformedPayloadError("missing X-GitHub-Event header")
    if delivery_id is None:
        raise MalformedPayloadError("missing X-GitHub-Delivery header")

    event = parse_pull_request_event(payload, event_name, delivery_id)
    if not replay_store.claim(delivery_id):
        raise ReplayDetectedError(
            f"GitHub delivery has already been processed: {delivery_id}"
        )
    return event


def _header(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            normalized = value.strip()
            return normalized or None
    return None


def _as_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MalformedPayloadError(f"webhook {field_name} must be an object")
    return cast(Mapping[str, object], value)


def _required_mapping(
    parent: Mapping[str, object], field_name: str
) -> Mapping[str, object]:
    value = parent.get(field_name)
    if value is None:
        raise MalformedPayloadError(f"webhook payload is missing {field_name}")
    return _as_mapping(value, field_name)


def _required_string(parent: Mapping[str, object], field_name: str) -> str:
    value = parent.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise MalformedPayloadError(
            f"webhook payload field {field_name} must be a non-empty string"
        )
    return value.strip()


def _required_positive_int(parent: Mapping[str, object], field_name: str) -> int:
    value = parent.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise MalformedPayloadError(
            f"webhook payload field {field_name} must be a positive integer"
        )
    return value
