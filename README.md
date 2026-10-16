# AgentGuard

AgentGuard is a static analysis CLI for AI agent codebases. It finds reliability,
cost, and security bugs in agent graphs, tool calls, retries, and LLM calls
before an agent runs.

The project ships the normalized Agent IR, generic/LangGraph/CrewAI/AutoGen
adapters, the plugin system, 15 documented reliability/cost/security rules,
SARIF and autofix support, and the Phase 5 graph, OWASP, triage, and trace
plugins.

## Development setup

AgentGuard requires Python 3.10+ and uses `uv` for environments and
dependencies. CI targets Python 3.10, 3.11, 3.12, and 3.13. The bootstrap uses
`uv` 0.13.0 and GNU Make.

If you just installed `uv` and the shell cannot find it, open a new terminal
or add its default install directory to your current shell's path:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

WSL users should keep the virtual environment outside a Windows-mounted
project directory and use copy mode for dependency links:

```bash
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/agentguard"
uv sync --locked --all-extras
```

Install the locked environment and run the complete local check suite with:

```bash
uv sync --locked --all-extras
make check
```

`make install` also installs the locked dependencies, using the same
environment as the check targets. The Makefile exports both WSL settings;
export them in your shell as above when running `uv` directly. All check
targets include the development dependencies automatically.

Keep `uv.lock` in version control. For intentional dependency updates, run
`uv lock --upgrade`, review the lockfile changes, and run `make check`.

## Quick start

Check the installed version:

```bash
uv run --locked agentguard --version
uv run --locked python -m agentguard --version
```

Scan the bundled examples without failing the shell command on findings:

```bash
uv run --locked agentguard scan examples/ --fail-on never
```

The support bot and plain Python agent intentionally contain findings. The
clean agent should produce no findings:

```bash
uv run --locked agentguard scan examples/clean_agent --format json --fail-on never
```

List the built-in rules or read a rule's remediation guidance:

```bash
uv run --locked agentguard rules
uv run --locked agentguard explain AG003
uv run --locked agentguard plugins list
uv run --locked agentguard baseline create examples/ --output baseline.json
uv run --locked agentguard graph examples/langgraph_support_bot
uv run --locked agentguard trace path/to/local-trace.json
```

Useful scan options include:

```text
agentguard scan [PATHS...] --format text|json
    --select AG001,AG00* --ignore AG003
    --min-severity info|warning|error
    --min-confidence low|medium|high
    --fail-on error|warning|never
    --jobs N --output FILE --no-cache
```

Phase 5 commands:

```text
agentguard graph PATH [--output FILE]                 # Mermaid normalized IR
agentguard trace TRACE.json [--output FILE]           # loops and cost spikes
agentguard triage --input FINDINGS.json               # explicit provider needed
    --source-root PROJECT --provider module:factory
    [--cache FILE]
```

`agentguard triage` can send redacted source snippets to arbitrary provider
code, so use it only with a provider you trust. It never runs during `scan`
and does not change finding severity.

The scanner parses source without importing or executing it. A syntax error is
reported as a warning and the remaining files continue to scan. Findings are
deterministically sorted and can be suppressed inline:

```python
requests.get(url)  # agentguard: ignore[AG003] reason: gateway adds timeout
```

See [the architecture guide](docs/architecture.md) and the individual pages in
[`docs/rules/`](docs/rules/) for the IR pipeline and rule-specific guidance.
See [the CI guide](docs/ci.md) for GitHub and pre-commit integration, and
[the autofix guide](docs/autofix.md) for safe dry-run and apply behavior.
See [the distribution guide](docs/distribution.md) for bundled and standalone
installation profiles. Do not install both profiles into the same environment.

## Phase 6 platform development

The hosted platform is split from the offline analyzer. The server package is
`packages/agentguard-server` and uses FastAPI, SQLAlchemy 2, psycopg 3, and
Alembic. The core CLI does not import the server or require PostgreSQL.

### Start everything with Docker Compose

Docker Compose is the recommended local platform setup. It starts PostgreSQL,
applies the Alembic migrations, and starts the FastAPI service. The database is
stored in the named `agentguard-postgres` volume and the API is exposed on port
`8000`. PostgreSQL is exposed on port `5432` so local integration tests can use
the same database.

```bash
cp .env.example .env
docker compose up --build
```

Verify the services from a second terminal:

```bash
curl -fsS http://localhost:8000/healthz
curl -fsS http://localhost:8000/readyz
curl -fsS http://localhost:8000/openapi.json > /tmp/agentguard-openapi.json
```

Expected health output is:

```json
{"status":"ok","service":"agentguard-server"}
```

Open the interactive API contract at <http://localhost:8000/docs>. Stop the
services without deleting the database with:

```bash
docker compose down
```

Use `docker compose down -v` only when intentionally resetting the local
database. The web dashboard is a separate process and is started below.

### Run the dashboard

The Next.js dashboard lives under `web/` and reads the backend URL from
`AGENTGUARD_API_URL`:

```bash
cd web
npm ci
AGENTGUARD_API_URL=http://localhost:8000 npm run dev
```

Open <http://localhost:3000>. The dashboard has repository, scan, and finding
views plus explicit loading, empty, API-unavailable, forbidden, and error
states. Its API client forwards only the incoming `Authorization` and `Cookie`
headers; authorization remains a backend responsibility.

Run dashboard checks from `web/`:

```bash
npm test       # strict TypeScript check
npm run build  # production Next.js build
npm start      # serve the production build
```

### Run the API with an existing PostgreSQL instance

Docker is not required if you already have PostgreSQL. Set the connection URL
in the shell, apply migrations, and start Uvicorn:

```bash
export AGENTGUARD_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/DB'
export AGENTGUARD_CORS_ORIGINS='http://localhost:3000'

uv run --locked --all-extras --package agentguard-server alembic \
  -c packages/agentguard-server/alembic.ini upgrade head

uv run --locked --all-extras --package agentguard-server uvicorn \
  agentguard_server.main:app --host 127.0.0.1 --port 8000
```

Never put a real password, token, private key, or webhook secret in the
repository. Use environment variables, a local secret manager, or Docker
secrets. `.env.example` contains placeholders only.

### Submit and query a scan

The JSON ingestion endpoint is idempotent by `scan_key`. Repeating the same
request returns the existing scan rather than inserting duplicate findings.

```bash
curl -X POST http://localhost:8000/api/v1/scans \
  -H 'Content-Type: application/json' \
  -d '{
    "scan_key": "local-scan-1",
    "repository": {"provider": "github", "full_name": "acme/demo"},
    "branch": "main",
    "commit": {"sha": "abc123"},
    "analyzer_version": "0.1.0",
    "findings": []
  }'
```

Useful read endpoints are:

```text
GET /api/v1/repositories?page=1&page_size=50
GET /api/v1/repositories/{repository_id}
GET /api/v1/repositories/{repository_id}/scans?page=1&page_size=20
GET /api/v1/scans/{scan_id}
GET /api/v1/scans?page=1&page_size=50
```

SARIF uploads use the same persistence and idempotency path. The repository,
branch, commit, analyzer version, and scan key are explicit query parameters:

```bash
curl -X POST \
  'http://localhost:8000/api/v1/scans/sarif?scan_key=ci-123&repository=acme%2Fdemo&branch=main&commit_sha=abc123&analyzer_version=0.1.0' \
  -H 'Content-Type: application/json' \
  --data-binary @results.sarif
```

The server validates repository identifiers, relative source paths, finding
severity/confidence, source ranges, field lengths, duplicate fingerprints, and
the declared request size before persisting data.

### Configure development authentication

Authentication is optional for local development. To require bearer tokens:

```bash
export AGENTGUARD_AUTH_REQUIRED=true
export AGENTGUARD_API_TOKENS='ci-token=ci;read|write;acme/demo'
```

The token format is:

```text
token=subject;scope1|scope2;repository1|repository2
```

Then call protected endpoints with:

```bash
curl http://localhost:8000/api/v1/repositories \
  -H 'Authorization: Bearer ci-token'
```

`read` and `write` scopes are enforced, and repository scopes provide tenant
isolation. Cross-repository access returns a generic `404` rather than
revealing whether another repository exists. The service adds an `X-Request-ID`
response header, limits declared request size, rate-limits clients, and stores
redacted audit details. The default rate limiter and audit fallback are
process-local development implementations; production replicas need shared
operational services.

### GitHub webhooks and badges

Configure a webhook secret before enabling the GitHub endpoint:

```bash
export AGENTGUARD_GITHUB_WEBHOOK_SECRET='replace-with-a-secret'
```

`POST /api/v1/github/webhook` accepts signed GitHub `pull_request` events for
`opened`, `synchronize`, and `reopened`. It verifies `X-Hub-Signature-256`,
claims delivery IDs to reject replays, and creates one queued scan tied to the
pull-request head commit. A background worker that executes queued scans and
publishes Check Runs is not included in this foundation.

Badges require both `AGENTGUARD_PUBLIC_BADGES=true` and the repository's
`badge_public` flag. They expose only aggregate risk state and severity counts:

```text
GET /api/v1/badges/{repository_id}.svg
GET /api/v1/badges/{repository_id}.json
```

Private repositories return `404`, and public responses use deterministic ETags
and cache headers without source snippets or finding messages.

### Run tests and migrations

Install all locked Python workspace dependencies:

```bash
uv sync --locked --all-extras --all-packages
```

Run the complete Python check suite:

```bash
make check
```

`make check` runs Ruff lint/format checks, strict mypy, the root tests, and the
server tests. PostgreSQL-specific tests run when
`AGENTGUARD_TEST_DATABASE_URL` is set; otherwise only those integration tests
are skipped:

```bash
export AGENTGUARD_TEST_DATABASE_URL='postgresql+psycopg://agentguard:agentguard@localhost:5432/agentguard'
make server-test
```

Apply or inspect migrations directly:

```bash
AGENTGUARD_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/DB' \
  uv run --locked --all-extras --package agentguard-server alembic \
  -c packages/agentguard-server/alembic.ini upgrade head

uv run --locked --all-extras --package agentguard-server alembic \
  -c packages/agentguard-server/alembic.ini current
```

The current migration head is `0004_audit_records`.

### Package and release checks

Build the root CLI and standalone server distributions outside the repository:

```bash
uv build --out-dir /tmp/omnirush/agentguard-build-root
uv build --directory packages/agentguard-server \
  --out-dir /tmp/omnirush/agentguard-build-server
```

The supported Python CI matrix is 3.10, 3.11, 3.12, and 3.13. GitHub Actions
also runs the PostgreSQL-backed server suite and the dashboard TypeScript and
production-build checks. See [`docs/server.md`](docs/server.md) for the full
server contract, [`docs/distribution.md`](docs/distribution.md) for package
profiles, and [`web/README.md`](web/README.md) for the dashboard contract.

## License

AgentGuard is released under the MIT license. See [LICENSE](LICENSE).
