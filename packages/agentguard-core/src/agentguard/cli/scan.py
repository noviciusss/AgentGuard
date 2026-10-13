"""Scan command and project-level analysis orchestration."""

from __future__ import annotations

import os
import tokenize
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
from agentguard.fixes import (
    FixEngine,
    FixError,
    preview_model_pin_fixes,
    preview_recursion_limit_fixes,
    preview_timeout_fixes,
)
from agentguard.ir.builder import IRBuilder
from agentguard.ir.models import AgentSystem
from agentguard.plugins.manager import PluginManager
from agentguard.reporters.base import Reporter
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
        system=system,
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
        Literal["text", "json", "sarif"],
        typer.Option("--format", help="Report format."),
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
    fix_dry_run: Annotated[
        bool, typer.Option("--fix-dry-run", help="Print safe autofix diffs.")
    ] = False,
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe autofixes to source files.")
    ] = False,
    fix_timeout: Annotated[
        int,
        typer.Option("--fix-timeout", min=1, help="Timeout seconds for AG003 fixes."),
    ] = 30,
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
        if fix_dry_run and fix:
            raise ConfigError("--fix-dry-run and --fix cannot be used together")
        result = analyze_project(scan_paths, config, root=scan_root)
        if baseline is not None:
            baseline_data = load_baseline(baseline)
            result = replace(
                result,
                findings=tuple(filter_baselined(result.findings, baseline_data)),
            )
        fix_diffs = _run_fixes(
            result.findings,
            root=scan_root,
            dry_run=fix_dry_run,
            apply=fix,
            timeout=fix_timeout,
            model_map=config.fix.model,
        )
    except (
        BaselineError,
        ConfigError,
        FixError,
        FileNotFoundError,
        ValueError,
    ) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error

    for diagnostic in result.parse_errors:
        typer.echo(
            f"warning: skipped {diagnostic.path}: {diagnostic.message}",
            err=True,
        )
    if fix_diffs:
        typer.echo("".join(fix_diffs), nl=False)
    reporter = _reporter(report_format, PluginManager.default())
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


def _reporter(report_format: str, manager: PluginManager) -> Reporter:
    for reporter_class in manager.reporters():
        if reporter_class.format_name == report_format:
            return reporter_class()
    raise ConfigError(f"reporter format is not installed: {report_format}")


def _run_fixes(
    findings: tuple[Finding, ...],
    *,
    root: Path,
    dry_run: bool,
    apply: bool,
    timeout: int,
    model_map: dict[str, str],
) -> list[str]:
    if not dry_run and not apply:
        return []
    by_file: dict[Path, list[Finding]] = {}
    for finding in findings:
        if finding.rule_id in {"AG003", "AG004"}:
            by_file.setdefault(root / finding.loc.file, []).append(finding)
    diffs: list[str] = []
    engine = FixEngine()
    for path in sorted(by_file, key=lambda item: item.as_posix()):
        with tokenize.open(path) as stream:
            source = stream.read()
        current_source = source
        timeout_result = preview_timeout_fixes(
            path, current_source, by_file[path], timeout
        )
        recursion_result = preview_recursion_limit_fixes(
            path,
            timeout_result.after if timeout_result is not None else current_source,
            by_file[path],
            25,
        )
        recursion_source = (
            recursion_result.after
            if recursion_result is not None
            else (
                timeout_result.after if timeout_result is not None else current_source
            )
        )
        model_result = preview_model_pin_fixes(
            path, recursion_source, by_file[path], model_map
        )
        for result in (timeout_result, recursion_result, model_result):
            if result is None:
                continue
            if not result.changed:
                continue
            current_source = result.after
            if apply:
                engine.apply(result)
            if dry_run:
                diffs.append(result.diff)
    return diffs


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
