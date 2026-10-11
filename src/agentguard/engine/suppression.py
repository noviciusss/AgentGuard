"""Inline and file-level finding suppressions."""

from __future__ import annotations

import io
import re
import tokenize
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from agentguard.findings import Finding

_SUPPRESSION_RE = re.compile(
    r"^#\s*agentguard:\s*(?P<directive>ignore(?:-file)?)"
    r"(?:\[\s*(?P<rules>AG[0-9]{3}(?:\s*,\s*AG[0-9]{3})*)\s*\])?"
    r"(?:\s+reason:\s*.*)?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Suppressions:
    """Parsed suppressions for one source file."""

    file_rules: frozenset[str] = frozenset()
    file_all: bool = False
    line_rules: dict[int, frozenset[str]] = field(default_factory=dict)
    line_all: frozenset[int] = frozenset()

    def is_suppressed(self, rule_id: str, line: int) -> bool:
        """Return whether *rule_id* is suppressed on *line*."""
        normalized_rule = rule_id.upper()
        return (
            self.file_all
            or normalized_rule in self.file_rules
            or line in self.line_all
            or normalized_rule in self.line_rules.get(line, frozenset())
        )


def parse_suppressions(source: str) -> Suppressions:
    """Parse inline suppressions and file suppressions in the first ten lines."""
    file_rules: set[str] = set()
    file_all = False
    line_rules: dict[int, frozenset[str]] = {}
    line_all: set[int] = set()

    for line_number, comment in _comments(source):
        match = _SUPPRESSION_RE.fullmatch(comment)
        if match is None:
            continue
        raw_rules = match.group("rules")
        rules = (
            frozenset(rule.strip().upper() for rule in raw_rules.split(","))
            if raw_rules is not None
            else frozenset()
        )
        if match.group("directive").lower() == "ignore-file":
            if line_number > 10:
                continue
            if raw_rules is None:
                file_all = True
            else:
                file_rules.update(rules)
            continue
        if raw_rules is None:
            line_all.add(line_number)
        else:
            line_rules[line_number] = rules

    return Suppressions(
        file_rules=frozenset(file_rules),
        file_all=file_all,
        line_rules=line_rules,
        line_all=frozenset(line_all),
    )


def filter_suppressed(
    findings: Iterable[Finding], suppressions: Suppressions
) -> list[Finding]:
    """Remove findings covered by a parsed suppression set."""
    return [
        finding
        for finding in findings
        if not suppressions.is_suppressed(finding.rule_id, finding.loc.line)
    ]


def _comments(source: str) -> Iterator[tuple[int, str]]:
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                yield token.start[0], token.string
    except (tokenize.TokenError, IndentationError):
        # Invalid files are rejected by the parser; retain only complete comments.
        return
