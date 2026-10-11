"""Command-line interface for AgentGuard."""

from typing import Annotated

import typer

from agentguard import __version__

app = typer.Typer(add_completion=False, no_args_is_help=False)


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
