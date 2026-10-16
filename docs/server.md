# Server package development

`packages/agentguard-server` is a standalone workspace package for the Phase 6.1
FastAPI and PostgreSQL service. The root `agentguard-core` package remains the
offline analyzer and does not import or depend on the server package.

The service foundation now also includes the Phase 6.2–6.6 contract pieces:
JSON and SARIF ingestion, repository-scoped reads, bearer-token authorization,
redacted audit events, retention helpers, GitHub pull-request webhook
verification, and opt-in aggregate-only badges. The platform helpers do not run
the analyzer or send source code to a network service.

## Reproducible local checks

Install the locked root and workspace environments:

```bash
uv sync --locked --all-extras --all-packages
```

Run the server tests against PostgreSQL by setting `AGENTGUARD_TEST_DATABASE_URL`.
Without that variable, PostgreSQL integration tests are skipped rather than
silently using a database substitute:

```bash
export AGENTGUARD_TEST_DATABASE_URL=postgresql://agentguard:agentguard@localhost:5432/agentguard_test
make server-test
```

The server test command runs with the locked `agentguard-server` workspace
package and its optional development dependencies:

```bash
uv run --locked --all-extras --package agentguard-server \
  pytest packages/agentguard-server/tests
```

`make check` runs the root lint, type, and test checks and then runs
`make server-test`. A PostgreSQL service and the same database URL are provided
to every Python job in `.github/workflows/ci.yml`.

When PostgreSQL is available, the complete server suite should report 56 passed
and no skipped tests. Without PostgreSQL, only the five database integration
tests are skipped; the remaining server tests still run.

## Docker Compose runtime

The repository includes a reproducible local runtime:

```bash
docker compose up --build
```

The `postgres` service is exposed on host port `5432` for local integration
tests. The `server` service waits for the PostgreSQL health check, applies all
Alembic migrations, and serves Uvicorn on host port `8000`.

Verify the runtime from a second terminal:

```bash
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
curl -fsS http://localhost:8000/openapi.json
```

Expected health responses are JSON objects with `status: "ok"` and
`service: "agentguard-server"`. Stop the services while preserving the local
database volume with `docker compose down`; add `-v` only when intentionally
resetting the local database.

## Migrations

The migration head is `0004_audit_records`:

```bash
AGENTGUARD_DATABASE_URL='postgresql+psycopg://user:password@localhost/db' \
  uv run --locked --all-extras --package agentguard-server alembic \
  -c packages/agentguard-server/alembic.ini upgrade head
```

Migrations are append-only. The initial schema stores repositories, branches,
commits, scans, findings, baselines, plugins, configuration versions, webhook
delivery claims, explicit badge visibility, and sanitized audit records.

## API and protection boundaries

- `POST /api/v1/scans` accepts normalized JSON and is idempotent by `scan_key`.
- `POST /api/v1/scans/sarif` converts bounded SARIF results into the same
  ingestion path; it does not execute source files.
- Repository and scan reads are deterministically ordered and honor configured
  repository scopes.
- `AGENTGUARD_AUTH_REQUIRED=true` enables bearer tokens configured through
  `AGENTGUARD_API_TOKENS`; token values are never written to audit details.
- Request IDs, declared payload-size limits, rate limits, and recursive audit
  redaction are applied in the HTTP layer.
- `POST /api/v1/github/webhook` verifies `X-Hub-Signature-256`, accepts only
  pull-request `opened`, `synchronize`, and `reopened`, and claims delivery IDs
  in PostgreSQL before scheduling work.
- Badge routes are disabled unless globally enabled and a repository's
  `badge_public` flag is true. They return only aggregate severity counts and
  risk state, with ETags and cache headers.

The process-local rate limiter and audit fallback are safe development defaults.
Production deployments should provide a shared rate-limit store and an
operational audit sink before running multiple service replicas.
