# AgentGuard dashboard

This directory is a dependency-light Next.js frontend scaffold for the Phase
6.5 dashboard. It is intentionally separate from the Python packages and does
not generate an API client. The request and response contract lives in
`lib/api.ts` so it can be reviewed alongside the server contract.

## Run locally

From this directory:

```bash
nvm use 20.17.0
npm install
AGENTGUARD_API_URL=http://localhost:8000 npm run dev
```

Open <http://localhost:3000>. `AGENTGUARD_API_URL` defaults to
`http://localhost:8000` and should point at the FastAPI service. The frontend
uses the incoming request's `Authorization` and `Cookie` headers when it calls
the service; it does not implement or bypass authorization itself.

## Checks

```bash
npm test       # required strict TypeScript check
npm run build  # production Next.js build; run npm test first
```

The production build skips duplicate TypeScript and ESLint work inside the
Next.js worker. `npm test` remains the required strict type gate before a build
or deployment; this avoids long-running worker hangs on WSL-mounted drives.

There is no test framework or generated-code step in this scaffold. The `test`
script is the lightweight contract check until browser smoke tests are added
with the dashboard's backend-authenticated integration environment.

The repository pins Node through the root `.nvmrc`. Next production builds use
one build worker (`experimental.cpus = 1`) because parallel Next workers can
hang on WSL-mounted filesystems. This is a build-performance/reproducibility
setting, not a replacement for `npm test`.

## API contract used by the scaffold

The typed client expects these repository-facing read endpoints:

```text
GET /api/v1/repositories?page=1&page_size=50
GET /api/v1/repositories/:repositoryId
GET /api/v1/repositories/:repositoryId/scans?page=1&page_size=20
GET /api/v1/scans/:scanId
```

Repository detail responses include a repository summary, trend points, scan
page, recent findings, optional baseline comparison, and pull-request context.
Scan responses contain the complete finding objects required by the finding
view: rule, severity, confidence, source location, explanation, and
remediation. The existing Phase 6.1 scan summary naming (`scan_key`,
`finding_count`, `created_at`) is normalized to camelCase in `lib/api.ts`.
