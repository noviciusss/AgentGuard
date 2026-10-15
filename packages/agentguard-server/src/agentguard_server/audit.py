"""Redacted, injectable audit event sink for server actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Final

from sqlalchemy.exc import SQLAlchemyError

from agentguard_server.db import SessionFactory
from agentguard_server.models import AuditRecord
from agentguard_server.security import Principal, redact

_MAX_DETAIL_TEXT: Final[int] = 4_000


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One sanitized request or domain action record."""

    action: str
    request_id: str
    subject: str
    status_code: int
    created_at: datetime
    details: object


class InMemoryAuditSink:
    """Bounded process-local sink used by development and tests.

    Production deployments can replace this sink with a database or log sink
    without changing route behavior. The sink never stores authorization data.
    """

    def __init__(self, max_events: int = 10_000) -> None:
        if max_events < 1:
            raise ValueError("max_events must be positive")
        self._max_events = max_events
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(
        self,
        action: str,
        request_id: str,
        principal: Principal,
        status_code: int,
        details: object = None,
    ) -> None:
        """Record a redacted event and retain only the newest events."""
        safe_details = redact(details)
        if len(repr(safe_details)) > _MAX_DETAIL_TEXT:
            safe_details = "[TRUNCATED]"
        event = AuditEvent(
            action=action,
            request_id=request_id,
            subject=principal.subject,
            status_code=status_code,
            created_at=datetime.now(timezone.utc),
            details=safe_details,
        )
        with self._lock:
            self._events.append(event)
            del self._events[: max(0, len(self._events) - self._max_events)]

    def snapshot(self) -> tuple[AuditEvent, ...]:
        """Return a stable copy for tests and administrative exporters."""
        with self._lock:
            return tuple(self._events)


class SqlAlchemyAuditSink:
    """Durable audit sink with a bounded in-memory fallback before migration."""

    def __init__(self, factory: SessionFactory, fallback: InMemoryAuditSink) -> None:
        self._factory = factory
        self._fallback = fallback

    def record(
        self,
        action: str,
        request_id: str,
        principal: Principal,
        status_code: int,
        details: object = None,
    ) -> None:
        safe_details = redact(details)
        if not isinstance(safe_details, dict):
            safe_details = {"value": safe_details}
        try:
            with self._factory() as session:
                session.add(
                    AuditRecord(
                        action=action,
                        request_id=request_id,
                        subject=principal.subject,
                        status_code=status_code,
                        details=safe_details,
                    )
                )
                session.commit()
        except SQLAlchemyError:
            self._fallback.record(
                action, request_id, principal, status_code, safe_details
            )
