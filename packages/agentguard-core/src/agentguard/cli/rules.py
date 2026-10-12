"""Rules listing and documentation commands."""

from pathlib import Path

import typer

from agentguard.plugins.manager import PluginManager
from agentguard.rules.registry import RuleRegistry


def rules_command() -> None:
    """List installed rules and their one-line descriptions."""
    for descriptor in _registry().descriptors():
        typer.echo(
            f"{descriptor.rule_id}  {descriptor.name}  "
            f"{descriptor.default_severity.value}  {descriptor.description}"
        )


def explain_command(rule_id: str) -> None:
    """Render a rule's Markdown documentation in the terminal."""
    normalized = rule_id.upper()
    if normalized not in {
        descriptor.rule_id for descriptor in _registry().descriptors()
    }:
        typer.echo(f"unknown rule: {normalized}", err=True)
        raise typer.Exit(code=2)
    documentation = _docs_root() / "rules" / f"{normalized}.md"
    try:
        text = documentation.read_text(encoding="utf-8")
    except OSError as error:
        typer.echo(f"could not read {documentation}: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(text, nl=False)


def _docs_root() -> Path:
    repository_docs = Path.cwd() / "docs"
    if repository_docs.is_dir():
        return repository_docs
    return Path(__file__).resolve().parents[3] / "docs"


def _registry() -> RuleRegistry:
    return RuleRegistry(PluginManager.default().rules())
