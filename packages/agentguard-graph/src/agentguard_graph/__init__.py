"""Mermaid graph visualization plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from agentguard.cli.scan import analyze_project
from agentguard.config import load_config
from agentguard.plugins import hookimpl


class Plugin:
    """Register the ``agentguard graph`` command."""

    name = "agentguard-graph"

    @hookimpl
    def register_commands(self, app: typer.Typer) -> None:
        app.command("graph")(graph_command)


def graph_command(
    path: Annotated[Path, typer.Argument(help="Source file or directory.")],
    output: Annotated[
        Path | None, typer.Option("--output", help="Write Mermaid output.")
    ] = None,
) -> None:
    """Render normalized agent graphs as Mermaid text."""
    root = path.resolve() if path.is_dir() else path.resolve().parent
    result = analyze_project([path], load_config(root), root=root)
    text = _render(result)
    if output is not None:
        output.write_text(text, encoding="utf-8")
    else:
        typer.echo(text, nl=False)


def _render(result: object) -> str:
    # Importing the scan result type would couple this optional plugin to a
    # concrete CLI return annotation; the public result shape is intentional.
    system = getattr(result, "system", None)
    if system is None:
        # The current scan result deliberately exposes findings only. Graph
        # rendering uses the same parser pipeline through this helper later.
        return "flowchart TD\n  empty[No graph data]\n"
    lines = ["flowchart TD"]
    for module in system.modules:
        for graph in module.graphs:
            for edge in graph.edges:
                target = edge.target or "unresolved"
                lines.append(f"  {graph.name}_{edge.source} --> {graph.name}_{target}")
    return "\n".join(lines) + "\n"
