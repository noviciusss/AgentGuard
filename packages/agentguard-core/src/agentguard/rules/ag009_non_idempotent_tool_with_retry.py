"""AG009: detect dangerous tools invoked in retryable code."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import dangerous_tool_name, finding


class NonIdempotentToolWithRetryRule(Rule):
    """Report likely non-idempotent tool calls inside retry loops."""

    rule_id = "AG009"
    name = "non-idempotent-tool-with-retry"
    description = "Non-idempotent tool calls repeated without an idempotency guard."
    default_severity = Severity.ERROR

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for call in module.call_sites:
                if (
                    call.kind == "tool"
                    and call.in_loop
                    and dangerous_tool_name(call.qualified_name)
                    and "idempotency_key" not in call.kwargs
                ):
                    yield finding(
                        self.rule_id,
                        call.loc,
                        "Non-idempotent tool call is inside a retryable loop.",
                        "A retry can repeat a payment, deletion, write, or message "
                        "send.",
                        "Use an idempotency key or make the operation explicitly "
                        "idempotent.",
                        severity=Severity.ERROR,
                    )
