"""Regression tests for same-file inter-procedural return summaries."""

from pathlib import Path

from agentguard.engine.parser import parse_source
from agentguard.ir.models import DataSource, TaintSink
from agentguard.ir.taint import TaintFacts, analyze_taint


def _analyze(source: str) -> TaintFacts:
    module = parse_source(source, Path("agent.py"))
    return analyze_taint(module.tree, Path("agent.py"))


def test_return_sources_propagate_across_definition_order_and_multiple_hops() -> None:
    facts = _analyze(
        """
def outer():
    return middle()

def middle():
    return inner()

def inner():
    return input("prompt")

eval(outer())
"""
    )

    assert any(
        flow.source == DataSource.USER_INPUT and flow.sink == TaintSink.EVAL
        for flow in facts.flows
    )
    assert facts.call_graph["outer"] == ("middle",)
    assert facts.call_graph["middle"] == ("inner",)


def test_recursive_return_summary_terminates_and_keeps_recursive_call() -> None:
    facts = _analyze(
        """
def recursive():
    return recursive()
"""
    )

    assert facts.call_graph["recursive"] == ("recursive",)
    assert facts.flows == []


def test_clean_return_chain_does_not_become_tainted() -> None:
    facts = _analyze(
        """
def clean_outer():
    return clean_inner()

def clean_inner():
    return "constant"

eval(clean_outer())
"""
    )

    assert facts.flows == []
