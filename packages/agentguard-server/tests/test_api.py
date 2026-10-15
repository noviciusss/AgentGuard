"""Focused scan ingestion and pagination tests without a PostgreSQL service."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agentguard_server.api import (
    _sarif_payload_to_request,
    ingest_scan,
    list_scans,
    liveness,
)
from agentguard_server.app import create_app
from agentguard_server.config import ServerSettings
from agentguard_server.models import Base
from agentguard_server.schemas import ScanIngestRequest
from agentguard_server.security import ANONYMOUS

TEST_DATABASE_URL = os.environ.get("AGENTGUARD_TEST_DATABASE_URL")


def _session() -> Session:
    if TEST_DATABASE_URL is None:
        raise RuntimeError("AGENTGUARD_TEST_DATABASE_URL is required")
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return Session(engine)


def _payload(scan_key: str, created_fingerprint: str) -> ScanIngestRequest:
    return ScanIngestRequest.model_validate(
        {
            "scan_key": scan_key,
            "repository": {"provider": "github", "full_name": "acme/demo"},
            "branch": "main",
            "commit": {"sha": "abc123"},
            "analyzer_version": "0.1.0",
            "findings": [
                {
                    "fingerprint": created_fingerprint,
                    "rule_id": "AG003",
                    "severity": "warning",
                    "confidence": "high",
                    "message": "missing timeout",
                    "why": "request may hang",
                    "suggestion": "add a timeout",
                    "file": "agent.py",
                    "line": 4,
                    "col": 0,
                    "end_line": 4,
                    "end_col": 10,
                }
            ],
        }
    )


def test_liveness_does_not_require_a_database() -> None:
    response = liveness()
    assert response.status == "ok"
    assert response.service == "agentguard-server"


def test_scan_ingestion_is_idempotent_and_lists_stably() -> None:
    if TEST_DATABASE_URL is None:
        pytest.skip("set AGENTGUARD_TEST_DATABASE_URL to run PostgreSQL tests")
    with _session() as session:
        first_response = Response()
        first = ingest_scan(
            _payload("scan-1", "fingerprint-1"), first_response, session, ANONYMOUS
        )
        duplicate_response = Response()
        duplicate = ingest_scan(
            _payload("scan-1", "fingerprint-1"), duplicate_response, session, ANONYMOUS
        )

        assert first.id == duplicate.id
        assert first.finding_count == 1
        assert duplicate_response.status_code == 200

        second_payload = _payload("scan-2", "fingerprint-2")
        second_payload = second_payload.model_copy(
            update={
                "completed_at": datetime.now(timezone.utc) + timedelta(seconds=1),
            }
        )
        ingest_scan(second_payload, Response(), session, ANONYMOUS)

        page = list_scans(page=1, page_size=1, session=session)
        assert page.total == 2
        assert page.pages == 2
        assert len(page.items) == 1


def test_scan_request_rejects_duplicate_fingerprints() -> None:
    payload = _payload("scan-duplicate", "same")
    duplicate = payload.model_copy(
        update={"findings": [payload.findings[0], payload.findings[0]]}
    )
    try:
        duplicate.model_validate(duplicate.model_dump())
    except ValueError as error:
        assert "unique fingerprints" in str(error)
    else:
        raise AssertionError("duplicate finding fingerprints should be rejected")


def test_scan_response_ids_are_uuid_values() -> None:
    if TEST_DATABASE_URL is None:
        pytest.skip("set AGENTGUARD_TEST_DATABASE_URL to run PostgreSQL tests")
    with _session() as session:
        response = ingest_scan(
            _payload("scan-uuid", "fp"), Response(), session, ANONYMOUS
        )
    assert isinstance(response.id, uuid.UUID)


def test_sarif_import_maps_results_to_the_ingestion_contract() -> None:
    payload = _sarif_payload_to_request(
        {
            "runs": [
                {
                    "results": [
                        {
                            "ruleId": "AG003",
                            "level": "error",
                            "message": {"text": "missing timeout"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "agent.py"},
                                        "region": {"startLine": 8, "startColumn": 2},
                                    }
                                }
                            ],
                        }
                    ]
                }
            ]
        },
        scan_key="sarif-1",
        repository="acme/demo",
        branch="main",
        commit_sha="abc",
        analyzer_version="0.1.0",
    )
    assert payload.findings[0].rule_id == "AG003"
    assert payload.findings[0].line == 8
    assert payload.findings[0].severity == "error"


@pytest.mark.anyio
async def test_http_ingestion_rejects_invalid_payload_and_returns_health() -> None:
    if TEST_DATABASE_URL is None:
        pytest.skip("set AGENTGUARD_TEST_DATABASE_URL to run PostgreSQL tests")
    if TEST_DATABASE_URL is None:
        raise AssertionError("database URL is checked above")
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app = create_app(ServerSettings(database_url=TEST_DATABASE_URL), engine=engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/healthz")).status_code == 200
        assert (await client.get("/readyz")).json()["status"] == "ok"
        invalid = await client.post("/api/v1/scans", json={"scan_key": "missing"})
        assert invalid.status_code == 422
    engine.dispose()
