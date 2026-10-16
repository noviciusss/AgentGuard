"""HTTP-level coverage for ingestion, authorization, badges, and webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from agentguard_server.app import create_app
from agentguard_server.config import ServerSettings
from agentguard_server.models import Base, Repository


def _scan_payload(scan_key: str = "scan-http") -> dict[str, object]:
    return {
        "scan_key": scan_key,
        "repository": {"provider": "github", "full_name": "acme/demo"},
        "branch": "main",
        "commit": {"sha": "abc123"},
        "analyzer_version": "0.1.0",
        "findings": [],
    }


def _app(
    directory: str,
    *,
    auth_required: bool = False,
    api_tokens: str = "",
    public_badges: bool = False,
    webhook_secret: str | None = None,
) -> tuple[FastAPI, Engine]:
    database = Path(directory) / "server.sqlite"
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    Base.metadata.create_all(engine)
    app = create_app(
        ServerSettings(
            database_url=f"sqlite+pysqlite:///{database}",
            auth_required=auth_required,
            api_tokens=api_tokens,
            public_badges=public_badges,
            github_webhook_secret=webhook_secret,
        ),
        engine=engine,
    )
    return app, engine


@pytest.mark.anyio
async def test_http_ingestion_sarif_auth_pagination_and_payload_limit() -> None:
    with TemporaryDirectory() as directory:
        app, engine = _app(
            directory,
            auth_required=True,
            api_tokens="ci-token=ci;read|write;acme/demo",
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            unauthorized = await client.get("/api/v1/repositories")
            assert unauthorized.status_code == 401

            headers = {"Authorization": "Bearer ci-token", "X-Request-ID": "req-1"}
            created = await client.post(
                "/api/v1/scans", json=_scan_payload(), headers=headers
            )
            assert created.status_code == 201
            assert created.headers["x-request-id"] == "req-1"

            sarif = {
                "runs": [
                    {
                        "results": [
                            {
                                "ruleId": "AG003",
                                "level": "error",
                                "message": {"text": "timeout missing"},
                            }
                        ]
                    }
                ]
            }
            imported = await client.post(
                "/api/v1/scans/sarif?scan_key=sarif-http&repository=acme%2Fdemo&commit_sha=def456",
                json=sarif,
                headers=headers,
            )
            assert imported.status_code == 201
            assert imported.json()["findings"][0]["rule_id"] == "AG003"

            page = await client.get(
                "/api/v1/repositories?page=1&page_size=1", headers=headers
            )
            assert page.status_code == 200
            assert page.json()["total"] == 1

            denied = await client.post(
                "/api/v1/scans",
                json={
                    **_scan_payload("denied"),
                    "repository": {"provider": "github", "full_name": "other/repo"},
                },
                headers=headers,
            )
            assert denied.status_code == 404

            conflicting_key = await client.post(
                "/api/v1/scans",
                json={
                    **_scan_payload("scan-http"),
                    "repository": {
                        "provider": "github",
                        "full_name": "acme/other",
                    },
                },
                headers=headers,
            )
            assert conflicting_key.status_code == 404

            too_large = await client.post(
                "/api/v1/scans",
                content=b"{}",
                headers={**headers, "content-length": "3000000"},
            )
            assert too_large.status_code == 413
        engine.dispose()


@pytest.mark.anyio
async def test_public_badge_and_github_webhook_are_privacy_safe_and_idempotent() -> (
    None
):
    secret = "webhook-secret"
    with TemporaryDirectory() as directory:
        app, engine = _app(directory, public_badges=True, webhook_secret=secret)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            created = await client.post("/api/v1/scans", json=_scan_payload())
            repository_id = created.json()["repository_id"]
            with Session(engine) as session:
                repository = session.get(Repository, uuid.UUID(repository_id))
                assert repository is not None
                repository.badge_public = True
                session.commit()

            badge = await client.get(f"/api/v1/badges/{repository_id}.json")
            assert badge.status_code == 200
            assert "acme/demo" not in badge.text
            repeated = await client.get(
                f"/api/v1/badges/{repository_id}.json",
                headers={"if-none-match": badge.headers["etag"]},
            )
            assert repeated.status_code == 304

            event = {
                "action": "opened",
                "repository": {"full_name": "acme/demo"},
                "pull_request": {"number": 4, "head": {"sha": "head-1"}},
            }
            raw = json.dumps(event, separators=(",", ":")).encode()
            signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
            webhook_headers = {
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "delivery-http-1",
            }
            accepted = await client.post(
                "/api/v1/github/webhook", content=raw, headers=webhook_headers
            )
            assert accepted.status_code == 202
            queued_scan = await client.get(
                f"/api/v1/scans/{accepted.json()['scan_id']}"
            )
            assert queued_scan.status_code == 200
            assert queued_scan.json()["status"] == "queued"
            replay = await client.post(
                "/api/v1/github/webhook", content=raw, headers=webhook_headers
            )
            assert replay.status_code == 409
        engine.dispose()
