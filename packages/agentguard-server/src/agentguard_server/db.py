"""SQLAlchemy engine and synchronous session helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from agentguard_server.config import ServerSettings

SessionFactory: TypeAlias = Callable[[], Session]


def create_database_engine(settings: ServerSettings) -> Engine:
    """Create a synchronous SQLAlchemy engine from validated settings."""
    common: dict[str, object] = {
        "echo": settings.db_echo,
        "pool_pre_ping": True,
    }
    if settings.database_url.startswith("sqlite"):
        common["connect_args"] = {"check_same_thread": False}
    else:
        common["pool_size"] = settings.db_pool_size
        common["max_overflow"] = settings.db_max_overflow
    return create_engine(settings.database_url, **common)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the synchronous session factory used by request dependencies."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
