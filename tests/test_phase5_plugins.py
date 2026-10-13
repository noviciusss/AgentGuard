"""Behavior tests for graph, trace, and inter-procedural Phase 5 pieces."""

import json
from pathlib import Path

from agentguard.engine.parser import parse_source
from agentguard.ir.taint import analyze_taint
from agentguard_trace import load_spans


def test_trace_loader_accepts_otel_like_span_exports(tmp_path: Path) -> None:
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps({"spans": [{"name": "node", "duration": 12, "status": "error"}]}),
        encoding="utf-8",
    )

    spans = load_spans(path)

    assert spans[0].name == "node"
    assert spans[0].duration_ms == 12


def test_interprocedural_taint_exposes_call_graph_and_return_flow() -> None:
    source = """
def ask():
    return input("prompt")

def wrapper():
    return ask()

value = wrapper()
eval(value)
"""
    facts = analyze_taint(parse_source(source, Path("agent.py")).tree, Path("agent.py"))

    assert facts.call_graph["wrapper"] == ("ask",)
    assert any(flow.sink.value == "eval" for flow in facts.flows)
