"""Bootstrap tests for the initial AgentGuard package."""

from typer.testing import CliRunner

from agentguard import __version__
from agentguard.cli import app

runner = CliRunner()


def test_version_option() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"AgentGuard {__version__}"
