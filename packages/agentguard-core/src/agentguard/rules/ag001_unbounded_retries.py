"""AG001: detect retry and loop constructs without an attempt/time bound."""

from __future__ import annotations

from collections.abc import Iterable

from agentguard.findings import Confidence, Finding, Severity
from agentguard.ir.models import CallSite
from agentguard.rules.base import Rule, RuleContext


class UnboundedRetriesRule(Rule):
    """Report unbounded retries around fallible agent operations."""

    rule_id = "AG001"
    name = "unbounded-retries"
    description = "Retry and loop constructs without a maximum attempt or time bound."
    default_severity = Severity.ERROR

    def check(self, context: RuleContext) -> Iterable[Finding]:
        """Inspect normalized loop facts and retry-related call metadata."""
        for module in context.system.modules:
            for loop in module.loops:
                if loop.has_bound is True:
                    continue
                calls = [call for call in loop.calls_inside if _fallible(call)]
                if not calls:
                    continue
                call = calls[0]
                confidence = (
                    Confidence.HIGH if loop.has_bound is False else Confidence.MEDIUM
                )
                severity = Severity.ERROR if call.kind == "llm" else Severity.WARNING
                yield Finding(
                    rule_id=self.rule_id,
                    severity=severity,
                    confidence=confidence,
                    message="Retry loop has no maximum attempts or time budget.",
                    why=(
                        "A persistent failure can burn tokens and hammer a failing "
                        "service."
                    ),
                    suggestion=(
                        "Add a bounded attempt counter or "
                        "stop_after_attempt/stop_after_delay."
                    ),
                    loc=loop.loc,
                    related=(call.loc,),
                )
            for call in module.call_sites:
                max_retries = call.kwargs.get("max_retries")
                if max_retries is None or not max_retries.is_literal:
                    continue
                if isinstance(max_retries.value, int) and max_retries.value > 10:
                    yield Finding(
                        rule_id=self.rule_id,
                        severity=Severity.WARNING,
                        confidence=Confidence.MEDIUM,
                        message="max_retries is greater than 10.",
                        why=(
                            "Large retry limits can amplify cost and provider pressure."
                        ),
                        suggestion=(
                            "Use a bounded retry policy with backoff and a lower "
                            "maximum."
                        ),
                        loc=call.loc,
                    )


def _fallible(call: CallSite) -> bool:
    return call.kind in {"llm", "http", "tool"}
