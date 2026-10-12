"""AG011: detect state collections that grow on every cycle."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class UnboundedStateGrowthRule(Rule):
    """Report repeated message/state appends without a retention policy."""

    rule_id = "AG011"
    name = "unbounded-state-growth"
    description = "Agent state collections grow inside loops without trimming."
    default_severity = Severity.WARNING

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for location in module.state_growths:
                yield finding(
                    self.rule_id,
                    location,
                    "Agent state collection grows inside a loop.",
                    "Unbounded message history increases memory and LLM prompt cost.",
                    "Trim, summarize, or cap the collection before the next cycle.",
                )
