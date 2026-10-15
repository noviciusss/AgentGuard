"""Durable audit and fallback redaction coverage."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from agentguard_server.audit import InMemoryAuditSink, SqlAlchemyAuditSink
from agentguard_server.models import AuditRecord, Base
from agentguard_server.security import Principal


def test_sqlalchemy_audit_sink_persists_only_redacted_details() -> None:
    with TemporaryDirectory() as directory:
        engine = create_engine(f"sqlite+pysqlite:///{Path(directory) / 'db.sqlite'}")
        Base.metadata.create_all(engine)

        sink = SqlAlchemyAuditSink(lambda: Session(engine), InMemoryAuditSink())
        sink.record(
            "POST",
            "request-1",
            Principal(subject="ci"),
            201,
            {"authorization": "Bearer secret", "path": "/api/v1/scans"},
        )

        with Session(engine) as session:
            record = session.scalar(select(AuditRecord))
            assert record is not None
            assert record.details["authorization"] == "[REDACTED]"
