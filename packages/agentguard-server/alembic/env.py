"""Alembic environment configured from AgentGuard server settings."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from agentguard_server.config import ServerSettings
from agentguard_server.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = ServerSettings.from_env()
configured_url = config.get_main_option("sqlalchemy.url")
if configured_url and not (
    os.environ.get("AGENTGUARD_DATABASE_URL") or os.environ.get("DATABASE_URL")
):
    settings = settings.model_copy(update={"database_url": configured_url})
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a synchronous SQLAlchemy connection."""
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
