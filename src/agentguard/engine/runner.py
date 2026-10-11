"""Scan orchestration for parsed files and adapter-provided analyzers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from agentguard.engine.discovery import discover_python_files
from agentguard.engine.parser import ParsedModule, ParseError, parse_file
from agentguard.engine.suppression import filter_suppressed, parse_suppressions
from agentguard.findings import Finding, sort_findings

Analyzer: TypeAlias = Callable[[ParsedModule], Iterable[Finding]]


@dataclass(frozen=True)
class ParseDiagnostic:
    """A non-fatal parse failure encountered during a scan."""

    path: Path
    message: str
    line: int | None
    col: int | None


@dataclass(frozen=True)
class ScanResult:
    """Deterministic findings and diagnostics from one scan."""

    findings: tuple[Finding, ...]
    scanned_files: tuple[Path, ...]
    parse_errors: tuple[ParseDiagnostic, ...]


@dataclass(frozen=True)
class _FileScanResult:
    path: Path
    findings: tuple[Finding, ...]
    parse_error: ParseDiagnostic | None


def run_scan(
    paths: Iterable[Path],
    analyzer: Analyzer | None = None,
    *,
    excludes: Iterable[str] = (),
    jobs: int = 1,
    root: Path | None = None,
) -> ScanResult:
    """Discover, parse, analyze, and suppress findings for Python files.

    A parse failure is recorded and skipped. When ``jobs`` is greater than one,
    each file is analyzed in a separate process as required by the scan model;
    the analyzer must therefore be importable and pickleable.
    """
    if jobs < 1:
        raise ValueError("jobs must be at least 1")
    files = discover_python_files(paths, excludes=excludes, root=root)
    if jobs == 1:
        results = [_scan_file(path, analyzer) for path in files]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as executor:
            results = list(executor.map(_scan_file, files, [analyzer] * len(files)))

    findings = sort_findings(
        [finding for result in results for finding in result.findings]
    )
    parse_errors_list: list[ParseDiagnostic] = []
    for result in results:
        if result.parse_error is not None:
            parse_errors_list.append(result.parse_error)
    parse_errors = tuple(parse_errors_list)
    return ScanResult(
        findings=tuple(findings),
        scanned_files=tuple(files),
        parse_errors=parse_errors,
    )


def _scan_file(path: Path, analyzer: Analyzer | None) -> _FileScanResult:
    try:
        parsed = parse_file(path)
    except ParseError as error:
        return _FileScanResult(
            path=path,
            findings=(),
            parse_error=ParseDiagnostic(
                error.path, error.message, error.line, error.col
            ),
        )

    findings = list(analyzer(parsed)) if analyzer is not None else []
    filtered = filter_suppressed(findings, parse_suppressions(parsed.source))
    return _FileScanResult(path=path, findings=tuple(filtered), parse_error=None)
