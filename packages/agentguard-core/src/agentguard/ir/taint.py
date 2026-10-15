"""Conservative taint, secret extraction, and same-file call summaries.

Inter-procedural return and sink propagation is intentionally limited to
direct module-local functions. Imported, dynamic, class, and nested-function
return flows are left unknown rather than inferred across module boundaries.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from agentguard.findings import Location
from agentguard.ir.models import (
    ExceptionFact,
    SecretFact,
    TaintFlow,
)
from agentguard.ir.taint_interprocedural import analyze_interprocedural

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


def analyze_taint(tree: ast.Module, path: Path) -> TaintFacts:
    """Extract simple source-to-sink flows without executing application code."""
    visitor = _TaintVisitor(path, tree)
    visitor.visit(tree)
    flows, call_graph = analyze_interprocedural(tree, path)
    return TaintFacts(
        flows=flows,
        secrets=visitor.secrets,
        exceptions=visitor.exceptions,
        state_growths=visitor.state_growths,
        call_graph=call_graph,
    )


class _TaintVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, tree: ast.Module) -> None:
        self.path = path
        self.aliases: dict[str, str] = {}
        self.secrets: list[SecretFact] = []
        self.exceptions: list[ExceptionFact] = []
        self.state_growths: list[Location] = []
        self.functions: list[str] = []
        self.loop_depth = 0
        self.trimmed_loop_depth = 0

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
        for statement in node.body:
            self.visit(statement)
        self.functions.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._secret(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
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
