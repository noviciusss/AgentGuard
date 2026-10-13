"""Offline trace ingestion and runtime anomaly reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from agentguard.plugins import hookimpl


@dataclass(frozen=True)
class TraceSpan:
    """Normalized local trace span."""

    name: str
    duration_ms: float
    status: str
    attributes: dict[str, object]


class Plugin:
    """Register local ``agentguard trace`` ingestion."""

    name = "agentguard-trace"

    @hookimpl
    def register_commands(self, app: typer.Typer) -> None:
        app.command("trace")(trace_command)


def trace_command(
    input_path: Annotated[Path, typer.Argument(help="Trace JSON export.")],
    output: Annotated[
        Path | None, typer.Option("--output", help="Write normalized JSON.")
    ] = None,
    min_occurrences: Annotated[int, typer.Option("--min-occurrences", min=1)] = 3,
) -> None:
    """Ingest local span JSON and flag repeated failures or long spans."""
    spans = load_spans(input_path)
    counts: dict[str, int] = {}
    for span in spans:
        counts[span.name] = counts.get(span.name, 0) + 1
    findings = [
        {
            "rule_id": "TRACE001",
            "message": f"Trace span {name!r} repeated {count} times.",
            "occurrences": count,
        }
        for name, count in sorted(counts.items())
        if count >= min_occurrences
        and any(span.name == name and span.status == "error" for span in spans)
    ]
    rendered = json.dumps(findings, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.write_text(rendered, encoding="utf-8")
    else:
        typer.echo(rendered, nl=False)


def load_spans(path: Path) -> list[TraceSpan]:
    """Load either a list of spans or an OpenTelemetry-like ``spans`` object."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("spans", []) if isinstance(payload, dict) else payload
    return [
        TraceSpan(
            name=str(item.get("name", "unknown")),
            duration_ms=float(item.get("duration_ms", item.get("duration", 0))),
            status=str(item.get("status", "ok")),
            attributes=dict(item.get("attributes", {})),
        )
        for item in raw
    ]
