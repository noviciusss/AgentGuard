"""Measure AgentGuard analysis on a deterministic 10,000-line fixture.

This benchmark measures the project analysis path, including parsing, IR
construction, rules, and plugin finding modifiers. It does not import or
execute the generated Python source.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_LINES = 10_000
DEFAULT_BUDGET_SECONDS = 5.0
_FUNCTION_LINES = (
    "def node_{index:04d}(value):",
    '    state = {{"value": value}}',
    "    if value:",
    '        state["value"] = value',
    "    else:",
    '        state["value"] = None',
    "    return state",
    "# benchmark separator",
)


@dataclass(frozen=True)
class BenchmarkResult:
    """Serializable result from one or more benchmark runs."""

    lines: int
    files: int
    findings: int
    parse_errors: int
    elapsed_seconds: list[float]
    median_seconds: float
    budget_seconds: float
    budget_passed: bool


def generate_source(lines: int = DEFAULT_LINES) -> str:
    """Return a valid deterministic Python module with exactly ``lines`` lines."""
    if lines < len(_FUNCTION_LINES) or lines % len(_FUNCTION_LINES) != 0:
        raise ValueError("lines must be a positive multiple of 8")
    function_count = lines // len(_FUNCTION_LINES)
    return "\n".join(
        line.format(index=index)
        for index in range(function_count)
        for line in _FUNCTION_LINES
    )


def run_benchmark(
    *,
    lines: int = DEFAULT_LINES,
    repeats: int = 1,
    jobs: int = 1,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    workdir: Path | None = None,
) -> BenchmarkResult:
    """Run the fixed-size analysis workload and return timing information."""
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if jobs < 1:
        raise ValueError("jobs must be at least 1")
    if budget_seconds <= 0:
        raise ValueError("budget_seconds must be positive")
    source = generate_source(lines)
    if workdir is None:
        with tempfile.TemporaryDirectory(prefix="agentguard-benchmark-") as value:
            return _run_in_directory(
                Path(value), source, lines, repeats, jobs, budget_seconds
            )
    workdir.mkdir(parents=True, exist_ok=True)
    return _run_in_directory(workdir, source, lines, repeats, jobs, budget_seconds)


def _run_in_directory(
    workdir: Path,
    source: str,
    lines: int,
    repeats: int,
    jobs: int,
    budget_seconds: float,
) -> BenchmarkResult:
    source_path = workdir / "benchmark_agent.py"
    source_path.write_text(source, encoding="utf-8")
    timings: list[float] = []
    finding_count = 0
    parse_error_count = 0
    scanned_file_count = 1
    for _ in range(repeats):
        started = time.perf_counter()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "agentguard",
                "scan",
                str(source_path),
                "--format",
                "json",
                "--fail-on",
                "never",
                "--no-cache",
                "--jobs",
                str(jobs),
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        timings.append(time.perf_counter() - started)
        if completed.returncode != 0:
            raise RuntimeError(
                f"benchmark scan failed with exit code {completed.returncode}: "
                f"{completed.stderr.strip()}"
            )
        payload = json.loads(completed.stdout)
        if not isinstance(payload, list):
            raise RuntimeError("benchmark scan did not return a JSON finding list")
        finding_count = len(payload)
    ordered = sorted(timings)
    median_seconds = ordered[len(ordered) // 2]
    return BenchmarkResult(
        lines=lines,
        files=scanned_file_count,
        findings=finding_count,
        parse_errors=parse_error_count,
        elapsed_seconds=timings,
        median_seconds=median_seconds,
        budget_seconds=budget_seconds,
        budget_passed=median_seconds <= budget_seconds,
    )


def main() -> None:
    """Run the benchmark command and print stable JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lines", type=int, default=DEFAULT_LINES)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--budget-seconds", type=float, default=DEFAULT_BUDGET_SECONDS)
    args = parser.parse_args()
    result = run_benchmark(
        lines=args.lines,
        repeats=args.repeats,
        jobs=args.jobs,
        budget_seconds=args.budget_seconds,
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
