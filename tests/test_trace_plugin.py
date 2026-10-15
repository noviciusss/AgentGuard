"""Focused parser, heuristic, and CLI tests for the trace plugin."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from agentguard_trace import (
    TraceInputError,
    analyze_spans,
    load_spans,
    trace_command,
)


def _write_json(tmp_path: Path, payload: object, name: str = "trace.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_flat_span_duration_remains_supported(tmp_path: Path) -> None:
    path = _write_json(
        tmp_path,
        {"spans": [{"name": "node", "duration": 12, "status": "error"}]},
    )

    spans = load_spans(path)

    assert spans[0].name == "node"
    assert spans[0].duration_ms == 12
    assert spans[0].status == "error"
    assert spans[0].trace_id is None


def test_nested_otlp_json_normalizes_ids_timestamps_status_and_typed_attributes(
    tmp_path: Path,
) -> None:
    path = _write_json(
        tmp_path,
        {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "bot"}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "instrumentation"},
                            "spans": [
                                {
                                    "name": "model.call",
                                    "traceId": "ABC",
                                    "spanId": "DEF",
                                    "parentSpanId": "ROOT",
                                    "startTimeUnixNano": "1000000000",
                                    "endTimeUnixNano": "1125000000",
                                    "attributes": [
                                        {
                                            "key": "gen_ai.request.model",
                                            "value": {"stringValue": "model-a"},
                                        },
                                        {
                                            "key": "llm.cost",
                                            "value": {"doubleValue": 0.12},
                                        },
                                        {
                                            "key": "attempt",
                                            "value": {"intValue": "2"},
                                        },
                                        {
                                            "key": "flags",
                                            "value": {
                                                "arrayValue": {
                                                    "values": [
                                                        {"boolValue": True},
                                                        {"stringValue": "x"},
                                                    ]
                                                }
                                            },
                                        },
                                    ],
                                    "status": {"code": 2, "message": "failed"},
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )

    span = load_spans(path)[0]

    assert span.trace_id == "abc"
    assert span.span_id == "def"
    assert span.parent_span_id == "root"
    assert span.parent_id == "root"
    assert span.start_time_ns == 1_000_000_000
    assert span.end_time_ns == 1_125_000_000
    assert span.start_time == span.start_time_ns
    assert span.end_time == span.end_time_ns
    assert span.duration_ms == 125
    assert span.status == "error"
    assert span.attributes["service.name"] == "bot"
    assert span.attributes["attempt"] == 2
    assert span.attributes["flags"] == [True, "x"]
    assert span.model == "model-a"
    assert span.cost == 0.12


def test_langsmith_runs_list_and_nested_children_inherit_trace_relationships(
    tmp_path: Path,
) -> None:
    path = _write_json(
        tmp_path,
        {
            "runs": [
                {
                    "id": "ROOT",
                    "name": "agent",
                    "run_type": "chain",
                    "start_time": "2025-01-01T00:00:00Z",
                    "end_time": "2025-01-01T00:00:00.100000Z",
                    "child_runs": [
                        {
                            "id": "C1",
                            "name": "step",
                            "run_type": "chain",
                            "start_time": "2025-01-01T00:00:00.010000Z",
                            "end_time": "2025-01-01T00:00:00.020000Z",
                        },
                        {
                            "id": "C2",
                            "name": "step",
                            "run_type": "chain",
                            "start_time": "2025-01-01T00:00:00.030000Z",
                            "end_time": "2025-01-01T00:00:00.040000Z",
                        },
                    ],
                }
            ]
        },
    )

    spans = load_spans(path)

    assert [span.span_id for span in spans] == ["root", "c1", "c2"]
    assert all(span.trace_id == "root" for span in spans)
    assert spans[1].parent_span_id == "root"
    assert spans[2].start_time_ns == 1_735_689_600_030_000_000


def test_top_level_langsmith_run_list_is_detected_without_runs_wrapper(
    tmp_path: Path,
) -> None:
    path = _write_json(
        tmp_path,
        [
            {
                "id": "root",
                "name": "agent",
                "run_type": "chain",
                "start_time": "2025-01-01T00:00:00Z",
            },
            {
                "id": "child",
                "name": "step",
                "run_type": "llm",
                "parent_run_id": "root",
                "start_time": "2025-01-01T00:00:00Z",
                "extra": {"metadata": {"ls_model_name": "model-a"}},
                "total_cost": 0.25,
            },
        ],
    )

    spans = load_spans(path)

    assert spans[0].trace_id == "root"
    assert spans[1].parent_span_id == "root"
    assert spans[1].model == "model-a"
    assert spans[1].cost == 0.25


def test_repetition_is_trace_local_and_skips_spans_without_trace_ids(
    tmp_path: Path,
) -> None:
    path = _write_json(
        tmp_path,
        [
            {"name": "step", "trace_id": "a", "span_id": "a1"},
            {"name": "step", "trace_id": "a", "span_id": "a2"},
            {"name": "step", "trace_id": "b", "span_id": "b1"},
            {"name": "step", "trace_id": "b", "span_id": "b2"},
            {"name": "step"},
            {"name": "step"},
        ],
    )

    findings = analyze_spans(load_spans(path), min_occurrences=2)

    assert [finding["identity"] for finding in findings] == [
        "TRACE001:a:step",
        "TRACE001:b:step",
    ]


def test_duplicate_span_ids_do_not_inflate_repetition_or_cost_findings(
    tmp_path: Path,
) -> None:
    path = _write_json(
        tmp_path,
        [
            {"name": "step", "trace_id": "trace", "span_id": "one"},
            {"name": "step", "trace_id": "trace", "span_id": "two"},
            {"name": "step", "trace_id": "trace", "span_id": "three"},
            {
                "name": "model-call",
                "trace_id": "trace",
                "span_id": "expensive",
                "model": "model-a",
                "cost": 10,
            },
            {
                "name": "model-call",
                "trace_id": "trace",
                "span_id": "cheap-1",
                "model": "model-a",
                "cost": 1,
            },
            {
                "name": "model-call",
                "trace_id": "trace",
                "span_id": "cheap-2",
                "model": "model-a",
                "cost": 1,
            },
            {
                "name": "model-call",
                "trace_id": "trace",
                "span_id": "cheap-3",
                "model": "model-a",
                "cost": 1,
            },
            {
                "name": "model-call",
                "trace_id": "trace",
                "span_id": "expensive",
                "model": "model-a",
                "cost": 10,
            },
        ],
    )

    findings = analyze_spans(
        load_spans(path), min_occurrences=99, cost_multiplier=3, min_cost_samples=3
    )

    assert [finding["rule_id"] for finding in findings] == ["TRACE002"]
    assert findings[0]["span_id"] == "expensive"


def test_cost_findings_use_explicit_maximum_and_comparable_median_only() -> None:
    from agentguard_trace import TraceSpan

    spans = [
        TraceSpan("model", 0, "ok", {}, "t1", "s1", model="model-a", cost=1),
        TraceSpan("model", 0, "ok", {}, "t2", "s2", model="model-a", cost=1),
        TraceSpan("model", 0, "ok", {}, "t3", "s3", model="model-a", cost=1),
        TraceSpan("model", 0, "ok", {}, "t4", "s4", model="model-a", cost=10),
        TraceSpan("model", 0, "ok", {}, "t5", "s5", model="model-b", cost=10),
        TraceSpan("tokens-only", 0, "ok", {"prompt_tokens": 999_999}, "t6", "s6"),
    ]

    findings = analyze_spans(spans, max_cost=20, cost_multiplier=3, min_cost_samples=3)

    assert len(findings) == 1
    assert findings[0]["rule_id"] == "TRACE002"
    assert findings[0]["cost"] == 10
    assert findings[0]["baseline_median"] == 1
    assert findings[0]["confidence"] == "high"

    threshold_findings = analyze_spans(spans, max_cost=5, min_cost_samples=99)
    assert [finding["cost"] for finding in threshold_findings] == [10, 10]


def test_cost_without_trace_id_is_low_confidence_but_still_real() -> None:
    from agentguard_trace import TraceSpan

    findings = analyze_spans([TraceSpan("model", 0, "ok", {}, cost=2)], max_cost=1)

    assert findings[0]["rule_id"] == "TRACE002"
    assert findings[0]["confidence"] == "low"


def test_cli_writes_the_same_json_to_stdout_and_output_file(tmp_path: Path) -> None:
    input_path = _write_json(
        tmp_path,
        [
            {"name": "step", "trace_id": "trace", "span_id": "a"},
            {"name": "step", "trace_id": "trace", "span_id": "b"},
        ],
    )
    output_path = tmp_path / "findings.json"
    app = typer.Typer()
    app.command()(trace_command)

    result = CliRunner().invoke(
        app,
        [str(input_path), "--min-occurrences", "2", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.read_text(encoding="utf-8") == result.stdout
    assert json.loads(result.stdout)[0]["rule_id"] == "TRACE001"


@pytest.mark.parametrize(
    "payload",
    [None, [], {"spans": []}, {"resourceSpans": []}, "not a trace"],
)
def test_empty_or_wrong_shape_is_a_controlled_cli_error(
    tmp_path: Path, payload: object
) -> None:
    path = _write_json(tmp_path, payload)
    app = typer.Typer()
    app.command()(trace_command)

    result = CliRunner().invoke(app, [str(path)])

    assert result.exit_code == 2
    assert "error:" in result.output


@pytest.mark.parametrize(
    "payload",
    [
        [{"name": "step", "duration": -1}],
        [{"name": "step", "cost": -1}],
        [{"name": "step", "cost": float("nan")}],
    ],
)
def test_malformed_numeric_input_is_a_controlled_cli_error(
    tmp_path: Path, payload: object
) -> None:
    path = _write_json(tmp_path, payload)
    app = typer.Typer()
    app.command()(trace_command)

    result = CliRunner().invoke(app, [str(path)])

    assert result.exit_code == 2
    assert "finite nonnegative" in result.output or "nonnegative" in result.output


def test_invalid_cli_numeric_options_raise_usage_error(tmp_path: Path) -> None:
    path = _write_json(tmp_path, [{"name": "step"}])
    app = typer.Typer()
    app.command()(trace_command)

    result = CliRunner().invoke(app, [str(path), "--max-cost", "nan"])

    assert result.exit_code == 2
    assert "max-cost" in result.output


def test_load_spans_exposes_direct_validation_errors(tmp_path: Path) -> None:
    path = _write_json(tmp_path, [{"name": "step", "end_time": "bad"}])

    with pytest.raises(TraceInputError, match="ISO timestamp"):
        load_spans(path)


def test_missing_span_name_is_a_malformed_export(tmp_path: Path) -> None:
    path = _write_json(tmp_path, [{"duration": 1}])

    with pytest.raises(TraceInputError, match="non-empty string name"):
        load_spans(path)
