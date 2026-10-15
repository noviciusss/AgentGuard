"""Tests for deterministic normalized-graph Mermaid rendering."""

from pathlib import Path

from agentguard.findings import Location
from agentguard.ir.models import AgentGraph, AgentNode, AgentSystem, Edge, ModuleFacts
from agentguard_graph import _render_system


def _graph() -> AgentGraph:
    location = Location(Path("agent.py"), 1, 0, 1, 1)
    nodes = {
        "start node": AgentNode(
            name="start node",
            framework="test",
            loc=location,
            function_ref=None,
            reads_state=set(),
            writes_state=set(),
            call_sites=[],
            tools=[],
        ),
        "worker": AgentNode(
            name="worker",
            framework="test",
            loc=location,
            function_ref=None,
            reads_state=set(),
            writes_state=set(),
            call_sites=[],
            tools=[],
        ),
    }
    return AgentGraph(
        name="test graph",
        framework="test",
        nodes=nodes,
        edges=[
            Edge("start node", "worker", False, location),
            Edge("worker", None, True, location),
        ],
        entry="start node",
        terminals={"worker"},
        state_keys={},
        recursion_limit=None,
        fan_outs=[],
        loc=location,
    )


def test_renderer_includes_nodes_entry_terminal_and_conditional_edges() -> None:
    rendered = _render_system(AgentSystem([_module(_graph())]))

    assert 'g0_0_n0["start node"]' in rendered
    assert 'g0_0_n1["worker"]' in rendered
    assert 'g0_0_start["START"]' in rendered
    assert 'g0_0_end["END"]' in rendered
    assert "-.-> g0_0_end" in rendered
    assert "-->" in rendered
    assert "test graph" in rendered


def test_renderer_is_deterministic_and_handles_empty_system() -> None:
    graph = _graph()
    first = _render_system(AgentSystem([_module(graph)]))
    second = _render_system(AgentSystem([_module(graph)]))

    assert first == second
    assert _render_system(AgentSystem([])) == 'flowchart TD\n  empty["No graph data"]\n'


def _module(graph: AgentGraph) -> ModuleFacts:
    return ModuleFacts(
        path=Path("agent.py"),
        call_sites=[],
        loops=[],
        graphs=[graph],
        module_mutables={},
        imports={},
    )
