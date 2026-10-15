"""Declarative persistence models for scan history and platform metadata."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all server persistence models."""


class ScanStatus(str, Enum):
    """Lifecycle state reported for a scan."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Repository(Base):
    """A source-code repository known to AgentGuard."""

    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("provider", "full_name", name="uq_repositories_provider_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="github")
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    badge_public: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    branches: Mapped[list[Branch]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    commits: Mapped[list[Commit]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    scans: Mapped[list[Scan]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    baselines: Mapped[list[Baseline]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    configuration_versions: Mapped[list[ConfigurationVersion]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class Branch(Base):
    """A named branch belonging to a repository."""

    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("repository_id", "name", name="uq_branches_repository_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    repository: Mapped[Repository] = relationship(back_populates="branches")
    scans: Mapped[list[Scan]] = relationship(back_populates="branch")


class Commit(Base):
    """A commit associated with a repository."""

    __tablename__ = "commits"
    __table_args__ = (
        UniqueConstraint("repository_id", "sha", name="uq_commits_repository_sha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    sha: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1000))
    authored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    repository: Mapped[Repository] = relationship(back_populates="commits")
    scans: Mapped[list[Scan]] = relationship(back_populates="commit")


class Scan(Base):
    """One deterministic analysis run submitted by a CI client."""

    __tablename__ = "scans"
    __table_args__ = (
        UniqueConstraint("scan_key", name="uq_scans_scan_key"),
        Index("ix_scans_created_at_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_key: Mapped[str] = mapped_column(String(255), nullable=False)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id"))
    commit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("commits.id"))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScanStatus.COMPLETED.value
    )
    analyzer_version: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    repository: Mapped[Repository] = relationship(back_populates="scans")
    branch: Mapped[Branch | None] = relationship(back_populates="scans")
    commit: Mapped[Commit | None] = relationship(back_populates="scans")
    findings: Mapped[list[Finding]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", order_by="Finding.id"
    )


class Finding(Base):
    """A finding emitted by one scan, identified by its stable fingerprint."""

    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("scan_id", "fingerprint", name="uq_findings_scan_fingerprint"),
        Index("ix_findings_rule_id", "rule_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    why: Mapped[str] = mapped_column(String(2000), nullable=False)
    suggestion: Mapped[str] = mapped_column(String(2000), nullable=False)
    file: Mapped[str] = mapped_column(String(1000), nullable=False)
    line: Mapped[int] = mapped_column(nullable=False)
    col: Mapped[int] = mapped_column(nullable=False)
    end_line: Mapped[int] = mapped_column(nullable=False)
    end_col: Mapped[int] = mapped_column(nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    scan: Mapped[Scan] = relationship(back_populates="findings")


class Baseline(Base):
    """A named set of accepted finding fingerprints for a repository."""

    __tablename__ = "baselines"
    __table_args__ = (
        UniqueConstraint("repository_id", "name", name="uq_baselines_repository_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprints: Mapped[list[object]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    repository: Mapped[Repository] = relationship(back_populates="baselines")


class Plugin(Base):
    """A plugin version registered with the platform."""

    __tablename__ = "plugins"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_plugins_name_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_point: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class ConfigurationVersion(Base):
    """An immutable version of repository scan configuration."""

    __tablename__ = "configuration_versions"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "version", name="uq_config_versions_repository_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    repository: Mapped[Repository] = relationship(
        back_populates="configuration_versions"
    )


class WebhookDelivery(Base):
    """Durable GitHub delivery claim used for replay protection."""

    __tablename__ = "webhook_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class AuditRecord(Base):
    """Sanitized record of an API action and its outcome."""

    __tablename__ = "audit_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
