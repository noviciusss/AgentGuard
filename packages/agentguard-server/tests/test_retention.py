"""Retention policy behavior on an isolated SQLAlchemy database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentguard_server.models import Base, Repository, Scan
from agentguard_server.retention import RetentionPolicy, purge_scans


def test_retention_purges_only_expired_scans() -> None:
    with TemporaryDirectory() as directory:
        engine = create_engine(f"sqlite+pysqlite:///{Path(directory) / 'db.sqlite'}")
        Base.metadata.create_all(engine)
        now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        with Session(engine) as session:
            repository = Repository(provider="github", full_name="acme/demo")
            session.add(repository)
            session.flush()
            old = Scan(
                scan_key="old",
                repository_id=repository.id,
                status="completed",
                analyzer_version="0.1.0",
                created_at=now - timedelta(days=31),
                details={},
            )
            current = Scan(
                scan_key="current",
                repository_id=repository.id,
                status="completed",
                analyzer_version="0.1.0",
                created_at=now - timedelta(days=1),
                details={},
            )
            session.add_all([old, current])
            session.commit()
            assert purge_scans(session, RetentionPolicy(scan_days=30), now=now) == 1
            assert session.get(Scan, old.id) is None
            assert session.get(Scan, current.id) is not None
