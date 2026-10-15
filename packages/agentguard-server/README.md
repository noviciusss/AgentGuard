# agentguard-server

The standalone Phase 6.1 HTTP service for AgentGuard scan history. It stores
repositories, commits, scans, findings, baselines, plugins, and configuration
versions in PostgreSQL.

## Configuration

The application reads these environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTGUARD_DATABASE_URL` or `DATABASE_URL` | `postgresql+psycopg://agentguard:agentguard@localhost:5432/agentguard` | SQLAlchemy database URL |
| `AGENTGUARD_ENVIRONMENT` | `development` | Deployment environment label |
| `AGENTGUARD_DEBUG` | `false` | FastAPI debug mode |
| `AGENTGUARD_HOST` | `127.0.0.1` | Uvicorn bind host |
| `AGENTGUARD_PORT` | `8000` | Uvicorn bind port |
| `AGENTGUARD_DB_POOL_SIZE` | `5` | PostgreSQL connection pool size |
| `AGENTGUARD_DB_MAX_OVERFLOW` | `10` | Extra PostgreSQL connections allowed |
| `AGENTGUARD_DB_ECHO` | `false` | SQLAlchemy SQL logging |
| `AGENTGUARD_AUTH_REQUIRED` | `false` | Require bearer authentication for API routes |
| `AGENTGUARD_API_TOKENS` | empty | Development/service tokens as `token=subject;scopes;repositories` |
| `AGENTGUARD_MAX_PAYLOAD_BYTES` | `2000000` | Maximum declared request body size |
| `AGENTGUARD_RATE_LIMIT` | `120` | Requests per client per process window |
| `AGENTGUARD_GITHUB_WEBHOOK_SECRET` | empty | HMAC secret for GitHub pull-request webhooks |
| `AGENTGUARD_PUBLIC_BADGES` | `false` | Enable repository opt-in badge routes |
| `AGENTGUARD_CORS_ORIGINS` | empty | Comma-separated dashboard origins |

## Run

From the repository root after installing the workspace:

```bash
uv run --package agentguard-server alembic -c packages/agentguard-server/alembic.ini upgrade head
uv run --package agentguard-server uvicorn agentguard_server.main:app --reload
```

The service exposes `GET /health/live` without a database query and
`GET /health/ready`, which executes `SELECT 1` against the configured database.
Versioned scan endpoints are under `/api/v1`:

```text
POST /api/v1/scans
POST /api/v1/scans/sarif?scan_key=...&repository=...&commit_sha=...
GET  /api/v1/scans?page=1&page_size=50
GET  /api/v1/repositories?page=1&page_size=50
GET  /api/v1/repositories/{repository_id}
POST /api/v1/github/webhook
GET  /api/v1/badges/{repository_id}.svg
```

`scan_key` is the idempotency key for ingestion. Repeating a request with the
same key returns the original scan and does not add duplicate findings.

The dashboard can use `AGENTGUARD_CORS_ORIGINS` for a narrowly scoped browser
origin. Authentication is bearer-token based in this foundation; production
deployments should place token ownership and rotation behind the Phase 6.3
identity provider integration rather than committing tokens to configuration.

## Tests

Package tests use an in-memory SQLite database for model and API-independent
checks. PostgreSQL integration tests are enabled only when
`AGENTGUARD_TEST_DATABASE_URL` is set:

```bash
AGENTGUARD_TEST_DATABASE_URL=postgresql://agentguard:agentguard@localhost:5432/agentguard_test \
  uv run --package agentguard-server pytest packages/agentguard-server/tests
```
