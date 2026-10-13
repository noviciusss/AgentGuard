"""Safe AG004 LangGraph recursion-limit transformations."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import libcst as cst

from agentguard.findings import Finding
from agentguard.fixes.engine import FixEngine, FixResult


def preview_recursion_limit_fixes(
    path: Path,
    source: str,
    findings: Iterable[Finding],
    limit: int,
) -> FixResult | None:
    """Preview invocation-config limits for supported AG004 graph findings."""
    target_lines = {
        finding.loc.line for finding in findings if finding.rule_id == "AG004"
    }
    if not target_lines:
        return None
    return FixEngine().preview(
        path,
        source,
        lambda module: _add_recursion_limit(module, target_lines, limit),
    )


def _add_recursion_limit(
    module: cst.Module, target_lines: set[int], limit: int
) -> cst.Module:
    class AddRecursionLimit(cst.CSTTransformer):
        def __init__(self) -> None:
            self.builders: set[str] = set()
            self.compiled_graphs: set[str] = set()

        def leave_Assign(
            self, original_node: cst.Assign, updated_node: cst.Assign
        ) -> cst.Assign:
            value = updated_node.value
            if not isinstance(value, cst.Call):
                return updated_node
            if _is_state_graph_call(value):
                for target in updated_node.targets:
                    if isinstance(target.target, cst.Name):
                        self.builders.add(target.target.value)
                return updated_node
            if not (
                isinstance(value.func, cst.Attribute)
                and value.func.attr.value == "compile"
                and isinstance(value.func.value, cst.Name)
                and value.func.value.value in self.builders
            ):
                return updated_node
            for target in updated_node.targets:
                if isinstance(target.target, cst.Name):
                    self.compiled_graphs.add(target.target.value)
            return updated_node

        def leave_Call(
            self, original_node: cst.Call, updated_node: cst.Call
        ) -> cst.Call:
            if not _is_invoke_call(updated_node, self.compiled_graphs):
                return updated_node
            if len(updated_node.args) > 1 or not updated_node.args:
                return updated_node
            return updated_node.with_changes(
                args=[
                    *updated_node.args,
                    cst.Arg(
                        cst.Dict(
                            [
                                cst.DictElement(
                                    cst.SimpleString('"recursion_limit"'),
                                    cst.Integer(str(limit)),
                                )
                            ]
                        )
                    ),
                ]
            )

    transformed = cst.MetadataWrapper(module).visit(AddRecursionLimit())
    assert isinstance(transformed, cst.Module)
    return transformed


def _is_state_graph_call(call: cst.Call) -> bool:
    function = call.func
    return isinstance(function, cst.Name) and function.value == "StateGraph"


def _is_invoke_call(call: cst.Call, graphs: set[str]) -> bool:
    function = call.func
    return (
        isinstance(function, cst.Attribute)
        and function.attr.value in {"invoke", "ainvoke", "stream", "astream"}
        and isinstance(function.value, cst.Name)
        and function.value.value in graphs
    )
