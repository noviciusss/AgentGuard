"""Explicit scan-retention helpers for operators and scheduled jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from agentguard_server.models import Scan


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Validated retention configuration expressed in days."""

    scan_days: int = 90

    def __post_init__(self) -> None:
        if self.scan_days < 1:
            raise ValueError("scan_days must be positive")

    def cutoff(self, now: datetime | None = None) -> datetime:
        """Return the timezone-aware cutoff for scan deletion."""
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        return reference - timedelta(days=self.scan_days)


def purge_scans(
    session: Session,
    policy: RetentionPolicy,
    *,
    now: datetime | None = None,
    repository_id: UUID | None = None,
) -> int:
    """Delete old scan history and return the number of removed scans."""
    statement = select(Scan).where(Scan.created_at < policy.cutoff(now))
    if repository_id is not None:
        statement = statement.where(Scan.repository_id == repository_id)
    scans = list(session.scalars(statement).all())
    for scan in scans:
        session.delete(scan)
    session.commit()
    return len(scans)
