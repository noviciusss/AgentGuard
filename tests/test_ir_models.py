"""Unit tests for normalized Agent IR dataclasses."""

from pathlib import Path

from agentguard.findings import Location
from agentguard.ir.models import (
    AgentGraph,
    AgentNode,
    AgentSystem,
    CallSite,
    Capability,
    DataSource,
    Edge,
    FanOut,
    KwargInfo,
    Loop,
    ModuleFacts,
    StateKey,
    ToolDef,
)


def test_ir_models_preserve_graph_relationships() -> None:
    loc = Location(Path("agent.py"), 1, 0, 1, 10)
    call = CallSite(
        loc=loc,
        kind="llm",
        qualified_name="client.invoke",
        kwargs={"temperature": KwargInfo(0.0, True)},
        has_timeout=False,
        enclosing_function="node",
        in_loop=True,
    )
    loop = Loop(
        loc=loc,
        kind="while",
        has_bound=False,
        bound_value=None,
        bounded_by=None,
        has_backoff=False,
        calls_inside=[call],
        catches_exceptions=True,
    )
    tool = ToolDef(
        name="search",
        loc=loc,
        capabilities={Capability.NETWORK},
        requires_approval=False,
        is_idempotent=True,
    )
    node = AgentNode(
        name="answer",
        framework="generic",
        loc=loc,
        function_ref="answer",
        reads_state={"question"},
        writes_state={"response"},
        call_sites=[call],
        tools=[tool],
    )
    edge = Edge(source="start", target="answer", conditional=False, loc=loc)
    fan_out = FanOut(
        source="start",
        branches=["search", "answer"],
        loc=loc,
        mechanism="multiple_edges",
    )
    graph = AgentGraph(
        name="support",
        framework="generic",
        nodes={"answer": node},
        edges=[edge],
        entry="start",
        terminals={"answer"},
        state_keys={"response": StateKey("response", False, False)},
        recursion_limit=None,
        fan_outs=[fan_out],
        loc=loc,
    )
    module = ModuleFacts(
        path=Path("agent.py"),
        call_sites=[call],
        loops=[loop],
        graphs=[graph],
        module_mutables={},
        imports={"r": "requests"},
    )
    system = AgentSystem(modules=[module])

    assert system.modules[0].graphs[0].nodes["answer"].tools[0] == tool
    assert system.modules[0].loops[0].calls_inside[0].qualified_name == "client.invoke"


def test_ir_enum_values_are_stable_strings() -> None:
    assert Capability.FS_WRITE.value == "fs_write"
    assert DataSource.USER_INPUT.value == "user_input"
