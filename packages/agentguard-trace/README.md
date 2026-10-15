# agentguard-trace

Offline JSON trace ingestion plugin for local LangSmith and OpenTelemetry
exports. It performs no network calls and does not estimate model prices.

## Usage

```console
agentguard trace trace.json
agentguard trace trace.json --min-occurrences 4 --max-cost 0.25
agentguard trace trace.json --cost-multiplier 3 --min-cost-samples 5 \
  --output findings.json
```

When `--output` is provided, the exact same deterministic JSON is written to
that file and stdout. Invalid JSON, empty exports, malformed spans, and invalid
finite/nonnegative numeric options are reported as CLI usage errors (exit 2).

## Accepted exports

The loader accepts:

* a flat list of span objects;
* `{ "spans": [...] }` flat exports;
* `{ "runs": [...] }` or a list of LangSmith runs, including nested
  `child_runs`;
* OTLP JSON `{ "resourceSpans": [{ "resource": ..., "scopeSpans": [{
  "spans": [...] }] }] }`.

Spans are normalized to names, trace/span/parent IDs, Unix-nanosecond start and
end timestamps, duration in milliseconds, typed attributes, status, explicit
model, and explicit cost. OTLP attribute wrappers such as `stringValue`,
`intValue`, `doubleValue`, arrays, and key-value lists are unwrapped.

`TRACE001` counts a repeated operation within one trace ID. It does not combine
same-named spans from independent traces. Repetition is skipped when a trace ID
is absent. Cost findings (`TRACE002`) use only an explicitly reported cost (or
explicit prompt and completion cost components), never token counts or a built-
in price table. `--max-cost` is an absolute threshold; the optional comparable
operation/model baseline uses the median of at least `--min-cost-samples` peer
spans and `--cost-multiplier`.

For format reference, see the [OTLP JSON encoding specification](https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding)
and [LangSmith trace documentation](https://docs.langchain.com/oss/python/langchain/observability).
