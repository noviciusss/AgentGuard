"""Configuration contract tests."""

import pytest
from pydantic import ValidationError

from agentguard_server.config import ServerSettings


def test_settings_use_typed_environment_values() -> None:
    settings = ServerSettings.from_env(
        {
            "AGENTGUARD_DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "AGENTGUARD_DEBUG": "true",
            "AGENTGUARD_PORT": "9000",
            "AGENTGUARD_DB_POOL_SIZE": "3",
            "AGENTGUARD_DB_MAX_OVERFLOW": "4",
        }
    )

    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.debug is True
    assert settings.port == 9000
    assert settings.db_pool_size == 3
    assert settings.db_max_overflow == 4


def test_settings_reject_invalid_boolean() -> None:
    with pytest.raises(ValueError, match="AGENTGUARD_DEBUG"):
        ServerSettings.from_env({"AGENTGUARD_DEBUG": "sometimes"})


def test_settings_reject_invalid_port() -> None:
    with pytest.raises(ValidationError):
        ServerSettings.from_env({"AGENTGUARD_PORT": "0"})
