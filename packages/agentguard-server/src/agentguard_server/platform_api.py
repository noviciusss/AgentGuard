"""HTTP endpoints for badges and GitHub App webhook intake."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agentguard_server.badges import (
    BadgeFormat,
    BadgeMediaType,
    BadgeVisibility,
    FindingCounts,
    build_badge_response,
)
from agentguard_server.db import SessionFactory
from agentguard_server.github import (
    GitHubWebhookConfig,
    GitHubWebhookError,
    PullRequestEvent,
    SqlAlchemyDeliveryReplayStore,
    process_pull_request_webhook,
)
from agentguard_server.models import (
    Branch,
    Commit,
    Repository,
    Scan,
    WebhookDelivery,
)

router = APIRouter()


def _session(request: Request) -> Session:
    """Open a short-lived session for public platform endpoints."""
    factory = cast(SessionFactory, request.app.state.session_factory)
    return factory()


def _queue_pull_request_scan(session: Session, event: PullRequestEvent) -> Scan:
    """Create or return the queued scan represented by a normalized PR event."""
    repository_name = event.repository
    pull_request_number = event.pull_request_number
    head_sha = event.head_sha
    idempotency_key = event.idempotency_key
    existing = session.scalar(select(Scan).where(Scan.scan_key == idempotency_key))
    if existing is not None:
        return existing
    repository = session.scalar(
        select(Repository).where(
            Repository.provider == "github",
            Repository.full_name == repository_name,
        )
    )
    if repository is None:
        repository = Repository(provider="github", full_name=repository_name)
        session.add(repository)
        session.flush()
    branch_name = f"pull/{pull_request_number}"
    branch = session.scalar(
        select(Branch).where(
            Branch.repository_id == repository.id,
            Branch.name == branch_name,
        )
    )
    if branch is None:
        branch = Branch(repository_id=repository.id, name=branch_name)
        session.add(branch)
        session.flush()
    commit = session.scalar(
        select(Commit).where(
            Commit.repository_id == repository.id,
            Commit.sha == head_sha,
        )
    )
    if commit is None:
        commit = Commit(repository_id=repository.id, sha=head_sha)
        session.add(commit)
        session.flush()
    scan = Scan(
        scan_key=idempotency_key,
        repository_id=repository.id,
        branch_id=branch.id,
        commit_id=commit.id,
        status="queued",
        analyzer_version="github-app",
        details={
            "pull_request": pull_request_number,
            "head_sha": head_sha,
            "source": "github-webhook",
        },
    )
    session.add(scan)
    session.flush()
    return scan


@router.get("/api/v1/badges/{repository_id}.{format}")
def repository_badge(
    repository_id: uuid.UUID,
    format: str,
    request: Request,
) -> Response:
    """Render a privacy-safe repository risk badge."""
    if format not in {"svg", "json"}:
        raise HTTPException(status_code=404, detail="badge format not found")
    settings = request.app.state.settings
    if not settings.public_badges:
        raise HTTPException(status_code=404, detail="badge not found")
    with _session(request) as session:
        repository = session.get(Repository, repository_id)
        if repository is None or not repository.badge_public:
            raise HTTPException(status_code=404, detail="badge not found")
        scan = session.scalar(
            select(Scan)
            .options(selectinload(Scan.findings))
            .where(Scan.repository_id == repository.id)
            .order_by(Scan.created_at.desc(), Scan.id.desc())
            .limit(1)
        )
        counts = None
        updated_at = None
        if scan is not None:
            counts = FindingCounts.from_severity_counts(
                {
                    "error": sum(f.severity == "error" for f in scan.findings),
                    "warning": sum(f.severity == "warning" for f in scan.findings),
                    "info": sum(f.severity == "info" for f in scan.findings),
                }
            )
            updated_at = scan.created_at
        badge = build_badge_response(
            counts,
            now=datetime.now(timezone.utc),
            updated_at=updated_at,
            visibility=BadgeVisibility.PUBLIC,
        )
    media_type: BadgeMediaType = (
        "application/json" if format == "json" else "image/svg+xml"
    )
    headers = badge.headers(media_type=media_type)
    if request.headers.get("if-none-match") == badge.etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(
        content=badge.render(cast(BadgeFormat, format)),
        media_type=media_type,
        headers=headers,
    )


@router.post("/api/v1/github/webhook", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(request: Request) -> dict[str, str]:
    """Verify and normalize a GitHub PR event before job scheduling."""
    secret = request.app.state.settings.github_webhook_secret
    if not secret:
        raise HTTPException(status_code=503, detail="GitHub App is not configured")
    config = GitHubWebhookConfig(webhook_secret=secret)
    raw = await request.body()
    with _session(request) as session:
        try:
            event = process_pull_request_webhook(
                raw,
                dict(request.headers),
                config,
                SqlAlchemyDeliveryReplayStore(session),
            )
        except GitHubWebhookError as error:
            session.rollback()
            code = 409 if error.__class__.__name__ == "ReplayDetectedError" else 401
            raise HTTPException(
                status_code=code, detail="invalid GitHub webhook"
            ) from error
        delivery_id = event.delivery_id
        if delivery_id is not None:
            delivery = session.get(WebhookDelivery, delivery_id)
            if delivery is not None:
                delivery.event_name = event.event_name
                delivery.idempotency_key = event.idempotency_key
                delivery.payload_sha256 = hashlib.sha256(raw).hexdigest()
        queued_scan = _queue_pull_request_scan(session, event)
        session.commit()
    return {
        "status": "accepted",
        "idempotency_key": event.idempotency_key,
        "repository": event.repository,
        "head_sha": event.head_sha,
        "scan_id": str(queued_scan.id),
    }
