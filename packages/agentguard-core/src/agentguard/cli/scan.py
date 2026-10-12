"""Scan command and project-level analysis orchestration."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Literal

import typer

from agentguard.baseline import BaselineError, filter_baselined, load_baseline
from agentguard.config import (
    AgentGuardConfig,
    ConfigError,
    FailOn,
    load_config,
    merge_cli_config,
)
from agentguard.engine.discovery import discover_python_files
from agentguard.engine.parser import ParsedModule, ParseError, parse_file
from agentguard.engine.runner import ParseDiagnostic, ScanResult
from agentguard.engine.suppression import parse_suppressions
from agentguard.findings import Confidence, Finding, Severity, sort_findings
from agentguard.ir.builder import IRBuilder
from agentguard.ir.models import AgentSystem
from agentguard.plugins.manager import PluginManager
from agentguard.reporters import JsonReporter, TextReporter
from agentguard.rules.base import RuleContext
from agentguard.rules.registry import RuleRegistry


@dataclass(frozen=True)
class _ParsedFileResult:
    """Parsed module or non-fatal diagnostic returned by one worker."""

    module: ParsedModule | None
    diagnostic: ParseDiagnostic | None


def analyze_project(
    paths: list[Path],
    config: AgentGuardConfig,
    *,
    root: Path | None = None,
    registry: RuleRegistry | None = None,
    plugin_manager: PluginManager | None = None,
) -> ScanResult:
    """Parse a project, build IR, run rules, and apply suppressions/filters."""
    scan_root = (root or Path.cwd()).resolve()
    if config.jobs < 1:
        raise ConfigError("jobs must be at least 1")
    excludes = list(config.exclude)
    if config.exclude_tests:
        excludes.append("tests/")
    files = discover_python_files(paths, excludes=excludes, root=scan_root)
    if config.jobs == 1:
        parsed_files = [_parse_path(path, scan_root) for path in files]
    else:
        with ProcessPoolExecutor(max_workers=config.jobs) as executor:
            parsed_files = list(
                executor.map(_parse_path, files, [scan_root] * len(files))
            )

    modules: list[ParsedModule] = []
    sources: dict[Path, str] = {}
    parse_errors: list[ParseDiagnostic] = []
    for parsed_file in parsed_files:
        if parsed_file.module is None:
            assert parsed_file.diagnostic is not None
            parse_errors.append(parsed_file.diagnostic)
            continue
        modules.append(parsed_file.module)
        sources[parsed_file.module.path] = parsed_file.module.source

    manager = plugin_manager or PluginManager.default()
    adapters = [adapter() for adapter in manager.adapters()]
    system = IRBuilder(adapters).build_system(modules)
    selected_registry = registry or RuleRegistry(manager.rules())
    findings = selected_registry.run(
        _rule_context(system, scan_root, sources),
        selected=config.select,
        ignored=config.ignore,
    )
    findings = _apply_config(findings, config)
    findings = _filter_project_suppressions(findings, sources)
    findings = manager.apply_finding_modifiers(findings, system)
    return ScanResult(
        findings=tuple(sort_findings(findings)),
        scanned_files=tuple(files),
        parse_errors=tuple(parse_errors),
    )


def _parse_path(path: Path, root: Path) -> _ParsedFileResult:
    try:
        parsed = parse_file(path)
    except ParseError as error:
        relative = _relative_path(error.path, root)
        return _ParsedFileResult(
            module=None,
            diagnostic=ParseDiagnostic(relative, error.message, error.line, error.col),
        )
    relative = _relative_path(path, root)
    return _ParsedFileResult(replace(parsed, path=relative), diagnostic=None)


def scan_command(
    paths: Annotated[
        list[Path] | None, typer.Argument(help="Files or directories to scan.")
    ] = None,
    report_format: Annotated[
        Literal["text", "json"], typer.Option("--format", help="Report format.")
    ] = "text",
    output: Annotated[
        Path | None, typer.Option("--output", help="Write report to a file.")
    ] = None,
    select: Annotated[
        list[str] | None, typer.Option("--select", help="Rule patterns.")
    ] = None,
    ignore: Annotated[
        list[str] | None, typer.Option("--ignore", help="Ignored rule patterns.")
    ] = None,
    min_severity: Annotated[
        Severity | None, typer.Option("--min-severity", help="Minimum severity.")
    ] = None,
    min_confidence: Annotated[
        Confidence | None, typer.Option("--min-confidence", help="Minimum confidence.")
    ] = None,
    fail_on: Annotated[
        Literal["error", "warning", "never"] | None,
        typer.Option("--fail-on", help="Severity that fails the command."),
    ] = None,
    jobs: Annotated[
        int | None, typer.Option("--jobs", min=1, help="Analysis workers.")
    ] = None,
    baseline: Annotated[
        Path | None, typer.Option("--baseline", help="Ignore findings in a baseline.")
    ] = None,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Disable cache (reserved).")
    ] = False,
) -> None:
    """Scan Python agent code and report reliability findings."""
    del no_cache
    scan_paths = paths or [Path(".")]
    scan_root = _root_for_paths(scan_paths)
    try:
        config = merge_cli_config(
            load_config(scan_root),
            select=_split_patterns(select),
            ignore=_split_patterns(ignore),
            min_severity=min_severity,
            min_confidence=min_confidence,
            fail_on=fail_on,
            jobs=jobs,
        )
        result = analyze_project(scan_paths, config, root=scan_root)
        if baseline is not None:
            baseline_data = load_baseline(baseline)
            result = replace(
                result,
                findings=tuple(filter_baselined(result.findings, baseline_data)),
            )
    except (BaselineError, ConfigError, FileNotFoundError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error

    for diagnostic in result.parse_errors:
        typer.echo(
            f"warning: skipped {diagnostic.path}: {diagnostic.message}",
            err=True,
        )
    reporter = JsonReporter() if report_format == "json" else TextReporter()
    rendered = reporter.render(result.findings)
    if output is not None:
        output.write_text(rendered, encoding="utf-8")
    elif rendered:
        typer.echo(rendered, nl=False)
    raise typer.Exit(code=_exit_code(result.findings, config.fail_on))


def _rule_context(
    system: AgentSystem, root: Path, sources: dict[Path, str]
) -> RuleContext:
    return RuleContext(system, root=root, sources=sources)


def _root_for_paths(paths: list[Path]) -> Path:
    resolved = [path.resolve() for path in paths]
    cwd = Path.cwd().resolve()
    if all(_is_under(path, cwd) for path in resolved):
        return cwd
    common = Path(os.path.commonpath([str(path) for path in resolved]))
    return common if common.is_dir() else common.parent


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _relative_path(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root)
    except ValueError:
        return path


def _apply_config(findings: list[Finding], config: AgentGuardConfig) -> list[Finding]:
    severity_order = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}
    confidence_order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
    adjusted = [
        replace(
            finding,
            severity=config.severity.get(finding.rule_id, finding.severity),
        )
        for finding in findings
    ]
    return [
        finding
        for finding in adjusted
        if severity_order[finding.severity] >= severity_order[config.min_severity]
        and confidence_order[finding.confidence]
        >= confidence_order[config.min_confidence]
    ]


def _filter_project_suppressions(
    findings: list[Finding], sources: dict[Path, str]
) -> list[Finding]:
    return [
        finding
        for finding in findings
        if not parse_suppressions(sources.get(finding.loc.file, "")).is_suppressed(
            finding.rule_id, finding.loc.line
        )
    ]


def _split_patterns(patterns: list[str] | None) -> list[str] | None:
    if patterns is None:
        return None
    return [
        part.strip() for value in patterns for part in value.split(",") if part.strip()
    ]


def _exit_code(findings: list[Finding] | tuple[Finding, ...], fail_on: FailOn) -> int:
    if fail_on == FailOn.NEVER:
        return 0
    threshold = Severity.ERROR if fail_on == FailOn.ERROR else Severity.WARNING
    order = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}
    return (
        1
        if any(order[finding.severity] >= order[threshold] for finding in findings)
        else 0
    )
