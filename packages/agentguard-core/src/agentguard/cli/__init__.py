"""Command-line interface for AgentGuard."""

from typing import Annotated

import typer

from agentguard import __version__
from agentguard.cli.baseline import baseline_create_command
from agentguard.cli.plugins import plugins_app
from agentguard.cli.rules import explain_command, rules_command
from agentguard.cli.scan import scan_command
from agentguard.plugins.manager import PluginManager

app = typer.Typer(add_completion=False, no_args_is_help=False)
app.command("scan")(scan_command)
app.command("rules")(rules_command)
app.command("explain")(explain_command)
app.add_typer(plugins_app, name="plugins")
baseline_app = typer.Typer(help="Create and inspect finding baselines.")
baseline_app.command("create")(baseline_create_command)
app.add_typer(baseline_app, name="baseline")
PluginManager.default().register_commands(app)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"AgentGuard {__version__}")
        raise typer.Exit


@app.callback()
def callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the installed AgentGuard version.",
            callback=_show_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Analyze AI agent codebases before they run."""


def main() -> None:
    """Run the AgentGuard command-line application."""
    app()
