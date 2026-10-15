"""Mermaid graph visualization plugin."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Annotated

import typer

from agentguard.config import ConfigError, load_config
from agentguard.engine.runner import ScanResult
from agentguard.ir.models import AgentGraph, AgentSystem, Edge, ModuleFacts
from agentguard.plugins import hookimpl

_START_ALIASES = frozenset({"START", "__start__"})
_END_ALIASES = frozenset({"END", "__end__"})


class Plugin:
    """Register the ``agentguard graph`` command."""

    name = "agentguard-graph"

    @hookimpl
    def register_commands(self, app: typer.Typer) -> None:
        app.command("graph")(graph_command)


def graph_command(
    path: Annotated[Path, typer.Argument(help="Source file or directory.")],
    output: Annotated[
        Path | None, typer.Option("--output", help="Write Mermaid output.")
    ] = None,
) -> None:
    """Render normalized agent graphs as Mermaid text."""
    try:
        from agentguard.cli.scan import analyze_project

        root = path.resolve() if path.is_dir() else path.resolve().parent
        result = analyze_project([path], load_config(root), root=root)
        for diagnostic in result.parse_errors:
            typer.echo(
                f"warning: skipped {diagnostic.path}: {diagnostic.message}",
                err=True,
            )
        text = _render(result)
        if output is not None:
            output.write_text(text, encoding="utf-8")
        else:
            typer.echo(text, nl=False)
    except (ConfigError, FileNotFoundError, OSError, ValueError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=2) from error


def _render(result: ScanResult) -> str:
    """Render every normalized graph in a scan result as deterministic Mermaid."""
    system = result.system
    if system is None:
        return _render_empty()
    return _render_system(system)


def _render_system(system: AgentSystem) -> str:
    modules = sorted(system.modules, key=_module_sort_key)
    if not any(module.graphs for module in modules):
        return _render_empty()
    lines = ["flowchart TD"]
    for module_index, module in enumerate(modules):
        graphs = sorted(module.graphs, key=_graph_sort_key)
        for graph_index, graph in enumerate(graphs):
            lines.extend(_render_graph(graph, module_index, graph_index))
    return "\n".join(lines) + "\n"


def _module_sort_key(module: ModuleFacts) -> tuple[str, str]:
    """Return a stable key for a module and its graph content."""
    graphs = sorted(module.graphs, key=_graph_sort_key)
    graph_key = "\x01".join("\x02".join(_graph_sort_key(graph)) for graph in graphs)
    return module.path.as_posix(), graph_key


def _graph_sort_key(graph: AgentGraph) -> tuple[str, ...]:
    """Return a key independent of dictionary/list insertion order."""
    node_names = tuple(
        sorted(set(graph.nodes).union(node.name for node in graph.nodes.values()))
    )
    edge_keys = tuple(sorted(_edge_sort_key(edge) for edge in graph.edges))
    fan_out_keys = tuple(
        sorted(
            "\x00".join(
                (
                    fan_out.source,
                    "\x01".join(sorted(set(fan_out.branches))),
                    fan_out.mechanism,
                    str(fan_out.loc.line),
                    str(fan_out.loc.col),
                )
            )
            for fan_out in graph.fan_outs
        )
    )
    return (
        graph.name,
        graph.framework,
        _optional_name(graph.entry),
        "\x00".join(node_names),
        "\x01".join(edge_keys),
        "\x02".join(sorted(graph.terminals)),
        "\x03".join(fan_out_keys),
        str(graph.loc.line),
        str(graph.loc.col),
    )


def _edge_sort_key(edge: Edge) -> str:
    """Return a stable serialized key for an IR edge."""
    return "\x00".join(
        (
            edge.source,
            _optional_name(edge.target),
            str(int(edge.conditional)),
            str(edge.loc.line),
            str(edge.loc.col),
        )
    )


def _optional_name(value: str | None) -> str:
    return "\x00" if value is None else value


def _render_graph(graph: AgentGraph, module_index: int, graph_index: int) -> list[str]:
    prefix = f"g{module_index}_{graph_index}"
    names = _graph_names(graph)
    node_ids = {name: f"{prefix}_n{index}" for index, name in enumerate(names)}
    start_id = f"{prefix}_start"
    end_id = f"{prefix}_end"
    unresolved_id = f"{prefix}_unresolved"
    terminal_names = _terminal_names(graph)

    start_targets: set[str] = set()
    if graph.entry is not None and graph.entry not in _START_ALIASES | _END_ALIASES:
        start_targets.add(graph.entry)
    for edge in graph.edges:
        if (
            edge.source in _START_ALIASES
            and edge.target is not None
            and edge.target not in _END_ALIASES
        ):
            start_targets.add(edge.target)
    has_start_edge = any(edge.source in _START_ALIASES for edge in graph.edges)
    has_start_fan_out = any(
        fan_out.source in _START_ALIASES for fan_out in graph.fan_outs
    )
    has_start = bool(start_targets) or has_start_edge or has_start_fan_out

    has_explicit_end = any(edge.target in _END_ALIASES for edge in graph.edges) or any(
        branch in _END_ALIASES
        for fan_out in graph.fan_outs
        for branch in fan_out.branches
    )
    has_end = bool(terminal_names) or has_explicit_end
    has_unresolved = any(
        edge.target is None and edge.source not in terminal_names
        for edge in graph.edges
    )

    lines = [f"  %% graph: {_escape_label(graph.name)}"]
    for name in names:
        lines.append(f'  {node_ids[name]}["{_escape_label(name)}"]')
    if has_start:
        lines.append(f'  {start_id}["START"]')
    if has_end:
        lines.append(f'  {end_id}["END"]')
    if has_unresolved:
        lines.append(f'  {unresolved_id}["unresolved"]')

    candidates: list[tuple[str, str | None, bool]] = [
        ("START", target, False) for target in sorted(start_targets)
    ]
    candidates.extend(
        (
            edge.source,
            _resolved_edge_target(edge, terminal_names),
            edge.conditional,
        )
        for edge in sorted(graph.edges, key=_edge_sort_key)
    )

    explicit_pairs: set[tuple[str, str]] = set()
    for edge in graph.edges:
        target = _resolved_edge_target(edge, terminal_names)
        if target is not None:
            explicit_pairs.add(
                (
                    _endpoint_id(edge.source, node_ids, start_id, end_id),
                    _endpoint_id(target, node_ids, start_id, end_id),
                )
            )

    terminal_edges: set[tuple[str, str]] = set()
    for edge in graph.edges:
        target = _resolved_edge_target(edge, terminal_names)
        if edge.source in terminal_names and target in _END_ALIASES:
            terminal_edges.add((edge.source, target))
    candidates.extend(
        (terminal, "END", False)
        for terminal in sorted(terminal_names)
        if (terminal, "END") not in terminal_edges
    )

    fan_outs = sorted(
        graph.fan_outs,
        key=lambda fan_out: (
            fan_out.source,
            tuple(sorted(set(fan_out.branches))),
            fan_out.mechanism,
            fan_out.loc.line,
            fan_out.loc.col,
        ),
    )
    for fan_out in fan_outs:
        for branch in sorted(set(fan_out.branches)):
            target = branch if branch not in _END_ALIASES else "END"
            source_id = _endpoint_id(fan_out.source, node_ids, start_id, end_id)
            target_id = _endpoint_id(target, node_ids, start_id, end_id)
            if (source_id, target_id) not in explicit_pairs:
                candidates.append((fan_out.source, target, True))

    rendered_edges: list[str] = []
    seen_edges: set[tuple[str, str, bool]] = set()
    for source, target, conditional in sorted(
        candidates,
        key=lambda item: (item[0], _optional_name(item[1]), item[2]),
    ):
        source_id = _endpoint_id(source, node_ids, start_id, end_id)
        target_id = (
            unresolved_id
            if target is None
            else _endpoint_id(target, node_ids, start_id, end_id)
        )
        edge_key = (source_id, target_id, conditional)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        arrow = "-.->" if conditional else "-->"
        rendered_edges.append(f"  {source_id} {arrow} {target_id}")
    lines.extend(rendered_edges)
    return lines


def _graph_names(graph: AgentGraph) -> list[str]:
    names: set[str] = set()

    def add(name: str) -> None:
        if name not in _START_ALIASES | _END_ALIASES:
            names.add(name)

    for name in graph.nodes:
        add(name)
    for node in graph.nodes.values():
        add(node.name)
    for edge in graph.edges:
        add(edge.source)
        if edge.target is not None:
            add(edge.target)
    for terminal in graph.terminals:
        add(terminal)
    if graph.entry is not None:
        add(graph.entry)
    for fan_out in graph.fan_outs:
        add(fan_out.source)
        for branch in fan_out.branches:
            add(branch)
    return sorted(names)


def _terminal_names(graph: AgentGraph) -> set[str]:
    return {
        terminal
        for terminal in graph.terminals
        if terminal not in _START_ALIASES | _END_ALIASES
    }


def _resolved_edge_target(edge: Edge, terminal_names: set[str]) -> str | None:
    if edge.target is None:
        return "END" if edge.source in terminal_names else None
    return edge.target


def _endpoint_id(
    name: str,
    node_ids: dict[str, str],
    start_id: str,
    end_id: str,
) -> str:
    if name in _START_ALIASES:
        return start_id
    if name in _END_ALIASES:
        return end_id
    return node_ids[name]


def _render_empty() -> str:
    return 'flowchart TD\n  empty["No graph data"]\n'


def _escape_label(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    escaped = html.escape(normalized, quote=True)
    return escaped.replace("[", "&#91;").replace("]", "&#93;").replace("\n", "&#10;")
