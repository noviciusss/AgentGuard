"""AG005: detect repeated LLM calls without a token budget."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class NoCostBudgetRule(Rule):
    """Report LLM calls inside repeated execution without max tokens."""

    rule_id = "AG005"
    name = "no-cost-budget"
    description = "Repeated LLM calls without a max_tokens budget."
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for call in module.call_sites:
                if (
                    call.kind == "llm"
                    and call.in_loop
                    and call.max_tokens is None
                    and "max_tokens" not in call.kwargs
                    and "**" not in call.kwargs
                ):
                    yield finding(
                        self.rule_id,
                        call.loc,
                        "LLM call inside a loop has no token budget.",
                        "Repeated unbounded responses can multiply token cost.",
                        "Pass max_tokens or configure an equivalent provider budget.",
                    )
