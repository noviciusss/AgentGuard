"""Tests for the opt-in provider-neutral LLM triage plugin."""

from __future__ import annotations

import json
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

from agentguard.cli import app
from agentguard_llm_triage import TriageRequest, TriageResult

runner = CliRunner()


class RecordingProvider:
    """Local fake provider used without network access."""

    def __init__(self) -> None:
        self.requests: list[TriageRequest] = []

    def evaluate(self, request: TriageRequest) -> TriageResult:
        self.requests.append(request)
        return TriageResult(
            classification="true_positive",
            confidence="high",
            explanation="The bounded fake-provider explanation.",
            fix_suggestion="Add an explicit bound in the agent code.",
        )


def _install_provider(
    monkeypatch: pytest.MonkeyPatch, name: str, factory: Callable[[], object]
) -> str:
    module = ModuleType(name)
    module.__dict__["make_provider"] = factory
    monkeypatch.setitem(sys.modules, name, module)
    return f"{name}:make_provider"


def _write_source(root: Path) -> None:
    (root / "agent.py").write_text(
        'secret = "literal-secret-123"\n# comment-secret-456\nvalue = 1\n',
        encoding="utf-8",
    )


def _write_findings(path: Path, *, count: int = 1) -> None:
    findings = [
        {
            "confidence": "high",
            "fingerprint": "" if count > 1 else "abc123",
            "location": {
                "col": 0,
                "end_col": 6,
                "end_line": 1,
                "file": "agent.py",
                "line": 1,
            },
            "message": f"Finding {index}",
            "rule_id": "AG003",
            "severity": "warning",
            "suggestion": "Configure a timeout.",
            "why": "A provider call can hang.",
        }
        for index in range(count)
    ]
    path.write_text(json.dumps(findings), encoding="utf-8")


def _command(
    input_path: Path,
    source_root: Path,
    provider: str,
    cache: Path | None = None,
    namespace: str | None = None,
) -> list[str]:
    arguments = [
        "triage",
        "--input",
        str(input_path),
        "--source-root",
        str(source_root),
        "--provider",
        provider,
    ]
    if cache is not None:
        arguments.extend(["--cache", str(cache)])
    if namespace is not None:
        arguments.extend(["--cache-namespace", namespace])
    return arguments


def test_triage_sends_bounded_redacted_snippet_and_writes_private_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source(tmp_path)
    findings = tmp_path / "findings.json"
    cache = tmp_path / "triage-cache.json"
    _write_findings(findings)
    provider = RecordingProvider()
    provider_path = _install_provider(
        monkeypatch, "fake_triage_success", lambda: provider
    )

    result = runner.invoke(
        app, _command(findings, tmp_path, provider_path, cache=cache)
    )

    assert result.exit_code == 0, result.stderr
    rendered = json.loads(result.stdout)
    assert rendered[0]["fix_suggestion"] == "Add an explicit bound in the agent code."
    assert rendered[0]["request_hash"]
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert "literal-secret-123" not in request.snippet
    assert "comment-secret-456" not in request.snippet
    assert "[REDACTED]" in request.snippet
    assert "redacted source snippet" in request.snippet
    assert "literal-secret-123" not in cache.read_text(encoding="utf-8")
    assert stat.S_IMODE(cache.stat().st_mode) == 0o600


def test_cache_uses_request_hash_and_namespace_not_only_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source(tmp_path)
    findings = tmp_path / "findings.json"
    cache = tmp_path / "triage-cache.json"
    _write_findings(findings, count=2)
    first = RecordingProvider()
    provider_path = _install_provider(monkeypatch, "fake_triage_cache", lambda: first)

    first_result = runner.invoke(
        app, _command(findings, tmp_path, provider_path, cache=cache)
    )
    assert first_result.exit_code == 0, first_result.stderr
    assert len(first.requests) == 2
    cache_payload = json.loads(cache.read_text(encoding="utf-8"))
    assert len(cache_payload["entries"]) == 2

    second = RecordingProvider()
    sys.modules["fake_triage_cache"].__dict__["make_provider"] = lambda: second
    second_result = runner.invoke(
        app, _command(findings, tmp_path, provider_path, cache=cache)
    )
    assert second_result.exit_code == 0, second_result.stderr
    assert second.requests == []

    third = RecordingProvider()
    sys.modules["fake_triage_cache"].__dict__["make_provider"] = lambda: third
    namespace_result = runner.invoke(
        app,
        _command(
            findings,
            tmp_path,
            provider_path,
            cache=cache,
            namespace="new-provider-contract",
        ),
    )
    assert namespace_result.exit_code == 0, namespace_result.stderr
    assert len(third.requests) == 2


def test_invalid_input_is_reported_before_provider_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source(tmp_path)
    findings = tmp_path / "findings.json"
    findings.write_text(
        '{"not": "an array", "secret": "do-not-print"}', encoding="utf-8"
    )

    result = runner.invoke(
        app,
        _command(
            findings,
            tmp_path,
            "module_that_must_not_be_imported:make_provider",
        ),
    )

    assert result.exit_code == 2
    assert "invalid triage input" in result.stderr
    assert "module_that_must_not_be_imported" not in result.stderr
    assert "do-not-print" not in result.stderr


def test_traversal_and_symlink_escape_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source(tmp_path)
    outside = tmp_path.parent / "outside-agentguard-source.py"
    outside.write_text('secret = "outside-secret"\n', encoding="utf-8")
    findings = tmp_path / "findings.json"
    provider = RecordingProvider()
    provider_path = _install_provider(
        monkeypatch, "fake_triage_paths", lambda: provider
    )

    findings.write_text(
        json.dumps(
            [
                {
                    "location": {"file": "../outside-agentguard-source.py", "line": 1},
                    "message": "bad",
                    "rule_id": "AG003",
                    "suggestion": "fix",
                    "why": "why",
                }
            ]
        ),
        encoding="utf-8",
    )
    traversal = runner.invoke(app, _command(findings, tmp_path, provider_path))
    assert traversal.exit_code == 2
    assert provider.requests == []

    link = tmp_path / "link.py"
    link.symlink_to(outside)
    findings.write_text(
        json.dumps(
            [
                {
                    "location": {"file": "link.py", "line": 1},
                    "message": "bad",
                    "rule_id": "AG003",
                    "suggestion": "fix",
                    "why": "why",
                }
            ]
        ),
        encoding="utf-8",
    )
    symlink = runner.invoke(app, _command(findings, tmp_path, provider_path))
    assert symlink.exit_code == 2
    assert provider.requests == []


def test_provider_errors_are_controlled_and_do_not_write_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source(tmp_path)
    findings = tmp_path / "findings.json"
    cache = tmp_path / "triage-cache.json"
    _write_findings(findings)

    class FailingProvider:
        def evaluate(self, request: TriageRequest) -> TriageResult:
            raise RuntimeError("secret-provider-token")

    provider_path = _install_provider(
        monkeypatch, "fake_triage_failure", FailingProvider
    )
    result = runner.invoke(
        app, _command(findings, tmp_path, provider_path, cache=cache)
    )

    assert result.exit_code == 3
    assert "triage provider failed" in result.stderr
    assert "secret-provider-token" not in result.stderr
    assert not cache.exists()


def test_malformed_provider_result_is_a_provider_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source(tmp_path)
    findings = tmp_path / "findings.json"
    _write_findings(findings)

    class MalformedProvider:
        def evaluate(self, request: TriageRequest) -> object:
            return {"classification": "true_positive"}

    provider_path = _install_provider(
        monkeypatch, "fake_triage_malformed", MalformedProvider
    )
    result = runner.invoke(app, _command(findings, tmp_path, provider_path))

    assert result.exit_code == 3
    assert "triage provider failed" in result.stderr


def test_invalid_cache_is_input_error_before_provider_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_source(tmp_path)
    findings = tmp_path / "findings.json"
    _write_findings(findings)
    cache = tmp_path / "triage-cache.json"
    cache.write_text(json.dumps({"version": 1, "entries": []}), encoding="utf-8")

    result = runner.invoke(
        app,
        _command(
            findings,
            tmp_path,
            "module_that_must_not_be_imported_cache:make_provider",
            cache=cache,
        ),
    )

    assert result.exit_code == 2
    assert "invalid triage input" in result.stderr
