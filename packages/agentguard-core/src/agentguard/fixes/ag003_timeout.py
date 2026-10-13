"""Safe AG003 timeout transformations."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import libcst as cst
from libcst.metadata import PositionProvider

from agentguard.findings import Finding
from agentguard.fixes.engine import FixEngine, FixResult


def preview_timeout_fixes(
    path: Path,
    source: str,
    findings: Iterable[Finding],
    seconds: int,
) -> FixResult | None:
    """Preview timeout additions for supported AG003 call locations."""
    targets = {
        (finding.loc.line, finding.loc.col)
        for finding in findings
        if finding.rule_id == "AG003"
    }
    if not targets:
        return None
    return FixEngine().preview(
        path,
        source,
        lambda module: _add_timeouts(module, targets, seconds),
    )


def _add_timeouts(
    module: cst.Module, targets: set[tuple[int, int]], seconds: int
) -> cst.Module:
    class AddTimeout(cst.CSTTransformer):
        METADATA_DEPENDENCIES = (PositionProvider,)

        def leave_Call(
            self, original_node: cst.Call, updated_node: cst.Call
        ) -> cst.Call:
            position = self.get_metadata(PositionProvider, original_node)
            target = (position.start.line, position.start.column)
            if target not in targets or _has_timeout(updated_node):
                return updated_node
            return updated_node.with_changes(
                args=[
                    *updated_node.args,
                    cst.Arg(
                        cst.Integer(str(seconds)),
                        keyword=cst.Name("timeout"),
                    ),
                ]
            )

    transformed = cst.MetadataWrapper(module).visit(AddTimeout())
    assert isinstance(transformed, cst.Module)
    return transformed


def _has_timeout(call: cst.Call) -> bool:
    return any(
        argument.keyword is not None and argument.keyword.value == "timeout"
        for argument in call.args
    )
