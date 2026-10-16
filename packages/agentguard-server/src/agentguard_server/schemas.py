"""Pydantic request and response contracts for the versioned API."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScanStatus(str, Enum):
    """Accepted scan lifecycle values."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RepositoryInput(BaseModel):
    """Repository identity supplied by a scan client."""

    provider: str = Field(
        default="github", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$"
    )
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Accept provider names, not URLs or path traversal strings."""
        if (
            value != value.strip()
            or "\\" in value
            or value.startswith("/")
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or len(value.split("/")) != 2
        ):
            raise ValueError("full_name must be an owner/name identifier")
        return value


class CommitInput(BaseModel):
    """Commit identity and optional source-control metadata."""

    sha: str = Field(min_length=1, max_length=128)
    message: str | None = Field(default=None, max_length=1000)
    authored_at: datetime | None = None


class FindingInput(BaseModel):
    """One serialized AgentGuard finding."""

    fingerprint: str = Field(min_length=1, max_length=128)
    rule_id: str = Field(min_length=1, max_length=32)
    severity: Literal["error", "warning", "info"]
    confidence: Literal["high", "medium", "low"]
    message: str = Field(min_length=1, max_length=2000)
    why: str = Field(min_length=1, max_length=2000)
    suggestion: str = Field(min_length=1, max_length=2000)
    file: str = Field(min_length=1, max_length=1000)
    line: int = Field(ge=1)
    col: int = Field(ge=0)
    end_line: int = Field(ge=1)
    end_col: int = Field(ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("file")
    @classmethod
    def validate_file(cls, value: str) -> str:
        """Keep persisted source references relative to the scanned root."""
        if (
            value != value.strip()
            or value.startswith("/")
            or "\\" in value
            or any(part == ".." for part in value.split("/"))
        ):
            raise ValueError("file must be a relative POSIX path")
        return value

    @model_validator(mode="after")
    def validate_location(self) -> FindingInput:
        """Require a non-inverted source range."""
        if self.end_line < self.line or (
            self.end_line == self.line and self.end_col < self.col
        ):
            raise ValueError("finding location range is inverted")
        return self


class ScanIngestRequest(BaseModel):
    """Payload accepted by ``POST /api/v1/scans``."""

    scan_key: str = Field(min_length=1, max_length=255)
    repository: RepositoryInput
    branch: str = Field(min_length=1, max_length=255)
    commit: CommitInput
    status: ScanStatus = ScanStatus.COMPLETED
    analyzer_version: str = Field(min_length=1, max_length=128)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    findings: list[FindingInput] = Field(default_factory=list, max_length=10_000)

    @model_validator(mode="after")
    def fingerprints_are_unique(self) -> ScanIngestRequest:
        """Reject duplicate finding identities before the database transaction."""
        fingerprints = [finding.fingerprint for finding in self.findings]
        if len(fingerprints) != len(set(fingerprints)):
            raise ValueError("findings must contain unique fingerprints")
        return self


class FindingResponse(BaseModel):
    """Finding returned by the server."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fingerprint: str
    rule_id: str
    severity: str
    confidence: str
    message: str
    why: str
    suggestion: str
    file: str
    line: int
    col: int
    end_line: int
    end_col: int
    metadata: dict[str, object]


class ScanSummary(BaseModel):
    """Stable, compact representation used by scan listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_key: str
    repository_id: uuid.UUID
    branch_id: uuid.UUID | None
    commit_id: uuid.UUID | None
    status: str
    analyzer_version: str
    finding_count: int
    created_at: datetime


class ScanResponse(ScanSummary):
    """Full scan response returned after ingestion."""

    findings: list[FindingResponse]


class ScanPage(BaseModel):
    """Deterministic page of scan summaries."""

    items: list[ScanSummary]
    page: int
    page_size: int
    total: int
    pages: int


class RepositorySummary(BaseModel):
    """Repository summary exposed to authorized dashboard clients."""

    id: uuid.UUID
    provider: str
    full_name: str
    default_branch: str | None
    finding_count: int
    risk_score: int | None
    updated_at: datetime | None
    latest_scan: ScanSummary | None


class TrendPoint(BaseModel):
    """Aggregate finding trend point with no source-level data."""

    date: str
    finding_count: int
    error_count: int
    scan_count: int


class RepositoryPage(BaseModel):
    """Deterministically paginated repository summaries."""

    items: list[RepositorySummary]
    page: int
    page_size: int
    total: int
    pages: int


class RepositoryDetail(BaseModel):
    """Repository dashboard contract."""

    repository: RepositorySummary
    trend: list[TrendPoint]
    scans: ScanPage
    recent_findings: list[FindingResponse]
    baseline: dict[str, object] | None
    pull_requests: list[dict[str, object]]


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str
    service: str
