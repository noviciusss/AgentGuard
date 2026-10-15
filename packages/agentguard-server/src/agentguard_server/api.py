"""Versioned HTTP routes for health checks and scan history."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from agentguard_server.db import SessionFactory
from agentguard_server.models import Branch, Commit, Finding, Repository, Scan
from agentguard_server.schemas import (
    FindingResponse,
    HealthResponse,
    RepositoryDetail,
    RepositoryPage,
    RepositorySummary,
    ScanIngestRequest,
    ScanPage,
    ScanResponse,
    ScanSummary,
    TrendPoint,
)
from agentguard_server.security import (
    Principal,
    require_read_access,
    require_write_access,
)

router = APIRouter()
v1_router = APIRouter(prefix="/api/v1")
ReadPrincipal = Annotated[Principal, Depends(require_read_access)]
WritePrincipal = Annotated[Principal, Depends(require_write_access)]


def get_session(request: Request) -> Iterator[Session]:
    """Yield one transaction-scoped synchronous session per request."""
    factory = cast(SessionFactory, request.app.state.session_factory)
    with factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


@router.get("/health/live", response_model=HealthResponse)
@router.get("/healthz", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Report that the application process is serving requests."""
    return HealthResponse(status="ok", service="agentguard-server")


@router.get("/health/ready", response_model=HealthResponse)
@router.get("/readyz", response_model=HealthResponse)
def readiness(
    session: Annotated[Session, Depends(get_session)],
) -> HealthResponse:
    """Report readiness only when the configured database accepts a query."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database is not ready",
        ) from error
    return HealthResponse(status="ok", service="agentguard-server")


def _finding_response(finding: Finding) -> FindingResponse:
    return FindingResponse(
        id=finding.id,
        fingerprint=finding.fingerprint,
        rule_id=finding.rule_id,
        severity=finding.severity,
        confidence=finding.confidence,
        message=finding.message,
        why=finding.why,
        suggestion=finding.suggestion,
        file=finding.file,
        line=finding.line,
        col=finding.col,
        end_line=finding.end_line,
        end_col=finding.end_col,
        metadata=finding.details,
    )


def _scan_summary(scan: Scan) -> ScanSummary:
    return ScanSummary(
        id=scan.id,
        scan_key=scan.scan_key,
        repository_id=scan.repository_id,
        branch_id=scan.branch_id,
        commit_id=scan.commit_id,
        status=scan.status,
        analyzer_version=scan.analyzer_version,
        finding_count=len(scan.findings),
        created_at=scan.created_at,
    )


def _scan_response(scan: Scan) -> ScanResponse:
    summary = _scan_summary(scan)
    return ScanResponse(
        **summary.model_dump(),
        findings=[_finding_response(finding) for finding in scan.findings],
    )


def _load_scan(session: Session, scan_id: uuid.UUID) -> Scan | None:
    statement = (
        select(Scan).options(selectinload(Scan.findings)).where(Scan.id == scan_id)
    )
    return session.scalar(statement)


def _find_or_create_repository(
    session: Session, payload: ScanIngestRequest
) -> Repository:
    repository = session.scalar(
        select(Repository).where(
            Repository.provider == payload.repository.provider,
            Repository.full_name == payload.repository.full_name,
        )
    )
    if repository is not None:
        return repository
    repository = Repository(
        provider=payload.repository.provider,
        full_name=payload.repository.full_name,
    )
    session.add(repository)
    session.flush()
    return repository


def _find_or_create_branch(
    session: Session, repository: Repository, payload: ScanIngestRequest
) -> Branch:
    branch = session.scalar(
        select(Branch).where(
            Branch.repository_id == repository.id,
            Branch.name == payload.branch,
        )
    )
    if branch is not None:
        return branch
    branch = Branch(repository_id=repository.id, name=payload.branch)
    session.add(branch)
    session.flush()
    return branch


def _find_or_create_commit(
    session: Session, repository: Repository, payload: ScanIngestRequest
) -> Commit:
    commit = session.scalar(
        select(Commit).where(
            Commit.repository_id == repository.id,
            Commit.sha == payload.commit.sha,
        )
    )
    if commit is not None:
        return commit
    commit = Commit(
        repository_id=repository.id,
        sha=payload.commit.sha,
        message=payload.commit.message,
        authored_at=payload.commit.authored_at,
    )
    session.add(commit)
    session.flush()
    return commit


def _new_scan(
    repository: Repository,
    branch: Branch,
    commit: Commit,
    payload: ScanIngestRequest,
) -> Scan:
    scan = Scan(
        scan_key=payload.scan_key,
        repository_id=repository.id,
        branch_id=branch.id,
        commit_id=commit.id,
        status=payload.status.value,
        analyzer_version=payload.analyzer_version,
        started_at=payload.started_at,
        completed_at=payload.completed_at,
        details=payload.metadata,
    )
    scan.findings = [
        Finding(
            fingerprint=finding.fingerprint,
            rule_id=finding.rule_id,
            severity=finding.severity,
            confidence=finding.confidence,
            message=finding.message,
            why=finding.why,
            suggestion=finding.suggestion,
            file=finding.file,
            line=finding.line,
            col=finding.col,
            end_line=finding.end_line,
            end_col=finding.end_col,
            details=finding.metadata,
        )
        for finding in payload.findings
    ]
    return scan


@v1_router.post(
    "/scans",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_scan(
    payload: ScanIngestRequest,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    principal: WritePrincipal,
) -> ScanResponse:
    """Ingest a scan once and return the persisted scan and findings."""
    if principal.authenticated and not principal.can_access(
        payload.repository.full_name
    ):
        raise HTTPException(status_code=404, detail="repository not found")
    existing = session.scalar(
        select(Scan)
        .options(selectinload(Scan.findings))
        .where(Scan.scan_key == payload.scan_key)
    )
    if existing is not None:
        existing_repository = session.get(Repository, existing.repository_id)
        if existing_repository is None or (
            existing_repository.provider != payload.repository.provider
            or existing_repository.full_name != payload.repository.full_name
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="scan_key is already used by another repository",
            )
        if principal.authenticated and not principal.can_access(
            existing_repository.full_name
        ):
            raise HTTPException(status_code=404, detail="repository not found")
        response.status_code = status.HTTP_200_OK
        return _scan_response(existing)

    try:
        repository = _find_or_create_repository(session, payload)
        branch = _find_or_create_branch(session, repository, payload)
        commit = _find_or_create_commit(session, repository, payload)
        scan = _new_scan(repository, branch, commit, payload)
        session.add(scan)
        session.flush()
        scan_id = scan.id
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(Scan)
            .options(selectinload(Scan.findings))
            .where(Scan.scan_key == payload.scan_key)
        )
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="scan could not be created because of a uniqueness conflict",
            ) from None
        response.status_code = status.HTTP_200_OK
        return _scan_response(existing)

    persisted = _load_scan(session, scan_id)
    if persisted is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="created scan could not be loaded",
        )
    return _scan_response(persisted)


@v1_router.get(
    "/scans",
    response_model=ScanPage,
    dependencies=[Depends(require_read_access)],
)
def list_scans(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ScanPage:
    """List scans with deterministic created-time and UUID tie-breaking."""
    total = session.scalar(select(func.count()).select_from(Scan)) or 0
    statement = (
        select(Scan)
        .options(selectinload(Scan.findings))
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    scans = list(session.scalars(statement).all())
    pages = math.ceil(total / page_size) if total else 0
    return ScanPage(
        items=[_scan_summary(scan) for scan in scans],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


def _repository_summary(session: Session, repository: Repository) -> RepositorySummary:
    """Build an aggregate repository summary from its latest scan."""
    latest = session.scalar(
        select(Scan)
        .options(selectinload(Scan.findings), selectinload(Scan.branch))
        .where(Scan.repository_id == repository.id)
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .limit(1)
    )
    findings = latest.findings if latest is not None else []
    weighted_score = min(
        100,
        sum(
            20
            if finding.severity == "error"
            else 5
            if finding.severity == "warning"
            else 1
            for finding in findings
        ),
    )
    return RepositorySummary(
        id=repository.id,
        provider=repository.provider,
        full_name=repository.full_name,
        default_branch=latest.branch.name if latest and latest.branch else None,
        finding_count=len(findings),
        risk_score=weighted_score if latest is not None else None,
        updated_at=repository.updated_at,
        latest_scan=_scan_summary(latest) if latest is not None else None,
    )


def _assert_repository_access(principal: Principal, repository: Repository) -> None:
    """Enforce repository scope without exposing whether another tenant exists."""
    if principal.authenticated and not principal.can_access(repository.full_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="repository not found"
        )


def _page_count(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0


@v1_router.get("/repositories", response_model=RepositoryPage)
def list_repositories(
    principal: ReadPrincipal,
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RepositoryPage:
    """List only repositories visible to the authenticated principal."""
    repositories = list(
        session.scalars(
            select(Repository).order_by(Repository.full_name.asc(), Repository.id.asc())
        ).all()
    )
    visible = [
        repository
        for repository in repositories
        if not principal.authenticated or principal.can_access(repository.full_name)
    ]
    start = (page - 1) * page_size
    items = visible[start : start + page_size]
    return RepositoryPage(
        items=[_repository_summary(session, repository) for repository in items],
        page=page,
        page_size=page_size,
        total=len(visible),
        pages=_page_count(len(visible), page_size),
    )


@v1_router.get("/repositories/{repository_id}", response_model=RepositoryDetail)
def get_repository(
    repository_id: uuid.UUID,
    principal: ReadPrincipal,
    session: Annotated[Session, Depends(get_session)],
) -> RepositoryDetail:
    """Return repository aggregates, history, and recent findings."""
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    _assert_repository_access(principal, repository)
    scans = list(
        session.scalars(
            select(Scan)
            .options(selectinload(Scan.findings))
            .where(Scan.repository_id == repository.id)
            .order_by(Scan.created_at.desc(), Scan.id.desc())
        ).all()
    )
    trend = [
        TrendPoint(
            date=(scan.created_at or datetime.now(timezone.utc)).date().isoformat(),
            finding_count=len(scan.findings),
            error_count=sum(finding.severity == "error" for finding in scan.findings),
            scan_count=1,
        )
        for scan in reversed(scans[:20])
    ]
    latest_findings = scans[0].findings if scans else []
    scan_page = ScanPage(
        items=[_scan_summary(scan) for scan in scans[:20]],
        page=1,
        page_size=20,
        total=len(scans),
        pages=_page_count(len(scans), 20),
    )
    return RepositoryDetail(
        repository=_repository_summary(session, repository),
        trend=trend,
        scans=scan_page,
        recent_findings=[
            _finding_response(finding) for finding in latest_findings[:50]
        ],
        baseline=None,
        pull_requests=[],
    )


@v1_router.get("/repositories/{repository_id}/scans", response_model=ScanPage)
def list_repository_scans(
    repository_id: uuid.UUID,
    principal: ReadPrincipal,
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ScanPage:
    """List scan summaries for one authorized repository."""
    repository = session.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    _assert_repository_access(principal, repository)
    total = (
        session.scalar(
            select(func.count())
            .select_from(Scan)
            .where(Scan.repository_id == repository.id)
        )
        or 0
    )
    scans = list(
        session.scalars(
            select(Scan)
            .options(selectinload(Scan.findings))
            .where(Scan.repository_id == repository.id)
            .order_by(Scan.created_at.desc(), Scan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return ScanPage(
        items=[_scan_summary(scan) for scan in scans],
        page=page,
        page_size=page_size,
        total=total,
        pages=_page_count(total, page_size),
    )


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail=f"SARIF {name} must be an object")
    return value


def _integer(value: object, default: int, name: str) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=422, detail=f"SARIF {name} must be an integer")
    return value


def _sarif_payload_to_request(
    payload: object,
    *,
    scan_key: str,
    repository: str,
    branch: str,
    commit_sha: str,
    analyzer_version: str,
) -> ScanIngestRequest:
    """Convert a bounded SARIF document into the normal ingestion contract."""
    root = _object(payload, "document")
    runs = root.get("runs")
    if not isinstance(runs, list) or not runs:
        raise HTTPException(status_code=422, detail="SARIF document must contain runs")
    findings: list[dict[str, object]] = []
    for run in runs:
        run_object = _object(run, "run")
        results = run_object.get("results", [])
        if not isinstance(results, list):
            raise HTTPException(status_code=422, detail="SARIF results must be a list")
        for result in results:
            result_object = _object(result, "result")
            rule_id = str(result_object.get("ruleId", "AG000"))
            message_object = _object(result_object.get("message", {}), "message")
            message = str(message_object.get("text", "AgentGuard finding"))
            level = str(result_object.get("level", "warning")).lower()
            severity = (
                "error"
                if level == "error"
                else "info"
                if level in {"note", "info"}
                else "warning"
            )
            locations = result_object.get("locations", [])
            location = (
                _object(locations[0], "location")
                if isinstance(locations, list) and locations
                else {}
            )
            physical = _object(location.get("physicalLocation", {}), "physicalLocation")
            artifact = _object(physical.get("artifactLocation", {}), "artifactLocation")
            region = _object(physical.get("region", {}), "region")
            file_name = str(artifact.get("uri", "unknown"))
            line = _integer(region.get("startLine"), 1, "startLine")
            col = max(0, _integer(region.get("startColumn"), 1, "startColumn") - 1)
            end_line = _integer(region.get("endLine"), line, "endLine")
            end_col = max(
                col,
                _integer(region.get("endColumn"), col + 1, "endColumn") - 1,
            )
            fingerprint = hashlib.sha256(
                f"{rule_id}|{file_name}|{line}|{message}".encode()
            ).hexdigest()[:16]
            findings.append(
                {
                    "fingerprint": fingerprint,
                    "rule_id": rule_id,
                    "severity": severity,
                    "confidence": "medium",
                    "message": message,
                    "why": "Imported from SARIF scan output.",
                    "suggestion": (
                        "Review the rule documentation and remediate the finding."
                    ),
                    "file": file_name,
                    "line": line,
                    "col": col,
                    "end_line": end_line,
                    "end_col": end_col,
                }
            )
    return ScanIngestRequest.model_validate(
        {
            "scan_key": scan_key,
            "repository": {"provider": "github", "full_name": repository},
            "branch": branch,
            "commit": {"sha": commit_sha},
            "analyzer_version": analyzer_version,
            "findings": findings,
        }
    )


@v1_router.post("/scans/sarif", response_model=ScanResponse, status_code=201)
async def ingest_sarif(
    request: Request,
    response: Response,
    principal: WritePrincipal,
    session: Annotated[Session, Depends(get_session)],
    scan_key: str = Query(min_length=1, max_length=255),
    repository: str = Query(min_length=1, max_length=255),
    branch: str = Query(default="main", min_length=1, max_length=255),
    commit_sha: str = Query(min_length=1, max_length=128),
    analyzer_version: str = Query(default="unknown", min_length=1, max_length=128),
) -> ScanResponse:
    """Accept a SARIF upload and route it through idempotent JSON ingestion."""
    try:
        raw = await request.body()
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=422, detail="request body is not valid JSON"
        ) from error
    try:
        payload = _sarif_payload_to_request(
            document,
            scan_key=scan_key,
            repository=repository,
            branch=branch,
            commit_sha=commit_sha,
            analyzer_version=analyzer_version,
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail="SARIF finding is invalid") from error
    return ingest_scan(payload, response, session, principal)


@v1_router.get("/scans/{scan_id}", response_model=ScanResponse)
def get_scan(
    scan_id: uuid.UUID,
    principal: ReadPrincipal,
    session: Annotated[Session, Depends(get_session)],
) -> ScanResponse:
    """Return one authorized scan and its findings."""
    scan = _load_scan(session, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")
    repository = session.get(Repository, scan.repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="scan not found")
    _assert_repository_access(principal, repository)
    return _scan_response(scan)
