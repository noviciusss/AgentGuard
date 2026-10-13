"""Conservative intra-function taint and secret extraction."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from agentguard.findings import Location
from agentguard.ir.calls import lookup_known_call
from agentguard.ir.models import (
    DataSource,
    ExceptionFact,
    SecretFact,
    TaintFlow,
    TaintSink,
)

_SECRET_NAME = re.compile(
    r"(?:api[_-]?key|token|secret|password|passwd|credential)", re.I
)
_SECRET_VALUE = re.compile(
    r"(?:sk-[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{12,}|gh[pousr]_[A-Za-z0-9_]{20,})"
)


@dataclass(frozen=True)
class TaintFacts:
    """Facts extracted from a single parsed module."""

    flows: list[TaintFlow]
    secrets: list[SecretFact]
    exceptions: list[ExceptionFact]
    state_growths: list[Location]
    call_graph: dict[str, tuple[str, ...]]


@dataclass
class _ReturnSummary:
    """Symbolic return sources before local-call summaries are resolved."""

    sources: set[DataSource]
    dependencies: set[str]


def analyze_taint(tree: ast.Module, path: Path) -> TaintFacts:
    """Extract simple source-to-sink flows without executing application code."""
    visitor = _TaintVisitor(path, tree)
    visitor.visit(tree)
    return TaintFacts(
        flows=visitor.flows,
        secrets=visitor.secrets,
        exceptions=visitor.exceptions,
        state_growths=visitor.state_growths,
        call_graph=visitor.call_graph,
    )


class _TaintVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, tree: ast.Module) -> None:
        self.path = path
        self.aliases: dict[str, str] = {}
        self.tainted: dict[str, set[DataSource]] = {}
        self.flows: list[TaintFlow] = []
        self.secrets: list[SecretFact] = []
        self.exceptions: list[ExceptionFact] = []
        self.state_growths: list[Location] = []
        self.functions: list[str] = []
        self.loop_depth = 0
        self.trimmed_loop_depth = 0
        self.call_graph = _build_call_graph(tree)
        self.function_returns = _build_return_sources(tree)

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            self.aliases[item.asname or item.name.split(".")[0]] = item.name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for item in node.names:
            if item.name != "*":
                self.aliases[item.asname or item.name] = f"{module}.{item.name}".strip(
                    "."
                )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.functions.append(node.name)
        arguments = [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ]
        for argument in arguments:
            if argument.arg in {"user_input", "prompt", "query", "message"}:
                self.tainted[argument.arg] = {DataSource.USER_INPUT}
        for statement in node.body:
            self.visit(statement)
        self.functions.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        sources = self._sources(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if sources:
                    self.tainted[target.id] = sources
                self._secret(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            sources = self._sources(node.value)
            if sources:
                self.tainted[node.target.id] = sources
            self._secret(node.target, node.value)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.loop_depth += 1
        if _contains_trim(node):
            self.trimmed_loop_depth += 1
        self.generic_visit(node)
        if _contains_trim(node):
            self.trimmed_loop_depth -= 1
        self.loop_depth -= 1

    def visit_While(self, node: ast.While) -> None:
        self.loop_depth += 1
        if _contains_trim(node):
            self.trimmed_loop_depth += 1
        self.generic_visit(node)
        if _contains_trim(node):
            self.trimmed_loop_depth -= 1
        self.loop_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        qualified = self._qualified(node.func)
        sources = self._sources(node)
        sink = self._sink(qualified, node)
        if sink is not None and sources:
            for source in sorted(sources, key=lambda value: value.value):
                self.flows.append(
                    TaintFlow(
                        loc=_location(self.path, node),
                        source=source,
                        sink=sink,
                        function=self.functions[-1] if self.functions else None,
                        value_name=None,
                    )
                )
        if (
            self.loop_depth
            and not self.trimmed_loop_depth
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"append", "extend", "insert", "update"}
        ):
            root = _root_name(node.func.value)
            if root is not None and root in {"state", "messages", "history"}:
                self.state_growths.append(_location(self.path, node))
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        for handler in node.handlers:
            has_raise = any(isinstance(item, ast.Raise) for item in ast.walk(handler))
            has_logging = any(
                isinstance(item, ast.Call)
                and self._qualified(item.func).split(".")[-1]
                in {"debug", "info", "warning", "error", "exception", "log"}
                for item in ast.walk(handler)
            )
            has_fallback = any(
                isinstance(item, (ast.Return, ast.Break, ast.Continue))
                for item in ast.walk(handler)
            )
            catches = ast.unparse(handler.type) if handler.type is not None else None
            self.exceptions.append(
                ExceptionFact(
                    loc=_location(self.path, handler),
                    function=self.functions[-1] if self.functions else None,
                    catches=catches,
                    has_raise=has_raise,
                    has_logging=has_logging,
                    has_fallback=has_fallback,
                )
            )
        self.generic_visit(node)

    def _sources(self, node: ast.AST) -> set[DataSource]:
        sources: set[DataSource] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                sources.update(self.tainted.get(child.id, set()))
            if isinstance(child, ast.Call):
                qualified = self._qualified(child.func)
                if qualified in {"input", "builtins.input"}:
                    sources.add(DataSource.USER_INPUT)
                if qualified.endswith(".getenv") or qualified == "os.getenv":
                    sources.add(DataSource.ENV)
                known = lookup_known_call(qualified)
                if (known is not None and known.kind == "llm") or any(
                    marker in qualified.lower()
                    for marker in {".responses.", ".chat.", ".completions."}
                ):
                    sources.add(DataSource.LLM_OUTPUT)
                if known is not None and known.kind == "tool":
                    sources.add(DataSource.TOOL_OUTPUT)
                if isinstance(child.func, ast.Name):
                    sources.update(self.function_returns.get(child.func.id, set()))
        return sources

    def _sink(self, qualified: str, node: ast.Call) -> TaintSink | None:
        leaf = qualified.rsplit(".", 1)[-1]
        if leaf == "eval":
            return TaintSink.EVAL
        if leaf == "exec":
            return TaintSink.EXEC
        if qualified.startswith("subprocess."):
            return TaintSink.SUBPROCESS
        if leaf in {"execute", "executemany"}:
            return TaintSink.SQL
        if leaf == "open" or qualified == "pathlib.Path":
            return TaintSink.FILE_PATH
        if any(
            keyword in qualified.lower()
            for keyword in {"system_prompt", "systemmessage"}
        ):
            return TaintSink.SYSTEM_PROMPT
        for keyword in node.keywords:
            if keyword.arg in {"system", "system_prompt"}:
                return TaintSink.SYSTEM_PROMPT
        return None

    def _secret(self, target: ast.Name, value: ast.AST) -> None:
        if not _SECRET_NAME.search(target.id):
            return
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            self.secrets.append(
                SecretFact(_location(self.path, target), target.id, "credential")
            )
        elif isinstance(value, ast.Call) and self._qualified(value.func).endswith(
            "Secret"
        ):
            return
        elif _SECRET_VALUE.search(ast.unparse(value)):
            self.secrets.append(
                SecretFact(_location(self.path, target), target.id, "credential")
            )

    def _qualified(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{self._qualified(node.value)}.{node.attr}"
        return "<dynamic>"


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _build_call_graph(tree: ast.Module) -> dict[str, tuple[str, ...]]:
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    graph: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = sorted(
            {
                child.func.id
                for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id in functions
            }
        )
        graph[node.name] = tuple(calls)
    return graph


def _build_return_sources(tree: ast.Module) -> dict[str, set[DataSource]]:
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    function_names = set(functions)
    aliases = _module_aliases(tree)
    symbolic: dict[str, _ReturnSummary] = {
        name: _summarize_function(node, function_names, aliases)
        for name, node in functions.items()
    }
    result = {name: set(summary.sources) for name, summary in symbolic.items()}

    changed = True
    while changed:
        changed = False
        for name, summary in symbolic.items():
            resolved = set(summary.sources)
            for dependency in summary.dependencies:
                resolved.update(result[dependency])
            if resolved != result[name]:
                result[name] = resolved
                changed = True
    return result


def _summarize_function(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    function_names: set[str],
    aliases: dict[str, str],
) -> _ReturnSummary:
    visitor = _ReturnSummaryVisitor(function, function_names, aliases)
    visitor.visit(function)
    return _ReturnSummary(visitor.sources, visitor.dependencies)


class _ReturnSummaryVisitor(ast.NodeVisitor):
    """Collect return sources while excluding nested function scopes."""

    def __init__(
        self,
        root: ast.FunctionDef | ast.AsyncFunctionDef,
        function_names: set[str],
        aliases: dict[str, str],
    ) -> None:
        self.root = root
        self.function_names = function_names
        self.aliases = aliases
        self.locals: dict[str, _ReturnSummary] = {}
        self.sources: set[DataSource] = set()
        self.dependencies: set[str] = set()
        for argument in [
            *root.args.posonlyargs,
            *root.args.args,
            *root.args.kwonlyargs,
        ]:
            if argument.arg in {"user_input", "prompt", "query", "message"}:
                self.locals[argument.arg] = _ReturnSummary(
                    {DataSource.USER_INPUT}, set()
                )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        summary = self._expression(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.locals[target.id] = _copy_summary(summary)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            self.locals[node.target.id] = self._expression(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Name):
            summary = self._expression(node.value)
            previous = self.locals.get(node.target.id)
            if previous is not None:
                summary = _merge_summaries(previous, summary)
            self.locals[node.target.id] = summary

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            summary = self._expression(node.value)
            self.sources.update(summary.sources)
            self.dependencies.update(summary.dependencies)

    def _expression(self, node: ast.AST) -> _ReturnSummary:
        summary = _ReturnSummary(set(), set())
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                local = self.locals.get(child.id)
                if local is not None:
                    summary = _merge_summaries(summary, local)
            elif isinstance(child, ast.Call):
                qualified = _qualified_static(child.func, self.aliases)
                if (
                    isinstance(child.func, ast.Name)
                    and child.func.id in self.function_names
                ):
                    summary.dependencies.add(child.func.id)
                else:
                    summary.sources.update(_direct_call_sources(qualified))
        return summary


def _direct_call_sources(qualified: str) -> set[DataSource]:
    sources: set[DataSource] = set()
    if qualified in {"input", "builtins.input"}:
        sources.add(DataSource.USER_INPUT)
    if qualified.endswith(".getenv") or qualified == "os.getenv":
        sources.add(DataSource.ENV)
    known = lookup_known_call(qualified)
    if known is not None and known.kind == "llm":
        sources.add(DataSource.LLM_OUTPUT)
    if known is not None and known.kind == "tool":
        sources.add(DataSource.TOOL_OUTPUT)
    if any(
        marker in qualified.lower()
        for marker in (".responses.", ".chat.", ".completions.")
    ):
        sources.add(DataSource.LLM_OUTPUT)
    return sources


def _merge_summaries(left: _ReturnSummary, right: _ReturnSummary) -> _ReturnSummary:
    return _ReturnSummary(
        sources={*left.sources, *right.sources},
        dependencies={*left.dependencies, *right.dependencies},
    )


def _copy_summary(summary: _ReturnSummary) -> _ReturnSummary:
    return _ReturnSummary(set(summary.sources), set(summary.dependencies))


def _module_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for item in node.names:
                if item.name != "*":
                    aliases[item.asname or item.name] = f"{module}.{item.name}".strip(
                        "."
                    )
    return aliases


def _qualified_static(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return f"{_qualified_static(node.value, aliases)}.{node.attr}"
    return "<dynamic>"


def _contains_trim(node: ast.For | ast.While) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Assign):
            continue
        if not any(isinstance(target, ast.Subscript) for target in child.targets):
            continue
        if isinstance(child.value, ast.Subscript):
            return True
    return False


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
