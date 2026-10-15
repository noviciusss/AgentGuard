"""Opt-in, provider-neutral finding triage for AgentGuard.

The plugin deliberately keeps provider loading behind the ``triage`` command.
Importing this module, or running ``agentguard scan``, never imports an LLM
provider.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import tempfile
import tokenize
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, NoReturn, Protocol, cast

import typer

from agentguard.plugins import hookimpl

MAX_SNIPPET_LINES = 21
MAX_SNIPPET_CHARS = 4096
MAX_TEXT_LENGTH = 16_384
_CACHE_VERSION = 1
_SNIPPET_NOTICE = (
    "[AgentGuard: redacted source snippet; string literals and comments are "
    "replaced. Identifiers and code structure may remain. The snippet is "
    f"limited to {MAX_SNIPPET_LINES} lines and {MAX_SNIPPET_CHARS} characters.]"
)
_REDACTION_MARKER = "[REDACTED]"
_CLASSIFICATIONS = frozenset({"true_positive", "false_positive", "uncertain"})
_CONFIDENCES = frozenset({"high", "medium", "low"})


@dataclass(frozen=True)
class TriageRequest:
    """Redacted, provider-neutral input for one triage decision.

    ``snippet`` is produced by this package and is bounded before the request
    is passed to a provider. Providers should treat every field as untrusted
    source text.
    """

    rule_id: str
    message: str
    why: str
    suggestion: str
    snippet: str
    fingerprint: str = ""
    severity: str = ""
    confidence: str = ""
    file: str = ""
    line: int = 0
    col: int = 0


@dataclass(frozen=True)
class TriageResult:
    """Validated advisory response; it never changes finding severity."""

    classification: str
    confidence: str
    explanation: str
    fix_suggestion: str

    def __post_init__(self) -> None:
        _validate_result_fields(self)


class TriageProvider(Protocol):
    """Provider contract for an optional local or remote implementation.

    ``evaluate`` is synchronous. The provider owns its HTTP/SDK timeout
    configuration; this CLI does not forcibly terminate a provider call.
    """

    def evaluate(self, request: TriageRequest) -> TriageResult:
        """Return one validated advisory evaluation."""


class Plugin:
    """Register the explicit ``agentguard triage`` command."""

    name = "agentguard-llm-triage"

    @hookimpl
    def register_commands(self, app: typer.Typer) -> None:
        app.command("triage")(triage_command)


@dataclass(frozen=True)
class _PreparedFinding:
    request: TriageRequest
    request_hash: str


@dataclass(frozen=True)
class _FindingInput:
    rule_id: str
    message: str
    why: str
    suggestion: str
    fingerprint: str
    severity: str
    confidence: str
    file: str
    line: int
    col: int


@dataclass(frozen=True)
class _CacheEntry:
    request_hash: str
    result: TriageResult


class _TriageInputError(Exception):
    """An input, source, or cache validation failure."""


class _TriageProviderError(Exception):
    """A provider import, construction, invocation, or result failure."""


def triage_command(
    input_path: Annotated[Path, typer.Option("--input", help="JSON findings file.")],
    provider: Annotated[
        str, typer.Option("--provider", help="module:factory provider path.")
    ],
    source_root: Annotated[
        Path,
        typer.Option(
            "--source-root",
            help="Explicit root containing finding source files.",
        ),
    ],
    cache: Annotated[
        Path | None, typer.Option("--cache", help="Optional private JSON result cache.")
    ] = None,
    cache_namespace: Annotated[
        str | None,
        typer.Option(
            "--cache-namespace",
            help="Namespace for intentionally invalidating a cache.",
        ),
    ] = None,
) -> None:
    """Run opt-in advisory triage through a user-supplied provider.

    All findings, source files, and caches are validated before the provider
    module is imported. Invalid input exits with code 2; provider failures exit
    with code 3 and do not include provider exception text.
    """
    try:
        provider_path = _validate_provider_path(provider)
        prepared = _prepare_findings(input_path, source_root)
        namespace = _make_namespace(provider_path, cache_namespace)
        cached = _load_cache(cache, namespace)
    except _TriageInputError:
        _exit_invalid_input()

    try:
        factory = _load_provider(provider_path)
        evaluator = _load_evaluator(factory)
        results, changed = _evaluate_findings(prepared, cached, evaluator, namespace)
    except _TriageProviderError:
        _exit_provider_error()

    if cache is not None and changed:
        try:
            _write_cache(cache, namespace, cached)
        except _TriageInputError:
            _exit_invalid_input()

    typer.echo(json.dumps(results, indent=2, sort_keys=True))


def _prepare_findings(input_path: Path, source_root: Path) -> list[_PreparedFinding]:
    payload = _read_json_file(input_path)
    if not isinstance(payload, list):
        raise _TriageInputError("findings must be a JSON array")
    root = _resolve_source_root(source_root)
    prepared: list[_PreparedFinding] = []
    for index, item in enumerate(payload):
        finding = _parse_finding(item, index)
        snippet = _source_snippet(root, finding.file, finding.line)
        request = TriageRequest(
            rule_id=finding.rule_id,
            message=finding.message,
            why=finding.why,
            suggestion=finding.suggestion,
            snippet=snippet,
            fingerprint=finding.fingerprint,
            severity=finding.severity,
            confidence=finding.confidence,
            file=finding.file,
            line=finding.line,
            col=finding.col,
        )
        prepared.append(_PreparedFinding(request, _request_hash(request)))
    return prepared


def _parse_finding(item: object, index: int) -> _FindingInput:
    if not isinstance(item, dict):
        raise _TriageInputError(f"finding {index + 1} is not an object")
    location = item.get("location")
    if not isinstance(location, dict):
        raise _TriageInputError(f"finding {index + 1} has no valid location")
    file_value = _required_text(location.get("file"), index, "location")
    if "\x00" in file_value:
        raise _TriageInputError(f"finding {index + 1} has an invalid path")
    line = _positive_int(location.get("line"), index, "line")
    col = _nonnegative_int(location.get("col", 0), index, "column")
    return _FindingInput(
        rule_id=_required_text(item.get("rule_id"), index, "rule_id"),
        message=_text(item.get("message", ""), index, "message"),
        why=_text(item.get("why", ""), index, "why"),
        suggestion=_text(item.get("suggestion", ""), index, "suggestion"),
        fingerprint=_text(item.get("fingerprint", ""), index, "fingerprint"),
        severity=_text(item.get("severity", ""), index, "severity"),
        confidence=_text(item.get("confidence", ""), index, "confidence"),
        file=file_value,
        line=line,
        col=col,
    )


def _required_text(value: object, index: int, field: str) -> str:
    result = _text(value, index, field)
    if not result:
        raise _TriageInputError(f"finding {index + 1} has an empty {field}")
    return result


def _text(value: object, index: int, field: str) -> str:
    if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
        raise _TriageInputError(f"finding {index + 1} has invalid {field}")
    return value


def _positive_int(value: object, index: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _TriageInputError(f"finding {index + 1} has invalid {field}")
    return value


def _nonnegative_int(value: object, index: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _TriageInputError(f"finding {index + 1} has invalid {field}")
    return value


def _resolve_source_root(path: Path) -> Path:
    try:
        root = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _TriageInputError("source root is unavailable") from None
    if not root.is_dir():
        raise _TriageInputError("source root is not a directory")
    return root


def _source_snippet(root: Path, relative_name: str, line: int) -> str:
    relative = Path(relative_name)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise _TriageInputError("finding source path must stay below source root")
    candidate = root.joinpath(relative)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise _TriageInputError("finding source file is unavailable") from None
    if not _is_under(resolved, root) or not resolved.is_file():
        raise _TriageInputError("finding source path escapes source root")
    try:
        with tokenize.open(resolved) as stream:
            source = stream.read()
    except (OSError, SyntaxError, UnicodeError):
        raise _TriageInputError("finding source file cannot be read safely") from None
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (IndentationError, SyntaxError, tokenize.TokenError):
        raise _TriageInputError("finding source cannot be redacted safely") from None
    redacted = _redact_lines(source.splitlines(keepends=True), tokens)
    if line > len(redacted):
        raise _TriageInputError("finding line is outside source file")
    start = max(1, line - (MAX_SNIPPET_LINES // 2))
    end = min(len(redacted), start + MAX_SNIPPET_LINES - 1)
    source_part = "".join(redacted[start - 1 : end])
    available = max(0, MAX_SNIPPET_CHARS - len(_SNIPPET_NOTICE) - 64)
    truncated = len(source_part) > available
    if truncated:
        source_part = source_part[:available]
    limit_note = "truncated" if truncated else "complete within the line bound"
    return (
        f"{_SNIPPET_NOTICE}\n"
        f"[AgentGuard: source lines {start}-{end}; {limit_note}.]\n"
        f"{source_part}"
    )


def _redact_lines(lines: list[str], tokens: list[tokenize.TokenInfo]) -> list[str]:
    result = list(lines)
    redactable = [
        token for token in tokens if token.type in {tokenize.STRING, tokenize.COMMENT}
    ]
    for token in sorted(redactable, key=lambda item: item.start, reverse=True):
        _replace_token(result, token)
    return result


def _replace_token(lines: list[str], token: tokenize.TokenInfo) -> None:
    start_line, start_col = token.start
    end_line, end_col = token.end
    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        raise _TriageInputError("finding source cannot be redacted safely")
    if start_line == end_line:
        body, ending = _split_ending(lines[start_line - 1])
        if end_col > len(body):
            raise _TriageInputError("finding source cannot be redacted safely")
        lines[start_line - 1] = (
            body[:start_col] + _REDACTION_MARKER + body[end_col:] + ending
        )
        return

    first_body, first_ending = _split_ending(lines[start_line - 1])
    last_body, last_ending = _split_ending(lines[end_line - 1])
    if start_col > len(first_body) or end_col > len(last_body):
        raise _TriageInputError("finding source cannot be redacted safely")
    lines[start_line - 1] = first_body[:start_col] + _REDACTION_MARKER + first_ending
    for line_number in range(start_line, end_line - 1):
        _, ending = _split_ending(lines[line_number])
        lines[line_number] = _REDACTION_MARKER + ending
    lines[end_line - 1] = _REDACTION_MARKER + last_body[end_col:] + last_ending


def _split_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith(("\n", "\r")):
        return line[:-1], line[-1:]
    return line, ""


def _request_hash(request: TriageRequest) -> str:
    document = {
        "col": request.col,
        "confidence": request.confidence,
        "file": request.file,
        "fingerprint": request.fingerprint,
        "line": request.line,
        "message": request.message,
        "rule_id": request.rule_id,
        "severity": request.severity,
        "snippet": request.snippet,
        "suggestion": request.suggestion,
        "why": request.why,
    }
    encoded = json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _make_namespace(provider: str, requested: str | None) -> dict[str, str]:
    value = requested if requested is not None else "default"
    if not value or len(value) > 256:
        raise _TriageInputError("cache namespace is invalid")
    return {"provider": provider, "cache_namespace": value}


def _namespace_key(namespace: Mapping[str, str], request_hash: str) -> str:
    document = {"namespace": dict(namespace), "request_hash": request_hash}
    encoded = json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_cache(
    path: Path | None, namespace: Mapping[str, str]
) -> dict[str, _CacheEntry]:
    if path is None:
        return {}
    parent = path.parent
    if not parent.is_dir():
        raise _TriageInputError("cache parent directory is unavailable")
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise _TriageInputError("cache is not valid JSON") from None
    if not isinstance(payload, dict):
        raise _TriageInputError("cache has an invalid shape")
    if payload.get("version") != _CACHE_VERSION:
        raise _TriageInputError("cache version is unsupported")
    stored_namespace = payload.get("namespace")
    if not _valid_namespace(stored_namespace):
        raise _TriageInputError("cache namespace is invalid")
    normalized_namespace = cast(Mapping[str, str], stored_namespace)
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, dict):
        raise _TriageInputError("cache entries are invalid")
    validated: dict[str, _CacheEntry] = {}
    for key, raw_entry in raw_entries.items():
        entry = _parse_cache_entry(key, raw_entry, normalized_namespace)
        validated[key] = entry
    if dict(normalized_namespace) != dict(namespace):
        return {}
    return validated


def _valid_namespace(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"provider", "cache_namespace"}
        and all(isinstance(item, str) and bool(item) for item in value.values())
        and len(cast(str, value["provider"])) <= MAX_TEXT_LENGTH
        and len(cast(str, value["cache_namespace"])) <= 256
    )


def _parse_cache_entry(
    key: object, raw_entry: object, namespace: Mapping[str, str]
) -> _CacheEntry:
    if not isinstance(key, str) or len(key) != 64:
        raise _TriageInputError("cache entry key is invalid")
    if not isinstance(raw_entry, dict):
        raise _TriageInputError("cache entry is invalid")
    request_hash = raw_entry.get("request_hash")
    if not isinstance(request_hash, str) or len(request_hash) != 64:
        raise _TriageInputError("cache request hash is invalid")
    if _namespace_key(namespace, request_hash) != key:
        raise _TriageInputError("cache request hash does not match its key")
    raw_result = raw_entry.get("result")
    if not isinstance(raw_result, dict):
        raise _TriageInputError("cache result is invalid")
    return _CacheEntry(request_hash, _result_from_mapping(raw_result))


def _result_from_mapping(value: Mapping[str, object]) -> TriageResult:
    fields = ("classification", "confidence", "explanation", "fix_suggestion")
    if any(field not in value for field in fields):
        raise _TriageInputError("triage result is incomplete")
    raw = {field: value[field] for field in fields}
    if not all(isinstance(item, str) for item in raw.values()):
        raise _TriageInputError("triage result has invalid fields")
    try:
        return TriageResult(
            classification=cast(str, raw["classification"]),
            confidence=cast(str, raw["confidence"]),
            explanation=cast(str, raw["explanation"]),
            fix_suggestion=cast(str, raw["fix_suggestion"]),
        )
    except ValueError:
        raise _TriageInputError("triage result has invalid values") from None


def _write_cache(
    path: Path, namespace: Mapping[str, str], entries: Mapping[str, _CacheEntry]
) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise _TriageInputError("cache parent directory is unavailable")
    payload = {
        "entries": {
            key: {
                "request_hash": entry.request_hash,
                "result": _result_document(entry.result),
            }
            for key, entry in sorted(entries.items())
        },
        "namespace": dict(namespace),
        "version": _CACHE_VERSION,
    }
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=parent
        )
        temporary = Path(temporary_name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise _TriageInputError("cache could not be written safely") from None
    finally:
        if temporary is not None:
            with suppress(FileNotFoundError):
                temporary.unlink()


def _result_document(result: TriageResult) -> dict[str, str]:
    return {
        "classification": result.classification,
        "confidence": result.confidence,
        "explanation": result.explanation,
        "fix_suggestion": result.fix_suggestion,
    }


def _evaluate_findings(
    prepared: list[_PreparedFinding],
    cached: dict[str, _CacheEntry],
    evaluator: Callable[[TriageRequest], object],
    namespace: Mapping[str, str],
) -> tuple[list[dict[str, str]], bool]:
    results: list[dict[str, str]] = []
    changed = False
    for item in prepared:
        cache_key = _namespace_key(namespace, item.request_hash)
        cached_item = cached.get(cache_key)
        if cached_item is not None and cached_item.request_hash == item.request_hash:
            result = cached_item.result
        else:
            try:
                result = _validate_provider_result(evaluator(item.request))
            except _TriageProviderError:
                raise
            except Exception:
                raise _TriageProviderError from None
            cached[cache_key] = _CacheEntry(item.request_hash, result)
            changed = True
        results.append(
            {
                "classification": result.classification,
                "confidence": result.confidence,
                "explanation": result.explanation,
                "fingerprint": item.request.fingerprint,
                "fix_suggestion": result.fix_suggestion,
                "request_hash": item.request_hash,
            }
        )
    return results, changed


def _validate_provider_result(value: object) -> TriageResult:
    if not isinstance(value, TriageResult):
        raise _TriageProviderError
    try:
        _validate_result_fields(value)
    except ValueError:
        raise _TriageProviderError from None
    return value


def _validate_result_fields(result: TriageResult) -> None:
    if result.classification not in _CLASSIFICATIONS:
        raise ValueError("unsupported classification")
    if result.confidence not in _CONFIDENCES:
        raise ValueError("unsupported confidence")
    if not isinstance(result.explanation, str) or not result.explanation:
        raise ValueError("explanation must be non-empty")
    if not isinstance(result.fix_suggestion, str) or not result.fix_suggestion:
        raise ValueError("fix suggestion must be non-empty")
    if len(result.explanation) > MAX_TEXT_LENGTH:
        raise ValueError("explanation is too long")
    if len(result.fix_suggestion) > MAX_TEXT_LENGTH:
        raise ValueError("fix suggestion is too long")


def _validate_provider_path(path: str) -> str:
    module_name, separator, attribute = path.partition(":")
    if (
        not separator
        or not module_name
        or not attribute
        or ":" in attribute
        or path != path.strip()
    ):
        raise _TriageInputError("provider must use module:factory syntax")
    return path


def _load_provider(path: str) -> Callable[[], object]:
    module_name, _, attribute = path.partition(":")
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute)
    except Exception:
        raise _TriageProviderError from None
    if not callable(factory):
        raise _TriageProviderError
    return cast(Callable[[], object], factory)


def _provider_evaluator(instance: object) -> Callable[[TriageRequest], object]:
    evaluator = getattr(instance, "evaluate", None)
    if not callable(evaluator):
        raise _TriageProviderError
    return cast(Callable[[TriageRequest], object], evaluator)


def _load_evaluator(factory: Callable[[], object]) -> Callable[[TriageRequest], object]:
    try:
        instance = factory()
        return _provider_evaluator(instance)
    except _TriageProviderError:
        raise
    except Exception:
        raise _TriageProviderError from None


def _read_json_file(path: Path) -> object:
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise _TriageInputError("input is not readable valid JSON") from None


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _exit_invalid_input() -> NoReturn:
    typer.echo("invalid triage input", err=True)
    raise typer.Exit(code=2)


def _exit_provider_error() -> NoReturn:
    typer.echo("triage provider failed", err=True)
    raise typer.Exit(code=3)
