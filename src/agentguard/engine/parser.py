"""Safe Python source parsing for the scan engine."""

from __future__ import annotations

import ast
import tokenize
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedModule:
    """An AST and source representation for one Python file."""

    path: Path
    tree: ast.Module
    source: str
    source_lines: tuple[str, ...]

    @property
    def lines(self) -> tuple[str, ...]:
        """Return source lines as a convenient short alias."""
        return self.source_lines


ParsedFile = ParsedModule


class ParseError(ValueError):
    """A source file could not be read or parsed."""

    def __init__(
        self,
        path: Path,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
    ) -> None:
        self.path = path
        self.message = message
        self.line = line
        self.col = col
        location = f":{line}:{col}" if line is not None and col is not None else ""
        super().__init__(f"{path}{location}: {message}")


def parse_file(path: Path) -> ParsedModule:
    """Read and parse *path*, raising :class:`ParseError` on failure."""
    try:
        with tokenize.open(path) as source_file:
            source = source_file.read()
    except OSError as error:
        raise ParseError(path, str(error)) from error
    except (UnicodeError, SyntaxError) as error:
        raise ParseError(path, f"invalid source encoding: {error}") from error
    return parse_source(source, path)


def parse_source(source: str, path: Path | None = None) -> ParsedModule:
    """Parse source text and retain its original lines for locations/snippets."""
    source_path = path if path is not None else Path("<string>")
    try:
        tree = ast.parse(
            source,
            filename=str(source_path),
            mode="exec",
            type_comments=True,
        )
    except SyntaxError as error:
        line = error.lineno
        col = error.offset - 1 if error.offset is not None else None
        raise ParseError(
            source_path,
            error.msg,
            line=line,
            col=col,
        ) from error
    except ValueError as error:
        raise ParseError(source_path, str(error)) from error
    return ParsedModule(source_path, tree, source, tuple(source.splitlines()))
