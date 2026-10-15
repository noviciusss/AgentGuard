"""Acceptance coverage for the graph plugin renderer and CLI command."""

from pathlib import Path

from typer.testing import CliRunner

from agentguard.cli import app
from agentguard.findings import Location
from agentguard.ir.models import (
    AgentGraph,
    AgentNode,
    AgentSystem,
    Edge,
    FanOut,
    ModuleFacts,
)
from agentguard_graph import _render_system

runner = CliRunner()


def test_renderer_golden_sorts_modules_and_graphs_and_deduplicates() -> None:
    location = Location(Path("source.py"), 1, 0, 1, 1)
    alpha = _make_graph(
        "alpha",
        ["branch-a", "branch-b", "branch-c", "entry", "isolated"],
        [
            Edge("START", "entry", False, location),
            Edge("__start__", "entry", False, location),
            Edge("entry", "branch-a", True, location),
            Edge("entry", "branch-a", True, location),
            Edge("entry", "branch-b", True, location),
            Edge("branch-a", None, False, location),
            Edge("branch-a", None, False, location),
            Edge("branch-b", None, True, location),
        ],
        entry="entry",
        terminals={"branch-a", "isolated"},
        fan_outs=[
            FanOut(
                "entry",
                ["branch-c", "branch-c"],
                location,
                "send_api",
            )
        ],
    )
    duplicate_name = _make_graph(
        "same",
        ["same"],
        [],
        entry="same",
        terminals={"same"},
    )

    rendered = _render_system(
        AgentSystem(
            [
                _make_module(Path("z/module.py"), [duplicate_name]),
                _make_module(Path("a/module.py"), [duplicate_name, alpha]),
            ]
        )
    )

    expected = (
        "\n".join(
            [
                "flowchart TD",
                "  %% graph: alpha",
                '  g0_0_n0["branch-a"]',
                '  g0_0_n1["branch-b"]',
                '  g0_0_n2["branch-c"]',
                '  g0_0_n3["entry"]',
                '  g0_0_n4["isolated"]',
                '  g0_0_start["START"]',
                '  g0_0_end["END"]',
                '  g0_0_unresolved["unresolved"]',
                "  g0_0_start --> g0_0_n3",
                "  g0_0_n0 --> g0_0_end",
                "  g0_0_n1 -.-> g0_0_unresolved",
                "  g0_0_n3 -.-> g0_0_n0",
                "  g0_0_n3 -.-> g0_0_n1",
                "  g0_0_n3 -.-> g0_0_n2",
                "  g0_0_n4 --> g0_0_end",
                "  %% graph: same",
                '  g0_1_n0["same"]',
                '  g0_1_start["START"]',
                '  g0_1_end["END"]',
                "  g0_1_start --> g0_1_n0",
                "  g0_1_n0 --> g0_1_end",
                "  %% graph: same",
                '  g1_0_n0["same"]',
                '  g1_0_start["START"]',
                '  g1_0_end["END"]',
                "  g1_0_start --> g1_0_n0",
                "  g1_0_n0 --> g1_0_end",
            ]
        )
        + "\n"
    )
    assert rendered == expected


def test_renderer_escapes_mermaid_label_syntax() -> None:
    location = Location(Path("labels.py"), 1, 0, 1, 1)
    graph = _make_graph(
        'graph ] [" <tag> &',
        ['node ] ["\n<tag> &'],
        [],
        entry=None,
        terminals=set(),
    )

    rendered = _render_system(AgentSystem([_make_module(location.file, [graph])]))

    assert 'graph ] [" <tag> &' not in rendered
    assert 'node ] ["\n<tag> &' not in rendered
    assert "node &#93; &#91;&quot;&#10;&lt;tag&gt; &amp;" in rendered


def test_renderer_uses_isolated_terminal_metadata_and_start_aliases() -> None:
    location = Location(Path("isolated.py"), 1, 0, 1, 1)
    graph = _make_graph(
        "isolated",
        ["finish"],
        [
            Edge("START", "finish", False, location),
            Edge("__start__", "finish", False, location),
        ],
        entry="finish",
        terminals={"finish"},
    )

    rendered = _render_system(AgentSystem([_make_module(location.file, [graph])]))

    assert rendered.count('g0_0_start["START"]') == 1
    assert rendered.count('g0_0_end["END"]') == 1
    assert rendered.count("g0_0_start --> g0_0_n0") == 1
    assert rendered.count("g0_0_n0 --> g0_0_end") == 1
    assert "__start__" not in rendered


def test_graph_help_describes_source_and_output_options() -> None:
    result = runner.invoke(app, ["graph", "--help"])

    assert result.exit_code == 0
    assert "Source file or directory" in result.stdout
    assert "--output" in result.stdout


def test_graph_cli_renders_conditional_edges_and_output_path(tmp_path: Path) -> None:
    source = _write_langgraph_source(tmp_path / "agent.py")
    output = tmp_path / "nested" / "agent.mmd"
    output.parent.mkdir()

    result = runner.invoke(app, ["graph", str(source), "--output", str(output)])

    assert result.exit_code == 0
    assert result.stdout == ""
    rendered = output.read_text(encoding="utf-8")
    assert "flowchart TD" in rendered
    assert "-.->" in rendered
    assert rendered.count("g0_0_unresolved") == 0


def test_graph_cli_empty_directory_renders_empty_graph(tmp_path: Path) -> None:
    result = runner.invoke(app, ["graph", str(tmp_path)])

    assert result.exit_code == 0
    assert result.stdout == 'flowchart TD\n  empty["No graph data"]\n'


def test_graph_cli_malformed_source_warns_and_renders_empty_graph(
    tmp_path: Path,
) -> None:
    source = tmp_path / "broken.py"
    source.write_text("def broken(:\n", encoding="utf-8")

    result = runner.invoke(app, ["graph", str(source)])

    assert result.exit_code == 0
    assert result.stdout == 'flowchart TD\n  empty["No graph data"]\n'
    assert "warning: skipped" in result.stderr


def test_graph_cli_missing_file_returns_usage_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["graph", str(tmp_path / "missing.py")])

    assert result.exit_code == 2
    assert "error:" in result.stderr
    assert "missing.py" in result.stderr


def test_graph_cli_invalid_config_returns_usage_error(tmp_path: Path) -> None:
    (tmp_path / "agentguard.toml").write_text("unknown = true\n", encoding="utf-8")
    source = _write_langgraph_source(tmp_path / "agent.py")

    result = runner.invoke(app, ["graph", str(source)])

    assert result.exit_code == 2
    assert "error:" in result.stderr
    assert "unknown" in result.stderr


def test_graph_cli_output_error_returns_usage_error(tmp_path: Path) -> None:
    source = _write_langgraph_source(tmp_path / "agent.py")
    output = tmp_path / "missing" / "agent.mmd"

    result = runner.invoke(app, ["graph", str(source), "--output", str(output)])

    assert result.exit_code == 2
    assert "error:" in result.stderr


def _make_module(path: Path, graphs: list[AgentGraph]) -> ModuleFacts:
    return ModuleFacts(
        path=path,
        call_sites=[],
        loops=[],
        graphs=graphs,
        module_mutables={},
        imports={},
    )


def _make_graph(
    name: str,
    node_names: list[str],
    edges: list[Edge],
    *,
    entry: str | None,
    terminals: set[str],
    fan_outs: list[FanOut] | None = None,
) -> AgentGraph:
    location = edges[0].loc if edges else Location(Path("graph.py"), 1, 0, 1, 1)
    nodes = {
        node_name: AgentNode(
            name=node_name,
            framework="test",
            loc=location,
            function_ref=None,
            reads_state=set(),
            writes_state=set(),
            call_sites=[],
            tools=[],
        )
        for node_name in node_names
    }
    return AgentGraph(
        name=name,
        framework="test",
        nodes=nodes,
        edges=edges,
        entry=entry,
        terminals=terminals,
        state_keys={},
        recursion_limit=None,
        fan_outs=fan_outs or [],
        loc=location,
    )


def _write_langgraph_source(path: Path) -> Path:
    path.write_text(
        """from langgraph.graph import END, START, StateGraph


def route(state):
    return "left"


def left(state):
    return state


def right(state):
    return state


builder = StateGraph(dict)
builder.add_node("route", route)
builder.add_node("left", left)
builder.add_node("right", right)
builder.add_edge(START, "route")
builder.add_edge("route", "left")
builder.add_edge("route", "right")
builder.add_conditional_edges(
    "route", route, {"left": "left", "done": END}
)
builder.add_edge("left", END)
builder.add_edge("right", END)
builder.compile()
""",
        encoding="utf-8",
    )
    return path
