"""Configuration loading tests."""

from pathlib import Path

import pytest

from agentguard.config import (
    AgentGuardConfig,
    ConfigError,
    FailOn,
    load_config,
    merge_cli_config,
)
from agentguard.findings import Confidence, Severity


def test_load_config_from_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.agentguard]\nselect = ["AG003"]\n'
        'min_severity = "warning"\nfail_on = "never"\n',
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.select == ["AG003"]
    assert config.min_severity == Severity.WARNING
    assert config.fail_on == FailOn.NEVER


def test_load_config_reads_model_fix_mappings(tmp_path: Path) -> None:
    (tmp_path / "agentguard.toml").write_text(
        '[fix.model]\n"gpt-4" = "gpt-4-2024-08-06"\n',
        encoding="utf-8",
    )

    assert load_config(tmp_path).fix.model == {"gpt-4": "gpt-4-2024-08-06"}


def test_load_config_from_agentguard_toml_and_rejects_extra(tmp_path: Path) -> None:
    config_path = tmp_path / "agentguard.toml"
    config_path.write_text(
        '[tool.agentguard]\nmin_confidence = "high"\nunknown = true\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="invalid configuration"):
        load_config(tmp_path, config_path=config_path)

    config_path.write_text('min_confidence = "high"\n', encoding="utf-8")
    assert (
        load_config(tmp_path, config_path=config_path).min_confidence == Confidence.HIGH
    )


def test_agentguard_toml_takes_precedence_over_parent_pyproject(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.agentguard]\nselect = ["AG001"]\n',
        encoding="utf-8",
    )
    nested = tmp_path / "src"
    nested.mkdir()
    (nested / "agentguard.toml").write_text(
        'select = ["AG002"]\n',
        encoding="utf-8",
    )

    assert load_config(nested).select == ["AG002"]


def test_merge_cli_config_only_overrides_explicit_values() -> None:
    original = AgentGuardConfig(
        select=["AG001"],
        ignore=["AG003"],
        min_severity=Severity.WARNING,
        min_confidence=Confidence.MEDIUM,
        fail_on=FailOn.WARNING,
        jobs=2,
    )

    merged = merge_cli_config(original, min_confidence=Confidence.HIGH)

    assert merged.min_confidence == Confidence.HIGH
    assert merged.select == ["AG001"]
    assert merged.ignore == ["AG003"]
    assert merged.min_severity == Severity.WARNING
    assert merged.fail_on == FailOn.WARNING
    assert merged.jobs == 2


def test_invalid_jobs_are_rejected_from_files_and_overrides(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "agentguard.toml"
    config_path.write_text("jobs = 0\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid configuration"):
        load_config(tmp_path, config_path=config_path)

    with pytest.raises(ConfigError, match="invalid CLI configuration"):
        merge_cli_config(AgentGuardConfig(), jobs=0)


def test_malformed_toml_is_a_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "agentguard.toml"
    config_path.write_text("jobs = [\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid configuration"):
        load_config(tmp_path, config_path=config_path)
