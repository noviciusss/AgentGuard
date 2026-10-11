"""Tests for LangGraph AST-to-IR extraction without importing LangGraph."""

from pathlib import Path

from agentguard.adapters.langgraph import LangGraphAdapter
from agentguard.engine.parser import parse_source
from agentguard.ir.builder import IRBuilder


def test_langgraph_adapter_extracts_nodes_edges_state_reducers_and_send() -> None:
    source = """
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
import operator

class State(TypedDict):
    items: Annotated[list[str], operator.add]
    status: str

def start(state: State):
    return {"status": "running"}

def worker(state: State):
    return {"items": [state["status"]]}

def route(state: State):
    return [Send("worker", {"status": value}) for value in state["items"]]

builder = StateGraph(State)
builder.add_node("start", start)
builder.add_node(worker)
builder.add_edge(START, "start")
builder.add_conditional_edges("start", route, {"go": "worker", "done": END})
graph = builder.compile()
"""
    module = parse_source(source, Path("graph.py"))
    assert LangGraphAdapter().can_handle(module)
    facts = LangGraphAdapter().build(module)
    graph = facts.graphs[0]

    assert graph.framework == "langgraph"
    assert graph.entry == "start"
    assert graph.terminals == {"start"}
    assert graph.nodes["worker"].function_ref == "worker"
    assert graph.nodes["start"].writes_state == {"status"}
    assert graph.state_keys["items"].has_reducer is True
    assert graph.state_keys["items"].mutable_type is True
    assert any(edge.conditional for edge in graph.edges)
    assert any(fanout.mechanism == "send_api" for fanout in graph.fan_outs)


def test_ir_builder_prefers_langgraph_then_falls_back_to_generic() -> None:
    graph_module = parse_source(
        "from langgraph.graph import StateGraph\nb = StateGraph(State)\n",
        Path("graph.py"),
    )
    plain_module = parse_source("requests.get(url)\n", Path("plain.py"))
    builder = IRBuilder([LangGraphAdapter()])

    graph_facts = builder.build_module(graph_module)
    assert graph_facts.graphs[0].framework == "langgraph"
    assert (
        builder.build_system([plain_module]).modules[0].graphs[0].framework == "generic"
    )
