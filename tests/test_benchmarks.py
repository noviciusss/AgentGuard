"""Tests for reproducible benchmark and corpus-gate helpers."""

from pathlib import Path

from benchmarks.corpus_gate import scan_path
from benchmarks.scan_10k import generate_source, run_benchmark


def test_generate_source_has_requested_line_count() -> None:
    source = generate_source(16)

    assert len(source.splitlines()) == 16
    assert "def node_0000(value):" in source
    assert "def node_0001(value):" in source


def test_small_benchmark_is_valid_and_deterministic(tmp_path: Path) -> None:
    result = run_benchmark(
        lines=16,
        repeats=2,
        budget_seconds=30.0,
        workdir=tmp_path / "benchmark",
    )

    assert result.lines == 16
    assert result.files == 1
    assert result.parse_errors == 0
    assert len(result.elapsed_seconds) == 2
    assert result.budget_passed


def test_corpus_gate_reports_files_lines_and_rule_counts(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    source.write_text(generate_source(16), encoding="utf-8")

    result = scan_path(source)

    assert result.python_files == 1
    assert result.lines == 16
    assert result.parse_errors == 0
    assert result.findings_by_rule == {}
