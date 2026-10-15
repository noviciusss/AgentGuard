"""Optional PostgreSQL integration check, enabled only by explicit configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from agentguard_server.config import ServerSettings
from agentguard_server.db import create_database_engine
from agentguard_server.models import Base

TEST_DATABASE_URL = os.environ.get("AGENTGUARD_TEST_DATABASE_URL")


@pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="set AGENTGUARD_TEST_DATABASE_URL to run PostgreSQL integration tests",
)
def test_configured_postgres_accepts_a_connection() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_database_engine(ServerSettings(database_url=TEST_DATABASE_URL))
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


@pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="set AGENTGUARD_TEST_DATABASE_URL to run PostgreSQL integration tests",
)
def test_initial_migration_applies_to_a_clean_database() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_database_engine(ServerSettings(database_url=TEST_DATABASE_URL))
    try:
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            )
            assert version.scalar_one() == "0004_audit_records"
    finally:
        engine.dispose()
