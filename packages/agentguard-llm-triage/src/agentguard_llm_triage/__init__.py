"""Opt-in, provider-neutral finding triage plugin."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Protocol, cast

import typer

from agentguard.plugins import hookimpl


@dataclass(frozen=True)
class TriageRequest:
    """Redacted, provider-neutral input for one triage decision."""

    rule_id: str
    message: str
    why: str
    suggestion: str
    snippet: str


@dataclass(frozen=True)
class TriageResult:
    """Advisory triage response; it never changes finding severity."""

    classification: str
    confidence: str
    explanation: str


class TriageProvider(Protocol):
    """Provider contract implemented by an optional local or remote plugin."""

    def evaluate(self, request: TriageRequest) -> TriageResult:
        """Return an advisory evaluation."""


class Plugin:
    """Register the explicit ``agentguard triage`` command."""

    name = "agentguard-llm-triage"

    @hookimpl
    def register_commands(self, app: typer.Typer) -> None:
        app.command("triage")(triage_command)


def triage_command(
    input_path: Annotated[Path, typer.Option("--input", help="JSON findings file.")],
    provider: Annotated[
        str, typer.Option("--provider", help="module:factory provider path.")
    ],
    cache: Annotated[
        Path | None, typer.Option("--cache", help="Optional JSON result cache.")
    ] = None,
) -> None:
    """Run opt-in advisory triage through a user-supplied provider."""
    factory = _load_provider(provider)
    instance = factory()
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    results: list[dict[str, str]] = []
    cache_data = _load_cache(cache)
    for item in payload:
        fingerprint = str(item.get("fingerprint", ""))
        if fingerprint in cache_data:
            result = cache_data[fingerprint]
        else:
            result = instance.evaluate(
                TriageRequest(
                    rule_id=str(item.get("rule_id", "")),
                    message=str(item.get("message", "")),
                    why=str(item.get("why", "")),
                    suggestion=str(item.get("suggestion", "")),
                    snippet="",
                )
            )
            cache_data[fingerprint] = {
                "classification": result.classification,
                "confidence": result.confidence,
                "explanation": result.explanation,
            }
        results.append({"fingerprint": fingerprint, **cache_data[fingerprint]})
    if cache is not None:
        cache.write_text(json.dumps(cache_data, indent=2, sort_keys=True) + "\n")
    typer.echo(json.dumps(results, indent=2, sort_keys=True))


def _load_provider(path: str):  # type: ignore[no-untyped-def]
    module_name, separator, attribute = path.partition(":")
    if not separator or not module_name or not attribute:
        raise typer.BadParameter("provider must use module:factory syntax")
    return getattr(importlib.import_module(module_name), attribute)


def _load_cache(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return cast(dict[str, dict[str, str]], payload)
