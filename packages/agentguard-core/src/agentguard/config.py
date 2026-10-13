"""Validated AgentGuard configuration loading."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentguard.findings import Confidence, Severity


class FailOn(str, Enum):
    """Finding threshold that makes a scan fail."""

    ERROR = "error"
    WARNING = "warning"
    NEVER = "never"


class FixConfig(BaseModel):
    """Explicit mappings used by safe autofixes."""

    model: dict[str, str] = Field(default_factory=dict)


class AgentGuardConfig(BaseModel):
    """All scan configuration with safe defaults."""

    model_config = ConfigDict(extra="forbid")

    select: list[str] = Field(default_factory=lambda: ["AG*"])
    ignore: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=lambda: [".venv/", "build/"])
    exclude_tests: bool = True
    min_severity: Severity = Severity.INFO
    min_confidence: Confidence = Confidence.LOW
    fail_on: FailOn = FailOn.ERROR
    jobs: int = Field(default=1, ge=1)
    severity: dict[str, Severity] = Field(default_factory=dict)
    fix: FixConfig = Field(default_factory=FixConfig)


class ConfigError(ValueError):
    """A configuration file is missing, invalid, or unreadable."""


def load_config(
    start: Path = Path("."),
    *,
    config_path: Path | None = None,
) -> AgentGuardConfig:
    """Load ``agentguard.toml`` or ``pyproject.toml`` from the directory tree."""
    path = config_path or _find_config(start)
    if path is None:
        return AgentGuardConfig()
    try:
        data = _read_toml(path)
        if path.name == "pyproject.toml":
            tool = data.get("tool", {})
            if not isinstance(tool, Mapping):
                raise ConfigError(f"{path}: [tool] must be a table")
            section = tool.get("agentguard", {})
        else:
            section = data.get("tool", data)
            if isinstance(section, Mapping) and "agentguard" in section:
                section = section["agentguard"]
        if not isinstance(section, Mapping):
            raise ConfigError(f"{path}: [tool.agentguard] must be a table")
        return AgentGuardConfig.model_validate(dict(section))
    except ConfigError:
        raise
    except (OSError, ValueError, ValidationError) as error:
        raise ConfigError(f"{path}: invalid configuration: {error}") from error


def _find_config(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        agentguard = directory / "agentguard.toml"
        if agentguard.is_file():
            return agentguard
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            return pyproject
    return None


def _read_toml(path: Path) -> dict[str, object]:
    module_name = "tomllib" if sys.version_info >= (3, 11) else "tomli"
    module = cast(_TomlLoader, importlib.import_module(module_name))
    with path.open("rb") as stream:
        return module.load(stream)


class _TomlLoader(Protocol):
    def load(self, stream: BinaryIO) -> dict[str, object]:
        """Parse a TOML byte stream."""


def merge_cli_config(
    config: AgentGuardConfig,
    *,
    select: list[str] | None = None,
    ignore: list[str] | None = None,
    min_severity: Severity | None = None,
    min_confidence: Confidence | None = None,
    fail_on: Literal["error", "warning", "never"] | None = None,
    jobs: int | None = None,
) -> AgentGuardConfig:
    """Return config with only explicitly provided CLI values overridden."""
    updates: dict[str, object] = {}
    if select is not None:
        updates["select"] = select
    if ignore is not None:
        updates["ignore"] = ignore
    if min_severity is not None:
        updates["min_severity"] = min_severity
    if min_confidence is not None:
        updates["min_confidence"] = min_confidence
    if fail_on is not None:
        updates["fail_on"] = fail_on
    if jobs is not None:
        updates["jobs"] = jobs
    try:
        return AgentGuardConfig.model_validate({**config.model_dump(), **updates})
    except ValidationError as error:
        raise ConfigError(f"invalid CLI configuration: {error}") from error
