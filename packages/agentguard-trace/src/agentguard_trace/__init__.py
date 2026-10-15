"""Offline LangSmith/OpenTelemetry trace ingestion and anomaly reporting."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from statistics import median
from typing import Annotated, cast

import typer

from agentguard.plugins import hookimpl

JsonObject = dict[str, object]


class TraceInputError(ValueError):
    """Raised when a trace export cannot be safely normalized."""


@dataclass(frozen=True)
class TraceSpan:
    """Normalized local trace span.

    ``start_time_ns`` and ``end_time_ns`` use Unix nanoseconds when the source
    provides timestamps. Cost is populated only from an explicitly reported
    cost field; token counts are deliberately not used to estimate it.
    """

    name: str
    duration_ms: float
    status: str
    attributes: dict[str, object]
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    start_time_ns: int | None = None
    end_time_ns: int | None = None
    model: str | None = None
    cost: float | None = None

    @property
    def parent_id(self) -> str | None:
        """Return the normalized parent identifier."""
        return self.parent_span_id

    @property
    def start_time(self) -> int | None:
        """Return the normalized start timestamp in Unix nanoseconds."""
        return self.start_time_ns

    @property
    def end_time(self) -> int | None:
        """Return the normalized end timestamp in Unix nanoseconds."""
        return self.end_time_ns

    @property
    def identity(self) -> str:
        """Return a deterministic identity for deduplication and findings."""
        if self.span_id is not None:
            return f"id:{self.trace_id or ''}:{self.span_id}"
        value = {
            "attributes": self.attributes,
            "duration_ms": self.duration_ms,
            "end_time_ns": self.end_time_ns,
            "model": self.model,
            "name": self.name,
            "parent_span_id": self.parent_span_id,
            "start_time_ns": self.start_time_ns,
            "status": self.status,
            "trace_id": self.trace_id,
        }
        return "value:" + json.dumps(value, sort_keys=True, separators=(",", ":"))


class Plugin:
    """Register local ``agentguard trace`` ingestion."""

    name = "agentguard-trace"

    @hookimpl
    def register_commands(self, app: typer.Typer) -> None:
        app.command("trace")(trace_command)


def trace_command(
    input_path: Annotated[Path, typer.Argument(help="Trace JSON export.")],
    output: Annotated[
        Path | None, typer.Option("--output", help="Also write findings JSON.")
    ] = None,
    min_occurrences: Annotated[
        int, typer.Option("--min-occurrences", help="Minimum repeated spans.")
    ] = 3,
    max_cost: Annotated[
        float | None,
        typer.Option("--max-cost", help="Flag explicit costs above this value."),
    ] = None,
    cost_multiplier: Annotated[
        float,
        typer.Option(
            "--cost-multiplier",
            help="Flag a cost above this multiple of its peer median.",
        ),
    ] = 3.0,
    min_cost_samples: Annotated[
        int,
        typer.Option("--min-cost-samples", help="Peer samples needed for a median."),
    ] = 3,
) -> None:
    """Ingest local trace JSON and flag trace-local repetition and cost spikes."""
    try:
        _validate_options(
            min_occurrences=min_occurrences,
            max_cost=max_cost,
            cost_multiplier=cost_multiplier,
            min_cost_samples=min_cost_samples,
        )
        spans = load_spans(input_path)
        findings = analyze_spans(
            spans,
            min_occurrences=min_occurrences,
            max_cost=max_cost,
            cost_multiplier=cost_multiplier,
            min_cost_samples=min_cost_samples,
        )
        rendered = json.dumps(findings, indent=2, sort_keys=True) + "\n"
        if output is not None:
            output.write_text(rendered, encoding="utf-8")
        typer.echo(rendered, nl=False)
    except (OSError, TraceInputError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=2) from error


def load_spans(path: Path) -> list[TraceSpan]:
    """Load flat, LangSmith, or nested OTLP JSON into normalized spans."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise TraceInputError(f"cannot read trace JSON: {error}") from error
    try:
        payload = cast(object, json.loads(text))
    except json.JSONDecodeError as error:
        raise TraceInputError(f"invalid trace JSON: {error.msg}") from error
    return _parse_document(payload)


def analyze_spans(
    spans: Sequence[TraceSpan],
    *,
    min_occurrences: int = 3,
    max_cost: float | None = None,
    cost_multiplier: float = 3.0,
    min_cost_samples: int = 3,
) -> list[JsonObject]:
    """Return deterministic loop and explicit-cost findings for normalized spans."""
    _validate_options(
        min_occurrences=min_occurrences,
        max_cost=max_cost,
        cost_multiplier=cost_multiplier,
        min_cost_samples=min_cost_samples,
    )
    unique_spans = _deduplicate_spans(spans)
    findings = _repetition_findings(unique_spans, min_occurrences)
    findings.extend(
        _cost_findings(
            unique_spans,
            max_cost=max_cost,
            cost_multiplier=cost_multiplier,
            min_cost_samples=min_cost_samples,
        )
    )
    return sorted(
        findings, key=lambda item: (str(item["rule_id"]), str(item["identity"]))
    )


def _validate_options(
    *,
    min_occurrences: int,
    max_cost: float | None,
    cost_multiplier: float,
    min_cost_samples: int,
) -> None:
    if not isinstance(min_occurrences, int) or isinstance(min_occurrences, bool):
        raise TraceInputError("min-occurrences must be an integer greater than zero")
    if min_occurrences < 1:
        raise TraceInputError("min-occurrences must be an integer greater than zero")
    if not isinstance(min_cost_samples, int) or isinstance(min_cost_samples, bool):
        raise TraceInputError("min-cost-samples must be an integer greater than zero")
    if min_cost_samples < 1:
        raise TraceInputError("min-cost-samples must be an integer greater than zero")
    _validate_number(cost_multiplier, "cost-multiplier")
    if max_cost is not None:
        _validate_number(max_cost, "max-cost")


def _validate_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TraceInputError(f"{label} must be a finite nonnegative number")
    number = float(value)
    if not isfinite(number) or number < 0:
        raise TraceInputError(f"{label} must be a finite nonnegative number")
    return number


def _parse_document(payload: object) -> list[TraceSpan]:
    if isinstance(payload, list):
        records = _objects(payload)
        source = (
            "langsmith"
            if any(_looks_like_langsmith_run(item) for item in records)
            else "flat"
        )
        if source == "langsmith":
            spans = _walk_langsmith_runs(_infer_langsmith_trace_ids(records))
        else:
            spans = [_normalize_record(item, source=source) for item in records]
    elif isinstance(payload, Mapping):
        document = _object(payload, "trace document")
        if "resourceSpans" in document or "resource_spans" in document:
            spans = _parse_otlp(document)
        elif "runs" in document:
            spans = _parse_langsmith_runs(document["runs"])
        elif "spans" in document:
            spans = [
                _normalize_record(item, source="flat")
                for item in _objects(document["spans"])
            ]
        elif _looks_like_span(document):
            spans = [_normalize_record(document, source="flat")]
        else:
            raise TraceInputError(
                "trace JSON must be a span list, a spans/runs object, or an "
                "OTLP resourceSpans object"
            )
    else:
        raise TraceInputError("trace JSON must contain an object or list")
    if not spans:
        raise TraceInputError("trace JSON contains no spans")
    return _deduplicate_spans(spans)


def _parse_langsmith_runs(value: object) -> list[TraceSpan]:
    runs = _objects(value, label="LangSmith runs")
    runs = _infer_langsmith_trace_ids(runs)
    spans = _walk_langsmith_runs(runs)
    if not spans:
        raise TraceInputError("trace JSON contains no LangSmith runs")
    return spans


def _infer_langsmith_trace_ids(runs: Sequence[JsonObject]) -> list[JsonObject]:
    resolved: dict[str, str] = {}
    for run in runs:
        run_id = _identifier(run, "id", "run_id", "runId")
        parent_id = _identifier(
            run, "parent_run_id", "parentRunId", "parent_span_id", "parentSpanId"
        )
        trace_id = _identifier(run, "trace_id", "traceId")
        if run_id is not None and trace_id is not None:
            resolved[run_id] = trace_id
        elif run_id is not None and parent_id is None:
            resolved[run_id] = run_id
    changed = True
    while changed:
        changed = False
        for run in runs:
            run_id = _identifier(run, "id", "run_id", "runId")
            parent_id = _identifier(
                run, "parent_run_id", "parentRunId", "parent_span_id", "parentSpanId"
            )
            if run_id is not None and run_id not in resolved and parent_id in resolved:
                resolved[run_id] = resolved[parent_id]
                changed = True
    result: list[JsonObject] = []
    for run in runs:
        current = dict(run)
        run_id = _identifier(run, "id", "run_id", "runId")
        if run_id is not None and not _has_any(current, ("trace_id", "traceId")):
            trace_id = resolved.get(run_id)
            if trace_id is not None:
                current["trace_id"] = trace_id
        result.append(current)
    return result


def _walk_langsmith_runs(
    runs: Sequence[JsonObject],
    *,
    inherited_parent_id: str | None = None,
    inherited_trace_id: str | None = None,
) -> list[TraceSpan]:
    spans: list[TraceSpan] = []
    for run in runs:
        current = dict(run)
        if inherited_parent_id is not None and not _has_any(
            current, ("parent_run_id", "parentRunId", "parent_span_id", "parentSpanId")
        ):
            current["parent_run_id"] = inherited_parent_id
        if inherited_trace_id is not None and not _has_any(
            current, ("trace_id", "traceId")
        ):
            current["trace_id"] = inherited_trace_id
        span = _normalize_record(current, source="langsmith")
        spans.append(span)
        child_value = current.get("child_runs", current.get("childRuns", []))
        if child_value is not None:
            children = _objects(child_value, label="LangSmith child_runs")
            spans.extend(
                _walk_langsmith_runs(
                    children,
                    inherited_parent_id=span.span_id,
                    inherited_trace_id=span.trace_id,
                )
            )
    return spans


def _parse_otlp(document: JsonObject) -> list[TraceSpan]:
    resource_value = document.get("resourceSpans", document.get("resource_spans"))
    resources = _objects(resource_value, label="OTLP resourceSpans")
    spans: list[TraceSpan] = []
    for resource_span in resources:
        resource = _object(resource_span.get("resource", {}), "OTLP resource")
        resource_attributes = _parse_attributes(resource.get("attributes", {}))
        scopes_value = resource_span.get(
            "scopeSpans", resource_span.get("scope_spans", [])
        )
        scopes = _objects(scopes_value, label="OTLP scopeSpans")
        for scope in scopes:
            raw_spans = scope.get("spans", [])
            for raw_span in _objects(raw_spans, label="OTLP spans"):
                spans.append(
                    _normalize_record(
                        raw_span,
                        source="otlp",
                        inherited_attributes=resource_attributes,
                    )
                )
    if not spans:
        raise TraceInputError("trace JSON contains no OTLP spans")
    return spans


def _normalize_record(
    record: JsonObject,
    *,
    source: str,
    inherited_attributes: Mapping[str, object] | None = None,
) -> TraceSpan:
    name_value = record.get("name", record.get("run_name"))
    if not isinstance(name_value, str) or not name_value.strip():
        raise TraceInputError("each trace span must have a non-empty string name")
    name = name_value.strip()
    attributes = dict(inherited_attributes or {})
    attributes.update(_record_attributes(record, source=source))
    trace_id = _identifier(record, "trace_id", "traceId")
    span_id = _identifier(record, "span_id", "spanId", "id", "run_id", "runId")
    parent_span_id = _identifier(
        record,
        "parent_span_id",
        "parentSpanId",
        "parent_run_id",
        "parentRunId",
        "parent_id",
        "parentId",
    )
    if source == "langsmith" and trace_id is None and parent_span_id is None:
        trace_id = span_id
    start_time_ns, end_time_ns = _timestamps(record, source=source)
    duration_ms = _duration(
        record, start_time_ns=start_time_ns, end_time_ns=end_time_ns
    )
    status = _status(record, source=source)
    model = _model(record, attributes)
    cost = _cost(record, attributes)
    return TraceSpan(
        name=name,
        duration_ms=duration_ms,
        status=status,
        attributes=attributes,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        start_time_ns=start_time_ns,
        end_time_ns=end_time_ns,
        model=model,
        cost=cost,
    )


def _record_attributes(record: JsonObject, *, source: str) -> dict[str, object]:
    attributes = _parse_attributes(record.get("attributes", {}))
    metadata = record.get("metadata")
    if isinstance(metadata, Mapping):
        attributes.update(_parse_attributes(metadata))
    extra = record.get("extra")
    if isinstance(extra, Mapping):
        extra_metadata = extra.get("metadata")
        if isinstance(extra_metadata, Mapping):
            attributes.update(_parse_attributes(extra_metadata))
        invocation_params = extra.get("invocation_params")
        if isinstance(invocation_params, Mapping):
            attributes.update(_parse_attributes(invocation_params))
    if source == "langsmith":
        serialized = record.get("serialized")
        if isinstance(serialized, Mapping):
            kwargs = serialized.get("kwargs")
            if isinstance(kwargs, Mapping):
                attributes.update(_parse_attributes(kwargs))
    return attributes


def _parse_attributes(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, list):
        result: dict[str, object] = {}
        for item in value:
            entry = _object(item, "trace attributes entry")
            key = entry.get("key")
            if not isinstance(key, str) or not key:
                raise TraceInputError("trace attribute entries need string keys")
            if "value" not in entry:
                raise TraceInputError(f"trace attribute {key!r} has no value")
            result[key] = _typed_value(entry["value"])
        return result
    if not isinstance(value, Mapping):
        raise TraceInputError("trace attributes must be an object or OTLP list")
    return {
        str(key): _typed_value(item)
        for key, item in cast(Mapping[object, object], value).items()
    }


def _typed_value(value: object) -> object:
    if not isinstance(value, Mapping):
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [_typed_value(item) for item in value]
        raise TraceInputError("trace attributes contain an unsupported value")
    mapping = cast(Mapping[object, object], value)
    wrapper_keys = {
        "stringValue",
        "boolValue",
        "intValue",
        "doubleValue",
        "bytesValue",
        "arrayValue",
        "kvlistValue",
    }
    present = [key for key in wrapper_keys if key in mapping]
    if len(present) == 1:
        key = present[0]
        item = mapping[key]
        if key == "arrayValue":
            array = _object(item, "OTLP arrayValue")
            values = array.get("values", [])
            if not isinstance(values, list):
                raise TraceInputError("OTLP arrayValue.values must be a list")
            return [_typed_value(element) for element in values]
        if key == "kvlistValue":
            kvlist = _object(item, "OTLP kvlistValue")
            return _parse_attributes(kvlist.get("values", []))
        if key == "intValue":
            if isinstance(item, int) and not isinstance(item, bool):
                return item
            if isinstance(item, str) and item.lstrip("-").isdigit():
                return int(item)
            raise TraceInputError("OTLP intValue must be an integer")
        return _typed_value(item)
    return {str(key): _typed_value(item) for key, item in mapping.items()}


def _timestamps(record: JsonObject, *, source: str) -> tuple[int | None, int | None]:
    if source == "otlp":
        start = _unix_nano(
            record.get("startTimeUnixNano", record.get("start_time_unix_nano")),
            "startTimeUnixNano",
        )
        end = _unix_nano(
            record.get("endTimeUnixNano", record.get("end_time_unix_nano")),
            "endTimeUnixNano",
        )
    else:
        start = _timestamp(
            record.get(
                "start_time_ns", record.get("start_time", record.get("startTime"))
            ),
            "start_time",
        )
        end = _timestamp(
            record.get("end_time_ns", record.get("end_time", record.get("endTime"))),
            "end_time",
        )
    if start is not None and end is not None and end < start:
        raise TraceInputError("trace span end timestamp precedes its start timestamp")
    return start, end


def _unix_nano(value: object, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TraceInputError(f"{label} must be a nonnegative Unix-nanosecond integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdigit():
        result = int(value)
    else:
        raise TraceInputError(f"{label} must be a nonnegative Unix-nanosecond integer")
    if result < 0:
        raise TraceInputError(f"{label} must be a nonnegative Unix-nanosecond integer")
    return result


def _timestamp(value: object, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TraceInputError(f"{label} must be a valid timestamp")
    if isinstance(value, int):
        if value < 0:
            raise TraceInputError(f"{label} must be a nonnegative timestamp")
        return value
    if isinstance(value, float):
        if not isfinite(value) or value < 0:
            raise TraceInputError(f"{label} must be a finite nonnegative timestamp")
        return int(value * 1_000_000_000)
    if not isinstance(value, str):
        raise TraceInputError(f"{label} must be a timestamp string or number")
    if value.isdigit():
        return int(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise TraceInputError(f"{label} is not a valid ISO timestamp") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = parsed - epoch
    if delta.total_seconds() < 0:
        raise TraceInputError(f"{label} must be a finite nonnegative timestamp")
    return (
        delta.days * 86_400 * 1_000_000_000
        + delta.seconds * 1_000_000_000
        + delta.microseconds * 1_000
    )


def _duration(
    record: JsonObject,
    *,
    start_time_ns: int | None,
    end_time_ns: int | None,
) -> float:
    value = record.get("duration_ms", record.get("duration"))
    if value is not None:
        return _validate_number(value, "duration")
    if start_time_ns is not None and end_time_ns is not None:
        return (end_time_ns - start_time_ns) / 1_000_000
    return 0.0


def _status(record: JsonObject, *, source: str) -> str:
    value = record.get("status")
    if isinstance(value, Mapping):
        code = value.get("code")
        if code == 2 or str(code).upper() == "ERROR":
            return "error"
        if code == 1 or str(code).upper() == "UNSET":
            return "unset"
        return "ok"
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"error", "failed", "failure"}:
            return "error"
        if normalized in {"unset", "unknown"}:
            return normalized
        return "ok"
    if source == "langsmith" and record.get("error") not in (None, "", False):
        return "error"
    return "ok"


def _model(record: JsonObject, attributes: Mapping[str, object]) -> str | None:
    keys = (
        "model",
        "model_name",
        "modelName",
        "ls_model_name",
        "model_id",
        "modelId",
    )
    value = _first_value((record, attributes), keys)
    if value is None:
        for key in ("gen_ai.request.model", "llm.model_name", "ls_model_name"):
            value = attributes.get(key)
            if value is not None:
                break
    if value is None:
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise TraceInputError("model must be a scalar string or number")
    return str(value)


def _cost(record: JsonObject, attributes: Mapping[str, object]) -> float | None:
    keys = (
        "cost",
        "total_cost",
        "totalCost",
        "cost_usd",
        "total_cost_usd",
        "totalCostUsd",
        "price",
    )
    value = _first_value((record, attributes), keys)
    if value is not None:
        return _validate_number(value, "explicit cost")
    for key, item in attributes.items():
        if key.rsplit(".", 1)[-1] in {"cost", "total_cost", "totalCost"}:
            return _validate_number(item, "explicit cost")
    component_values = [
        attributes.get("prompt_cost"),
        attributes.get("completion_cost"),
        record.get("prompt_cost"),
        record.get("completion_cost"),
    ]
    components = [item for item in component_values if item is not None]
    if not components:
        return None
    return sum(_validate_number(item, "explicit cost component") for item in components)


def _first_value(
    sources: Sequence[Mapping[str, object]], keys: Sequence[str]
) -> object | None:
    for source in sources:
        for key in keys:
            if key in source:
                return source[key]
    return None


def _identifier(record: JsonObject, *keys: str) -> str | None:
    value = _first_value((record,), keys)
    if value is None:
        return None
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise TraceInputError(f"trace identifier {keys[0]!r} must be a string")
    normalized = str(value).strip().lower()
    if not normalized:
        raise TraceInputError(f"trace identifier {keys[0]!r} cannot be empty")
    return normalized


def _looks_like_span(value: Mapping[str, object]) -> bool:
    return "name" in value or "run_name" in value


def _looks_like_langsmith_run(value: Mapping[str, object]) -> bool:
    return any(
        key in value
        for key in (
            "run_type",
            "runType",
            "run_id",
            "start_time",
            "parent_run_id",
            "trace_id",
            "inputs",
            "outputs",
        )
    )


def _has_any(value: Mapping[str, object], keys: Sequence[str]) -> bool:
    return any(key in value and value[key] is not None for key in keys)


def _object(value: object, label: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise TraceInputError(f"{label} must be an object")
    return {
        str(key): item for key, item in cast(Mapping[object, object], value).items()
    }


def _objects(value: object, *, label: str = "trace spans") -> list[JsonObject]:
    if not isinstance(value, list):
        raise TraceInputError(f"{label} must be a list")
    result: list[JsonObject] = []
    for item in value:
        result.append(_object(item, label[:-1] if label.endswith("s") else label))
    return result


def _deduplicate_spans(spans: Sequence[TraceSpan]) -> list[TraceSpan]:
    seen: set[str] = set()
    result: list[TraceSpan] = []
    for span in spans:
        if span.span_id is not None and span.identity in seen:
            continue
        if span.span_id is not None:
            seen.add(span.identity)
        result.append(span)
    return result


def _repetition_findings(
    spans: Sequence[TraceSpan], min_occurrences: int
) -> list[JsonObject]:
    grouped: dict[tuple[str, str], list[TraceSpan]] = {}
    for span in spans:
        if span.trace_id is None:
            continue
        grouped.setdefault((span.trace_id, span.name), []).append(span)
    findings: list[JsonObject] = []
    for (trace_id, name), matching in sorted(grouped.items()):
        if len(matching) < min_occurrences:
            continue
        identity = f"TRACE001:{trace_id}:{name}"
        findings.append(
            {
                "confidence": "high",
                "identity": identity,
                "message": (
                    f"Trace {trace_id!r} repeated span {name!r} {len(matching)} times."
                ),
                "occurrences": len(matching),
                "operation": name,
                "rule_id": "TRACE001",
                "trace_id": trace_id,
            }
        )
    return findings


def _cost_findings(
    spans: Sequence[TraceSpan],
    *,
    max_cost: float | None,
    cost_multiplier: float,
    min_cost_samples: int,
) -> list[JsonObject]:
    comparable: dict[tuple[str, str], list[TraceSpan]] = {}
    for span in spans:
        if span.cost is not None:
            comparable.setdefault((span.name, span.model or ""), []).append(span)

    findings: list[JsonObject] = []
    for span in spans:
        if span.cost is None:
            continue
        signals: list[str] = []
        if max_cost is not None and span.cost > max_cost:
            signals.append("max-cost")
        peers = [
            peer.cost
            for peer in comparable[(span.name, span.model or "")]
            if peer.identity != span.identity and peer.cost is not None
        ]
        baseline: float | None = None
        if len(peers) >= min_cost_samples:
            baseline = float(median(peers))
            if span.cost > baseline * cost_multiplier:
                signals.append("baseline-outlier")
        if not signals:
            continue
        identity = f"TRACE002:{span.identity}"
        reason = " and ".join(signals)
        message = f"Explicit cost {span.cost:g} for span {span.name!r} is a {reason}."
        finding: JsonObject = {
            "confidence": "high" if span.trace_id is not None else "low",
            "cost": span.cost,
            "identity": identity,
            "message": message,
            "model": span.model,
            "operation": span.name,
            "rule_id": "TRACE002",
        }
        if max_cost is not None and "max-cost" in signals:
            finding["max_cost"] = max_cost
        if baseline is not None and "baseline-outlier" in signals:
            finding["baseline_median"] = baseline
            finding["cost_multiplier"] = cost_multiplier
        if span.span_id is not None:
            finding["span_id"] = span.span_id
        if span.trace_id is not None:
            finding["trace_id"] = span.trace_id
        findings.append(finding)
    return _deduplicate_findings(findings)


def _deduplicate_findings(findings: Sequence[JsonObject]) -> list[JsonObject]:
    unique: dict[str, JsonObject] = {}
    for finding in findings:
        identity = str(finding["identity"])
        unique.setdefault(identity, finding)
    return list(unique.values())
