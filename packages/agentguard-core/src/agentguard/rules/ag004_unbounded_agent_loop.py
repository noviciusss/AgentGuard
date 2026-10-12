"""AG004: detect agent graph cycles without an iteration bound."""

from collections.abc import Iterable

from agentguard.findings import Finding, Severity
from agentguard.rules.base import Rule, RuleContext
from agentguard.rules.phase3_common import finding


class UnboundedAgentLoopRule(Rule):
    """Report cyclic agent graphs without a configured run limit."""

    rule_id = "AG004"
    name = "unbounded-agent-loop"
    description = "Agent graph cycles without a recursion or iteration limit."
    default_severity = Severity.ERROR

    def check(self, context: RuleContext) -> Iterable[Finding]:
        for module in context.system.modules:
            for graph in module.graphs:
                if graph.cycle_nodes and graph.iteration_limit is None:
                    yield finding(
                        self.rule_id,
                        graph.loc,
                        "Agent graph contains a cycle without an iteration limit.",
                        "A cyclic graph can run indefinitely and consume unbounded "
                        "resources.",
                        "Set recursion_limit, max_iter, or max_round for the graph.",
                        severity=Severity.ERROR,
                    )
