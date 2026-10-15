# Server package development

`packages/agentguard-server` is a standalone workspace package for the Phase 6.1
FastAPI and PostgreSQL service. The root `agentguard-core` package remains the
offline analyzer and does not import or depend on the server package.

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
