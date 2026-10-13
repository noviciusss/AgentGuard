"""Safe, deterministic source transformation support built on LibCST."""

from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import libcst as cst

ModuleTransform = Callable[[cst.Module], cst.Module]


class FixError(ValueError):
    """A source file cannot be safely transformed."""


@dataclass(frozen=True)
class FixResult:
    """The result of previewing one source transformation."""

    path: Path
    before: str
    after: str
    changed: bool
    diff: str


class FixEngine:
    """Parse, transform, and diff source without writing files by default."""

    def preview(self, path: Path, source: str, transform: ModuleTransform) -> FixResult:
        """Return a deterministic diff for a LibCST module transformation."""
        try:
            module = cst.parse_module(source)
        except (cst.ParserSyntaxError, ValueError) as error:
            raise FixError(
                f"{path}: cannot parse source for autofix: {error}"
            ) from error
        try:
            updated = transform(module)
        except (TypeError, ValueError) as error:
            raise FixError(f"{path}: autofix transformation failed: {error}") from error
        after = updated.code
        return FixResult(
            path, source, after, source != after, _diff(path, source, after)
        )

    def apply(self, result: FixResult) -> None:
        """Apply a previously previewed changed result explicitly."""
        if result.changed:
            result.path.write_text(result.after, encoding="utf-8")


def _diff(path: Path, before: str, after: str) -> str:
    if before == after:
        return ""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )
