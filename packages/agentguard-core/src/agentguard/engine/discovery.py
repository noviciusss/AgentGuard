"""Deterministic Python-file discovery with excludes and nested ignore files."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path


@dataclass(frozen=True)
class _Pattern:
    base: Path
    text: str
    negated: bool
    anchored: bool
    directory_only: bool


def discover_python_files(
    paths: Iterable[Path],
    *,
    excludes: Iterable[str] = (),
    root: Path | None = None,
) -> list[Path]:
    """Return sorted Python files under *paths* that are not ignored.

    Paths are returned as normalized absolute paths. Ignore files apply from
    the scan root downwards, with nested files taking precedence. Ignored
    directories and symlinks are not traversed. Excludes use the same pattern
    syntax and are relative to the scan root.
    """
    requested = [Path(path) for path in paths]
    if not requested:
        requested = [Path(".")]

    scan_root = _scan_root(requested, root)
    exclude_patterns = _parse_patterns(excludes, scan_root)
    candidates: set[Path] = set()

    @cache
    def directory_rules(directory: Path) -> tuple[_Pattern, ...] | None:
        if directory == scan_root:
            return _read_gitignore(directory)
        inherited = directory_rules(directory.parent)
        if inherited is None or _is_ignored(directory, True, inherited):
            return None
        if _is_ignored(directory, True, exclude_patterns):
            return None
        return (*inherited, *_read_gitignore(directory))

    def collect(path: Path, rules: tuple[_Pattern, ...]) -> None:
        if path.suffix != ".py" or path.is_symlink() or not path.is_file():
            return
        if not _is_ignored(path, False, rules) and not _is_ignored(
            path, False, exclude_patterns
        ):
            candidates.add(path)

    for requested_path in requested:
        normalized = requested_path.resolve()
        if not normalized.exists():
            raise FileNotFoundError(normalized)
        if not normalized.is_relative_to(scan_root):
            raise ValueError(f"scan path {normalized} is outside root {scan_root}")
        if normalized.is_dir():
            if directory_rules(normalized) is None:
                continue
            for current, directories, filenames in os.walk(
                normalized, onerror=_raise_walk_error
            ):
                current_path = Path(current)
                rules = directory_rules(current_path)
                if rules is None:
                    directories[:] = []
                    continue
                directories[:] = [
                    name
                    for name in directories
                    if name != ".git"
                    and not (current_path / name).is_symlink()
                    and directory_rules(current_path / name) is not None
                ]
                for filename in filenames:
                    collect(current_path / filename, rules)
        else:
            rules = directory_rules(normalized.parent)
            if rules is not None:
                collect(normalized, rules)

    return sorted(candidates, key=lambda path: path.as_posix())


def _raise_walk_error(error: OSError) -> None:
    raise error


def _scan_root(paths: list[Path], root: Path | None) -> Path:
    if root is not None:
        return root.resolve()
    if len(paths) == 1:
        candidate = paths[0].resolve()
        return candidate if candidate.is_dir() else candidate.parent
    common = os.path.commonpath([str(path.resolve()) for path in paths])
    common_path = Path(common)
    return common_path if common_path.is_dir() else common_path.parent


def _read_gitignore(root: Path) -> tuple[_Pattern, ...]:
    gitignore = root / ".gitignore"
    try:
        contents = gitignore.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ()
    return _parse_patterns(contents.splitlines(), root)


def _parse_patterns(lines: Iterable[str], base: Path) -> tuple[_Pattern, ...]:
    patterns = []
    for line in lines:
        text = line.rstrip()
        if not text or text.startswith("#"):
            continue
        negated = text.startswith("!")
        if negated:
            text = text[1:]
        if text.startswith((r"\!", r"\#")):
            text = text[1:]
        anchored = text.startswith("/")
        directory_only = text.endswith("/")
        text = text.strip("/")
        if text:
            patterns.append(_Pattern(base, text, negated, anchored, directory_only))
    return tuple(patterns)


def _is_ignored(path: Path, is_directory: bool, patterns: Iterable[_Pattern]) -> bool:
    ignored = False
    for pattern in patterns:
        if pattern.directory_only and not is_directory:
            continue
        relative = path.relative_to(pattern.base)
        if pattern.anchored or "/" in pattern.text:
            matches = _match_parts(tuple(pattern.text.split("/")), relative.parts)
        else:
            matches = fnmatch.fnmatchcase(relative.name, pattern.text)
        if matches:
            ignored = not pattern.negated
    return ignored


def _match_parts(pattern: tuple[str, ...], path: tuple[str, ...]) -> bool:
    if not pattern:
        return not path
    if pattern[0] == "**":
        return any(
            _match_parts(pattern[1:], path[index:]) for index in range(len(path) + 1)
        )
    return (
        bool(path)
        and fnmatch.fnmatchcase(path[0], pattern[0])
        and _match_parts(pattern[1:], path[1:])
    )
