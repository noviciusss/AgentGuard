"""Tests for the formatting-preserving autofix foundation."""

from pathlib import Path

import libcst as cst
import pytest

from agentguard.findings import Confidence, Finding, Location, Severity
from agentguard.fixes import FixEngine, FixError
from agentguard.fixes.ag003_timeout import preview_timeout_fixes
from agentguard.fixes.ag004_recursion_limit import preview_recursion_limit_fixes
from agentguard.fixes.ag010_model_pin import preview_model_pin_fixes


def add_timeout(module: cst.Module) -> cst.Module:
    class AddTimeout(cst.CSTTransformer):
        def leave_Call(
            self, original_node: cst.Call, updated_node: cst.Call
        ) -> cst.Call:
            if not isinstance(updated_node.func, cst.Attribute):
                return updated_node
            if updated_node.func.attr.value != "get":
                return updated_node
            return updated_node.with_changes(
                args=[
                    *updated_node.args,
                    cst.Arg(cst.Integer("30"), keyword=cst.Name("timeout")),
                ]
            )

    transformed = module.visit(AddTimeout())
    assert isinstance(transformed, cst.Module)
    return transformed


def test_fix_engine_preserves_formatting_and_produces_unified_diff() -> None:
    source = "import requests\n\nresult = requests.get(url)  # keep this comment\n"
    result = FixEngine().preview(Path("agent.py"), source, add_timeout)

    assert result.changed is True
    assert "# keep this comment" in result.after
    assert "+result = requests.get(url, timeout = 30)" in result.diff
    assert "--- agent.py\n+++ agent.py\n" in result.diff


def test_fix_engine_is_preview_only_until_apply(tmp_path: Path) -> None:
    path = tmp_path / "agent.py"
    source = "result = requests.get(url)\n"
    path.write_text(source, encoding="utf-8")

    result = FixEngine().preview(path, source, add_timeout)

    assert path.read_text(encoding="utf-8") == source
    FixEngine().apply(result)
    assert "timeout" in path.read_text(encoding="utf-8")


def test_fix_engine_rejects_invalid_source() -> None:
    with pytest.raises(FixError, match="cannot parse source"):
        FixEngine().preview(Path("broken.py"), "def broken(:\n", add_timeout)


def test_fix_engine_reports_noop_without_a_diff() -> None:
    source = "value = 1\n"
    result = FixEngine().preview(Path("agent.py"), source, lambda module: module)

    assert result.changed is False
    assert result.diff == ""


def test_ag003_timeout_fix_targets_the_finding_location(tmp_path: Path) -> None:
    path = tmp_path / "agent.py"
    source = "import requests\nrequests.get(url)\n"
    finding = Finding(
        rule_id="AG003",
        severity=Severity.WARNING,
        confidence=Confidence.HIGH,
        message="requests.get has no timeout",
        why="connection can hang",
        suggestion="add timeout",
        loc=Location(path, 2, 0, 2, 17),
    )

    result = preview_timeout_fixes(path, source, [finding], 12)

    assert result is not None
    assert "timeout = 12" in result.after
    assert "requests.get" in result.diff


def test_ag004_recursion_limit_fix_targets_graph_compile(tmp_path: Path) -> None:
    path = tmp_path / "graph.py"
    source = """from langgraph.graph import StateGraph

builder = StateGraph(dict)
graph = builder.compile()
graph.invoke({})
"""
    finding = Finding(
        rule_id="AG004",
        severity=Severity.ERROR,
        confidence=Confidence.HIGH,
        message="graph cycle",
        why="cycle",
        suggestion="bound it",
        loc=Location(path, 3, 0, 3, 25),
    )

    result = preview_recursion_limit_fixes(path, source, [finding], 25)

    assert result is not None
    assert '"recursion_limit": 25' in result.after


def test_ag010_model_pin_fix_only_replaces_configured_literals(tmp_path: Path) -> None:
    path = tmp_path / "agent.py"
    source = 'client.responses.create(model="gpt-4", input="hello")\n'
    finding = Finding(
        rule_id="AG010",
        severity=Severity.WARNING,
        confidence=Confidence.HIGH,
        message="model is not pinned",
        why="alias changes",
        suggestion="pin it",
        loc=Location(path, 1, 0, 1, 57),
    )

    result = preview_model_pin_fixes(
        path, source, [finding], {"gpt-4": "gpt-4-2024-08-06"}
    )

    assert result is not None
    assert "gpt-4-2024-08-06" in result.after


def test_ag010_model_pin_skips_dynamic_values(tmp_path: Path) -> None:
    path = tmp_path / "agent.py"
    source = 'client.responses.create(model=load_model(), input="hello")\n'
    finding = Finding(
        rule_id="AG010",
        severity=Severity.WARNING,
        confidence=Confidence.HIGH,
        message="model is not pinned",
        why="alias changes",
        suggestion="pin it",
        loc=Location(path, 1, 0, 1, 64),
    )

    result = preview_model_pin_fixes(
        path, source, [finding], {"gpt-4": "gpt-4-2024-08-06"}
    )

    assert result is not None
    assert result.changed is False
