"""Tests for plugin management commands."""

from pathlib import Path

from typer.testing import CliRunner

from agentguard.cli import app

runner = CliRunner()


def test_plugins_list_and_info_show_builtins() -> None:
    listing = runner.invoke(app, ["plugins", "list"])
    info = runner.invoke(app, ["plugins", "info", "agentguard-builtins"])

    assert listing.exit_code == 0
    assert "agentguard-builtins" in listing.stdout
    assert info.exit_code == 0
    assert "register_rules" in info.stdout
    assert "UnboundedRetriesRule" in info.stdout


def test_plugins_info_rejects_unknown_plugin() -> None:
    result = runner.invoke(app, ["plugins", "info", "missing"])

    assert result.exit_code == 2
    assert "unknown plugin: missing" in result.stderr


def test_plugins_new_creates_installable_scaffold(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["plugins", "new", "demo-plugin", "--destination", str(tmp_path)],
    )

    root = tmp_path / "demo-plugin"
    assert result.exit_code == 0
    assert (root / "pyproject.toml").is_file()
    assert (root / "src/demo_plugin/__init__.py").is_file()
    assert (root / "tests/test_plugin.py").is_file()


def test_plugins_new_rejects_existing_destination(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()

    result = runner.invoke(
        app,
        ["plugins", "new", "demo", "--destination", str(tmp_path)],
    )

    assert result.exit_code == 2
    assert "destination already exists" in result.stderr


def test_doctor_reports_healthy_environment() -> None:
    result = runner.invoke(app, ["plugins", "doctor"])

    assert result.exit_code == 0
    assert "ok:" in result.stdout
