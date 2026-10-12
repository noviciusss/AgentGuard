"""AG008: detect tool exceptions that are silently swallowed."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class ExceptionSwallowedInToolRule(Rule):
    """Report tool handlers that catch failures without observability."""

    rule_id = "AG008"
    name = "exception-swallowed-in-tool"
    description = "Tool exceptions caught without logging, propagation, or fallback."
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            tool_functions = {
                call.enclosing_function
                for call in module.call_sites
                if call.kind == "tool"
            }
            for fact in module.exception_facts:
                if fact.function not in tool_functions:
                    continue
                if (
                    not fact.has_raise
                    and not fact.has_logging
                    and not fact.has_fallback
                ):
                    yield finding(
                        self.rule_id,
                        fact.loc,
                        "Tool exception is caught and silently discarded.",
                        "Hidden tool failures make the agent appear successful when "
                        "work failed.",
                        "Log the error, return an explicit fallback, or re-raise it.",
                    )
