"""Plain-Python adapter for calls, loops, retries, and concurrency shapes."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from agentguard.adapters.base import FrameworkAdapter
from agentguard.engine.parser import ParsedModule
from agentguard.findings import Location
from agentguard.ir.calls import KnownCall, TimeoutMode, lookup_known_call
from agentguard.ir.models import (
    AgentGraph,
    AgentNode,
    CallSite,
    FanOut,
    KwargInfo,
    Loop,
    ModuleFacts,
    StateKey,
)

_MUTATING_METHODS = frozenset(
    {"append", "extend", "insert", "remove", "pop", "clear", "update", "setdefault"}
)
_MUTABLE_CONSTRUCTORS = frozenset({"list", "dict", "set", "defaultdict", "deque"})
FanOutMechanism: TypeAlias = Literal[
    "multiple_edges", "send_api", "thread_pool", "asyncio_gather", "crewai_async"
]

_FAN_OUT_MECHANISMS: dict[str, FanOutMechanism] = {
    "asyncio.gather": "asyncio_gather",
    "asyncio.create_task": "asyncio_gather",
    "asyncio.ensure_future": "asyncio_gather",
    "threading.Thread": "thread_pool",
    "concurrent.futures.ThreadPoolExecutor.submit": "thread_pool",
    "concurrent.futures.ThreadPoolExecutor.map": "thread_pool",
}


class GenericAdapter(FrameworkAdapter):
    """Build conservative IR facts for ordinary Python agent code."""

    name = "generic"

    def can_handle(self, module: ParsedModule) -> bool:
        """Generic Python is the fallback for every parsed module."""
        return True

    def build(self, module: ParsedModule) -> ModuleFacts:
        """Build module facts without importing or executing user code."""
        visitor = _GenericVisitor(module)
        visitor.visit(module.tree)
        return visitor.module_facts()


@dataclass
class _FunctionState:
    name: str
    loc: Location
    calls: list[CallSite]
    reads: set[str]
    writes: set[str]
    mutable_defaults: set[str]


class _GenericVisitor(ast.NodeVisitor):
    def __init__(self, module: ParsedModule) -> None:
        self.module = module
        self.path = module.path
        self.aliases: dict[str, str] = {}
        self.client_families: dict[str, str] = {}
        self.client_timeouts: dict[str, bool | None] = {}
        self.call_sites: list[CallSite] = []
        self.loops: list[Loop] = []
        self.module_mutables: dict[str, Location] = {}
        self.functions: dict[str, _FunctionState] = {}
        self.function_stack: list[_FunctionState] = []
        self.loop_stack: list[list[CallSite]] = []
        self.fan_outs: list[FanOut] = []
        self._top_level = True

    def module_facts(self) -> ModuleFacts:
        nodes = {
            name: AgentNode(
                name=name,
                framework="generic",
                loc=state.loc,
                function_ref=name,
                reads_state=state.reads,
                writes_state=state.writes,
                call_sites=state.calls,
                tools=[],
                mutable_default_args=state.mutable_defaults,
            )
            for name, state in sorted(self.functions.items())
        }
        state_keys = {
            name: StateKey(name, has_reducer=False, mutable_type=True)
            for name in sorted(self.module_mutables)
        }
        graph_loc = Location(
            self.path,
            1,
            0,
            max(len(self.module.source_lines), 1),
            0,
        )
        graph = AgentGraph(
            name=self.path.stem,
            framework="generic",
            nodes=nodes,
            edges=[],
            entry=None,
            terminals=set(),
            state_keys=state_keys,
            recursion_limit=None,
            fan_outs=self.fan_outs,
            loc=graph_loc,
        )
        return ModuleFacts(
            path=self.path,
            call_sites=self.call_sites,
            loops=self.loops,
            graphs=[graph],
            module_mutables=self.module_mutables,
            imports=self.aliases,
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".")[0]
            self.aliases[local_name] = alias.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            if alias.name == "*":
                continue
            local_name = alias.asname or alias.name
            self.aliases[local_name] = f"{module}.{alias.name}".strip(".")

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._top_level:
            for target in node.targets:
                name = _assigned_name(target)
                if name is not None and _is_mutable_value(node.value):
                    self.module_mutables[name] = _location(self.path, node)
        self._record_client_assignment(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._top_level:
            name = _assigned_name(node.target)
            if (
                name is not None
                and node.value is not None
                and _is_mutable_value(node.value)
            ):
                self.module_mutables[name] = _location(self.path, node)
        if node.value is not None:
            self._record_client_assignment([node.target], node.value)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        state = _FunctionState(
            name=node.name,
            loc=_location(self.path, node),
            calls=[],
            reads=set(),
            writes=set(),
            mutable_defaults=_mutable_default_names(node),
        )
        self.functions[node.name] = state
        self.function_stack.append(state)
        previous_top_level = self._top_level
        self._top_level = False
        for statement in node.body:
            self.visit(statement)
        self._top_level = previous_top_level
        self.function_stack.pop()
        self._add_retry_loops(node, state)

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node, _for_bound(node.iter))

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_loop(node, (None, None, None))

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node, _while_bound(node.test))

    def _visit_loop(
        self,
        node: ast.For | ast.AsyncFor | ast.While,
        bound: tuple[bool | None, int | None, str | None],
    ) -> None:
        calls: list[CallSite] = []
        self.loop_stack.append(calls)
        for statement in node.body:
            self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)
        self.loop_stack.pop()
        self.loops.append(
            Loop(
                loc=_location(self.path, node),
                kind="for" if isinstance(node, (ast.For, ast.AsyncFor)) else "while",
                has_bound=bound[0],
                bound_value=bound[1],
                bounded_by=bound[2],
                has_backoff=None,
                calls_inside=calls,
                catches_exceptions=_contains_try(node.body),
            )
        )

    def visit_Call(self, node: ast.Call) -> None:
        qualified_name = self._qualified_name(node.func)
        kwargs = _kwargs(node)
        known = lookup_known_call(qualified_name)
        if known is not None:
            site = self._call_site(node, qualified_name, kwargs, known)
            self.call_sites.append(site)
            self._attach_call(site)
            self._record_client_assignment_from_call(node, known)
        else:
            mechanism = _fan_out_mechanism(qualified_name)
            if mechanism is not None:
                self.fan_outs.append(
                    FanOut(
                        source=self._current_function_name() or self.path.stem,
                        branches=_fan_out_branches(node),
                        loc=_location(self.path, node),
                        mechanism=mechanism,
                    )
                )
            if _is_tool_call(qualified_name):
                site = self._call_site(
                    node,
                    qualified_name,
                    kwargs,
                    KnownCall(qualified_name, "tool", TimeoutMode.DEFAULT),
                )
                self.call_sites.append(site)
                self._attach_call(site)
            elif self.function_stack:
                mutated_name = _mutated_call_root(node)
                if mutated_name is not None:
                    self.function_stack[-1].writes.add(mutated_name)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self.function_stack and isinstance(node.value, ast.Name):
            if isinstance(node.ctx, ast.Store):
                self.function_stack[-1].writes.add(node.value.id)
            else:
                self.function_stack[-1].reads.add(node.value.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self.function_stack and isinstance(node.ctx, ast.Store):
            self.function_stack[-1].writes.add(_attribute_root(node))
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if self.function_stack:
            name = _assigned_name(node.target)
            if name is not None:
                self.function_stack[-1].writes.add(name)
        self.generic_visit(node)

    def _call_site(
        self,
        node: ast.Call,
        qualified_name: str,
        kwargs: dict[str, KwargInfo],
        known: KnownCall,
    ) -> CallSite:
        timeout = _timeout_status(
            qualified_name,
            kwargs,
            known,
            self.client_timeouts,
            self.client_families,
        )
        return CallSite(
            loc=_location(self.path, node),
            kind=known.kind,
            qualified_name=qualified_name,
            kwargs=kwargs,
            has_timeout=timeout,
            enclosing_function=self._current_function_name(),
            in_loop=bool(self.loop_stack),
        )

    def _attach_call(self, site: CallSite) -> None:
        if self.function_stack:
            self.function_stack[-1].calls.append(site)
        for calls in self.loop_stack:
            calls.append(site)

    def _current_function_name(self) -> str | None:
        return self.function_stack[-1].name if self.function_stack else None

    def _qualified_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, self.client_families.get(node.id, node.id))
        if isinstance(node, ast.Attribute):
            parent = self._qualified_name(node.value)
            return f"{parent}.{node.attr}"
        return "<dynamic>"

    def _record_client_assignment(
        self, targets: Iterable[ast.expr], value: ast.expr
    ) -> None:
        if not isinstance(value, ast.Call):
            return
        qualified_name = self._qualified_name(value.func)
        known = lookup_known_call(qualified_name)
        if (
            known is None
            or known.client_family is None
            or not _is_client_constructor(qualified_name)
        ):
            return
        for target in targets:
            name = _assigned_name(target)
            if name is not None:
                self.client_families[name] = known.client_family
                self.client_timeouts[name] = _explicit_timeout(value)
                self.client_timeouts[known.client_family] = _explicit_timeout(value)

    def _record_client_assignment_from_call(
        self, node: ast.Call, known: KnownCall
    ) -> None:
        if known.client_family is not None and _is_client_constructor(
            self._qualified_name(node.func)
        ):
            self.client_timeouts[self._qualified_name(node.func)] = _explicit_timeout(
                node
            )

    def _add_retry_loops(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, state: _FunctionState
    ) -> None:
        for decorator in node.decorator_list:
            qualified_name = self._qualified_name(
                decorator.func if isinstance(decorator, ast.Call) else decorator
            )
            if not (
                qualified_name in {"retry", "tenacity.retry", "backoff.on_exception"}
                or qualified_name.endswith(".retry")
                or qualified_name.endswith(".on_exception")
            ):
                continue
            args = decorator.args if isinstance(decorator, ast.Call) else []
            keywords = (
                {
                    keyword.arg: keyword.value
                    for keyword in decorator.keywords
                    if keyword.arg is not None
                }
                if isinstance(decorator, ast.Call)
                else {}
            )
            bound = _retry_bound(qualified_name, args, keywords)
            self.loops.append(
                Loop(
                    loc=_location(self.path, decorator),
                    kind="retry_decorator",
                    has_bound=bound[0],
                    bound_value=bound[1],
                    bounded_by=bound[2],
                    has_backoff="wait" in keywords or "max_time" in keywords,
                    calls_inside=state.calls,
                    catches_exceptions=True,
                )
            )


def _location(path: Path, node: ast.AST) -> Location:
    line = getattr(node, "lineno", 1)
    col = getattr(node, "col_offset", 0)
    end_line = getattr(node, "end_lineno", line)
    end_col = getattr(node, "end_col_offset", col + 1)
    return Location(path, line, col, end_line, end_col)


def _assigned_name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _attribute_root(node: ast.Attribute) -> str:
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else "<dynamic>"


def _is_mutable_value(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _MUTABLE_CONSTRUCTORS
    )


def _mutable_default_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    defaults = [
        *([None] * (len(arguments) - len(node.args.defaults))),
        *node.args.defaults,
    ]
    defaults.extend(node.args.kw_defaults)
    return {
        argument.arg
        for argument, default in zip(arguments, defaults, strict=False)
        if default is not None and _is_mutable_value(default)
    }


def _kwargs(node: ast.Call) -> dict[str, KwargInfo]:
    result: dict[str, KwargInfo] = {}
    for keyword in node.keywords:
        name = keyword.arg or "**"
        value, literal = _literal_value(keyword.value)
        result[name] = KwargInfo(value, literal)
    return result


def _literal_value(node: ast.AST) -> tuple[str | int | float | bool | None, bool]:
    if isinstance(node, ast.Constant) and isinstance(
        node.value, (str, int, float, bool, type(None))
    ):
        return node.value, True
    return None, False


def _explicit_timeout(node: ast.Call) -> bool | None:
    for keyword in node.keywords:
        if keyword.arg == "timeout":
            value, literal = _literal_value(keyword.value)
            if not literal:
                return None
            return value is not None
        if keyword.arg == "**":
            return None
    return False


def _timeout_status(
    qualified_name: str,
    kwargs: dict[str, KwargInfo],
    known: KnownCall,
    client_timeouts: dict[str, bool | None],
    client_families: dict[str, str],
) -> bool | None:
    if "timeout" in kwargs:
        timeout = kwargs["timeout"]
        return timeout.value is not None if timeout.is_literal else None
    if "**" in kwargs:
        return None
    if known.timeout_mode == TimeoutMode.DEFAULT:
        return True
    if known.timeout_mode == TimeoutMode.REQUIRED:
        return False
    if known.client_family is not None:
        if known.client_family in client_timeouts:
            return client_timeouts[known.client_family]
        if qualified_name in client_timeouts:
            return client_timeouts[qualified_name]
        for client_name, family in client_families.items():
            if family == known.client_family and qualified_name.startswith(
                f"{client_name}."
            ):
                return client_timeouts.get(client_name)
        if known.client_family == "httpx":
            return True
    return False


def _mutated_call_root(node: ast.Call) -> str | None:
    if not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr not in _MUTATING_METHODS:
        return None
    return _attribute_root(node.func)


def _is_client_constructor(qualified_name: str) -> bool:
    return qualified_name.rsplit(".", 1)[-1] in {
        "OpenAI",
        "AsyncOpenAI",
        "Client",
        "AsyncClient",
        "ClientSession",
        "ChatOpenAI",
        "ChatAnthropic",
    }


def _for_bound(node: ast.expr) -> tuple[bool | None, int | None, str | None]:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "range"
    ):
        if (
            len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, int)
        ):
            return True, node.args[0].value, "range(N)"
        return True, None, "range(config)"
    return None, None, None


def _while_bound(node: ast.expr) -> tuple[bool | None, int | None, str | None]:
    if isinstance(node, ast.Constant) and node.value in (True, 1):
        return False, None, None
    if isinstance(node, ast.Compare):
        if (
            isinstance(node.left, ast.Call)
            and _qualified_expr(node.left.func) == "time.monotonic"
        ):
            return True, None, "deadline"
        if node.comparators and isinstance(node.comparators[0], ast.Constant):
            value = node.comparators[0].value
            if isinstance(value, int):
                return True, value, "counter"
    return None, None, None


def _retry_bound(
    qualified_name: str, args: list[ast.expr], keywords: dict[str, ast.expr]
) -> tuple[bool | None, int | None, str | None]:
    if qualified_name.endswith("on_exception"):
        for name in ("max_tries", "max_time"):
            if name in keywords:
                return True, _constant_int(keywords[name]), name
        return False, None, None
    stop = keywords.get("stop")
    if not isinstance(stop, ast.Call):
        return False, None, None
    stop_name = _qualified_expr(stop.func)
    if stop_name.endswith("stop_after_attempt") or stop_name.endswith(
        "stop_after_delay"
    ):
        value = stop.args[0] if stop.args else None
        return True, _constant_int(value), stop_name.rsplit(".", 1)[-1]
    return False, None, None


def _constant_int(node: ast.expr | None) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _qualified_expr(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_expr(node.value)
        return f"{parent}.{node.attr}"
    return "<dynamic>"


def _contains_try(nodes: list[ast.stmt]) -> bool:
    for node in nodes:
        if isinstance(node, ast.Try):
            return True
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if _contains_try(child.body):
                return True
    return False


def _fan_out_mechanism(qualified_name: str) -> FanOutMechanism | None:
    for prefix, mechanism in _FAN_OUT_MECHANISMS.items():
        if qualified_name == prefix or qualified_name.endswith(
            f".{prefix.rsplit('.', 1)[-1]}"
        ):
            return mechanism
    return None


def _fan_out_branches(node: ast.Call) -> list[str]:
    branches: list[str] = []
    for argument in node.args:
        if isinstance(argument, ast.Name):
            branches.append(argument.id)
        elif isinstance(argument, ast.Call):
            branches.append(_qualified_expr(argument.func))
    return branches or ["<dynamic>"]


def _is_tool_call(qualified_name: str) -> bool:
    return qualified_name.endswith(".invoke_tool") or qualified_name.endswith(
        ".run_tool"
    )
