"""AST adapter for the LangGraph StateGraph construction API."""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from pathlib import Path

from agentguard.adapters.base import FrameworkAdapter
from agentguard.adapters.generic import GenericAdapter
from agentguard.engine.parser import ParsedModule
from agentguard.findings import Location
from agentguard.ir.models import (
    AgentGraph,
    AgentNode,
    Edge,
    FanOut,
    ModuleFacts,
    StateKey,
)


@dataclass
class _GraphDraft:
    name: str
    builder_name: str
    state_schema: str | None
    loc: Location
    nodes: dict[str, AgentNode]
    edges: list[Edge]
    entry: str | None
    terminals: set[str]
    fan_outs: list[FanOut]
    recursion_limit: int | None


class LangGraphAdapter(FrameworkAdapter):
    """Translate common LangGraph StateGraph builder calls into Agent IR."""

    name = "langgraph"

    def can_handle(self, module: ParsedModule) -> bool:
        """Return true for modules that construct a StateGraph."""
        aliases = _imports(module.tree)
        return any(
            _qualified_name(node.func, aliases).endswith("StateGraph")
            for node in ast.walk(module.tree)
            if isinstance(node, ast.Call)
        )

    def build(self, module: ParsedModule) -> ModuleFacts:
        """Build LangGraph graphs and reuse generic facts for node call sites."""
        generic = GenericAdapter().build(module)
        aliases = _imports(module.tree)
        schemas = _state_schemas(module.tree, aliases)
        functions = {
            node.name: node
            for node in ast.walk(module.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        drafts = _graph_drafts(module, aliases, schemas, generic, functions)
        graphs = [
            _finalize_graph(draft, schemas.get(draft.state_schema or ""))
            for draft in drafts
        ]
        return replace(generic, graphs=graphs)


def _graph_drafts(
    module: ParsedModule,
    aliases: dict[str, str],
    schemas: dict[str, dict[str, StateKey]],
    generic: ModuleFacts,
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> list[_GraphDraft]:
    drafts: dict[str, _GraphDraft] = {}
    compiled_names: dict[str, str] = {}
    for node in ast.walk(module.tree):
        if not isinstance(node, ast.Assign):
            continue
        if isinstance(node.value, ast.Call):
            qualified = _qualified_name(node.value.func, aliases)
            if qualified.endswith("StateGraph"):
                builder_name = _assigned_target(node)
                if builder_name is None:
                    continue
                schema = _name_arg(node.value, 0)
                drafts[builder_name] = _GraphDraft(
                    name=builder_name,
                    builder_name=builder_name,
                    state_schema=schema,
                    loc=_location(module.path, node),
                    nodes={},
                    edges=[],
                    entry=None,
                    terminals=set(),
                    fan_outs=[],
                    recursion_limit=None,
                )
            elif _is_compile_call(node.value, aliases):
                builder = _builder_name(node.value.func)
                if builder in drafts:
                    compiled_names[_assigned_target(node) or builder] = builder

    for node in ast.walk(module.tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        builder = _builder_name(node.func)
        if builder not in drafts:
            continue
        draft = drafts[builder]
        method = node.func.attr
        if method == "add_node":
            _add_node(draft, node, module.path, generic, functions)
        elif method == "add_edge":
            _add_edge(draft, node, module.path)
        elif method == "add_conditional_edges":
            _add_conditional_edges(draft, node, module.path)
        elif method == "set_entry_point":
            draft.entry = _string_arg(node, 0)
        elif method == "set_finish_point":
            target = _string_arg(node, 0)
            if target is not None:
                draft.terminals.add(target)
        elif method == "compile":
            draft.recursion_limit = _literal_keyword_int(node, "recursion_limit")

    for draft in drafts.values():
        _add_static_fanout(draft)
        for function in functions.values():
            for send in _send_calls(function, aliases):
                target = _string_arg(send, 0) or "<dynamic>"
                draft.fan_outs.append(
                    FanOut(
                        source=function.name,
                        branches=[target],
                        loc=_location(module.path, send),
                        mechanism="send_api",
                    )
                )
    return [drafts[name] for name in sorted(drafts)]


def _finalize_graph(
    draft: _GraphDraft, state_keys: dict[str, StateKey] | None
) -> AgentGraph:
    return AgentGraph(
        name=draft.name,
        framework="langgraph",
        nodes=draft.nodes,
        edges=draft.edges,
        entry=draft.entry,
        terminals=draft.terminals,
        state_keys=state_keys or {},
        recursion_limit=draft.recursion_limit,
        fan_outs=draft.fan_outs,
        loc=draft.loc,
    )


def _add_node(
    draft: _GraphDraft,
    call: ast.Call,
    path: Path,
    generic: ModuleFacts,
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> None:
    if not call.args:
        return
    explicit_name = _string_expr(call.args[0])
    function_expr = (
        call.args[1]
        if explicit_name is not None and len(call.args) > 1
        else call.args[0]
    )
    function_ref = _string_expr(function_expr) or _name_expr(function_expr)
    if function_ref is None:
        return
    name = explicit_name or function_ref
    generic_node = next(
        (
            node
            for node in generic.graphs[0].nodes.values()
            if node.name == function_ref
        ),
        None,
    )
    if generic_node is None:
        generic_node = AgentNode(
            name=name,
            framework="langgraph",
            loc=_location(path, call),
            function_ref=function_ref,
            reads_state=set(),
            writes_state=_returned_state_keys(functions.get(function_ref)),
            call_sites=[],
            tools=[],
        )
    else:
        generic_node = replace(
            generic_node,
            name=name,
            framework="langgraph",
            function_ref=function_ref,
            writes_state=(
                generic_node.writes_state
                | _returned_state_keys(functions.get(function_ref))
            ),
            loc=_location(path, call),
        )
    draft.nodes[name] = generic_node


def _add_edge(draft: _GraphDraft, call: ast.Call, path: Path) -> None:
    source = _graph_arg(call, 0)
    target = _graph_arg(call, 1)
    if source is None or target is None:
        return
    if source in {"START", "__start__"}:
        draft.entry = target
    if target in {"END", "__end__"}:
        draft.terminals.add(source)
        target_value: str | None = None
    else:
        target_value = target
    draft.edges.append(Edge(source, target_value, False, _location(path, call)))


def _add_conditional_edges(draft: _GraphDraft, call: ast.Call, path: Path) -> None:
    source = _string_arg(call, 0)
    if source is None:
        return
    path_map: list[str] = []
    if len(call.args) >= 3 and isinstance(call.args[2], ast.Dict):
        path_map = [
            target
            for value in call.args[2].values
            if (target := _graph_expr(value)) is not None
        ]
    keyword = next((item for item in call.keywords if item.arg == "path_map"), None)
    if keyword is not None and isinstance(keyword.value, ast.Dict):
        path_map = [
            target
            for value in keyword.value.values
            if (target := _graph_expr(value)) is not None
        ]
    targets: list[str | None] = [*path_map] or [None]
    for target in targets:
        if target in {"END", "__end__"}:
            draft.terminals.add(source)
            target = None
        draft.edges.append(Edge(source, target, True, _location(path, call)))


def _add_static_fanout(draft: _GraphDraft) -> None:
    grouped: dict[str, list[str]] = {}
    for edge in draft.edges:
        if edge.target is not None and not edge.conditional:
            grouped.setdefault(edge.source, []).append(edge.target)
    for source, branches in grouped.items():
        if len(branches) > 1:
            draft.fan_outs.append(
                FanOut(
                    source=source,
                    branches=sorted(set(branches)),
                    loc=draft.loc,
                    mechanism="multiple_edges",
                )
            )


def _state_schemas(
    tree: ast.Module, aliases: dict[str, str]
) -> dict[str, dict[str, StateKey]]:
    schemas: dict[str, dict[str, StateKey]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields: dict[str, StateKey] = {}
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(
                statement.target, ast.Name
            ):
                continue
            has_reducer, annotation = _annotated_info(statement.annotation, aliases)
            fields[statement.target.id] = StateKey(
                name=statement.target.id,
                has_reducer=has_reducer,
                mutable_type=_mutable_annotation(annotation),
            )
        if fields:
            schemas[node.name] = fields
    return schemas


def _annotated_info(
    annotation: ast.expr, aliases: dict[str, str]
) -> tuple[bool, ast.expr]:
    if isinstance(annotation, ast.Subscript):
        qualified = _qualified_name(annotation.value, aliases)
        if qualified.endswith("Annotated"):
            values = _subscript_values(annotation.slice)
            return len(values) > 1, values[0] if values else annotation
    return False, annotation


def _mutable_annotation(annotation: ast.expr) -> bool:
    target = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    value = _qualified_name(target, {})
    return value.rsplit(".", 1)[-1] in {"list", "dict", "set"}


def _subscript_values(node: ast.expr) -> list[ast.expr]:
    return list(node.elts) if isinstance(node, ast.Tuple) else [node]


def _returned_state_keys(
    function: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> set[str]:
    if function is None:
        return set()
    keys: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            keys.update(
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
    return keys


def _send_calls(
    function: ast.FunctionDef | ast.AsyncFunctionDef, aliases: dict[str, str]
) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and _qualified_name(node.func, aliases).endswith("Send")
    ]


def _imports(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for item in node.names:
                if item.name != "*":
                    aliases[item.asname or item.name] = f"{module}.{item.name}".strip(
                        "."
                    )
    return aliases


def _qualified_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return f"{_qualified_name(node.value, aliases)}.{node.attr}"
    return "<dynamic>"


def _builder_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id
    return ""


def _is_compile_call(node: ast.Call, aliases: dict[str, str]) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "compile"


def _assigned_target(node: ast.Assign) -> str | None:
    return _name_expr(node.targets[0]) if node.targets else None


def _name_expr(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _string_expr(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _string_arg(call: ast.Call, index: int) -> str | None:
    return _string_expr(call.args[index]) if len(call.args) > index else None


def _graph_arg(call: ast.Call, index: int) -> str | None:
    return _graph_expr(call.args[index]) if len(call.args) > index else None


def _graph_expr(node: ast.AST) -> str | None:
    string = _string_expr(node)
    if string is not None:
        return string
    if isinstance(node, ast.Name) and node.id in {"START", "END"}:
        return node.id
    return None


def _name_arg(call: ast.Call, index: int) -> str | None:
    return _name_expr(call.args[index]) if len(call.args) > index else None


def _literal_keyword_int(call: ast.Call, name: str) -> int | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value if isinstance(keyword.value.value, int) else None
    return None


def _location(path: Path, node: ast.AST) -> Location:
    line = getattr(node, "lineno", 1)
    col = getattr(node, "col_offset", 0)
    return Location(
        path,
        line,
        col,
        getattr(node, "end_lineno", line),
        getattr(node, "end_col_offset", col + 1),
    )
