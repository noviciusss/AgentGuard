"""Deterministic registry for built-in and future plugin rules."""

from __future__ import annotations

import fnmatch
from collections.abc import Iterable
from typing import TypeAlias

from agentguard.findings import Finding, sort_findings
from agentguard.rules.base import RULE_ID_PATTERN, Rule, RuleContext, RuleDescriptor

RuleClass: TypeAlias = type[Rule]


class RuleRegistrationError(ValueError):
    """A rule cannot be registered because its metadata is invalid."""


class RuleRegistry:
    """Store rule classes by ID and execute selected rules deterministically."""

    def __init__(self, rules: Iterable[RuleClass] = ()) -> None:
        self._rules: dict[str, RuleClass] = {}
        self.register_many(rules)

    def register(self, rule: RuleClass) -> None:
        """Register one rule class, rejecting invalid or duplicate IDs."""
        if not isinstance(rule, type) or not issubclass(rule, Rule):
            raise RuleRegistrationError("registered value must be a Rule subclass")
        try:
            descriptor = rule.descriptor()
        except AttributeError as error:
            raise RuleRegistrationError(
                "rule must define rule_id, name, and description"
            ) from error
        if RULE_ID_PATTERN.fullmatch(descriptor.rule_id) is None:
            raise RuleRegistrationError(
                f"invalid rule ID {descriptor.rule_id!r}; expected AG followed by "
                "3 digits"
            )
        if not descriptor.name.strip() or not descriptor.description.strip():
            raise RuleRegistrationError(
                f"rule {descriptor.rule_id} must define non-empty name and description"
            )
        if descriptor.rule_id in self._rules:
            raise RuleRegistrationError(f"duplicate rule ID: {descriptor.rule_id}")
        self._rules[descriptor.rule_id] = rule

    def register_many(self, rules: Iterable[RuleClass]) -> None:
        """Register several rule classes in input order."""
        for rule in rules:
            self.register(rule)

    def get(self, rule_id: str) -> RuleClass:
        """Return a registered rule class or raise ``KeyError``."""
        return self._rules[rule_id.upper()]

    def descriptors(self) -> tuple[RuleDescriptor, ...]:
        """Return rule metadata sorted by stable rule ID."""
        return tuple(
            self._rules[rule_id].descriptor() for rule_id in sorted(self._rules)
        )

    def select(
        self,
        selected: Iterable[str] = (),
        ignored: Iterable[str] = (),
    ) -> tuple[RuleClass, ...]:
        """Select rules using shell-style IDs such as ``AG00*``."""
        selected_patterns = tuple(pattern.upper() for pattern in selected)
        ignored_patterns = tuple(pattern.upper() for pattern in ignored)
        classes: list[RuleClass] = []
        for rule_id in sorted(self._rules):
            selected_match = not selected_patterns or any(
                fnmatch.fnmatchcase(rule_id, pattern) for pattern in selected_patterns
            )
            ignored_match = any(
                fnmatch.fnmatchcase(rule_id, pattern) for pattern in ignored_patterns
            )
            if selected_match and not ignored_match:
                classes.append(self._rules[rule_id])
        return tuple(classes)

    def run(
        self,
        context: RuleContext,
        *,
        selected: Iterable[str] = (),
        ignored: Iterable[str] = (),
    ) -> list[Finding]:
        """Run selected rules and return globally sorted findings."""
        findings: list[Finding] = []
        for rule_class in self.select(selected, ignored):
            findings.extend(rule_class().run(context))
        return sort_findings(findings)
