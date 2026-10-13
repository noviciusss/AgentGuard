"""Safe AG010 model-alias transformations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

import libcst as cst
from libcst.metadata import PositionProvider

from agentguard.findings import Finding
from agentguard.fixes.engine import FixEngine, FixResult


def preview_model_pin_fixes(
    path: Path,
    source: str,
    findings: Iterable[Finding],
    model_map: Mapping[str, str],
) -> FixResult | None:
    """Preview literal AG010 replacements configured by the user."""
    targets = {
        (finding.loc.line, finding.loc.col)
        for finding in findings
        if finding.rule_id == "AG010"
    }
    if not targets or not model_map:
        return None
    return FixEngine().preview(
        path,
        source,
        lambda module: _pin_models(module, targets, model_map),
    )


def _pin_models(
    module: cst.Module,
    targets: set[tuple[int, int]],
    model_map: Mapping[str, str],
) -> cst.Module:
    class PinModel(cst.CSTTransformer):
        METADATA_DEPENDENCIES = (PositionProvider,)

        def leave_Call(
            self, original_node: cst.Call, updated_node: cst.Call
        ) -> cst.Call:
            position = self.get_metadata(PositionProvider, original_node)
            if (position.start.line, position.start.column) not in targets:
                return updated_node
            args = list(updated_node.args)
            for index, argument in enumerate(args):
                if argument.keyword is None or argument.keyword.value != "model":
                    continue
                if not isinstance(argument.value, cst.SimpleString):
                    return updated_node
                current = _string_value(argument.value)
                replacement = model_map.get(current)
                if replacement is None:
                    return updated_node
                args[index] = argument.with_changes(
                    value=cst.SimpleString(repr(replacement))
                )
                return updated_node.with_changes(args=args)
            return updated_node

    transformed = cst.MetadataWrapper(module).visit(PinModel())
    assert isinstance(transformed, cst.Module)
    return transformed


def _string_value(value: cst.SimpleString) -> str:
    evaluated = value.evaluated_value
    return evaluated if isinstance(evaluated, str) else ""
