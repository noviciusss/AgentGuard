"""Run a deterministic, no-network corpus scan summary."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from agentguard.cli.scan import analyze_project
from agentguard.config import AgentGuardConfig


@dataclass(frozen=True)
class CorpusResult:
    """Measured result for one local corpus path."""

    path: str
    python_files: int
    lines: int
    findings: int
    findings_by_rule: dict[str, int]
    parse_errors: int
    elapsed_seconds: float


def scan_path(path: Path, *, jobs: int = 1) -> CorpusResult:
    """Analyze one local file or directory without importing source code."""
    resolved = path.resolve()
    root = resolved if resolved.is_dir() else resolved.parent
    started = time.perf_counter()
    result = analyze_project(
        [resolved],
        AgentGuardConfig(jobs=jobs),
        root=root,
    )
    by_rule: dict[str, int] = {}
    lines = 0
    for scanned in result.scanned_files:
        try:
            lines += len(scanned.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError):
            continue
    for finding in result.findings:
        by_rule[finding.rule_id] = by_rule.get(finding.rule_id, 0) + 1
    return CorpusResult(
        path=resolved.as_posix(),
        python_files=len(result.scanned_files),
        lines=lines,
        findings=len(result.findings),
        findings_by_rule=dict(sorted(by_rule.items())),
        parse_errors=len(result.parse_errors),
        elapsed_seconds=time.perf_counter() - started,
    )


def main() -> None:
    """Run the corpus gate for the supplied local paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = [scan_path(path, jobs=args.jobs) for path in args.paths]
    rendered = json.dumps(
        [asdict(result) for result in results], indent=2, sort_keys=True
    )
    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
