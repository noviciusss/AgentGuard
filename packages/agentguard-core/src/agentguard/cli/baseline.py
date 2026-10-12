"""Baseline creation command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from agentguard.baseline import create_baseline, save_baseline
from agentguard.cli.scan import _root_for_paths, analyze_project
from agentguard.config import ConfigError, load_config


def baseline_create_command(
    paths: Annotated[
        list[Path] | None, typer.Argument(help="Files or directories to scan.")
    ] = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Baseline JSON output path.")
    ] = Path(".agentguard-baseline.json"),
) -> None:
    """Create a baseline containing the current findings."""
    scan_paths = paths or [Path(".")]
    root = _root_for_paths(scan_paths)
    try:
        result = analyze_project(scan_paths, load_config(root), root=root)
        save_baseline(output, create_baseline(result.findings))
    except (ConfigError, OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error
    typer.echo(f"wrote {len(result.findings)} findings to {output}")
